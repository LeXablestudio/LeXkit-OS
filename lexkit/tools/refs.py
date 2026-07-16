"""Reference Manager — multi-format citation extraction, storage, and export.

v2.0 changes:
- **Fixed** the v1 SyntaxError in ``_chicago`` (unterminated f-string).
- **Multi-format citation parsing**: APA, MLA, Chicago, Harvard, and numeric /
  bracket (``[1] …``) reference-list styles, in addition to the original
  APA-only regex.
- DOI/URL normalization and cross-format dedup disambiguation.
- Optional LLM enrichment: when a backend is configured, fuzzy reference blocks
  can be parsed with higher quality. Off by default — deterministic engine only.

Public API
----------
- ``MultiFormatCitationParser`` — the deterministic parser used by the CLI.
- ``parse_citations(text)`` — convenience wrapper.
- ``extract`` / ``list`` / ``export`` Typer commands.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from lexkit.db.store import get_db, upsert_reference, list_references
from lexkit.config.settings import Settings
from lexkit.logging import get_logger

log = get_logger("refs")

app = typer.Typer(help="Reference Manager — extract & export citations.")
console = Console()

# ── Shared patterns ────────────────────────────────────────────────────────────
#: A 4-digit year, optionally parenthesised.
_YEAR = r"(\d{4})"
#: A single capitalised word, optionally ending in "." (for initials like "J.").
_CAP = r"[A-Z][A-Za-z'\-]*\.?"
#: Author-ish lead: one or more capitalised words/initials separated by commas,
#: spaces, or "and"/"&".  Covers:
#:   "Smith, J. A.", "Smith, John", "Smith J A", "Smith, J A and Lee, K."
_AUTHORS = rf"({_CAP}(?:\s*,?\s+(?:and|&\s+)?{_CAP})*)"
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\")]+")
URL_RE = re.compile(r"\bhttps?://[^\s\")]+", re.IGNORECASE)

# ── Per-style regexes ──────────────────────────────────────────────────────────
# APA:  Smith, J. A. (2020). Title of work.
APA_RE = re.compile(
    rf"{_AUTHORS}\s*\(\s*{_YEAR}\s*\)\.?\s*([^\n]{{5,300}}?)\.",
    re.MULTILINE,
)
# MLA:  Smith, John. "Title of Work."
MLA_RE = re.compile(
    rf'{_AUTHORS}\.?\s*"([^"\n]{{5,300}})"',
    re.MULTILINE,
)
# Chicago: Smith, John. 2020. "Title of Work."
CHICAGO_RE = re.compile(
    rf"{_AUTHORS}\.?\s*{_YEAR}\.?\s*\"([^\"]{{5,300}})\"",
    re.MULTILINE,
)
# Harvard: Smith, J 2020, 'Title of work.'
HARVARD_RE = re.compile(
    rf"{_AUTHORS}\s*{_YEAR},?\s+'([^'\n]{{5,300}})'",
    re.MULTILINE,
)
# Numeric / bracket reference list: [1] Author, Year. Title.
BRACKET_RE = re.compile(
    rf"\[\d+\]\s*{_AUTHORS}\.?\s*\(?\s*{_YEAR}\s*\)?\.?\s*([^\n]{{5,300}}?)\.",
    re.MULTILINE,
)

_STYLE_TABLE = [
    ("apa", APA_RE, 1, 2, 3),
    ("mla", MLA_RE, 1, None, 2),
    ("chicago", CHICAGO_RE, 1, 2, 3),
    ("harvard", HARVARD_RE, 1, 2, 3),
    ("bracket", BRACKET_RE, 1, 2, 3),
]


class MultiFormatCitationParser:
    """Deterministic, multi-style citation parser.

    Tries each style regex over the text, collects matches, and de-duplicates
    by a normalised ``(author, year, title-key)`` key so the same reference
    surfaced by two styles is stored once.

    Examples
    --------
    >>> p = MultiFormatCitationParser()
    >>> refs = p.parse('Smith, J. (2020). Neural methods for parsing.')
    >>> refs[0]['author'], refs[0]['year']
    ('Smith, J', '2020')
    """

    def __init__(self, *, min_title_len: int = 4) -> None:
        self.min_title_len = min_title_len

    def parse(self, text: str) -> list[dict]:
        if not text:
            return []
        found: dict[str, dict] = {}
        for style, rx, author_g, year_g, title_g in _STYLE_TABLE:
            for m in rx.finditer(text):
                author = _clean_author(m.group(author_g))
                title = _clean_title(m.group(title_g)) if title_g else ""
                year = m.group(year_g) if year_g else _nearest_year(text, m.start())
                if len(title) < self.min_title_len and not author:
                    continue
                ref = self._build_ref(text, m, author, year, title, style)
                key = _dedup_key(ref)
                # Prefer the entry with more complete fields.
                if key not in found or _completeness(ref) > _completeness(found[key]):
                    found[key] = ref
        return list(found.values())

    def _build_ref(self, text: str, m: re.Match, author: str, year: str, title: str, style: str) -> dict:
        span = text[m.start() : min(len(text), m.start() + 600)]
        doi = _first(DOI_RE, span)
        url = _first(URL_RE, span)
        return {
            "author": author or None,
            "year": year or None,
            "title": title or None,
            "doi": doi,
            "url": url,
            "source_file": None,
            "style": style,
        }


def parse_citations(text: str) -> list[dict]:
    """Convenience wrapper around :class:`MultiFormatCitationParser`."""
    return MultiFormatCitationParser().parse(text)


# ── Text helpers ───────────────────────────────────────────────────────────────

def _first(rx: re.Pattern[str], text: str) -> Optional[str]:
    m = rx.search(text)
    return m.group().rstrip(".,);") if m else None


def _clean_author(raw: str) -> str:
    a = re.sub(r"\s+", " ", raw or "").strip(" ,.;:")
    return a or None  # type: ignore[return-value]


def _clean_title(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw or "").strip(" .\"',")
    # Strip a trailing year/author echo some styles repeat.
    return t or None  # type: ignore[return-value]


def _nearest_year(text: str, pos: int) -> Optional[str]:
    window = text[max(0, pos - 80) : pos + 120]
    m = re.search(r"(19|20)\d{2}", window)
    return m.group() if m else None


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _dedup_key(ref: dict) -> str:
    """Key for cross-style dedup: normalised author-surname + year + title head."""
    author = ref.get("author") or ""
    surname = author.split(",")[0].split()[-1:] or [""]
    return f"{_norm(''.join(surname))[:10]}|{ref.get('year','')}|{_norm(ref.get('title'))[:40]}"


def _completeness(ref: dict) -> int:
    """Score how many fields are populated — used to pick the better duplicate."""
    return sum(1 for k in ("author", "year", "title", "doi", "url") if ref.get(k))


# ── CLI commands ───────────────────────────────────────────────────────────────

@app.command()
def extract(
    input_path: str = typer.Option(..., "--input", "-i"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    use_llm: bool = typer.Option(False, "--llm", help="Use optional LLM enrichment if configured."),
) -> None:
    """Extract citations (multi-format) and store them in the local database."""
    from lexkit.core.scanner import scan_directory
    from lexkit.tools.batch import _extract_pdf
    from lexkit.core.processor import make_progress
    from lexkit.errors import LexKitError, wrap

    path = Path(input_path).expanduser().resolve()
    settings = Settings.load_default()
    db = get_db(settings.db_path)
    parser = MultiFormatCitationParser()
    files = scan_directory(path, recursive=recursive, compute_hashes=False)
    total = 0

    llm = None
    if use_llm:
        from lexkit.llm import get_llm
        llm = get_llm()
        if not llm.is_available():
            console.print("[yellow]LLM not configured — falling back to deterministic parser.[/yellow]")
            llm = None

    with make_progress() as p:
        task = p.add_task("Extracting refs...", total=len(files))
        for meta in files:
            try:
                text = _extract_pdf(meta.path) if meta.suffix == ".pdf" else meta.path.read_text(encoding="utf-8", errors="replace")
                refs = parser.parse(text)
                for ref in refs:
                    ref["source_file"] = str(meta.path)
                    with wrap(LexKitError("ref_store_failed"), context={"file": str(meta.path)}):
                        upsert_reference(db, ref)
                    total += 1
                # Optional LLM enrichment for blocks the deterministic parser missed.
                if llm is not None and llm.is_available():
                    extra = _llm_extract(llm, text, str(meta.path), {r["title"] for r in refs if r.get("title")})
                    for ref in extra:
                        upsert_reference(db, ref)
                        total += 1
            except Exception as exc:
                log.exception("ref_extract_failed", exc, file=str(meta.path))
            p.advance(task)
    db.close()
    console.print(f"[green]Extracted {total} references.[/green]")


def _llm_extract(llm, text: str, source: str, already: set[str]) -> list[dict]:
    """Ask the LLM for citations the deterministic parser may have missed.

    Only runs when a backend is configured. Filters out titles we already have.
    """
    snippet = text[:3000]
    prompt = (
        "Extract academic citations from the text below as JSON objects with keys "
        "author, year, title, doi (nullable). Output one JSON object per line, "
        "nothing else.\n\nTEXT:\n" + snippet
    )
    try:
        records = llm.extract(prompt)
    except Exception as exc:  # noqa: BLE001 — enrichment must never break extraction
        log.warning("refs_llm_failed", error=str(exc))
        return []
    out: list[dict] = []
    for r in records:
        title = r.get("title")
        if title and _norm(title) not in {_norm(t) for t in already}:
            r["source_file"] = source
            out.append(r)
    return out


@app.command("list")
def list_refs(limit: int = typer.Option(50, "--limit", "-n")) -> None:
    """List stored references."""
    settings = Settings.load_default()
    db = get_db(settings.db_path)
    refs = list_references(db, limit=limit)
    db.close()
    t = Table(title=f"References ({len(refs)})", border_style="magenta")
    t.add_column("Author", max_width=28)
    t.add_column("Year", width=6)
    t.add_column("Title", max_width=52)
    t.add_column("DOI/URL", max_width=22)
    for r in refs:
        link = r.get("doi") or r.get("url") or ""
        t.add_row((r.get("author") or "")[:28], r.get("year") or "", (r.get("title") or "")[:52], link[:22])
    console.print(t)


@app.command()
def export(
    fmt: str = typer.Option("bibtex", "--export", "-e"),
    output: Optional[str] = typer.Option(None, "--out", "-o"),
) -> None:
    """Export references in bibtex | apa | mla | chicago."""
    settings = Settings.load_default()
    db = get_db(settings.db_path)
    refs = list_references(db, limit=100000)
    db.close()
    fmt = fmt.lower()
    fmts = {"bibtex": _bibtex, "apa": _apa, "mla": _mla, "chicago": _chicago}
    renderer = fmts.get(fmt)
    if renderer is None:
        console.print(f"[red]Unknown format '{fmt}'. Use: {', '.join(fmts)}[/red]")
        raise typer.Exit(1)
    content = "\n\n".join(renderer(r) for r in refs)
    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]Exported {len(refs)} refs → {output}[/green]")
    else:
        console.print(content)


# ── Export renderers ───────────────────────────────────────────────────────────

def _slug(r: dict) -> str:
    return re.sub(r"[^a-z]", "", (r.get("author") or "x").lower())[:8] + (r.get("year") or "0000")


def _bibtex(r: dict) -> str:
    return (
        f"@article{{{_slug(r)},\n"
        f"  author = {{{r.get('author', '')}}},\n"
        f"  year = {{{r.get('year', '')}}},\n"
        f"  title = {{{r.get('title', '')}}},\n"
        f"  doi = {{{r.get('doi') or ''}}},\n"
        f"  url = {{{r.get('url') or ''}}}\n}}"
    )


def _apa(r: dict) -> str:
    return f"{r.get('author', '')}. ({r.get('year', '')}). {r.get('title', '')}."


def _mla(r: dict) -> str:
    return f"{r.get('author', '')}. \"{r.get('title', '')}.\" {r.get('year', '')}."


def _chicago(r: dict) -> str:
    return f"{r.get('author', '')}. {r.get('year', '')}. \"{r.get('title', '')}.\""
