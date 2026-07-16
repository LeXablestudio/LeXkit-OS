"""Rich terminal formatting helpers."""
from rich.console import Console
from rich.panel import Panel

console = Console()

def success(msg: str) -> None: console.print(f"[bold green]✓[/bold green] {msg}")
def error(msg: str) -> None:   console.print(f"[bold red]✗[/bold red] {msg}")
def warn(msg: str) -> None:    console.print(f"[bold yellow]⚠[/bold yellow] {msg}")
def info(msg: str) -> None:    console.print(f"[bold magenta]→[/bold magenta] {msg}")
def header(title: str, sub: str = "") -> None:
    console.print(Panel(f"[bold magenta]{title}[/bold magenta]{'  ' + sub if sub else ''}", border_style="magenta"))
