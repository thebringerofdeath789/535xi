"""Bin Compare Widget for GUI.

Side-by-side binary file comparison tool for analyzing tune differences.
Highlights changed regions, shows map differences, and provides hex view.

Enhancements:
- Streaming diff for large files with progress + cancellation
- "Show first N differences" limit control
- CSV export of diff regions
- Integration with bin_analyzer for region categorization
- Basic SW ID and ECU type detection
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import hashlib
import os
import re

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
        from PyQt5.QtCore import pyqtSignal as Signal
    except Exception as exc:
        raise ImportError('Qt bindings not available for Bin Compare Widget') from exc

# Lazy imports for shared GUI utilities and worker
try:
    from flash_tool.gui.utils import (
        show_error_message,
        show_success_message,
        show_warning_message,
        show_info_message,
        format_timestamp,
    )
except Exception:
    # Headless fallback; functions will not be used in non-GUI contexts here
    show_error_message = lambda *args, **kwargs: None
    show_success_message = lambda *args, **kwargs: None
    show_warning_message = lambda *args, **kwargs: None
    show_info_message = lambda *args, **kwargs: None
    format_timestamp = lambda: ""

try:
    from flash_tool.gui.worker import Worker, CancelToken, ProgressEvent
except Exception:
    Worker = None  # type: ignore
    CancelToken = None  # type: ignore
    ProgressEvent = None  # type: ignore

try:
    from flash_tool.operation_logger import log_operation
except Exception:
    def log_operation(operation: str, status: str, details: Optional[str] = None) -> bool:  # type: ignore
        return True


class DiffRegion:
    """Represents a region of difference between two files."""
    def __init__(self, offset: int, size: int, data_a: bytes, data_b: bytes):
        self.offset = offset
        self.size = size
        self.data_a = data_a
        self.data_b = data_b
    
    def __repr__(self):
        return f"DiffRegion(0x{self.offset:06X}, {self.size} bytes)"


class BinCompareController:
    """Controller for binary comparison operations."""
    
    def __init__(self, log_controller: Optional[Any] = None):
        self.log_controller = log_controller
        self.file_a: Optional[Path] = None
        self.file_b: Optional[Path] = None
        self.data_a: Optional[bytes] = None
        self.data_b: Optional[bytes] = None
        self.differences: List[DiffRegion] = []
        self.diff_regions_total: int = 0
        self.diff_bytes_total: int = 0
        self.meta_a: Dict[str, Any] = {}
        self.meta_b: Dict[str, Any] = {}

    def _log(self, message: str, status: str = "info") -> None:
        try:
            log_operation("Bin Compare", status, message)
        except Exception:
            pass

    def _stream_hash(self, path: Path, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()[:16]

    def _extract_sw_id(self, path: Path, chunk_size: int = 1024 * 1024) -> Optional[str]:
        pattern = re.compile(rb'[A-Z][A-Z0-9]{3}S')
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                m = pattern.search(chunk)
                if m:
                    try:
                        return m.group().decode('ascii')
                    except Exception:
                        return None
        return None

    def _ecu_type_from_sw(self, sw_id: Optional[str]) -> str:
        if not sw_id:
            return "Unknown"
        # Basic mapping for N54
        if sw_id.startswith('I8') or sw_id.startswith('IJ'):
            return "MSD81"
        return "Unknown"
    
    def load_files(self, path_a: str, path_b: str) -> Tuple[bool, str]:
        """Load two files for comparison and compute basic metadata."""
        try:
            self.file_a = Path(path_a)
            self.file_b = Path(path_b)
            
            if not self.file_a.exists():
                return False, f"File A not found: {path_a}"
            if not self.file_b.exists():
                return False, f"File B not found: {path_b}"
            
            # Compute lightweight metadata without loading entire files
            size_a = self.file_a.stat().st_size
            size_b = self.file_b.stat().st_size
            self.meta_a = {
                'size': size_a,
                'hash': self._stream_hash(self.file_a),
                'sw_id': self._extract_sw_id(self.file_a),
            }
            self.meta_a['ecu_type'] = self._ecu_type_from_sw(self.meta_a.get('sw_id'))
            self.meta_b = {
                'size': size_b,
                'hash': self._stream_hash(self.file_b),
                'sw_id': self._extract_sw_id(self.file_b),
            }
            self.meta_b['ecu_type'] = self._ecu_type_from_sw(self.meta_b.get('sw_id'))

            self._log(f"Loaded files: A={size_a} bytes, B={size_b} bytes", status="info")
            return True, f"Loaded: {size_a} bytes vs {size_b} bytes"
        except Exception as e:
            self._log(f"Load error: {e}", status="error")
            return False, str(e)
    
    def compare(self, chunk_size: int = 16) -> Dict[str, Any]:
        """Compare the two loaded files."""
        if self.data_a is None or self.data_b is None:
            return {'error': 'Files not loaded'}
        
        self.differences = []
        
        # Basic stats
        size_a = len(self.data_a)
        size_b = len(self.data_b)
        min_size = min(size_a, size_b)
        max_size = max(size_a, size_b)
        
        # Find differences
        diff_start = None
        diff_bytes_a = bytearray()
        diff_bytes_b = bytearray()
        
        for i in range(min_size):
            if self.data_a[i] != self.data_b[i]:
                if diff_start is None:
                    diff_start = i
                diff_bytes_a.append(self.data_a[i])
                diff_bytes_b.append(self.data_b[i])
            else:
                if diff_start is not None:
                    # End of a diff region
                    self.differences.append(DiffRegion(
                        diff_start, len(diff_bytes_a),
                        bytes(diff_bytes_a), bytes(diff_bytes_b)
                    ))
                    diff_start = None
                    diff_bytes_a = bytearray()
                    diff_bytes_b = bytearray()
        
        # Handle trailing diff
        if diff_start is not None:
            self.differences.append(DiffRegion(
                diff_start, len(diff_bytes_a),
                bytes(diff_bytes_a), bytes(diff_bytes_b)
            ))
        
        # Size difference
        if size_a != size_b:
            if size_a > size_b:
                self.differences.append(DiffRegion(
                    size_b, size_a - size_b,
                    self.data_a[size_b:], b''
                ))
            else:
                self.differences.append(DiffRegion(
                    size_a, size_b - size_a,
                    b'', self.data_b[size_a:]
                ))
        
        # Calculate stats
        total_diff_bytes = sum(d.size for d in self.differences)
        
        return {
            'size_a': size_a,
            'size_b': size_b,
            'identical': len(self.differences) == 0,
            'diff_regions': len(self.differences),
            'diff_bytes': total_diff_bytes,
            'diff_percent': (total_diff_bytes / max_size * 100) if max_size > 0 else 0,
            'hash_a': hashlib.sha256(self.data_a).hexdigest()[:16],
            'hash_b': hashlib.sha256(self.data_b).hexdigest()[:16],
        }

    def compare_streaming(self, max_regions: int = 200, progress_cb: Optional[Any] = None, cancel_token: Optional[Any] = None, chunk_size: int = 1024 * 1024) -> Dict[str, Any]:
        """Streaming diff implementation for large files.

        Reads both files chunk-by-chunk to minimize memory footprint. Records
        at most `max_regions` detailed DiffRegion objects but continues scanning
        to compute accurate totals.
        """
        if not self.file_a or not self.file_b:
            return {'error': 'Files not loaded'}

        self.differences = []
        self.diff_regions_total = 0
        self.diff_bytes_total = 0

        size_a = self.meta_a.get('size') or self.file_a.stat().st_size
        size_b = self.meta_b.get('size') or self.file_b.stat().st_size
        min_size = min(size_a, size_b)
        max_size = max(size_a, size_b)

        diff_start: Optional[int] = None
        diff_bytes_a = bytearray()
        diff_bytes_b = bytearray()

        processed = 0
        with open(self.file_a, 'rb') as fa, open(self.file_b, 'rb') as fb:
            while processed < min_size:
                if cancel_token and cancel_token.is_cancelled():
                    self._log("Comparison cancelled by user", status="warning")
                    break
                to_read = min(chunk_size, min_size - processed)
                chunk_a = fa.read(to_read)
                chunk_b = fb.read(to_read)
                # Iterate bytes within chunk
                for i in range(to_read):
                    absolute_i = processed + i
                    a = chunk_a[i]
                    b = chunk_b[i]
                    if a != b:
                        if diff_start is None:
                            diff_start = absolute_i
                        diff_bytes_a.append(a)
                        diff_bytes_b.append(b)
                    else:
                        if diff_start is not None:
                            # finalize current diff region
                            self.diff_regions_total += 1
                            self.diff_bytes_total += len(diff_bytes_a)
                            if len(self.differences) < max_regions:
                                self.differences.append(DiffRegion(diff_start, len(diff_bytes_a), bytes(diff_bytes_a), bytes(diff_bytes_b)))
                            diff_start = None
                            diff_bytes_a = bytearray()
                            diff_bytes_b = bytearray()
                processed += to_read
                if progress_cb:
                    try:
                        pct = (processed / min_size * 100.0) if min_size else 100.0
                        progress_cb("Comparing bins...", pct)
                    except Exception:
                        pass

        # trailing diff region
        if diff_start is not None:
            self.diff_regions_total += 1
            self.diff_bytes_total += len(diff_bytes_a)
            if len(self.differences) < max_regions:
                self.differences.append(DiffRegion(diff_start, len(diff_bytes_a), bytes(diff_bytes_a), bytes(diff_bytes_b)))

        # handle size difference
        if size_a != size_b:
            if size_a > size_b:
                extra = size_a - size_b
                self.diff_regions_total += 1
                self.diff_bytes_total += extra
                if len(self.differences) < max_regions:
                    with open(self.file_a, 'rb') as fa:
                        fa.seek(size_b)
                        tail = fa.read()
                    self.differences.append(DiffRegion(size_b, extra, tail, b''))
            else:
                extra = size_b - size_a
                self.diff_regions_total += 1
                self.diff_bytes_total += extra
                if len(self.differences) < max_regions:
                    with open(self.file_b, 'rb') as fb:
                        fb.seek(size_a)
                        tail = fb.read()
                    self.differences.append(DiffRegion(size_a, extra, b'', tail))

        result = {
            'size_a': size_a,
            'size_b': size_b,
            'identical': (self.diff_regions_total == 0),
            'diff_regions': self.diff_regions_total,
            'diff_bytes': self.diff_bytes_total,
            'diff_percent': (self.diff_bytes_total / max_size * 100) if max_size > 0 else 0,
            'hash_a': self.meta_a.get('hash'),
            'hash_b': self.meta_b.get('hash'),
            'sw_id_a': self.meta_a.get('sw_id'),
            'sw_id_b': self.meta_b.get('sw_id'),
            'ecu_type_a': self.meta_a.get('ecu_type'),
            'ecu_type_b': self.meta_b.get('ecu_type'),
            'regions_displayed': len(self.differences),
        }
        self._log(f"Compare done: {self.diff_regions_total} regions, {self.diff_bytes_total} bytes diff")
        return result
    
    def get_hex_view(self, offset: int, size: int = 256) -> Tuple[str, str]:
        """Get hex view of both files at given offset."""
        if self.data_a is None or self.data_b is None:
            return "", ""
        
        def format_hex(data: bytes, start: int, length: int) -> str:
            lines = []
            for i in range(0, length, 16):
                addr = start + i
                chunk = data[start + i:start + i + 16] if start + i < len(data) else b''
                hex_part = ' '.join(f'{b:02X}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                lines.append(f"{addr:06X}: {hex_part:<48} {ascii_part}")
            return '\n'.join(lines)
        
        hex_a = format_hex(self.data_a, offset, size)
        hex_b = format_hex(self.data_b, offset, size)
        
        return hex_a, hex_b


class BinCompareWidget(QtWidgets.QWidget):
    """Binary file comparison widget."""
    
    def __init__(self, controller: BinCompareController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._worker: Optional[Worker] = None
        self._cancel: Optional[CancelToken] = None
        self._setup_ui()
        self._add_tooltips()
        self._add_help_button()

    def _add_tooltips(self):
        self.file_a_edit.setToolTip("Select the original (stock) binary file for comparison.")
        self.browse_a_btn.setToolTip("Browse for the original/stock .bin file.")
        self.file_b_edit.setToolTip("Select the modified/tuned binary file for comparison.")
        self.browse_b_btn.setToolTip("Browse for the modified/tuned .bin file.")
        self.compare_btn.setToolTip("Start the binary comparison process.")
        self.diff_limit_spin.setToolTip("Limit the number of difference regions displayed in the table.")
        self.size_a_label.setToolTip("Size of File A in bytes.")
        self.size_b_label.setToolTip("Size of File B in bytes.")
        self.diff_count_label.setToolTip("Number of difference regions detected.")
        self.diff_bytes_label.setToolTip("Total number of bytes that differ between files.")
        self.hash_a_label.setToolTip("SHA-256 hash of File A (first 16 chars).")
        self.hash_b_label.setToolTip("SHA-256 hash of File B (first 16 chars).")
        self.sw_a_label.setToolTip("Detected software ID in File A.")
        self.sw_b_label.setToolTip("Detected software ID in File B.")
        self.ecu_a_label.setToolTip("Detected ECU type for File A.")
        self.ecu_b_label.setToolTip("Detected ECU type for File B.")
        self.status_label.setToolTip("Comparison status and summary.")
        self.diff_table.setToolTip("Table of all detected difference regions between the two files.")
        self.progress_bar.setToolTip("Shows progress of the comparison operation.")
        self.cancel_btn.setToolTip("Cancel the current comparison operation.")
        self.hex_offset_edit.setToolTip("Enter a hex or decimal offset to view in the hex viewer.")
        self.hex_go_btn.setToolTip("Jump to the specified offset in the hex view.")
        self.export_btn.setToolTip("Export the difference report to a CSV or text file.")
        self.hex_a_text.setToolTip("Hex view of File A at the selected offset.")
        self.hex_b_text.setToolTip("Hex view of File B at the selected offset.")

    def _add_help_button(self):
        # Add a help button to the top right of the widget
        help_btn = QtWidgets.QPushButton("Help")
        help_btn.setToolTip("Show help and usage instructions for the Bin Compare tool.")
        help_btn.setFixedWidth(60)
        help_btn.clicked.connect(self._show_help_dialog)
        # Insert help button into the main layout (top right)
        layout = self.layout()
        if layout is not None:
            hlayout = QtWidgets.QHBoxLayout()
            hlayout.addStretch()
            hlayout.addWidget(help_btn)
            layout.insertLayout(0, hlayout)

    def _show_help_dialog(self):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Bin Compare Help")
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(
            "<b>Binary File Comparison Tool Help</b><br><br>"
            "<b>Purpose:</b> Compare two binary files (stock vs tuned) and highlight all differences.\n"
            "<ul>"
            "<li><b>File A:</b> Select the original/stock .bin file.</li>"
            "<li><b>File B:</b> Select the modified/tuned .bin file.</li>"
            "<li><b>Compare Files:</b> Starts the comparison. Progress and results are shown below.</li>"
            "<li><b>Show first N differences:</b> Limits the number of regions displayed in the table for large files.</li>"
            "<li><b>Difference Regions Table:</b> Shows offset, size, hex preview, map name, and category for each region.</li>"
            "<li><b>Hex View:</b> Double-click a region or enter an offset to view raw bytes in both files.</li>"
            "<li><b>Export Diff Report:</b> Save the difference report as CSV or text.</li>"
            "<li><b>Cancel:</b> Stops a long-running comparison.</li>"
            "</ul>"
            "<b>Tips:</b> Hover over any control for more info. Use the help button for guidance at any time."
        )
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("Binary File Comparison Tool")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # File selection
        files_group = QtWidgets.QGroupBox("Files to Compare")
        files_layout = QtWidgets.QGridLayout(files_group)
        
        files_layout.addWidget(QtWidgets.QLabel("File A (Original/Stock):"), 0, 0)
        self.file_a_edit = QtWidgets.QLineEdit()
        self.file_a_edit.setPlaceholderText("Select original .bin file...")
        files_layout.addWidget(self.file_a_edit, 0, 1)
        self.browse_a_btn = QtWidgets.QPushButton("Browse...")
        self.browse_a_btn.clicked.connect(lambda: self._browse_file('a'))
        files_layout.addWidget(self.browse_a_btn, 0, 2)
        
        files_layout.addWidget(QtWidgets.QLabel("File B (Modified/Tuned):"), 1, 0)
        self.file_b_edit = QtWidgets.QLineEdit()
        self.file_b_edit.setPlaceholderText("Select modified .bin file...")
        files_layout.addWidget(self.file_b_edit, 1, 1)
        self.browse_b_btn = QtWidgets.QPushButton("Browse...")
        self.browse_b_btn.clicked.connect(lambda: self._browse_file('b'))
        files_layout.addWidget(self.browse_b_btn, 1, 2)
        
        self.compare_btn = QtWidgets.QPushButton("Compare Files")
        self.compare_btn.clicked.connect(self._on_compare)
        self.compare_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        # Limit control for displayed differences
        self.diff_limit_spin = QtWidgets.QSpinBox()
        self.diff_limit_spin.setRange(10, 50000)
        self.diff_limit_spin.setValue(200)
        self.diff_limit_spin.setToolTip("Show at most N difference regions in the table")
        files_layout.addWidget(QtWidgets.QLabel("Show first N differences:"), 2, 0)
        files_layout.addWidget(self.diff_limit_spin, 2, 1)
        self.compare_btn = QtWidgets.QPushButton("Compare Files")
        self.compare_btn.clicked.connect(self._on_compare)
        self.compare_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        files_layout.addWidget(self.compare_btn, 2, 2)
        
        layout.addWidget(files_group)
        
        # Results summary
        self.summary_group = QtWidgets.QGroupBox("Comparison Summary")
        summary_layout = QtWidgets.QFormLayout(self.summary_group)
        
        self.size_a_label = QtWidgets.QLabel("-")
        self.size_b_label = QtWidgets.QLabel("-")
        self.diff_count_label = QtWidgets.QLabel("-")
        self.diff_bytes_label = QtWidgets.QLabel("-")
        self.hash_a_label = QtWidgets.QLabel("-")
        self.hash_b_label = QtWidgets.QLabel("-")
        self.sw_a_label = QtWidgets.QLabel("-")
        self.sw_b_label = QtWidgets.QLabel("-")
        self.ecu_a_label = QtWidgets.QLabel("-")
        self.ecu_b_label = QtWidgets.QLabel("-")
        self.status_label = QtWidgets.QLabel("-")
        
        summary_layout.addRow("File A Size:", self.size_a_label)
        summary_layout.addRow("File B Size:", self.size_b_label)
        summary_layout.addRow("Diff Regions:", self.diff_count_label)
        summary_layout.addRow("Total Diff Bytes:", self.diff_bytes_label)
        summary_layout.addRow("File A Hash:", self.hash_a_label)
        summary_layout.addRow("File B Hash:", self.hash_b_label)
        summary_layout.addRow("SW ID A:", self.sw_a_label)
        summary_layout.addRow("SW ID B:", self.sw_b_label)
        summary_layout.addRow("ECU Type A:", self.ecu_a_label)
        summary_layout.addRow("ECU Type B:", self.ecu_b_label)
        summary_layout.addRow("Status:", self.status_label)
        
        self.summary_group.setVisible(False)
        layout.addWidget(self.summary_group)
        
        # Differences table
        self.diff_group = QtWidgets.QGroupBox("Difference Regions")
        diff_layout = QtWidgets.QVBoxLayout(self.diff_group)
        
        self.diff_table = QtWidgets.QTableWidget()
        self.diff_table.setColumnCount(6)
        self.diff_table.setHorizontalHeaderLabels(['Offset', 'Size', 'File A (hex)', 'File B (hex)', 'Possible Map', 'Category'])
        self.diff_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.diff_table.doubleClicked.connect(self._on_diff_double_click)
        diff_layout.addWidget(self.diff_table)

        # Progress + cancel for long comparisons
        prog_layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        prog_layout.addWidget(self.progress_bar)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        prog_layout.addWidget(self.cancel_btn)
        diff_layout.addLayout(prog_layout)
        
        self.diff_group.setVisible(False)
        layout.addWidget(self.diff_group)
        
        # Hex view
        self.hex_group = QtWidgets.QGroupBox("Hex View")
        hex_layout = QtWidgets.QVBoxLayout(self.hex_group)
        
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.addWidget(QtWidgets.QLabel("Offset:"))
        self.hex_offset_edit = QtWidgets.QLineEdit("0x000000")
        self.hex_offset_edit.setMaximumWidth(100)
        nav_layout.addWidget(self.hex_offset_edit)
        
        self.hex_go_btn = QtWidgets.QPushButton("Go")
        self.hex_go_btn.clicked.connect(self._on_hex_go)
        nav_layout.addWidget(self.hex_go_btn)
        nav_layout.addStretch()
        
        self.export_btn = QtWidgets.QPushButton("Export Diff Report")
        self.export_btn.clicked.connect(self._on_export)
        nav_layout.addWidget(self.export_btn)
        
        hex_layout.addLayout(nav_layout)
        
        hex_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        self.hex_a_text = QtWidgets.QPlainTextEdit()
        self.hex_a_text.setReadOnly(True)
        self.hex_a_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.hex_a_text.setPlaceholderText("File A hex view")
        
        self.hex_b_text = QtWidgets.QPlainTextEdit()
        self.hex_b_text.setReadOnly(True)
        self.hex_b_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.hex_b_text.setPlaceholderText("File B hex view")
        
        hex_split.addWidget(self.hex_a_text)
        hex_split.addWidget(self.hex_b_text)
        hex_layout.addWidget(hex_split)
        
        self.hex_group.setVisible(False)
        layout.addWidget(self.hex_group)
    
    def _browse_file(self, which: str):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Select File {'A' if which == 'a' else 'B'}",
            "", "Binary Files (*.bin);;All Files (*)"
        )
        if filename:
            if which == 'a':
                self.file_a_edit.setText(filename)
            else:
                self.file_b_edit.setText(filename)
    
    def _on_compare(self):
        path_a = self.file_a_edit.text().strip()
        path_b = self.file_b_edit.text().strip()
        
        if not path_a or not path_b:
            show_warning_message(self, "Missing Files", "Please select both files to compare.")
            return
        
        success, msg = self.controller.load_files(path_a, path_b)
        if not success:
            show_error_message(self, "Load Error", msg)
            return
        # Run streaming compare in background
        limit = int(self.diff_limit_spin.value())
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)

        def _on_progress(evt: ProgressEvent):
            try:
                self.progress_bar.setValue(int(evt.progress))
                self.status_label.setText(evt.message)
                self.status_label.setStyleSheet("color: #0f9;")
            except Exception:
                pass

        self._cancel = CancelToken()

        def _on_done():
            try:
                results = self._worker.result()
            except Exception as exc:
                show_error_message(self, "Compare Error", str(exc))
                self.cancel_btn.setEnabled(False)
                return

            if 'error' in results:
                show_error_message(self, "Compare Error", results['error'])
                self.cancel_btn.setEnabled(False)
                return

            # Update summary
            self.size_a_label.setText(f"{results['size_a']:,} bytes")
            self.size_b_label.setText(f"{results['size_b']:,} bytes")
            self.diff_count_label.setText(str(results['diff_regions']))
            self.diff_bytes_label.setText(f"{results['diff_bytes']:,} bytes ({results['diff_percent']:.2f}%)")
            self.hash_a_label.setText(results.get('hash_a') or '-')
            self.hash_b_label.setText(results.get('hash_b') or '-')
            self.sw_a_label.setText(results.get('sw_id_a') or '-')
            self.sw_b_label.setText(results.get('sw_id_b') or '-')
            self.ecu_a_label.setText(results.get('ecu_type_a') or '-')
            self.ecu_b_label.setText(results.get('ecu_type_b') or '-')

            if results['identical']:
                self.status_label.setText("Files are identical")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.status_label.setText(f"{results['regions_displayed']} / {results['diff_regions']} differences shown")
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")

            self.summary_group.setVisible(True)

            # Populate differences table
            self._populate_diff_table()
            self.diff_group.setVisible(True)
            self.hex_group.setVisible(True)

            # Show first difference in hex view
            if self.controller.differences:
                first_diff = self.controller.differences[0]
                self.hex_offset_edit.setText(f"0x{first_diff.offset:06X}")
                self._on_hex_go()

            self.cancel_btn.setEnabled(False)
            show_success_message(self, "Comparison Complete", "Binary compare finished.")

        self._worker = Worker(
            self.controller.compare_streaming,
            args=(),
            kwargs={"max_regions": limit},
            progress_cb=_on_progress,
            cancel_token=self._cancel,
        )
        self._worker.start()

        # Poll worker completion via single-shot timer
        QtCore.QTimer.singleShot(100, self._check_worker_done)

    def _check_worker_done(self):
        if not self._worker:
            return
        if not self._worker.is_alive():
            # done
            self._worker.join(timeout=0)
            self._on_compare_done()
        else:
            QtCore.QTimer.singleShot(100, self._check_worker_done)

    def _on_compare_done(self):
        # Called when background worker finishes
        # Delegate to closure created in _on_compare
        # Reconstruct done handler by reading result and updating UI
        # (This mirrors _on_done logic but here due to timer-based completion)
        try:
            results = self._worker.result()
        except Exception as exc:
            show_error_message(self, "Compare Error", str(exc))
            self.cancel_btn.setEnabled(False)
            return

        if 'error' in results:
            show_error_message(self, "Compare Error", results['error'])
            self.cancel_btn.setEnabled(False)
            return

        self.size_a_label.setText(f"{results['size_a']:,} bytes")
        self.size_b_label.setText(f"{results['size_b']:,} bytes")
        self.diff_count_label.setText(str(results['diff_regions']))
        self.diff_bytes_label.setText(f"{results['diff_bytes']:,} bytes ({results['diff_percent']:.2f}%)")
        self.hash_a_label.setText(results.get('hash_a') or '-')
        self.hash_b_label.setText(results.get('hash_b') or '-')
        self.sw_a_label.setText(results.get('sw_id_a') or '-')
        self.sw_b_label.setText(results.get('sw_id_b') or '-')
        self.ecu_a_label.setText(results.get('ecu_type_a') or '-')
        self.ecu_b_label.setText(results.get('ecu_type_b') or '-')

        if results['identical']:
            self.status_label.setText("Files are identical")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setText(f"{results['regions_displayed']} / {results['diff_regions']} differences shown")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")

        self.summary_group.setVisible(True)
        self._populate_diff_table()
        self.diff_group.setVisible(True)
        self.hex_group.setVisible(True)
        if self.controller.differences:
            first_diff = self.controller.differences[0]
            self.hex_offset_edit.setText(f"0x{first_diff.offset:06X}")
            self._on_hex_go()
        self.cancel_btn.setEnabled(False)

    def _on_cancel(self):
        if self._cancel:
            self._cancel.request_cancel()
            self.status_label.setText("Cancelling...")
            self.status_label.setStyleSheet("color: #ff6;")
    
    def _populate_diff_table(self):
        diffs = self.controller.differences
        self.diff_table.setRowCount(len(diffs))
        
        # Try to identify known map offsets
        known_maps = self._get_known_maps()
        
        # Optional categorization via bin_analyzer
        try:
            from flash_tool.bin_analyzer import BinAnalyzer
            analyzer = BinAnalyzer(self.controller.file_b or self.controller.file_a)  # prefer modified file
        except Exception:
            analyzer = None
        
        for i, diff in enumerate(diffs):
            self.diff_table.setItem(i, 0, QtWidgets.QTableWidgetItem(f"0x{diff.offset:06X}"))
            self.diff_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{diff.size} bytes"))
            
            # Show first few bytes
            hex_a = ' '.join(f'{b:02X}' for b in diff.data_a[:8])
            hex_b = ' '.join(f'{b:02X}' for b in diff.data_b[:8])
            if diff.size > 8:
                hex_a += ' ...'
                hex_b += ' ...'
            
            self.diff_table.setItem(i, 2, QtWidgets.QTableWidgetItem(hex_a))
            self.diff_table.setItem(i, 3, QtWidgets.QTableWidgetItem(hex_b))
            
            # Check for known map
            map_name = self._identify_map(diff.offset, diff.size, known_maps)
            self.diff_table.setItem(i, 4, QtWidgets.QTableWidgetItem(map_name or "-"))

            # Category via analyzer
            category = "-"
            if analyzer is not None:
                # Build minimal region dict expected by analyzer
                changes = [(diff.offset + j, diff.data_a[j] if j < len(diff.data_a) else 0, diff.data_b[j] if j < len(diff.data_b) else 0) for j in range(min(diff.size, 32))]
                region = {'start': diff.offset, 'size': diff.size, 'changes': changes}
                try:
                    category = analyzer.categorize_region(region)
                except Exception:
                    category = "-"
            self.diff_table.setItem(i, 5, QtWidgets.QTableWidgetItem(category))
        
        self.diff_table.resizeColumnsToContents()
    
    def _get_known_maps(self) -> Dict[int, str]:
        """Get known map offsets from validated_maps."""
        try:
            from flash_tool.validated_maps import get_all_safe_maps
            maps = {}
            for m in get_all_safe_maps():
                maps[m.offset] = m.name
            return maps
        except Exception:
            return {}
    
    def _identify_map(self, offset: int, size: int, known_maps: Dict[int, str]) -> Optional[str]:
        """Try to identify which map a difference belongs to."""
        for map_offset, name in known_maps.items():
            # Check if offset is within this map's range (with some tolerance)
            if map_offset <= offset <= map_offset + 1000:
                return f"{name} (+{offset - map_offset})"
        return None
    
    def _on_diff_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self.controller.differences):
            diff = self.controller.differences[row]
            self.hex_offset_edit.setText(f"0x{diff.offset:06X}")
            self._on_hex_go()
    
    def _on_hex_go(self):
        offset_text = self.hex_offset_edit.text().strip()
        try:
            if offset_text.startswith('0x'):
                offset = int(offset_text, 16)
            else:
                offset = int(offset_text)
        except ValueError:
            return
        
        hex_a, hex_b = self.controller.get_hex_view(offset, 256)
        self.hex_a_text.setPlainText(hex_a)
        self.hex_b_text.setPlainText(hex_b)
    
    def _on_export(self):
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Diff Report", "diff_report.csv",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        if not filename:
            return
        
        try:
            if filename.lower().endswith('.csv'):
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['offset', 'size', 'hex_a', 'hex_b', 'map', 'category'])
                    # rebuild analyzer for category if available
                    try:
                        from flash_tool.bin_analyzer import BinAnalyzer
                        analyzer = BinAnalyzer(self.controller.file_b or self.controller.file_a)
                    except Exception:
                        analyzer = None
                    known_maps = self._get_known_maps()
                    for diff in self.controller.differences:
                        hex_a = ' '.join(f'{b:02X}' for b in diff.data_a[:32])
                        hex_b = ' '.join(f'{b:02X}' for b in diff.data_b[:32])
                        map_name = self._identify_map(diff.offset, diff.size, known_maps) or '-'
                        category = '-'
                        if analyzer is not None:
                            changes = [(diff.offset + j, diff.data_a[j] if j < len(diff.data_a) else 0, diff.data_b[j] if j < len(diff.data_b) else 0) for j in range(min(diff.size, 32))]
                            region = {'start': diff.offset, 'size': diff.size, 'changes': changes}
                            try:
                                category = analyzer.categorize_region(region)
                            except Exception:
                                category = '-'
                        writer.writerow([f"0x{diff.offset:06X}", diff.size, hex_a, hex_b, map_name, category])
            else:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Binary Comparison Report\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(f"File A: {self.file_a_edit.text()}\n")
                    f.write(f"File B: {self.file_b_edit.text()}\n\n")
                    f.write(f"Differences (showing {len(self.controller.differences)}):\n\n")
                    for diff in self.controller.differences:
                        f.write(f"Offset: 0x{diff.offset:06X}, Size: {diff.size} bytes\n")
                        f.write(f"  A: {' '.join(f'{b:02X}' for b in diff.data_a[:32])}\n")
                        f.write(f"  B: {' '.join(f'{b:02X}' for b in diff.data_b[:32])}\n\n")
            show_success_message(self, "Exported", f"Report saved to {filename}")
        except Exception as e:
            show_error_message(self, "Export Error", str(e))


def create_qt_widget(controller: Optional[BinCompareController] = None, parent=None):
    if controller is None:
        controller = BinCompareController()
    return BinCompareWidget(controller, parent)
