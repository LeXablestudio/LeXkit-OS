"""Tests for the LLM layer — off-by-default, NullLLM, parse_jsonl."""

import os
import pytest
from lexkit.llm import (
    get_llm,
    NullLLM,
    LLMUnavailableError,
    parse_jsonl,
    reset_llm_cache,
)
from lexkit.llm.base import LLMBackend


class TestNullLLM:
    def test_not_available(self):
        llm = NullLLM()
        assert llm.is_available() is False

    def test_complete_raises(self):
        llm = NullLLM()
        with pytest.raises(LLMUnavailableError):
            llm.complete("prompt")

    def test_extract_returns_empty(self):
        llm = NullLLM()
        assert llm.extract("prompt") == []

    def test_name(self):
        assert NullLLM().name == "null"


class TestGetLlm:
    def test_default_is_null(self):
        """Without env vars, get_llm returns NullLLM."""
        os.environ.pop("LEXKIT_LLM_BASE_URL", None)
        os.environ.pop("LEXKIT_LLM_API_KEY", None)
        reset_llm_cache()
        llm = get_llm()
        assert isinstance(llm, NullLLM)

    def test_cached(self):
        """Same instance returned on repeated calls."""
        reset_llm_cache()
        a = get_llm()
        b = get_llm()
        assert a is b

    def test_reset(self):
        reset_llm_cache()
        a = get_llm()
        reset_llm_cache()
        b = get_llm()
        # After reset, we still get NullLLM (no env configured) but a new instance.
        assert isinstance(a, NullLLM)
        assert isinstance(b, NullLLM)


class TestParseJsonl:
    def test_clean(self):
        result = parse_jsonl('{"a": 1}\n{"b": 2}')
        assert result == [{"a": 1}, {"b": 2}]

    def test_embedded_in_prose(self):
        result = parse_jsonl('Here are results: {"a": 1} and {"b": 2}.')
        assert result == [{"a": 1}, {"b": 2}]

    def test_malformed_skipped(self):
        result = parse_jsonl('{"a": 1} {bad} {"c": 3}')
        assert len(result) == 2
        assert result[0] == {"a": 1}

    def test_empty(self):
        assert parse_jsonl("") == []

    def test_no_objects(self):
        assert parse_jsonl("just text") == []
