"""Tests for the structured logger — lexkit/logging.py"""

from __future__ import annotations

import json
from pathlib import Path

from lexkit.logging import Logger, get_logger, configure, _now_utc


class TestNowUtc:
    def test_format(self) -> None:
        ts = _now_utc()
        assert ts.endswith("Z")
        assert "T" in ts

    def test_deterministic_format(self) -> None:
        # Two calls produce the same format
        ts1, ts2 = _now_utc(), _now_utc()
        assert len(ts1) == len(ts2)
        assert ts1[:10] == ts2[:10]  # same date prefix


class TestLogger:
    def _make_logger(self, tmp_path: Path) -> Logger:
        log_file = tmp_path / "test.log"
        configure(log_path=log_file, level="DEBUG")
        return get_logger("test_tool")

    def test_info_writes_record(self, tmp_path: Path) -> None:
        log      = self._make_logger(tmp_path)
        log_file = tmp_path / "test.log"
        log.info("test_event", files=42)
        lines = log_file.read_text().strip().splitlines()
        record = json.loads(lines[-1])
        assert record["level"]  == "INFO"
        assert record["event"]  == "test_event"
        assert record["tool"]   == "test_tool"
        assert record["files"]  == 42

    def test_error_writes_record(self, tmp_path: Path) -> None:
        log      = self._make_logger(tmp_path)
        log_file = tmp_path / "test.log"
        log.error("something_failed", error_code="E001")
        record = json.loads(log_file.read_text().strip().splitlines()[-1])
        assert record["level"]      == "ERROR"
        assert record["error_code"] == "E001"

    def test_record_has_ts_field(self, tmp_path: Path) -> None:
        log      = self._make_logger(tmp_path)
        log_file = tmp_path / "test.log"
        log.info("ts_check")
        record = json.loads(log_file.read_text().strip().splitlines()[-1])
        assert "ts" in record
        assert record["ts"].endswith("Z")

    def test_exception_logging(self, tmp_path: Path) -> None:
        from lexkit.errors import LexKitScanError
        log      = self._make_logger(tmp_path)
        log_file = tmp_path / "test.log"
        exc      = LexKitScanError("bad path", context={"path": "/missing"})
        log.exception("scan_error", exc, tool="fsm")
        record = json.loads(log_file.read_text().strip().splitlines()[-1])
        assert record["error_code"] == "E001"
        assert "E001" in record.get("error_code","")

    def test_valid_json_lines(self, tmp_path: Path) -> None:
        log      = self._make_logger(tmp_path)
        log_file = tmp_path / "test.log"
        for i in range(5):
            log.info(f"event_{i}", index=i)
        for line in log_file.read_text().strip().splitlines():
            json.loads(line)  # must not raise
