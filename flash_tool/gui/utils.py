"""GUI utility helpers for icons, theming, and standardized messaging.

This module is intentionally lightweight and avoids importing Qt at
module import time so that it remains safe to import in headless or
non-GUI environments. Qt classes are imported lazily inside helpers.
"""
from __future__ import annotations

import os
from typing import Optional
from datetime import datetime

# Base directory for the flash_tool package (one level above gui/)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
IMG_DIR = os.path.join(BASE_DIR, "img")
THEME_PATH = os.path.join(os.path.dirname(__file__), "theme.qss")


def load_icon(name: str):
    """Return a QIcon for an image in flash_tool/img.

    If Qt bindings are not available, this returns a dummy object so that
    non-GUI environments can still import this module.
    """
    path = os.path.join(IMG_DIR, name)

    try:
        from PySide6.QtGui import QIcon  # type: ignore
    except Exception:  # pragma: no cover - fallback for PyQt or headless
        try:
            from PyQt5.QtGui import QIcon  # type: ignore
        except Exception:
            class _DummyIcon:  # minimal stub used only in headless tests
                def __init__(self, *_: object, **__: object) -> None:
                    pass

            return _DummyIcon()

    return QIcon(path)


def load_stylesheet() -> str:
    """Load the neon theme stylesheet, rewriting icon paths to absolute.

    The QSS file uses paths like ``img/CheckboxOff.png``; at runtime we
    rewrite these to the absolute flash_tool/img directory so Qt can
    resolve them regardless of the current working directory.
    """
    if not os.path.isfile(THEME_PATH):
        return ""

    try:
        with open(THEME_PATH, "r", encoding="utf-8") as f:
            qss = f.read()
    except Exception:
        return ""

    img_path = IMG_DIR.replace("\\", "/")
    # Replace url("img/...") with an absolute path
    qss = qss.replace('url("img/', f'url("{img_path}/')
    return qss


__all__ = ["load_icon", "load_stylesheet", "BASE_DIR", "IMG_DIR", 
           "show_error_message", "show_success_message", "show_warning_message",
           "show_info_message", "format_timestamp"]


def show_error_message(parent, title: str, message: str, details: Optional[str] = None) -> None:
    """Show standardized error message with QMessageBox.
    
    Args:
        parent: Qt parent widget
        title: Dialog title
        message: Main message text
        details: Optional detailed error text
    """
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PyQt5 import QtWidgets
        except ImportError:
            print(f"ERROR [{title}]: {message}")
            if details:
                print(f"  Details: {details}")
            return
    
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    box.exec()


def show_success_message(parent, title: str, message: str, vin: str = None, 
                        ecu_type: str = None, include_timestamp: bool = True) -> None:
    """Show standardized success message with optional VIN, ECU type, timestamp.
    
    Args:
        parent: Qt parent widget
        title: Dialog title
        message: Main message text
        vin: Optional VIN to display
        ecu_type: Optional ECU type to display
        include_timestamp: Whether to add timestamp to message
    """
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PyQt5 import QtWidgets
        except ImportError:
            print(f"SUCCESS [{title}]: {message}")
            return
    
    details_parts = []
    if vin:
        details_parts.append(f"VIN: {vin}")
    if ecu_type:
        details_parts.append(f"ECU Type: {ecu_type}")
    if include_timestamp:
        details_parts.append(f"Timestamp: {format_timestamp()}")
    
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(message)
    if details_parts:
        box.setDetailedText("\n".join(details_parts))
    box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    box.exec()


def show_warning_message(parent, title: str, message: str, details: Optional[str] = None) -> None:
    """Show standardized warning message with QMessageBox.
    
    Args:
        parent: Qt parent widget
        title: Dialog title
        message: Main message text
        details: Optional detailed warning text
    """
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PyQt5 import QtWidgets
        except ImportError:
            print(f"WARNING [{title}]: {message}")
            if details:
                print(f"  Details: {details}")
            return
    
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    box.exec()


def show_info_message(parent, title: str, message: str, details: Optional[str] = None) -> None:
    """Show standardized info message with QMessageBox.
    
    Args:
        parent: Qt parent widget
        title: Dialog title
        message: Main message text
        details: Optional detailed info text
    """
    try:
        from PySide6 import QtWidgets
    except ImportError:
        try:
            from PyQt5 import QtWidgets
        except ImportError:
            print(f"INFO [{title}]: {message}")
            if details:
                print(f"  Details: {details}")
            return
    
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    box.exec()


def format_timestamp() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now().isoformat(timespec='seconds')
