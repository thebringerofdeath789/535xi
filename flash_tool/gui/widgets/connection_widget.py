"""Connection controller and lazy Qt widget for the flash_tool GUI.

This module provides:
- ConnectionController: a testable, GUI-framework-agnostic controller
  for adapter discovery, connect/disconnect and connection state.
- create_qt_widget(controller, parent=None): attempts to build a Qt
  `QWidget` bound to the controller. Qt imports are performed lazily so
  unit tests can exercise the controller without requiring PySide6/PyQt.

Do NOT include or rely on any repository "mock ECU" implementation here.
Unit tests should mock `flash_tool.gui.gui_api` or pass a fake GUI API
implementation into the controller for isolation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
from types import SimpleNamespace
try:
    from flash_tool.gui.utils import (
        show_error_message,
        show_success_message,
        show_warning_message,
        show_info_message,
    )
except Exception:
    show_error_message = lambda *args, **kwargs: None
    show_success_message = lambda *args, **kwargs: None
    show_warning_message = lambda *args, **kwargs: None
    show_info_message = lambda *args, **kwargs: None
from flash_tool.operation_logger import log_operation


class ConnectionController:
    """Framework-agnostic controller for connection UI logic.

    Keeps the GUI interactions separated from Qt so unit tests can mock
    the adapter layer without importing GUI libraries.
    """

    def __init__(self, gui_api_module: Optional[Any] = None):
        # Allow injection for tests; default to real GUI API
        if gui_api_module is None:
            try:
                from flash_tool.gui import gui_api as _gui_api

                gui_api_module = _gui_api
            except Exception:
                gui_api_module = SimpleNamespace(
                    list_adapters=lambda: [],
                    connect=lambda *a, **k: None,
                    disconnect=lambda *a, **k: None,
                )

        self.gui_api = gui_api_module
        self.handle: Optional[Any] = None
        self.current_adapter: Optional[Dict[str, Any]] = None

    def list_adapters(self) -> List[Dict[str, Any]]:
        """Return a list of adapter descriptors from `gui_api.list_adapters()`.

        Each adapter is expected to be a dict-like object with at least
        keys `name` and `type` (or the calling UI can interpret a simple
        string).
        """
        try:
            adapters = self.gui_api.list_adapters()
            if adapters is None:
                return []
            return list(adapters)
        except Exception:
            return []

    def connect(self, adapter: Any, params: Optional[Dict[str, Any]] = None, progress_cb: Optional[Any] = None, cancel_token: Optional[Any] = None) -> Any:
        """Connect to the specified adapter.

        adapter may be a dict from `list_adapters()` or a simple port string.
        Returns the opaque connection handle from `gui_api.connect()`.
        """
        params = params or {}

        # Normalize adapter into ConnectionInfo fields
        iface = None
        chan = None
        if isinstance(adapter, dict):
            chan = adapter.get('name') or adapter.get('channel')
            iface = adapter.get('type') or adapter.get('interface')
        elif isinstance(adapter, str):
            chan = adapter

        # Fallbacks
        iface = iface or params.get('interface', 'pcan')
        chan = chan or params.get('channel') or params.get('port')

        # Build a ConnectionInfo dataclass if available
        conn_obj = None
        try:
            from flash_tool.gui.gui_api import ConnectionInfo

            conn_obj = ConnectionInfo(interface=iface, channel=chan, params=params)
        except Exception:
            # Fallback to simple namespace
            conn_obj = SimpleNamespace(interface=iface, channel=chan, params=params)

        # Call GUI API connect; some test fakes may not accept progress_cb/cancel_token
        try:
            handle = self.gui_api.connect(conn_obj, progress_cb=progress_cb, cancel_token=cancel_token)
        except TypeError:
            # Fallback for lightweight test doubles that accept only the ConnectionInfo
            handle = self.gui_api.connect(conn_obj)
        self.handle = handle
        self.current_adapter = {'interface': iface, 'channel': chan, 'params': params}
        return handle

    def disconnect(self) -> bool:
        """Disconnect the current handle via `gui_api.disconnect()`."""
        if not self.handle:
            return True
        try:
            self.gui_api.disconnect(self.handle)
        except Exception:
            # Best-effort disconnect
            try:
                if hasattr(self.handle, 'disconnect'):
                    self.handle.disconnect()
            except Exception:
                pass
        finally:
            self.handle = None
            self.current_adapter = None
        return True

    def is_connected(self) -> bool:
        return self.handle is not None

    def get_connection_info(self) -> Dict[str, Any]:
        """Get detailed connection info from ConnectionManager if available."""
        try:
            from flash_tool import connection_manager

            return connection_manager.get_manager().get_connection_info()
        except Exception:
            return {'connected': bool(self.handle), 'port': (self.current_adapter or {}).get('channel')}


def create_qt_widget(controller: ConnectionController, parent: Optional[Any] = None):
    """Create a Qt `QWidget` bound to the provided controller.

    This function lazily imports Qt bindings (PySide6 or PyQt5) so the
    module itself remains importable in headless unit tests.
    Returns a QWidget instance when Qt is available; otherwise raises ImportError.
    """
    # Try PySide6 first, then PyQt5
    QtWidgets = None
    QtCore = None
    try:
        from PySide6 import QtWidgets as _w, QtCore as _c
        QtWidgets, QtCore = _w, _c
    except Exception:
        try:
            from PyQt5 import QtWidgets as _w, QtCore as _c
            QtWidgets, QtCore = _w, _c
        except Exception as exc:
            raise ImportError("Neither PySide6 nor PyQt5 available for GUI widget") from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._controller = controller

            main_layout = QtWidgets.QVBoxLayout(self)
            hl = QtWidgets.QHBoxLayout()

            self.adapter_combo = QtWidgets.QComboBox()
            self.refresh_btn = QtWidgets.QPushButton("Refresh")
            self.connect_btn = QtWidgets.QPushButton("Connect")
            self.reconnect_btn = QtWidgets.QPushButton("Reconnect")
            self.status_btn = QtWidgets.QPushButton("Status")
            self.status_label = QtWidgets.QLabel("Not connected")

            hl.addWidget(self.adapter_combo)
            hl.addWidget(self.refresh_btn)
            hl.addWidget(self.connect_btn)
            hl.addWidget(self.reconnect_btn)
            hl.addWidget(self.status_btn)
            hl.addWidget(self.status_label)

            main_layout.addLayout(hl)

            self.status_info = QtWidgets.QPlainTextEdit()
            self.status_info.setReadOnly(True)
            self.status_info.setMaximumHeight(120)
            main_layout.addWidget(self.status_info)

            self.refresh_btn.clicked.connect(self._on_refresh)
            self.connect_btn.clicked.connect(self._on_connect_toggle)
            self.reconnect_btn.clicked.connect(self._on_reconnect)
            self.status_btn.clicked.connect(self._on_status)

            # initial populate
            self._on_refresh()

        def _on_refresh(self):
            self.adapter_combo.clear()
            adapters = self._controller.list_adapters()
            # Accept either a list of strings or dicts and prefer COM3
            preferred_index = -1
            for idx, a in enumerate(adapters):
                if isinstance(a, dict):
                    chan = a.get('name') or a.get('channel') or ''
                    iface = a.get('type') or a.get('interface') or ''
                    display = f"{iface}:{chan}" if iface or chan else str(a)
                else:
                    display = str(a)
                self.adapter_combo.addItem(display, a)
                if preferred_index < 0 and 'COM3' in display.upper():
                    preferred_index = idx

            # Default selection: COM3 if present, otherwise first entry
            if self.adapter_combo.count() > 0:
                if preferred_index >= 0:
                    self.adapter_combo.setCurrentIndex(preferred_index)
                else:
                    self.adapter_combo.setCurrentIndex(0)

        def _on_connect_toggle(self):
            if not self._controller.is_connected():
                idx = self.adapter_combo.currentIndex()
                if idx < 0:
                    self.status_label.setText("No adapter selected")
                    return
                adapter = self.adapter_combo.itemData(idx)
                # Use a background Worker so connection progress doesn't block UI
                try:
                    # UI progress callback accepts either ProgressEvent or (msg, pct)
                    def ui_progress(event_or_msg, percent=None):
                        def _update():
                            try:
                                if hasattr(event_or_msg, 'message'):
                                    msg = str(getattr(event_or_msg, 'message'))
                                    pct = getattr(event_or_msg, 'progress', '')
                                else:
                                    msg = str(event_or_msg)
                                    pct = percent if percent is not None else ''
                                self.status_label.setText(f"{msg} {pct}")
                            except Exception:
                                self.status_label.setText(str(event_or_msg))
                        QtCore.QTimer.singleShot(0, _update)

                    from flash_tool.gui.worker import Worker, CancelToken

                    cancel_token = CancelToken()
                    worker = Worker(task=self._controller.connect, args=(adapter,), progress_cb=ui_progress, cancel_token=cancel_token)
                    # Disable connect button while connecting
                    self.connect_btn.setEnabled(False)
                    worker.start()

                    def poll():
                        if worker.is_alive():
                            QtCore.QTimer.singleShot(200, poll)
                            return

                        try:
                            handle = worker.result()
                        except Exception as e:
                            self.status_label.setText(f'Connect exception: {e}')
                            show_error_message(self, 'Connection Error', str(e))
                            log_operation('Adapter Connect', 'failure', str(e))
                            self.connect_btn.setEnabled(True)
                            return

                        if handle:
                            self.connect_btn.setText("Disconnect")
                            self.status_label.setText("Connected")
                            log_operation('Adapter Connect', 'success', f"Connected to {self.adapter_combo.currentText()}")
                            # Auto-show status details
                            self._on_status()
                            show_success_message(self, 'Connected', f"Adapter connected: {self.adapter_combo.currentText()}")
                        else:
                            self.status_label.setText("Connect failed")
                            show_error_message(self, 'Connection Failed', 'Adapter did not return a valid handle.')
                            log_operation('Adapter Connect', 'failure', 'No handle returned')

                        self.connect_btn.setEnabled(True)

                    QtCore.QTimer.singleShot(200, poll)
                except Exception as e:
                    self.status_label.setText(f"Error: {e}")
            else:
                self.status_label.setText("Disconnecting...")
                self._controller.disconnect()
                self.connect_btn.setText("Connect")
                self.status_label.setText("Not connected")
                log_operation('Adapter Disconnect', 'success', f"Disconnected from {self.adapter_combo.currentText()}")

        def _on_reconnect(self):
            # Convenience: disconnect then connect to currently selected adapter
            try:
                if self._controller.is_connected():
                    self._controller.disconnect()
                self.connect_btn.setText("Connect")
                self.status_label.setText("Reconnecting...")
                self._on_connect_toggle()
            except Exception as e:
                show_error_message(self, 'Reconnect Error', str(e))
                log_operation('Adapter Reconnect', 'failure', str(e))

        def _on_status(self):
            try:
                info = self._controller.get_connection_info()
            except Exception as e:
                self.status_info.setPlainText(f"Error retrieving status: {e}")
                return

            try:
                txt = json.dumps(info, indent=2, default=str)
            except Exception:
                txt = str(info)

            self.status_info.setPlainText(txt)
            # Also reflect connection summary on the label
            if info.get('connected'):
                self.status_label.setText("Connected")
            else:
                self.status_label.setText("Not connected")

    return _Widget(parent)
