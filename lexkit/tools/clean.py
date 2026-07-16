"""Document Cleaner — fix PDFs, normalize encoding, remove junk.

v2.0 changes:
- Deterministic byte counts and processing statistics.
- Cleaner error routing through ``BaseProcessor.report()``.
- Structured logging of every repair/clean action.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from lexkit.core.processor import BaseProcessor, make_progress
from lexkit.logging import get_logger

log = get_logger("clean")

app = typer.Typer(help="Document Cleaner.")
console = Console()

JUNK_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]|\ufffd|\s{3,}")


@app.command()
def run(
    input_path: str = typer.Option(..., "--input", "-i"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    fix_encoding: bool = typer.Option(True, "--fix-encoding/--no-fix-encoding"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Clean documents: fix encoding, remove junk, standardize whitespace."""
    path = Path(input_path).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve() if output_dir else None
    cleaner = DocumentCleaner(
        input_path=path, output_path=out, recursive=recursive,
        fix_encoding=fix_encoding, dry_run=dry_run,
    )
    results = cleaner.process()
    cleaner.report()
    console.print(
        f"[dim]Repaired: {results.get('repaired', 0)}  "
        f"Cleaned: {results.get('cleaned', 0)}  "
        f"Bytes saved: {results.get('bytes_saved', 0):,}[/dim]"
    )
    log.info("clean_complete", **results)


class DocumentCleaner(BaseProcessor):
    def process(self) -> dict:
        from lexkit.core.scanner import scan_directory
        dry_run = self.options.get("dry_run", False)
        if self.input_path.is_file():
            fps = [self.input_path]
        else:
            fps = [f.path for f in scan_directory(
                self.input_path, recursive=self.options.get("recursive", True),
                compute_hashes=False,
            )]

        repaired = cleaned = bytes_saved = 0
        with make_progress() as p:
            task = p.add_task("Cleaning...", total=len(fps))
            for fp in fps:
                try:
                    if fp.suffix.lower() == ".pdf":
                        if _pdf_corrupted(fp) and not dry_run:
                            _repair_pdf(fp)
                            repaired += 1
                            log.info("pdf_repaired", file=str(fp))
                    elif fp.suffix.lower() in {".txt", ".md", ".tex"}:
                        text = _read(fp, self.options.get("fix_encoding", True))
                        ct = clean_text(text)
                        saved = len(text.encode("utf-8")) - len(ct.encode("utf-8"))
                        if ct != text and not dry_run:
                            fp.write_text(ct, encoding="utf-8")
                            bytes_saved += saved
                            log.info("text_cleaned", file=str(fp), bytes_saved=saved)
                        cleaned += 1
                    self.processed += 1
                except Exception as e:
                    self.errors.append(f"{fp.name}: {e}")
                    self.skipped += 1
                    log.exception("clean_file_failed", exc=e, file=str(fp))
                p.advance(task)
        return {"repaired": repaired, "cleaned": cleaned, "bytes_saved": bytes_saved}


def clean_text(text: str) -> str:
    """Normalise and clean text deterministically."""
    text = unicodedata.normalize("NFC", text)
    text = JUNK_RE.sub(" ", text)
    text = "\n".join(l.rstrip() for l in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read(path: Path, fix: bool = True) -> str:
    if not fix:
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        import chardet
        raw = path.read_bytes()
        enc = chardet.detect(raw).get("encoding") or "latin-1"
        return raw.decode(enc, errors="replace")


def _pdf_corrupted(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return not f.read(8).startswith(b"%PDF")
    except OSError:
        return True


def _repair_pdf(path: Path) -> None:
    try:
        import fitz
        doc = fitz.open(str(path))
        doc.save(str(path), garbage=4, deflate=True, clean=True)
        doc.close()
    except Exception as exc:
        log.warning("pdf_repair_failed", file=str(path), error=str(exc))
