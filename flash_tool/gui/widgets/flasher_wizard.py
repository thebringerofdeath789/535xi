"""Flasher Wizard controller and lazy Qt widget.

Stage 1: file selection + offset validation + backup prompt.

This module mirrors the ConnectionWidget pattern: a framework-agnostic
controller (`FlasherController`) that can be tested without Qt, and a
`create_qt_widget(controller, parent=None)` function that builds a
Qt `QWidget` when Qt bindings are available.

Do NOT perform any write/flash in Stage 1. The controller exposes
`prepare_flash()` which validates inputs and returns a payload ready
for Stage 2 (which must call `map_flasher.flash_map`).
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import os
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime
from typing import Callable
import logging

logger = logging.getLogger(__name__)


def _log_exception(context: str, exc: Exception) -> None:
    """Log exceptions with context for easier debugging."""
    logger.exception(context, exc_info=exc)

from flash_tool.gui.worker import Worker, CancelToken


class FlasherController:
    """Framework-agnostic controller for flasher wizard stage 1.

    Responsibilities:
    - Hold selected file path and basic metadata
    - Validate offset/size using `validated_maps.is_offset_safe`
    - Validate map data using `map_validator`
    - Prepare a flash payload (in-memory) but DO NOT execute writes
    """

    def __init__(self, gui_api_module: Optional[Any] = None, map_flasher_module: Optional[Any] = None, validated_maps_module: Optional[Any] = None, map_validator_module: Optional[Any] = None, log_controller: Optional[Any] = None):
        # Dependency injection for tests
        if gui_api_module is None:
            try:
                from flash_tool.gui import gui_api as _g

                gui_api_module = _g
            except Exception as exc:
                _log_exception("Failed to import gui_api", exc)
                gui_api_module = SimpleNamespace()

        if map_flasher_module is None:
            try:
                from flash_tool import map_flasher as _m

                map_flasher_module = _m
            except Exception as exc:
                _log_exception("Failed to import map_flasher", exc)
                map_flasher_module = SimpleNamespace()

        if validated_maps_module is None:
            try:
                from flash_tool import validated_maps as _v

                validated_maps_module = _v
            except Exception as exc:
                _log_exception("Failed to import validated_maps", exc)
                validated_maps_module = SimpleNamespace(is_offset_safe=lambda o, s: (False, "no-validated-maps"))

        if map_validator_module is None:
            try:
                from flash_tool import map_validator as _mv
                map_validator_module = _mv
            except Exception as exc:
                _log_exception("Failed to import map_validator", exc)
                map_validator_module = None

        self.gui_api = gui_api_module
        self.map_flasher = map_flasher_module
        self.validated_maps = validated_maps_module
        self.map_validator = map_validator_module
        self.log_controller = log_controller

        self.selected_file: Optional[str] = None
        self.selected_size: Optional[int] = None

    def select_file(self, path: str) -> Dict[str, Any]:
        """Select a binary file and capture metadata.

        Returns metadata dict: {'path': path, 'size': size}
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        size = os.path.getsize(path)
        self.selected_file = path
        self.selected_size = size
        return {'path': path, 'size': size}

    def validate_offset(self, offset: int, size: Optional[int] = None) -> Dict[str, Any]:
        """Validate that the proposed offset+size is safe for flashing.

        Calls `validated_maps.is_offset_safe(offset, size)` and returns a dict
        with fields: {'safe': bool, 'reason': str}
        """
        if size is None:
            size = self.selected_size or 0

        try:
            result = self.validated_maps.is_offset_safe(offset, size)
        except Exception as exc:
            return {'safe': False, 'reason': f'validation-error: {exc}'}

        # support either bool or (bool, reason)
        if isinstance(result, tuple):
            safe, reason = result
        else:
            safe, reason = bool(result), ''

        return {'safe': bool(safe), 'reason': reason}

    def validate_map_data(self, data: bytes, offset: int, size: int) -> Dict[str, Any]:
        """Validate map data using map_validator.
        
        Calls map_validator.validate_map_before_write and returns full validation report.
        """
        try:
            if self.map_validator is None:
                return {
                    'valid': False,
                    'errors': ['map_validator not available'],
                    'warnings': [],
                    'details': {}
                }
            
            result = self.map_validator.validate_map_before_write(
                data=data,
                offset=offset,
                size=size
            )
            
            return {
                'valid': result.get('valid', False),
                'errors': result.get('errors', []),
                'warnings': result.get('warnings', []),
                'details': result
            }
        except Exception as exc:
            return {
                'valid': False,
                'errors': [f'validation-error: {exc}'],
                'warnings': [],
                'details': {}
            }

    def prepare_flash_payload(self, offset: int, size: Optional[int] = None) -> Dict[str, Any]:
        """Prepare an in-memory payload for flashing.

        This reads the selected file and slices the requested size, returning
        a dict: {'offset': offset, 'size': size, 'data': bytes, 'crc': int}
        Does NOT call any flasher functions.
        """
        if not self.selected_file:
            raise RuntimeError('no-file-selected')

        if size is None:
            size = self.selected_size

        with open(self.selected_file, 'rb') as f:
            data = f.read(size)

        # compute a simple CRC32 using built-in library
        try:
            import zlib

            crc = zlib.crc32(data) & 0xFFFFFFFF
        except Exception as exc:
            _log_exception("crc32 computation failed", exc)
            crc = 0

        return {'offset': offset, 'size': len(data), 'data': data, 'crc': crc}

    def execute_flash(self, vin: Optional[str] = None, safety_confirmed: bool = False, progress_cb: Optional[Callable[[str, int], None]] = None, cancel_token: Optional[CancelToken] = None, backup_dir: str = 'backups') -> Dict[str, Any]:
        """Execute the flash operation (Stage 2 orchestration).

        This method delegates the heavy lifting to `map_flasher.flash_map`.
        It requires `safety_confirmed=True` to proceed. `vin` may be provided
        explicitly or left as `None` so that `map_flasher` determines VIN via UDS.

        Returns the dict result from `map_flasher.flash_map`.
        """
        if not self.selected_file:
            raise RuntimeError('no-file-selected')

        if not safety_confirmed:
            raise RuntimeError('safety_confirmation_required')

        # Ensure file exists
        map_path = Path(self.selected_file)
        if not map_path.exists():
            raise FileNotFoundError(str(map_path))

        # If a log controller is available and no progress callback was
        # provided, build a small progress_cb that appends messages to it.
        if progress_cb is None and getattr(self, 'log_controller', None) is not None:
            def _log_progress(event_or_msg, percent=None):
                try:
                    if hasattr(event_or_msg, 'message'):
                        msg = f"{getattr(event_or_msg, 'message')} ({getattr(event_or_msg, 'progress', '')})"
                    else:
                        msg = str(event_or_msg)
                except Exception as exc:
                    _log_exception("progress message build failed", exc)
                    msg = str(event_or_msg)
                try:
                    self.log_controller.append(msg)
                except Exception as exc:
                    _log_exception("progress log append failed", exc)
            progress_cb = _log_progress

        # Delegate to map_flasher.flash_map. This function performs its own
        # pre-flash checks and will attempt to read VIN from ECU if vin is None.
        try:
            res = self.map_flasher.flash_map(map_path, vin or '', safety_confirmed=True, progress_callback=progress_cb)
            return res
        except Exception as e:
            _log_exception("flash_map execution failed", e)
            return {'success': False, 'error': str(e)}

    def check_backup(self, vin: Optional[str] = None) -> Dict[str, Any]:
        """Check whether a valid backup exists for `vin` without creating one.

        Returns the underlying `map_flasher.verify_backup_exists` result or
        a structured error dict on exception.
        """
        try:
            res = self.map_flasher.verify_backup_exists(vin)
            return res
        except Exception as e:
            _log_exception("verify_backup_exists failed", e)
            return {'success': False, 'error': str(e)}

    def ensure_backup(self, vin: Optional[str] = None, progress_cb: Optional[Callable[[str, int], None]] = None, cancel_token: Optional[CancelToken] = None, backup_dir: str = 'backups') -> Dict[str, Any]:
        """Ensure a valid full backup exists for `vin`.

        If a valid backup already exists (via `map_flasher.verify_backup_exists`) this
        returns immediately. Otherwise performs a full ECU flash read via
        `map_flasher.read_full_flash` and returns metadata.
        """
        # Provide a default progress callback that writes to the log controller
        if progress_cb is None and getattr(self, 'log_controller', None) is not None:
            def _log_progress(event_or_msg, percent=None):
                try:
                    if hasattr(event_or_msg, 'message'):
                        msg = f"{getattr(event_or_msg, 'message')} ({getattr(event_or_msg, 'progress', '')})"
                    else:
                        msg = str(event_or_msg)
                except Exception as exc:
                    _log_exception("backup progress message build failed", exc)
                    msg = str(event_or_msg)
                try:
                    self.log_controller.append(msg)
                except Exception as exc:
                    _log_exception("backup progress log append failed", exc)
            progress_cb = _log_progress

        # Build a combined progress callback that both forwards to any
        # provided progress_cb and appends messages to the log_controller
        orig_progress = progress_cb
        def _combined_progress(event_or_msg, percent=None):
            # Forward to original callback first
            try:
                if orig_progress:
                    orig_progress(event_or_msg, percent)
            except Exception as exc:
                _log_exception("orig progress callback failed", exc)
            # Then append to log controller if present
            try:
                if getattr(self, 'log_controller', None) is not None:
                    try:
                        if hasattr(event_or_msg, 'message'):
                            msg = f"{getattr(event_or_msg, 'message')} ({getattr(event_or_msg, 'progress', '')})"
                        else:
                            msg = str(event_or_msg)
                    except Exception as exc:
                        _log_exception("combined progress message build failed", exc)
                        msg = str(event_or_msg)
                    try:
                        self.log_controller.append(msg)
                    except Exception as exc:
                        _log_exception("combined progress log append failed", exc)
            except Exception as exc:
                _log_exception("combined progress handler failed", exc)

        # Use the combined progress callback for downstream calls
        progress_cb = _combined_progress

        # If VIN provided, check for existing valid backup first
        try:
            if vin:
                try:
                    check = self.map_flasher.verify_backup_exists(vin)
                except Exception as e:
                    # Non-fatal: log and continue to attempt a fresh backup
                    if progress_cb:
                        try:
                            progress_cb(f"Backup check failed: {e}", 0)
                        except Exception as exc:
                            _log_exception("progress callback during backup check failed", exc)
                    check = {'success': False, 'backup_found': False}

                if check.get('success') and check.get('backup_found'):
                    # Already have a valid backup
                    return {
                        'success': True,
                        'backup_path': str(check.get('backup_file')) if check.get('backup_file') else None,
                        'already_exists': True,
                        'backup_info': check.get('backup_info')
                    }

            # Respect an already-requested cancel before starting heavy I/O
            if cancel_token is not None and cancel_token.is_cancelled():
                if progress_cb:
                    try:
                        progress_cb('Backup cancelled', 0)
                    except Exception as exc:
                        _log_exception("progress callback during cancellation failed", exc)
                return {'success': False, 'error': 'cancelled'}

            # Perform full flash read (map_flasher will auto-generate filename/dir)
            res = self.map_flasher.read_full_flash(output_file=None, vin=vin, progress_callback=progress_cb)
            if res.get('success'):
                return {
                    'success': True,
                    'backup_path': res.get('filepath'),
                    'file_size': res.get('file_size'),
                    'checksum': res.get('checksum'),
                    'vin': res.get('vin')
                }
            return res
        except Exception as e:
            if progress_cb:
                try:
                    progress_cb(f'Error creating backup: {e}', 0)
                except Exception as exc:
                    _log_exception("progress callback during backup error failed", exc)
            _log_exception("ensure_backup failed", e)
            return {'success': False, 'error': str(e)}


