"""
Plugin loader — discovers and loads plugins from importlib.metadata entry points.

Entry point group: "lexkit.plugins"

Built-in tools are registered via pyproject.toml's
[project.entry-points."lexkit.plugins"] section. They export bare
``typer.Typer`` objects, which the loader auto-wraps via :class:`TyperPlugin`.

Third-party packages may export either a ``PluginBase`` instance or a bare
``typer.Typer`` — both are handled transparently.
"""

from __future__ import annotations

from importlib.metadata import entry_points

from lexkit.errors          import LexKitPluginError
from lexkit.logging         import get_logger
from lexkit.plugins.base    import PluginBase, TyperPlugin
from lexkit.plugins.registry import registry

log = get_logger("plugin_loader")


def _is_typer_app(obj: object) -> bool:
    """Check if ``obj`` is a ``typer.Typer`` instance (duck-typed for safety)."""
    cls_name = type(obj).__name__
    mod_name = type(obj).__module__.split(".")[0]
    return cls_name == "Typer" and mod_name == "typer"


class PluginLoader:
    """Discover and load all plugins registered under 'lexkit.plugins'."""

    ENTRY_POINT_GROUP = "lexkit.plugins"

    def load_all(self) -> int:
        """
        Load all entry-point plugins into the global registry.
        Returns the number of successfully loaded plugins.
        """
        loaded = 0
        eps    = entry_points(group=self.ENTRY_POINT_GROUP)

        for ep in eps:
            try:
                obj = ep.load()

                # Already a PluginBase instance — great.
                if isinstance(obj, PluginBase):
                    plugin = obj
                # Bare typer.Typer app — auto-wrap with TyperPlugin adapter.
                elif _is_typer_app(obj):
                    plugin = TyperPlugin(
                        name=ep.name,
                        typer_app=obj,
                        description=getattr(obj, "help", None) or "",
                    )
                # A callable that returns a PluginBase (class export pattern).
                elif callable(obj) and not isinstance(obj, PluginBase):
                    maybe = obj()
                    if isinstance(maybe, PluginBase):
                        plugin = maybe
                    else:
                        raise LexKitPluginError(
                            f"Entry point '{ep.name}' callable did not return PluginBase.",
                            context={"type": type(maybe).__name__},
                        )
                else:
                    raise LexKitPluginError(
                        f"Entry point '{ep.name}' has unexpected type.",
                        context={"type": type(obj).__name__},
                    )

                if ep.name not in registry:
                    registry.register(plugin)
                loaded += 1
                log.info("plugin_loaded", plugin=ep.name, version=plugin.version)
            except LexKitPluginError as exc:
                log.exception("plugin_load_failed", exc, plugin=ep.name)
            except Exception as exc:
                log.exception("plugin_load_error", exc, plugin=ep.name)

        return loaded

    @staticmethod
    def register_typer_apps(cli_app) -> None:
        """Add all registered plugin Typer apps to the root CLI."""
        for plugin in registry:
            try:
                cli_app.add_typer(
                    plugin.typer_app,
                    name=plugin.name,
                    help=plugin.description or f"[Plugin] {plugin.name}",
                )
            except Exception as exc:
                log.exception("plugin_register_typer_failed", exc, plugin=plugin.name)
