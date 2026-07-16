"""Pipeline runner — chain tools into reproducible workflows."""

from __future__ import annotations

from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

PIPELINES: dict[str, list[dict]] = {
    "intake": [
        {"tool": "fsm",    "args": {"auto_sort": True}},
        {"tool": "clean",  "args": {}},
        {"tool": "search", "args": {}},
        {"tool": "refs",   "args": {}},
    ],
    "export": [
        {"tool": "refs",   "args": {"action": "export", "fmt": "bibtex"}},
        {"tool": "notes",  "args": {"dedup": True}},
    ],
    "full": [
        {"tool": "fsm",   "args": {"auto_sort": True}},
        {"tool": "clean", "args": {}},
        {"tool": "search","args": {}},
        {"tool": "refs",  "args": {}},
        {"tool": "notes", "args": {}},
    ],
}


class PipelineRunner:
    def __init__(self, input_path: Path) -> None:
        self.input_path = input_path

    def run(self, pipeline_name: str) -> None:
        steps = PIPELINES.get(pipeline_name)
        if not steps:
            console.print(f"[red]Unknown pipeline. Available: {', '.join(PIPELINES)}[/red]"); return
        console.print(Panel(f"[bold]Pipeline:[/bold] [magenta]{pipeline_name}[/magenta]  Steps: {len(steps)}", border_style="magenta"))
        for i, step in enumerate(steps, 1):
            console.print(f"\n[bold magenta][{i}/{len(steps)}][/bold magenta] {step['tool']}...")
            try:
                self._run_step(step["tool"], step.get("args", {}))
                console.print(f"  [green]✓ {step['tool']} done[/green]")
            except Exception as e:
                console.print(f"  [red]✗ {step['tool']}: {e}[/red]")
        console.print(f"\n[green]Pipeline '{pipeline_name}' complete.[/green]")

    def _run_step(self, tool: str, args: dict) -> None:
        p = str(self.input_path)
        import lexkit.tools.fsm    as _fsm
        import lexkit.tools.clean  as _clean
        import lexkit.tools.search as _search
        import lexkit.tools.refs   as _refs
        import lexkit.tools.notes  as _notes
        {
            "fsm":    lambda: _fsm.scan(directory=p, auto_sort=args.get("auto_sort",False), find_duplicates=False, recursive=True, export=None, output=None),
            "clean":  lambda: _clean.run(input_path=p, recursive=True, fix_encoding=True, dry_run=False, output_dir=None),
            "search": lambda: _search.index(directory=p, rebuild=False),
            "refs":   lambda: _refs.extract(input_path=p, recursive=True),
            "notes":  lambda: _notes.run(input_path=p, output=None, dedup=True, recursive=True, sort_by="name"),
        }.get(tool, lambda: None)()