def create_qt_widget(controller: FlasherController, parent: Optional[Any] = None):
    """Build a Qt widget for the flasher wizard stage 1.

    Lazy imports the Qt bindings (PySide6 or PyQt5). The widget allows
    selecting a file, entering an offset, validating with `validated_maps`,
    and preparing the payload (but does not execute the flash).
    """
    QtWidgets = None
    QtCore = None
    try:
        from PySide6 import QtWidgets as _w, QtCore as _c
        QtWidgets, QtCore = _w, _c
    except Exception as exc:
        _log_exception("PySide6 import failed", exc)
        try:
            from PyQt5 import QtWidgets as _w, QtCore as _c
            QtWidgets, QtCore = _w, _c
        except Exception as exc:
            _log_exception("PyQt5 import failed", exc)
            raise ImportError('Qt bindings not available') from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            # runtime worker/cancel token refs (used by Cancel button)
            self._current_worker = None
            self._current_cancel_token = None

            layout = QtWidgets.QVBoxLayout(self)

            file_h = QtWidgets.QHBoxLayout()
            self.file_edit = QtWidgets.QLineEdit()
            self.browse_btn = QtWidgets.QPushButton('Browse')
            file_h.addWidget(self.file_edit)
            file_h.addWidget(self.browse_btn)
            layout.addLayout(file_h)

            offset_h = QtWidgets.QHBoxLayout()
            self.offset_edit = QtWidgets.QLineEdit()
            self.offset_edit.setPlaceholderText('Offset (hex, e.g. 0x57B58)')
            self.size_edit = QtWidgets.QLineEdit()
            self.size_edit.setPlaceholderText('Size (bytes, optional)')
            self.validate_btn = QtWidgets.QPushButton('Validate')
            offset_h.addWidget(self.offset_edit)
            offset_h.addWidget(self.size_edit)
            offset_h.addWidget(self.validate_btn)
            layout.addLayout(offset_h)

            self.result_label = QtWidgets.QLabel('')
            layout.addWidget(self.result_label)

            # Progress bar for long-running operations (updated via Worker ProgressEvent)
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            layout.addWidget(self.progress_bar)

            self.prepare_btn = QtWidgets.QPushButton('Prepare Payload')
            self.prepare_btn.setEnabled(False)
            layout.addWidget(self.prepare_btn)
            self.backup_btn = QtWidgets.QPushButton('Backup')
            self.backup_btn.setEnabled(True)
            layout.addWidget(self.backup_btn)
            self.check_backup_btn = QtWidgets.QPushButton('Check Backup')
            self.check_backup_btn.setEnabled(True)
            layout.addWidget(self.check_backup_btn)
            self.execute_btn = QtWidgets.QPushButton('Execute Flash')
            self.execute_btn.setEnabled(False)
            layout.addWidget(self.execute_btn)
            self.cancel_btn = QtWidgets.QPushButton('Cancel')
            self.cancel_btn.setEnabled(False)
            layout.addWidget(self.cancel_btn)

            self.browse_btn.clicked.connect(self._on_browse)
            self.validate_btn.clicked.connect(self._on_validate)
            self.prepare_btn.clicked.connect(self._on_prepare)
            self.execute_btn.clicked.connect(self._on_execute)
            self.backup_btn.clicked.connect(self._on_backup)
            self.check_backup_btn.clicked.connect(self._on_check_backup)
            self.cancel_btn.clicked.connect(self._on_cancel)

        def _on_browse(self):
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select binary', '', 'Binary Files (*.bin);;All Files (*)')
            if path:
                self.file_edit.setText(path)
                try:
                    meta = self._ctrl.select_file(path)
                    self.result_label.setText(f"Selected {meta['path']} ({meta['size']} bytes)")
                    # Try to auto-populate offset/size if file matches a validated map
                    valid_maps = getattr(self._ctrl.validated_maps, 'VALIDATED_MAPS', None)
                    if valid_maps and isinstance(valid_maps, dict):
                        found = False
                        for offset, info in valid_maps.items():
                            if isinstance(info, dict):
                                sz = info.get('size')
                                if sz == meta['size']:
                                    # Auto-fill offset/size fields
                                    self.offset_edit.setText(hex(offset))
                                    self.size_edit.setText(str(sz))
                                    self.result_label.setText(f"Selected {meta['path']} ({meta['size']} bytes)\nAuto-filled offset: {hex(offset)}, size: {sz}")
                                    found = True
                                    break
                        if not found:
                            self.result_label.setText(f"Selected {meta['path']} ({meta['size']} bytes)\nNo validated map found for this size. Please enter a valid offset and size.")
                    else:
                        self.result_label.setText(f"Selected {meta['path']} ({meta['size']} bytes)\n(Validated map info unavailable)")
                except Exception as e:
                    _log_exception("select_file failed", e)
                    self.result_label.setText(f'Error selecting file: {e}')

        def _parse_offset(self, text: str) -> Optional[int]:
            if not text:
                return None
            try:
                if text.lower().startswith('0x'):
                    return int(text, 16)
                return int(text, 10)
            except ValueError:
                return None
            except Exception as exc:
                _log_exception("parse offset failed", exc)
                return None

        def _on_validate(self):
            off = self._parse_offset(self.offset_edit.text())
            if off is None:
                self.result_label.setText('Invalid offset. Please enter a valid hex or decimal offset (e.g. 0x57B58).')
                return
            size_text = self.size_edit.text().strip()
            size = None
            if size_text:
                try:
                    size = int(size_text)
                except Exception as exc:
                    _log_exception("parse size failed", exc)
                    self.result_label.setText('Invalid size. Please enter a valid integer size in bytes.')
                    return

            res = self._ctrl.validate_offset(off, size)
            if res.get('safe'):
                self.result_label.setText('Offset safe: ' + (res.get('reason') or '') + '\nYou may now prepare or flash this region.')
                self.prepare_btn.setEnabled(True)
                self.execute_btn.setEnabled(True)
            else:
                # Add more guidance if validation fails
                msg = 'Offset NOT safe: ' + (res.get('reason') or '')
                msg += '\nCheck that you are using a validated map region and correct offset/size.'
                self.result_label.setText(msg)
                self.prepare_btn.setEnabled(False)
                self.execute_btn.setEnabled(False)

        def _on_prepare(self):
            off = self._parse_offset(self.offset_edit.text())
            size_text = self.size_edit.text().strip()
            size = None
            if size_text:
                try:
                    size = int(size_text)
                except Exception as exc:
                    _log_exception("prepare size parse failed", exc)
                    size = None

            try:
                payload = self._ctrl.prepare_flash_payload(off, size)
            except Exception as e:
                self.result_label.setText(f'Prepare failed: {e}')
                return

            self.result_label.setText(f"Prepared payload: {payload['size']} bytes @ {hex(payload['offset'])}, crc={hex(payload['crc'])}")

        def _on_execute(self):
            # CLI-parity confirmation workflow (three-step):
            # 1) Type YES to acknowledge risks
            # 2) Type FLASH to confirm intent
            # 3) Type last 7 digits of VIN to confirm vehicle (if VIN available)
            # Step 1
            text1, ok = QtWidgets.QInputDialog.getText(self, 'Confirm Flash - Step 1', 'Type YES (all caps) to acknowledge risks:')
            if not ok or (text1 or '').strip() != 'YES':
                self.result_label.setText('Flash cancelled (confirmation 1 failed)')
                return
            # Step 2
            text2, ok = QtWidgets.QInputDialog.getText(self, 'Confirm Flash - Step 2', 'Type FLASH (all caps) to confirm intent:')
            if not ok or (text2 or '').strip() != 'FLASH':
                self.result_label.setText('Flash cancelled (confirmation 2 failed)')
                return
            # Step 3: VIN confirmation (best-effort - attempt to read VIN if available)
            vin_last_7 = None
            try:
                # try to obtain VIN via controller's map_flasher if available
                if hasattr(self._ctrl, 'map_flasher') and getattr(self._ctrl.map_flasher, 'read_vin', None):
                    try:
                        vin_val = self._ctrl.map_flasher.read_vin()
                        if vin_val:
                            vin_last_7 = vin_val[-7:]
                    except Exception as exc:
                        _log_exception("read_vin failed", exc)
                        vin_last_7 = None
            except Exception as exc:
                _log_exception("VIN confirmation setup failed", exc)
                vin_last_7 = None

            prompt = 'Type the LAST 7 DIGITS of your VIN to confirm:'
            if vin_last_7:
                prompt = f"Type the LAST 7 DIGITS of your VIN to confirm (expected: {vin_last_7}):"

            text3, ok = QtWidgets.QInputDialog.getText(self, 'Confirm Flash - Step 3', prompt)
            if not ok:
                self.result_label.setText('Flash cancelled (confirmation 3 cancelled)')
                return
            if vin_last_7 and (text3 or '').strip() != vin_last_7:
                self.result_label.setText(f'Flash cancelled (VIN confirmation failed)')
                return

            # Disable UI controls during operation
            self.prepare_btn.setEnabled(False)
            self.execute_btn.setEnabled(False)
            self.result_label.setText('Starting flash...')
            try:
                self.progress_bar.setValue(0)
            except Exception as exc:
                _log_exception("reset progress bar before flash", exc)

            # Progress callback marshalled to Qt main thread
            def ui_progress(event_or_msg, percent=None):
                def _update():
                    try:
                        # Accept either (msg, percent) or ProgressEvent-like
                        if hasattr(event_or_msg, 'message'):
                            msg = str(getattr(event_or_msg, 'message'))
                            pct = getattr(event_or_msg, 'progress', '')
                        else:
                            msg = str(event_or_msg)
                            pct = percent if percent is not None else ''
                        self.result_label.setText(f"{msg} {pct}")
                        # Update progress bar when percent available
                        try:
                            if pct != '' and pct is not None:
                                self.progress_bar.setValue(int(float(pct)))
                        except Exception as exc:
                            _log_exception("update flash progress bar", exc)
                    except Exception as exc:
                        _log_exception("update flash progress UI failed", exc)
                        self.result_label.setText(str(event_or_msg))
                QtCore.QTimer.singleShot(0, _update)

            # create and track cancel token + worker for possible cancellation
            self._current_cancel_token = CancelToken()
            cancel_token = self._current_cancel_token

            # Worker task: call controller.execute_flash with progress callback
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.execute_flash(vin=None, safety_confirmed=True, progress_cb=progress_cb, cancel_token=cancel_token)

            worker = Worker(task=task, progress_cb=ui_progress, cancel_token=cancel_token)
            self._current_worker = worker
            # enable cancel button while operation is running
            try:
                self.cancel_btn.setEnabled(True)
            except Exception as exc:
                _log_exception("enable cancel button for flash", exc)
            worker.start()

            # Poll for completion and update UI when done
            def poll():
                if worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll)
                    return

                try:
                    res = worker.result()
                except Exception as e:
                    self.result_label.setText(f'Flash exception: {e}')
                    self.prepare_btn.setEnabled(True)
                    self.execute_btn.setEnabled(True)
                    return

                if isinstance(res, dict) and res.get('success'):
                    self.result_label.setText('Flash completed successfully')
                    try:
                        self.progress_bar.setValue(100)
                    except Exception as exc:
                        _log_exception("complete progress bar set", exc)
                else:
                    err = res.get('error') if isinstance(res, dict) else str(res)
                    self.result_label.setText('Flash failed: ' + (err or 'unknown'))
                    try:
                        self.progress_bar.setValue(0)
                    except Exception as exc:
                        _log_exception("reset progress bar after flash failure", exc)

                # cleanup worker/cancel state and UI
                try:
                    self.cancel_btn.setEnabled(False)
                except Exception as exc:
                    _log_exception("disable cancel button after flash", exc)
                self._current_worker = None
                self._current_cancel_token = None

                self.prepare_btn.setEnabled(True)
                self.execute_btn.setEnabled(True)

            QtCore.QTimer.singleShot(200, poll)

        def _on_backup(self):
            # Disable UI controls during backup
            self.backup_btn.setEnabled(False)
            self.prepare_btn.setEnabled(False)
            self.execute_btn.setEnabled(False)
            self.result_label.setText('Starting backup...')
            try:
                self.progress_bar.setValue(0)
            except Exception as exc:
                _log_exception("reset progress bar before backup", exc)

            def ui_progress(event_or_msg, percent=None):
                def _update():
                    try:
                        if hasattr(event_or_msg, 'message'):
                            msg = str(getattr(event_or_msg, 'message'))
                            pct = getattr(event_or_msg, 'progress', '')
                        else:
                            msg = str(event_or_msg)
                            pct = percent if percent is not None else ''
                        self.result_label.setText(f"{msg} {pct}")
                        # Update progress bar
                        try:
                            if pct != '' and pct is not None:
                                self.progress_bar.setValue(int(float(pct)))
                        except Exception as exc:
                            _log_exception("update backup progress bar", exc)
                        # Also append to log if available
                        try:
                            if hasattr(self._ctrl, 'log_controller') and getattr(self._ctrl, 'log_controller') is not None:
                                self._ctrl.log_controller.append(f"BACKUP: {msg} {pct}")
                        except Exception as exc:
                            _log_exception("log backup progress", exc)
                    except Exception as exc:
                        _log_exception("update backup progress UI failed", exc)
                        self.result_label.setText(str(event_or_msg))
                QtCore.QTimer.singleShot(0, _update)

            # Track cancel token and worker so user can cancel
            self._current_cancel_token = CancelToken()
            cancel_token = self._current_cancel_token

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.ensure_backup(vin=None, progress_cb=progress_cb, cancel_token=cancel_token)

            worker = Worker(task=task, progress_cb=ui_progress, cancel_token=cancel_token)
            self._current_worker = worker
            try:
                self.cancel_btn.setEnabled(True)
            except Exception as exc:
                _log_exception("enable cancel button for backup", exc)
            worker.start()

            def poll():
                if worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll)
                    return

                try:
                    res = worker.result()
                except Exception as e:
                    self.result_label.setText(f'Backup exception: {e}')
                    self.backup_btn.setEnabled(True)
                    self.prepare_btn.setEnabled(True)
                    self.execute_btn.setEnabled(True)
                    return

                if isinstance(res, dict) and res.get('success'):
                    path = res.get('backup_path') or res.get('filepath') or ''
                    self.result_label.setText(f'Backup saved: {path}')
                    try:
                        self.progress_bar.setValue(100)
                    except Exception as exc:
                        _log_exception("complete backup progress bar set", exc)
                else:
                    err = res.get('error') if isinstance(res, dict) else str(res)
                    self.result_label.setText('Backup failed: ' + (err or 'unknown'))
                    try:
                        self.progress_bar.setValue(0)
                    except Exception as exc:
                        _log_exception("reset progress bar after backup failure", exc)

                # cleanup worker state
                try:
                    self.cancel_btn.setEnabled(False)
                except Exception as exc:
                    _log_exception("disable cancel button after backup", exc)
                self._current_worker = None
                self._current_cancel_token = None

                self.backup_btn.setEnabled(True)
                self.prepare_btn.setEnabled(True)
                self.execute_btn.setEnabled(True)

            QtCore.QTimer.singleShot(200, poll)

        def _on_check_backup(self):
            # Run a quick check for an existing backup without creating one
            self.check_backup_btn.setEnabled(False)
            self.result_label.setText('Checking backups...')
            try:
                self.progress_bar.setValue(0)
            except Exception as exc:
                _log_exception("reset progress bar before check backup", exc)

            def ui_progress(event_or_msg, percent=None):
                def _update():
                    try:
                        if hasattr(event_or_msg, 'message'):
                            msg = str(getattr(event_or_msg, 'message'))
                            pct = getattr(event_or_msg, 'progress', '')
                        else:
                            msg = str(event_or_msg)
                            pct = percent if percent is not None else ''
                        self.result_label.setText(msg)
                        try:
                            if pct != '' and pct is not None:
                                self.progress_bar.setValue(int(float(pct)))
                        except Exception as exc:
                            _log_exception("update check-backup progress bar", exc)
                        try:
                            if hasattr(self._ctrl, 'log_controller') and getattr(self._ctrl, 'log_controller') is not None:
                                self._ctrl.log_controller.append(f"CHECK_BACKUP: {msg}")
                        except Exception as exc:
                            _log_exception("log check-backup progress", exc)
                    except Exception as exc:
                        _log_exception("update check-backup progress UI failed", exc)
                        self.result_label.setText(str(event_or_msg))
                QtCore.QTimer.singleShot(0, _update)

            cancel_token = CancelToken()

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.check_backup(vin=None)

            worker = Worker(task=task, progress_cb=ui_progress, cancel_token=cancel_token)
            self._current_worker = worker
            self._current_cancel_token = cancel_token
            try:
                self.cancel_btn.setEnabled(True)
            except Exception as exc:
                _log_exception("enable cancel button for check backup", exc)
            worker.start()

            def poll_check():
                if worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll_check)
                    return

                try:
                    res = worker.result()
                except Exception as e:
                    self.result_label.setText(f'Check exception: {e}')
                    self.check_backup_btn.setEnabled(True)
                    try:
                        self.cancel_btn.setEnabled(False)
                    except Exception as exc:
                        _log_exception("disable cancel button after check exception", exc)
                    self._current_worker = None
                    self._current_cancel_token = None
                    return

                if isinstance(res, dict) and res.get('success') and res.get('backup_found'):
                    path = res.get('backup_file') or ''
                    self.result_label.setText(f'Valid backup found: {path}')
                    try:
                        self.progress_bar.setValue(100)
                    except Exception as exc:
                        _log_exception("complete check-backup progress bar set", exc)
                else:
                    err = res.get('error') if isinstance(res, dict) else str(res)
                    self.result_label.setText('No valid backup: ' + (err or 'none'))
                    try:
                        self.progress_bar.setValue(0)
                    except Exception as exc:
                        _log_exception("reset progress bar after check-backup failure", exc)

                self.check_backup_btn.setEnabled(True)
                try:
                    self.cancel_btn.setEnabled(False)
                except Exception as exc:
                    _log_exception("disable cancel button after check backup", exc)
                self._current_worker = None
                self._current_cancel_token = None

            QtCore.QTimer.singleShot(200, poll_check)

        def _on_cancel(self):
            try:
                if getattr(self, '_current_cancel_token', None) is not None:
                    self._current_cancel_token.request_cancel()
                    self.result_label.setText('Cancellation requested...')
                    try:
                        self.progress_bar.setValue(0)
                    except Exception as exc:
                        _log_exception("reset progress bar on cancel", exc)
                    try:
                        self.cancel_btn.setEnabled(False)
                    except Exception as exc:
                        _log_exception("disable cancel button on cancel", exc)
            except Exception as exc:
                _log_exception("cancel handler failed", exc)

    return _Widget(parent)
