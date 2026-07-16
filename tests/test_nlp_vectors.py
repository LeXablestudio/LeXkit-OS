"""Tests for lexkit.analysis.vectors — TF-IDF determinism, cosine, keyterms."""

import pytest
from lexkit.analysis.vectors import (
    TfidfModel,
    cosine_similarity,
    keyterms,
    tfidf_vector,
    _l2_normalize,
)


CORPUS = [
    "neural networks for natural language processing",
    "graph neural networks and knowledge graphs",
    "medieval manuscript studies and paleography",
    "quantum computing for machine learning",
]


class TestTfidfModel:
    def test_fit_determinism(self):
        """Same corpus → same IDF table."""
        m1 = TfidfModel(CORPUS)
        m2 = TfidfModel(CORPUS)
        assert m1.idf == m2.idf
        assert m1.vocabulary == m2.vocabulary

    def test_transform_determinism(self):
        """Same doc → same vector, always."""
        m = TfidfModel(CORPUS)
        v1 = m.transform("neural networks")
        v2 = m.transform("neural networks")
        assert v1 == v2

    def test_unfitted_transform(self):
        """Transform on unfitted model returns normalised TF (no crash)."""
        m = TfidfModel()  # no corpus
        v = m.transform("hello world hello")
        assert len(v) == 2  # two unique terms
        assert "hello" in v

    def test_self_similarity(self):
        """A vector's cosine with itself is 1.0."""
        m = TfidfModel(CORPUS)
        v = m.transform(CORPUS[0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_related_higher_sim(self):
        """Related docs should have higher cosine than unrelated."""
        m = TfidfModel(CORPUS)
        v_nn = m.transform("neural networks for language")
        v_gnn = m.transform("graph neural networks")
        v_med = m.transform("medieval manuscript paleography")
        sim_nn = cosine_similarity(v_nn, v_gnn)
        sim_nm = cosine_similarity(v_nn, v_med)
        assert sim_nn > sim_nm

    def test_empty_transform(self):
        m = TfidfModel(CORPUS)
        assert m.transform("") == {}

    def test_keyterms(self):
        m = TfidfModel(CORPUS)
        kt = keyterms("neural networks for language processing", m, k=3)
        assert len(kt) <= 3
        assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in kt)
        # Terms should be from the doc
        terms = [t for t, _ in kt]
        assert any("neural" in t or "network" in t for t in terms)

    def test_vocab_size(self):
        m = TfidfModel(CORPUS)
        assert m.vocab_size > 0
        assert len(m.vocabulary) == m.vocab_size


class TestCosineSimilarity:
    def test_empty_vectors(self):
        assert cosine_similarity({}, {"a": 1.0}) == 0.0

    def test_clamped(self):
        """Result always in [0, 1]."""
        m = TfidfModel(CORPUS)
        for d in CORPUS:
            for d2 in CORPUS:
                s = cosine_similarity(m.transform(d), m.transform(d2))
                assert 0.0 <= s <= 1.0


class TestL2Normalize:
    def test_unit_norm(self):
        vec = _l2_normalize({"a": 3.0, "b": 4.0})
        norm = sum(v * v for v in vec.values()) ** 0.5
        assert abs(norm - 1.0) < 1e-9

    def test_empty(self):
        assert _l2_normalize({}) == {}
