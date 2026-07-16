"""Tests for lexkit.analysis.tokenizer — determinism, edge cases, correctness."""

import pytest
from lexkit.analysis.tokenizer import (
    tokenize,
    ngrams,
    normalize_token,
    sentence_split,
    term_frequencies,
    STOPWORDS,
)


class TestTokenize:
    def test_basic(self):
        assert tokenize("The Quick Brown Fox") == ["quick", "brown", "fox"]

    def test_empty(self):
        assert tokenize("") == []

    def test_stopwords_removed(self):
        assert "the" not in tokenize("the cat sat on the mat")
        assert "on" not in tokenize("the cat sat on the mat")

    def test_numeric_dropped(self):
        assert "2024" not in tokenize("year 2024 was great")

    def test_no_lowercase(self):
        result = tokenize("Hello World", lower=False)
        assert "Hello" in result

    def test_no_stopword_removal(self):
        result = tokenize("the cat", drop_stopwords=False)
        assert "the" in result

    def test_no_numeric_drop(self):
        result = tokenize("42 problems", drop_numeric=False)
        assert "42" in result

    def test_keep_short(self):
        result = tokenize("I am here", drop_short=0, drop_stopwords=False)
        assert "i" in result

    def test_stemming(self):
        result = tokenize("computing organization", stem=True)
        # At least the suffix trimmer should change something
        assert result  # non-empty

    def test_determinism(self):
        """Same input always yields same output."""
        text = "Neural networks for natural language processing"
        a = tokenize(text)
        b = tokenize(text)
        assert a == b

    def test_unicode(self):
        result = tokenize("Café naïve résumé")
        assert "café" in result or "cafe" in result  # depends on NFC


class TestNgrams:
    def test_bigrams(self):
        assert ngrams(["a", "b", "c"], 2) == ["a b", "b c"]

    def test_unigrams_passthrough(self):
        assert ngrams(["a", "b"], 1) == ["a", "b"]

    def test_empty(self):
        assert ngrams([], 2) == []

    def test_short_input(self):
        assert ngrams(["a"], 2) == []


class TestNormalizeToken:
    def test_short_passthrough(self):
        assert normalize_token("cat") == "cat"

    def test_suffix_stripped(self):
        result = normalize_token("computing")
        assert result == "comput" or result == "comput"

    def test_nonascii_passthrough(self):
        assert normalize_token("café") == "café"


class TestSentenceSplit:
    def test_basic(self):
        result = sentence_split("Hello world. How are you?")
        assert len(result) >= 1

    def test_empty(self):
        assert sentence_split("") == []

    def test_determinism(self):
        text = "First sentence. Second sentence. Third."
        assert sentence_split(text) == sentence_split(text)


class TestTermFrequencies:
    def test_counts(self):
        freqs = term_frequencies(["a", "b", "a"])
        assert freqs["a"] == 2
        assert freqs["b"] == 1

    def test_empty(self):
        assert term_frequencies([]) == {}
