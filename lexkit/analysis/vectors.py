"""Deterministic TF-IDF vectors & cosine similarity.

Everything here is pure-Python with sparse-dict vectors. Vocabulary order is
canonicalised (sorted) so two runs over the same corpus produce identical
IDF tables and therefore identical vectors — the reproducibility LeXKit promises.

Public API
----------
- ``TfidfModel``   — fit IDF over a corpus, transform docs into sparse vectors.
- ``tfidf_vector`` — convenience: vector for one doc given a fitted model.
- ``cosine_similarity`` — sparse-dict cosine, O(min(|a|,|b|)).
- ``keyterms``     — top-k highest TF-IDF terms in a document.

Math
----
- TF  = count(term) / total_terms(doc)            (normalised term frequency)
- IDF = ln( (1 + N) / (1 + df(term)) ) + 1        (smoothed, sklearn-style)
- TF-IDF = TF * IDF, then each document vector is L2-normalised so that cosine
  similarity reduces to a dot product.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from lexkit.analysis.tokenizer import tokenize, term_frequencies

#: A sparse vector: term -> weight. Only non-zero entries are stored.
SparseVector = dict[str, float]


class TfidfModel:
    """Fit an IDF table over a corpus and transform documents into TF-IDF vectors.

    The vocabulary is stored in **sorted** order so the model is deterministic
    and reproducible: the same corpus always yields the same model, byte for
    byte (given the same tokenizer settings).

    Examples
    --------
    >>> corpus = ["neural networks for language", "graph neural networks"]
    >>> model = TfidfModel(corpus)
    >>> v = model.transform("neural networks")
    >>> round(v["neural"], 3)
    0.0
    >>> isinstance(v, dict)
    True
    """

    def __init__(
        self,
        corpus: Iterable[str] | None = None,
        *,
        ngram: int = 1,
        **tokenize_kwargs: object,
    ) -> None:
        self._tokenize_kwargs = dict(tokenize_kwargs)
        self._ngram = max(1, int(ngram))
        #: document frequency per term (how many docs contain it)
        self.df: dict[str, int] = {}
        #: smoothed IDF per term
        self.idf: dict[str, float] = {}
        self.n_docs: int = 0
        if corpus is not None:
            self.fit(list(corpus))

    # ── fitting ────────────────────────────────────────────────────────────────
    def _doc_tokens(self, doc: str) -> list[str]:
        toks = tokenize(doc, **self._tokenize_kwargs)  # type: ignore[arg-type]
        if self._ngram > 1:
            from lexkit.analysis.tokenizer import ngrams
            return ngrams(toks, self._ngram)
        return toks

    def fit(self, corpus: Sequence[str]) -> "TfidfModel":
        """Compute document frequencies and IDF over ``corpus``."""
        self.df = {}
        self.n_docs = 0
        for doc in corpus:
            toks = self._doc_tokens(doc)
            self.n_docs += 1
            for term in set(toks):  # unique terms in this doc
                self.df[term] = self.df.get(term, 0) + 1
        self._compute_idf()
        return self

    def _compute_idf(self) -> None:
        """Smoothed, deterministic IDF. Sorted vocab for reproducibility."""
        n = self.n_docs if self.n_docs > 0 else 1
        # Sort terms so model state is byte-stable across runs/platforms.
        self.idf = {
            term: math.log((1 + n) / (1 + df)) + 1.0
            for term in sorted(self.df)
            for df in (self.df[term],)
        }

    # ── transform ──────────────────────────────────────────────────────────────
    def transform(self, doc: str) -> SparseVector:
        """Return the L2-normalised TF-IDF sparse vector for ``doc``."""
        if not self.idf:
            # Unfitted model: fall back to raw TF (still deterministic).
            toks = self._doc_tokens(doc)
            tf = term_frequencies(toks)
            total = len(toks) or 1
            vec = {t: c / total for t, c in tf.items()}
            return _l2_normalize(vec)
        toks = self._doc_tokens(doc)
        if not toks:
            return {}
        tf = term_frequencies(toks)
        total = len(toks)
        vec: SparseVector = {}
        for term, count in tf.items():
            idf = self.idf.get(term)
            if idf is None:
                # Unseen term: use default IDF for a term appearing in 0 docs.
                idf = math.log((1 + self.n_docs) / 1) + 1.0
            vec[term] = (count / total) * idf
        return _l2_normalize(vec)

    def transform_corpus(self, corpus: Iterable[str]) -> list[SparseVector]:
        """Transform many documents. Returns a list aligned with ``corpus``."""
        return [self.transform(doc) for doc in corpus]

    # ── inspection ─────────────────────────────────────────────────────────────
    @property
    def vocabulary(self) -> list[str]:
        """Sorted list of all terms seen during fitting."""
        return sorted(self.df)

    @property
    def vocab_size(self) -> int:
        return len(self.df)


# ── Free functions ────────────────────────────────────────────────────────────

def _l2_normalize(vec: SparseVector) -> SparseVector:
    """Return a new L2-normalised copy of ``vec`` (in place if empty)."""
    norm = math.sqrt(sum(w * w for w in vec.values()))
    if norm == 0.0:
        return {}
    return {t: w / norm for t, w in vec.items()}


def tfidf_vector(doc: str, model: TfidfModel) -> SparseVector:
    """Shorthand for ``model.transform(doc)``."""
    return model.transform(doc)


def cosine_similarity(a: SparseVector, b: SparseVector) -> float:
    """Cosine similarity between two (already L2-normalised) sparse vectors.

    Since vectors produced by :class:`TfidfModel` are unit-norm, this is just a
    dot product. For safety we iterate over the smaller vector, and the result
    is clamped to ``[0, 1]`` (TF-IDF weights are non-negative).
    """
    if not a or not b:
        return 0.0
    # Iterate over the shorter dict for speed.
    if len(b) < len(a):
        a, b = b, a
    dot = 0.0
    for term, weight in a.items():
        other = b.get(term)
        if other is not None:
            dot += weight * other
    # Clamp tiny float overshoot.
    if dot > 1.0:
        dot = 1.0
    if dot < 0.0:
        dot = 0.0
    return dot


def keyterms(doc: str, model: TfidfModel, k: int = 10) -> list[tuple[str, float]]:
    """Return the ``k`` highest TF-IDF terms in ``doc``.

    Sorted by descending weight, ties broken alphabetically (deterministic).
    """
    vec = model.transform(doc)
    ranked = sorted(vec.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[: max(0, k)]
