import re
import html
import urllib.parse
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser

from .registry import BaseTool
from ..utils.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


# ── Tool: Company News RSS Feed ───────────────────────────────────────

class CompanyNewsTool(BaseTool):
    name = "company_news"
    description = (
        "Fetch latest stock-related news for a company using Google News RSS.\n"
        "Input: {\"company\": \"Tesla\"}\n"
        "Optional: {\"company\": \"Tesla\", \"limit\": 5}"
    )
    skill_path = "src/skills/company_news.md"
    inject_skill_before = True

    def run(self, tool_input: Any) -> str:
        """
        Fetch and format recent company news.
        """

        # ── Parse Input ──────────────────────────────────────────────

        if isinstance(tool_input, dict):
            company = str(tool_input.get("company", "")).strip()
            limit = int(tool_input.get("limit", 10))
        else:
            company = str(tool_input).strip()
            limit = 10

        if not company:
            raise ToolExecutionError(
                "Missing company name."
            )

        # ── Build RSS URL ───────────────────────────────────────────

        encoded_query = urllib.parse.quote(
            f"{company} stock"
        )

        rss_url = (
            "https://news.google.com/rss/search?"
            f"q={encoded_query}"
            "&hl=en-IN"
            "&gl=IN"
            "&ceid=IN:en"
        )

        logger.info(
            f"[CompanyNewsTool] Fetching news for: {company}"
        )

        # ── Fetch Feed ──────────────────────────────────────────────

        try:
            feed = feedparser.parse(rss_url)

        except Exception as e:
            raise ToolExecutionError(
                f"RSS fetch failed: {e}"
            )

        if not feed.entries:
            return (
                f"No recent news found for {company}."
            )

        # ── Sort by Published Date ─────────────────────────────────

        entries = sorted(
            feed.entries,
            key=self._get_entry_datetime,
            reverse=True,
        )

        # ── Format Output ──────────────────────────────────────────

        output = []

        for entry in entries[:limit]:

            title = self._clean_text(
                getattr(entry, "title", "")
            )

            # Remove trailing source name
            display_title = re.split(
                r" - [^-]+$",
                title
            )[0].strip()

            raw_summary = self._clean_text(
                getattr(entry, "summary", "")
            )

            if (
                len(raw_summary) < 30
                or raw_summary.startswith(display_title[:20])
            ):
                summary = (
                    f"Recent market activity and coverage "
                    f"for {company}."
                )
            else:
                summary = (
                    raw_summary[:250] + "..."
                    if len(raw_summary) > 250
                    else raw_summary
                )

            published = self._get_entry_datetime(
                entry
            ).strftime("%Y-%m-%d %H:%M UTC")

            link = getattr(entry, "link", "")

            output.append(
                (
                    f"Title: {display_title}\n"
                    f"Published: {published}\n"
                    f"Summary: {summary}\n"
                    f"Link: {link}"
                )
            )

        return "\n\n".join(output)

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """
        Remove HTML tags and normalize whitespace.
        """

        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r"<.*?>", "", text)

        # Decode HTML entities
        text = html.unescape(text)

        # Normalize whitespace
        return " ".join(text.split()).strip()

    def _get_entry_datetime(self, entry) -> datetime:
        """
        Extract published datetime safely.
        """

        if (
            hasattr(entry, "published_parsed")
            and entry.published_parsed
        ):
            return datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc,
            )

        return datetime.min.replace(
            tzinfo=timezone.utc
        )
