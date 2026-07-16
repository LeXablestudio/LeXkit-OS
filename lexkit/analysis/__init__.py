"""LeXKit deterministic analysis core.

A dependency-free, fully reproducible NLP toolkit powering similarity search,
near-duplicate detection, keyterm extraction and citation matching across all
LeXKit tools.

Modules
-------
- :mod:`tokenizer` — tokenisation, n-grams, sentence splitting, stopwords.
- :mod:`vectors`   — TF-IDF model, cosine similarity, keyterms.
- :mod:`minhash`   — MinHash signatures, LSH, near-duplicate clustering.

Philosophy: same input → same output, always, offline, no models.
"""

from lexkit.analysis.tokenizer import (
    STOPWORDS,
    ngrams,
    normalize_token,
    sentence_split,
    term_frequencies,
    tokenize,
)
from lexkit.analysis.vectors import (
    SparseVector,
    TfidfModel,
    cosine_similarity,
    keyterms,
    tfidf_vector,
)
from lexkit.analysis.minhash import (
    ClusterResult,
    LSH,
    MinHasher,
    cluster_signatures,
    jaccard,
    shingles,
    signature_similarity,
)

__all__ = [
    # tokenizer
    "STOPWORDS",
    "tokenize",
    "ngrams",
    "normalize_token",
    "sentence_split",
    "term_frequencies",
    # vectors
    "SparseVector",
    "TfidfModel",
    "tfidf_vector",
    "cosine_similarity",
    "keyterms",
    # minhash
    "shingles",
    "jaccard",
    "MinHasher",
    "signature_similarity",
    "LSH",
    "cluster_signatures",
    "ClusterResult",
]
