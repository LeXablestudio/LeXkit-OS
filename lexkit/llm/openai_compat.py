"""OpenAI-compatible chat backend (stdlib-only HTTP).

Talks to any server that implements the ``POST /v1/chat/completions`` (or
``/chat/completions``) schema. Activated **only** when the user sets:

- ``LEXKIT_LLM_BASE_URL`` (e.g. ``https://api.openai.com/v1``), and
- ``LEXKIT_LLM_API_KEY``.

Uses only :mod:`urllib` from the standard library, so enabling AI enrichment
adds **no new Python dependency**. When unset, :class:`NullLLM` is used and
LeXKit stays fully offline and deterministic.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from lexkit.llm.base import LLMBackend, LLMUnavailableError
from lexkit.logging import get_logger

log = get_logger("llm")

#: Default request timeout (seconds). Keep modest so offline-only users never hang.
_DEFAULT_TIMEOUT = 60


class OpenAICompatibleLLM(LLMBackend):
    """Minimal OpenAI-compatible chat client over stdlib ``urllib``."""

    name = "openai-compat"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.environ.get("LEXKIT_LLM_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("LEXKIT_LLM_API_KEY") or ""
        self.model = model or os.environ.get("LEXKIT_LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    # ── availability ───────────────────────────────────────────────────────────
    def is_available(self) -> bool:
        return bool(self.base_url and self.api_key)

    # ── completion ─────────────────────────────────────────────────────────────
    def complete(self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0) -> str:
        if not self.is_available():
            raise LLMUnavailableError("OpenAI-compatible backend not configured.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = self._endpoint()
        data = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urlerror.URLError as exc:
            log.warning("llm_request_failed", error=str(exc), url=url)
            raise LLMUnavailableError(f"LLM request failed: {exc}") from exc
        try:
            obj = json.loads(body)
            choices = obj.get("choices") or []
            if choices:
                return str(choices[0].get("message", {}).get("content", "")).strip()
        except json.JSONDecodeError as exc:
            log.warning("llm_bad_json", error=str(exc))
        return ""

    def _endpoint(self) -> str:
        """Resolve the chat-completions URL, tolerant of base URL shape."""
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        # Append /v1 only if the base looks bare (no path beyond host).
        parsed = urlparse.urlparse(self.base_url)
        if parsed.path in ("", "/"):
            return f"{self.base_url}/v1/chat/completions"
        return f"{self.base_url}/chat/completions"
