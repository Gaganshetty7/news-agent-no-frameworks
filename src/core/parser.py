import re
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StepType(Enum):
    THOUGHT      = "thought"
    ACTION       = "action"
    OBSERVATION  = "observation"
    FINAL_ANSWER = "final_answer"


@dataclass
class Step:
    type: StepType
    content: str
    tool: Optional[str] = None        # only for ACTION steps
    tool_input: Optional[Any] = None  # only for ACTION steps


class ReActParser:
    """
    Parses raw LLM output into a list of Steps.

    Expected LLM format:
        Thought: I need to calculate something.
        Action: calculator
        Action Input: {"expression": "2 + 2"}

        ...or to finish...

        Thought: I have enough info.
        Final Answer: The answer is 4.
    """

    def parse(self, text: str) -> list[Step]:
        steps = []

        # Final Answer takes priority — check it first
        fa = re.search(
            r"Final\s+Answer\s*:\s*(.+?)$",
            text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )
        if fa:
            # Grab any thoughts before the final answer
            steps += self._extract_thoughts(text[: fa.start()])
            steps.append(Step(
                type=StepType.FINAL_ANSWER,
                content=fa.group(1).strip(),
            ))
            return steps

        # Otherwise extract thoughts and actions in order
        all_steps = self._extract_thoughts(text) + self._extract_actions(text)
        all_steps.sort(key=lambda s: s._pos)

        for s in all_steps:
            del s.__dict__["_pos"]  # remove internal sorting attr

        return all_steps

    def make_observation(self, result: str) -> Step:
        """Wrap a tool result string into an Observation step."""
        return Step(type=StepType.OBSERVATION, content=result)

    # ── private ────────────────────────────────────────────────────────

    def _extract_thoughts(self, text: str) -> list[Step]:
        steps = []
        pattern = re.compile(
            r"Thought\s*:\s*(.+?)(?=\n(?:Action|Observation|Final Answer)|$)",
            re.IGNORECASE | re.DOTALL,
        )
        for m in pattern.finditer(text):
            content = m.group(1).strip()
            if content:
                s = Step(type=StepType.THOUGHT, content=content)
                s._pos = m.start()
                steps.append(s)
        return steps

    def _extract_actions(self, text: str) -> list[Step]:
        steps = []
        action_pattern = re.compile(
            r"Action\s*:\s*(.+?)$", re.IGNORECASE | re.MULTILINE
        )
        for m in action_pattern.finditer(text):
            tool_name = m.group(1).strip()

            # Look for Action Input immediately after this Action line
            remainder = text[m.end():]
            input_match = re.search(
                r"Action\s+Input\s*:\s*(.+?)(?=\n(?:Thought|Action|Observation|Final Answer)|$)",
                remainder,
                re.IGNORECASE | re.DOTALL,
            )
            raw_input = input_match.group(1).strip() if input_match else ""
            tool_input = self._parse_input(raw_input)

            s = Step(
                type=StepType.ACTION,
                content=f"{tool_name}: {raw_input}",
                tool=tool_name,
                tool_input=tool_input,
            )
            s._pos = m.start()
            steps.append(s)
        return steps

    def _parse_input(self, raw: str) -> Any:
        """Try JSON first, fall back to plain string."""
        raw = raw.strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
