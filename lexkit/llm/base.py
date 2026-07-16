"""LeXKit optional LLM layer — base contract.

The LLM layer is an *opt-in enrichment* that sits beside the deterministic
analysis core. It is **off by default**: unless explicitly configured, LeXKit
uses the deterministic engine only, preserving full offline, reproducible
behaviour.

Contract
--------
Every backend implements :class:`LLMBackend`:

- :meth:`is_available` — whether the backend can actually serve requests.
- :meth:`complete`     — single prompt -> text.
- :meth:`extract`      — structured enrichment (returns dicts) used by tools
  that want higher-quality citation parsing, keyterm refinement, etc.

When no backend is configured, :class:`NullLLM` is returned: it reports
unavailable and returns empty results, so tool code paths degrade gracefully to
the deterministic fallback without special-casing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMBackend(ABC):
    """Abstract interface for all LLM backends."""

    #: Short identifier e.g. ``"null"``, ``"openai-compat"``.
    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True iff the backend is ready to serve requests."""
        ...

    @abstractmethod
    def complete(self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0) -> str:
        """Return the model's completion for ``prompt``.

        ``temperature`` defaults to 0 for maximum determinism where supported.
        Implementations should raise :class:`LLMUnavailableError` if not ready.
        """
        ...

    def extract(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
    ) -> list[dict[str, Any]]:
        """Return a list of structured records parsed from the completion.

        Default implementation asks for one JSON object per line and parses
        leniently. Backends may override. Returns ``[]`` when unavailable.
        """
        if not self.is_available():
            return []
        raw = self.complete(prompt, max_tokens=max_tokens)
        return parse_jsonl(raw)


class LLMUnavailableError(RuntimeError):
    """Raised when an LLM operation is attempted with no configured backend."""


class NullLLM(LLMBackend):
    """The no-op backend. Always unavailable; always returns empty results.

    This is the default so that every call site can invoke the LLM layer
    unconditionally and simply get deterministic fallback behaviour when no
    provider is configured.
    """

    name = "null"

    def is_available(self) -> bool:
        return False

    def complete(self, prompt: str, *, max_tokens: int = 512, temperature: float = 0.0) -> str:
        raise LLMUnavailableError(
            "No LLM backend is configured. Set LEXKIT_LLM_BASE_URL and "
            "LEXKIT_LLM_API_KEY (or Settings.llm_backend) to enable."
        )


# ── Lenient JSON / JSON-lines parsing of model output ─────────────────────────

def parse_jsonl(text: str) -> list[dict[str, Any]]:
    """Parse zero or more JSON objects out of free-form model text.

    Models often wrap JSON in prose or fences. We scan for ``{...}`` spans and
    parse each. Malformed spans are silently skipped so a single bad line never
    drops the whole result.
    """
    import json

    results: list[dict[str, Any]] = []
    if not text:
        return results
    # Walk braces at depth 1 to capture top-level objects only.
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    chunk = text[start : i + 1]
                    try:
                        obj = json.loads(chunk)
                        if isinstance(obj, dict):
                            results.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = -1
    return results
