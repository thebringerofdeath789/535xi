Connection Widgets
==================

This folder contains small, self-contained UI widgets used by the GUI.

ConnectionWidget
----------------
- File: `connection_widget.py`
- Provides: `ConnectionController` (framework-agnostic) and `create_qt_widget(controller, parent=None)` (lazy-Qt widget factory).
- Purpose: adapter discovery, connect/disconnect, and a diagnostic status dump area.

Testing & Safety
----------------
- The `ConnectionController` is intentionally framework-agnostic so unit tests can inject a fake `gui_api` or a small fake controller implementation. Tests should not rely on or ship a repository-provided mock ECU. Instead, mock the adapter/bus interface or inject fakes.

Embedding
---------
Import and create the widget like so (Qt must be available at runtime):

```python
from flash_tool.gui.widgets.connection_widget import ConnectionController, create_qt_widget

ctrl = ConnectionController()  # optional injection for tests
widget = create_qt_widget(ctrl)
# add `widget` to your main window layout
```

The widget delegates actual connect/disconnect to `flash_tool.gui.gui_api` via the controller.
