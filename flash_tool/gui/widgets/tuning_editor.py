#!/usr/bin/env python3
"""
BMW N54 Tuning Editor Widget
=============================

Author: Gregory King
Date: December 2, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Full-featured PySide6/PyQt5 widget for editing all ECU tuning parameters.
    Organized by category with tabbed interface, preset management, and
    comprehensive validation.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import json

# Try PySide6 first, fall back to PyQt5
try:
    from PySide6 import QtWidgets as qw
    from PySide6 import QtCore as qc
    from PySide6 import QtGui as qg
    HAS_QT = True
    QT_VERSION = "PySide6"
    Signal = qc.Signal
except ImportError:
    try:
        from PyQt5 import QtWidgets as qw
        from PyQt5 import QtCore as qc
        from PyQt5 import QtGui as qg
        HAS_QT = True
        QT_VERSION = "PyQt5"
        Signal = qc.pyqtSignal
    except ImportError:
        HAS_QT = False
        QT_VERSION = None
        Signal = None

# Import tuning parameters
try:
    from flash_tool.tuning_parameters import (
        ALL_PARAMETERS, ALL_PRESETS, TuningParameter, TuningPreset,
        ParameterCategory, SafetyLevel, ParameterType,
        get_parameters_by_category, read_all_parameters, write_parameters
    )
    HAS_TUNING = True
except ImportError:
    HAS_TUNING = False


# ============================================================================
# REUSABLE COMPONENTS
# ============================================================================

class ParameterSpinBox(qw.QWidget):
    """Spinbox for scalar parameters with unit display and validation"""
    
    valueChanged = Signal(object) if Signal else None
    
    def __init__(self, param: 'TuningParameter', parent=None):
        super().__init__(parent)
        self.param = param
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Determine if we need float or int
        if self.param.conversion and self.param.conversion.decimal_places > 0:
            self.spin = qw.QDoubleSpinBox()
            self.spin.setDecimals(self.param.conversion.decimal_places)
        else:
            self.spin = qw.QSpinBox()
        
        # Set range based on validation
        if self.param.validation:
            if self.param.validation.min_value is not None:
                display_min = self.param.to_display_value(self.param.validation.min_value)
                self.spin.setMinimum(int(display_min) if isinstance(self.spin, qw.QSpinBox) else display_min)
            if self.param.validation.max_value is not None:
                display_max = self.param.to_display_value(self.param.validation.max_value)
                self.spin.setMaximum(int(display_max) if isinstance(self.spin, qw.QSpinBox) else display_max)
        else:
            self.spin.setMinimum(0)
            self.spin.setMaximum(65535)
        
        # Unit suffix
        if self.param.conversion:
            self.spin.setSuffix(f" {self.param.conversion.display_unit}")
        
        # Tooltip with description
        self.spin.setToolTip(f"{self.param.description}\n\nStock: {self.param.stock_value}")
        
        layout.addWidget(self.spin)
        
        # Warning indicator
        self.warning_label = qw.QLabel()
        self.warning_label.setFixedWidth(20)
        layout.addWidget(self.warning_label)
        
        # Connect signal
        self.spin.valueChanged.connect(self._on_value_changed)
    
    def _on_value_changed(self, value):
        # Validate and show warning
        raw_value = self.param.from_display_value(value)
        valid, msg = self.param.validate(raw_value)
        
        if not valid:
            self.warning_label.setText("INVALID")
            self.warning_label.setToolTip(msg)
            self.spin.setStyleSheet("background-color: #ffcccc;")
        elif msg:  # Warning
            self.warning_label.setText("WARNING")
            self.warning_label.setToolTip(msg)
            self.spin.setStyleSheet("background-color: #ffffcc;")
        else:
            self.warning_label.setText("")
            self.warning_label.setToolTip("")
            self.spin.setStyleSheet("")
        
        if self.valueChanged:
            self.valueChanged.emit(raw_value)
    
    def setValue(self, raw_value):
        """Set value from raw (storage) format"""
        display_value = self.param.to_display_value(raw_value)
        self.spin.blockSignals(True)
        self.spin.setValue(display_value)
        self.spin.blockSignals(False)
    
    def value(self):
        """Get value in raw (storage) format"""
        return self.param.from_display_value(self.spin.value())


class ParameterCheckBox(qw.QCheckBox):
    """Checkbox for boolean/toggle parameters"""
    
    def __init__(self, param: 'TuningParameter', parent=None):
        super().__init__(parent)
        self.param = param
        self.setText(param.name)
        self.setToolTip(f"{param.description}\n\nStock: {param.stock_value}")
    
    def setValue(self, raw_value):
        self.setChecked(bool(raw_value))
    
    def value(self):
        return 1 if self.isChecked() else 0


class ArrayEditor(qw.QWidget):
    """Editor for 1D array parameters (like rev limiter per gear)"""
    
    valueChanged = Signal(object) if Signal else None
    
    def __init__(self, param: 'TuningParameter', labels: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.param = param
        self.labels = labels or [str(i) for i in range(param.count)]
        self.spins = []
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QGridLayout(self)
        layout.setSpacing(4)
        
        # Create spinbox for each element
        for i in range(self.param.count):
            # Label
            label = qw.QLabel(self.labels[i] if i < len(self.labels) else str(i))
            label.setAlignment(qc.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label, 0, i)
            
            # Spinbox
            if self.param.conversion and self.param.conversion.decimal_places > 0:
                spin = qw.QDoubleSpinBox()
                spin.setDecimals(self.param.conversion.decimal_places)
            else:
                spin = qw.QSpinBox()
            
            # Set range
            if self.param.validation:
                if self.param.validation.min_value is not None:
                    spin.setMinimum(int(self.param.validation.min_value))
                if self.param.validation.max_value is not None:
                    spin.setMaximum(int(self.param.validation.max_value))
            else:
                spin.setMinimum(0)
                spin.setMaximum(65535)
            
            spin.setFixedWidth(80)
            spin.valueChanged.connect(lambda v, idx=i: self._on_value_changed(idx, v))
            layout.addWidget(spin, 1, i)
            self.spins.append(spin)
        
        # Unit label
        if self.param.conversion:
            unit_label = qw.QLabel(self.param.conversion.display_unit)
            unit_label.setStyleSheet("color: gray;")
            layout.addWidget(unit_label, 1, self.param.count)
        
        # Quick set all button
        set_all_layout = qw.QHBoxLayout()
        self.set_all_spin = qw.QSpinBox()
        self.set_all_spin.setRange(self.spins[0].minimum(), self.spins[0].maximum())
        set_all_layout.addWidget(qw.QLabel("Set All:"))
        set_all_layout.addWidget(self.set_all_spin)
        set_all_btn = qw.QPushButton("Apply")
        set_all_btn.clicked.connect(self._apply_all)
        set_all_layout.addWidget(set_all_btn)
        set_all_layout.addStretch()
        layout.addLayout(set_all_layout, 2, 0, 1, self.param.count + 1)
    
    def _on_value_changed(self, index: int, value):
        if self.valueChanged:
            self.valueChanged.emit(self.value())
    
    def _apply_all(self):
        val = self.set_all_spin.value()
        for spin in self.spins:
            spin.setValue(val)
    
    def setValue(self, values: List):
        """Set values from raw (storage) format list"""
        if not isinstance(values, list):
            # Handle single value by converting to list
            values = [values]
        
        for i, val in enumerate(values):
            if i < len(self.spins):
                self.spins[i].blockSignals(True)
                # For identity conversions (RPM, etc.), raw value = display value
                # Just ensure it's a number
                if isinstance(val, (int, float)):
                    self.spins[i].setValue(int(val))
                else:
                    # Try to convert from display if needed
                    display_val = self.param.to_display_value(val) if self.param.conversion else val
                    self.spins[i].setValue(int(display_val) if isinstance(display_val, (int, float)) else 0)
                self.spins[i].blockSignals(False)
    
    def value(self) -> List:
        return [spin.value() for spin in self.spins]


class TableEditor(qw.QWidget):
    """Editor for 2D table parameters with heatmap visualization"""
    
    valueChanged = Signal(object) if Signal else None
    
    def __init__(self, param: 'TuningParameter', 
                 row_labels: Optional[List[str]] = None,
                 col_labels: Optional[List[str]] = None,
                 parent=None):
        super().__init__(parent)
        self.param = param
        self.row_labels = row_labels
        self.col_labels = col_labels
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Table widget
        self.table = qw.QTableWidget(self.param.rows, self.param.cols)
        self.table.setEditTriggers(qw.QTableWidget.EditTrigger.DoubleClicked | 
                                    qw.QTableWidget.EditTrigger.EditKeyPressed)
        
        # Set headers
        if self.col_labels:
            self.table.setHorizontalHeaderLabels(self.col_labels[:self.param.cols])
        if self.row_labels:
            self.table.setVerticalHeaderLabels(self.row_labels[:self.param.rows])
        
        self.table.horizontalHeader().setSectionResizeMode(qw.QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        
        layout.addWidget(self.table)
        
        # Controls
        ctrl_layout = qw.QHBoxLayout()
        
        # Copy/Paste buttons
        copy_btn = qw.QPushButton("Copy")
        copy_btn.clicked.connect(self._copy_table)
        ctrl_layout.addWidget(copy_btn)
        
        paste_btn = qw.QPushButton("Paste")
        paste_btn.clicked.connect(self._paste_table)
        ctrl_layout.addWidget(paste_btn)
        
        ctrl_layout.addStretch()
        
        # Multiply all
        ctrl_layout.addWidget(qw.QLabel("Multiply All:"))
        self.mult_spin = qw.QDoubleSpinBox()
        self.mult_spin.setRange(0.5, 2.0)
        self.mult_spin.setValue(1.0)
        self.mult_spin.setSingleStep(0.05)
        ctrl_layout.addWidget(self.mult_spin)
        mult_btn = qw.QPushButton("Apply")
        mult_btn.clicked.connect(self._multiply_all)
        ctrl_layout.addWidget(mult_btn)
        
        layout.addLayout(ctrl_layout)
    
    def _on_item_changed(self, item):
        if self.valueChanged:
            self.valueChanged.emit(self.value())
    
    def _copy_table(self):
        """Copy table to clipboard as TSV"""
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row.append(item.text() if item else "0")
            rows.append("\t".join(row))
        
        clipboard = qw.QApplication.clipboard()
        clipboard.setText("\n".join(rows))
    
    def _paste_table(self):
        """Paste TSV data from clipboard"""
        clipboard = qw.QApplication.clipboard()
        text = clipboard.text()
        
        rows = text.strip().split("\n")
        self.table.blockSignals(True)
        for r, row in enumerate(rows):
            if r >= self.table.rowCount():
                break
            cols = row.split("\t")
            for c, val in enumerate(cols):
                if c >= self.table.columnCount():
                    break
                try:
                    num = float(val)
                    item = qw.QTableWidgetItem(f"{num:.1f}")
                    item.setTextAlignment(qc.Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, c, item)
                except ValueError:
                    pass
        self.table.blockSignals(False)
        
        if self.valueChanged:
            self.valueChanged.emit(self.value())
    
    def _multiply_all(self):
        """Multiply all values by factor"""
        factor = self.mult_spin.value()
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item:
                    try:
                        val = float(item.text()) * factor
                        item.setText(f"{val:.1f}")
                    except ValueError:
                        pass
        self.table.blockSignals(False)
        
        if self.valueChanged:
            self.valueChanged.emit(self.value())
    
    def setValue(self, values: List):
        """Set values from flat list (raw storage format)"""
        if not isinstance(values, list):
            values = [values]
        
        self.table.blockSignals(True)
        for i, val in enumerate(values):
            r = i // self.param.cols
            c = i % self.param.cols
            if r < self.param.rows and c < self.param.cols:
                # Convert individual raw value to display
                if isinstance(val, (int, float)):
                    # Apply conversion if exists
                    if self.param.conversion:
                        display_val = self.param.conversion.to_display(val)
                    else:
                        display_val = val
                else:
                    display_val = val
                
                # Create table item with formatted value
                if isinstance(display_val, float):
                    item = qw.QTableWidgetItem(f"{display_val:.1f}")
                else:
                    item = qw.QTableWidgetItem(str(display_val))
                item.setTextAlignment(qc.Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)
        self.table.blockSignals(False)
    
    def value(self) -> List:
        """Get values as flat list"""
        values = []
        for r in range(self.param.rows):
            for c in range(self.param.cols):
                item = self.table.item(r, c)
                if item:
                    try:
                        val = float(item.text())
                        raw = self.param.from_display_value(val)
                        values.append(raw)
                    except ValueError:
                        values.append(0)
                else:
                    values.append(0)
        return values


# ============================================================================
# CATEGORY TAB WIDGETS
# ============================================================================

class PerformanceTab(qw.QWidget):
    """Performance tab: Speed Limiter, Rev Limiter"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Speed Limiter Group
        speed_group = qw.QGroupBox("Speed Limiter")
        speed_layout = qw.QFormLayout(speed_group)
        
        if 'speed_limiter_master' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['speed_limiter_master']
            editor = ParameterSpinBox(param)
            speed_layout.addRow("Maximum Speed:", editor)
            self.editors['speed_limiter_master'] = editor
        
        if 'speed_limiter_disable' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['speed_limiter_disable']
            editor = ParameterCheckBox(param)
            editor.setText("Remove Speed Limiter (set to 255+ MPH)")
            speed_layout.addRow("", editor)
            self.editors['speed_limiter_disable'] = editor
        
        layout.addWidget(speed_group)
        
        # Rev Limiter Group
        rev_group = qw.QGroupBox("Rev Limiter")
        rev_layout = qw.QVBoxLayout(rev_group)
        
        # Transmission selector
        trans_layout = qw.QHBoxLayout()
        trans_layout.addWidget(qw.QLabel("Transmission:"))
        self.trans_combo = qw.QComboBox()
        self.trans_combo.addItems(["Manual (MT)", "Automatic (AT)"])
        self.trans_combo.currentIndexChanged.connect(self._on_trans_changed)
        trans_layout.addWidget(self.trans_combo)
        trans_layout.addStretch()
        rev_layout.addLayout(trans_layout)
        
        # Gear labels
        gear_labels = ["P/R/N", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
        
        # Clutch Pressed
        if 'rev_limiter_clutch_pressed' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['rev_limiter_clutch_pressed']
            clutch_group = qw.QGroupBox("Clutch Pressed (all gears)")
            clutch_layout = qw.QVBoxLayout(clutch_group)
            editor = ArrayEditor(param, labels=gear_labels[:8])
            clutch_layout.addWidget(editor)
            rev_layout.addWidget(clutch_group)
            self.editors['rev_limiter_clutch_pressed'] = editor
        
        # Floor/Ceiling MT (shown by default)
        self.mt_widget = qw.QWidget()
        mt_layout = qw.QVBoxLayout(self.mt_widget)
        mt_layout.setContentsMargins(0, 0, 0, 0)
        
        if 'rev_limiter_floor_mt' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['rev_limiter_floor_mt']
            floor_group = qw.QGroupBox("Rev Limit Floor (MT)")
            floor_layout = qw.QVBoxLayout(floor_group)
            editor = ArrayEditor(param, labels=gear_labels)
            floor_layout.addWidget(editor)
            mt_layout.addWidget(floor_group)
            self.editors['rev_limiter_floor_mt'] = editor
        
        if 'rev_limiter_ceiling_mt' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['rev_limiter_ceiling_mt']
            ceil_group = qw.QGroupBox("Rev Limit Ceiling (MT)")
            ceil_layout = qw.QVBoxLayout(ceil_group)
            editor = ArrayEditor(param, labels=gear_labels)
            ceil_layout.addWidget(editor)
            mt_layout.addWidget(ceil_group)
            self.editors['rev_limiter_ceiling_mt'] = editor
        
        rev_layout.addWidget(self.mt_widget)
        
        # Floor/Ceiling AT (hidden by default)
        self.at_widget = qw.QWidget()
        at_layout = qw.QVBoxLayout(self.at_widget)
        at_layout.setContentsMargins(0, 0, 0, 0)
        
        if 'rev_limiter_floor_at' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['rev_limiter_floor_at']
            floor_group = qw.QGroupBox("Rev Limit Floor (AT)")
            floor_layout = qw.QVBoxLayout(floor_group)
            editor = ArrayEditor(param, labels=gear_labels)
            floor_layout.addWidget(editor)
            at_layout.addWidget(floor_group)
            self.editors['rev_limiter_floor_at'] = editor
        
        if 'rev_limiter_ceiling_at' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['rev_limiter_ceiling_at']
            ceil_group = qw.QGroupBox("Rev Limit Ceiling (AT)")
            ceil_layout = qw.QVBoxLayout(ceil_group)
            editor = ArrayEditor(param, labels=gear_labels)
            ceil_layout.addWidget(editor)
            at_layout.addWidget(ceil_group)
            self.editors['rev_limiter_ceiling_at'] = editor
        
        self.at_widget.hide()
        rev_layout.addWidget(self.at_widget)
        
        layout.addWidget(rev_group)
        layout.addStretch()
    
    def _on_trans_changed(self, index):
        if index == 0:  # MT
            self.mt_widget.show()
            self.at_widget.hide()
        else:  # AT
            self.mt_widget.hide()
            self.at_widget.show()
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values:
                editor.setValue(values[key])
    
    def get_values(self) -> Dict[str, Any]:
        return {key: editor.value() for key, editor in self.editors.items()}


class AntilagTab(qw.QWidget):
    """Antilag/Launch Control tab"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Enable switch
        if 'antilag_enable' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['antilag_enable']
            editor = ParameterCheckBox(param)
            editor.setText("Enable Antilag / Launch Control")
            layout.addWidget(editor)
            self.editors['antilag_enable'] = editor
            editor.stateChanged.connect(self._on_enable_changed)
        
        # Settings group
        self.settings_group = qw.QGroupBox("Antilag Settings")
        settings_layout = qw.QFormLayout(self.settings_group)
        
        antilag_params = [
            ('antilag_boost_target', "Boost Target:"),
            ('antilag_cooldown', "Cooldown Timer:"),
            ('antilag_fuel_target', "Fuel Target (AFR):"),
        ]
        
        for key, label in antilag_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = ParameterSpinBox(param)
                settings_layout.addRow(label, editor)
                self.editors[key] = editor
        
        layout.addWidget(self.settings_group)
        
        # Safety Limits group
        safety_group = qw.QGroupBox("Safety Limits")
        safety_layout = qw.QFormLayout(safety_group)
        
        safety_params = [
            ('antilag_coolant_min', "Min Coolant Temp:"),
            ('antilag_coolant_max', "Max Coolant Temp:"),
            ('antilag_egt_max', "Max EGT:"),
        ]
        
        for key, label in safety_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = ParameterSpinBox(param)
                safety_layout.addRow(label, editor)
                self.editors[key] = editor
        
        layout.addWidget(safety_group)
        layout.addStretch()
        
        # Initial state
        self.settings_group.setEnabled(False)
    
    def _on_enable_changed(self, state):
        enabled = state == qc.Qt.CheckState.Checked.value if QT_VERSION == "PySide6" else state == qc.Qt.Checked
        self.settings_group.setEnabled(enabled)
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values:
                editor.setValue(values[key])
        
        # Update enabled state
        if 'antilag_enable' in values:
            self.settings_group.setEnabled(bool(values['antilag_enable']))
    
    def get_values(self) -> Dict[str, Any]:
        return {key: editor.value() for key, editor in self.editors.items()}


class FeaturesTab(qw.QWidget):
    """Features tab: Burble, DTC codes, Throttle, etc."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Burble/Pops group
        burble_group = qw.QGroupBox("Exhaust Burbles / Pops")
        burble_layout = qw.QFormLayout(burble_group)
        
        burble_params = [
            ('burble_duration_normal', "Duration (Normal Mode):"),
            ('burble_duration_sport', "Duration (Sport Mode):"),
            ('burble_ignition_retard', "Ignition Retard:"),
        ]
        
        for key, label in burble_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = ParameterSpinBox(param)
                burble_layout.addRow(label, editor)
                self.editors[key] = editor
        
        layout.addWidget(burble_group)
        
        # Advanced Burble Timing (2D table)
        if 'burble_timing_base' in ALL_PARAMETERS:
            burble_adv_group = qw.QGroupBox("Advanced Burble Timing (RPM × Load)")
            burble_adv_layout = qw.QVBoxLayout(burble_adv_group)
            
            burble_info = qw.QLabel(
                "Timing retard per RPM and load. More negative = more aggressive pops."
            )
            burble_info.setStyleSheet("color: #666; padding: 5px;")
            burble_adv_layout.addWidget(burble_info)
            
            param = ALL_PARAMETERS['burble_timing_base']
            try:
                from flash_tool.tuning_parameters import BURBLE_TIMING_RPM_AXIS
                rpm_labels = [str(r) for r in BURBLE_TIMING_RPM_AXIS]
            except ImportError:
                rpm_labels = [f"RPM{i}" for i in range(8)]
            load_labels = [f"Load{i}" for i in range(6)]
            
            editor = TableEditor(param, row_labels=load_labels, col_labels=rpm_labels)
            self.editors['burble_timing_base'] = editor
            burble_adv_layout.addWidget(editor)
            
            layout.addWidget(burble_adv_group)
        
        # Throttle group
        if 'throttle_angle_wot' in ALL_PARAMETERS:
            throttle_group = qw.QGroupBox("Throttle Angle (WOT)")
            throttle_layout = qw.QVBoxLayout(throttle_group)
            
            throttle_info = qw.QLabel(
                "Wide Open Throttle angle targets per RPM range."
            )
            throttle_info.setStyleSheet("color: #666; padding: 5px;")
            throttle_layout.addWidget(throttle_info)
            
            param = ALL_PARAMETERS['throttle_angle_wot']
            # 1x7 table
            rpm_labels = [f"RPM{i}" for i in range(7)]
            editor = TableEditor(param, row_labels=["Angle"], col_labels=rpm_labels)
            self.editors['throttle_angle_wot'] = editor
            throttle_layout.addWidget(editor)
            
            # Throttle Sensitivity (scalar)
            if 'throttle_sensitivity' in ALL_PARAMETERS:
                param = ALL_PARAMETERS['throttle_sensitivity']
                throttle_sens_layout = qw.QHBoxLayout()
                throttle_sens_layout.addWidget(qw.QLabel("Throttle Sensitivity:"))
                editor = ParameterSpinBox(param)
                self.editors['throttle_sensitivity'] = editor
                throttle_sens_layout.addWidget(editor)
                throttle_sens_layout.addStretch()
                throttle_layout.addLayout(throttle_sens_layout)
            
            layout.addWidget(throttle_group)
        
        # DTC Codes group
        dtc_group = qw.QGroupBox("Diagnostic Trouble Codes")
        dtc_layout = qw.QVBoxLayout(dtc_group)
        
        dtc_info = qw.QLabel(
            "Disable fault codes that may trigger with modified tune.\n"
            "Stock = 0xFFFF (enabled), Disabled = 0x0000"
        )
        dtc_info.setStyleSheet("color: #666; padding: 5px;")
        dtc_info.setWordWrap(True)
        dtc_layout.addWidget(dtc_info)
        
        dtc_params = [
            ('dtc_overboost', "30FE (Overboost)"),
            ('dtc_underboost', "30FF (Underboost)"),
            ('dtc_boost_deactivation', "3100 (Boost Deactivation)"),
            ('dtc_ibs_battery_sensor', "2E8E (IBS Battery Sensor)"),
            ('dtc_coding_missing', "2FA3 (Coding Missing)"),
        ]
        
        for key, label in dtc_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                check = qw.QCheckBox(f"Disable {label}")
                check.setToolTip(param.description)
                dtc_layout.addWidget(check)
                self.editors[key] = check
        
        layout.addWidget(dtc_group)
        layout.addStretch()
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values:
                if isinstance(editor, qw.QCheckBox):
                    # DTC: 0x0000 = disabled (checked), 0xFFFF = enabled (unchecked)
                    editor.setChecked(values[key] == 0)
                else:
                    editor.setValue(values[key])
    
    def get_values(self) -> Dict[str, Any]:
        result = {}
        for key, editor in self.editors.items():
            if isinstance(editor, qw.QCheckBox):
                # DTC: checked = disable (0x0000), unchecked = enable (0xFFFF)
                result[key] = 0x0000 if editor.isChecked() else 0xFFFF
            else:
                result[key] = editor.value()
        return result


class IgnitionTab(qw.QWidget):
    """Ignition timing tab with 2D table editors for validated timing maps"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._current_map = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Warning
        warning = qw.QLabel(
            "WARNING: Modifying ignition timing can cause engine knock and damage.\n"
            "Only adjust if you understand the implications and have proper monitoring."
        )
        warning.setStyleSheet("color: #c00; padding: 10px; background: #fff0f0; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Map selector (validated maps only)
        map_layout = qw.QHBoxLayout()
        map_layout.addWidget(qw.QLabel("Timing Map:"))
        self.map_combo = qw.QComboBox()
        
        # Use XDF-validated timing maps from tuning_parameters
        self.map_keys = ['timing_main', 'timing_spool']
        self.map_names = [
            "Main Timing Map (KF_ZW_VT98)",
            "Spool Timing Map (KF_ZW_VTUESP)"
        ]
        self.map_combo.addItems(self.map_names)
        self.map_combo.currentIndexChanged.connect(self._on_map_changed)
        map_layout.addWidget(self.map_combo)
        map_layout.addStretch()
        layout.addLayout(map_layout)
        
        # Map info
        self.map_info = qw.QLabel()
        self.map_info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.map_info)
        
        # Create table editors for each map (in a stacked widget)
        self.stack = qw.QStackedWidget()
        
        # Get axis labels from tuning_parameters
        try:
            from flash_tool.tuning_parameters import TIMING_RPM_AXIS, TIMING_LOAD_AXIS
            rpm_labels = [str(r) for r in TIMING_RPM_AXIS]
            load_labels = [str(l) for l in TIMING_LOAD_AXIS]
        except ImportError:
            rpm_labels = [f"RPM{i}" for i in range(9)]
            load_labels = [f"Load{i}" for i in range(8)]
        
        for key in self.map_keys:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = TableEditor(param, row_labels=load_labels, col_labels=rpm_labels)
                self.editors[key] = editor
                self.stack.addWidget(editor)
            else:
                placeholder = qw.QLabel(f"Map '{key}' not available")
                placeholder.setAlignment(qc.Qt.AlignmentFlag.AlignCenter)
                self.stack.addWidget(placeholder)
        
        layout.addWidget(self.stack, 1)  # Stretch factor 1
        
        # Quick adjust controls
        adjust_layout = qw.QHBoxLayout()
        adjust_layout.addWidget(qw.QLabel("Quick Adjust All:"))
        
        self.adjust_spin = qw.QDoubleSpinBox()
        self.adjust_spin.setRange(-10.0, 10.0)
        self.adjust_spin.setValue(0.0)
        self.adjust_spin.setSingleStep(0.5)
        self.adjust_spin.setSuffix("°")
        adjust_layout.addWidget(self.adjust_spin)
        
        add_btn = qw.QPushButton("Add to All")
        add_btn.clicked.connect(self._add_to_all)
        adjust_layout.addWidget(add_btn)
        
        adjust_layout.addStretch()
        layout.addLayout(adjust_layout)
        
        # Show first map info
        self._on_map_changed(0)
    
    def _on_map_changed(self, index):
        if 0 <= index < len(self.map_keys):
            self.stack.setCurrentIndex(index)
            key = self.map_keys[index]
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                self.map_info.setText(
                    f"{param.name}\n"
                    f"Offset: 0x{param.offset:06X} | Size: {param.rows}x{param.cols} ({param.count} values)"
                )
                self._current_map = key
    
    def _add_to_all(self):
        """Add degrees to all cells in current map"""
        if self._current_map and self._current_map in self.editors:
            editor = self.editors[self._current_map]
            delta = self.adjust_spin.value()
            table = editor.table
            table.blockSignals(True)
            for r in range(table.rowCount()):
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    if item:
                        try:
                            val = float(item.text()) + delta
                            item.setText(f"{val:.1f}")
                        except ValueError:
                            pass
            table.blockSignals(False)
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values and isinstance(values[key], list):
                editor.setValue(values[key])
    
    def get_values(self) -> Dict[str, Any]:
        result = {}
        for key, editor in self.editors.items():
            result[key] = editor.value()
        return result


class TorqueTab(qw.QWidget):
    """Torque limits tab for controlling maximum torque output"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Info panel
        info = qw.QLabel(
            "Torque Limits\n"
            "Controls maximum torque output per gear and RPM. Higher values = more power."
        )
        info.setStyleSheet("color: #666; padding: 10px; background: #fff8e0; border-radius: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Torque limit table (driver demand)
        group = qw.QGroupBox("Torque Limit (Driver Demand) - by RPM")
        group_layout = qw.QVBoxLayout(group)
        
        if 'torque_limit_driver' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['torque_limit_driver']
            # Get axis labels
            try:
                from flash_tool.tuning_parameters import TORQUE_LIMIT_DRIVER_RPM_AXIS
                rpm_labels = [str(r) for r in TORQUE_LIMIT_DRIVER_RPM_AXIS]
            except ImportError:
                rpm_labels = [f"RPM{i}" for i in range(11)]
            
            editor = TableEditor(param, row_labels=["Torque"], col_labels=rpm_labels)
            self.editors['torque_limit_driver'] = editor
            group_layout.addWidget(editor)
        else:
            group_layout.addWidget(qw.QLabel("Parameter not available"))
        
        layout.addWidget(group)
        
        # Torque cap scalar
        cap_layout = qw.QHBoxLayout()
        cap_layout.addWidget(qw.QLabel("Torque Cap (Maximum):"))
        
        if 'torque_limit_cap' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['torque_limit_cap']
            self.cap_spin = qw.QDoubleSpinBox()
            self.cap_spin.setRange(0, 1000)
            self.cap_spin.setValue(550)  # Stock ~550 ft-lb
            self.cap_spin.setSuffix(" ft-lb")
            self.cap_spin.setDecimals(1)
            cap_layout.addWidget(self.cap_spin)
            self.editors['torque_limit_cap'] = self.cap_spin
        else:
            cap_layout.addWidget(qw.QLabel("N/A"))
        
        cap_layout.addStretch()
        layout.addLayout(cap_layout)
        layout.addStretch()
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values:
                if isinstance(editor, TableEditor) and isinstance(values[key], list):
                    editor.setValue(values[key])
                elif isinstance(editor, qw.QDoubleSpinBox) and isinstance(values[key], (int, float)):
                    editor.setValue(float(values[key]))
            else:
                # Clear if not in preset
                if isinstance(editor, TableEditor):
                    param = ALL_PARAMETERS.get(key)
                    if param:
                        zero_values = [0] * param.count
                        editor.setValue(zero_values)
                elif isinstance(editor, qw.QDoubleSpinBox):
                    editor.setValue(0.0)
    
    def get_values(self) -> Dict[str, Any]:
        result = {}
        for key, editor in self.editors.items():
            if isinstance(editor, TableEditor):
                result[key] = editor.value()
            elif isinstance(editor, qw.QDoubleSpinBox):
                result[key] = editor.value()
        return result


class LoadTargetTab(qw.QWidget):
    """Load target tab with per-gear and boost modifier tables"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._current_map = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Info panel
        info = qw.QLabel(
            "Load Target Maps\n"
            "Controls target boost/load per gear and RPM. Modify for per-gear power delivery."
        )
        info.setStyleSheet("color: #666; padding: 10px; background: #e8f4ea; border-radius: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Map selector
        map_layout = qw.QHBoxLayout()
        map_layout.addWidget(qw.QLabel("Map:"))
        self.map_combo = qw.QComboBox()
        
        self.map_keys = ['load_target_per_gear', 'boost_pressure_target_modifier']
        self.map_names = [
            "Load Target per Gear (6 gears × 16 RPM)",
            "Boost Pressure Target Modifier (6×6)"
        ]
        self.map_combo.addItems(self.map_names)
        self.map_combo.currentIndexChanged.connect(self._on_map_changed)
        map_layout.addWidget(self.map_combo)
        map_layout.addStretch()
        layout.addLayout(map_layout)
        
        # Map info
        self.map_info = qw.QLabel()
        self.map_info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.map_info)
        
        # Stacked widget for tables
        self.stack = qw.QStackedWidget()
        
        # Load Target per Gear table
        if 'load_target_per_gear' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['load_target_per_gear']
            try:
                from flash_tool.tuning_parameters import LOAD_TARGET_RPM_AXIS, LOAD_TARGET_GEAR_AXIS
                rpm_labels = [str(r) for r in LOAD_TARGET_RPM_AXIS]
                gear_labels = [str(g) for g in LOAD_TARGET_GEAR_AXIS]
            except ImportError:
                rpm_labels = [f"RPM{i}" for i in range(16)]
                gear_labels = [f"Gear{i}" for i in range(6)]
            
            editor = TableEditor(param, row_labels=gear_labels, col_labels=rpm_labels)
            self.editors['load_target_per_gear'] = editor
            self.stack.addWidget(editor)
        else:
            self.stack.addWidget(qw.QLabel("Load Target per Gear not available"))
        
        # Boost Pressure Target Modifier table
        if 'boost_pressure_target_modifier' in ALL_PARAMETERS:
            param = ALL_PARAMETERS['boost_pressure_target_modifier']
            try:
                from flash_tool.tuning_parameters import BOOST_TARGET_RPM_AXIS
                rpm_labels = [str(r) for r in BOOST_TARGET_RPM_AXIS]
            except ImportError:
                rpm_labels = [f"RPM{i}" for i in range(6)]
            load_labels = [f"Load{i}" for i in range(6)]
            
            editor = TableEditor(param, row_labels=load_labels, col_labels=rpm_labels)
            self.editors['boost_pressure_target_modifier'] = editor
            self.stack.addWidget(editor)
        else:
            self.stack.addWidget(qw.QLabel("Boost Target Modifier not available"))
        
        layout.addWidget(self.stack, 1)
        
        # Advanced boost control parameters
        adv_group = qw.QGroupBox("Advanced Boost Control")
        adv_layout = qw.QFormLayout(adv_group)
        
        adv_params = [
            ('boost_ceiling', "Boost Ceiling (bar):"),
            ('boost_limit_multiplier', "Boost Limit Multiplier:"),
            ('load_limit_factor', "Load Limit Factor:"),
        ]
        
        for key, label in adv_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = ParameterSpinBox(param)
                adv_layout.addRow(label, editor)
                self.editors[key] = editor
        
        layout.addWidget(adv_group)
        
        # Show first map info
        self._on_map_changed(0)
    
    def _on_map_changed(self, index):
        if 0 <= index < len(self.map_keys):
            self.stack.setCurrentIndex(index)
            key = self.map_keys[index]
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                self.map_info.setText(
                    f"{param.name}\n"
                    f"Offset: 0x{param.offset:06X} | Size: {param.rows}x{param.cols} ({param.count} values)"
                )
                self._current_map = key
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values:
                if isinstance(values[key], list):
                    editor.setValue(values[key])
                else:
                    editor.setValue(values[key])
    
    def get_values(self) -> Dict[str, Any]:
        result = {}
        for key, editor in self.editors.items():
            result[key] = editor.value()
        return result


class FlexFuelTab(qw.QWidget):
    """FlexFuel / E85 configuration tab"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Info panel
        info = qw.QLabel(
            "FlexFuel / Ethanol Support\n"
            "Configure E85/ethanol settings. Requires proper fuel system for high ethanol content!"
        )
        info.setStyleSheet("color: #666; padding: 10px; background: #f0f0ff; border-radius: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # FlexFuel enable checkbox
        flex_layout = qw.QHBoxLayout()
        self.flex_enable = qw.QCheckBox("Enable FlexFuel Mode")
        self.flex_enable.setToolTip("MHD+ feature - requires FlexFuel sensor or static ethanol content")
        flex_layout.addWidget(self.flex_enable)
        self.editors['flexfuel_enable'] = self.flex_enable
        flex_layout.addStretch()
        layout.addLayout(flex_layout)
        
        # Static ethanol content
        eth_layout = qw.QHBoxLayout()
        eth_layout.addWidget(qw.QLabel("Static Ethanol Content:"))
        
        self.ethanol_spin = qw.QSpinBox()
        self.ethanol_spin.setRange(0, 100)
        self.ethanol_spin.setValue(0)
        self.ethanol_spin.setSuffix("%")
        self.ethanol_spin.setToolTip("Set static ethanol percentage if no FlexFuel sensor installed")
        eth_layout.addWidget(self.ethanol_spin)
        self.editors['static_ethanol_content'] = self.ethanol_spin
        
        eth_layout.addStretch()
        layout.addLayout(eth_layout)
        
        # Ethanol content presets
        preset_layout = qw.QHBoxLayout()
        preset_layout.addWidget(qw.QLabel("Common Presets:"))
        
        e0_btn = qw.QPushButton("E0 (0%)")
        e0_btn.clicked.connect(lambda: self.ethanol_spin.setValue(0))
        preset_layout.addWidget(e0_btn)
        
        e30_btn = qw.QPushButton("E30 (30%)")
        e30_btn.clicked.connect(lambda: self.ethanol_spin.setValue(30))
        preset_layout.addWidget(e30_btn)
        
        e50_btn = qw.QPushButton("E50 (50%)")
        e50_btn.clicked.connect(lambda: self.ethanol_spin.setValue(50))
        preset_layout.addWidget(e50_btn)
        
        e85_btn = qw.QPushButton("E85 (85%)")
        e85_btn.clicked.connect(lambda: self.ethanol_spin.setValue(85))
        preset_layout.addWidget(e85_btn)
        
        preset_layout.addStretch()
        layout.addLayout(preset_layout)
        
        # Warning about high ethanol
        warning = qw.QLabel(
            "WARNING: Running high ethanol content (E50+) requires:\n"
            "• Upgraded fuel pump (LPFP/HPFP)\n"
            "• Larger injectors or port injection\n"
            "• FlexFuel sensor (recommended) or accurate static content"
        )
        warning.setStyleSheet("color: #c00; padding: 10px; background: #fff0f0; border-radius: 5px; margin-top: 20px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        layout.addStretch()
    
    def load_values(self, values: Dict[str, Any]):
        if 'flexfuel_enable' in values:
            self.flex_enable.setChecked(bool(values['flexfuel_enable']))
        if 'static_ethanol_content' in values:
            self.ethanol_spin.setValue(int(values['static_ethanol_content']))
    
    def get_values(self) -> Dict[str, Any]:
        return {
            'flexfuel_enable': self.flex_enable.isChecked(),
            'static_ethanol_content': self.ethanol_spin.value()
        }


class WGDCTab(qw.QWidget):
    """WGDC (Wastegate Duty Cycle) tab with 2D table editors for boost control"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self._current_map = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        
        # Info panel
        info = qw.QLabel(
            "WGDC = Wastegate Duty Cycle (controls turbo boost pressure)\n"
            "Higher values = more boost. Be careful with high boost on stock hardware!"
        )
        info.setStyleSheet("color: #666; padding: 10px; background: #f0f8ff; border-radius: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # PID Control parameters
        pid_group = qw.QGroupBox("WGDC PID Control")
        pid_layout = qw.QFormLayout(pid_group)
        
        pid_params = [
            ('wgdc_p_factor', "P Factor (Proportional):"),
            ('wgdc_i_factor', "I Factor (Integral):"),
            ('wgdc_d_factor', "D Factor (Derivative):"),
            ('wgdc_d_multiplier', "D Multiplier:"),
        ]
        
        for key, label in pid_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = ParameterSpinBox(param)
                pid_layout.addRow(label, editor)
                self.editors[key] = editor
        
        layout.addWidget(pid_group)
        
        # Map selector
        map_layout = qw.QHBoxLayout()
        map_layout.addWidget(qw.QLabel("WGDC Map:"))
        self.map_combo = qw.QComboBox()
        
        # Use XDF-validated WGDC maps from tuning_parameters
        self.map_keys = ['wgdc_base', 'wgdc_spool']
        self.map_names = [
            "WGDC Base (Main Control)",
            "WGDC Spool (Transient Additive)"
        ]
        self.map_combo.addItems(self.map_names)
        self.map_combo.currentIndexChanged.connect(self._on_map_changed)
        map_layout.addWidget(self.map_combo)
        map_layout.addStretch()
        layout.addLayout(map_layout)
        
        # Map info
        self.map_info = qw.QLabel()
        self.map_info.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.map_info)
        
        # Airflow adder parameters (quick adjust)
        airflow_group = qw.QGroupBox("Airflow Adders (Boost Enhancers)")
        airflow_layout = qw.QFormLayout(airflow_group)
        
        airflow_params = [
            ('wgdc_airflow_adder_e85', "E85 Adder:"),
            ('wgdc_airflow_adder_map2', "Map 2 Adder:"),
            ('wgdc_airflow_adder_map3', "Map 3 Adder:"),
            ('wgdc_airflow_adder_map4', "Map 4 Adder:"),
        ]
        
        for key, label in airflow_params:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = ParameterSpinBox(param)
                airflow_layout.addRow(label, editor)
                self.editors[key] = editor
        
        layout.addWidget(airflow_group)
        
        # Create table editors for each map
        self.stack = qw.QStackedWidget()
        
        # Get axis labels from tuning_parameters
        try:
            from flash_tool.tuning_parameters import WGDC_RPM_AXIS, WGDC_LOAD_AXIS
            rpm_labels = [str(r) for r in WGDC_RPM_AXIS]
            load_labels = [str(l) for l in WGDC_LOAD_AXIS]
        except ImportError:
            rpm_labels = [f"RPM{i}" for i in range(12)]
            load_labels = [f"Load{i}" for i in range(12)]
        
        for key in self.map_keys:
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                editor = TableEditor(param, row_labels=load_labels, col_labels=rpm_labels)
                self.editors[key] = editor
                self.stack.addWidget(editor)
            else:
                placeholder = qw.QLabel(f"Map '{key}' not available")
                placeholder.setAlignment(qc.Qt.AlignmentFlag.AlignCenter)
                self.stack.addWidget(placeholder)
        
        # Note: axis variants (wgdc_airflow_adder_axis_*) are auto-populated from main tables
        # and do not require separate UI controls
        
        layout.addWidget(self.stack, 1)
        
        # Quick adjust controls
        adjust_layout = qw.QHBoxLayout()
        adjust_layout.addWidget(qw.QLabel("Quick Adjust:"))
        
        self.adjust_spin = qw.QDoubleSpinBox()
        self.adjust_spin.setRange(-20.0, 20.0)
        self.adjust_spin.setValue(0.0)
        self.adjust_spin.setSingleStep(1.0)
        self.adjust_spin.setSuffix("%")
        adjust_layout.addWidget(self.adjust_spin)
        
        add_btn = qw.QPushButton("Add to All")
        add_btn.clicked.connect(self._add_to_all)
        adjust_layout.addWidget(add_btn)
        
        adjust_layout.addStretch()
        
        # Safety indicator
        self.safety_label = qw.QLabel("DANGEROUS")
        self.safety_label.setStyleSheet("color: #c00; font-weight: bold;")
        adjust_layout.addWidget(self.safety_label)
        
        layout.addLayout(adjust_layout)
        
        # Show first map info
        self._on_map_changed(0)
    
    def _on_map_changed(self, index):
        if 0 <= index < len(self.map_keys):
            self.stack.setCurrentIndex(index)
            key = self.map_keys[index]
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                self.map_info.setText(
                    f"{param.name}\n"
                    f"Offset: 0x{param.offset:06X} | Size: {param.rows}x{param.cols} ({param.count} values) | "
                    f"Values in % duty cycle"
                )
                self._current_map = key
    
    def _add_to_all(self):
        """Add percentage to all cells in current map"""
        if self._current_map and self._current_map in self.editors:
            editor = self.editors[self._current_map]
            delta = self.adjust_spin.value()
            table = editor.table
            table.blockSignals(True)
            for r in range(table.rowCount()):
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    if item:
                        try:
                            val = float(item.text()) + delta
                            # Clamp to 0-100%
                            val = max(0, min(100, val))
                            item.setText(f"{val:.1f}")
                        except ValueError:
                            pass
            table.blockSignals(False)
    
    def load_values(self, values: Dict[str, Any]):
        for key, editor in self.editors.items():
            if key in values:
                if isinstance(values[key], list):
                    editor.setValue(values[key])
                else:
                    editor.setValue(values[key])
    
    def get_values(self) -> Dict[str, Any]:
        result = {}
        for key, editor in self.editors.items():
            result[key] = editor.value()
        return result


# ============================================================================
# MAIN COMPREHENSIVE EDITOR WIDGET
# ============================================================================

class ComprehensiveTuningEditor(qw.QWidget):
    """Main tuning editor with all parameter categories"""
    
    valuesChanged = Signal() if Signal else None
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_values = {}
        self._loaded_file = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = qw.QVBoxLayout(self)
        layout.setSpacing(10)

        # Title bar
        title_layout = qw.QHBoxLayout()
        title = qw.QLabel("BMW N54 Tuning Editor")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        # File info
        self.file_label = qw.QLabel("No file loaded")
        self.file_label.setStyleSheet("color: gray;")
        title_layout.addWidget(self.file_label)

        layout.addLayout(title_layout)

        # Helper to wrap category widgets in scroll areas so nothing overlaps
        def _wrap_in_scroll(widget: qw.QWidget) -> qw.QScrollArea:
            scroll = qw.QScrollArea()
            scroll.setWidget(widget)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(qw.QFrame.NoFrame)
            return scroll

        # Tab widget
        self.tabs = qw.QTabWidget()

        # Create tabs with scrolling containers
        self.performance_tab = PerformanceTab()
        self.tabs.addTab(_wrap_in_scroll(self.performance_tab), "Performance")

        self.antilag_tab = AntilagTab()
        self.tabs.addTab(_wrap_in_scroll(self.antilag_tab), "Antilag/Launch")

        self.wgdc_tab = WGDCTab()
        self.tabs.addTab(_wrap_in_scroll(self.wgdc_tab), "WGDC/Boost")

        self.ignition_tab = IgnitionTab()
        self.tabs.addTab(_wrap_in_scroll(self.ignition_tab), "Ignition")

        self.torque_tab = TorqueTab()
        self.tabs.addTab(_wrap_in_scroll(self.torque_tab), "Torque Limits")

        self.load_target_tab = LoadTargetTab()
        self.tabs.addTab(_wrap_in_scroll(self.load_target_tab), "Load Target")

        self.flexfuel_tab = FlexFuelTab()
        self.tabs.addTab(_wrap_in_scroll(self.flexfuel_tab), "FlexFuel")

        self.features_tab = FeaturesTab()
        self.tabs.addTab(_wrap_in_scroll(self.features_tab), "Features")

        layout.addWidget(self.tabs)
        
        # Preset and file buttons
        btn_layout = qw.QHBoxLayout()
        
        # Preset dropdown
        btn_layout.addWidget(qw.QLabel("Preset:"))
        self.preset_combo = qw.QComboBox()
        self.preset_combo.addItems(["-- Select --"] + list(ALL_PRESETS.keys()))
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        btn_layout.addWidget(self.preset_combo)
        
        btn_layout.addStretch()
        
        # File buttons
        self.load_btn = qw.QPushButton("Load .bin")
        self.load_btn.clicked.connect(self._on_load)
        btn_layout.addWidget(self.load_btn)
        
        self.save_btn = qw.QPushButton("Save .bin")
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        
        self.export_preset_btn = qw.QPushButton("Export Preset")
        self.export_preset_btn.clicked.connect(self._on_export_preset)
        btn_layout.addWidget(self.export_preset_btn)
        
        layout.addLayout(btn_layout)
        
        # Status bar
        self.status_label = qw.QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def _on_preset_changed(self, preset_name: str):
        print(f"DEBUG: Preset changed to: {preset_name}")
        if preset_name == "-- Select --":
            return
        
        if preset_name in ALL_PRESETS:
            preset = ALL_PRESETS[preset_name]
            print(f"DEBUG: Applying {len(preset.values)} values from preset")
            self._apply_values(preset.values)
            self.status_label.setText(f"Loaded preset: {preset.name} - {preset.description}")
            # Reset combo box to allow re-selecting the same preset
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText("-- Select --")
            self.preset_combo.blockSignals(False)
        else:
            self.status_label.setText(f"Unknown preset: {preset_name}")
    
    def _apply_values(self, values: Dict[str, Any]):
        """Apply values to all tabs"""
        print(f"DEBUG: _apply_values called with {len(values)} parameters")
        # Replace _current_values entirely (don't use .update() which keeps old keys)
        self._current_values = values.copy()
        self.performance_tab.load_values(values)
        self.antilag_tab.load_values(values)
        self.wgdc_tab.load_values(values)
        self.ignition_tab.load_values(values)
        self.torque_tab.load_values(values)
        self.load_target_tab.load_values(values)
        self.flexfuel_tab.load_values(values)
        self.features_tab.load_values(values)
        print(f"DEBUG: All tabs updated")
    
    def _collect_values(self) -> Dict[str, Any]:
        """Collect values from all tabs"""
        values = {}
        values.update(self.performance_tab.get_values())
        values.update(self.antilag_tab.get_values())
        values.update(self.wgdc_tab.get_values())
        values.update(self.ignition_tab.get_values())
        values.update(self.torque_tab.get_values())
        values.update(self.load_target_tab.get_values())
        values.update(self.flexfuel_tab.get_values())
        values.update(self.features_tab.get_values())
        return values
    
    def _on_load(self):
        """Load values from binary file"""
        start_dir = str(Path("maps/reference_bins").resolve()) if Path("maps/reference_bins").exists() else str(Path.cwd())
        filename, _ = qw.QFileDialog.getOpenFileName(
            self, "Load Binary File", start_dir,
            "Binary Files (*.bin);;All Files (*)"
        )
        if filename:
            try:
                values = read_all_parameters(Path(filename))
                # Filter out errors
                clean_values = {k: v for k, v in values.items() if not isinstance(v, str)}
                self._apply_values(clean_values)
                self._loaded_file = filename
                self.file_label.setText(f"Loaded: {Path(filename).name}")
                self.status_label.setText(f"Loaded {len(clean_values)} parameters from {filename}")
            except Exception as e:
                qw.QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{e}")
    
    def _on_save(self):
        """Save values to binary file"""
        print(f"DEBUG: Save clicked on widget {id(self)}")
        print(f"DEBUG: Save button clicked. _loaded_file = {self._loaded_file}")
        
        if not self._loaded_file:
            qw.QMessageBox.warning(self, "No Source", "Please load a source .bin file first.")
            return
        
        values = self._collect_values()
        
        # Select output file
        start_dir = str(Path("maps").resolve()) if Path("maps").exists() else str(Path.cwd())
        filename, _ = qw.QFileDialog.getSaveFileName(
            self, "Save Modified Binary", start_dir,
            "Binary Files (*.bin);;All Files (*)"
        )
        if filename:
            try:
                changes = write_parameters(Path(self._loaded_file), Path(filename), values)
                
                # Show summary
                msg = "Changes applied:\n\n" + "\n".join(changes[:20])
                if len(changes) > 20:
                    msg += f"\n... and {len(changes) - 20} more"
                
                qw.QMessageBox.information(self, "Saved", msg)
                self.status_label.setText(f"Saved to {filename}")
            except Exception as e:
                qw.QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")
    
    def _on_export_preset(self):
        """Export current values as preset JSON"""
        values = self._collect_values()
        
        # Get preset name
        name, ok = qw.QInputDialog.getText(self, "Preset Name", "Enter preset name:")
        if not ok or not name:
            return
        
        desc, ok = qw.QInputDialog.getText(self, "Description", "Enter description:")
        if not ok:
            desc = ""
        
        preset = TuningPreset(name=name, description=desc, values=values)
        
        # Save to file
        start_dir = str(Path("presets").resolve()) if Path("presets").exists() else str(Path.cwd())
        filename, _ = qw.QFileDialog.getSaveFileName(
            self, "Save Preset", f"{start_dir}/{name}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if filename:
            try:
                Path(filename).write_text(preset.to_json())
                self.status_label.setText(f"Preset exported to {filename}")
            except Exception as e:
                qw.QMessageBox.critical(self, "Export Error", f"Failed to export preset:\n{e}")


# ============================================================================
# CONTROLLER CLASS (for GUI pattern compatibility)
# ============================================================================

class TuningEditorController:
    """GUI-agnostic controller for tuning editor.
    
    Follows the existing widget controller pattern for integration with app.py.
    """
    
    def __init__(self, log_controller=None):
        """Initialize controller.
        
        Args:
            log_controller: Optional log controller for status messages
        """
        self.log_controller = log_controller
        self._parameters = ALL_PARAMETERS if HAS_TUNING else {}
        self._presets = ALL_PRESETS if HAS_TUNING else {}
        self._widget = None  # Will be set by create_qt_widget
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get all available tuning parameters."""
        return self._parameters
    
    def get_presets(self) -> Dict[str, Any]:
        """Get all available presets."""
        return self._presets
    
    def get_preset_names(self) -> List[str]:
        """Get list of preset names."""
        return list(self._presets.keys())
    
    def load_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Load a preset by name."""
        preset = self._presets.get(preset_name)
        if preset:
            return preset.values
        return None
    
    def load_from_binary(self, data: bytes, file_path: str) -> None:
        """Load tuning parameters from binary file data.
        
        Args:
            data: Binary file data
            file_path: Path to the file being loaded
        """
        try:
            if not HAS_TUNING:
                self.log("Tuning parameters module not available", "error")
                return
            
            # Read all parameters from binary data
            from flash_tool.tuning_parameters import read_all_parameters
            from pathlib import Path
            
            # Write data to temp file (read_all_parameters expects file path)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            
            try:
                values = read_all_parameters(Path(tmp_path))
                # Filter out error strings
                clean_values = {k: v for k, v in values.items() if not isinstance(v, str)}
                
                # Apply values to widget if available
                if self._widget:
                    print(f"DEBUG: Controller widget id: {id(self._widget)}")
                    print(f"DEBUG: Setting _loaded_file on widget {id(self._widget)} to: {file_path}")
                    self._widget._apply_values(clean_values)
                    self._widget._loaded_file = file_path
                    self._widget.file_label.setText(f"Loaded: {Path(file_path).name}")
                    self._widget.status_label.setText(f"Loaded {len(clean_values)} parameters from binary")
                    print(f"DEBUG: Verify _loaded_file is set: {self._widget._loaded_file}")
                else:
                    print("DEBUG: Widget not available!")
                
                self.log(f"Loaded {len(clean_values)} parameters from {Path(file_path).name}", "info")
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        except Exception as e:
            self.log(f"Failed to load parameters from binary: {e}", "error")
    
    def log(self, message: str, level: str = "info"):
        """Log a message if log controller is available."""
        if self.log_controller and hasattr(self.log_controller, 'log'):
            self.log_controller.log(message, level)


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_comprehensive_tuning_editor(parent=None) -> qw.QWidget:
    """Factory function to create the comprehensive tuning editor"""
    if not HAS_QT:
        raise ImportError("Neither PySide6 nor PyQt5 is available")
    if not HAS_TUNING:
        raise ImportError("tuning_parameters module not available")
    
    return ComprehensiveTuningEditor(parent)


def create_qt_widget(controller: TuningEditorController, parent=None) -> qw.QWidget:
    """Factory function following the standard widget pattern.
    
    Args:
        controller: TuningEditorController instance
        parent: Optional parent widget
        
    Returns:
        ComprehensiveTuningEditor widget
    """
    if not HAS_QT:
        raise ImportError("Neither PySide6 nor PyQt5 is available")
    if not HAS_TUNING:
        raise ImportError("tuning_parameters module not available")
    
    widget = ComprehensiveTuningEditor(parent)
    widget._controller = controller  # Store reference for potential future use
    controller._widget = widget  # Store widget reference in controller for load_from_binary
    return widget


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if not HAS_QT:
        print("Error: Neither PySide6 nor PyQt5 is installed")
        sys.exit(1)
    
    if not HAS_TUNING:
        print("Error: tuning_parameters module not available")
        sys.exit(1)
    
    app = qw.QApplication(sys.argv)
    
    # Create main window
    window = qw.QMainWindow()
    window.setWindowTitle("BMW N54 Tuning Editor")
    window.setMinimumSize(900, 700)
    
    # Create and set central widget
    editor = create_comprehensive_tuning_editor()
    window.setCentralWidget(editor)
    
    window.show()
    sys.exit(app.exec())
