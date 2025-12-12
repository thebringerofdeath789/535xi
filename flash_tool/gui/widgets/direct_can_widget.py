"""Direct CAN Flash Widget for GUI.

Provides direct CAN/UDS communication for ECU flashing operations.
Implements connection via PCAN adapter, security access, memory read/write.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
import traceback

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, QThread
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
        from PyQt5.QtCore import pyqtSignal as Signal, QThread
    except Exception as exc:
        raise ImportError('Qt bindings not available for Direct CAN Widget') from exc

# Standardized background worker and messaging
try:
    from flash_tool.gui.worker import Worker, CancelToken, ProgressEvent
except Exception:
    Worker = None  # type: ignore
    CancelToken = None  # type: ignore
    ProgressEvent = None  # type: ignore

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


class DirectCANWorker(QThread):
    """Background worker for CAN operations."""
    progress = Signal(int, str)  # percent, message
    finished = Signal(bool, str)  # success, result/error
    log_message = Signal(str)  # log output
    
    def __init__(self, operation: str, params: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params
        self._cancel = False
    
    def cancel(self):
        self._cancel = True
    
    def run(self):
        try:
            from flash_tool.direct_can_flasher import DirectCANFlasher
            
            interface = self.params.get('interface', 'pcan')
            channel = self.params.get('channel', 'PCAN_USBBUS1')
            
            self.log_message.emit(f"Connecting to {interface}:{channel}...")
            self.progress.emit(10, "Initializing CAN interface...")
            
            flasher = DirectCANFlasher(can_interface=interface, can_channel=channel)
            
            if self.operation == 'connect':
                self.progress.emit(30, "Connecting to ECU...")
                if flasher.connect():
                    self.progress.emit(100, "Connected!")
                    self.finished.emit(True, "Successfully connected to ECU")
                else:
                    self.finished.emit(False, "Failed to connect to ECU")
            
            elif self.operation == 'unlock':
                self.progress.emit(20, "Connecting...")
                if not flasher.connect():
                    self.finished.emit(False, "Failed to connect")
                    return
                
                self.progress.emit(40, "Requesting security access...")
                algorithm = self.params.get('algorithm', None)
                
                if algorithm:
                    self.log_message.emit(f"Using algorithm: {algorithm}")
                    success = flasher.unlock_ecu(algorithm=algorithm)
                else:
                    self.log_message.emit("Trying all algorithms...")
                    success = flasher.unlock_ecu(try_all_algorithms=True)
                
                if success:
                    self.progress.emit(100, "ECU Unlocked!")
                    self.finished.emit(True, "Security access granted")
                else:
                    self.finished.emit(False, "Security access denied")
            
            elif self.operation == 'read_memory':
                self.progress.emit(20, "Connecting...")
                if not flasher.connect():
                    self.finished.emit(False, "Failed to connect")
                    return
                
                offset = self.params.get('offset', 0)
                size = self.params.get('size', 256)
                output_file = self.params.get('output_file', None)
                
                self.progress.emit(40, f"Reading {size} bytes from 0x{offset:06X}...")
                self.log_message.emit(f"Read request: offset=0x{offset:06X}, size={size}")
                
                data = flasher.read_memory(offset, size)
                
                if data:
                    if output_file:
                        Path(output_file).write_bytes(data)
                        self.log_message.emit(f"Saved to {output_file}")
                    self.progress.emit(100, "Read complete!")
                    self.finished.emit(True, f"Read {len(data)} bytes successfully")
                else:
                    self.finished.emit(False, "Failed to read memory")
            
            elif self.operation == 'read_calibration':
                self.progress.emit(20, "Connecting...")
                if not flasher.connect():
                    self.finished.emit(False, "Failed to connect")
                    return
                
                output_file = self.params.get('output_file', 'calibration_backup.bin')
                
                self.progress.emit(30, "Unlocking ECU...")
                if not flasher.unlock_ecu(try_all_algorithms=True):
                    self.finished.emit(False, "Failed to unlock ECU")
                    return
                
                self.progress.emit(50, "Reading calibration region...")
                self.log_message.emit("Reading full calibration area...")
                
                data = flasher.read_calibration_region()
                
                if data:
                    Path(output_file).write_bytes(data)
                    self.progress.emit(100, "Backup complete!")
                    self.log_message.emit(f"Saved {len(data)} bytes to {output_file}")
                    self.finished.emit(True, f"Calibration backup saved: {output_file}")
                else:
                    self.finished.emit(False, "Failed to read calibration")
            
            elif self.operation == 'get_ecu_info':
                self.progress.emit(30, "Connecting...")
                if not flasher.connect():
                    self.finished.emit(False, "Failed to connect")
                    return
                
                self.progress.emit(60, "Reading ECU info...")
                info = flasher.get_ecu_info()
                
                if info:
                    result = "\n".join([f"{k}: {v}" for k, v in info.items()])
                    self.progress.emit(100, "Info retrieved!")
                    self.finished.emit(True, result)
                else:
                    self.finished.emit(False, "Failed to get ECU info")
            
            else:
                self.finished.emit(False, f"Unknown operation: {self.operation}")
                
        except Exception as e:
            self.log_message.emit(f"Error: {traceback.format_exc()}")
            self.finished.emit(False, str(e))


class DirectCANController:
    """Controller for Direct CAN operations."""
    
    def __init__(self, log_controller: Optional[Any] = None):
        self.log_controller = log_controller
        self.connected = False
        self.unlocked = False
    
    def log(self, message: str):
        if self.log_controller and hasattr(self.log_controller, 'append'):
            self.log_controller.append(message)


class DirectCANWidget(QtWidgets.QWidget):
    """Direct CAN Flash Widget with full ECU communication capabilities."""
    
    def __init__(self, controller: DirectCANController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.worker = None
        self._bg_worker = None
        self._cancel = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("Direct CAN/UDS Flash Interface")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Warning banner
        warning = QtWidgets.QLabel(
            "⚠ ADVANCED DIRECT CAN/UDS\nUse ONLY on bench ECU first. Incorrect usage may brick ECU."
        )
        warning.setStyleSheet("color: #ff6; background: #332; padding: 10px; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Connection settings
        conn_group = QtWidgets.QGroupBox("CAN Interface Settings")
        conn_layout = QtWidgets.QFormLayout(conn_group)
        
        self.interface_combo = QtWidgets.QComboBox()
        self.interface_combo.addItems(['pcan', 'socketcan', 'vector', 'kvaser', 'ixxat'])
        conn_layout.addRow("Interface:", self.interface_combo)
        
        self.channel_edit = QtWidgets.QLineEdit("PCAN_USBBUS1")
        self.channel_edit.setPlaceholderText("e.g., PCAN_USBBUS1, can0, 0")
        conn_layout.addRow("Channel:", self.channel_edit)
        
        # Algorithm selection
        self.algo_combo = QtWidgets.QComboBox()
        self.algo_combo.addItems(['Auto (try all)', 'v1 (MH XOR)', 'v2 (Swap+MH)', 'v3 (BM XOR)'])
        conn_layout.addRow("Security Algorithm:", self.algo_combo)
        
        # Expert mode checkbox (gates unlock/read operations)
        self.expert_check = QtWidgets.QCheckBox("Enable Expert Mode (I understand the risks)")
        self.expert_check.setChecked(False)
        layout.addWidget(self.expert_check)

        layout.addWidget(conn_group)
        
        # Action buttons
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_layout = QtWidgets.QGridLayout(actions_group)
        
        self.connect_btn = QtWidgets.QPushButton("Test Connection")
        self.connect_btn.clicked.connect(self._on_connect)
        actions_layout.addWidget(self.connect_btn, 0, 0)
        
        self.unlock_btn = QtWidgets.QPushButton("Unlock ECU")
        self.unlock_btn.clicked.connect(self._on_unlock)
        actions_layout.addWidget(self.unlock_btn, 0, 1)
        
        self.info_btn = QtWidgets.QPushButton("Get ECU Info")
        self.info_btn.clicked.connect(self._on_get_info)
        actions_layout.addWidget(self.info_btn, 0, 2)
        
        self.backup_btn = QtWidgets.QPushButton("Backup Calibration")
        self.backup_btn.clicked.connect(self._on_backup)
        actions_layout.addWidget(self.backup_btn, 1, 0)
        
        self.read_btn = QtWidgets.QPushButton("Read Memory")
        self.read_btn.clicked.connect(self._on_read_memory)
        actions_layout.addWidget(self.read_btn, 1, 1)
        
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setEnabled(False)
        actions_layout.addWidget(self.cancel_btn, 1, 2)
        
        layout.addWidget(actions_group)
        
        # Memory read settings
        mem_group = QtWidgets.QGroupBox("Memory Read Settings")
        mem_layout = QtWidgets.QFormLayout(mem_group)
        
        self.offset_edit = QtWidgets.QLineEdit("0x000000")
        self.offset_edit.setPlaceholderText("0x000000")
        mem_layout.addRow("Offset (hex):", self.offset_edit)
        
        self.size_spin = QtWidgets.QSpinBox()
        self.size_spin.setRange(1, 1048576)  # Up to 1MB
        self.size_spin.setValue(256)
        self.size_spin.setSuffix(" bytes")
        mem_layout.addRow("Size:", self.size_spin)
        
        layout.addWidget(mem_group)
        
        # Progress
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Log output
        log_group = QtWidgets.QGroupBox("Operation Log")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("font-family: monospace;")
        log_layout.addWidget(self.log_text)
        
        clear_btn = QtWidgets.QPushButton("Clear Log")
        clear_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_btn)
        
        layout.addWidget(log_group)
        
        # Status indicators
        status_group = QtWidgets.QGroupBox("Status")
        status_layout = QtWidgets.QHBoxLayout(status_group)
        
        self.conn_indicator = QtWidgets.QLabel("Disconnected")
        status_layout.addWidget(self.conn_indicator)
        
        self.lock_indicator = QtWidgets.QLabel("Locked")
        status_layout.addWidget(self.lock_indicator)
        
        status_layout.addStretch()
        layout.addWidget(status_group)
        
        layout.addStretch()
    
    def _get_params(self) -> Dict[str, Any]:
        algo_map = {
            'Auto (try all)': None,
            'v1 (MH XOR)': 'v1',
            'v2 (Swap+MH)': 'v2',
            'v3 (BM XOR)': 'v3'
        }
        return {
            'interface': self.interface_combo.currentText(),
            'channel': self.channel_edit.text().strip(),
            'algorithm': algo_map.get(self.algo_combo.currentText())
        }
    
    def _start_operation(self, operation: str, params: Dict[str, Any]):
        # Prefer standardized Worker; fall back to legacy QThread if unavailable
        if Worker is None or CancelToken is None:
            if self.worker and self.worker.isRunning():
                return
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.cancel_btn.setEnabled(True)
            self._set_buttons_enabled(False)
            self.worker = DirectCANWorker(operation, params)
            self.worker.progress.connect(self._on_progress)
            self.worker.finished.connect(self._on_finished)
            self.worker.log_message.connect(self._on_log)
            self.worker.start()
            return

        # Gate dangerous operations behind expert mode
        if operation in ('unlock', 'read_calibration', 'read_memory') and not self.expert_check.isChecked():
            show_warning_message(self, 'Expert Mode Required', 'Enable Expert Mode to perform unlock/backup/memory operations.')
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)
        self._set_buttons_enabled(False)

        self._cancel = CancelToken()

        def task(progress_cb=None, cancel_token=None):
            try:
                from flash_tool.direct_can_flasher import DirectCANFlasher
                flasher = DirectCANFlasher(can_interface=params.get('interface', 'pcan'), can_channel=params.get('channel', 'PCAN_USBBUS1'))

                def emit(msg: str, pct: float):
                    if progress_cb:
                        try:
                            progress_cb(ProgressEvent(progress=pct, message=msg))
                        except Exception:
                            try:
                                progress_cb(msg, pct)
                            except Exception:
                                pass

                if operation == 'connect':
                    emit('Connecting to ECU...', 10)
                    ok = flasher.connect()
                    emit('Connected!' if ok else 'Failed to connect', 100)
                    return {'success': ok, 'message': 'Successfully connected to ECU' if ok else 'Failed to connect to ECU'}

                if operation == 'unlock':
                    emit('Connecting...', 20)
                    if not flasher.connect():
                        return {'success': False, 'error': 'Failed to connect'}
                    emit('Requesting security access...', 40)
                    algorithm = params.get('algorithm', None)
                    ok = flasher.unlock_ecu(algorithm=algorithm) if algorithm else flasher.unlock_ecu(try_all_algorithms=True)
                    emit('ECU Unlocked!' if ok else 'Security access denied', 100)
                    return {'success': ok, 'message': 'Security access granted' if ok else 'Security access denied'}

                if operation == 'read_memory':
                    emit('Connecting...', 20)
                    if not flasher.connect():
                        return {'success': False, 'error': 'Failed to connect'}
                    offset = params.get('offset', 0)
                    size = params.get('size', 256)
                    output_file = params.get('output_file')
                    emit(f'Reading {size} bytes from 0x{offset:06X}...', 40)
                    data = flasher.read_memory(offset, size)
                    if data:
                        if output_file:
                            Path(output_file).write_bytes(data)
                        emit('Read complete!', 100)
                        return {'success': True, 'message': f'Read {len(data)} bytes successfully'}
                    return {'success': False, 'error': 'Failed to read memory'}

                if operation == 'read_calibration':
                    emit('Connecting...', 20)
                    if not flasher.connect():
                        return {'success': False, 'error': 'Failed to connect'}
                    output_file = params.get('output_file', 'calibration_backup.bin')
                    emit('Unlocking ECU...', 30)
                    if not flasher.unlock_ecu(try_all_algorithms=True):
                        return {'success': False, 'error': 'Failed to unlock ECU'}
                    emit('Reading calibration region...', 50)
                    data = flasher.read_calibration_region()
                    if data:
                        Path(output_file).write_bytes(data)
                        emit('Backup complete!', 100)
                        return {'success': True, 'message': f'Calibration backup saved: {output_file}'}
                    return {'success': False, 'error': 'Failed to read calibration'}

                if operation == 'get_ecu_info':
                    emit('Connecting...', 30)
                    if not flasher.connect():
                        return {'success': False, 'error': 'Failed to connect'}
                    emit('Reading ECU info...', 60)
                    info = flasher.get_ecu_info()
                    if info:
                        emit('Info retrieved!', 100)
                        return {'success': True, 'message': "\n".join([f"{k}: {v}" for k, v in info.items()])}
                    return {'success': False, 'error': 'Failed to get ECU info'}

                return {'success': False, 'error': f'Unknown operation: {operation}'}
            except Exception as exc:
                return {'success': False, 'error': str(exc)}

        def on_progress(evt: ProgressEvent):
            try:
                self.progress_bar.setValue(int(evt.progress))
                self.status_label.setText(evt.message)
            except Exception:
                pass

        self._bg_worker = Worker(task=task, args=(), kwargs={}, progress_cb=on_progress, cancel_token=self._cancel)
        self._bg_worker.start()

        def poll():
            if self._bg_worker and self._bg_worker.is_alive():
                QtCore.QTimer.singleShot(200, poll)
                return
            try:
                res = self._bg_worker.result()
            except Exception as e:
                res = {'success': False, 'error': str(e)}
            self._on_finished_worker(res)
        QtCore.QTimer.singleShot(200, poll)
    
    def _set_buttons_enabled(self, enabled: bool):
        self.connect_btn.setEnabled(enabled)
        self.unlock_btn.setEnabled(enabled)
        self.info_btn.setEnabled(enabled)
        self.backup_btn.setEnabled(enabled)
        self.read_btn.setEnabled(enabled)
    
    def _on_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
    
    def _on_finished(self, success: bool, result: str):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self._set_buttons_enabled(True)
        
        if success:
            self.status_label.setText(f"SUCCESS: {result[:100]}")
            self.status_label.setStyleSheet("color: green; padding: 5px;")
            self._on_log(f"SUCCESS: {result}")
            
            # Update indicators
            if "connected" in result.lower():
                self.conn_indicator.setText("Connected")
            if "access granted" in result.lower() or "unlocked" in result.lower():
                self.lock_indicator.setText("Unlocked")
        else:
            self.status_label.setText(f"ERROR: {result[:100]}")
            self.status_label.setStyleSheet("color: red; padding: 5px;")
            self._on_log(f"FAILED: {result}")

    def _on_finished_worker(self, res: Dict[str, Any]):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self._set_buttons_enabled(True)

        success = bool(res.get('success'))
        message = res.get('message') or res.get('error') or 'Operation completed'

        if success:
            self.status_label.setText(f"SUCCESS: {str(message)[:100]}")
            self.status_label.setStyleSheet("color: green; padding: 5px;")
            self._on_log(f"SUCCESS: {message}")
            try:
                show_success_message(self, 'Operation Completed', str(message))
            except Exception:
                pass
            # Update indicators
            msg_lc = str(message).lower()
            if "connected" in msg_lc or "successfully connected" in msg_lc:
                self.conn_indicator.setText("Connected")
            if "access granted" in msg_lc or "unlocked" in msg_lc:
                self.lock_indicator.setText("Unlocked")
        else:
            self.status_label.setText(f"ERROR: {str(message)[:100]}")
            self.status_label.setStyleSheet("color: red; padding: 5px;")
            self._on_log(f"FAILED: {message}")
            try:
                show_error_message(self, 'Operation Failed', str(message))
            except Exception:
                pass
    
    def _on_log(self, message: str):
        self.log_text.appendPlainText(message)
        self.controller.log(message)
    
    def _on_cancel(self):
        cancelled = False
        if self.worker:
            try:
                self.worker.cancel()
                cancelled = True
            except Exception:
                pass
        if self._cancel:
            try:
                self._cancel.cancel()
                cancelled = True
            except Exception:
                pass
        if cancelled:
            self._on_log("Operation cancelling...")
            self.status_label.setText("Cancelling...")
    
    def _on_connect(self):
        params = self._get_params()
        self._on_log(f"Testing connection to {params['interface']}:{params['channel']}...")
        self._start_operation('connect', params)
    
    def _on_unlock(self):
        params = self._get_params()
        algo = params.get('algorithm') or 'auto'
        self._on_log(f"Attempting ECU unlock with algorithm: {algo}...")
        self._start_operation('unlock', params)
    
    def _on_get_info(self):
        params = self._get_params()
        self._on_log("Requesting ECU information...")
        self._start_operation('get_ecu_info', params)
    
    def _on_backup(self):
        params = self._get_params()
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Calibration Backup", "calibration_backup.bin",
            "Binary Files (*.bin);;All Files (*)"
        )
        if not filename:
            return
        
        params['output_file'] = filename
        self._on_log(f"Starting calibration backup to {filename}...")
        self._start_operation('read_calibration', params)
    
    def _on_read_memory(self):
        params = self._get_params()
        
        # Parse offset
        offset_text = self.offset_edit.text().strip()
        try:
            if offset_text.startswith('0x'):
                offset = int(offset_text, 16)
            else:
                offset = int(offset_text)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid Offset", "Please enter a valid hex offset (e.g., 0x057B58)")
            return
        
        params['offset'] = offset
        params['size'] = self.size_spin.value()
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Memory Dump", f"memory_0x{offset:06X}.bin",
            "Binary Files (*.bin);;All Files (*)"
        )
        if filename:
            params['output_file'] = filename
        
        self._on_log(f"Reading {params['size']} bytes from 0x{offset:06X}...")
        self._start_operation('read_memory', params)


def create_qt_widget(controller: Optional[DirectCANController] = None, parent=None):
    if controller is None:
        controller = DirectCANController()
    return DirectCANWidget(controller, parent)
