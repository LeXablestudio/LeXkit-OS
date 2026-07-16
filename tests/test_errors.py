"""Tests for the error taxonomy — lexkit/errors.py"""

from __future__ import annotations

import pytest
from lexkit.errors import (
    LexKitError, LexKitScanError, LexKitCleanError,
    LexKitSearchError, LexKitDatabaseError, LexKitPluginError,
    LexKitPipelineError, wrap,
)


class TestErrorCodes:
    def test_base_code(self)     -> None: assert LexKitError.code          == "E000"
    def test_scan_code(self)     -> None: assert LexKitScanError.code      == "E001"
    def test_clean_code(self)    -> None: assert LexKitCleanError.code     == "E002"
    def test_search_code(self)   -> None: assert LexKitSearchError.code    == "E003"
    def test_db_code(self)       -> None: assert LexKitDatabaseError.code  == "E004"
    def test_plugin_code(self)   -> None: assert LexKitPluginError.code    == "E005"
    def test_pipeline_code(self) -> None: assert LexKitPipelineError.code  == "E006"


class TestLexKitError:
    def test_message(self) -> None:
        exc = LexKitError("something went wrong")
        assert "something went wrong" in str(exc)

    def test_code_in_str(self) -> None:
        exc = LexKitScanError("bad path")
        assert "E001" in str(exc)

    def test_context_in_str(self) -> None:
        exc = LexKitError("msg", context={"path": "/tmp"})
        assert "/tmp" in str(exc)

    def test_to_dict(self) -> None:
        exc = LexKitDatabaseError("db failure", context={"table": "files"})
        d   = exc.to_dict()
        assert d["error_code"] == "E004"
        assert "files" in d["context"].values()

    def test_default_message(self) -> None:
        exc = LexKitScanError()
        assert exc.message  # non-empty default

    def test_cause_preserved(self) -> None:
        cause = ValueError("root cause")
        exc   = LexKitCleanError("wrap", cause=cause)
        assert exc.cause is cause

    def test_hierarchy(self) -> None:
        assert issubclass(LexKitScanError,     LexKitError)
        assert issubclass(LexKitDatabaseError, LexKitError)
        assert issubclass(LexKitPluginError,   LexKitError)


class TestWrapContextManager:
    def test_wrap_converts_stdlib(self) -> None:
        with pytest.raises(LexKitDatabaseError):
            with wrap(LexKitDatabaseError, context={"op": "read"}):
                raise OSError("disk read error")

    def test_wrap_passes_lexkit_errors_through(self) -> None:
        with pytest.raises(LexKitScanError):
            with wrap(LexKitDatabaseError):
                raise LexKitScanError("already typed")

    def test_wrap_no_exception(self) -> None:
        with wrap(LexKitPipelineError):
            x = 1 + 1
        assert x == 2

    def test_wrap_context_propagated(self) -> None:
        try:
            with wrap(LexKitSearchError, context={"index": "papers"}):
                raise RuntimeError("index broken")
        except LexKitSearchError as exc:
            assert exc.context.get("index") == "papers"
