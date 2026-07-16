"""LeXKit optional LLM enrichment layer.

**Off by default.** LeXKit is deterministic and offline-first; this package adds
an *optional* way to call a large language model for higher-quality tasks
(citation parsing, keyterm refinement). It never runs unless the user opts in by
configuring ``LEXKIT_LLM_BASE_URL`` + ``LEXKIT_LLM_API_KEY`` or
``Settings.llm_backend``.

When inactive, :class:`NullLLM` is returned and all call sites silently fall
back to the deterministic analysis core.

Example
-------
    from lexkit.llm import get_llm
    llm = get_llm()           # NullLLM unless configured
    if llm.is_available():
        answer = llm.complete("Summarise ...")
"""

from lexkit.llm.base import (
    LLMBackend,
    LLMUnavailableError,
    NullLLM,
    parse_jsonl,
)
from lexkit.llm.registry import get_llm, reset_llm_cache

__all__ = [
    "LLMBackend",
    "NullLLM",
    "LLMUnavailableError",
    "parse_jsonl",
    "get_llm",
    "reset_llm_cache",
]
