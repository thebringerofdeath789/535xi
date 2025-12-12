"""Settings Dialog widget for GUI.

Allows users to view and modify adapter settings, port preferences, themes,
logging options, safety toggles, and other configuration options.
"""
from __future__ import annotations

from typing import Any, Optional
import os
import json
from pathlib import Path
from flash_tool import connection_manager

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
    except Exception as exc:
        raise ImportError('Qt bindings not available for Settings Dialog') from exc


class SettingsDialog(QtWidgets.QDialog):
    """Enhanced settings dialog with multiple configuration sections."""
    
    def __init__(self, parent: Optional[Any] = None):
        super().__init__(parent)
        self.setWindowTitle('Settings / Configuration')
        self.setModal(True)
        self.setMinimumSize(500, 600)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Tabs for different settings categories
        self.tabs = QtWidgets.QTabWidget()
        
        # Connection Tab
        self.tabs.addTab(self._create_connection_tab(), "Connection")
        
        # Appearance Tab
        self.tabs.addTab(self._create_appearance_tab(), "Appearance")
        
        # Safety Tab
        self.tabs.addTab(self._create_safety_tab(), "Safety")
        
        # Logging Tab
        self.tabs.addTab(self._create_logging_tab(), "Logging")
        
        # Advanced Tab
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        layout.addWidget(self.tabs)
        
        # Button row
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(self.reset_btn)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_connection_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        # Port settings
        layout.addRow(QtWidgets.QLabel("<b>Serial Port Settings</b>"))
        
        self.port_edit = QtWidgets.QLineEdit()
        self.port_edit.setPlaceholderText("e.g., COM3, /dev/ttyUSB0")
        layout.addRow("Preferred Port:", self.port_edit)
        
        self.baudrate_combo = QtWidgets.QComboBox()
        self.baudrate_combo.addItems(['9600', '19200', '38400', '57600', '115200', '500000'])
        self.baudrate_combo.setCurrentText('500000')
        layout.addRow("Baudrate:", self.baudrate_combo)
        
        self.timeout_spin = QtWidgets.QSpinBox()
        self.timeout_spin.setRange(1, 30)
        self.timeout_spin.setValue(5)
        self.timeout_spin.setSuffix(" seconds")
        layout.addRow("Timeout:", self.timeout_spin)
        
        # CAN settings
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>CAN Interface Settings</b>"))
        
        self.can_interface_combo = QtWidgets.QComboBox()
        self.can_interface_combo.addItems(['pcan', 'socketcan', 'vector', 'kvaser', 'ixxat', 'usb2can'])
        layout.addRow("CAN Interface:", self.can_interface_combo)
        
        self.can_channel_edit = QtWidgets.QLineEdit()
        self.can_channel_edit.setPlaceholderText("e.g., PCAN_USBBUS1, can0")
        self.can_channel_edit.setText("PCAN_USBBUS1")
        layout.addRow("CAN Channel:", self.can_channel_edit)
        
        self.can_bitrate_combo = QtWidgets.QComboBox()
        self.can_bitrate_combo.addItems(['125000', '250000', '500000', '1000000'])
        self.can_bitrate_combo.setCurrentText('500000')
        layout.addRow("CAN Bitrate:", self.can_bitrate_combo)
        
        # Auto-connect
        layout.addRow(QtWidgets.QLabel(""))
        self.auto_connect_check = QtWidgets.QCheckBox("Auto-connect on startup")
        layout.addRow("", self.auto_connect_check)
        
        self.remember_port_check = QtWidgets.QCheckBox("Remember last used port")
        self.remember_port_check.setChecked(True)
        layout.addRow("", self.remember_port_check)
        
        return widget
    
    def _create_appearance_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        layout.addRow(QtWidgets.QLabel("<b>Theme Settings</b>"))
        
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(['System Default', 'Dark', 'Light', 'Dark Blue', 'High Contrast'])
        layout.addRow("Theme:", self.theme_combo)
        
        self.font_size_spin = QtWidgets.QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(10)
        self.font_size_spin.setSuffix(" pt")
        layout.addRow("Font Size:", self.font_size_spin)
        
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>Dashboard Settings</b>"))
        
        self.gauge_style_combo = QtWidgets.QComboBox()
        self.gauge_style_combo.addItems(['Modern', 'Classic', 'Racing', 'Minimal'])
        layout.addRow("Gauge Style:", self.gauge_style_combo)
        
        self.show_digital_check = QtWidgets.QCheckBox("Show digital readouts on gauges")
        self.show_digital_check.setChecked(True)
        layout.addRow("", self.show_digital_check)
        
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>Window Settings</b>"))
        
        self.remember_size_check = QtWidgets.QCheckBox("Remember window size and position")
        self.remember_size_check.setChecked(True)
        layout.addRow("", self.remember_size_check)
        
        self.start_maximized_check = QtWidgets.QCheckBox("Start maximized")
        layout.addRow("", self.start_maximized_check)
        
        return widget
    
    def _create_safety_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Warning banner
        warning = QtWidgets.QLabel(
            "<b>Safety settings protect your ECU from accidental damage.</b><br>"
            "Only modify these if you understand the risks."
        )
        warning.setStyleSheet("background: #fff3cd; padding: 10px; border-radius: 5px; color: #856404;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        form = QtWidgets.QFormLayout()
        
        form.addRow(QtWidgets.QLabel("<b>Write Protection</b>"))
        
        self.confirm_writes_check = QtWidgets.QCheckBox("Confirm before all write operations")
        self.confirm_writes_check.setChecked(True)
        form.addRow("", self.confirm_writes_check)
        
        self.backup_before_write_check = QtWidgets.QCheckBox("Auto-backup before writing")
        self.backup_before_write_check.setChecked(True)
        form.addRow("", self.backup_before_write_check)
        
        self.verify_after_write_check = QtWidgets.QCheckBox("Verify data after writing")
        self.verify_after_write_check.setChecked(True)
        form.addRow("", self.verify_after_write_check)
        
        form.addRow(QtWidgets.QLabel(""))
        form.addRow(QtWidgets.QLabel("<b>Region Protection</b>"))
        
        self.enforce_forbidden_check = QtWidgets.QCheckBox("Enforce forbidden region protection")
        self.enforce_forbidden_check.setChecked(True)
        self.enforce_forbidden_check.setEnabled(False)  # Cannot disable
        form.addRow("", self.enforce_forbidden_check)
        
        self.warn_checksum_check = QtWidgets.QCheckBox("Warn before modifying checksum areas")
        self.warn_checksum_check.setChecked(True)
        form.addRow("", self.warn_checksum_check)
        
        form.addRow(QtWidgets.QLabel(""))
        form.addRow(QtWidgets.QLabel("<b>Security Access</b>"))
        
        self.max_unlock_attempts_spin = QtWidgets.QSpinBox()
        self.max_unlock_attempts_spin.setRange(1, 10)
        self.max_unlock_attempts_spin.setValue(3)
        form.addRow("Max unlock attempts:", self.max_unlock_attempts_spin)
        
        self.lockout_timeout_spin = QtWidgets.QSpinBox()
        self.lockout_timeout_spin.setRange(1, 60)
        self.lockout_timeout_spin.setValue(10)
        self.lockout_timeout_spin.setSuffix(" minutes")
        form.addRow("Lockout timeout:", self.lockout_timeout_spin)
        
        layout.addLayout(form)
        layout.addStretch()
        
        return widget
    
    def _create_logging_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        layout.addRow(QtWidgets.QLabel("<b>Log Settings</b>"))
        
        self.log_level_combo = QtWidgets.QComboBox()
        self.log_level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
        self.log_level_combo.setCurrentText('INFO')
        layout.addRow("Log Level:", self.log_level_combo)
        
        self.log_to_file_check = QtWidgets.QCheckBox("Save logs to file")
        self.log_to_file_check.setChecked(True)
        layout.addRow("", self.log_to_file_check)
        
        log_dir_layout = QtWidgets.QHBoxLayout()
        self.log_dir_edit = QtWidgets.QLineEdit()
        self.log_dir_edit.setText(str(Path.home() / ".535xi" / "logs"))
        log_dir_layout.addWidget(self.log_dir_edit)
        self.log_dir_btn = QtWidgets.QPushButton("Browse...")
        self.log_dir_btn.clicked.connect(self._browse_log_dir)
        log_dir_layout.addWidget(self.log_dir_btn)
        layout.addRow("Log Directory:", log_dir_layout)
        
        self.max_log_size_spin = QtWidgets.QSpinBox()
        self.max_log_size_spin.setRange(1, 100)
        self.max_log_size_spin.setValue(10)
        self.max_log_size_spin.setSuffix(" MB")
        layout.addRow("Max Log Size:", self.max_log_size_spin)
        
        self.max_log_files_spin = QtWidgets.QSpinBox()
        self.max_log_files_spin.setRange(1, 50)
        self.max_log_files_spin.setValue(5)
        layout.addRow("Max Log Files:", self.max_log_files_spin)
        
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>OBD Logging</b>"))
        
        self.log_obd_data_check = QtWidgets.QCheckBox("Log all OBD data")
        layout.addRow("", self.log_obd_data_check)
        
        self.log_can_frames_check = QtWidgets.QCheckBox("Log raw CAN frames (verbose)")
        layout.addRow("", self.log_can_frames_check)
        
        return widget
    
    def _create_advanced_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        layout.addRow(QtWidgets.QLabel("<b>Advanced Tools</b>"))
        
        self.advanced_tools_check = QtWidgets.QCheckBox("Show Advanced Tools (Coding, Direct CAN, Live Control)")
        self.advanced_tools_check.setToolTip(
            "When enabled, advanced features like coding and direct CAN access are visible.\n"
            "These tools require expert knowledge. Use with caution."
        )
        layout.addRow("", self.advanced_tools_check)
        
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>Developer Options</b>"))
        
        self.debug_mode_check = QtWidgets.QCheckBox("Enable debug mode")
        layout.addRow("", self.debug_mode_check)
        
        self.mock_ecu_check = QtWidgets.QCheckBox("Use mock ECU for testing")
        layout.addRow("", self.mock_ecu_check)
        
        self.show_offsets_check = QtWidgets.QCheckBox("Show memory offsets in UI")
        self.show_offsets_check.setChecked(True)
        layout.addRow("", self.show_offsets_check)
        
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>Performance</b>"))
        
        self.update_rate_spin = QtWidgets.QSpinBox()
        self.update_rate_spin.setRange(1, 60)
        self.update_rate_spin.setValue(10)
        self.update_rate_spin.setSuffix(" Hz")
        layout.addRow("Dashboard Update Rate:", self.update_rate_spin)
        
        self.buffer_size_spin = QtWidgets.QSpinBox()
        self.buffer_size_spin.setRange(1024, 65536)
        self.buffer_size_spin.setValue(4096)
        self.buffer_size_spin.setSuffix(" bytes")
        layout.addRow("Read Buffer Size:", self.buffer_size_spin)
        
        layout.addRow(QtWidgets.QLabel(""))
        layout.addRow(QtWidgets.QLabel("<b>Paths</b>"))
        
        maps_layout = QtWidgets.QHBoxLayout()
        self.maps_dir_edit = QtWidgets.QLineEdit()
        self.maps_dir_edit.setText("maps/")
        maps_layout.addWidget(self.maps_dir_edit)
        maps_btn = QtWidgets.QPushButton("Browse...")
        maps_btn.clicked.connect(lambda: self._browse_dir(self.maps_dir_edit))
        maps_layout.addWidget(maps_btn)
        layout.addRow("Maps Directory:", maps_layout)
        
        backups_layout = QtWidgets.QHBoxLayout()
        self.backups_dir_edit = QtWidgets.QLineEdit()
        self.backups_dir_edit.setText("backups/")
        backups_layout.addWidget(self.backups_dir_edit)
        backups_btn = QtWidgets.QPushButton("Browse...")
        backups_btn.clicked.connect(lambda: self._browse_dir(self.backups_dir_edit))
        backups_layout.addWidget(backups_btn)
        layout.addRow("Backups Directory:", backups_layout)
        
        return widget
    
    def _browse_log_dir(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Log Directory")
        if dir_path:
            self.log_dir_edit.setText(dir_path)
    
    def _browse_dir(self, edit: QtWidgets.QLineEdit):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            edit.setText(dir_path)
    
    def _get_settings_path(self) -> Path:
        return Path.home() / ".535xi" / "settings.json"
    
    def _load_settings(self):
        """Load settings from file."""
        settings_path = self._get_settings_path()
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text())
                # Apply settings to widgets
                if 'port' in settings:
                    self.port_edit.setText(settings['port'])
                if 'baudrate' in settings:
                    self.baudrate_combo.setCurrentText(str(settings['baudrate']))
                if 'theme' in settings:
                    self.theme_combo.setCurrentText(settings['theme'])
                if 'log_level' in settings:
                    self.log_level_combo.setCurrentText(settings['log_level'])
                if 'advanced_tools_enabled' in settings:
                    self.advanced_tools_check.setChecked(settings['advanced_tools_enabled'])
            except Exception:
                pass
        
        # Also load from connection manager
        try:
            manager = connection_manager.get_manager()
            config = manager.get_connection_settings() if hasattr(manager, 'get_connection_settings') else {}
            if config.get('port'):
                self.port_edit.setText(config['port'])
        except Exception:
            pass
    
    def _on_save(self):
        """Save all settings."""
        settings = {
            'port': self.port_edit.text().strip(),
            'baudrate': int(self.baudrate_combo.currentText()),
            'timeout': self.timeout_spin.value(),
            'can_interface': self.can_interface_combo.currentText(),
            'can_channel': self.can_channel_edit.text().strip(),
            'can_bitrate': int(self.can_bitrate_combo.currentText()),
            'auto_connect': self.auto_connect_check.isChecked(),
            'theme': self.theme_combo.currentText(),
            'font_size': self.font_size_spin.value(),
            'gauge_style': self.gauge_style_combo.currentText(),
            'log_level': self.log_level_combo.currentText(),
            'log_to_file': self.log_to_file_check.isChecked(),
            'log_dir': self.log_dir_edit.text(),
            'confirm_writes': self.confirm_writes_check.isChecked(),
            'backup_before_write': self.backup_before_write_check.isChecked(),
            'debug_mode': self.debug_mode_check.isChecked(),
            'advanced_tools_enabled': self.advanced_tools_check.isChecked(),
        }
        
        # Save to file
        settings_path = self._get_settings_path()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2))
        
        # Update connection manager
        try:
            connection_manager.save_port_preference(settings['port'])
        except Exception:
            pass
        
        self.accept()
    
    def _on_reset(self):
        """Reset to default settings."""
        reply = QtWidgets.QMessageBox.question(
            self, "Reset Settings",
            "Are you sure you want to reset all settings to defaults?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.port_edit.clear()
            self.baudrate_combo.setCurrentText('500000')
            self.timeout_spin.setValue(5)
            self.theme_combo.setCurrentIndex(0)
            self.font_size_spin.setValue(10)
            self.log_level_combo.setCurrentText('INFO')
            self.confirm_writes_check.setChecked(True)
            self.backup_before_write_check.setChecked(True)


def create_qt_widget(parent: Optional[Any] = None):
    return SettingsDialog(parent)

