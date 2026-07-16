"""Tests for the File System Manager."""
from __future__ import annotations
from pathlib import Path
import pytest
from lexkit.core.scanner import extract_metadata, scan_directory, compute_sha256
from lexkit.tools.fsm import _guess_topic

class TestFileMetadata:
    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "Smith_2024_NLP.txt"; f.write_text("hello")
        m = extract_metadata(f, compute_hash=False)
        assert m.year == "2024"; assert m.suffix == ".txt"

    def test_sha256_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"; f.write_text("content")
        assert compute_sha256(f) == compute_sha256(f)
        assert len(compute_sha256(f)) == 64

    def test_no_year(self, tmp_path: Path) -> None:
        f = tmp_path / "random.txt"; f.write_text("x")
        assert extract_metadata(f, compute_hash=False).year is None

class TestScanDirectory:
    def test_finds_supported(self, tmp_path: Path) -> None:
        (tmp_path/"a.txt").write_text("t"); (tmp_path/"b.exe").write_text("b")
        r = scan_directory(tmp_path, compute_hashes=False)
        assert any(x.name=="a.txt" for x in r)
        assert not any(x.name=="b.exe" for x in r)

    def test_detects_duplicates(self, tmp_path: Path) -> None:
        c = "same content"
        (tmp_path/"orig.txt").write_text(c); (tmp_path/"copy.txt").write_text(c)
        r = scan_directory(tmp_path, compute_hashes=True)
        assert sum(1 for x in r if x.is_duplicate) == 1

    def test_empty(self, tmp_path: Path) -> None:
        assert scan_directory(tmp_path) == []

class TestGuessTopic:
    def test_nlp(self)   -> None: assert _guess_topic("bert_nlp_2024") == "nlp"
    def test_graph(self) -> None: assert _guess_topic("knowledge_graph") == "knowledge-graphs"
    def test_ml(self)    -> None: assert _guess_topic("deep_neural") == "ml"
    def test_gen(self)   -> None: assert _guess_topic("random_paper") == "general"
