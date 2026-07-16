"""
LeXKit Plugin System — v2.0
===========================
Plugins are discovered at runtime via importlib.metadata entry points
under the group "lexkit.plugins".

To create a plugin package:

  1. Create a Python package, e.g. lexkit-plugin-ocr
  2. In its pyproject.toml:

     [project.entry-points."lexkit.plugins"]
     ocr = "lexkit_plugin_ocr:plugin"

  3. The exported object must be a PluginBase subclass instance.

Built-in tools (fsm, clean, ...) are also registered through this
same entry-point group, wrapped via TyperPlugin so they behave identically
to third-party plugins.
"""

from lexkit.plugins.base     import PluginBase, TyperPlugin
from lexkit.plugins.registry import PluginRegistry
from lexkit.plugins.loader   import PluginLoader

__all__ = ["PluginBase", "TyperPlugin", "PluginRegistry", "PluginLoader"]
