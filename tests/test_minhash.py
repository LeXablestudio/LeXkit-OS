"""Tests for lexkit.analysis.minhash — determinism, clustering, edge cases."""

import pytest
from lexkit.analysis.minhash import (
    MinHasher,
    shingles,
    jaccard,
    signature_similarity,
    LSH,
    cluster_signatures,
    ClusterResult,
)


TEXT_A = "the quick brown fox jumps over the lazy dog"
TEXT_B = "the quick brown fox leaps over the lazy dog"
TEXT_C = "quantum entanglement is a physical phenomenon"
TEXT_D = ""


class TestShingles:
    def test_char_shingles(self):
        s = shingles("abcde", n=3, unit="char")
        assert "abc" in s
        assert "cde" in s
        assert len(s) == 3

    def test_word_shingles(self):
        s = shingles("a b c d e", n=2, unit="word")
        assert "a b" in s
        assert "d e" in s

    def test_empty(self):
        assert shingles("", n=3) == frozenset()

    def test_short_input(self):
        s = shingles("ab", n=3)
        assert len(s) == 1  # whole string as one shingle


class TestJaccard:
    def test_identical(self):
        s = shingles(TEXT_A, n=3)
        assert jaccard(s, s) == 1.0

    def test_disjoint(self):
        a = shingles(TEXT_A, n=3)
        c = shingles(TEXT_C, n=3)
        assert jaccard(a, c) == 0.0

    def test_similar(self):
        a = shingles(TEXT_A, n=3)
        b = shingles(TEXT_B, n=3)
        sim = jaccard(a, b)
        assert 0.0 < sim < 1.0


class TestMinHasher:
    def test_determinism(self):
        """Same shingle set → same signature, always."""
        mh = MinHasher(num_perm=64)
        s = shingles(TEXT_A, n=3)
        assert mh.signature(s) == mh.signature(s)

    def test_empty_set(self):
        mh = MinHasher(num_perm=64)
        sig = mh.signature(frozenset())
        assert len(sig) == 64
        assert all(v == mh.signature(frozenset())[0] for v in sig)

    def test_signature_length(self):
        mh = MinHasher(num_perm=128)
        sig = mh.signature(shingles(TEXT_A, n=3))
        assert len(sig) == 128

    def test_near_dup_higher_sim(self):
        mh = MinHasher(num_perm=128)
        sa = mh.signature(shingles(TEXT_A, n=3))
        sb = mh.signature(shingles(TEXT_B, n=3))
        sc = mh.signature(shingles(TEXT_C, n=3))
        sim_ab = signature_similarity(sa, sb)
        sim_ac = signature_similarity(sa, sc)
        assert sim_ab > sim_ac

    def test_signature_text(self):
        mh = MinHasher(num_perm=64)
        sig = mh.signature_text(TEXT_A, n=3, unit="char")
        assert len(sig) == 64


class TestLSH:
    def test_threshold(self):
        lsh = LSH(bands=32, rows=4)
        t = lsh.threshold
        assert 0.0 < t < 1.0

    def test_band_hashes_length(self):
        mh = MinHasher(num_perm=128)
        sig = mh.signature(shingles(TEXT_A, n=3))
        lsh = LSH(bands=32, rows=4)
        hashes = lsh.band_hashes(sig)
        assert len(hashes) == 32


class TestClusterSignatures:
    def test_near_dups_clustered(self):
        mh = MinHasher(num_perm=64)
        sa = mh.signature(shingles(TEXT_A, n=3))
        sb = mh.signature(shingles(TEXT_B, n=3))
        sc = mh.signature(shingles(TEXT_C, n=3))
        result = cluster_signatures(
            {"a": sa, "b": sb, "c": sc}, bands=16, rows=4
        )
        assert isinstance(result, ClusterResult)
        # a and b should be in the same cluster; c should be isolated.
        assert result.membership["a"] == result.membership["b"]
        assert result.membership["c"] != result.membership["a"] or result.singletons > 0

    def test_single_item(self):
        mh = MinHasher(num_perm=64)
        sig = mh.signature(shingles(TEXT_A, n=3))
        result = cluster_signatures({"a": sig}, bands=16, rows=4)
        assert result.singletons == 1

    def test_empty(self):
        result = cluster_signatures({}, bands=16, rows=4)
        assert result.clusters == {}
