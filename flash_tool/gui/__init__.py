"""flash_tool.gui package

Small GUI package for the flash tool.

This package exposes:
- GUIApp: the main Qt application entry point
- gui_api: the production programmatic GUI API used by widgets and tools

Stubs and test helpers (for example ``gui_api_stub``) are available as
separate modules but are **not** wired in automatically here. This
enforces the "no silent demo mode" rule from the development guide: if
the production GUI API cannot be imported, the error should surface
instead of falling back to a fake implementation.
"""

from .app import GUIApp
from . import gui_api

__all__ = ["GUIApp", "gui_api"]
__version__ = "0.1"
