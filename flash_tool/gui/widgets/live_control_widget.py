#!/usr/bin/env python3
"""Live Control / Live RAM Tuning widget.

This widget provides a user-friendly interface for live ECU control:

- Start/stop a BMW extended diagnostic session (0x87 + TesterPresent)
  using gui_api.start_live_session/stop_live_session.
- Predefined "Live Tune" controls for wastegate duty cycle related
  RAM variables in the 0xD000xxxx region, so the user does not need
  to enter raw RAM addresses manually.
- An optional advanced "Custom RAM Write" section for expert use that
  only allows writes to the 0xD000xxxx RAM region.

All writes are performed via UDS WriteMemoryByAddress (0x3D) through
DirectCANFlasher. Changes are temporary (RAM only) and are lost when
power is cycled or the ECU resets.

This widget is intended for bench / controlled testing. It should not
be used for aggressive on-road tuning without proper safeguards.
"""
from __future__ import annotations

from typing import Callable, Optional, Dict, Any
import struct

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore
    except Exception as exc:  # pragma: no cover - GUI-only
        raise ImportError("Qt bindings not available for Live Control widget") from exc

try:
    from flash_tool.gui import gui_api
except Exception:  # pragma: no cover - allows import in limited environments
    gui_api = None  # type: ignore


