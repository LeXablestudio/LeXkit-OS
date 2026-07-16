"""
Thread-safe plugin registry.
Maps plugin names to their PluginBase instances.
"""

from __future__ import annotations

import threading
from typing import Iterator

from lexkit.plugins.base import PluginBase
from lexkit.errors       import LexKitPluginError


class PluginRegistry:
    """Singleton-style, thread-safe store for all loaded plugins."""

    def __init__(self) -> None:
        self._lock:    threading.Lock              = threading.Lock()
        self._plugins: dict[str, PluginBase]       = {}

    def register(self, plugin: PluginBase) -> None:
        """Register a plugin. Raises LexKitPluginError if name is already taken."""
        if not isinstance(plugin, PluginBase):
            raise LexKitPluginError(
                f"Cannot register {plugin!r}: must be a PluginBase subclass.",
                context={"type": type(plugin).__name__},
            )
        if not plugin.name:
            raise LexKitPluginError("Plugin has no name.", context={"plugin": repr(plugin)})

        with self._lock:
            if plugin.name in self._plugins:
                raise LexKitPluginError(
                    f"Plugin '{plugin.name}' is already registered.",
                    context={"existing": repr(self._plugins[plugin.name])},
                )
            self._plugins[plugin.name] = plugin

    def get(self, name: str) -> PluginBase | None:
        with self._lock:
            return self._plugins.get(name)

    def all(self) -> list[PluginBase]:
        with self._lock:
            return sorted(self._plugins.values(), key=lambda p: p.name)

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._plugins.keys())

    def __iter__(self) -> Iterator[PluginBase]:
        return iter(self.all())

    def __len__(self) -> int:
        with self._lock:
            return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._plugins


# ── Global registry singleton ─────────────────────────────────────────────────
registry = PluginRegistry()
