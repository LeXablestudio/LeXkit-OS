"""Base processor and shared Rich progress bar."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
    TaskProgressColumn, TextColumn, TimeRemainingColumn,
)

console = Console()


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=32, style="magenta", complete_style="bright_magenta"),
        MofNCompleteColumn(), TaskProgressColumn(), TimeRemainingColumn(),
        console=console,
    )


class BaseProcessor(ABC):
    def __init__(self, input_path: Path, output_path: Path | None = None, **kwargs: Any) -> None:
        self.input_path  = input_path
        self.output_path = output_path or input_path.parent / (input_path.stem + "_output")
        self.options = kwargs
        self.errors: list[str] = []
        self.processed = 0
        self.skipped   = 0

    @abstractmethod
    def process(self) -> dict[str, Any]: ...

    def report(self) -> None:
        console.print(
            f"[green]✓[/green] Processed: [cyan]{self.processed}[/cyan]  "
            f"Skipped: [yellow]{self.skipped}[/yellow]  "
            f"Errors: [red]{len(self.errors)}[/red]"
        )
        for err in self.errors[:10]:
            console.print(f"  [red]✗[/red] {err}")