class LiveControlWidget(QtWidgets.QWidget):
    """Qt widget for Live Control / Live RAM tuning.

    Args:
        handle_provider: Callable returning the current ConnectionHandle
            from ConnectionController (or None if not connected).
        parent: Optional Qt parent widget.
    """

    def __init__(self, handle_provider: Callable[[], Any], parent: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._handle_provider = handle_provider
        self._session_active = False

        # Add help button (top right)
        help_btn = QtWidgets.QPushButton('Help')
        help_btn.setToolTip('Show help and usage instructions for the Live Control widget.')
        help_btn.setFixedWidth(60)
        help_btn.clicked.connect(self._show_help_dialog)
        hlayout = QtWidgets.QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(help_btn)
        if self.layout() is None:
            vlayout = QtWidgets.QVBoxLayout(self)
            self.setLayout(vlayout)
        self.layout().addLayout(hlayout)

        # Predefined WGDC / boost-related RAM variables (0xD000xxxx)
        # Addresses and semantics from docs/ADDRESS_TRANSLATION_VALIDATION.md,
        # MSD80 A2L files, and flash_tool/n54_pids.py (WGDC_* entries).
        self._params: Dict[str, Dict[str, Any]] = {
            "wgdc_feedforward": {
                "label": "WGDC Feedforward (Atlvst)",
                "address": 0xD00069E4,
                "type": "percent_u8",
                "suffix": " %",
                "min": 0.0,
                "max": 100.0,
                "step": 0.5,
            },
            "wgdc_total": {
                "label": "WGDC Total (Atlr)",
                "address": 0xD00069E8,
                "type": "percent_u8",
                "suffix": " %",
                "min": 0.0,
                "max": 100.0,
                "step": 0.5,
            },
            "wgdc_no_adapt": {
                "label": "WGDC Without Adaptation (Atlr_oad)",
                "address": 0xD0007070,
                "type": "percent_u8",
                "suffix": " %",
                "min": 0.0,
                "max": 100.0,
                "step": 0.5,
            },
            "wgdc_p": {
                "label": "WGDC P Component (Atlr_p)",
                "address": 0xD00069FA,
                "type": "signed_percent_i16",
                "suffix": " %",
                "min": -100.0,
                "max": 100.0,
                "step": 1.0,
            },
            "wgdc_i": {
                "label": "WGDC I Component (Atlr_i)",
                "address": 0xD00069EA,
                "type": "signed_percent_i16",
                "suffix": " %",
                "min": -100.0,
                "max": 100.0,
                "step": 1.0,
            },
            "wgdc_d": {
                "label": "WGDC D Component (Atlr_d)",
                "address": 0xD00069FE,
                "type": "signed_percent_i16",
                "suffix": " %",
                "min": -100.0,
                "max": 100.0,
                "step": 1.0,
            },
            "wgdc_pi_sum": {
                "label": "WGDC P+I Sum (Atlr_pi)",
                "address": 0xD00069FC,
                "type": "signed_percent_i16",
                "suffix": " %",
                "min": -100.0,
                "max": 100.0,
                "step": 1.0,
            },
            # Boost controller targets and error terms (hPa). These use the
            # pressure scalings from the MSD80 A2L: raw U/SWORD values scaled
            # into a 0..~2559.96 hPa physical range.
            "boost_target_reg": {
                "label": "Boost Target (Pldr_soll, hPa)",
                "address": 0xD0006A34,
                "type": "pressure_hpa_u16",
                "suffix": " hPa",
                "min": 0.0,
                "max": 2559.9,
                "step": 10.0,
            },
            "boost_deviation": {
                "label": "Boost Deviation (Pld_diff, hPa)",
                "address": 0xD0006A20,
                "type": "signed_pressure_hpa_i16",
                "suffix": " hPa",
                "min": -2560.0,
                "max": 2560.0,
                "step": 10.0,
                "writable": False,
            },
            "boost_deviation_filtered": {
                "label": "Boost Deviation Filtered (Pld_diff_fil, hPa)",
                "address": 0xD0006A22,
                "type": "signed_pressure_hpa_i16",
                "suffix": " hPa",
                "min": -2560.0,
                "max": 2560.0,
                "step": 10.0,
                "writable": False,
            },
            "atl_reg_status": {
                "label": "ATL Regulator Status (St_atlreg)",
                "address": 0xD00069EE,
                "type": "ubyte",
                "suffix": "",
                "min": 0.0,
                "max": 255.0,
                "step": 1.0,
                "writable": False,
            },
        }
        # Live tuning presets expressed as deltas (in percentage points)
        # applied on top of the current widget values. These are intentionally
        # conservative and focus on feedforward WGDC adjustments.
        self._presets: Dict[str, Dict[str, Any]] = {
            "custom": {
                "label": "Custom (no preset)",
                "adjustments": {},
            },
            "wgdc_ff_plus_3": {
                "label": "+3% WGDC Feedforward",
                "adjustments": {"wgdc_feedforward": 3.0},
            },
            "wgdc_ff_plus_6": {
                "label": "+6% WGDC Feedforward",
                "adjustments": {"wgdc_feedforward": 6.0},
            },
            "wgdc_ff_plus_10": {
                "label": "+10% WGDC Feedforward",
                "adjustments": {"wgdc_feedforward": 10.0},
            },
            "wgdc_ff_minus_5": {
                "label": "-5% WGDC Feedforward (reduce)",
                "adjustments": {"wgdc_feedforward": -5.0},
            },
        }
        # Baseline snapshot of live values (per-session). When set, the
        # user can quickly restore these values to undo live changes
        # without cycling ignition.
        self._baseline_values: Dict[str, float] = {}
        self._spin_widgets: Dict[str, QtWidgets.QDoubleSpinBox] = {}

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Live Control / Live RAM Tuning")
        title.setToolTip("Control and tune ECU RAM variables in real time. Changes are temporary and for bench/controlled testing only.")
        font = title.font()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Session controls
        session_group = QtWidgets.QGroupBox("Live Session (Extended + TesterPresent)")
        session_layout = QtWidgets.QHBoxLayout(session_group)
        self._btn_start_session = QtWidgets.QPushButton("Start Live Session")
        self._btn_start_session.setToolTip("Begin a UDS extended diagnostic session for live RAM tuning.")
        self._btn_stop_session = QtWidgets.QPushButton("Stop Live Session")
        self._btn_stop_session.setToolTip("End the current live session and restore normal ECU operation.")
        self._btn_stop_session.setEnabled(False)
        self._lbl_session_status = QtWidgets.QLabel("Status: Idle")
        self._lbl_session_status.setToolTip("Shows the current live session status and errors.")

        session_layout.addWidget(self._btn_start_session)
        session_layout.addWidget(self._btn_stop_session)
        session_layout.addStretch(1)
        session_layout.addWidget(self._lbl_session_status)
        # Give the session group enough height so the header and
        # buttons are not visually cramped, especially under themed
        # styles.
        session_group.setMinimumHeight(80)
        layout.addWidget(session_group)

        self._btn_start_session.clicked.connect(self._on_start_session_clicked)
        self._btn_stop_session.clicked.connect(self._on_stop_session_clicked)

        # Safety enable checkbox (gates all write operations)
        safety_layout = QtWidgets.QHBoxLayout()
        safety_layout.addWidget(QtWidgets.QLabel("⚠ LIVE RAM TUNING:"))
        self._safety_check = QtWidgets.QCheckBox("I understand: Changes are TEMPORARY and volatile. Bench ECU ONLY.")
        self._safety_check.setChecked(False)
        safety_layout.addWidget(self._safety_check)
        safety_layout.addStretch()
        layout.addLayout(safety_layout)

        # Predefined WGDC / Boost live tuning
        tuning_group = QtWidgets.QGroupBox("WGDC / Boost Live Tuning (RAM 0xD000xxxx)")
        tuning_layout = QtWidgets.QVBoxLayout(tuning_group)

        info_label = QtWidgets.QLabel(
            "These controls write to ECU RAM (0xD000xxxx) using UDS 0x3D. "
            "Changes are TEMPORARY and reset when the ECU powers down.\n\n"
            "Use primarily on a bench ECU or in controlled test conditions."
        )
        info_label.setWordWrap(True)
        info_label.setToolTip("Important safety and usage information for live RAM tuning.")
        tuning_layout.addWidget(info_label)

        # Preset selection row
        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel("Preset:"))
        self._preset_combo = QtWidgets.QComboBox()
        self._preset_combo.setToolTip("Select a predefined set of RAM values for quick tuning.")
        for key, cfg in self._presets.items():
            self._preset_combo.addItem(cfg["label"], key)
        self._btn_apply_preset = QtWidgets.QPushButton("Apply Preset")
        self._btn_apply_preset.setToolTip("Apply the selected preset values to all parameters.")
        preset_row.addWidget(self._preset_combo)
        preset_row.addWidget(self._btn_apply_preset)
        preset_row.addStretch(1)
        tuning_layout.addLayout(preset_row)

        # Global actions row
        actions_row = QtWidgets.QHBoxLayout()
        self._btn_read_all = QtWidgets.QPushButton("Read All")
        self._btn_read_all.setToolTip("Read all parameter values from ECU RAM.")
        self._btn_capture_baseline = QtWidgets.QPushButton("Capture Baseline")
        self._btn_capture_baseline.setToolTip("Save current RAM values as a baseline for later restore.")
        self._btn_restore_baseline = QtWidgets.QPushButton("Restore Baseline")
        self._btn_restore_baseline.setToolTip("Restore all parameters to the last captured baseline values.")
        self._btn_restore_baseline.setEnabled(False)
        actions_row.addWidget(self._btn_read_all)
        actions_row.addWidget(self._btn_capture_baseline)
        actions_row.addWidget(self._btn_restore_baseline)
        actions_row.addStretch(1)
        tuning_layout.addLayout(actions_row)

        grid = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel("Parameter"), 0, 0)
        grid.addWidget(QtWidgets.QLabel("Value"), 0, 1)
        grid.addWidget(QtWidgets.QLabel("Actions"), 0, 2)

        row = 1
        for key, cfg in self._params.items():
            name_lbl = QtWidgets.QLabel(cfg["label"])
            name_lbl.setToolTip(f"{cfg['label']} (RAM: 0x{cfg['address']:08X})")
            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(1)
            spin.setSingleStep(cfg.get("step", 1.0))
            spin.setMinimum(cfg.get("min", -100.0))
            spin.setMaximum(cfg.get("max", 100.0))
            spin.setSuffix(cfg.get("suffix", " %"))
            spin.setToolTip(f"Adjust value for {cfg['label']}. Range: {cfg['min']} to {cfg['max']} {cfg['suffix']}")

            self._spin_widgets[key] = spin

            btn_read = QtWidgets.QPushButton("Read")
            btn_read.setToolTip(f"Read current value of {cfg['label']} from ECU RAM.")
            btn_write = QtWidgets.QPushButton("Write")
            btn_write.setToolTip(f"Write new value to {cfg['label']} in ECU RAM.")

            writable = cfg.get("writable", True)

            btn_read.clicked.connect(lambda _=False, k=key: self._on_read_param(k))
            btn_write.clicked.connect(lambda _=False, k=key: self._on_write_param(k))

            if not writable:
                # Read-only parameters: hide write button and prevent manual edits
                btn_write.setVisible(False)
                spin.setReadOnly(True)

            btn_row = QtWidgets.QHBoxLayout()
            btn_row.addWidget(btn_read)
            if writable:
                btn_row.addWidget(btn_write)
            btn_row.addStretch(1)

            grid.addWidget(name_lbl, row, 0)
            grid.addWidget(spin, row, 1)

            btn_container = QtWidgets.QWidget()
            btn_container.setLayout(btn_row)
            grid.addWidget(btn_container, row, 2)

            row += 1

        tuning_layout.addLayout(grid)

        # Ensure the main tuning group has enough vertical space so the
        # explanatory text ("These controls write to ECU RAM...") and
        # controls are fully visible inside themed panels.
        tuning_group.setMinimumHeight(260)
        layout.addWidget(tuning_group)

        self._btn_apply_preset.clicked.connect(self._on_apply_preset_clicked)
        self._btn_read_all.clicked.connect(self._on_read_all_clicked)
        self._btn_capture_baseline.clicked.connect(self._on_capture_baseline_clicked)
        self._btn_restore_baseline.clicked.connect(self._on_restore_baseline_clicked)

        # Advanced custom RAM write section (for expert use)
        adv_group = QtWidgets.QGroupBox("Advanced: Custom RAM Write (D000xxxx only)")
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_layout = QtWidgets.QFormLayout(adv_group)

        self._edit_address = QtWidgets.QLineEdit()
        self._edit_address.setPlaceholderText("0xD00069E8")
        self._edit_address.setToolTip("Enter a custom RAM address in the 0xD000xxxx region.")
        self._edit_data = QtWidgets.QLineEdit()
        self._edit_data.setPlaceholderText("Hex bytes, e.g. '64' or '40 FF'")
        self._edit_data.setToolTip("Enter the value to write to the custom RAM address.")
        self._btn_custom_write = QtWidgets.QPushButton("Write Custom")
        self._btn_custom_write.setToolTip("Write the specified value to the custom RAM address.")

        adv_layout.addRow("RAM Address:", self._edit_address)
        adv_layout.addRow("Data (hex bytes):", self._edit_data)
        adv_layout.addRow("", self._btn_custom_write)

        self._btn_custom_write.clicked.connect(self._on_custom_write)

        # Slightly increase the minimum height so the header, address,
        # and data fields are not drawn over the group frame.
        adv_group.setMinimumHeight(140)
        layout.addWidget(adv_group)
        layout.addStretch(1)

    def _show_help_dialog(self):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('Live Control Help')
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.setText(
            '<b>Live Control / Live RAM Tuning Help</b><br><br>'
            '<b>Purpose:</b> Temporarily adjust ECU RAM variables for bench/controlled testing.<br>'
            '<ul>'
            '<li><b>Start/Stop Live Session:</b> Begin or end a UDS diagnostic session for RAM tuning.</li>'
            '<li><b>Presets:</b> Quickly apply predefined sets of values to all parameters.</li>'
            '<li><b>Read/Write:</b> Read or write individual RAM variables (WGDC, boost, etc.).</li>'
            '<li><b>Custom RAM Write:</b> For advanced users, write to any 0xD000xxxx RAM address.</li>'
            '<li><b>Baseline:</b> Capture and restore all values for safe experimentation.</li>'
            '<li><b>Status:</b> Shows current session state and errors.</li>'
            '<li><b>Tooltips:</b> Hover over any control for more information.</li>'
            '</ul>'
            '<b>Warning:</b> All changes are temporary and lost on ECU reset. Use only for safe, controlled testing.'
        )
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg.exec()

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _get_handle(self) -> Optional[Any]:
        if not callable(self._handle_provider):
            return None
        try:
            return self._handle_provider()
        except Exception:
            return None

    def _require_handle_and_session(self) -> Optional[Any]:
        handle = self._get_handle()
        if handle is None or not getattr(handle, "connected", True):
            QtWidgets.QMessageBox.warning(self, "Not Connected", "Connect to the ECU first using the Connection tab.")
            return None
        if not self._session_active:
            QtWidgets.QMessageBox.warning(self, "Session Not Active", "Start a Live Session before performing live tuning.")
            return None
        return handle

    def _on_start_session_clicked(self) -> None:
        handle = self._get_handle()
        if handle is None or not getattr(handle, "connected", True):
            QtWidgets.QMessageBox.warning(self, "Not Connected", "Connect to the ECU first using the Connection tab.")
            return

        if gui_api is None or not hasattr(gui_api, "start_live_session"):
            QtWidgets.QMessageBox.critical(self, "Live Session Error", "GUI API does not expose start_live_session().")
            return

        self._lbl_session_status.setText("Status: Starting session...")
        QtWidgets.QApplication.processEvents()

        try:
            result = gui_api.start_live_session(handle)
        except Exception as exc:  # pragma: no cover - runtime error path
            QtWidgets.QMessageBox.critical(self, "Live Session Error", f"Failed to start live session:\n{exc}")
            self._lbl_session_status.setText("Status: Error starting session")
            self._session_active = False
            self._btn_start_session.setEnabled(True)
            self._btn_stop_session.setEnabled(False)
            return

        if not isinstance(result, dict) or not result.get("success"):
            error = result.get("error") if isinstance(result, dict) else "Unknown error"
            QtWidgets.QMessageBox.critical(self, "Live Session Error", f"Failed to start live session:\n{error}")
            self._lbl_session_status.setText("Status: Error starting session")
            self._session_active = False
            self._btn_start_session.setEnabled(True)
            self._btn_stop_session.setEnabled(False)
            return

        self._session_active = True
        # Reset any previous baseline snapshot for the new session
        self._baseline_values.clear()
        self._btn_restore_baseline.setEnabled(False)
        self._btn_start_session.setEnabled(False)
        self._btn_stop_session.setEnabled(True)
        self._lbl_session_status.setText("Status: Session active")

    def _on_stop_session_clicked(self) -> None:
        handle = self._get_handle()
        if handle is None:
            self._session_active = False
            self._btn_start_session.setEnabled(True)
            self._btn_stop_session.setEnabled(False)
            self._lbl_session_status.setText("Status: Idle")
            return

        if gui_api is None or not hasattr(gui_api, "stop_live_session"):
            QtWidgets.QMessageBox.critical(self, "Live Session Error", "GUI API does not expose stop_live_session().")
            return

        try:
            result = gui_api.stop_live_session(handle)
        except Exception as exc:  # pragma: no cover - runtime error path
            QtWidgets.QMessageBox.critical(self, "Live Session Error", f"Failed to stop session:\n{exc}")
            return

        if isinstance(result, dict) and not result.get("success"):
            error = result.get("error", "Unknown error")
            QtWidgets.QMessageBox.warning(self, "Live Session", f"Session stop reported an error:\n{error}")

        self._session_active = False
        self._btn_start_session.setEnabled(True)
        self._btn_stop_session.setEnabled(False)
        self._lbl_session_status.setText("Status: Idle")

    # ------------------------------------------------------------------
    # Encoding helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _decode_percent_u8(data: bytes) -> float:
        if not data:
            return 0.0
        return round(data[0] * 100.0 / 255.0, 1)

    @staticmethod
    def _encode_percent_u8(value: float) -> bytes:
        raw = int(round(max(0.0, min(100.0, value)) * 255.0 / 100.0))
        return bytes([raw])

    @staticmethod
    def _decode_signed_percent_i16(data: bytes) -> float:
        if len(data) < 2:
            return 0.0
        val = struct.unpack("<h", data[:2])[0]
        return round(val * 100.0 / 32768.0, 2)

    @staticmethod
    def _encode_signed_percent_i16(value: float) -> bytes:
        # Inverse of decode_signed_percent: val = value_pct * 327.68
        clamped = max(-100.0, min(100.0, value))
        raw = int(round(clamped * 327.68))
        if raw < -32768:
            raw = -32768
        if raw > 32767:
            raw = 32767
        return struct.pack("<h", raw)

    @staticmethod
    def _decode_pressure_hpa_u16(data: bytes) -> float:
        """Decode unsigned pressure value in hPa.

        MSD80 uses a 16-bit unsigned value scaled so that 0xFFFF maps to
        ~2559.96 hPa (factor 0.0390625).
        """
        if len(data) < 2:
            return 0.0
        raw = struct.unpack("<H", data[:2])[0]
        return round(raw * 0.0390625, 1)

    @staticmethod
    def _encode_pressure_hpa_u16(value: float) -> bytes:
        clamped = max(0.0, min(65535.0 * 0.0390625, value))
        raw = int(round(clamped / 0.0390625))
        if raw < 0:
            raw = 0
        if raw > 0xFFFF:
            raw = 0xFFFF
        return struct.pack("<H", raw)

    @staticmethod
    def _decode_signed_pressure_hpa_i16(data: bytes) -> float:
        """Decode signed pressure deviation in hPa.

        Signed 16-bit value scaled so that +/-32768 maps to +/-2560 hPa
        (factor 0.078125).
        """
        if len(data) < 2:
            return 0.0
        raw = struct.unpack("<h", data[:2])[0]
        return round(raw * 0.078125, 1)

    @staticmethod
    def _encode_signed_pressure_hpa_i16(value: float) -> bytes:
        clamped = max(-2560.0, min(2560.0, value))
        raw = int(round(clamped / 0.078125))
        if raw < -32768:
            raw = -32768
        if raw > 32767:
            raw = 32767
        return struct.pack("<h", raw)

    @staticmethod
    def _decode_ubyte(data: bytes) -> float:
        if not data:
            return 0.0
        return float(data[0])

    @staticmethod
    def _encode_ubyte(value: float) -> bytes:
        clamped = max(0.0, min(255.0, value))
        return bytes([int(clamped)])

    @staticmethod
    def _is_d000_ram(address: int) -> bool:
        return 0xD0000000 <= address <= 0xD000FFFF

    # ------------------------------------------------------------------
    # Predefined parameter handlers
    # ------------------------------------------------------------------
    def _on_read_param(self, key: str) -> None:
        handle = self._require_handle_and_session()
        if handle is None:
            return

        cfg = self._params.get(key)
        spin = self._spin_widgets.get(key)
        if cfg is None or spin is None:
            return

        addr = int(cfg["address"])
        ptype = cfg.get("type", "percent_u8")

        if gui_api is None or not hasattr(gui_api, "read_region"):
            QtWidgets.QMessageBox.critical(self, "Read Error", "GUI API does not expose read_region().")
            return

        if ptype in ("percent_u8", "ubyte"):
            size = 1
        else:
            size = 2

        try:
            data = gui_api.read_region(handle, addr, size)
        except Exception as exc:  # pragma: no cover - runtime error path
            QtWidgets.QMessageBox.critical(self, "Read Error", f"Failed to read RAM:\n{exc}")
            return

        if not data or len(data) < size:
            QtWidgets.QMessageBox.warning(self, "Read Error", "No data returned from ECU for this address.")
            return

        if ptype == "percent_u8":
            val = self._decode_percent_u8(data)
        elif ptype == "signed_percent_i16":
            val = self._decode_signed_percent_i16(data)
        elif ptype == "pressure_hpa_u16":
            val = self._decode_pressure_hpa_u16(data)
        elif ptype == "signed_pressure_hpa_i16":
            val = self._decode_signed_pressure_hpa_i16(data)
        elif ptype == "ubyte":
            val = self._decode_ubyte(data)
        else:
            val = self._decode_signed_percent_i16(data)

        spin.blockSignals(True)
        spin.setValue(val)
        spin.blockSignals(False)

    def _on_read_all_clicked(self) -> None:
        """Read all predefined parameters from ECU RAM into the controls."""
        handle = self._require_handle_and_session()
        if handle is None:
            return

        if gui_api is None or not hasattr(gui_api, "read_region"):
            QtWidgets.QMessageBox.critical(self, "Read Error", "GUI API does not expose read_region().")
            return

        errors = []
        for key, cfg in self._params.items():
            spin = self._spin_widgets.get(key)
            if spin is None:
                continue

            addr = int(cfg["address"])
            ptype = cfg.get("type", "percent_u8")
            if ptype in ("percent_u8", "ubyte"):
                size = 1
            else:
                size = 2

            try:
                data = gui_api.read_region(handle, addr, size)
            except Exception as exc:  # pragma: no cover - runtime error path
                errors.append(f"{cfg['label']}: exception during read: {exc}")
                continue

            if not data or len(data) < size:
                errors.append(f"{cfg['label']}: no data returned from ECU for this address")
                continue

            if ptype == "percent_u8":
                val = self._decode_percent_u8(data)
            elif ptype == "signed_percent_i16":
                val = self._decode_signed_percent_i16(data)
            elif ptype == "pressure_hpa_u16":
                val = self._decode_pressure_hpa_u16(data)
            elif ptype == "signed_pressure_hpa_i16":
                val = self._decode_signed_pressure_hpa_i16(data)
            elif ptype == "ubyte":
                val = self._decode_ubyte(data)
            else:
                val = self._decode_signed_percent_i16(data)

            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Read All",
                "Some parameters failed to read:\n\n" + "\n".join(errors),
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Read All",
                "Successfully read all live WGDC/boost parameters from ECU RAM.",
            )

    def _on_write_param(self, key: str) -> None:
        # Safety gate: require enable checkbox
        if not getattr(self, '_safety_check', None) or not self._safety_check.isChecked():
            QtWidgets.QMessageBox.warning(
                self,
                "Safety Disabled",
                "Enable the safety checkbox to perform write operations.",
            )
            return

        handle = self._require_handle_and_session()
        if handle is None:
            return

        cfg = self._params.get(key)
        spin = self._spin_widgets.get(key)
        if cfg is None or spin is None:
            return

        if not cfg.get("writable", True):
            QtWidgets.QMessageBox.information(
                self,
                "Read-Only Parameter",
                f"{cfg['label']} is read-only and cannot be written.",
            )
            return

        addr = int(cfg["address"])
        ptype = cfg.get("type", "percent_u8")

        if not self._is_d000_ram(addr):
            QtWidgets.QMessageBox.critical(
                self,
                "Safety Block",
                f"Refusing to write to non-RAM address 0x{addr:08X}.\n"
                "Only 0xD000xxxx RAM addresses are allowed for live tuning.",
            )
            return

        value = float(spin.value())
        if ptype == "percent_u8":
            data = self._encode_percent_u8(value)
        elif ptype == "signed_percent_i16":
            data = self._encode_signed_percent_i16(value)
        elif ptype == "pressure_hpa_u16":
            data = self._encode_pressure_hpa_u16(value)
        elif ptype == "signed_pressure_hpa_i16":
            data = self._encode_signed_pressure_hpa_i16(value)
        elif ptype == "ubyte":
            data = self._encode_ubyte(value)
        else:
            data = self._encode_signed_percent_i16(value)

        if gui_api is None or not hasattr(gui_api, "live_write"):
            QtWidgets.QMessageBox.critical(self, "Write Error", "GUI API does not expose live_write().")
            return

        try:
            result = gui_api.live_write(handle, addr, data)
        except Exception as exc:  # pragma: no cover - runtime error path
            QtWidgets.QMessageBox.critical(self, "Write Error", f"Failed to write RAM:\n{exc}")
            return

        if not isinstance(result, dict) or not result.get("success"):
            error = result.get("error") if isinstance(result, dict) else "Unknown error"
            QtWidgets.QMessageBox.critical(self, "Write Error", f"Live write failed:\n{error}")
            return

        QtWidgets.QMessageBox.information(self, "Live Write", f"Successfully wrote {cfg['label']} at 0x{addr:08X}.")

    def _on_capture_baseline_clicked(self) -> None:
        """Capture current live values as a per-session baseline.

        This reads all predefined parameters from ECU RAM and stores the
        decoded values so they can be restored later without cycling
        ignition. Spinboxes are also updated to the captured values.
        """
        handle = self._require_handle_and_session()
        if handle is None:
            return

        if gui_api is None or not hasattr(gui_api, "read_region"):
            QtWidgets.QMessageBox.critical(self, "Baseline Error", "GUI API does not expose read_region().")
            return

        baseline: Dict[str, float] = {}
        errors = []

        for key, cfg in self._params.items():
            spin = self._spin_widgets.get(key)
            if spin is None:
                continue

            addr = int(cfg["address"])
            ptype = cfg.get("type", "percent_u8")
            if ptype in ("percent_u8", "ubyte"):
                size = 1
            else:
                size = 2

            try:
                data = gui_api.read_region(handle, addr, size)
            except Exception as exc:  # pragma: no cover - runtime error path
                errors.append(f"{cfg['label']}: exception during read: {exc}")
                continue

            if not data or len(data) < size:
                errors.append(f"{cfg['label']}: no data returned from ECU for this address")
                continue

            if ptype == "percent_u8":
                val = self._decode_percent_u8(data)
            elif ptype == "signed_percent_i16":
                val = self._decode_signed_percent_i16(data)
            elif ptype == "pressure_hpa_u16":
                val = self._decode_pressure_hpa_u16(data)
            elif ptype == "signed_pressure_hpa_i16":
                val = self._decode_signed_pressure_hpa_i16(data)
            elif ptype == "ubyte":
                val = self._decode_ubyte(data)
            else:
                val = self._decode_signed_percent_i16(data)

            # Always update the UI spinbox, but only persist baseline for
            # writable parameters so restore does not attempt to change
            # monitoring/status-only values.
            if cfg.get("writable", True):
                baseline[key] = val
            spin.blockSignals(True)
            spin.setValue(val)
            spin.blockSignals(False)

        if baseline:
            self._baseline_values = baseline
            self._btn_restore_baseline.setEnabled(True)

        if errors and baseline:
            QtWidgets.QMessageBox.warning(
                self,
                "Baseline Captured With Warnings",
                "Baseline captured, but some parameters failed to read:\n\n" + "\n".join(errors),
            )
        elif errors and not baseline:
            QtWidgets.QMessageBox.critical(
                self,
                "Baseline Error",
                "Failed to capture baseline; all parameter reads failed:\n\n" + "\n".join(errors),
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Baseline Captured",
                "Captured current live WGDC/boost values as baseline for this session.",
            )

    def _on_restore_baseline_clicked(self) -> None:
        """Restore captured baseline values back to ECU RAM."""
        handle = self._require_handle_and_session()
        if handle is None:
            return

        if not self._baseline_values:
            QtWidgets.QMessageBox.information(
                self,
                "Baseline",
                "No baseline has been captured yet. Use 'Capture Baseline' first.",
            )
            return

        if gui_api is None or not hasattr(gui_api, "live_write"):
            QtWidgets.QMessageBox.critical(self, "Baseline Error", "GUI API does not expose live_write().")
            return

        preview_lines = []
        for param_key, baseline_val in self._baseline_values.items():
            cfg = self._params.get(param_key)
            spin = self._spin_widgets.get(param_key)
            if cfg is None or spin is None:
                continue

            if not cfg.get("writable", True):
                continue

            current_val = float(spin.value())
            suffix = cfg.get("suffix", "")
            preview_lines.append(
                f"{cfg['label']}: {current_val:.1f}{suffix} -> {baseline_val:.1f}{suffix} (restore)"
            )

        if not preview_lines:
            QtWidgets.QMessageBox.warning(
                self,
                "Baseline",
                "No matching parameters found for the captured baseline.",
            )
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Restore Baseline",
            "About to restore the captured baseline values to ECU RAM (0xD000xxxx):\n\n"
            + "\n".join(preview_lines)
            + "\n\nChanges are temporary and will be lost on power cycle. Proceed?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        errors = []
        for param_key, baseline_val in self._baseline_values.items():
            cfg = self._params.get(param_key)
            spin = self._spin_widgets.get(param_key)
            if cfg is None or spin is None:
                continue

            if not cfg.get("writable", True):
                continue

            addr = int(cfg["address"])
            if not self._is_d000_ram(addr):
                errors.append(
                    f"{cfg['label']}: address 0x{addr:08X} is not in 0xD000xxxx RAM; skipping."
                )
                continue

            ptype = cfg.get("type", "percent_u8")
            # Clamp to widget limits to avoid out-of-range writes
            restored_val = max(spin.minimum(), min(spin.maximum(), float(baseline_val)))
            spin.setValue(restored_val)

            if ptype == "percent_u8":
                data = self._encode_percent_u8(restored_val)
            elif ptype == "signed_percent_i16":
                data = self._encode_signed_percent_i16(restored_val)
            elif ptype == "pressure_hpa_u16":
                data = self._encode_pressure_hpa_u16(restored_val)
            elif ptype == "signed_pressure_hpa_i16":
                data = self._encode_signed_pressure_hpa_i16(restored_val)
            elif ptype == "ubyte":
                data = self._encode_ubyte(restored_val)
            else:
                data = self._encode_signed_percent_i16(restored_val)

            try:
                result = gui_api.live_write(handle, addr, data)
            except Exception as exc:  # pragma: no cover - runtime error path
                errors.append(f"{cfg['label']}: exception during write: {exc}")
                continue

            if not isinstance(result, dict) or not result.get("success"):
                error_msg = result.get("error") if isinstance(result, dict) else "Unknown error"
                errors.append(f"{cfg['label']}: live write failed: {error_msg}")

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Baseline Restored With Warnings",
                "Some parameters failed to restore:\n\n" + "\n".join(errors),
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Baseline Restored",
                "Baseline values successfully restored to ECU RAM.",
            )

    def _on_apply_preset_clicked(self) -> None:
        """Apply the selected preset as deltas and write to RAM.

        Presets are defined as percentage-point adjustments on top of the
        current widget values. This requires an active live session and a
        connected ECU. For safety, all writes remain limited to 0xD000xxxx
        RAM addresses.
        """
        # Safety gate: require enable checkbox
        if not getattr(self, '_safety_check', None) or not self._safety_check.isChecked():
            QtWidgets.QMessageBox.warning(
                self,
                "Safety Disabled",
                "Enable the safety checkbox to perform write operations.",
            )
            return

        handle = self._require_handle_and_session()
        if handle is None:
            return

        if gui_api is None or not hasattr(gui_api, "live_write"):
            QtWidgets.QMessageBox.critical(self, "Preset Error", "GUI API does not expose live_write().")
            return

        current_key = self._preset_combo.currentData()
        if not current_key or current_key not in self._presets:
            return

        preset = self._presets[current_key]
        adjustments: Dict[str, float] = preset.get("adjustments", {}) or {}
        if not adjustments:
            QtWidgets.QMessageBox.information(
                self,
                "Preset",
                "Selected preset does not change any values. Use the individual controls instead.",
            )
            return

        # Build a preview of changes based on current widget values
        preview_lines = []
        for param_key, delta in adjustments.items():
            cfg = self._params.get(param_key)
            spin = self._spin_widgets.get(param_key)
            if cfg is None or spin is None:
                continue
            current_val = float(spin.value())
            new_val = current_val + float(delta)
            new_val = max(spin.minimum(), min(spin.maximum(), new_val))
            preview_lines.append(
                f"{cfg['label']}: {current_val:+.1f}% -> {new_val:+.1f}% (Δ {float(delta):+.1f}%)"
            )

        if not preview_lines:
            QtWidgets.QMessageBox.warning(
                self,
                "Preset",
                "No matching parameters found for this preset.",
            )
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Apply Live Tuning Preset",
            "About to apply the following live tuning changes and write them to ECU RAM (0xD000xxxx):\n\n"
            + "\n".join(preview_lines)
            + "\n\nChanges are temporary and will be lost on power cycle. Proceed?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        errors = []
        for param_key, delta in adjustments.items():
            cfg = self._params.get(param_key)
            spin = self._spin_widgets.get(param_key)
            if cfg is None or spin is None:
                continue

            addr = int(cfg["address"])
            if not self._is_d000_ram(addr):
                errors.append(
                    f"{cfg['label']}: address 0x{addr:08X} is not in 0xD000xxxx RAM; skipping."
                )
                continue

            ptype = cfg.get("type", "percent_u8")
            new_val = float(spin.value()) + float(delta)
            new_val = max(spin.minimum(), min(spin.maximum(), new_val))
            spin.setValue(new_val)

            if ptype == "percent_u8":
                data = self._encode_percent_u8(new_val)
            elif ptype == "signed_percent_i16":
                data = self._encode_signed_percent_i16(new_val)
            elif ptype == "pressure_hpa_u16":
                data = self._encode_pressure_hpa_u16(new_val)
            elif ptype == "signed_pressure_hpa_i16":
                data = self._encode_signed_pressure_hpa_i16(new_val)
            elif ptype == "ubyte":
                data = self._encode_ubyte(new_val)
            else:
                data = self._encode_signed_percent_i16(new_val)

            try:
                result = gui_api.live_write(handle, addr, data)
            except Exception as exc:  # pragma: no cover - runtime error path
                errors.append(f"{cfg['label']}: exception during write: {exc}")
                continue

            if not isinstance(result, dict) or not result.get("success"):
                error_msg = result.get("error") if isinstance(result, dict) else "Unknown error"
                errors.append(f"{cfg['label']}: live write failed: {error_msg}")

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Preset Applied With Warnings",
                "Some parameters failed to write:\n\n" + "\n".join(errors),
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Preset Applied",
                "Live tuning preset applied successfully to ECU RAM.",
            )

    # ------------------------------------------------------------------
    # Advanced custom write
    # ------------------------------------------------------------------
    def _on_custom_write(self) -> None:
        handle = self._require_handle_and_session()
        if handle is None:
            return

        addr_text = self._edit_address.text().strip()
        data_text = self._edit_data.text().strip()

        if not addr_text or not data_text:
            QtWidgets.QMessageBox.warning(self, "Input Required", "Please enter both a RAM address and data bytes.")
            return

        try:
            # int(x, 0) handles 0x prefix as hex automatically
            address = int(addr_text, 0)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid Address", "RAM address must be a valid integer (e.g. 0xD00069E8).")
            return

        if not self._is_d000_ram(address):
            QtWidgets.QMessageBox.critical(
                self,
                "Safety Block",
                f"Refusing custom write to non-RAM address 0x{address:08X}.\n"
                "Only 0xD000xxxx RAM addresses are allowed for custom writes.",
            )
            return

        # Normalize hex string: allow spaces and optional 0x prefixes
        clean = data_text.replace(",", " ").replace(";", " ")
        parts = []
        for token in clean.split():
            t = token.strip()
            if not t:
                continue
            if t.lower().startswith("0x"):
                t = t[2:]
            parts.append(t)
        hex_str = "".join(parts)

        try:
            data = bytes.fromhex(hex_str)
        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Data",
                "Data must be valid hex bytes, e.g. '64' or '40 FF'.",
            )
            return

        if not data:
            QtWidgets.QMessageBox.warning(self, "Invalid Data", "No bytes parsed from data input.")
            return

        if gui_api is None or not hasattr(gui_api, "live_write"):
            QtWidgets.QMessageBox.critical(self, "Write Error", "GUI API does not expose live_write().")
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Custom RAM Write",
            f"About to write {len(data)} byte(s) to RAM address 0x{address:08X}.\n\n"
            "This is a low-level operation intended for advanced users.\n"
            "Proceed?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            result = gui_api.live_write(handle, address, data)
        except Exception as exc:  # pragma: no cover - runtime error path
            QtWidgets.QMessageBox.critical(self, "Write Error", f"Failed to write RAM:\n{exc}")
            return

        if not isinstance(result, dict) or not result.get("success"):
            error = result.get("error") if isinstance(result, dict) else "Unknown error"
            QtWidgets.QMessageBox.critical(self, "Write Error", f"Custom live write failed:\n{error}")
            return

        QtWidgets.QMessageBox.information(self, "Custom RAM Write", f"Successfully wrote {len(data)} byte(s) to 0x{address:08X}.")
