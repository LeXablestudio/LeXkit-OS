"""Template Generator — APA, IEEE, ACM, MLA paper stubs + markdown notes.

v2.0 changes:
- Added **MLA** LaTeX template.
- Added **Markdown** note/research-log template.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Template Generator.")
console = Console()

TEMPLATES: dict[str, dict[str, str]] = {
    "apa": {"desc": "APA 7th Edition research paper", "ext": ".tex"},
    "ieee": {"desc": "IEEE Conference/Journal paper", "ext": ".tex"},
    "acm": {"desc": "ACM SIGCONF paper", "ext": ".tex"},
    "mla": {"desc": "MLA 9th Edition research paper", "ext": ".tex"},
    "markdown": {"desc": "Markdown research notes / reading log", "ext": ".md"},
}


@app.command()
def generate(
    fmt: str = typer.Option("apa", "--format", "-f"),
    title: str = typer.Option("Research Paper Title", "--title", "-t"),
    author: str = typer.Option("Author Name", "--author", "-a"),
    output: Optional[str] = typer.Option(None, "--out", "-o"),
) -> None:
    """Generate a paper template pre-filled with section stubs."""
    fmt = fmt.lower()
    if fmt not in TEMPLATES:
        console.print(f"[red]Unknown format. Use: {', '.join(TEMPLATES)}[/red]")
        raise typer.Exit(1)
    content = _render(fmt, title=title, author=author)
    out_path = Path(output).expanduser().resolve() if output else Path(f"paper_{fmt}.{TEMPLATES[fmt]['ext']}")
    out_path.write_text(content, encoding="utf-8")
    console.print(f"[green]Template generated → {out_path}[/green]")


@app.command("list")
def list_templates() -> None:
    """List available templates."""
    t = Table(title="Templates", border_style="magenta")
    t.add_column("Format", style="magenta", width=10)
    t.add_column("Description", style="white")
    t.add_column("Ext", style="cyan", width=6)
    for k, v in TEMPLATES.items():
        t.add_row(k.upper(), v["desc"], v["ext"])
    console.print(t)


def _render(fmt: str, title: str, author: str) -> str:
    return {
        "apa": _apa,
        "ieee": _ieee,
        "acm": _acm,
        "mla": _mla,
        "markdown": _markdown,
    }[fmt](title, author)


def _apa(title: str, author: str) -> str:
    return (
        "\\documentclass[12pt,apa7]{apa7}\n"
        "\\usepackage[american]{babel}\n"
        "\\usepackage[style=apa,backend=biber]{biblatex}\n\n"
        f"\\title{{{title}}}\n\\author{{{author}}}\n\\date{{\\today}}\n\n"
        "\\begin{document}\n\\maketitle\n\n"
        "\\begin{abstract}\n% Abstract (150–250 words).\n\\end{abstract}\n\n"
        "\\section{Introduction}\n% Introduce the research problem.\n\n"
        "\\section{Literature Review}\n% Summarize existing research.\n\n"
        "\\section{Method}\n% Describe methodology.\n\n"
        "\\section{Results}\n% Present findings.\n\n"
        "\\section{Discussion}\n% Interpret results.\n\n"
        "\\section{Conclusion}\n% Summarize contributions.\n\n"
        "\\printbibliography\n\\end{document}\n"
    )


def _ieee(title: str, author: str) -> str:
    return (
        "\\documentclass[conference]{IEEEtran}\n"
        "\\usepackage{amsmath,graphicx,cite}\n\n"
        f"\\title{{{title}}}\n"
        f"\\author{{\\IEEEauthorblockN{{{author}}}\\IEEEauthorblockA{{Institution\\\\email@institution.edu}}}}\n\n"
        "\\begin{document}\n\\maketitle\n\n"
        "\\begin{abstract}\n% 150-word abstract.\n\\end{abstract}\n\n"
        "\\begin{IEEEkeywords}\nkeyword1, keyword2\n\\end{IEEEkeywords}\n\n"
        "\\section{Introduction}\n% Motivate the problem.\n\n"
        "\\section{Related Work}\n% Prior work.\n\n"
        "\\section{Proposed Approach}\n% Method.\n\n"
        "\\section{Experiments}\n% Setup and results.\n\n"
        "\\section{Conclusion}\n% Summary.\n\n"
        "\\bibliographystyle{IEEEtran}\n\\bibliography{references}\n\\end{document}\n"
    )


def _acm(title: str, author: str) -> str:
    return (
        "\\documentclass[sigconf]{acmart}\n"
        "\\usepackage{booktabs}\n\n"
        f"\\title{{{title}}}\n\\author{{{author}}}\n"
        "\\affiliation{\\institution{Institution Name}}\n\\email{author@institution.edu}\n\n"
        "\\begin{document}\n\\maketitle\n\n"
        "\\begin{abstract}\n% Abstract (150–200 words).\n\\end{abstract}\n\n"
        "\\keywords{keyword1, keyword2}\n\n"
        "\\section{Introduction}\n% Problem and contributions.\n\n"
        "\\section{Background}\n% Theoretical background.\n\n"
        "\\section{System Design}\n% Architecture.\n\n"
        "\\section{Evaluation}\n% Results.\n\n"
        "\\section{Related Work}\n% Comparison.\n\n"
        "\\section{Conclusion}\n% Summary.\n\n"
        "\\bibliographystyle{ACM-Reference-Format}\n\\bibliography{references}\n\\end{document}\n"
    )


def _mla(title: str, author: str) -> str:
    return (
        "\\documentclass[12pt]{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage{setspace}\n\\doublespacing\n\n"
        "\\begin{document}\n\n"
        f"\\noindent {author}\\\\\n"
        f"{title}\\\\\n"
        "\\today\n\n"
        "\\noindent\\maketitle\n\n"
        "\\begin{abstract}\n% Abstract (optional in MLA, 150–200 words).\n\\end{abstract}\n\n"
        "\\section*{Introduction}\n% Introduce the topic and thesis.\n\n"
        "\\section*{Background}\n% Context and relevant prior work.\n\n"
        "\\section*{Analysis}\n% Close reading, evidence, argument.\n\n"
        "\\section*{Conclusion}\n% Restate thesis and implications.\n\n"
        "\\begin{thebibliography}{9}\n% \\bibitem{key} Author. \\emph{Title}. Publisher, Year.\n\\end{thebibliography}\n\n"
        "\\end{document}\n"
    )


def _markdown(title: str, author: str) -> str:
    return (
        f"# {title}\n\n"
        f"**Author:** {author}  \n"
        f"**Date:** {{date}}  \n\n"
        "---\n\n"
        "## Objective\n\n<!-- What question or hypothesis drives this work? -->\n\n\n"
        "## Key Sources\n\n"
        "| # | Citation | Notes |\n"
        "|---|----------|-------|\n"
        "| 1 | | |\n\n\n"
        "## Findings\n\n<!-- Main observations, data, patterns. -->\n\n\n"
        "## Argument / Position\n\n<!-- Your analysis and reasoning chain. -->\n\n\n"
        "## Open Questions\n\n- \n\n\n"
        "## Next Steps\n\n- \n\n"
        "---\n"
        f"*Generated by LeXKit v2.0.0*\n"
    )
