"""LLM backend registry and factory.

Resolution order for :func:`get_llm`:

1. ``settings.llm_backend`` if explicitly set to a known backend.
2. Environment configuration — if ``LEXKIT_LLM_BASE_URL`` and
   ``LEXKIT_LLM_API_KEY`` are both present, the OpenAI-compatible backend is
   selected.
3. Otherwise → :class:`NullLLM` (LeXKit stays offline & deterministic).

A cached singleton avoids re-reading the environment on every call.
"""

from __future__ import annotations

from functools import lru_cache

from lexkit.llm.base import LLMBackend, NullLLM
from lexkit.logging import get_logger

log = get_logger("llm")


@lru_cache(maxsize=1)
def get_llm() -> LLMBackend:
    """Return the active LLM backend (cached). Defaults to :class:`NullLLM`."""
    # Imported lazily to keep settings optional at import time.
    try:
        from lexkit.config.settings import Settings
        settings = Settings.load_default()
        backend = (settings.llm_backend or "").strip().lower()
        model = settings.llm_model or None
    except Exception:  # noqa: BLE001 — settings must never block the LLM layer
        backend, model = "", None

    if backend == "openai-compat" or (backend == "" and _env_configured()):
        from lexkit.llm.openai_compat import OpenAICompatibleLLM
        client = OpenAICompatibleLLM(model=model)
        if client.is_available():
            log.info("llm_backend_active", backend=client.name, model=client.model)
            return client
        log.warning("llm_backend_unavailable", backend="openai-compat")

    # Default: offline, deterministic, zero cost.
    return NullLLM()


def reset_llm_cache() -> None:
    """Clear the cached backend. Useful after changing settings in-process."""
    get_llm.cache_clear()


def _env_configured() -> bool:
    import os
    return bool(os.environ.get("LEXKIT_LLM_BASE_URL") and os.environ.get("LEXKIT_LLM_API_KEY"))
