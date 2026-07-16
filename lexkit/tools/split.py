"""Lecture Splitter — split PDFs by table of contents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.tree import Tree

app = typer.Typer(help="Lecture Splitter.")
console = Console()

SECTION_RES = [
    re.compile(r"^(Chapter|Section|Part|Unit|Lecture)\s+(\d+|[IVXLC]+)\.?\s+(.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(\d+)\.\s+([A-Z].+)$", re.MULTILINE),
]


@app.command()
def run(
    input_file: str           = typer.Option(..., "--input", "-i"),
    show_toc:   bool          = typer.Option(False, "--toc"),
    output_dir: Optional[str] = typer.Option(None,  "--output", "-o"),
    min_pages:  int           = typer.Option(2,     "--min-pages"),
) -> None:
    """Split a PDF into sections by table of contents."""
    fp = Path(input_file).expanduser().resolve()
    if not fp.exists() or fp.suffix.lower() != ".pdf":
        console.print(f"[red]Not a valid PDF: {fp}[/red]"); raise typer.Exit(1)
    out      = Path(output_dir).expanduser().resolve() if output_dir else fp.parent / fp.stem
    sections = _detect(fp)
    if not sections:
        console.print("[yellow]No table of contents detected.[/yellow]"); return
    if show_toc:
        t = Tree(f"[bold magenta]{fp.name}[/bold magenta]")
        for s in sections:
            t.add(f"[dim]p.{s['page']+1}[/dim] {s['title']}")
        console.print(t); return
    _split(fp, sections, out, min_pages)


def _detect(pdf_path: Path) -> list[dict]:
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        toc = doc.get_toc()
        if toc:
            doc.close()
            return [{"title": i[1], "page": i[2]-1, "level": i[0]} for i in toc if i[2]>0]
        sections = []
        for pn in range(min(10, len(doc))):
            text = doc[pn].get_text()
            for rx in SECTION_RES:
                for m in rx.finditer(text):
                    title = m.group(m.lastindex or 1).strip()
                    if len(title) > 3:
                        sections.append({"title": title, "page": pn, "level": 1})
        doc.close()
        return sections
    except Exception:
        return []


def _split(pdf_path: Path, sections: list[dict], out: Path, min_pages: int) -> None:
    import fitz
    doc   = fitz.open(str(pdf_path))
    total = len(doc)
    out.mkdir(parents=True, exist_ok=True)
    saved = 0
    from lexkit.core.processor import make_progress
    with make_progress() as p:
        task = p.add_task("Splitting...", total=len(sections))
        for i, sec in enumerate(sections):
            start = sec["page"]
            end   = sections[i+1]["page"] if i+1 < len(sections) else total
            if (end-start) < min_pages:
                p.advance(task); continue
            new   = fitz.open()
            new.insert_pdf(doc, from_page=start, to_page=end-1)
            safe  = re.sub(r"[^\w\s-]","",sec["title"])[:50].strip().replace(" ","_")
            new.save(str(out / f"{i+1:02d}_{safe}.pdf"))
            new.close(); saved += 1
            p.advance(task)
    doc.close()
    console.print(f"[green]Split into {saved} sections → {out}[/green]")
