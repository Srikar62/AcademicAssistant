"""
LLM client wrapper — provider-agnostic interface for language model calls.

Uses the OpenAI-compatible API format (works with Groq, OpenAI, Together,
local vLLM, etc.) so swapping providers is a config change, not a code change.

The API key is held server-side (env var) — never exposed to the browser.
"""

import json
import logging
import time
from typing import Optional, List, Dict, Any

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Synchronous LLM client using the OpenAI chat completions format.

    Supports any provider that exposes a /chat/completions endpoint
    (Groq, OpenAI, Together AI, local vLLM, etc.).
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        temperature: float = None,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._temperature = temperature

    @property
    def api_key(self) -> str:
        return self._api_key or settings.LLM_API_KEY

    @property
    def base_url(self) -> str:
        return (self._base_url or settings.LLM_BASE_URL).rstrip("/")

    @property
    def model(self) -> str:
        return self._model or settings.LLM_MODEL

    @property
    def temperature(self) -> float:
        return self._temperature if self._temperature is not None else settings.LLM_TEMPERATURE

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Send a chat completion request and return the assistant's response.
        """
        req_messages = [dict(m) for m in messages]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": req_messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                payload["model"] = self.model
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code in (413, 429) and attempt < max_retries:
                        sleep_time = 4.0 * (attempt + 1)
                        if response.status_code == 413 or "rate_limit_exceeded" in response.text or "TPM" in response.text:
                            logger.warning(
                                "LLM payload/TPM limit hit (status=%d), truncating prompt context (attempt %d/%d)...",
                                response.status_code, attempt + 1, max_retries
                            )
                            for msg in payload["messages"]:
                                if msg.get("role") == "user" and len(msg.get("content", "")) > 1000:
                                    curr = msg["content"]
                                    msg["content"] = curr[:int(len(curr) * 0.6)] + "\n\n...[context truncated to fit token limits]"
                        else:
                            retry_hdr = response.headers.get("retry-after")
                            if retry_hdr and retry_hdr.isdigit():
                                sleep_time = float(retry_hdr) + 1.0
                            logger.warning(
                                "LLM 429 rate limit hit, backing off for %.1fs (attempt %d/%d)...",
                                sleep_time, attempt + 1, max_retries
                            )
                        time.sleep(sleep_time)
                        continue
                    response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(
                    "LLM response: %d tokens (model=%s).",
                    data.get("usage", {}).get("completion_tokens", -1),
                    self.model,
                )
                return content

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (413, 429) and attempt < max_retries:
                    time.sleep(3.0 * (attempt + 1))
                    continue
                logger.error(
                    "LLM API error %d: %s",
                    exc.response.status_code,
                    exc.response.text[:500],
                )
                raise
            except Exception as exc:
                if attempt < max_retries:
                    time.sleep(2.0)
                    continue
                logger.error("LLM call failed: %s", exc)
                raise

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        Send a chat request expecting a JSON response.

        Returns:
            Parsed JSON dict from the LLM response.

        Raises:
            ValueError: If the response isn't valid JSON.
        """
        raw = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("LLM returned invalid JSON: %s", raw[:200])
            raise ValueError(f"LLM response is not valid JSON: {exc}") from exc


# ── Module-level singleton ─────────────────────────────────────
llm_client = LLMClient()
