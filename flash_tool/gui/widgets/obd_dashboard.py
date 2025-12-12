"""OBD Dashboard controller and lazy Qt widget.

Provides a testable, Qt-free `OBDController` that wraps `flash_tool.obd_reader`
APIs, and a `create_qt_widget(controller, parent=None)` function that builds
the corresponding Qt widget when bindings are available.

The controller methods return simple dicts for success/error to make unit
testing straightforward without Qt.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import time
import traceback

from flash_tool.gui.worker import Worker, CancelToken
from flash_tool import obd_session_manager
from flash_tool import obd_reader as _obd


class OBDController:
    """Framework-agnostic controller for OBD diagnostics.

    Methods return dicts like {'success': True, 'data': ...} or
    {'success': False, 'error': '...'} for easy consumption by the GUI.
    """

    def __init__(self, obd_module: Optional[Any] = None, log_controller: Optional[Any] = None):
        # Dependency injection for tests
        if obd_module is None:
            try:
                from flash_tool import obd_reader as _o

                obd_module = _o
            except Exception:
                obd_module = None

        self.obd = obd_module
        self.log_controller = log_controller
        self._connection = None

    # ------------------------- Connection management -------------------------
    def connect(self, port: Optional[str] = None, baudrate: int = 38400) -> Dict[str, Any]:
        try:
            if self.obd is None:
                return {'success': False, 'error': 'obd module not available'}

            # Use shared session manager so connection can be reused elsewhere.
            # For tests, `self.obd` may be a stub that does not integrate with
            # the session manager; in that case we fall back to direct usage
            # of the provided module.
            try:
                session = obd_session_manager.get_session()
            except Exception:
                session = None

            if session is not None and hasattr(self.obd, 'connect_obd') and self.obd is _obd:
                # Real obd_reader module: let the session own the connection.
                use_port = port or session.get_current_port() or ''
                if not use_port:
                    conn = self.obd.connect_obd(None, baudrate)
                else:
                    conn = session.get_connection(use_port, baudrate)
            else:
                # Stub or custom module in tests: call directly.
                conn = self.obd.connect_obd(port, baudrate)

            self._connection = conn
            port_name = getattr(conn, 'port_name', lambda: str(conn))()
            return {'success': True, 'port': port_name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def disconnect(self) -> Dict[str, Any]:
        try:
            if self._connection and self.obd is not None:
                try:
                    session = obd_session_manager.get_session()
                    session.disconnect()
                except Exception:
                    # Fall back to direct disconnect if session manager fails
                    try:
                        self.obd.disconnect_obd(self._connection)
                    except Exception:
                        pass
            self._connection = None
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ----------------------------- Diagnostic API ----------------------------
    def read_dtcs(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            dtcs = self.obd.read_obd_dtcs(self._connection)
            return {'success': True, 'data': dtcs}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_pending_dtcs(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            dtcs = self.obd.read_pending_dtcs(self._connection)
            return {'success': True, 'data': dtcs}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def filter_dtcs_by_status(self, status: str) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            status_lower = (status or 'all').lower()
            base_dtcs = self.obd.read_obd_dtcs(self._connection)
            try:
                filtered = self.obd.filter_dtcs_by_status(base_dtcs, status_lower)
            except Exception:
                filtered = base_dtcs
            return {'success': True, 'data': filtered, 'status': status_lower}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def clear_dtcs(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            ok = self.obd.clear_obd_dtcs(self._connection)
            return {'success': True, 'cleared': bool(ok)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_vehicle_info(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            info = self.obd.get_vehicle_info(self._connection)
            return {'success': True, 'data': info}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_extended_vehicle_info(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            info = self.obd.expand_vehicle_info(self._connection)
            return {'success': True, 'data': info}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_engine_type(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            engine = self.obd.get_engine_type(self._connection)
            return {'success': True, 'data': engine}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_ecu_reset_status(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            status = self.obd.get_ecu_reset_status(self._connection)
            return {'success': True, 'data': status}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_mil_history(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            history = self.obd.read_mil_history(self._connection)
            return {'success': True, 'data': history}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_component_tests(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            results = self.obd.read_component_test_results(self._connection)
            ok = results.get('success', True) if isinstance(results, dict) else True
            return {'success': bool(ok), 'data': results}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_supported_pids(self, mode: int = 0x01, start_pid: int = 0x00) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            pids = self.obd.read_supported_pids(self._connection, mode=mode, start_pid=start_pid)
            return {'success': True, 'data': pids}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def query_readiness(self) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            res = self.obd.query_readiness_monitors(self._connection)
            return {'success': True, 'data': res}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_pids(self, pid_ids: List[str]) -> Dict[str, Any]:
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            data = self.obd.read_pid_data(pid_ids, connection=self._connection)
            return {'success': True, 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_all_module_dtcs(self, protocol: str = 'CAN') -> Dict[str, Any]:
        try:
            # This may create a temporary UDS client internally
            res = self.obd.read_all_module_dtcs(protocol=protocol)
            return {'success': True, 'data': res}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def read_freeze_frame(self) -> Dict[str, Any]:
        """Read freeze frame data via the OBD reader.

        Uses the existing `obd_reader.read_freeze_frame` implementation
        against the active OBD connection. Returns a dict with either
        `{'success': True, 'data': {...}}` or an error message.
        """
        try:
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            if self.obd is None:
                return {'success': False, 'error': 'obd module not available'}
            data = self.obd.read_freeze_frame(self._connection)
            return {'success': True, 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def _format_dtcs_list(dtcs: List[Dict[str, Any]]) -> str:
    if not dtcs:
        return 'No DTCs found.'
    lines = []
    for d in dtcs:
        code = d.get('code', '??')
        desc = d.get('description', '')
        status = []
        if d.get('pending'):
            status.append('PENDING')
        if d.get('confirmed'):
            status.append('CONFIRMED')
        if d.get('active'):
            status.append('ACTIVE')
        lines.append(f"{code:8} | {', '.join(status) or 'STORED':10} | {desc}")
    return "\n".join(lines)


def create_qt_widget(controller: OBDController, parent: Optional[Any] = None):
    try:
        from PySide6 import QtWidgets, QtCore
    except Exception:
        try:
            from PyQt5 import QtWidgets, QtCore
        except Exception as exc:
            raise ImportError('Qt bindings not available for OBD Dashboard') from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._worker: Optional[Worker] = None
            self._cancel_token: Optional[CancelToken] = None

            layout = QtWidgets.QVBoxLayout(self)

            # Connection row
            conn_h = QtWidgets.QHBoxLayout()
            self.port_edit = QtWidgets.QLineEdit()
            self.port_edit.setPlaceholderText('COM port (e.g., COM3) or leave blank for auto')
            self.baud_edit = QtWidgets.QLineEdit('38400')
            self.connect_btn = QtWidgets.QPushButton('Connect')
            self.reconnect_btn = QtWidgets.QPushButton('Reconnect')
            conn_h.addWidget(self.port_edit)
            conn_h.addWidget(self.baud_edit)
            conn_h.addWidget(self.connect_btn)
            conn_h.addWidget(self.reconnect_btn)
            layout.addLayout(conn_h)

            # Action buttons
            btn_h = QtWidgets.QHBoxLayout()
            self.read_dtcs_btn = QtWidgets.QPushButton('Read DTCs')
            self.clear_dtcs_btn = QtWidgets.QPushButton('Clear DTCs')
            self.vehicle_info_btn = QtWidgets.QPushButton('Vehicle Info')
            self.freeze_btn = QtWidgets.QPushButton('Freeze Frame')
            self.readiness_btn = QtWidgets.QPushButton('Query Readiness')
            self.scan_all_btn = QtWidgets.QPushButton('Scan All Modules')
            btn_h.addWidget(self.read_dtcs_btn)
            btn_h.addWidget(self.clear_dtcs_btn)
            btn_h.addWidget(self.vehicle_info_btn)
            btn_h.addWidget(self.freeze_btn)
            btn_h.addWidget(self.readiness_btn)
            btn_h.addWidget(self.scan_all_btn)
            layout.addLayout(btn_h)

            # Advanced diagnostics
            adv_h1 = QtWidgets.QHBoxLayout()
            self.pending_dtcs_btn = QtWidgets.QPushButton('Pending DTCs')
            self.status_filter = QtWidgets.QComboBox()
            self.status_filter.addItems(['all', 'pending', 'confirmed', 'active', 'stored'])
            self.filter_dtcs_btn = QtWidgets.QPushButton('Filter DTCs')
            self.ext_info_btn = QtWidgets.QPushButton('Extended Info')
            self.engine_type_btn = QtWidgets.QPushButton('Engine Type')
            adv_h1.addWidget(self.pending_dtcs_btn)
            adv_h1.addWidget(self.status_filter)
            adv_h1.addWidget(self.filter_dtcs_btn)
            adv_h1.addWidget(self.ext_info_btn)
            adv_h1.addWidget(self.engine_type_btn)
            layout.addLayout(adv_h1)

            adv_h2 = QtWidgets.QHBoxLayout()
            self.reset_status_btn = QtWidgets.QPushButton('ECU Reset Status')
            self.mil_history_btn = QtWidgets.QPushButton('MIL History')
            self.component_tests_btn = QtWidgets.QPushButton('Component Tests')
            self.supported_pids_btn = QtWidgets.QPushButton('Supported PIDs')
            adv_h2.addWidget(self.reset_status_btn)
            adv_h2.addWidget(self.mil_history_btn)
            adv_h2.addWidget(self.component_tests_btn)
            adv_h2.addWidget(self.supported_pids_btn)
            layout.addLayout(adv_h2)

            # Live data row
            live_h = QtWidgets.QHBoxLayout()
            self.pids_edit = QtWidgets.QLineEdit('0C,0D,BOOST_ACTUAL')
            self.poll_interval = QtWidgets.QSpinBox()
            self.poll_interval.setRange(100, 5000)
            self.poll_interval.setValue(500)
            self.poll_interval.setSuffix(' ms')
            self.poll_btn = QtWidgets.QPushButton('Start Poll')
            live_h.addWidget(self.pids_edit)
            live_h.addWidget(self.poll_interval)
            live_h.addWidget(self.poll_btn)
            layout.addLayout(live_h)

            # Output view
            self.output = QtWidgets.QPlainTextEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)

            # Hook up signals
            self.connect_btn.clicked.connect(self._on_connect)
            self.reconnect_btn.clicked.connect(self._on_reconnect)
            self.read_dtcs_btn.clicked.connect(self._on_read_dtcs)
            self.clear_dtcs_btn.clicked.connect(self._on_clear_dtcs)
            self.vehicle_info_btn.clicked.connect(self._on_vehicle_info)
            self.freeze_btn.clicked.connect(self._on_freeze_frame)
            self.readiness_btn.clicked.connect(self._on_readiness)
            self.scan_all_btn.clicked.connect(self._on_scan_all)
            self.pending_dtcs_btn.clicked.connect(self._on_read_pending_dtcs)
            self.filter_dtcs_btn.clicked.connect(self._on_filter_dtcs)
            self.ext_info_btn.clicked.connect(self._on_extended_vehicle_info)
            self.engine_type_btn.clicked.connect(self._on_engine_type)
            self.reset_status_btn.clicked.connect(self._on_reset_status)
            self.mil_history_btn.clicked.connect(self._on_mil_history)
            self.component_tests_btn.clicked.connect(self._on_component_tests)
            self.supported_pids_btn.clicked.connect(self._on_supported_pids)
            self.poll_btn.clicked.connect(self._on_toggle_poll)

        def _append(self, text: str):
            try:
                ts = QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate)
                self.output.appendPlainText(f"[{ts}] {text}")
            except Exception:
                try:
                    self.output.appendPlainText(str(text))
                except Exception:
                    pass

        def _on_connect(self):
            port = self.port_edit.text().strip() or None
            try:
                baud = int(self.baud_edit.text().strip())
            except Exception:
                baud = 38400

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.connect(port, baud)

            def ui_progress(evt):
                # Connection is quick; ignore progress events
                pass

            self._run_worker(task, ui_progress, on_done=self._connect_done)

        def _connect_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                port = result.get('port', '')
                self._append(f"Connected: {port}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Connect failed: {err}")

        def _on_reconnect(self):
            """Disconnect and reconnect with current settings."""
            self._append("Reconnecting...")
            self._ctrl.disconnect()
            self._on_connect()

        def _on_read_dtcs(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_dtcs()

            def ui_progress(evt):
                # brief progress; show message
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._read_dtcs_done)

        def _read_dtcs_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                dtcs = result.get('data') or []
                self._append(_format_dtcs_list(dtcs))
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Read DTCs failed: {err}")

        def _on_read_pending_dtcs(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_pending_dtcs()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._pending_dtcs_done)

        def _pending_dtcs_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                dtcs = result.get('data') or []
                if not dtcs:
                    self._append('No pending DTCs found.')
                    return
                self._append('Pending DTCs:')
                self._append(_format_dtcs_list(dtcs))
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Pending DTCs failed: {err}")

        def _on_filter_dtcs(self):
            status = (self.status_filter.currentText() or 'all').lower()

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.filter_dtcs_by_status(status)

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._filter_dtcs_done)

        def _filter_dtcs_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                dtcs = result.get('data') or []
                status = result.get('status', 'all')
                self._append(f"Filtered DTCs ({status}):")
                self._append(_format_dtcs_list(dtcs))
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Filter DTCs failed: {err}")

        def _on_clear_dtcs(self):
            # explicit typed confirmation
            text, ok = QtWidgets.QInputDialog.getText(self, 'Confirm Clear', 'Type CLEAR to confirm clearing DTCs:')
            if not ok or (text or '').strip() != 'CLEAR':
                self._append('Clear DTCs cancelled by user')
                return

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.clear_dtcs()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._clear_done)

        def _clear_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                self._append(f"Clear DTCs: {result.get('cleared')}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Clear DTCs failed: {err}")

        def _on_vehicle_info(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.get_vehicle_info()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._vehicle_info_done)

        def _vehicle_info_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                info = result.get('data') or {}
                lines = [f"{k}: {v}" for k, v in sorted(info.items())]
                self._append('\n'.join(lines))
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Vehicle info failed: {err}")

        def _on_extended_vehicle_info(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.get_extended_vehicle_info()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._extended_vehicle_info_done)

        def _extended_vehicle_info_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                info = result.get('data') or {}
                lines = [f"{k}: {v}" for k, v in sorted(info.items())]
                self._append('Extended vehicle info:')
                self._append('\n'.join(lines))
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Extended info failed: {err}")

        def _on_engine_type(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.get_engine_type()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._engine_type_done)

        def _engine_type_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                engine = result.get('data', 'Unknown')
                self._append(f"Engine type: {engine}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Engine type failed: {err}")

        def _on_readiness(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.query_readiness()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._readiness_done)

        def _readiness_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                data = result.get('data') or {}
                # Pretty-print a subset
                readiness_byte = data.get('readiness_byte')
                all_ready = data.get('all_ready')
                dtc_count = data.get('dtc_count')
                self._append(f"Readiness: byte=0x{(readiness_byte or 0):02X}, all_ready={all_ready}, dtc_count={dtc_count}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Readiness failed: {err}")

        def _on_reset_status(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.get_ecu_reset_status()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._reset_status_done)

        def _reset_status_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                status = result.get('data') or {}
                runtime = status.get('runtime_seconds', 0)
                mil_cycles = status.get('mil_cycles', 0)
                clear_cycles = status.get('clear_cycles', 0)
                self._append(f"ECU reset detected: {status.get('reset_detected')} | runtime: {runtime}s | mil_cycles: {mil_cycles} | clear_cycles: {clear_cycles}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"ECU reset status failed: {err}")

        def _on_mil_history(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_mil_history()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._mil_history_done)

        def _mil_history_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                history = result.get('data') or {}
                self._append(f"MIL ON: {history.get('mil_on')} | DTC count: {history.get('dtc_count')} | distance: {history.get('mil_distance')} km | time: {history.get('mil_time')} min")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"MIL history failed: {err}")

        def _on_scan_all(self):
            def task(progress_cb=None, cancel_token=None):
                # Delegate to multi-module scan (may be longer running)
                return self._ctrl.read_all_module_dtcs(protocol='CAN')

            def ui_progress(evt):
                # evt is ProgressEvent
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._scan_all_done)

        def _scan_all_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                data = result.get('data') or {}
                # format using existing helper from obd_reader if available
                try:
                    from flash_tool.obd_reader import format_dtc_report

                    # If the module-level helper exists, use it
                    report = format_dtc_report(data)
                    self._append(report)
                    return
                except Exception:
                    pass

                # Fallback: simple count summary
                counts = {m: len(v) for m, v in data.items()}
                self._append(f"Modules scanned: {len(counts)}, dtc totals: {counts}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Module scan failed: {err}")

        def _on_component_tests(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_component_tests()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._component_tests_done)

        def _component_tests_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                data = result.get('data') or {}
                tests = data.get('tests', {}) if isinstance(data, dict) else {}
                note = data.get('note') if isinstance(data, dict) else None
                if tests:
                    self._append('Component test results:')
                    for name, values in tests.items():
                        current = values.get('current')
                        min_v = values.get('min')
                        max_v = values.get('max')
                        self._append(f"  {name}: current={current}, min={min_v}, max={max_v}")
                elif note:
                    self._append(note)
                else:
                    self._append('No component test data returned.')
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Component tests failed: {err}")

        def _on_supported_pids(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_supported_pids()

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._supported_pids_done)

        def _supported_pids_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                pids = result.get('data') or []
                if not pids:
                    self._append('No supported PIDs returned.')
                    return
                self._append(f"Supported PIDs ({len(pids)}): {', '.join(pids)}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Supported PIDs failed: {err}")

        def _on_freeze_frame(self):
            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.read_freeze_frame()

            def ui_progress(evt):
                # Freeze frame is a quick, single-shot read; ignore progress.
                self._append(getattr(evt, 'message', str(evt)))

            self._run_worker(task, ui_progress, on_done=self._freeze_done)

        def _freeze_done(self, result):
            if isinstance(result, dict) and result.get('success'):
                data = result.get('data') or {}
                if not data:
                    self._append('No freeze frame data available.')
                    return
                self._append('Freeze frame data:')
                for key, value in data.items():
                    self._append(f"  {key}: {value}")
            else:
                err = result.get('error') if isinstance(result, dict) else str(result)
                self._append(f"Freeze frame read failed: {err}")

        def _on_toggle_poll(self):
            if self._worker and self._worker.is_alive():
                # stop polling
                if self._cancel_token:
                    self._cancel_token.request_cancel()
                self._append('Stopping poll...')
                self.poll_btn.setText('Start Poll')
                return

            # start polling
            pid_text = self.pids_edit.text().strip()
            pid_list = [p.strip() for p in pid_text.split(',') if p.strip()]
            interval_ms = int(self.poll_interval.value())

            def polling_task(progress_cb=None, cancel_token=None):
                try:
                    while not (cancel_token and cancel_token.is_cancelled()):
                        try:
                            res = self._ctrl.read_pids(pid_list)
                            if res.get('success'):
                                data = res.get('data') or {}
                                # create compact display
                                parts = []
                                for pid_id, v in data.items():
                                    name = v.get('name', pid_id)
                                    val = v.get('value')
                                    unit = v.get('unit', '')
                                    parts.append(f"{name}:{val}{unit}")
                                msg = ' | '.join(parts)
                                progress_cb(0.0, msg)
                            else:
                                progress_cb(0.0, 'PID read error: ' + str(res.get('error')))
                        except Exception as e:
                            progress_cb(0.0, 'PID poll exception: ' + str(e))
                        time.sleep(interval_ms / 1000.0)
                    return {'success': True, 'stopped': True}
                except Exception as e:
                    return {'success': False, 'error': str(e), 'trace': traceback.format_exc()}

            def ui_progress(evt):
                self._append(getattr(evt, 'message', str(evt)))

            # create cancel token and worker
            self._cancel_token = CancelToken()
            worker = Worker(task=polling_task, progress_cb=ui_progress, cancel_token=self._cancel_token)
            self._worker = worker
            worker.start()
            self.poll_btn.setText('Stop Poll')

            # monitor worker and reset UI when it ends
            def poll_monitor():
                if self._worker and self._worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll_monitor)
                    return
                self._append('Poll stopped')
                self.poll_btn.setText('Start Poll')
                self._worker = None
                self._cancel_token = None

            QtCore.QTimer.singleShot(200, poll_monitor)

        # -------------------- Worker helpers & lifecycle --------------------
        def _run_worker(self, task_callable, progress_cb, on_done=None):
            # stop any existing worker first
            if getattr(self, '_worker', None) and self._worker.is_alive():
                try:
                    if getattr(self, '_cancel_token', None):
                        self._cancel_token.request_cancel()
                except Exception:
                    pass

            # prepare worker
            self._cancel_token = CancelToken()
            worker = Worker(task=task_callable, progress_cb=progress_cb, cancel_token=self._cancel_token)
            self._worker = worker
            try:
                worker.start()
            except Exception as e:
                self._append(f'Failed to start task: {e}')
                return

            # poll for completion and invoke callback
            def _poll_done():
                if worker.is_alive():
                    QtCore.QTimer.singleShot(200, _poll_done)
                    return

                try:
                    res = worker.result()
                except Exception as e:
                    res = {'success': False, 'error': str(e)}

                # cleanup
                try:
                    self._cancel_token = None
                except Exception:
                    pass
                self._worker = None

                try:
                    if on_done:
                        on_done(res)
                except Exception:
                    self._append('on_done handler error: ' + traceback.format_exc())

            QtCore.QTimer.singleShot(200, _poll_done)

    return _Widget(parent)
