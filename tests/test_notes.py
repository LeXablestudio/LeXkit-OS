"""Tests for Notes Compiler."""
from lexkit.tools.notes import _paras, _hash

class TestParas:
    def test_splits(self)  -> None: assert len(_paras("A\n\nB\n\nC")) == 3
    def test_strips(self)  -> None: assert _paras("  hello  \n\nworld")[0] == "hello"
    def test_empty(self)   -> None: assert _paras("") == []
    def test_no_empties(self) -> None: assert "" not in _paras("A\n\n\n\nB")

class TestHash:
    def test_stable(self)      -> None: assert _hash("test") == _hash("test")
    def test_different(self)   -> None: assert _hash("A") != _hash("B")
    def test_case_insensitive(self) -> None: assert _hash("HELLO") == _hash("hello")
    def test_whitespace(self)  -> None: assert _hash("a b") == _hash("a  b")
