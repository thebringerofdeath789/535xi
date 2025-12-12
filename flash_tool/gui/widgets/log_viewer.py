"""Log viewer controller and lazy Qt widget.

Provides a small, testable log viewer that the GUI can embed as a
bottom panel. The controller stores recent log lines in-memory and the
Qt widget displays them. The widget exposes a `refresh()` method so
unit tests can update the view deterministically.
"""
from __future__ import annotations

"""Log viewer controller and lazy Qt widget.

Provides a small, testable log viewer that the GUI can embed as a
bottom panel. The controller stores recent log lines in-memory and the
Qt widget displays them. The widget exposes a `refresh()` method so
unit tests can update the view deterministically.
"""

from collections import deque
from datetime import datetime
from typing import Any, Deque, List, Optional


# Simple severity levels for logs
class LogLevel:
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40


class LogEntry:
    def __init__(self, level: int, message: str):
        self.level = level
        self.message = message
        self.ts = datetime.utcnow().isoformat() + 'Z'

    def __str__(self):
        return f"[{self.ts}] [{self.level}] {self.message}"


class LogViewerController:
    def __init__(self, max_lines: int = 1000, level: int = LogLevel.INFO):
        self._entries: Deque[LogEntry] = deque(maxlen=max_lines)
        self._level = level

    def clear(self) -> None:
        """Clear the in-memory log buffer."""
        try:
            self._entries.clear()
        except Exception:
            # best-effort
            self._entries = deque(maxlen=getattr(self._entries, 'maxlen', 1000))

    def set_level(self, level: int):
        self._level = level

    def append(self, msg: str, level: int = LogLevel.INFO) -> None:
        # Collapse newlines and sanitize
        sanitized = ' '.join(str(msg).splitlines()).strip()
        entry = LogEntry(level=level, message=sanitized)
        self._entries.append(entry)

    def get_messages(self) -> List[str]:
        return [str(e) for e in self._entries if e.level >= self._level]

    def get_entries(self) -> List[LogEntry]:
        return list(self._entries)


def create_qt_widget(controller: LogViewerController, parent: Optional[Any] = None):
    try:
        from PySide6 import QtWidgets, QtCore
    except Exception:
        try:
            from PyQt5 import QtWidgets, QtCore
        except Exception as exc:
            raise ImportError("Qt bindings not available for LogViewer") from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller

            layout = QtWidgets.QVBoxLayout(self)
            btn_h = QtWidgets.QHBoxLayout()
            self.refresh_btn = QtWidgets.QPushButton('Refresh')
            self.clear_btn = QtWidgets.QPushButton('Clear')
            self.level_combo = QtWidgets.QComboBox()
            self.level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
            self.jump_latest_btn = QtWidgets.QPushButton('Jump to Latest')
            btn_h.addWidget(self.refresh_btn)
            btn_h.addWidget(self.clear_btn)
            btn_h.addWidget(self.level_combo)
            btn_h.addWidget(self.jump_latest_btn)
            layout.addLayout(btn_h)

            # Search/filter row
            search_h = QtWidgets.QHBoxLayout()
            search_h.addWidget(QtWidgets.QLabel("Filter:"))
            self.search_edit = QtWidgets.QLineEdit()
            self.search_edit.setPlaceholderText("Search text (case-insensitive)...")
            search_h.addWidget(self.search_edit)
            layout.addLayout(search_h)

            self.view = QtWidgets.QPlainTextEdit()
            self.view.setReadOnly(True)
            layout.addWidget(self.view)

            self.refresh_btn.clicked.connect(self.refresh)
            self.clear_btn.clicked.connect(self._on_clear)
            self.level_combo.currentIndexChanged.connect(self._on_level_changed)
            self.jump_latest_btn.clicked.connect(self._on_jump_latest)
            self.search_edit.textChanged.connect(self.refresh)

            # initial populate
            self.refresh()

        def refresh(self):
            try:
                msgs = self._ctrl.get_messages()
                # Apply search filter if text entered
                search_text = getattr(self.search_edit, 'text', lambda: '')().lower()
                if search_text:
                    msgs = [m for m in msgs if search_text in m.lower()]
                self.view.setPlainText('\n'.join(msgs))
            except Exception as e:
                self.view.setPlainText(f'Error refreshing log viewer: {e}')

        def _on_jump_latest(self):
            """Scroll to the end of the log."""
            try:
                cursor = self.view.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.view.setTextCursor(cursor)
            except Exception:
                pass

        def _on_level_changed(self, idx: int):
            try:
                mapping = {0: LogLevel.DEBUG, 1: LogLevel.INFO, 2: LogLevel.WARNING, 3: LogLevel.ERROR}
                lvl = mapping.get(int(idx), LogLevel.INFO)
                self._ctrl.set_level(lvl)
                self.refresh()
            except Exception:
                pass

        def _on_clear(self):
            # Clearing controller buffer is a best-effort operation
            try:
                if hasattr(self._ctrl, 'clear'):
                    self._ctrl.clear()
                else:
                    # fallback to clearing underlying deque if present
                    try:
                        self._ctrl._entries.clear()
                    except Exception:
                        pass
            except Exception:
                pass
            self.refresh()

    return _Widget(parent)
