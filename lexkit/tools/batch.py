"""Batch Processor — rename, convert, extract text from files.

v2.0 changes:
- Structured logging for all operations.
- Deterministic error counts and reporting.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from lexkit.core.processor import BaseProcessor, make_progress
from lexkit.core.scanner import scan_directory
from lexkit.logging import get_logger

log = get_logger("batch")

app = typer.Typer(help="Batch Processor.")
console = Console()


@app.command()
def rename(
    input_path: str = typer.Option(..., "--input", "-i"),
    pattern: str = typer.Option("{year}_{author}_{stem}", "--pattern"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
) -> None:
    """Bulk rename files using a pattern template."""
    path = Path(input_path).expanduser().resolve()
    files = scan_directory(path, recursive=recursive, compute_hashes=False)
    renamed = 0
    with make_progress() as p:
        task = p.add_task("Renaming...", total=len(files))
        for meta in files:
            new_name = pattern.format(
                year=meta.year or "undated",
                author=_slug(meta.author or "unknown"),
                stem=_slug(meta.stem)[:40],
                suffix=meta.suffix,
            ) + meta.suffix
            new_path = meta.path.parent / new_name
            if not dry_run and not new_path.exists():
                meta.path.rename(new_path)
                renamed += 1
            elif dry_run:
                console.print(f"[dim]{meta.name}[/dim] → [cyan]{new_name}[/cyan]")
                renamed += 1
            p.advance(task)
    console.print(f"[green]Renamed {renamed} files[/green]")
    log.info("batch_rename", renamed=renamed, dry_run=dry_run)


@app.command()
def extract(
    input_path: str = typer.Option(..., "--input", "-i"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o"),
    fmt: str = typer.Option("txt", "--format", "-f"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
) -> None:
    """Extract text from PDFs to plaintext files."""
    path = Path(input_path).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve() if output_dir else path / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    files = [f.path for f in scan_directory(path, recursive=recursive, compute_hashes=False) if f.suffix == ".pdf"]
    with make_progress() as p:
        task = p.add_task("Extracting...", total=len(files))
        ok = 0
        for fp in files:
            try:
                text = _extract_pdf(fp)
                (out / (fp.stem + "." + fmt)).write_text(text, encoding="utf-8")
                ok += 1
            except Exception as exc:
                log.exception("batch_extract_failed", exc, file=str(fp))
            p.advance(task)
    console.print(f"[green]Extracted {ok}/{len(files)} files → {out}[/green]")
    log.info("batch_extract", ok=ok, total=len(files))


def _extract_pdf(path: Path) -> str:
    """Extract text from a PDF using pdfminer (primary) or fitz (fallback)."""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(path))
    except Exception:
        try:
            import fitz
            doc = fitz.open(str(path))
            return "\n\n".join(page.get_text() for page in doc)
        except Exception:
            return ""


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "_", text).strip("_")
