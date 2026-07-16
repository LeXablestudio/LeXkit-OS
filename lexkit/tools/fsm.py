"""File System Manager — scan, sort, deduplicate, and near-duplicate cluster.

v2.0 changes:
- **Near-duplicate clustering** via MinHash alongside exact SHA-256 dedup.
- Richer auto-classify with more topic buckets.
- ``--cluster`` flag reports MinHash-based near-duplicate groups.
- Near-dup signatures stored in the DB for cross-session tracking.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from lexkit.core.scanner import scan_directory, FileMetadata
from lexkit.core.processor import make_progress
from lexkit.logging import get_logger

log = get_logger("fsm")

app = typer.Typer(help="File System Manager.")
console = Console()


@app.command()
def scan(
    directory: str = typer.Option(".", "--scan", "-s"),
    auto_sort: bool = typer.Option(False, "--auto-sort"),
    find_duplicates: bool = typer.Option(False, "--duplicates"),
    cluster_near_dups: bool = typer.Option(False, "--cluster", help="Run MinHash near-duplicate clustering."),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    export: Optional[str] = typer.Option(None, "--export"),
    output: Optional[str] = typer.Option(None, "--out"),
) -> None:
    """Scan a directory and display file metadata."""
    path = Path(directory).expanduser().resolve()
    if not path.exists():
        console.print(f"[red]Directory not found: {path}[/red]")
        raise typer.Exit(1)

    with make_progress() as p:
        task = p.add_task("Scanning...", total=None)
        files = scan_directory(path, recursive=recursive)
        p.update(task, completed=len(files), total=len(files))

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        return

    _print_table(files, show_duplicates=find_duplicates)
    dupes = [f for f in files if f.is_duplicate]
    if dupes:
        console.print(f"[yellow]Found {len(dupes)} exact duplicate(s).[/yellow]")

    if cluster_near_dups:
        _cluster_and_report(files, path)
    if auto_sort:
        _auto_sort(files, base=path)
    if export:
        _export(files, fmt=export, out_path=Path(output) if output else path / "metadata.json")


def _print_table(files: list[FileMetadata], show_duplicates: bool = False) -> None:
    t = Table(title=f"Found {len(files)} files", border_style="magenta")
    t.add_column("Filename", max_width=48)
    t.add_column("Year", style="cyan", width=6)
    t.add_column("Author", style="green", max_width=20)
    t.add_column("Size", style="yellow", width=10, justify="right")
    t.add_column("Type", style="dim", width=6)
    if show_duplicates:
        t.add_column("Dup", style="red", width=5)
    for f in files[:200]:
        row = [f.name[:48], f.year or "—", (f.author or "—")[:20], f"{f.size_kb:.1f} KB", f.suffix]
        if show_duplicates:
            row.append("✓" if f.is_duplicate else "")
        t.add_row(*row)
    console.print(t)


def _cluster_and_report(files: list[FileMetadata], base: Path) -> None:
    """Run MinHash near-duplicate clustering on file text content."""
    from lexkit.analysis.minhash import MinHasher, shingles, cluster_signatures
    from lexkit.db.store import get_db, upsert_near_duplicate
    from lexkit.config.settings import Settings

    # Collect text for non-PDFs; for PDFs, read first 4KB of text.
    signatures: dict[str, tuple[int, ...]] = {}
    file_paths: dict[str, Path] = {}
    mh = MinHasher(num_perm=128)

    with make_progress() as p:
        task = p.add_task("MinHash clustering...", total=len(files))
        for meta in files:
            try:
                text = _peek_text(meta.path)
                if text:
                    sig = mh.signature(shingles(text, n=5, unit="word"))
                    key = meta.name
                    signatures[key] = sig
                    file_paths[key] = meta.path
            except Exception:
                pass
            p.advance(task)

    if not signatures:
        console.print("[yellow]Not enough text content for near-duplicate analysis.[/yellow]")
        return

    result = cluster_signatures(signatures, bands=32, rows=4)

    # Store clusters in DB.
    db = get_db(Settings.load_default().db_path)
    for cid, members in result.clusters.items():
        for name in members:
            fp = file_paths.get(name)
            upsert_near_duplicate(
                db, path=str(fp) if fp else name, name=name,
                minhash=str(list(signatures[name][:8])) + "…",
                cluster_id=cid if len(members) > 1 else None,
                similarity=None,
            )
    db.close()

    multi = {cid: m for cid, m in result.clusters.items() if len(m) > 1}
    if multi:
        console.print(f"[bold magenta]Near-duplicate clusters: {len(multi)}[/bold magenta]")
        t = Table(border_style="magenta")
        t.add_column("Cluster", style="magenta", width=8)
        t.add_column("Members")
        for cid in sorted(multi):
            t.add_row(str(cid), ", ".join(multi[cid][:10]))
        console.print(t)
    else:
        console.print("[green]No near-duplicate clusters found.[/green]")

    log.info("near_dup_clustered", clusters=len(multi), files=len(files))


def _peek_text(path: Path, max_chars: int = 8000) -> str:
    """Extract a text snippet for MinHash shingling."""
    try:
        if path.suffix.lower() in {".txt", ".md", ".tex", ".rst"}:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        if path.suffix.lower() == ".pdf":
            from lexkit.tools.batch import _extract_pdf
            return _extract_pdf(path)[:max_chars]
    except Exception:
        pass
    return ""


def _auto_sort(files: list[FileMetadata], base: Path, dry_run: bool = False) -> None:
    moved = 0
    base.mkdir(parents=True, exist_ok=True)
    with make_progress() as p:
        task = p.add_task("Sorting...", total=len(files))
        for meta in files:
            year_folder = meta.year or "undated"
            topic_folder = _guess_topic(meta.stem)
            dest_dir = base / year_folder / topic_folder
            dest = dest_dir / meta.name
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(meta.path, dest)
                    moved += 1
            p.advance(task)
    console.print(f"[green]Sorted {moved} files.[/green]")


def _guess_topic(stem: str) -> str:
    s = stem.lower()
    topic_map = [
        (["nlp", "language", "text", "linguist", "syntax", "morpholog", "semantics", "corpus"], "nlp"),
        (["graph", "network", "knowledge", "ontology", "rdf", "sparql"], "knowledge-graphs"),
        (["machine", "learning", "neural", "deep", "transformer", "bert", "gpt", "llm"], "ml"),
        (["history", "medieval", "manuscript", "paleograph", "codicolog", "diplomat"], "humanities"),
        (["biology", "genom", "proteom", "bioinform", "evolut"], "bioinformatics"),
        (["physics", "quantum", "relativ", "thermodynamic", "cosmolog"], "physics"),
        (["sociolog", "anthropolog", "ethnograph", "demograph"], "social-science"),
        (["econom", "finance", "market", "trade", "fiscal", "monetar"], "economics"),
        (["psycholog", "cognit", "behaviour", "neuroscienc"], "psychology"),
    ]
    for keywords, topic in topic_map:
        if any(w in s for w in keywords):
            return topic
    return "general"


def _export(files: list[FileMetadata], fmt: str, out_path: Path) -> None:
    if fmt == "json":
        out_path.write_text(json.dumps([f.to_dict() for f in files], indent=2))
        console.print(f"[green]Exported → {out_path}[/green]")
    elif fmt == "csv":
        import csv
        p = out_path.with_suffix(".csv")
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["path", "name", "year", "author", "size_kb", "suffix"])
            w.writeheader()
            w.writerows([m.to_dict() for m in files])
        console.print(f"[green]Exported CSV → {p}[/green]")
