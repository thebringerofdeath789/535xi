"""Coding Controller and lazy Qt widget.

Provides a framework-agnostic `CodingController` that wraps `flash_tool.dme_handler`
APIs for DME-specific functions (identification, errors, boost/VANOS data, VIN memory reads,
flash counter operations). Also provides a `create_qt_widget` to display and invoke these
operations in the GUI.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List
import traceback
import time

from flash_tool.gui.worker import Worker, CancelToken


class CodingController:
    def __init__(self, dme_module: Optional[Any] = None, log_controller: Optional[Any] = None):
        if dme_module is None:
            try:
                from flash_tool import dme_handler as _d
                dme_module = _d
            except Exception:
                dme_module = None
        self.dme = dme_module
        self.log_controller = log_controller

    def get_identification(self) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            res = self.dme.read_ecu_identification()
            return {'success': True, 'data': res}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_dme_errors(self) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            res = self.dme.read_dme_errors()
            return {'success': True, 'data': res}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def clear_dme_errors(self) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            ok = self.dme.clear_dme_errors()
            return {'success': True, 'cleared': bool(ok)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_vin_from_memory(self) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            vin = self.dme.read_vin_from_memory()
            return {'success': True, 'vin': vin}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_flash_counter(self) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            cnt = self.dme.read_flash_counter_from_memory()
            return {'success': True, 'counter': cnt}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def reset_flash_counter(self, value: int = 0) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            ok = self.dme.reset_flash_counter(value=value, backup=True)
            return {'success': True, 'ok': bool(ok)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_immo_status(self) -> Dict[str, Any]:
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            st = self.dme.check_immo_status()
            return {'success': True, 'data': st}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_available_modules(self) -> List[str]:
        """Return a list of available module names for coding operations.

        Tries several dme handler entrypoints and falls back to a sensible
        default list when discovery isn't available.
        """
        defaults = ['DME', 'ABS', 'EGS', 'TCU', 'CAS']
        try:
            if self.dme is None:
                return defaults
            if hasattr(self.dme, 'list_modules'):
                mods = self.dme.list_modules()
            elif hasattr(self.dme, 'get_available_modules'):
                mods = self.dme.get_available_modules()
            elif hasattr(self.dme, 'discover_modules'):
                mods = self.dme.discover_modules()
            else:
                try:
                    ident = getattr(self.dme, 'read_ecu_identification', lambda: {})()
                    if isinstance(ident, dict) and 'modules' in ident:
                        mods = ident.get('modules') or defaults
                    else:
                        mods = defaults
                except Exception:
                    mods = defaults
            # ensure a list of strings
            if not isinstance(mods, (list, tuple)):
                return defaults
            return [str(m) for m in mods]
        except Exception:
            return defaults

    def read_module_coding(self, module: str) -> Dict[str, Any]:
        """Read coding/options for a specified module.
        Tries multiple handler method names for compatibility.
        """
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            if hasattr(self.dme, 'read_module_coding'):
                data = self.dme.read_module_coding(module)
            elif hasattr(self.dme, 'read_coding'):
                data = self.dme.read_coding(module)
            elif hasattr(self.dme, 'read_module_configuration'):
                data = self.dme.read_module_configuration(module)
            else:
                return {'success': False, 'error': 'coding read not implemented in dme handler'}
            return {'success': True, 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def write_module_coding(self, module: str, data: Any, backup: bool = True) -> Dict[str, Any]:
        """Write coding/options to a specified module."""
        try:
            if self.dme is None:
                return {'success': False, 'error': 'dme handler not available'}
            if hasattr(self.dme, 'write_module_coding'):
                ok = self.dme.write_module_coding(module, data, backup=backup)
            elif hasattr(self.dme, 'write_coding'):
                ok = self.dme.write_coding(module, data, backup=backup)
            else:
                return {'success': False, 'error': 'coding write not implemented in dme handler'}
            return {'success': True, 'ok': bool(ok)}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def create_qt_widget(controller: CodingController, parent: Optional[Any] = None):
    try:
        from PySide6 import QtWidgets, QtCore
    except Exception:
        try:
            from PyQt5 import QtWidgets, QtCore
        except Exception as exc:
            raise ImportError('Qt bindings not available for Coding Widget') from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._worker = None
            self._cancel_token = None
            self._coding_enabled = False

            layout = QtWidgets.QVBoxLayout(self)
            
            # =================== SAFETY SECTION ===================
            # Warning banner
            warning_group = QtWidgets.QGroupBox("⚠ ADVANCED CODING OPERATIONS")
            warning_layout = QtWidgets.QVBoxLayout(warning_group)
            warning_text = QtWidgets.QLabel(
                "Coding operations can modify critical ECU parameters.\n"
                "Improper changes may cause:\n"
                "  • Engine malfunction\n"
                "  • Performance loss\n"
                "  • Warranty voidance\n\n"
                "Ensure you have a verified full backup before proceeding."
            )
            warning_text.setStyleSheet("color: #ff6; font-weight: bold;")
            warning_layout.addWidget(warning_text)
            layout.addWidget(warning_group)
            
            # Enable checkbox
            enable_group = QtWidgets.QGroupBox("Enable Coding")
            enable_layout = QtWidgets.QHBoxLayout(enable_group)
            self.enable_check = QtWidgets.QCheckBox("I understand the risks and have a verified backup")
            self.enable_check.stateChanged.connect(self._on_enable_toggled)
            enable_layout.addWidget(self.enable_check)
            layout.addWidget(enable_group)
            
            # =================== OPERATIONS SECTION ===================
            # Buttons row
            btn_h = QtWidgets.QHBoxLayout()
            self.ident_btn = QtWidgets.QPushButton('Read ECU Identification')
            self.errors_btn = QtWidgets.QPushButton('Read DME Errors')
            self.clear_errors_btn = QtWidgets.QPushButton('Clear DME Errors')
            self.vin_read_btn = QtWidgets.QPushButton('Read VIN (Flash)')
            self.flash_counter_btn = QtWidgets.QPushButton('Read Flash Counter')
            self.reset_counter_btn = QtWidgets.QPushButton('Reset Flash Counter')
            btn_h.addWidget(self.ident_btn)
            btn_h.addWidget(self.errors_btn)
            btn_h.addWidget(self.clear_errors_btn)
            btn_h.addWidget(self.vin_read_btn)
            btn_h.addWidget(self.flash_counter_btn)
            btn_h.addWidget(self.reset_counter_btn)
            layout.addLayout(btn_h)

            # --- Coding read/write controls ---
            coding_h = QtWidgets.QHBoxLayout()
            # editable combo populated from controller discovery
            self.module_combo = QtWidgets.QComboBox()
            try:
                self.module_combo.setEditable(True)
            except Exception:
                pass
            # Defer module discovery to an explicit user action to avoid
            # attempting ECU/DME access during GUI startup (which can fail
            # when hardware drivers are missing). User may type a module
            # name manually or click Discover to populate the list.
            self.discover_btn = QtWidgets.QPushButton('Discover')
            try:
                self.module_combo.setEditable(True)
            except Exception:
                pass
            # add discover button next to combo
            coding_h.addWidget(self.module_combo)
            coding_h.addWidget(self.discover_btn)
            self.read_code_btn = QtWidgets.QPushButton('Read Coding')
            self.write_code_btn = QtWidgets.QPushButton('Write Coding')
            self.import_code_btn = QtWidgets.QPushButton('Import Coding')
            self.export_code_btn = QtWidgets.QPushButton('Export Coding')
            coding_h.addWidget(self.module_combo)
            coding_h.addWidget(self.read_code_btn)
            coding_h.addWidget(self.write_code_btn)
            coding_h.addWidget(self.import_code_btn)
            coding_h.addWidget(self.export_code_btn)
            layout.addLayout(coding_h)

            # Editor for coding payload (JSON/text)
            self.coding_edit = QtWidgets.QPlainTextEdit()
            self.coding_edit.setPlaceholderText('Coding JSON or text (read from module).')
            layout.addWidget(self.coding_edit)

            self.output = QtWidgets.QPlainTextEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)

            # connect
            self.ident_btn.clicked.connect(self._on_ident)
            self.errors_btn.clicked.connect(self._on_read_errors)
            self.clear_errors_btn.clicked.connect(self._on_clear_errors)
            self.vin_read_btn.clicked.connect(self._on_read_vin)
            self.flash_counter_btn.clicked.connect(self._on_read_flash_counter)
            self.reset_counter_btn.clicked.connect(self._on_reset_counter)
            # coding read/write connections
            self.read_code_btn.clicked.connect(self._on_read_coding)
            self.write_code_btn.clicked.connect(self._on_write_coding)
            self.import_code_btn.clicked.connect(self._on_import_coding)
            self.export_code_btn.clicked.connect(self._on_export_coding)
            # discovery button (lazy discovery to avoid auto-probing hardware)
            try:
                self.discover_btn.clicked.connect(self._on_discover_modules)
            except Exception:
                pass
            
            # Initial state: disable write operations
            self._update_enable_state()

        def _append(self, text: str):
            try:
                ts = QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate)
                self.output.appendPlainText(f"[{ts}] {text}")
            except Exception:
                try:
                    self.output.appendPlainText(str(text))
                except Exception:
                    pass

        def _on_enable_toggled(self):
            """Handle enable checkbox toggle."""
            self._update_enable_state()

        def _update_enable_state(self):
            """Update button enable/disable based on checkbox state."""
            self._coding_enabled = self.enable_check.isChecked()
            # Enable write operations only if checkbox is checked
            self.write_code_btn.setEnabled(self._coding_enabled)
            self.reset_counter_btn.setEnabled(self._coding_enabled)
            self.clear_errors_btn.setEnabled(self._coding_enabled)
            # Read operations are always enabled
            self.ident_btn.setEnabled(True)
            self.errors_btn.setEnabled(True)
            self.vin_read_btn.setEnabled(True)
            self.flash_counter_btn.setEnabled(True)
            self.discover_btn.setEnabled(True)
            self.read_code_btn.setEnabled(True)
            self.import_code_btn.setEnabled(self._coding_enabled)

        def _run_worker(self, task_callable, on_done=None):
            if getattr(self, '_worker', None) and self._worker.is_alive():
                try:
                    if getattr(self, '_cancel_token', None):
                        self._cancel_token.request_cancel()
                except Exception:
                    pass

            self._cancel_token = CancelToken()
            worker = Worker(task=task_callable, progress_cb=lambda evt: self._append(getattr(evt, 'message', str(evt))), cancel_token=self._cancel_token)
            self._worker = worker
            worker.start()

            def poll_done():
                if worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll_done)
                    return
                try:
                    res = worker.result()
                except Exception as e:
                    res = {'success': False, 'error': str(e)}
                if on_done:
                    on_done(res)

            QtCore.QTimer.singleShot(200, poll_done)

        def _on_ident(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.get_identification()
            self._run_worker(task, on_done=self._finish_ident)

        def _finish_ident(self, res):
            if res.get('success'):
                data = res.get('data')
                lines = [f"{k}: {v}" for k, v in sorted(data.items())]
                self._append('\n'.join(lines))
            else:
                self._append('Ident failed: ' + str(res.get('error', 'unknown')))

        def _on_read_errors(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_dme_errors()
            self._run_worker(task, on_done=self._finish_read_errors)

        def _finish_read_errors(self, res):
            if res.get('success'):
                data = res.get('data') or []
                if not data:
                    self._append('No DME errors found')
                    return
                for d in data:
                    self._append(f"{d.get('code')} | {d.get('status')} | {d.get('description')}")
            else:
                self._append('Read DME errors failed: ' + str(res.get('error', 'unknown')))

        def _on_clear_errors(self):
            text, ok = QtWidgets.QInputDialog.getText(self, 'Confirm Clear DME Errors', 'Type CLEAR to confirm:')
            if not ok or (text or '').strip() != 'CLEAR':
                self._append('Clear cancelled')
                return

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.clear_dme_errors()
            self._run_worker(task, on_done=self._finish_clear_errors)

        def _finish_clear_errors(self, res):
            if res.get('success'):
                self._append(f"Cleared: {res.get('cleared')}")
            else:
                self._append('Clear errors failed: ' + str(res.get('error', 'unknown')))

        def _on_read_vin(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_vin_from_memory()
            self._run_worker(task, on_done=self._finish_read_vin)

        def _finish_read_vin(self, res):
            if res.get('success'):
                self._append('VIN: ' + str(res.get('vin')))
            else:
                self._append('Read VIN failed: ' + str(res.get('error', 'unknown')))

        def _on_read_flash_counter(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_flash_counter()
            self._run_worker(task, on_done=self._finish_read_counter)

        def _finish_read_counter(self, res):
            if res.get('success'):
                self._append('Flash counter: ' + str(res.get('counter')))
            else:
                self._append('Read counter failed: ' + str(res.get('error', 'unknown')))

        def _on_reset_counter(self):
            # typed confirmation
            text, ok = QtWidgets.QInputDialog.getText(self, 'Confirm Reset Flash Counter', 'Type RESET to confirm counter reset to 0:')
            if not ok or (text or '').strip() != 'RESET':
                self._append('Reset cancelled')
                return

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.reset_flash_counter(0)
            self._run_worker(task, on_done=self._finish_reset_counter)

        def _finish_reset_counter(self, res):
            if res.get('success'):
                self._append('Reset done: ' + str(res.get('ok')))
            else:
                self._append('Reset failed: ' + str(res.get('error', 'unknown')))

        def _on_read_coding(self):
            try:
                module = self.module_combo.currentText().strip()
            except Exception:
                module = ''
            if not module:
                self._append('No module specified for coding read')
                return
            self._last_requested_module = module
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_module_coding(module)
            self._run_worker(task, on_done=self._finish_read_coding)

        def _on_discover_modules(self):
            # Run discovery in background and populate the combo when done
            self._append('Discovering modules...')

            def task(progress_cb=None, cancel_token=None):
                try:
                    return {'success': True, 'modules': self._ctrl.get_available_modules()}
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            def on_done(res):
                if isinstance(res, dict) and res.get('success'):
                    mods = res.get('modules') or []
                    try:
                        self.module_combo.clear()
                        for m in mods:
                            try:
                                self.module_combo.addItem(str(m))
                            except Exception:
                                pass
                        self._append(f'Discovered {len(mods)} modules')
                    except Exception:
                        self._append('Failed to populate modules list')
                else:
                    err = res.get('error') if isinstance(res, dict) else str(res)
                    self._append('Module discovery failed: ' + (err or 'unknown'))

            # Kick off discovery via the worker abstraction
            self._run_worker(lambda progress_cb=None, cancel_token=None: task(progress_cb, cancel_token), on_done=on_done)

        def _finish_read_coding(self, res):
            if res.get('success'):
                data = res.get('data')
                try:
                    import json
                    pretty = json.dumps(data, indent=2)
                except Exception:
                    pretty = str(data)
                try:
                    self.coding_edit.setPlainText(pretty)
                except Exception:
                    pass
                self._append(f'Read coding for {getattr(self, "_last_requested_module", "?")}: {pretty}')
            else:
                self._append('Read coding failed: ' + str(res.get('error', 'unknown')))

        def _on_write_coding(self):
            try:
                module = self.module_combo.currentText().strip()
            except Exception:
                module = ''
            if not module:
                self._append('No module specified for coding write')
                return
            text = self.coding_edit.toPlainText()
            try:
                import json
                data = json.loads(text)
            except Exception as e:
                self._append('Invalid coding data: ' + str(e))
                return
            self._last_requested_module = module
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.write_module_coding(module, data)
            self._run_worker(task, on_done=self._finish_write_coding)

        def _on_import_coding(self):
            try:
                path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Import coding', '', 'JSON Files (*.json);;All Files (*)')
                if not path:
                    return
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                self.coding_edit.setPlainText(content)
                self._append(f'Imported coding from {path}')
            except Exception as e:
                self._append('Import failed: ' + str(e))

        def _on_export_coding(self):
            try:
                path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export coding', '', 'JSON Files (*.json);;All Files (*)')
                if not path:
                    return
                content = self.coding_edit.toPlainText()
                with open(path, 'w', encoding='utf-8') as fh:
                    fh.write(content)
                self._append(f'Exported coding to {path}')
            except Exception as e:
                self._append('Export failed: ' + str(e))

        def _finish_write_coding(self, res):
            if res.get('success'):
                self._append(f'Write coding success for {getattr(self, "_last_requested_module", "?")}')
            else:
                self._append('Write coding failed: ' + str(res.get('error', 'unknown')))

    return _Widget(parent)
