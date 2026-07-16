"""
LeXKit CLI — v2.0.0 "Relate"
==============================
Root Typer application. Loads all plugins (built-in + third-party) via
the importlib.metadata entry-point group "lexkit.plugins", then registers
each plugin's Typer sub-app dynamically.

Built-in tools (fsm, clean, …) are shipped as first-class plugins via
[project.entry-points."lexkit.plugins"] in pyproject.toml. Bare Typer apps
are auto-wrapped by TyperPlugin in the loader.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text

from lexkit          import __version__
from lexkit.db.store import init_db, get_stats
from lexkit.config.settings import Settings
from lexkit.logging  import get_logger
from lexkit.errors   import LexKitError

log = get_logger("cli")

app = typer.Typer(
    name="lexkit",
    help=(
        "[bold magenta]LeXKit v2.0.0[/bold magenta] — Research OS.\n"
        "CLI-first · Deterministic · Zero cloud · Plugin-based · Optional AI."
    ),
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()

# ── Load all plugins (built-in + third-party) at import time ─────────────────
from lexkit.plugins.loader import PluginLoader as _PluginLoader

_loader = _PluginLoader()
_loaded = _loader.load_all()
_loader.register_typer_apps(app)


@app.callback(invoke_without_command=True)
def main(
    ctx:     typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version."),
    verbose: bool = typer.Option(False, "--verbose",       help="Enable DEBUG logging."),
) -> None:
    """LeXKit Research OS — offline, deterministic, high-performance."""
    if verbose:
        from lexkit.logging import configure
        configure(level="DEBUG")
    if version:
        console.print(f"[bold magenta]LeXKit[/bold magenta] v{__version__} — Research OS")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        text = Text()
        text.append("LeX", style="bold magenta")
        text.append("Kit", style="bold white")
        text.append(f"  v{__version__}", style="dim")
        console.print(Panel(
            text,
            subtitle=f"[dim]{_loaded} tools loaded · Run [bold]lexkit --help[/bold] for commands[/dim]",
            border_style="magenta",
        ))


@app.command()
def init(
    workspace: str = typer.Argument(".", help="Path to initialize workspace."),
) -> None:
    """Initialize a LeXKit workspace with config and SQLite database."""
    from pathlib import Path
    ws = Path(workspace).expanduser().resolve()
    try:
        ws.mkdir(parents=True, exist_ok=True)
        settings = Settings(workspace=ws)
        settings.save()
        init_db(settings.db_path)
        log.info("workspace_initialized", path=str(ws))
        console.print(Panel(
            f"[green]Workspace:[/green] {ws}\n"
            f"[green]Database: [/green] {settings.db_path}\n"
            f"[green]Config:   [/green] {settings.config_path}",
            title="[bold magenta]LeXKit[/bold magenta] — Workspace Ready",
            border_style="magenta",
        ))
    except LexKitError as exc:
        log.exception("init_failed", exc)
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@app.command()
def pipeline(
    run:        str = typer.Option(...,     help="Pipeline: intake | export | full"),
    input_path: str = typer.Option(..., "--input", help="Input directory."),
) -> None:
    """Execute a named pipeline of chained tools."""
    from lexkit.pipelines.runner import PipelineRunner
    from pathlib import Path
    try:
        PipelineRunner(input_path=Path(input_path)).run(run)
    except LexKitError as exc:
        log.exception("pipeline_failed", exc, pipeline=run)
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@app.command()
def plugins(
    list_all: bool = typer.Option(True, "--list", help="List all loaded plugins."),
) -> None:
    """List all loaded plugins (built-in and third-party)."""
    from lexkit.plugins.registry import registry
    all_plugins = registry.all()
    t = Table(title=f"Loaded Plugins ({len(all_plugins)})", border_style="magenta")
    t.add_column("Name",        style="magenta", width=14)
    t.add_column("Version",     style="cyan",    width=10)
    t.add_column("Description", style="white")
    for p in all_plugins:
        t.add_row(p.name, p.version, p.description or "—")
    console.print(t)


@app.command()
def gui(
    shortcut: bool = typer.Option(False, "--shortcut", help="Create a Windows desktop shortcut instead of launching."),
) -> None:
    """Launch the LeXKit desktop GUI (PySide6 dashboard).

    Equivalent to running ``lexkit-gui``. If PySide6 isn't installed, prints
    install instructions. Use ``--shortcut`` to drop a one-click desktop launcher.
    """
    try:
        from lexkit.gui import main as gui_main
    except ImportError:
        console.print(
            "[red]GUI dependencies not installed.[/red]\n\n"
            "Install them with:\n"
            "  [bold cyan]pip install \"lexkit[gui]\"[/bold cyan]\n"
        )
        raise typer.Exit(1)
    if shortcut:
        _create_shortcut()
        return
    console.print("[bold magenta]Launching LeXKit GUI…[/bold magenta]")
    raise typer.Exit(gui_main())


def _create_shortcut() -> None:
    """Create a one-click Windows desktop launcher (.bat) for the GUI."""
    import sys
    from pathlib import Path
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    pyexe = sys.executable
    bat = desktop / "LeXKit.bat"
    bat.write_text(
        f'@echo off\n'
        f'start "" "{pyexe}" -m lexkit.gui\n',
        encoding="utf-8",
    )
    console.print(f"[green]Desktop shortcut created:[/green] {bat}")
    console.print(f"[dim]Double-click it to launch LeXKit in one click.[/dim]")


@app.command()
def db(
    stats:      bool = typer.Option(False, "--stats",      help="Show stats."),
    clear:      bool = typer.Option(False, "--clear",      help="Clear all records."),
    list_files: bool = typer.Option(False, "--list-files", help="List indexed files."),
) -> None:
    """Manage the local SQLite database."""
    from lexkit.db.store import clear_db, list_all_files
    from lexkit.errors   import LexKitDatabaseError
    settings = Settings.load_default()
    try:
        if stats:
            s = get_stats(settings.db_path)
            console.print(
                f"Files: {s['files']}  Refs: {s['refs']}  "
                f"Citation edges: {s['citation_edges']}  "
                f"Near-dup clusters: {s['near_dup_clusters']}  "
                f"Size: {s['size_mb']:.2f}MB"
            )
        elif clear:
            if typer.confirm("Clear all data? This cannot be undone."):
                clear_db(settings.db_path)
                log.info("database_cleared")
                console.print("[green]Database cleared.[/green]")
        elif list_files:
            for f in list_all_files(settings.db_path):
                console.print(f"[dim]{f['path']}[/dim]  {f['size_kb']} KB")
    except LexKitError as exc:
        log.exception("db_command_failed", exc)
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
