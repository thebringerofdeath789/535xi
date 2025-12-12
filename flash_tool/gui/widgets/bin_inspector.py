"""Bin Inspector controller and lazy Qt widget.

Provides a testable `BinInspectorController` that analyzes a `.bin` file to extract
VINs, hardware part numbers, and interesting ASCII strings. The `create_qt_widget`
function builds a UI to select a file and show analysis results.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List
from pathlib import Path
import hashlib
import traceback
import re

from flash_tool.gui.worker import Worker, CancelToken
from flash_tool.operation_logger import log_operation

try:
    from flash_tool.gui.utils import (
        show_error_message,
        show_success_message,
        show_warning_message,
        show_info_message,
        format_timestamp,
    )
except Exception:
    # headless fallbacks
    show_error_message = lambda *args, **kwargs: None
    show_success_message = lambda *args, **kwargs: None
    show_warning_message = lambda *args, **kwargs: None
    show_info_message = lambda *args, **kwargs: None
    format_timestamp = lambda: ""


class BinInspectorController:
    def __init__(self, analyzer_module: Optional[Any] = None, log_controller: Optional[Any] = None):
        if analyzer_module is None:
            try:
                import analyze_bin_vehicle_data as _an
                analyzer_module = _an
            except Exception:
                analyzer_module = None
        self.analyzer = analyzer_module
        self.log_controller = log_controller

    def inspect_file(self, file_path: str) -> Dict[str, Any]:
        try:
            p = Path(file_path)
            if not p.exists() or not p.is_file():
                return {'success': False, 'error': 'file-not-found'}

            data = p.read_bytes()
            size = len(data)
            checksum = hashlib.sha256(data).hexdigest()

            result: Dict[str, Any] = {
                'success': True,
                'file': str(p),
                'size': size,
                'checksum': checksum,
                'vins': [],
                'part_numbers': [],
                'strings': {},
                'sw_id': None,
                'ecu_type': None,
            }

            # Extract SW ID and ECU type (basic heuristic)
            try:
                sw_id = self._extract_sw_id(data)
                result['sw_id'] = sw_id
                result['ecu_type'] = self._ecu_type_from_sw(sw_id)
            except Exception:
                result['sw_id'] = None
                result['ecu_type'] = None

            if self.analyzer is None:
                return result

            try:
                vins = self.analyzer.find_vin_in_bin(data)
                result['vins'] = [{'vin': v, 'offset': offset} for (v, offset) in vins]
            except Exception:
                result['vins'] = []

            try:
                pns = self.analyzer.find_hardware_numbers(data)
                result['part_numbers'] = [{'part': pnum, 'offset': off} for (pnum, off) in pns]
            except Exception:
                result['part_numbers'] = []

            try:
                strings = self.analyzer.find_ascii_strings(data)
                result['strings'] = strings
            except Exception:
                result['strings'] = {}

            return result
        except Exception as e:
            return {'success': False, 'error': str(e), 'trace': traceback.format_exc()}

    def validate_crcs(self, file_path: str) -> Dict[str, Any]:
        """Validate known CRC zones and return per-zone results."""
        try:
            p = Path(file_path)
            if not p.exists() or not p.is_file():
                return {'success': False, 'error': 'file-not-found'}

            data = p.read_bytes()
            sw_id = self._extract_sw_id(data)
            ecu_type = self._ecu_type_from_sw(sw_id) or 'MSD81'

            from flash_tool.bmw_checksum import calculate_zone_checksums
            zones = calculate_zone_checksums(data, ecu_type=ecu_type)
            valid_count = sum(1 for z in zones if z.get('valid') is True)
            total = len(zones)

            log_operation('CRC Validate', 'info', f"{valid_count}/{total} zones valid (ECU={ecu_type}, SW={sw_id or '-'})")

            return {
                'success': True,
                'file': str(p),
                'ecu_type': ecu_type,
                'sw_id': sw_id,
                'zones': zones,
                'summary': f"{valid_count}/{total} zones valid"
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'trace': traceback.format_exc()}

    def _extract_sw_id(self, data: bytes) -> Optional[str]:
        pattern = re.compile(rb'[A-Z][A-Z0-9]{3}S')
        m = pattern.search(data)
        if m:
            try:
                return m.group().decode('ascii')
            except Exception:
                return None
        return None

    def _ecu_type_from_sw(self, sw_id: Optional[str]) -> Optional[str]:
        if not sw_id:
            return None
        if sw_id.startswith('I8') or sw_id.startswith('IJ'):
            return 'MSD81'
        return None


def create_qt_widget(controller: BinInspectorController, parent: Optional[Any] = None):
    try:
        from PySide6 import QtWidgets, QtCore
    except Exception:
        try:
            from PyQt5 import QtWidgets, QtCore
        except Exception as exc:
            raise ImportError('Qt bindings not available for Bin Inspector') from exc


    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._worker = None
            self._cancel_token = None

            layout = QtWidgets.QVBoxLayout(self)

            # Add help button (top right)
            help_btn = QtWidgets.QPushButton('Help')
            help_btn.setToolTip('Show help and usage instructions for the Bin Inspector tool.')
            help_btn.setFixedWidth(60)
            help_btn.clicked.connect(self._show_help_dialog)
            hlayout = QtWidgets.QHBoxLayout()
            hlayout.addStretch()
            hlayout.addWidget(help_btn)
            layout.addLayout(hlayout)

            # File selection row
            file_h = QtWidgets.QHBoxLayout()
            self.file_edit = QtWidgets.QLineEdit()
            self.file_edit.setToolTip('Select the .bin file to inspect.')
            self.browse_btn = QtWidgets.QPushButton('Browse')
            self.browse_btn.setToolTip('Browse for a .bin file to inspect.')
            self.inspect_btn = QtWidgets.QPushButton('Inspect')
            self.inspect_btn.setToolTip('Analyze the selected .bin file for VINs, part numbers, and strings.')
            self.crc_btn = QtWidgets.QPushButton('Validate CRCs')
            self.crc_btn.setToolTip('Validate known CRC zones in the selected .bin file.')
            file_h.addWidget(self.file_edit)
            file_h.addWidget(self.browse_btn)
            file_h.addWidget(self.inspect_btn)
            file_h.addWidget(self.crc_btn)
            layout.addLayout(file_h)

            self.output = QtWidgets.QPlainTextEdit()
            self.output.setReadOnly(True)
            self.output.setToolTip('Analysis results and log output will appear here.')
            layout.addWidget(self.output)

            self.browse_btn.clicked.connect(self._on_browse)
            self.inspect_btn.clicked.connect(self._on_inspect)
            self.crc_btn.clicked.connect(self._on_crc)

        def _show_help_dialog(self):
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle('Bin Inspector Help')
            msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
            msg.setText(
                '<b>Bin Inspector Tool Help</b><br><br>'
                '<b>Purpose:</b> Analyze a .bin file to extract VINs, hardware part numbers, and interesting ASCII strings.<br>'
                '<ul>'
                '<li><b>Browse:</b> Select a .bin file to inspect.</li>'
                '<li><b>Inspect:</b> Analyze the file for VINs, part numbers, and ASCII strings.</li>'
                '<li><b>Validate CRCs:</b> Check known CRC zones for validity.</li>'
                '<li><b>Output:</b> Results and logs are shown in the output area below.</li>'
                '</ul>'
                '<b>Tips:</b> Hover over any control for more info. Use the help button for guidance at any time.'
            )
            msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            msg.exec()

        def _append(self, text: str):
            try:
                ts = QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate)
                self.output.appendPlainText(f"[{ts}] {text}")
            except Exception:
                try:
                    self.output.appendPlainText(str(text))
                except Exception:
                    pass

        def _on_browse(self):
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select binary', '', 'Binary Files (*.bin);;All Files (*)')
            if path:
                self.file_edit.setText(path)

        def _on_inspect(self):
            path = self.file_edit.text().strip()
            if not path:
                show_warning_message(self, 'Missing File', 'Please select a .bin file to inspect.')
                return

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.inspect_file(path)

            def on_done(res):
                if not res.get('success'):
                    show_error_message(self, 'Inspect Failed', str(res.get('error', 'unknown')))
                    return
                self._append(f"File: {res.get('file')}")
                self._append(f"Size: {res.get('size')} bytes; SHA256: {res.get('checksum')}")
                sw_id = res.get('sw_id')
                ecu_type = res.get('ecu_type')
                if sw_id or ecu_type:
                    self._append(f"SW ID: {sw_id or '-'}; ECU: {ecu_type or '-'}")
                vins = res.get('vins', [])
                if vins:
                    for v in vins: self._append(f"Found VIN: {v['vin']} @ 0x{v['offset']:08X}")
                else:
                    self._append('No VINs found')
                pns = res.get('part_numbers', [])
                if pns:
                    for p in pns: self._append(f"Part: {p['part']} @ 0x{p['offset']:08X}")
                strings = res.get('strings', {}) or {}
                if strings:
                    for off, s in list(strings.items())[:10]:
                        self._append(f"0x{off:08X}: {s}")

            self._worker = Worker(task=task, progress_cb=lambda e: self._append(getattr(e, 'message', str(e))), cancel_token=CancelToken())
            self._worker.start()
            # poll for done
            def poll_done():
                if self._worker and self._worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll_done)
                    return
                try:
                    res = self._worker.result()
                except Exception as e:
                    res = {'success': False, 'error': str(e)}
                on_done(res)

            QtCore.QTimer.singleShot(200, poll_done)

        def _on_crc(self):
            path = self.file_edit.text().strip()
            if not path:
                show_warning_message(self, 'Missing File', 'Please select a .bin file to validate CRCs.')
                return

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.validate_crcs(path)

            def on_done(res):
                if not res.get('success'):
                    show_error_message(self, 'CRC Validation Failed', str(res.get('error', 'unknown')))
                    return
                self._append(f"CRC Validation Summary: {res.get('summary')}")
                self._append(f"ECU: {res.get('ecu_type')} / SW: {res.get('sw_id') or '-'}")
                zones = res.get('zones', [])
                if zones:
                    # Show boundaries and validity
                    for z in zones:
                        start = z.get('start'); end = z.get('end'); crc_type = z.get('crc_type')
                        calc = z.get('calculated'); stored = z.get('stored'); valid = z.get('valid')
                        name = z.get('zone_name')
                        self._append(f"{name}: 0x{start:06X} - 0x{(end or 0):06X} [{crc_type}] -> calc=0x{(calc or 0):X} stored=0x{(stored or 0):X} valid={'✓' if valid else '✗' if valid is not None else '-'}")
                else:
                    self._append('No zones available for this ECU type')
                show_success_message(self, 'CRC Validation', 'Completed CRC checks for known zones.')

            self._worker = Worker(task=task, progress_cb=lambda e: self._append(getattr(e, 'message', str(e))), cancel_token=CancelToken())
            self._worker.start()
            def poll_done():
                if self._worker and self._worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll_done)
                    return
                try:
                    res = self._worker.result()
                except Exception as e:
                    res = {'success': False, 'error': str(e)}
                on_done(res)
            QtCore.QTimer.singleShot(200, poll_done)

    return _Widget(parent)
