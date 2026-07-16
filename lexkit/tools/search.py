"""Search Engine — full-text, regex, fuzzy, and similarity search.

v2.0 changes:
- **Incremental indexing**: file mtime + content hash tracked in the DB so
  unchanged files are skipped on re-index (much faster repeat runs).
- **Similarity search** (``lexkit search similar``): TF-IDF cosine ranking via
  the deterministic :mod:`lexkit.analysis` core — find "more like this".
- Extracted-text caching in a sidecar directory to avoid re-parsing PDFs.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from lexkit.logging import get_logger
from lexkit.config.settings import Settings
from lexkit.db.store import get_db, get_file_signature, set_file_signature

log = get_logger("search")

app = typer.Typer(help="Search Engine.")
console = Console()
INDEX_DIR = ".lexkit_index"
CACHE_DIR = ".lexkit_text_cache"


@app.command()
def index(
    directory: str = typer.Option(..., "--index", "-i"),
    rebuild: bool = typer.Option(False, "--rebuild"),
) -> None:
    """Build or update the full-text search index (incremental)."""
    from lexkit.core.scanner import scan_directory
    from lexkit.core.processor import make_progress

    path = Path(directory).expanduser().resolve()
    index_dir = path / INDEX_DIR
    ix = _open_or_create(index_dir, rebuild=rebuild)
    files = scan_directory(path, compute_hashes=False)
    db = get_db(Settings.load_default().db_path)

    from whoosh.writing import AsyncWriter
    writer = AsyncWriter(ix)
    indexed = skipped = 0
    with make_progress() as p:
        task = p.add_task("Indexing...", total=len(files))
        for meta in files:
            try:
                content, content_sha = _read_text_cached(meta.path)
                mtime = meta.path.stat().st_mtime
                sig = get_file_signature(db, str(meta.path)) if not rebuild else None
                # Skip unchanged files.
                if sig and sig.get("content_sha") == content_sha and sig.get("mtime") == mtime:
                    skipped += 1
                    p.advance(task)
                    continue
                writer.update_document(
                    path=str(meta.path), filename=meta.name, content=content,
                    year=meta.year or "", author=meta.author or "",
                )
                set_file_signature(db, str(meta.path), mtime=mtime, content_sha=content_sha)
                indexed += 1
            except Exception as exc:
                log.exception("index_file_failed", exc, file=str(meta.path))
            p.advance(task)
    writer.commit()
    db.close()
    console.print(
        f"[green]Indexed {indexed} files.[/green] "
        f"[dim](skipped {skipped} unchanged)[/dim]"
    )


@app.command()
def query(
    search_query: str = typer.Option(..., "--query", "-q"),
    directory: str = typer.Option(".", "--dir", "-d"),
    use_regex: bool = typer.Option(False, "--regex"),
    fuzzy: bool = typer.Option(False, "--fuzzy"),
    field: str = typer.Option("content", "--field"),
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """Search the index (full-text, regex, or fuzzy)."""
    path = Path(directory).expanduser().resolve()
    index_dir = path / INDEX_DIR
    if use_regex:
        _regex_search(path, search_query, limit)
        return
    if not index_dir.exists():
        console.print(f"[red]No index found. Run: lexkit search --index {directory}[/red]")
        raise typer.Exit(1)
    ix = _open_or_create(index_dir)
    from whoosh.qparser import QueryParser, FuzzyTermPlugin
    with ix.searcher() as searcher:
        qp = QueryParser(field, ix.schema)
        if fuzzy:
            qp.add_plugin(FuzzyTermPlugin())
        q = qp.parse(f"{search_query}~1" if fuzzy else search_query)
        res = searcher.search(q, limit=limit)
        t = Table(title=f'Results for "{search_query}"', border_style="magenta")
        t.add_column("File", max_width=50)
        t.add_column("Author", width=18)
        t.add_column("Year", width=6)
        t.add_column("Score", width=8, justify="right")
        for hit in res:
            t.add_row(hit["filename"][:50], hit.get("author", "")[:18], hit.get("year", ""), f"{hit.score:.2f}")
        console.print(t)
        console.print(f"[dim]{len(res)} result(s)[/dim]")


@app.command()
def similar(
    directory: str = typer.Option(..., "--dir", "-d", help="Library directory."),
    to: str = typer.Option(..., "--to", "-t", help="Anchor file to find documents similar to."),
    threshold: float = typer.Option(0.25, "--threshold", help="Minimum cosine similarity."),
    limit: int = typer.Option(10, "--limit", "-n"),
) -> None:
    """Find documents similar to ``--to`` using deterministic TF-IDF cosine.

    Builds an in-memory TF-IDF model over the corpus and ranks by cosine
    similarity to the anchor document. Fully deterministic & offline.
    """
    from lexkit.analysis import TfidfModel, cosine_similarity
    from lexkit.core.scanner import iter_directory

    base = Path(directory).expanduser().resolve()
    anchor = Path(to).expanduser().resolve()
    docs: list[tuple[Path, str]] = []
    for fp in iter_directory(base):
        docs.append((fp, _read_text_cached(fp)[0]))
    if not docs:
        console.print("[yellow]No documents found.[/yellow]")
        return
    model = TfidfModel([d for _, d in docs])
    anchor_text = _read_text_cached(anchor)[0] if anchor.is_file() else anchor.read_text(encoding="utf-8", errors="replace")
    anchor_vec = model.transform(anchor_text)
    scored: list[tuple[Path, float]] = []
    for fp, text in docs:
        if fp.resolve() == anchor:
            continue
        sim = cosine_similarity(anchor_vec, model.transform(text))
        if sim >= threshold:
            scored.append((fp, sim))
    scored.sort(key=lambda kv: (-kv[1], str(kv[0])))
    scored = scored[:limit]
    t = Table(title=f"Similar to {anchor.name}", border_style="magenta")
    t.add_column("File", max_width=50)
    t.add_column("Similarity", width=12, justify="right")
    for fp, sim in scored:
        t.add_row(fp.name[:50], f"{sim:.3f}")
    console.print(t)
    console.print(f"[dim]{len(scored)} similar document(s)[/dim]")


# ── internals ──────────────────────────────────────────────────────────────────

def _read_text_cached(path: Path) -> tuple[str, str]:
    """Return (text, content_sha256). Caches extracted PDF text to a sidecar."""
    from lexkit.tools.batch import _extract_pdf
    sha = _content_sha(path)
    if path.suffix.lower() == ".pdf":
        cache = path.parent / CACHE_DIR / (path.stem + ".txt")
        if cache.exists():
            try:
                raw = cache.read_text(encoding="utf-8", errors="replace")
                nl = raw.find("\n")
                cached_sha, body = raw[:nl], raw[nl + 1 :]
                if cached_sha == sha:
                    return body, sha
            except Exception:
                pass
        text = _extract_pdf(path)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(sha + "\n" + text, encoding="utf-8")
        except OSError:
            pass
        return text, sha
    text = path.read_text(encoding="utf-8", errors="replace")
    return text, sha


def _content_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _regex_search(base: Path, pattern: str, limit: int) -> None:
    from lexkit.core.scanner import iter_directory
    rx = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    hits = 0
    for fp in iter_directory(base):
        try:
            for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    console.print(f"[cyan]{fp.name}[/cyan]:[dim]{i}[/dim]: {line.strip()[:120]}")
                    hits += 1
                    if hits >= limit:
                        console.print(f"[dim]{hits} match(es)[/dim]")
                        return
        except Exception:
            continue
    console.print(f"[dim]{hits} match(es)[/dim]")


def _open_or_create(index_dir: Path, rebuild: bool = False):
    from whoosh import index as wi
    from whoosh.fields import Schema, TEXT, ID, STORED
    schema = Schema(
        path=ID(stored=True, unique=True), filename=TEXT(stored=True),
        content=TEXT(stored=False), year=STORED(), author=TEXT(stored=True),
    )
    if rebuild and index_dir.exists():
        import shutil
        shutil.rmtree(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    return wi.open_dir(str(index_dir)) if wi.exists_in(str(index_dir)) else wi.create_in(str(index_dir), schema)
