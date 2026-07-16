"""Abstract base class for all LeXKit plugins.

Built-in tools export bare ``typer.Typer`` objects via entry points; the
:class:`TyperPlugin` adapter wraps them into :class:`PluginBase` instances so
the loader can handle both styles transparently.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer


class PluginBase(ABC):
    """
    Base class every LeXKit plugin must subclass.

    Minimal example::

        import typer
        from lexkit.plugins import PluginBase

        app = typer.Typer(help="OCR plugin — extract text from scanned PDFs.")

        class OcrPlugin(PluginBase):
            name    = "ocr"
            version = "0.1.0"
            description = "OCR text extraction for scanned PDFs."

            @property
            def typer_app(self):
                return app

        plugin = OcrPlugin()
    """

    #: Unique snake_case identifier — must match the entry-point key.
    name: str = ""

    #: SemVer version string.
    version: str = "0.0.0"

    #: Human-readable description shown in ``lexkit plugins --list``.
    description: str = ""

    @property
    @abstractmethod
    def typer_app(self) -> "typer.Typer":
        """Return the Typer application for this plugin."""
        ...

    def __repr__(self) -> str:
        return f"<Plugin name={self.name!r} version={self.version!r}>"


class TyperPlugin(PluginBase):
    """Adapter that wraps a bare ``typer.Typer`` app into a :class:`PluginBase`.

    This lets built-in tools (which export ``app = typer.Typer(…)`` via entry
    points) participate in the plugin system without refactoring.

    Parameters
    ----------
    name
        Plugin identifier (must match the entry-point key).
    typer_app
        The bare Typer application.
    description
        Optional help text.
    version
        Version string, defaults to ``"2.0.0"`` for built-in tools.
    """

    def __init__(
        self,
        name: str,
        typer_app: "typer.Typer",
        description: str = "",
        version: str = "2.0.0",
    ) -> None:
        self.name = name
        self._app = typer_app
        self.description = description
        self.version = version

    @property
    def typer_app(self) -> "typer.Typer":
        return self._app
