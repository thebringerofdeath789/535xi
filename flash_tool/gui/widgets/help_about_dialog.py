"""Help/About Dialog widget for GUI.

Provides user guidance, documentation links, and version information. Accessible from the main menu or toolbar.
"""
from __future__ import annotations

from typing import Any, Optional
import platform

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore
    except Exception as exc:
        raise ImportError('Qt bindings not available for Help/About Dialog') from exc

class HelpAboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[Any] = None):
        super().__init__(parent)
        self.setWindowTitle('Help / About')
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        about_text = (
            '<b>BMW N54 Flash Tool GUI</b><br>'
            'Version: 2025.11.29<br>'
            'Platform: {}<br>'
            'Python: {}<br>'
            '<br>'
            'Project home: <a href="http://github.com/thebringerofdeath789/FreeN54Flasher">GitHub</a><br>'
            '<br>'
            'Contact: gking707@yahoo.com'
        ).format(platform.system(), platform.python_version())

        self.label = QtWidgets.QLabel(about_text)
        self.label.setOpenExternalLinks(True)
        layout.addWidget(self.label)

        self.close_btn = QtWidgets.QPushButton('Close')
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)

def create_qt_widget(parent: Optional[Any] = None):
    return HelpAboutDialog(parent)
