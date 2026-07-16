"""Notes Compiler — merge, deduplicate, and near-duplicate-cluster research notes.

v2.0 changes:
- **Near-duplicate paragraph detection** via MinHash alongside exact-hash dedup.
- ``--near-dup-threshold`` to control sensitivity.
- Reports on near-duplicate clusters found.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from lexkit.logging import get_logger

log = get_logger("notes")

app = typer.Typer(help="Notes Compiler.")
console = Console()
NOTE_EXTS = {".md", ".txt", ".tex", ".rst"}


@app.command()
def run(
    input_path: str = typer.Option(..., "--input", "-i"),
    output: Optional[str] = typer.Option(None, "--out", "-o"),
    dedup: bool = typer.Option(True, "--dedup/--no-dedup"),
    near_dup: bool = typer.Option(True, help="Enable MinHash near-duplicate paragraph dedup."),
    near_dup_threshold: float = typer.Option(0.7, "--near-dup-threshold", help="MinHash similarity threshold (0–1)."),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    sort_by: str = typer.Option("name", "--sort"),
) -> None:
    """Merge multiple note files into a single structured markdown document."""
    path = Path(input_path).expanduser().resolve()
    out = Path(output).expanduser().resolve() if output else path / "compiled_notes.md"
    files = sorted(
        [p for p in (path.rglob("*") if recursive else path.glob("*")) if p.is_file() and p.suffix.lower() in NOTE_EXTS],
        key=lambda x: x.name if sort_by == "name" else x.stat().st_size,
    )
    if not files:
        console.print("[yellow]No note files found.[/yellow]")
        return

    from lexkit.core.processor import make_progress

    seen_exact: set[str] = set()
    sections = ["# Compiled Research Notes\n"]
    dedup_n = 0
    near_dup_n = 0

    # Optional MinHash signatures for near-dup detection.
    from lexkit.analysis.minhash import MinHasher, shingles, signature_similarity
    mh = MinHasher(num_perm=64)
    sig_cache: list[tuple[str, tuple[int, ...]]] = []  # (para_text, sig)

    with make_progress() as p:
        task = p.add_task("Merging...", total=len(files))
        for fp in files:
            try:
                paras = _paras(fp.read_text(encoding="utf-8", errors="replace"))
                kept = []
                for para in paras:
                    h = _hash(para)
                    # Exact dedup.
                    if dedup and h in seen_exact:
                        dedup_n += 1
                        continue
                    # Near-dup dedup via MinHash.
                    if near_dup and len(para) > 40:
                        sig = mh.signature(shingles(para, n=3, unit="word"))
                        is_near = False
                        for prev_text, prev_sig in sig_cache:
                            if signature_similarity(sig, prev_sig) >= near_dup_threshold:
                                near_dup_n += 1
                                is_near = True
                                break
                        if is_near:
                            continue
                        sig_cache.append((para, sig))
                    seen_exact.add(h)
                    kept.append(para)
                if kept:
                    sections.append(f"\n## {fp.stem}\n")
                    sections.extend(kept)
            except Exception as e:
                console.print(f"[red]{fp.name}: {e}[/red]")
            p.advance(task)
    out.write_text("\n\n".join(sections), encoding="utf-8")
    console.print(
        f"[green]Compiled {len(files)} files → {out}[/green] "
        f"[dim](exact dedup: {dedup_n}, near-dup: {near_dup_n})[/dim]"
    )


def _paras(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


def _hash(para: str) -> str:
    return hashlib.md5(re.sub(r"\s+", " ", para.strip().lower()).encode()).hexdigest()
