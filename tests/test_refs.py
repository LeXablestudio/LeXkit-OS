"""Tests for Reference Manager — v2.0 multi-format parsing.

Replaces the v1 test_refs.py which referenced the old `_parse` function.
"""

import pytest
from lexkit.tools.refs import (
    MultiFormatCitationParser,
    parse_citations,
    _clean_author,
    _clean_title,
    _norm,
    _bibtex,
    _apa,
    _mla,
    _chicago,
)


SAMPLE_APA = """
Smith, J. A. (2020). Neural methods for natural language processing.
Journal of AI Research, 45, 1–25.
"""

SAMPLE_MLA = """
Smith, John. "Neural Methods for Natural Language Processing."
Modern Language Review, vol. 115, no. 3, 2020, pp. 400-420.
"""

SAMPLE_CHICAGO = """
Smith, John. 2020. "Neural Methods for Natural Language Processing."
Chicago Journal, 45: 1–25.
"""

SAMPLE_BRACKET = """
[1] Smith, J. A. (2020). Neural methods for natural language processing.
"""

SAMPLE_MULTI = SAMPLE_APA + SAMPLE_MLA + SAMPLE_CHICAGO


class TestMultiFormatParser:
    def test_apa(self):
        refs = MultiFormatCitationParser().parse(SAMPLE_APA)
        assert len(refs) >= 1
        r = refs[0]
        assert "smith" in _norm(r.get("author", ""))
        assert r.get("year") == "2020"

    def test_mla(self):
        refs = MultiFormatCitationParser().parse(SAMPLE_MLA)
        assert len(refs) >= 1
        r = refs[0]
        # MLA: "Smith, John" is the full author field (surname first)
        author = r.get("author") or ""
        assert "smith" in _norm(author) or "john" in _norm(author)

    def test_chicago(self):
        refs = MultiFormatCitationParser().parse(SAMPLE_CHICAGO)
        assert len(refs) >= 1

    def test_bracket(self):
        refs = MultiFormatCitationParser().parse(SAMPLE_BRACKET)
        assert len(refs) >= 1

    def test_empty(self):
        assert MultiFormatCitationParser().parse("") == []

    def test_dedup_across_styles(self):
        """Same reference found by multiple styles should be deduped."""
        refs = MultiFormatCitationParser().parse(SAMPLE_MULTI)
        titles = {r.get("title") for r in refs}
        neural_titles = [t for t in titles if t and "neural" in _norm(t)]
        assert len(neural_titles) <= 1

    def test_determinism(self):
        p = MultiFormatCitationParser()
        a = p.parse(SAMPLE_APA)
        b = p.parse(SAMPLE_APA)
        assert a == b


class TestConvenienceParse:
    def test_parse_citations(self):
        refs = parse_citations(SAMPLE_APA)
        assert len(refs) >= 1


class TestFormatters:
    """Preserved from v1 test suite."""
    R = {"author": "Smith, A.", "year": "2023", "title": "Knowledge Graphs", "doi": "10.1/xyz"}

    def test_bibtex(self):
        assert "@article" in _bibtex(self.R)

    def test_apa(self):
        assert "(2023)" in _apa(self.R)

    def test_mla(self):
        assert "Smith" in _mla(self.R)

    def test_chicago(self):
        assert "2023" in _chicago(self.R)

    def test_deterministic(self):
        assert _bibtex(self.R) == _bibtex(self.R)


class TestHelpers:
    def test_clean_author(self):
        assert _clean_author(" Smith, J. ") == "Smith, J"

    def test_clean_title(self):
        assert _clean_title(' "Neural Methods" ') == "Neural Methods"

    def test_norm(self):
        assert _norm("Hello World!") == "helloworld"
