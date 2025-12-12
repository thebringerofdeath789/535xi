"""OBD Logger controller and lazy Qt widget.

Provides PID selection, live plotting, and CSV logging for OBD/UDS data.

Architecture:
- `OBDLoggerController` is framework-agnostic and manages OBD connection and
  PID queries by delegating to `flash_tool.obd_reader` and `flash_tool.n54_pids`.
- `create_qt_widget(controller, parent=None)` builds a Qt widget (PySide6/PyQt5)
  with:
    - Connection controls (port/baud/connect)
    - PID selection pane with filter and common presets
    - Logging controls (interval, start/stop, Save As, open logs dir)
    - Scrollable live charts area (one plot per selected PID) using pyqtgraph
    - CSV logging with header and ISO timestamps

Notes:
- If pyqtgraph is not available, the widget disables plotting and shows a hint.
- Logging continues until stopped or the window is closed; the CSV is flushed
  every write.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import csv
import os
import time
import datetime
import traceback

try:
    from flash_tool import obd_reader as _obd
    from flash_tool import n54_pids as _pids
except Exception:
    _obd = None
    _pids = None

from flash_tool.gui.worker import Worker, CancelToken
from flash_tool import obd_session_manager


class OBDLoggerController:
    """Controller for OBD logging: connection + PID reads.

    Returns dicts for success/error to keep things testable and decoupled from Qt.
    """

    def __init__(self, obd_module: Optional[Any] = None):
        self.obd = obd_module if obd_module is not None else _obd
        self._connection = None

    # ---------------------- PID catalog helpers ----------------------
    def list_pids(self) -> List[Dict[str, Any]]:
        """Return list of PID dicts with id, name, unit, category."""
        try:
            if _pids is None:
                return []
            out = []
            for pid in _pids.ALL_PIDS:
                out.append({
                    'id': pid.pid,
                    'name': pid.name,
                    'unit': pid.unit,
                    'category': getattr(pid.category, 'value', str(pid.category)),
                    'verified': getattr(pid, 'verified', False),
                    'is_uds': bool(getattr(pid, 'uds_did', None)),
                })
            return out
        except Exception:
            return []

    def common_pid_ids(self) -> List[str]:
        try:
            if _pids is None:
                return []
            return [p.pid for p in _pids.get_common_dashboard_pids()]
        except Exception:
            return []

    # Predefined preset groups for quick selection ---------------------
    def preset_boost_fuel_ids(self) -> List[str]:
        """PIDs for boost and fuel monitoring (including context RPM/load)."""
        ids: List[str] = []
        if _pids is None:
            return ids
        try:
            for pid in _pids.get_boost_monitoring_pids():
                if pid.pid not in ids:
                    ids.append(pid.pid)
            for pid in _pids.get_fuel_monitoring_pids():
                if pid.pid not in ids:
                    ids.append(pid.pid)
            # Add some basics for context
            for name in ("Engine RPM", "Engine Load", "Throttle Position", "Vehicle Speed"):
                pid = _pids.get_pid_by_name(name)
                if pid and pid.pid not in ids:
                    ids.append(pid.pid)
        except Exception:
            pass
        return ids

    def preset_timing_knock_ids(self) -> List[str]:
        """PIDs focused on timing, knock, and VANOS position."""
        ids: List[str] = []
        if _pids is None:
            return ids
        try:
            from flash_tool.n54_pids import PIDCategory  # type: ignore

            for pid in _pids.ALL_PIDS:
                if getattr(pid, "category", None) in (PIDCategory.IGNITION, PIDCategory.VANOS):
                    if pid.pid not in ids:
                        ids.append(pid.pid)
            # Also include RPM and boost actual for timing context
            for name in ("Engine RPM", "Actual Boost Pressure"):
                pid = _pids.get_pid_by_name(name)
                if pid and pid.pid not in ids:
                    ids.append(pid.pid)
        except Exception:
            pass
        return ids

    def preset_engine_basic_ids(self) -> List[str]:
        """Core engine basics: RPM, speed, load, temps, throttle."""
        ids: List[str] = []
        if _pids is None:
            return ids
        try:
            from flash_tool.n54_pids import PIDCategory  # type: ignore

            for pid in _pids.get_pids_by_category(PIDCategory.ENGINE_BASIC):
                if pid.pid not in ids:
                    ids.append(pid.pid)
            # Add intake air temp as a common sensor
            iat = _pids.get_pid_by_name("Intake Air Temperature")
            if iat and iat.pid not in ids:
                ids.append(iat.pid)
        except Exception:
            pass
        return ids

    def preset_emissions_ids(self) -> List[str]:
        """Emissions-focused PIDs (lambda/O2, trims, etc.)."""
        ids: List[str] = []
        if _pids is None:
            return ids
        try:
            from flash_tool.n54_pids import PIDCategory  # type: ignore

            # Lambda/AFR and emissions category
            for pid in _pids.get_pids_by_category(PIDCategory.EMISSIONS):
                if pid.pid not in ids:
                    ids.append(pid.pid)
            # Fuel trims give a lot of emissions insight
            for name in (
                "Short Fuel Trim Bank 1",
                "Long Fuel Trim Bank 1",
                "Short Fuel Trim Bank 2",
                "Long Fuel Trim Bank 2",
            ):
                pid = _pids.get_pid_by_name(name)
                if pid and pid.pid not in ids:
                    ids.append(pid.pid)
        except Exception:
            pass
        return ids

    def preset_knock_safety_ids(self) -> List[str]:
        """PIDs to monitor knock/timing safety plus lambda and trims."""
        ids: List[str] = []
        if _pids is None:
            return ids
        try:
            from flash_tool.n54_pids import PIDCategory  # type: ignore

            # Core ignition/knock and emissions (lambda) categories
            for pid in _pids.get_pids_by_category(PIDCategory.IGNITION):
                if pid.pid not in ids:
                    ids.append(pid.pid)
            for pid in _pids.get_pids_by_category(PIDCategory.EMISSIONS):
                if pid.pid not in ids:
                    ids.append(pid.pid)

            # Add key context sensors
            for name in (
                "Engine RPM",
                "Coolant Temperature",
                "Intake Air Temperature",
                "Actual Boost Pressure",
            ):
                pid = _pids.get_pid_by_name(name)
                if pid and pid.pid not in ids:
                    ids.append(pid.pid)
        except Exception:
            pass
        return ids

    def preset_all_pids_ids(self) -> List[str]:
        """All defined PIDs (OBD + N54-specific).

        Useful for quick, exhaustive logging when desired.
        """
        if _pids is None:
            return []
        try:
            return [pid.pid for pid in _pids.ALL_PIDS]
        except Exception:
            return []

    # ------------------------- Connection API ------------------------
    def connect(self, port: Optional[str] = None, baudrate: int = 38400) -> Dict[str, Any]:
        try:
            if self.obd is None:
                return {'success': False, 'error': 'obd module not available'}
            session = obd_session_manager.get_session()

            # If no explicit port provided, try to reuse any active connection
            use_port = port or session.get_current_port() or ''
            if not use_port:
                conn = self.obd.connect_obd(None, baudrate)
            else:
                conn = session.get_connection(use_port, baudrate)

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
                    try:
                        self.obd.disconnect_obd(self._connection)
                    except Exception:
                        pass
            self._connection = None
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ------------------------ Live data queries ----------------------
    def read_pids(self, pid_ids: List[str]) -> Dict[str, Any]:
        try:
            if not self._connection:
                # Try to attach to any active shared session
                try:
                    session = obd_session_manager.get_session()
                    if session.is_connected():
                        from flash_tool.obd_session_manager import get_active_connection  # type: ignore

                        conn = get_active_connection()
                        if conn is not None:
                            self._connection = conn
                except Exception:
                    pass
            if not self._connection:
                return {'success': False, 'error': 'not connected'}
            data = self.obd.read_pid_data(pid_ids, connection=self._connection)
            return {'success': True, 'data': data}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_connection_status(self) -> Dict[str, Any]:
        """Lightweight status query used by GUI to sync labels.

        Checks the shared OBD session first and attaches to it if active.
        """
        try:
            if self.obd is None:
                return {'connected': False, 'port': None}

            session = obd_session_manager.get_session()
            if session.is_connected():
                try:
                    from flash_tool.obd_session_manager import get_active_connection  # type: ignore

                    conn = get_active_connection()
                except Exception:
                    conn = None
                if conn is not None:
                    self._connection = conn
                    port_name = getattr(conn, 'port_name', lambda: str(conn))()
                    return {'connected': True, 'port': port_name}
            return {'connected': False, 'port': None}
        except Exception:
            return {'connected': False, 'port': None}


def create_qt_widget(controller: OBDLoggerController, parent: Optional[Any] = None):
    try:
        from PySide6 import QtWidgets, QtCore
    except Exception:
        try:
            from PyQt5 import QtWidgets, QtCore
        except Exception as exc:
            raise ImportError('Qt bindings not available for OBD Logger') from exc

    # Optional plotting
    try:
        import pyqtgraph as pg
    except Exception:
        pg = None

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._worker: Optional[Worker] = None
            self._cancel: Optional[CancelToken] = None

            # CSV state
            self._csv_path: Optional[str] = None
            self._csv_file = None
            self._csv_writer: Optional[csv.writer] = None
            self._csv_header_written = False
            self._selected_pid_ids: List[str] = []

            root = QtWidgets.QVBoxLayout(self)

            # Container for connection + PID/control widgets so they can be
            # collapsed while logging to give charts maximum space.
            self._controls_container = QtWidgets.QWidget(self)
            controls_layout = QtWidgets.QVBoxLayout(self._controls_container)
            controls_layout.setContentsMargins(0, 0, 0, 0)

            # Connection row
            conn_h = QtWidgets.QHBoxLayout()
            self.port_edit = QtWidgets.QLineEdit()
            self.port_edit.setPlaceholderText('COM port (e.g., COM3) or blank for auto')
            self.baud_edit = QtWidgets.QLineEdit('38400')
            self.connect_btn = QtWidgets.QPushButton('Connect')
            self.status_lbl = QtWidgets.QLabel('Disconnected')
            conn_h.addWidget(self.port_edit)
            conn_h.addWidget(self.baud_edit)
            conn_h.addWidget(self.connect_btn)
            conn_h.addWidget(self.status_lbl)
            controls_layout.addLayout(conn_h)

            # PID selection + controls
            top_split = QtWidgets.QHBoxLayout()

            # Left: PID list with filter and presets
            left_col = QtWidgets.QVBoxLayout()
            filter_h = QtWidgets.QHBoxLayout()
            self.filter_edit = QtWidgets.QLineEdit()
            self.filter_edit.setPlaceholderText('Filter PIDs by name or id...')
            self.clear_filter_btn = QtWidgets.QPushButton('Clear')
            filter_h.addWidget(self.filter_edit)
            filter_h.addWidget(self.clear_filter_btn)
            left_col.addLayout(filter_h)

            self.pid_list = QtWidgets.QListWidget()
            self.pid_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
            left_col.addWidget(self.pid_list)

            preset_h = QtWidgets.QHBoxLayout()
            self.preset_common_btn = QtWidgets.QPushButton('Select Common')
            self.preset_none_btn = QtWidgets.QPushButton('Select None')
            preset_h.addWidget(self.preset_common_btn)
            preset_h.addWidget(self.preset_none_btn)
            left_col.addLayout(preset_h)

            # Additional preset rows for specific monitoring focuses
            preset2_h = QtWidgets.QHBoxLayout()
            self.preset_boost_btn = QtWidgets.QPushButton('Boost/Fuel')
            self.preset_timing_btn = QtWidgets.QPushButton('Timing/Knock')
            preset2_h.addWidget(self.preset_boost_btn)
            preset2_h.addWidget(self.preset_timing_btn)
            left_col.addLayout(preset2_h)

            preset3_h = QtWidgets.QHBoxLayout()
            self.preset_engine_btn = QtWidgets.QPushButton('Engine Basics')
            self.preset_emissions_btn = QtWidgets.QPushButton('Emissions')
            preset3_h.addWidget(self.preset_engine_btn)
            preset3_h.addWidget(self.preset_emissions_btn)
            left_col.addLayout(preset3_h)

            preset4_h = QtWidgets.QHBoxLayout()
            self.preset_knock_btn = QtWidgets.QPushButton('Knock Safety')
            self.preset_all_btn = QtWidgets.QPushButton('All PIDs')
            preset4_h.addWidget(self.preset_knock_btn)
            preset4_h.addWidget(self.preset_all_btn)
            left_col.addLayout(preset4_h)

            top_split.addLayout(left_col, 1)

            # Right: Logging controls
            right_col = QtWidgets.QVBoxLayout()
            form = QtWidgets.QFormLayout()
            self.interval_spin = QtWidgets.QSpinBox()
            self.interval_spin.setRange(50, 5000)
            self.interval_spin.setValue(200)
            self.interval_spin.setSuffix(' ms')
            form.addRow('Interval:', self.interval_spin)

            self.duration_spin = QtWidgets.QSpinBox()
            self.duration_spin.setRange(0, 24 * 3600 * 1000)
            self.duration_spin.setValue(0)
            self.duration_spin.setSuffix(' ms (0=until stop)')
            form.addRow('Duration:', self.duration_spin)

            file_h = QtWidgets.QHBoxLayout()
            self.file_edit = QtWidgets.QLineEdit()
            self.file_btn = QtWidgets.QPushButton('Save As...')
            file_h.addWidget(self.file_edit)
            file_h.addWidget(self.file_btn)
            form.addRow('Log File:', file_h)

            self.start_btn = QtWidgets.QPushButton('Start Logging')
            self.load_log_btn = QtWidgets.QPushButton('Load Log in Viewer')
            self.open_logs_btn = QtWidgets.QPushButton('Open Logs Folder')
            right_col.addLayout(form)
            right_col.addWidget(self.start_btn)
            right_col.addWidget(self.load_log_btn)
            right_col.addWidget(self.open_logs_btn)

            top_split.addLayout(right_col, 0)
            controls_layout.addLayout(top_split)

            root.addWidget(self._controls_container)

            # Charts area
            charts_group = QtWidgets.QGroupBox('Live Charts')
            charts_v = QtWidgets.QVBoxLayout(charts_group)

            self.scroll = QtWidgets.QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.scroll_content = QtWidgets.QWidget()
            self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_content)
            self.scroll_layout.setSpacing(8)
            self.scroll_layout.setContentsMargins(4, 4, 4, 4)
            self.scroll.setWidget(self.scroll_content)
            charts_v.addWidget(self.scroll)
            root.addWidget(charts_group)

            # plotting availability
            self._plots_available = pg is not None
            if not self._plots_available:
                root.addWidget(QtWidgets.QLabel('pyqtgraph not installed: plotting disabled.'))

            # internal plot registry: pid_id -> (plot_widget, curve, data(list[Tuple[ts,value]]))
            self._plot_series: Dict[str, Tuple[Any, Any, List[Tuple[float, float]]]] = {}

            # Signals
            self.connect_btn.clicked.connect(self._on_connect)
            self.start_btn.clicked.connect(self._on_toggle_start)
            self.file_btn.clicked.connect(self._on_choose_file)
            self.load_log_btn.clicked.connect(self._on_load_log)
            self.open_logs_btn.clicked.connect(self._on_open_logs_dir)
            self.filter_edit.textChanged.connect(self._refresh_pid_list)
            self.clear_filter_btn.clicked.connect(lambda: self.filter_edit.setText(''))
            self.preset_common_btn.clicked.connect(self._select_common)
            self.preset_none_btn.clicked.connect(self._select_none)
            self.preset_boost_btn.clicked.connect(self._select_boost_fuel)
            self.preset_timing_btn.clicked.connect(self._select_timing_knock)
            self.preset_engine_btn.clicked.connect(self._select_engine_basic)
            self.preset_emissions_btn.clicked.connect(self._select_emissions)
            self.preset_knock_btn.clicked.connect(self._select_knock_safety)
            self.preset_all_btn.clicked.connect(self._select_all_pids)

            # Populate PIDs
            self._all_pids_cache = self._ctrl.list_pids()
            self._refresh_pid_list()

            # Reflect any existing shared OBD connection in the status label
            self._refresh_connection_status()

        # --------------------------- UI helpers ---------------------------
        def _refresh_pid_list(self):
            filt = (self.filter_edit.text() or '').strip().lower()
            self.pid_list.clear()
            for info in self._all_pids_cache:
                marker = "\u2713 " if info.get('verified') else ""
                text = f"{marker}{info['name']} [{info['id']}] ({info['unit']})"
                if filt and (filt not in text.lower()):
                    continue
                item = QtWidgets.QListWidgetItem(text)
                # store id
                item.setData(QtCore.Qt.UserRole, info['id'])
                # make checkable for quick selection
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                # default unchecked
                item.setCheckState(QtCore.Qt.Unchecked)
                self.pid_list.addItem(item)

        def _selected_pid_ids_from_ui(self) -> List[str]:
            ids: List[str] = []
            for i in range(self.pid_list.count()):
                it = self.pid_list.item(i)
                if it.checkState() == QtCore.Qt.Checked:
                    ids.append(str(it.data(QtCore.Qt.UserRole)))
            return ids

        def _select_common(self):
            self._apply_preset_ids(self._ctrl.common_pid_ids())

        def _select_none(self):
            for i in range(self.pid_list.count()):
                it = self.pid_list.item(i)
                it.setCheckState(QtCore.Qt.Unchecked)

        def _apply_preset_ids(self, pid_ids: List[str]):
            ids = set(pid_ids or [])
            if not ids:
                return
            for i in range(self.pid_list.count()):
                it = self.pid_list.item(i)
                pid_id = str(it.data(QtCore.Qt.UserRole))
                it.setCheckState(QtCore.Qt.Checked if pid_id in ids else QtCore.Qt.Unchecked)

        def _select_boost_fuel(self):
            self._apply_preset_ids(self._ctrl.preset_boost_fuel_ids())

        def _select_timing_knock(self):
            self._apply_preset_ids(self._ctrl.preset_timing_knock_ids())

        def _select_engine_basic(self):
            self._apply_preset_ids(self._ctrl.preset_engine_basic_ids())

        def _select_emissions(self):
            self._apply_preset_ids(self._ctrl.preset_emissions_ids())

        def _select_knock_safety(self):
            self._apply_preset_ids(self._ctrl.preset_knock_safety_ids())

        def _select_all_pids(self):
            self._apply_preset_ids(self._ctrl.preset_all_pids_ids())

        def _on_choose_file(self):
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Log CSV', 'logs/datalog.csv', 'CSV Files (*.csv);;All Files (*)')
            if path:
                self.file_edit.setText(path)

        def _on_open_logs_dir(self):
            # Best-effort open logs directory
            base = os.path.abspath('logs')
            try:
                os.makedirs(base, exist_ok=True)
            except Exception:
                pass
            try:
                QtGui = None
                try:
                    from PySide6 import QtGui as _QtGui
                    QtGui = _QtGui
                except Exception:
                    try:
                        from PyQt5 import QtGui as _QtGui
                        QtGui = _QtGui
                    except Exception:
                        QtGui = None
                # Prefer OS-level open for simplicity
                os.startfile(base)
            except Exception:
                # fallback: message
                QtWidgets.QMessageBox.information(self, 'Logs Folder', f'Logs folder: {base}')

        def _on_load_log(self):
            """Open the currently selected log CSV in a separate viewer window."""
            path = (self.file_edit.text() or '').strip()
            if not path:
                QtWidgets.QMessageBox.information(self, 'No Log Selected', 'No log file path is set.')
                return
            if not os.path.exists(path):
                QtWidgets.QMessageBox.warning(self, 'File Not Found', f'File does not exist:\n{path}')
                return

            try:
                from flash_tool.gui.widgets import live_plot_widget as lp
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, 'Viewer Unavailable', f'Live plot widget unavailable: {exc}')
                return

            try:
                viewer = lp.create_qt_widget(None)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, 'Viewer Error', f'Could not create viewer: {exc}')
                return

            try:
                if hasattr(viewer, 'load_csv_path'):
                    viewer.load_csv_path(path)
            except Exception:
                # Ignore load error; viewer will show its own dialog if needed
                pass

            try:
                viewer.setWindowTitle(f"Log Viewer - {os.path.basename(path)}")
            except Exception:
                pass

            try:
                viewer.show()
            except Exception:
                QtWidgets.QMessageBox.warning(self, 'Viewer Error', 'Could not show log viewer window.')

        def _refresh_connection_status(self):
            """Update status label based on shared OBD session state."""
            try:
                status_func = getattr(self._ctrl, 'get_connection_status', None)
                info = status_func() if callable(status_func) else {'connected': False, 'port': None}
            except Exception:
                info = {'connected': False, 'port': None}

            if info.get('connected'):
                port = info.get('port') or ''
                self.status_lbl.setText(f"Connected: {port}")
                # If port edit is empty, pre-fill with the active port
                if port and not (self.port_edit.text() or '').strip():
                    self.port_edit.setText(str(port))
            else:
                self.status_lbl.setText('Disconnected')

        # ---------------------------- Connect ----------------------------
        def _on_connect(self):
            port = self.port_edit.text().strip() or None
            try:
                baud = int(self.baud_edit.text().strip())
            except Exception:
                baud = 38400

            def task(progress_cb=None, cancel_token=None):
                return self._ctrl.connect(port, baud)

            def ui_progress(evt):
                # no-op for connection
                pass

            def done(res):
                if isinstance(res, dict) and res.get('success'):
                    self.status_lbl.setText(f"Connected: {res.get('port','')}")
                else:
                    err = (res or {}).get('error') if isinstance(res, dict) else str(res)
                    self.status_lbl.setText(f"Connect failed: {err}")

                # After any connect attempt, resync with shared session state
                self._refresh_connection_status()

            self._run_worker(task, ui_progress, done)

        # ----------------------- Start/Stop logging ----------------------
        def _on_toggle_start(self):
            # Stop if running
            if self._worker and self._worker.is_alive():
                if self._cancel:
                    self._cancel.request_cancel()
                self.start_btn.setText('Start Logging')
                # Restore controls immediately so the user regains access
                if getattr(self, '_controls_container', None) is not None:
                    self._controls_container.setVisible(True)
                return

            # Collect selection
            pid_ids = self._selected_pid_ids_from_ui()
            if not pid_ids:
                QtWidgets.QMessageBox.information(self, 'Select PIDs', 'Please select at least one PID to log.')
                return
            self._selected_pid_ids = pid_ids

            # Prepare CSV
            csv_path = self.file_edit.text().strip()
            if not csv_path:
                # default path
                ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
                os.makedirs('logs', exist_ok=True)
                csv_path = os.path.join('logs', f'datalog_{ts}.csv')
                self.file_edit.setText(csv_path)

            # Reset CSV state
            self._csv_path = csv_path
            try:
                # Open in write mode (new session)
                self._csv_file = open(self._csv_path, 'w', newline='', encoding='utf-8')
                self._csv_writer = csv.writer(self._csv_file)
                
                # Write metadata header comments (VIN, ECU type, etc.)
                try:
                    vin_info = self._ctrl.get_vehicle_info()
                    if isinstance(vin_info, dict) and vin_info.get('success'):
                        vin = vin_info.get('data', {}).get('vin', 'N/A')
                        ecu_type = vin_info.get('data', {}).get('ecu_type', 'N/A')
                        self._csv_file.write(f"# VIN: {vin}\n")
                        self._csv_file.write(f"# ECU Type: {ecu_type}\n")
                        self._csv_file.write(f"# Timestamp: {datetime.datetime.utcnow().isoformat()}Z\n")
                except Exception:
                    pass
                
                # header: timestamp + pid names
                header = ['timestamp']
                # map pid id -> display name (with unit)
                self._pid_name_unit: Dict[str, str] = {}
                for pid_id in pid_ids:
                    # find in cache
                    name = pid_id
                    unit = ''
                    for info in self._all_pids_cache:
                        if info['id'] == pid_id:
                            name = info['name']
                            unit = info.get('unit') or ''
                            break
                    disp = f"{name} ({unit})" if unit else name
                    self._pid_name_unit[pid_id] = disp
                    header.append(disp)
                self._csv_writer.writerow(header)
                self._csv_file.flush()
                self._csv_header_written = True
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'CSV Error', f'Failed to open CSV file: {e}')
                # ensure state cleared
                try:
                    if self._csv_file:
                        self._csv_file.close()
                except Exception:
                    pass
                self._csv_file = None
                self._csv_writer = None
                self._csv_header_written = False
                return

            # Prepare plots
            self._setup_plots_for(pid_ids)

            # Start worker
            interval_ms = int(self.interval_spin.value())
            duration_ms = int(self.duration_spin.value())

            def poll_task(progress_cb=None, cancel_token=None):
                try:
                    started = time.time()
                    while not (cancel_token and cancel_token.is_cancelled()):
                        res = self._ctrl.read_pids(pid_ids)
                        if isinstance(res, dict) and res.get('success'):
                            data = res.get('data') or {}
                            # Emit for UI update
                            progress_cb(0.0, {'kind': 'data', 'data': data})
                            # Write CSV row
                            if self._csv_writer:
                                ts_iso = datetime.datetime.utcnow().isoformat() + 'Z'
                                row = [ts_iso]
                                for pid in pid_ids:
                                    v = data.get(pid, {}).get('value')
                                    row.append(v)
                                try:
                                    self._csv_writer.writerow(row)
                                    self._csv_file.flush()
                                except Exception:
                                    pass
                        else:
                            msg = res.get('error') if isinstance(res, dict) else str(res)
                            progress_cb(0.0, {'kind': 'message', 'text': f'PID read error: {msg}'})

                        if duration_ms and ((time.time() - started) * 1000.0 >= duration_ms):
                            break
                        time.sleep(max(0.01, interval_ms / 1000.0))
                    return {'success': True}
                except Exception as e:
                    return {'success': False, 'error': str(e), 'trace': traceback.format_exc()}

            def ui_progress(evt):
                payload = getattr(evt, 'message', None)
                if isinstance(payload, dict):
                    if payload.get('kind') == 'data':
                        self._on_new_data(payload.get('data') or {})
                    elif payload.get('kind') == 'message':
                        # Display message in status label for now
                        self.status_lbl.setText(str(payload.get('text') or ''))

            def done(res):
                # finalize
                self._teardown_csv()
                self.start_btn.setText('Start Logging')
                # Ensure controls are visible again after logging ends
                if getattr(self, '_controls_container', None) is not None:
                    self._controls_container.setVisible(True)
                if isinstance(res, dict) and not res.get('success', True):
                    QtWidgets.QMessageBox.warning(self, 'Logger Error', str(res.get('error')))

            self._cancel = CancelToken()
            self._worker = Worker(task=poll_task, progress_cb=ui_progress, cancel_token=self._cancel)
            try:
                self._worker.start()
                self.start_btn.setText('Stop Logging')
                # While actively logging, hide the configuration controls so
                # the charts can dominate the view.
                if getattr(self, '_controls_container', None) is not None:
                    self._controls_container.setVisible(False)
            except Exception as e:
                self._teardown_csv()
                QtWidgets.QMessageBox.warning(self, 'Start Failed', f'Could not start logging: {e}')

            # monitor completion
            def _monitor():
                if self._worker and self._worker.is_alive():
                    QtCore.QTimer.singleShot(250, _monitor)
                    return
                done({'success': True})

            QtCore.QTimer.singleShot(250, _monitor)

        def _teardown_csv(self):
            try:
                if self._csv_file:
                    self._csv_file.flush()
                    self._csv_file.close()
            except Exception:
                pass
            self._csv_file = None
            self._csv_writer = None
            self._csv_header_written = False

        # --------------------------- Plotting ---------------------------
        def _setup_plots_for(self, pid_ids: List[str]):
            # Clear existing
            for pid_id, (w, c, data) in list(self._plot_series.items()):
                try:
                    w.setParent(None)
                except Exception:
                    pass
            self._plot_series.clear()

            if not self._plots_available:
                return
            try:
                import pyqtgraph as pg
            except Exception:
                return

            for pid in pid_ids:
                gb = QtWidgets.QGroupBox(self._pid_name_unit.get(pid, pid))
                gb_l = QtWidgets.QVBoxLayout(gb)
                plot = pg.PlotWidget()
                gb_l.addWidget(plot)
                # Give each chart enough vertical space to be readable.
                # The scroll area above will handle the total height.
                gb.setMinimumHeight(220)
                curve = plot.plot([], [], pen=pg.mkPen('y', width=2))
                plot.showGrid(x=True, y=True, alpha=0.3)
                # store with empty history
                self._plot_series[pid] = (gb, curve, [])
                self.scroll_layout.addWidget(gb)
            self.scroll_layout.addStretch(1)

        def _on_new_data(self, data: Dict[str, Any]):
            if not self._plots_available:
                return
            now = time.time()
            # append and refresh curves
            for pid, (gb, curve, series) in self._plot_series.items():
                v = data.get(pid, {}).get('value')
                if v is None:
                    continue
                series.append((now, float(v)))
                # keep last N seconds
                cutoff = now - 60.0  # 1 min window
                while series and series[0][0] < cutoff:
                    series.pop(0)
                xs = [t - now for (t, _) in series]
                ys = [val for (_, val) in series]
                try:
                    curve.setData(xs, ys)
                except Exception:
                    pass

        # --------------------------- Worker util --------------------------
        def _run_worker(self, task, progress_cb, on_done):
            if getattr(self, '_worker', None) and self._worker.is_alive():
                try:
                    if getattr(self, '_cancel', None):
                        self._cancel.request_cancel()
                except Exception:
                    pass
            self._cancel = CancelToken()
            w = Worker(task=task, progress_cb=progress_cb, cancel_token=self._cancel)
            self._worker = w
            try:
                w.start()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Task Start Failed', str(e))
                return

            def _poll():
                if w.is_alive():
                    QtCore.QTimer.singleShot(200, _poll)
                    return
                try:
                    res = w.result()
                except Exception as e:
                    res = {'success': False, 'error': str(e)}
                try:
                    on_done(res)
                except Exception:
                    pass

            QtCore.QTimer.singleShot(200, _poll)

    return _Widget(parent)
