"""Deterministic tokenizer — the foundation of LeXKit's NLP core.

Zero dependencies beyond the standard library. Token order is stable and
reproducible: the same input always yields the same sequence of tokens, so any
downstream statistic (TF-IDF, co-occurrence, keyterms) is reproducible too.

Public API
----------
- ``STOPWORDS``      — curated English academic stopword set.
- ``tokenize()``      — lowercase Unicode word tokens, optionally filtered.
- ``ngrams()``        — contiguous n-grams over a token stream (deterministic).
- ``sentence_split()``— split text into sentences without third-party libs.
- ``normalize_token()``— light stemming for ASCII words (trims common suffixes).

Design notes
------------
- We split on word boundaries with ``\\w+`` under the ``re.UNICODE`` flag so
  accented letters are kept inside tokens (NFC-normalised first).
- Numbers and single characters are dropped by default — they carry little
  signal for academic keyterm extraction and add noise.
"""

from __future__ import annotations

import re
import unicodedata

# ── Regexes (module-level so they compile once) ────────────────────────────────
# \w+ under Unicode keeps accented letters; we NFC-normalise first so combining
# marks never split a grapheme cluster across two tokens.
_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Sentence boundaries: terminal punctuation followed by whitespace + capital,
# or a hard newline pair. Pragmatic — not a full parser.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n{2,}")
# Light suffix trimmer for ASCII word stems. Deterministic, not a real stemmer,
# but reduces surface-form variance enough to improve keyterm aggregation.
_SUFFIX_RE = re.compile(r"(?:ization|isations?|ization|iveness|fulness|ousness|alities|atively|ization|ements?|ances?|ences?|ities|ables?|ibles?|izing|ising|ation|tions?|sions?|ously|fully|ically|ished|ishes|ings?|ness|ment|less|able|ible|ally|ized|ised|ous|ive|ful|ity|ies|ied|ier|iest|ing|ers?|ed|es|s)\Z")

#: Curated English academic stopwords. A frozenset for O(1) membership tests.
#: Intentionally excludes domain words like "model", "system", "method" which
#: carry signal in academic text.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but if then else when while of to in on at by for with from into onto upon
    is are was were be been being am do does did doing have has had having will would shall should
    can could may might must ought this that these those there here it its it's they them their
    he she his her we us our you your i my mine yours ours theirs as also not no nor so than too
    very just only more most much many few less least some any all each every other another such
    which who whom whose what where why how about above below between through during before after
    up down out off over under again further once per via etc eg ie cf al et within without across
    among amongst toward towards onto whereby according using based following since until either
    neither both however therefore thus hence whereas although though moreover furthermore namely
    indeed notably respectively typically generally usually often one two three first second third
    new use used using two 1 2 3 4 5 6 7 8 9 0 10
    """.split()
)


def normalize_token(token: str) -> str:
    """Light, deterministic stemmer for ASCII word tokens.

    Strips a fixed set of common English suffixes. Non-ASCII tokens are returned
    unchanged. This is *not* Porter/Snowball — it is intentionally simple so the
    mapping is fully predictable and dependency-free.
    """
    if not token.isascii():
        return token
    if len(token) <= 4:
        return token
    # Try progressively; pick the first (longest-suffix) match.
    return _SUFFIX_RE.sub("", token) or token


def tokenize(
    text: str,
    *,
    lower: bool = True,
    drop_stopwords: bool = True,
    drop_numeric: bool = True,
    drop_short: int = 1,
    stem: bool = False,
) -> list[str]:
    """Tokenise ``text`` into a list of word tokens.

    Parameters
    ----------
    text
        Input string. NFC-normalised first for stable grapheme handling.
    lower
        Lowercase all tokens.
    drop_stopwords
        Remove tokens present in :data:`STOPWORDS`.
    drop_numeric
        Remove purely-numeric tokens (e.g. ``"2024"``).
    drop_short
        Remove tokens with fewer than this many characters (1 by default;
        set to 0 to keep everything).
    stem
        Apply :func:`normalize_token` light stemming.

    Returns
    -------
    list[str]
        Tokens in document order. Deterministic for a given input.
    """
    if not text:
        return []
    text = unicodedata.normalize("NFC", text)
    tokens = _WORD_RE.findall(text)
    out: list[str] = []
    for tok in tokens:
        if lower:
            tok = tok.lower()
        if drop_numeric and tok.isdigit():
            continue
        if drop_short and len(tok) <= drop_short:
            continue
        if drop_stopwords and tok in STOPWORDS:
            continue
        if stem:
            tok = normalize_token(tok)
        out.append(tok)
    return out


def ngrams(tokens: list[str], n: int = 2) -> list[str]:
    """Return contiguous ``n``-grams (joined by single spaces) in order.

    For ``n <= 1`` the original tokens are returned unchanged. The result is
    deterministic for a given token list.
    """
    if n <= 1:
        return list(tokens)
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def sentence_split(text: str) -> list[str]:
    """Split ``text`` into sentences using deterministic heuristics.

    Collapses surrounding whitespace. Empty segments are discarded. No model,
    no external data — the same text always splits the same way.
    """
    if not text:
        return []
    text = unicodedata.normalize("NFC", text)
    parts = _SENT_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def term_frequencies(tokens: list[str]) -> dict[str, int]:
    """Return a raw-count frequency map over ``tokens`` (deterministic order
    is irrelevant for a dict, but insertion order follows first occurrence)."""
    freqs: dict[str, int] = {}
    for tok in tokens:
        freqs[tok] = freqs.get(tok, 0) + 1
    return freqs
