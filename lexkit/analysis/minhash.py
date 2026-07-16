"""Deterministic MinHash + LSH for near-duplicate detection & clustering.

MinHash approximates Jaccard similarity between sets using a family of hash
functions. LeXKit builds those functions deterministically from a fixed seed
via ``hashlib``, so the **same shingle set always produces the same signature**,
across machines and runs — the reproducibility we require.

Public API
----------
- ``shingles()``   — character/word n-gram shingles of a string.
- ``MinHasher``    — produce fixed-length MinHash signatures.
- ``jaccard()``    — exact Jaccard similarity of two sets.
- ``signature_similarity`` — estimated Jaccard from two signatures.
- ``LSH``          — band signatures into candidate-pair buckets for clustering.

Notes
-----
- We deliberately avoid Python's built-in ``hash()`` because it is randomised
  per process (``PYTHONHASHSEED``). ``hashlib.blake2b`` with a fixed key gives
  us stable, seedable hashing.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

# 64-bit unsigned range, used as an inclusive modulus bound.
_MASK64 = (1 << 64) - 1

# A large prime < 2**64 for the (a*x + b) mod p universal-hash family.
_PRIME = (1 << 61) - 1


def shingles(text: str, n: int = 5, *, unit: str = "char") -> frozenset[str]:
    """Return the set of ``n``-shingles of ``text``.

    Parameters
    ----------
    n
        Shingle width.
    unit
        ``"char"`` (default) or ``"word"``. Character shingles are robust to
        minor word-level edits; word shingles are better for whole-paragraph
        near-dups.

    Returns
    -------
    frozenset[str]
        Deterministic set of shingles. Empty for inputs shorter than ``n``.
    """
    if not text:
        return frozenset()
    text = " ".join(text.split())  # collapse whitespace deterministically
    if unit == "word":
        words = text.split()
        if len(words) < n:
            return frozenset({" ".join(words)}) if words else frozenset()
        return frozenset(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))
    # char shingles
    if len(text) < n:
        return frozenset({text})
    return frozenset(text[i : i + n] for i in range(len(text) - n + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Exact Jaccard similarity ``|A∩B| / |A∪B|``. ``0.0`` if both empty."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _stable_hash(value: str, seed: int) -> int:
    """Stable 64-bit hash of ``value`` parameterised by ``seed``.

    Uses ``blake2b`` with the seed encoded into its key/personalisation so that
    different seeds yield independent hash families — all fully deterministic.
    """
    key = seed.to_bytes(8, "little", signed=False)
    h = hashlib.blake2b(value.encode("utf-8", errors="replace"), digest_size=8, key=key)
    return struct.unpack("<Q", h.digest())[0]


@dataclass
class MinHasher:
    """Produce fixed-length MinHash signatures from shingle sets.

    Attributes
    ----------
    num_perm
        Number of permutations (signature length). More = tighter Jaccard
        estimate, more compute. 128 is a good default.
    seed
        Base seed; each permutation uses ``seed + i``. Fixed by default so the
        hasher is reproducible.

    Examples
    --------
    >>> mh = MinHasher(num_perm=64)
    >>> s1 = shingles("the quick brown fox")
    >>> s2 = shingles("the quick brown dog")
    >>> 0.0 < signature_similarity(mh.signature(s1), mh.signature(s2)) < 1.0
    True
    """

    num_perm: int = 128
    seed: int = 0

    def __post_init__(self) -> None:
        if self.num_perm <= 0:
            raise ValueError("num_perm must be positive")
        # Precompute a per-permutation multiplier/offset pair for the
        # (a*x + b) mod p universal-hash family. Deterministic given seed.
        self._a: list[int] = []
        self._b: list[int] = []
        for i in range(self.num_perm):
            self._a.append(_stable_hash(f"a:{i}", self.seed + i) % (_PRIME - 1) + 1)
            self._b.append(_stable_hash(f"b:{i}", self.seed + i) % _PRIME)

    def signature(self, shingle_set: frozenset[str]) -> tuple[int, ...]:
        """Compute the MinHash signature of a shingle set.

        Returns a tuple of ``num_perm`` integers. Empty set → all-ones signature
        (max value) so two empty inputs compare as identical, as expected.
        """
        if not shingle_set:
            return tuple((_MASK64,) * self.num_perm)
        # Hash each shingle once to a stable 64-bit value, then derive each
        # permutation as (a*x + b) mod p. This is the standard min-hash trick.
        base = [_stable_hash(s, self.seed) for s in shingle_set]
        sig: list[int] = []
        for i in range(self.num_perm):
            a = self._a[i]
            b = self._b[i]
            m = min(((a * x + b) % _PRIME) & _MASK64 for x in base)
            sig.append(m)
        return tuple(sig)

    def signature_text(self, text: str, n: int = 5, *, unit: str = "char") -> tuple[int, ...]:
        """Shingle ``text`` then sign it — convenience for raw strings."""
        return self.signature(shingles(text, n=n, unit=unit))


def signature_similarity(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    """Estimate Jaccard similarity from two MinHash signatures (fraction of
    matching components). Signatures must have equal length."""
    if not sig_a or not sig_b:
        return 0.0
    n = min(len(sig_a), len(sig_b))
    if n == 0:
        return 0.0
    agree = sum(1 for i in range(n) if sig_a[i] == sig_b[i])
    return agree / n


@dataclass
class LSH:
    """Locality-sensitive hashing to bucket similar MinHash signatures.

    Banded hashing gives candidate pairs whose estimated Jaccard exceeds a
    threshold determined by ``bands`` and ``rows`` (``num_perm = bands * rows``).
    Members that share at least one band's hash are candidate near-duplicates.

    Attributes
    ----------
    bands
        Number of bands.
    rows
        Rows per band (= signature length / bands).
    seed
        Stable seed for band hashing.

    The approximate threshold is ``(1/bands) ** (1/rows)``.
    """

    bands: int = 32
    rows: int = 4
    seed: int = 0

    def __post_init__(self) -> None:
        if self.bands <= 0 or self.rows <= 0:
            raise ValueError("bands and rows must be positive")

    @property
    def threshold(self) -> float:
        """Approximate Jaccard threshold above which pairs become candidates."""
        return (1.0 / self.bands) ** (1.0 / self.rows)

    def band_hashes(self, signature: tuple[int, ...]) -> list[int]:
        """Collapse each band of the signature into a single stable hash."""
        if len(signature) != self.bands * self.rows:
            # Adapt to whatever length we received by re-banding evenly.
            per = max(1, len(signature) // self.bands)
        else:
            per = self.rows
        out: list[int] = []
        for b in range(self.bands):
            chunk = signature[b * per : (b + 1) * per]
            if not chunk:
                continue
            key = (b + 1).to_bytes(4, "little", signed=False)
            h = hashlib.blake2b(struct.pack(f"<{len(chunk)}Q", *chunk), digest_size=8, key=key)
            out.append(struct.unpack("<Q", h.digest())[0])
        return out


@dataclass
class ClusterResult:
    """Outcome of clustering a set of items by near-duplicate signatures."""

    #: cluster_id -> list of item keys
    clusters: dict[int, list[str]] = field(default_factory=dict)
    #: item key -> cluster_id
    membership: dict[str, int] = field(default_factory=dict)
    #: number of singleton (isolated) clusters
    singletons: int = 0


def cluster_signatures(
    signatures: dict[str, tuple[int, ...]],
    *,
    bands: int = 32,
    rows: int = 4,
    seed: int = 0,
) -> ClusterResult:
    """Cluster items by MinHash signature using LSH + union-find.

    Parameters
    ----------
    signatures
        Mapping of item key -> MinHash signature.

    Returns
    -------
    ClusterResult
        Deterministic grouping. Cluster ids are assigned by sorted first-member
        key so the result is stable across runs.
    """
    lsh = LSH(bands=bands, rows=rows, seed=seed)
    parent: dict[str, str] = {k: k for k in signatures}

    def find(x: str) -> str:
        root = x
        while parent[root] != root:
            root = parent[root]
        # path compression
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Bucket keys by each band hash; any two keys in the same band bucket
    # are candidate near-duplicates and get unioned.
    band_buckets: list[dict[int, list[str]]] = [
        {} for _ in range(max(1, lsh.bands))
    ]
    for key, sig in signatures.items():
        hashes = lsh.band_hashes(sig)
        for bi, h in enumerate(hashes):
            band_buckets[bi].setdefault(h, []).append(key)
    for buckets in band_buckets:
        for members in buckets.values():
            if len(members) < 2:
                continue
            anchor = members[0]
            for m in members[1:]:
                union(anchor, m)

    # Build clusters, assigning deterministic ids by sorted first member.
    groups: dict[str, list[str]] = {}
    for key in signatures:
        root = find(key)
        groups.setdefault(root, []).append(key)
    # Sort each group, then sort groups by their first member for stable ids.
    sorted_groups = sorted((sorted(members) for members in groups.values()))
    result = ClusterResult()
    for cid, members in enumerate(sorted_groups):
        result.clusters[cid] = members
        for m in members:
            result.membership[m] = cid
        if len(members) == 1:
            result.singletons += 1
    return result
