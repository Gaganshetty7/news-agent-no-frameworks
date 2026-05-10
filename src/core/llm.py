from abc import ABC, abstractmethod
import logging
import os
import time
from typing import Optional


logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# Abstract base — every client must implement complete()
# ══════════════════════════════════════════════════════════════════════

class LLMClient(ABC):
    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str: ...


# ══════════════════════════════════════════════════════════════════════
# Gemini client — raw HTTP, no SDK
# ══════════════════════════════════════════════════════════════════════

class GeminiClient(LLMClient):
    """
    Calls the Gemini generateContent endpoint directly.
    Docs: https://ai.google.dev/api/generate-content
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    # Constructor
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.1-flash-lite",
    ):
        import requests
        self._requests = requests

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY in your .env file."
            )
        self.model = model

    def complete(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        url = f"{self.BASE_URL}/{self.model}:generateContent?key={self.api_key}"

        # Gemini uses "contents" with "parts" instead of OpenAI-style messages
        contents = self._convert_messages(messages)

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        # system_instruction uses a different Gemini schema than chat messages, so we format it to gemini's format separately
        # _convert_messages() adds roles ("user"/"model"), but system_instruction only needs "parts".
        if system:
            payload["system_instruction"] = {
                "parts": [{"text": system}]
            }


        logger.debug(f"[Gemini] POST model={self.model}")
        t0 = time.time()

        resp = self._requests.post(url, json=payload, timeout=120)

        logger.debug(f"[Gemini] Response in {time.time() - t0:.2f}s status={resp.status_code}")

        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

        data = resp.json()
        return self._extract_text(data)
    
    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """
        Convert from standard {role, content} format to Gemini's
        {role, parts: [{text}]} format.
        Gemini uses "user" and "model" (not "assistant").
        """
        converted = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            converted.append({
                "role": role,
                "parts": [{"text": m["content"]}],
            })
        return converted

    def _extract_text(self, data: dict) -> str:
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Gemini response shape: {data}") from e

# ══════════════════════════════════════════════════════════════════════
# Mock client — for testing without any API calls
# ══════════════════════════════════════════════════════════════════════

class MockLLMClient(LLMClient):
    """
    Returns scripted responses in order.
    Perfect for unit tests — deterministic, instant, free.
    """

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._index = 0

    def complete(self, messages, system="", temperature=0.0, max_tokens=4096) -> str:
        if self._index >= len(self._responses):
            return "Final Answer: No more scripted responses."
        response = self._responses[self._index]
        self._index += 1
        logger.debug(f"[MockLLM] Returning response #{self._index}")
        return response

    def reset(self):
        self._index = 0


# ══════════════════════════════════════════════════════════════════════
# Factory — one function to create any client
# ══════════════════════════════════════════════════════════════════════

def create_llm_client(provider: str = "gemini", **kwargs) -> LLMClient:
    """
    Usage:
        client = create_llm_client("gemini")
        client = create_llm_client("mock", responses=["Final Answer: 42"])
    """

    # If adding more providers in the future, just add them here and implement their client classes above.
    providers = {
        "gemini": GeminiClient,
        "mock": MockLLMClient,
    }
    cls = providers.get(provider.lower())
    if cls is None:
        raise ValueError(f"Unknown provider: {provider!r}. Choose from {list(providers)}")
    return cls(**kwargs)
