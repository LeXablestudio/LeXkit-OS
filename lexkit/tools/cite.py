"""Citation Graph — build, query, and export who-cites-whom networks.

The ``cite`` tool cross-matches extracted references against the library to
build a **citation network**: directed edges from each library file to the
cited reference it mentions. Edges are scored by a combination of filename
heuristics and TF-IDF title similarity via the deterministic
:mod:`lexkit.analysis` core.

Export formats: **GraphML** (Gephi / NetworkX), **JSON**, **Graphviz DOT**.

CLI sub-commands
-----------------
- ``lexkit cite build --input DIR``       — build the citation graph.
- ``lexkit cite graph --export FORMAT``    — export edges.
- ``lexkit cite stats``                   — summary statistics.
- ``lexkit cite list``                    — list all edges.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from lexkit.core.scanner import scan_directory, iter_directory
from lexkit.core.processor import make_progress
from lexkit.db.store import (
    get_db, upsert_citation_edge, list_citation_edges,
    clear_citation_edges, list_references,
)
from lexkit.config.settings import Settings
from lexkit.logging import get_logger
from lexkit.analysis import TfidfModel, cosine_similarity

log = get_logger("cite")

app = typer.Typer(help="Citation Graph — who-cites-whom network.")
console = Console()

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_AUTHOR_LEAD_RE = re.compile(r"^([A-Z][a-z]+)")


@app.command()
def build(
    input_path: str = typer.Option(..., "--input", "-i", help="Library directory."),
    threshold: float = typer.Option(0.25, "--threshold", help="Min TF-IDF similarity for title match."),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
) -> None:
    """Build the citation graph: match references against library files."""
    from lexkit.tools.batch import _extract_pdf

    path = Path(input_path).expanduser().resolve()
    settings = Settings.load_default()
    db = get_db(settings.db_path)

    # 1. Load stored references.
    refs = list_references(db, limit=100000)
    if not refs:
        console.print("[yellow]No references in database. Run: lexkit refs --input DIR first.[/yellow]")
        raise typer.Exit(1)
    console.print(f"[dim]Loaded {len(refs)} references.[/dim]")

    # 2. Scan library files and build a title→file mapping + TF-IDF model.
    files = scan_directory(path, recursive=recursive, compute_hashes=False)
    file_titles: dict[str, Path] = {}  # normalised title → file path
    file_texts: dict[str, str] = {}   # file stem -> full text
    with make_progress() as p:
        task = p.add_task("Reading library...", total=len(files))
        for meta in files:
            try:
                text = _extract_pdf(meta.path) if meta.suffix == ".pdf" else meta.path.read_text(encoding="utf-8", errors="replace")
                file_texts[meta.stem] = text
                # Build a filename-derived title for heuristic matching.
                title = _file_title(meta.stem)
                file_titles[_norm(title)] = meta.path
            except Exception:
                pass
            p.advance(task)

    if not file_texts:
        console.print("[yellow]No text-extractable files in library.[/yellow]")
        raise typer.Exit(1)

    # 3. TF-IDF model over ref titles + file titles.
    ref_title_texts = [r.get("title") or "" for r in refs]
    file_title_texts = list(file_texts.keys())
    model = TfidfModel(ref_title_texts + file_title_texts, ngram=1)

    # Pre-compute file vectors.
    file_stems = list(file_texts.keys())
    file_vectors = {stem: model.transform(stem) for stem in file_stems}

    # 4. Match each reference to library files.
    clear_citation_edges(db)
    edges_built = 0

    with make_progress() as p:
        task = p.add_task("Matching citations...", total=len(refs))
        for ref in refs:
            ref_title = ref.get("title") or ""
            ref_year = ref.get("year") or ""
            ref_author = ref.get("author") or ""
            if not ref_title:
                p.advance(task)
                continue

            ref_vec = model.transform(ref_title)
            ref_author_lead = _AUTHOR_LEAD_RE.match(ref_author or "")
            ref_author_norm = _norm(ref_author_lead.group(1)) if ref_author_lead else ""

            candidates: list[tuple[Path, float]] = []
            for stem, fvec in file_vectors.items():
                # Filename heuristic: author-year prefix match.
                fname_score = 0.0
                fn = stem.lower()
                if ref_author_norm and ref_author_norm in fn:
                    fname_score += 0.3
                if ref_year and ref_year in fn:
                    fname_score += 0.2

                # TF-IDF title similarity.
                sim = cosine_similarity(ref_vec, fvec)
                combined = max(fname_score, sim)

                if combined >= threshold:
                    candidates.append((file_titles.get(_norm(stem), Path(stem)), combined))

            # Keep the best match per reference (to avoid noise).
            if candidates:
                candidates.sort(key=lambda kv: -kv[1])
                best_path, best_score = candidates[0]
                source = ref.get("source_file") or "unknown"
                upsert_citation_edge(
                    db,
                    source_file=source,
                    target_file=str(best_path),
                    matched_ref=f"{ref_author} {ref_year}: {ref_title}"[:80],
                    score=best_score,
                )
                edges_built += 1
            p.advance(task)

    db.close()
    console.print(f"[green]Built {edges_built} citation edges.[/green]")
    log.info("cite_graph_built", edges=edges_built, refs=len(refs), files=len(files))


@app.command()
def graph(
    export: str = typer.Option("json", "--export", "-e", help="Format: graphml | json | dot"),
    output: Optional[str] = typer.Option(None, "--out", "-o"),
) -> None:
    """Export the citation graph."""
    settings = Settings.load_default()
    db = get_db(settings.db_path)
    edges = list_citation_edges(db)
    db.close()

    if not edges:
        console.print("[yellow]No citation edges. Run: lexkit cite build first.[/yellow]")
        raise typer.Exit(1)

    out = Path(output).expanduser().resolve() if output else Path(f"citation_graph.{export}")
    fmt = export.lower()
    writers = {"graphml": _write_graphml, "json": _write_json, "dot": _write_dot}
    writer = writers.get(fmt)
    if writer is None:
        console.print(f"[red]Unknown format '{fmt}'. Use: {', '.join(writers)}[/red]")
        raise typer.Exit(1)
    writer(edges, out)
    console.print(f"[green]Exported {len(edges)} edges → {out}[/green]")


@app.command()
def stats() -> None:
    """Summary statistics of the citation graph."""
    settings = Settings.load_default()
    db = get_db(settings.db_path)
    edges = list_citation_edges(db)
    db.close()

    if not edges:
        console.print("[yellow]No citation edges.[/yellow]")
        return

    out_deg = Counter(e["source_file"] for e in edges)
    in_deg = Counter(e["target_file"] for e in edges)
    nodes = set(out_deg) | set(in_deg)

    t = Table(title="Citation Graph Stats", border_style="magenta")
    t.add_column("Metric", style="magenta")
    t.add_column("Value", style="cyan", justify="right")
    t.add_row("Nodes (files)", str(len(nodes)))
    t.add_row("Edges (citations)", str(len(edges)))
    t.add_row("Most-cited file", (in_deg.most_common(1)[0][0].split("/")[-1] if in_deg else "—"))
    t.add_row("Highest out-degree", (out_deg.most_common(1)[0][0].split("/")[-1] if out_deg else "—"))
    isolated = sum(1 for n in nodes if n not in in_deg and n not in out_deg)
    t.add_row("Isolated nodes", str(isolated))
    console.print(t)


@app.command()
def list_edges(limit: int = typer.Option(50, "--limit", "-n")) -> None:
    """List citation edges."""
    settings = Settings.load_default()
    db = get_db(settings.db_path)
    edges = list_citation_edges(db)
    db.close()

    if not edges:
        console.print("[yellow]No edges.[/yellow]")
        return

    t = Table(title=f"Citation Edges (top {min(limit, len(edges))})", border_style="magenta")
    t.add_column("Source", max_width=40)
    t.add_column("→", style="magenta", width=2)
    t.add_column("Target", max_width=40)
    t.add_column("Score", width=8, justify="right")
    for e in edges[:limit]:
        src = (e["source_file"] or "—").split("/")[-1][:40]
        tgt = (e["target_file"] or "—").split("/")[-1][:40]
        t.add_row(src, "→", tgt, f"{e['score']:.2f}")
    console.print(t)


# ── Export writers ────────────────────────────────────────────────────────────

def _write_graphml(edges: list[dict], out: Path) -> None:
    nodes: dict[str, str] = {}
    for e in edges:
        nodes[e["source_file"]] = nodes.get(e["source_file"], "source")
        nodes[e["target_file"]] = nodes.get(e["target_file"], "target")
    with out.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n')
        f.write('  <key id="d0" for="edge" attr.name="score" attr.type="double"/>\n')
        f.write('  <key id="d1" for="edge" attr.name="matched_ref" attr.type="string"/>\n')
        f.write('  <key id="d2" for="node" attr.name="role" attr.type="string"/>\n')
        f.write('  <graph id="CitationGraph" edgedefault="directed">\n')
        for nid in sorted(nodes):
            f.write(f'    <node id="{_xml_escape(nid)}">\n')
            f.write(f'      <data key="d2">{nodes[nid]}</data>\n')
            f.write('    </node>\n')
        for e in edges:
            f.write(
                f'    <edge source="{_xml_escape(e["source_file"])}" '
                f'target="{_xml_escape(e["target_file"])}">\n'
                f'      <data key="d0">{e["score"]:.4f}</data>\n'
                f'      <data key="d1">{_xml_escape(e.get("matched_ref") or "")}</data>\n'
                f'    </edge>\n'
            )
        f.write("  </graph>\n</graphml>\n")


def _write_json(edges: list[dict], out: Path) -> None:
    import json
    data = {
        "directed": True,
        "multigraph": False,
        "nodes": sorted(set(e["source_file"] for e in edges) | set(e["target_file"] for e in edges)),
        "edges": [
            {"source": e["source_file"], "target": e["target_file"],
             "score": round(e["score"], 4), "matched_ref": e.get("matched_ref")}
            for e in edges
        ],
    }
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_dot(edges: list[dict], out: Path) -> None:
    with out.open("w", encoding="utf-8") as f:
        f.write("digraph CitationGraph {\n")
        for e in edges:
            src = e["source_file"].split("/")[-1].replace(".", "_")
            tgt = e["target_file"].split("/")[-1].replace(".", "_")
            label = e.get("matched_ref", "")[:30]
            f.write(f'  "{src}" -> "{tgt}" [label="{_dot_escape(label)}"];\n')
        f.write("}\n")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _file_title(stem: str) -> str:
    """Derive a readable title from a filename stem by replacing _/- with spaces."""
    return re.sub(r"[_\-]+", " ", stem)


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _dot_escape(s: str) -> str:
    return s.replace('"', '\\"').replace("\\", "\\\\")
