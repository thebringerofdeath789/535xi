"""
Tuning Options Controller and Qt Widget
========================================

Provides a GUI-agnostic controller and optional Qt widget factory for user-selectable
tuning options (burbles, VMAX delete, DTC disable, launch control, rev limiter, boost settings).

Supports:
- Loading/saving preset configurations
- Interactive option editing
- Validation and safety checks
- Export to map patch for flashing
"""

from typing import Any, Optional, Dict, Callable, List, Tuple
from dataclasses import asdict
from pathlib import Path
from datetime import datetime


class TuningOptionsController:
    """GUI-agnostic controller for tuning options management."""

    def __init__(self, logger=None):
        """
        Initialize controller using canonical tuning_parameters only.
        Args:
            logger: Optional logger
        """
        from flash_tool import tuning_parameters
        from flash_tool import map_flasher
        self.tuning_parameters = tuning_parameters
        self.map_flasher = map_flasher
        self.logger = logger

    def list_presets(self) -> List[str]:
        """List available preset configurations from tuning_parameters."""
        return self.tuning_parameters.list_presets()

    def load_preset(self, preset_name: str) -> Dict[str, Any]:
        """
        Load a preset configuration.
        Args:
            preset_name: Name of preset (e.g., 'stage1', 'stage2', etc.)
        Returns:
            Dict with preset configuration data
        """
        preset = self.tuning_parameters.get_preset(preset_name)
        if preset:
            return asdict(preset)
        return {}

    def get_default_options(self) -> Dict[str, Any]:
        """Get default (stock) tuning options."""
        stock = self.tuning_parameters.get_preset('stock')
        if stock:
            return asdict(stock)
        return {}

    def validate_options(self, options: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate tuning options for safety.
        Args:
            options: Options dictionary
        Returns:
            (is_valid, error_message)
        """
        # For canonical system, assume options is a dict from a TuningPreset
        # If validation is needed, implement here
        return True, ''

    # _build_map_options and all MapOptions compatibility logic removed
                    else:
                        map_opts.burbles.mode = mo_mod.BurbleMode(mode_str)
                except Exception:
                    errors.append(f'Unknown burble mode: {mode_str}')
            if 'min_rpm' in b:
                map_opts.burbles.min_rpm = int(b['min_rpm'])
            if 'max_rpm' in b:
                map_opts.burbles.max_rpm = int(b['max_rpm'])
            if 'min_ect' in b:
                map_opts.burbles.min_ect = int(b['min_ect'])

            # VMAX
            v = options.get('vmax', {}) or {}
            map_opts.vmax.enabled = bool(v.get('enabled', False))
            if 'value' in v:
                map_opts.vmax.limit_kmh = int(v['value'])

            # DTC disable mapping (from code list to flags)
            dtc_dict = options.get('dtc_disable', {}) or {}
            codes = [c for c in dtc_dict.get('codes', []) if c]
            map_opts.dtc.disable_cat_codes = any(c in ('P0420', 'P0430') for c in codes)
            map_opts.dtc.disable_o2_codes = any(c == 'O2_SECONDARY' for c in codes)
            map_opts.dtc.disable_evap_codes = any(c == 'EVAP' for c in codes)
            # Any other codes become custom entries
            other_codes = [c for c in codes if c not in ('P0420', 'P0430', 'O2_SECONDARY', 'EVAP')]
            map_opts.dtc.custom_codes = other_codes

            # Launch control (current support: enable flag only)
            lc = options.get('launch_control', {}) or {}
            map_opts.launch_control.enabled = bool(lc.get('enabled', False))

            # Rev limiter
            r = options.get('rev_limiter', {}) or {}
            map_opts.rev_limiter.enabled = bool(r.get('enabled', False))
            rpm_val = int(r.get('rpm', map_opts.rev_limiter.hard_limit))
            map_opts.rev_limiter.hard_limit = rpm_val
            # Keep soft_limit slightly below hard_limit for safety
            map_opts.rev_limiter.soft_limit = max(6000, rpm_val - 200)

            # Boost
            bo = options.get('boost', {}) or {}
            map_opts.boost.enabled = bool(bo.get('enabled', False))
            if 'max_bar' in bo:
                map_opts.boost.max_boost_bar = float(bo['max_bar'])

            return map_opts, errors

        except Exception as exc:
            errors.append(str(exc))
            return None, errors

    def build_patch_set(self, options: Dict[str, Any], ecu_type: str = "MSD81") -> Tuple[Optional[Any], str]:
        """Build a PatchSet from GUI options using MapOptions+MapPatcher.

        Returns (patch_set | None, error_message).
        """
        try:
            map_opts, build_errors = self._build_map_options(options)
            if map_opts is None:
                return None, '; '.join(build_errors) or 'Unable to build MapOptions from GUI options'

            is_valid, val_errors = map_opts.validate()
            if not is_valid:
                return None, '; '.join(val_errors)

            from flash_tool import map_patcher as mp

            patcher = mp.MapPatcher(ecu_type=ecu_type)
            patch_set = patcher.create_patchset_from_map_options(
                map_opts,
                name="Tuning Options",
                description="Applied from Tuning Options GUI",
            )
            return patch_set, ''

        except Exception as exc:
            return None, str(exc)

    def create_summary(self, options: Dict[str, Any]) -> str:
        """
        Create human-readable summary of selected options.

        Args:
            options: Options dictionary

        Returns:
            Formatted summary string
        """
        lines = ['Selected Tuning Options:']
        lines.append('=' * 40)

        try:
            if options.get('burbles', {}).get('enabled'):
                mode = options['burbles'].get('mode', 'normal')
                lines.append(f'Burbles: {mode.upper()}')

            if options.get('vmax', {}).get('enabled'):
                value = options['vmax'].get('value', 250)
                lines.append(f'VMAX Delete: {value} km/h')

            if options.get('dtc_disable', {}).get('enabled'):
                codes = options['dtc_disable'].get('codes', [])
                lines.append(f'DTC Disable: {len(codes)} codes')

            if options.get('launch_control', {}).get('enabled'):
                lines.append('Launch Control: ENABLED')

            if options.get('rev_limiter', {}).get('enabled'):
                rpm = options['rev_limiter'].get('rpm', 7000)
                lines.append(f'Rev Limiter: {rpm} RPM')

            if options.get('boost', {}).get('enabled'):
                bar = options['boost'].get('max_bar', 1.0)
                lines.append(f'Boost Ceiling: {bar} bar')

            if not any(v.get('enabled') for k, v in options.items() if isinstance(v, dict)):
                lines.append('(No options selected - stock configuration)')

        except Exception:
            pass

        return '\n'.join(lines)

    def export_as_patch_info(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export options as patch info for map editor.

        Args:
            options: Options dictionary

        Returns:
            Dict with patch metadata for map editor export
        """
        return {
            'type': 'tuning_options',
            'options': options,
            'summary': self.create_summary(options),
        }


def create_qt_widget(controller: TuningOptionsController, parent: Optional[Any] = None):
    """
    Build a Qt widget for tuning options configuration.

    Lazy imports PySide6/PyQt5. Allows selecting preset configurations,
    enabling/disabling individual options, and adjusting parameters.
    """
    QtWidgets = None
    QtCore = None
    try:
        from PySide6 import QtWidgets as _w, QtCore as _c
        QtWidgets, QtCore = _w, _c
    except Exception:
        try:
            from PyQt5 import QtWidgets as _w, QtCore as _c
            QtWidgets, QtCore = _w, _c
        except Exception as exc:
            raise ImportError('Qt bindings not available') from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._current_options = controller.get_default_options()

            layout = QtWidgets.QVBoxLayout(self)

            # Title
            title = QtWidgets.QLabel('Tuning Options')
            title_font = title.font()
            title_font.setBold(True)
            title_font.setPointSize(12)
            title.setFont(title_font)
            layout.addWidget(title)

            # Presets row
            preset_h = QtWidgets.QHBoxLayout()
            preset_h.addWidget(QtWidgets.QLabel('Preset:'))
            self.preset_combo = QtWidgets.QComboBox()
            self.preset_combo.addItem('Custom', 'CUSTOM')
            for preset in controller.list_presets():
                self.preset_combo.addItem(preset, preset)
            preset_h.addWidget(self.preset_combo)
            preset_h.addStretch()
            layout.addLayout(preset_h)

            self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)

            # Scroll area for options
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_widget = QtWidgets.QWidget()
            scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)

            # === ENABLE/DISABLE CHECKBOXES GROUP ===
            enable_group = QtWidgets.QGroupBox("Enable Features")
            enable_layout = QtWidgets.QVBoxLayout(enable_group)
            enable_layout.setContentsMargins(10, 20, 10, 10)
            enable_layout.setSpacing(8)
            
            self.enable_burbles = QtWidgets.QCheckBox("Enable Burbles/Pops")
            self.enable_vmax = QtWidgets.QCheckBox("Enable VMAX Delete")
            self.enable_dtc = QtWidgets.QCheckBox("Enable DTC Disable")
            self.enable_launch = QtWidgets.QCheckBox("Enable Launch Control")
            self.enable_rev = QtWidgets.QCheckBox("Enable Rev Limiter Mod")
            self.enable_boost = QtWidgets.QCheckBox("Enable Boost Mod")
            
            enable_layout.addWidget(self.enable_burbles)
            enable_layout.addWidget(self.enable_vmax)
            enable_layout.addWidget(self.enable_dtc)
            enable_layout.addWidget(self.enable_launch)
            enable_layout.addWidget(self.enable_rev)
            enable_layout.addWidget(self.enable_boost)
            
            # Connect checkboxes to update summary
            self.enable_burbles.stateChanged.connect(lambda: self._on_option_changed('burbles', self.enable_burbles.isChecked()))
            self.enable_vmax.stateChanged.connect(lambda: self._on_option_changed('vmax', self.enable_vmax.isChecked()))
            self.enable_dtc.stateChanged.connect(lambda: self._on_option_changed('dtc', self.enable_dtc.isChecked()))
            self.enable_launch.stateChanged.connect(lambda: self._on_option_changed('launch', self.enable_launch.isChecked()))
            self.enable_rev.stateChanged.connect(lambda: self._on_option_changed('rev', self.enable_rev.isChecked()))
            self.enable_boost.stateChanged.connect(lambda: self._on_option_changed('boost', self.enable_boost.isChecked()))
            
            scroll_layout.addWidget(enable_group)

            # Burbles section (parameters only, no enable checkbox)
            scroll_layout.addWidget(self._create_burbles_section())

            # VMAX section
            scroll_layout.addWidget(self._create_vmax_section())

            # DTC Disable section
            scroll_layout.addWidget(self._create_dtc_section())

            # Launch Control section
            scroll_layout.addWidget(self._create_launch_section())

            # Rev Limiter section
            scroll_layout.addWidget(self._create_rev_section())

            # Boost section
            scroll_layout.addWidget(self._create_boost_section())

            scroll_layout.addStretch()
            scroll.setWidget(scroll_widget)
            layout.addWidget(scroll)

            # Summary and buttons
            self.summary_label = QtWidgets.QLabel('')
            self.summary_label.setWordWrap(True)
            self.summary_label.setStyleSheet('border: 1px solid #ccc; padding: 5px; background: #f9f9f9;')
            layout.addWidget(self.summary_label)

            button_h = QtWidgets.QHBoxLayout()
            self.reset_btn = QtWidgets.QPushButton('Reset to Stock')
            self.export_btn = QtWidgets.QPushButton('Export Options')
            self.apply_btn = QtWidgets.QPushButton('Apply to Map File...')
            self.tune_flash_btn = QtWidgets.QPushButton('Tune && Flash...')
            self.tune_flash_btn.setToolTip('Apply tuning options and flash to ECU in one step')
            button_h.addWidget(self.reset_btn)
            button_h.addWidget(self.export_btn)
            button_h.addWidget(self.apply_btn)
            button_h.addWidget(self.tune_flash_btn)
            button_h.addStretch()
            layout.addLayout(button_h)

            self.reset_btn.clicked.connect(self._on_reset)
            self.export_btn.clicked.connect(self._on_export)
            self.apply_btn.clicked.connect(self._on_apply_to_map)
            self.tune_flash_btn.clicked.connect(self._on_tune_and_flash)

            self._update_summary()

        def _create_section(self, title: str) -> Tuple[QtWidgets.QGroupBox, QtWidgets.QVBoxLayout]:
            """Create a section group box."""
            group = QtWidgets.QGroupBox(title)
            group_layout = QtWidgets.QVBoxLayout(group)
            group_layout.setContentsMargins(10, 20, 10, 10)
            group_layout.setSpacing(8)
            return group, group_layout

        def _create_burbles_section(self) -> QtWidgets.QGroupBox:
            """Create burbles/pops configuration section."""
            group, layout = self._create_section('Burbles / Pops')

            mode_h = QtWidgets.QHBoxLayout()
            mode_h.addWidget(QtWidgets.QLabel('Mode:'))
            self.burbles_mode = QtWidgets.QComboBox()
            self.burbles_mode.addItems(['normal', 'sport', 'custom'])
            mode_h.addWidget(self.burbles_mode)
            mode_h.addStretch()
            layout.addLayout(mode_h)

            rpm_h = QtWidgets.QHBoxLayout()
            rpm_h.addWidget(QtWidgets.QLabel('RPM Range:'))
            self.burbles_min_rpm = QtWidgets.QSpinBox()
            self.burbles_min_rpm.setRange(1000, 8000)
            self.burbles_min_rpm.setValue(2000)
            rpm_h.addWidget(self.burbles_min_rpm)
            rpm_h.addWidget(QtWidgets.QLabel('to'))
            self.burbles_max_rpm = QtWidgets.QSpinBox()
            self.burbles_max_rpm.setRange(1000, 8000)
            self.burbles_max_rpm.setValue(7000)
            rpm_h.addWidget(self.burbles_max_rpm)
            rpm_h.addStretch()
            layout.addLayout(rpm_h)

            temp_h = QtWidgets.QHBoxLayout()
            temp_h.addWidget(QtWidgets.QLabel('Min ECT:'))
            self.burbles_min_ect = QtWidgets.QSpinBox()
            self.burbles_min_ect.setRange(0, 120)
            self.burbles_min_ect.setValue(60)
            self.burbles_min_ect.setSuffix('°C')
            temp_h.addWidget(self.burbles_min_ect)
            temp_h.addStretch()
            layout.addLayout(temp_h)

            group.toggled.connect(lambda checked: self._on_option_changed('burbles', checked))
            self.burbles_mode.currentTextChanged.connect(lambda: self._on_option_changed('burbles', group.isChecked()))
            self.burbles_min_rpm.valueChanged.connect(lambda: self._on_option_changed('burbles', group.isChecked()))
            self.burbles_max_rpm.valueChanged.connect(lambda: self._on_option_changed('burbles', group.isChecked()))
            self.burbles_min_ect.valueChanged.connect(lambda: self._on_option_changed('burbles', group.isChecked()))

            return group

        def _create_vmax_section(self) -> QtWidgets.QGroupBox:
            """Create VMAX delete configuration section."""
            group, layout = self._create_section('VMAX Delete (Speed Limiter)')

            vmax_h = QtWidgets.QHBoxLayout()
            vmax_h.addWidget(QtWidgets.QLabel('Max Speed:'))
            self.vmax_value = QtWidgets.QSpinBox()
            self.vmax_value.setRange(100, 300)
            self.vmax_value.setValue(250)
            self.vmax_value.setSuffix(' km/h')
            vmax_h.addWidget(self.vmax_value)
            vmax_h.addStretch()
            layout.addLayout(vmax_h)

            group.toggled.connect(lambda checked: self._on_option_changed('vmax', checked))
            self.vmax_value.valueChanged.connect(lambda: self._on_option_changed('vmax', group.isChecked()))

            return group

        def _create_dtc_section(self) -> QtWidgets.QGroupBox:
            """Create DTC disable configuration section."""
            group, layout = self._create_section('DTC Disable (Check Engine Light)')

            codes_h = QtWidgets.QHBoxLayout()
            codes_h.addWidget(QtWidgets.QLabel('Disable codes:'))
            self.dtc_p0420 = QtWidgets.QCheckBox('P0420 (Catalyst efficiency)')
            self.dtc_p0430 = QtWidgets.QCheckBox('P0430 (Catalyst efficiency 2)')
            self.dtc_o2 = QtWidgets.QCheckBox('O2 Sensors (secondary)')
            self.dtc_evap = QtWidgets.QCheckBox('EVAP System')
            codes_h.addWidget(self.dtc_p0420)
            codes_h.addWidget(self.dtc_p0430)
            codes_h.addWidget(self.dtc_o2)
            codes_h.addWidget(self.dtc_evap)
            codes_h.addStretch()
            layout.addLayout(codes_h)

            self.dtc_p0420.toggled.connect(lambda: self._on_option_changed('dtc', True))
            self.dtc_p0430.toggled.connect(lambda: self._on_option_changed('dtc', True))
            self.dtc_o2.toggled.connect(lambda: self._on_option_changed('dtc', True))
            self.dtc_evap.toggled.connect(lambda: self._on_option_changed('dtc', True))
            group.toggled.connect(lambda checked: self._on_option_changed('dtc', checked))

            return group

        def _create_launch_section(self) -> QtWidgets.QGroupBox:
            """Create launch control configuration section."""
            group, layout = self._create_section('Launch Control / Antilag')
            layout.addWidget(QtWidgets.QLabel('(Full configuration available after hardware validation)'))
            group.toggled.connect(lambda checked: self._on_option_changed('launch', checked))
            return group

        def _create_rev_section(self) -> QtWidgets.QGroupBox:
            """Create rev limiter configuration section."""
            group, layout = self._create_section('Rev Limiter')

            rpm_h = QtWidgets.QHBoxLayout()
            rpm_h.addWidget(QtWidgets.QLabel('Limit:'))
            self.rev_rpm = QtWidgets.QSpinBox()
            self.rev_rpm.setRange(6000, 8500)
            self.rev_rpm.setValue(7000)
            self.rev_rpm.setSuffix(' RPM')
            rpm_h.addWidget(self.rev_rpm)
            rpm_h.addStretch()
            layout.addLayout(rpm_h)

            group.toggled.connect(lambda checked: self._on_option_changed('rev', checked))
            self.rev_rpm.valueChanged.connect(lambda: self._on_option_changed('rev', group.isChecked()))

            return group

        def _create_boost_section(self) -> QtWidgets.QGroupBox:
            """Create boost configuration section."""
            group, layout = self._create_section('Boost Ceiling')

            boost_h = QtWidgets.QHBoxLayout()
            boost_h.addWidget(QtWidgets.QLabel('Max Boost:'))
            self.boost_bar = QtWidgets.QDoubleSpinBox()
            self.boost_bar.setRange(1.0, 2.5)
            self.boost_bar.setValue(1.2)
            self.boost_bar.setSingleStep(0.1)
            self.boost_bar.setSuffix(' bar')
            boost_h.addWidget(self.boost_bar)
            boost_h.addStretch()
            layout.addLayout(boost_h)

            group.toggled.connect(lambda checked: self._on_option_changed('boost', checked))
            self.boost_bar.valueChanged.connect(lambda: self._on_option_changed('boost', group.isChecked()))

            return group

        def _on_preset_changed(self, index: int):
            """Handle preset selection."""
            try:
                preset_name = self.preset_combo.currentData()
                if preset_name and preset_name != 'CUSTOM':
                    options = self._ctrl.load_preset(preset_name)
                    self._apply_options(options)
                    self._update_summary()
            except Exception:
                pass

        def _on_option_changed(self, option_type: str, enabled: bool):
            """Handle option change."""
            self._sync_options_from_ui()
            self._update_summary()
            self.preset_combo.setCurrentIndex(0)  # Reset to Custom

        def _sync_options_from_ui(self):
            """Sync UI controls to current options dict."""
            self._current_options['burbles'] = {
                'enabled': self.enable_burbles.isChecked(),
                'mode': self.burbles_mode.currentText(),
                'min_rpm': self.burbles_min_rpm.value(),
                'max_rpm': self.burbles_max_rpm.value(),
                'min_ect': self.burbles_min_ect.value(),
            }
            self._current_options['vmax'] = {
                'enabled': self.enable_vmax.isChecked(),
                'value': self.vmax_value.value(),
            }
            self._current_options['dtc_disable'] = {
                'enabled': self.enable_dtc.isChecked(),
                'codes': [
                    'P0420' if self.dtc_p0420.isChecked() else None,
                    'P0430' if self.dtc_p0430.isChecked() else None,
                    'O2_SECONDARY' if self.dtc_o2.isChecked() else None,
                    'EVAP' if self.dtc_evap.isChecked() else None,
                ],
            }
            self._current_options['launch_control'] = {'enabled': self.enable_launch.isChecked()}
            self._current_options['rev_limiter'] = {
                'enabled': self.enable_rev.isChecked(),
                'rpm': self.rev_rpm.value(),
            }
            self._current_options['boost'] = {
                'enabled': self.enable_boost.isChecked(),
                'max_bar': self.boost_bar.value(),
            }

        def _apply_options(self, options: Dict[str, Any]):
            """Apply options dict to UI controls."""
            try:
                # Burbles
                if 'burbles' in options and options['burbles']:
                    b = options['burbles']
                    self.enable_burbles.setChecked(b.get('enabled', False))
                    if 'mode' in b:
                        idx = self.burbles_mode.findText(b['mode'])
                        if idx >= 0:
                            self.burbles_mode.setCurrentIndex(idx)
                    if 'min_rpm' in b:
                        self.burbles_min_rpm.setValue(b['min_rpm'])
                    if 'max_rpm' in b:
                        self.burbles_max_rpm.setValue(b['max_rpm'])
                    if 'min_ect' in b:
                        self.burbles_min_ect.setValue(b['min_ect'])

                # VMAX
                if 'vmax' in options and options['vmax']:
                    v = options['vmax']
                    self.enable_vmax.setChecked(v.get('enabled', False))
                    if 'value' in v:
                        self.vmax_value.setValue(v['value'])

                # DTC
                if 'dtc_disable' in options and options['dtc_disable']:
                    d = options['dtc_disable']
                    self.enable_dtc.setChecked(d.get('enabled', False))
                    # Note: checkbox states are set in _create_dtc_section

                # Launch Control
                if 'launch_control' in options and options['launch_control']:
                    lc = options['launch_control']
                    self.enable_launch.setChecked(lc.get('enabled', False))

                # Rev Limiter
                if 'rev_limiter' in options and options['rev_limiter']:
                    r = options['rev_limiter']
                    self.enable_rev.setChecked(r.get('enabled', False))
                    if 'rpm' in r:
                        self.rev_rpm.setValue(r['rpm'])

                # Boost
                if 'boost' in options and options['boost']:
                    bo = options['boost']
                    self.enable_boost.setChecked(bo.get('enabled', False))
                    if 'max_bar' in bo:
                        self.boost_bar.setValue(bo['max_bar'])

            except Exception:
                pass

        def _update_summary(self):
            """Update summary display."""
            try:
                self._sync_options_from_ui()
                summary = self._ctrl.create_summary(self._current_options)
                self.summary_label.setText(summary)
            except Exception as e:
                self.summary_label.setText(f'Error: {e}')

        def _on_reset(self):
            """Reset all options to stock configuration."""
            self.preset_combo.setCurrentIndex(self.preset_combo.findData('CUSTOM'))
            self._current_options = self._ctrl.get_default_options()
            self._apply_options(self._current_options)
            self._update_summary()

        def _on_export(self):
            """Export current options."""
            self._sync_options_from_ui()
            valid, error = self._ctrl.validate_options(self._current_options)
            if not valid:
                try:
                    from PySide6 import QtWidgets as qw
                    qw.QMessageBox.warning(self, 'Validation Error', error)
                except Exception:
                    try:
                        from PyQt5 import QtWidgets as qw
                        qw.QMessageBox.warning(self, 'Validation Error', error)
                    except Exception:
                        pass
                return

            # Emit signal or show dialog with export info
            summary = self._ctrl.create_summary(self._current_options)
            try:
                from PySide6 import QtWidgets as qw
                qw.QMessageBox.information(self, 'Options Ready for Export', summary + '\n\nThese options are ready to be applied to a map patch.')
            except Exception:
                try:
                    from PyQt5 import QtWidgets as qw
                    qw.QMessageBox.information(self, 'Options Ready for Export', summary + '\n\nThese options are ready to be applied to a map patch.')
                except Exception:
                    pass

        def _on_apply_to_map(self):
            """
            Apply current tuning options to a full ECU binary (.bin) file.
            
            Workflow:
            1. Validate selected tuning options
            2. User selects a full ECU backup .bin file
            3. Creates modified copy with patches applied
            4. Saves to modified/ folder with timestamp
            5. Shows detailed results: patches applied, CRCs updated, affected zones
            """
            self._sync_options_from_ui()

            # Validate options first
            valid, error = self._ctrl.validate_options(self._current_options)
            if not valid:
                try:
                    from PySide6 import QtWidgets as qw
                    qw.QMessageBox.warning(self, 'Invalid Tuning Options', 
                        f'Selected options failed validation:\n\n{error}')
                except Exception:
                    try:
                        from PyQt5 import QtWidgets as qw
                        qw.QMessageBox.warning(self, 'Invalid Tuning Options', 
                            f'Selected options failed validation:\n\n{error}')
                    except Exception:
                        pass
                return

            # Get Qt widgets
            try:
                from PySide6 import QtWidgets as qw
            except Exception:
                try:
                    from PyQt5 import QtWidgets as qw
                except Exception:
                    return

            # Prompt user to select input ECU binary
            start_dir = Path('backups') if Path('backups').exists() else Path.cwd()
            filename, _ = qw.QFileDialog.getOpenFileName(
                self,
                'Select ECU Binary to Modify',
                str(start_dir),
                'Binary images (*.bin);;All files (*)',
            )
            if not filename:
                return

            bin_path = Path(filename)
            if not bin_path.exists():
                qw.QMessageBox.warning(self, 'File Not Found', f'Selected file does not exist:\n{bin_path}')
                return

            # Validate binary size (full ECU binary should be 2MB or 4MB)
            file_size = bin_path.stat().st_size
            if file_size not in (0x200000, 0x400000):  # 2MB or 4MB
                response = qw.QMessageBox.question(
                    self, 'Unusual File Size',
                    f'Selected file is {file_size} bytes ({file_size/(1024*1024):.1f} MB).\n'
                    f'Full ECU binaries are typically 2MB or 4MB.\n\n'
                    f'Continue anyway?',
                    qw.QMessageBox.Yes | qw.QMessageBox.No
                )
                if response == qw.QMessageBox.No:
                    return

            # Build PatchSet from tuning options
            patch_set, err = self._ctrl.build_patch_set(self._current_options, ecu_type='MSD81')
            if patch_set is None:
                qw.QMessageBox.warning(self, 'Patch Set Build Failed', 
                    f'Unable to build patches from tuning options:\n\n{err}')
                return

            if len(patch_set.patches) == 0:
                qw.QMessageBox.warning(self, 'No Patches to Apply', 
                    'The selected tuning options did not generate any patches.\n'
                    'Ensure at least one option is enabled.')
                return

            # Create output paths
            output_dir = bin_path.parent / 'modified'
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f'{bin_path.stem}_tuned_{timestamp}.bin'
            original_file = output_dir / f'{bin_path.stem}_original_{timestamp}.bin'

            # Show progress dialog
            progress = qw.QProgressDialog(
                'Applying tuning patches...',
                'Cancel',
                0, 100,
                self
            )
            progress.setWindowModality(qw.Qt.WindowModal)
            progress.show()

            # Copy original file unchanged
            try:
                import shutil
                progress.setValue(5)
                shutil.copy2(bin_path, original_file)
                progress.setValue(8)
            except Exception as exc:
                progress.close()
                qw.QMessageBox.warning(self, 'Failed to Copy Original', 
                    f'Could not create backup of original file:\n\n{exc}')
                return

            # Apply patches to binary
            try:
                from flash_tool import map_patcher as mp
                progress.setValue(10)
                result = mp.apply_patches_to_file(bin_path, output_file, patch_set, ecu_type='MSD81')
                progress.setValue(100)
            except Exception as exc:
                progress.close()
                qw.QMessageBox.critical(self, 'Patch Application Failed', 
                    f'Error while applying patches to binary:\n\n{exc}')
                return
            finally:
                progress.close()

            # Extract results
            applied = len(result.get('applied_patches', []))
            total = result.get('total_patches', 0)
            failed = len(result.get('failed_patches', []))
            updated_crc = result.get('updated_crc_count', 0)
            zones = result.get('affected_zones', [])
            errors = result.get('errors', [])

            # Build detailed results message
            msg_parts = [
                f'Modified ECU binary saved to:\n{output_file}',
                '',
                f'Original file (unchanged) saved to:\n{original_file}',
                '',
                f'Patches Applied: {applied}/{total}',
            ]

            if failed > 0:
                msg_parts.append(f'Failed: {failed}')
                msg_parts.append('')
                msg_parts.append('Failed Patches:')
                for err_item in result.get('failed_patches', []):
                    msg_parts.append(f'  - {err_item.get("name")}: {err_item.get("error")}')
                msg_parts.append('')

            msg_parts.extend([
                f'CRC Zones Updated: {updated_crc}',
                f'Affected Zones: {", ".join(zones) if zones else "(none)"}',
            ])

            if result.get('boost', {}).get('applied'):
                boost_info = result['boost']
                msg_parts.extend([
                    '',
                    f'Boost Modifications Applied:',
                    f'  Software Version: {boost_info.get("software_version", "unknown")}',
                    f'  Max Boost: {boost_info.get("max_boost_bar", 0):.1f} bar',
                    f'  Boost Increase: {boost_info.get("boost_increase_psi", 0):.1f} psi',
                ])

            msg = '\n'.join(msg_parts)

            # Show results dialog with option to open folder
            if failed == 0 and applied == total:
                qw.QMessageBox.information(self, 'Tuning Applied Successfully', msg)
            else:
                qw.QMessageBox.warning(self, 'Tuning Applied (with issues)', msg)

            # Ask if user wants to open folder
            response = qw.QMessageBox.question(
                self, 'Open Modified Folder?',
                f'Open the folder containing the modified binary?',
                qw.QMessageBox.Yes | qw.QMessageBox.No
            )
            if response == qw.QMessageBox.Yes:
                import os
                import subprocess
                import sys
                try:
                    if sys.platform == 'win32':
                        os.startfile(str(output_dir))
                    elif sys.platform == 'darwin':
                        subprocess.Popen(['open', str(output_dir)])
                    else:
                        subprocess.Popen(['xdg-open', str(output_dir)])
                except Exception as e:
                    qw.QMessageBox.warning(self, 'Could Not Open Folder', str(e))

        def _on_tune_and_flash(self):
            """
            Tune & Flash: Apply tuning options to a .bin file, then flash to ECU.
            
            This orchestrates the full pipeline:
            1. Validate options
            2. Select source .bin (backup or other)
            3. Apply patches + boost via MapPatcher
            4. Run pre-flash safety checks (VIN, SW-ID, battery, backup)
            5. Flash to ECU via map_flasher
            """
            self._sync_options_from_ui()

            valid, error = self._ctrl.validate_options(self._current_options)
            if not valid:
                try:
                    from PySide6 import QtWidgets as qw
                    qw.QMessageBox.warning(self, 'Validation Error', error)
                except Exception:
                    try:
                        from PyQt5 import QtWidgets as qw
                        qw.QMessageBox.warning(self, 'Validation Error', error)
                    except Exception:
                        pass
                return

            # Import Qt
            try:
                from PySide6 import QtWidgets as qw
            except Exception:
                try:
                    from PyQt5 import QtWidgets as qw
                except Exception:
                    return

            # Confirm the dangerous operation
            reply = qw.QMessageBox.warning(
                self,
                'Tune & Flash - Confirm',
                'This will:\n'
                '1. Apply tuning options to a .bin file\n'
                '2. Flash the result directly to ECU\n\n'
                'This is a DANGEROUS operation that writes to ECU memory.\n'
                'Ensure stable 12V+ power and do NOT disconnect during flash.\n\n'
                'Continue?',
                qw.QMessageBox.StandardButton.Yes | qw.QMessageBox.StandardButton.No,
                qw.QMessageBox.StandardButton.No
            )
            if reply != qw.QMessageBox.StandardButton.Yes:
                return

            # Select source .bin file
            start_dir = Path('backups') if Path('backups').exists() else Path.cwd()
            filename, _ = qw.QFileDialog.getOpenFileName(
                self,
                'Select Backup or Map File for Tune & Flash',
                str(start_dir),
                'Binary images (*.bin);;All files (*)',
            )
            if not filename:
                return

            bin_path = Path(filename)
            if not bin_path.exists():
                qw.QMessageBox.warning(self, 'File Not Found', f'Selected file does not exist:\n{bin_path}')
                return

            # Build PatchSet from options
            patch_set, err = self._ctrl.build_patch_set(self._current_options, ecu_type='MSD80')
            if patch_set is None:
                qw.QMessageBox.warning(self, 'Patch Build Failed', f'Unable to build patch set from options:\n{err}')
                return

            # Determine output file path
            output_dir = bin_path.parent / 'tuned'
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f'{bin_path.stem}_tuneflash_{timestamp}.bin'

            # Apply patches to file (includes boost and CRC updates)
            try:
                from flash_tool import map_patcher as mp
                from flash_tool import map_flasher as mf
                from flash_tool.direct_can_flasher import DirectCANFlasher

                result = mp.apply_patches_to_file(bin_path, output_file, patch_set, ecu_type='MSD80')
            except Exception as exc:
                qw.QMessageBox.critical(self, 'Patch Application Failed', f'Error applying patches:\n{exc}')
                return

            if not result.get('success', False):
                errors = '\n'.join(result.get('errors', []))
                qw.QMessageBox.critical(self, 'Patch Failed', f'Patching failed:\n{errors}')
                return

            applied = len(result.get('applied_patches', []))
            total = result.get('total_patches', 0)
            crc_count = result.get('updated_crc_count', 0)
            boost_info = result.get('boost', {})

            # Get VIN from ECU
            try:
                flasher = DirectCANFlasher()
                if not flasher.connect():
                    qw.QMessageBox.critical(self, 'Connection Failed', 'Cannot connect to ECU.\nEnsure K+DCAN cable is connected and ignition is ON.')
                    return

                vin = flasher.read_vin()
                flasher.disconnect()

                if not vin:
                    vin, ok = qw.QInputDialog.getText(self, 'Enter VIN', 'Could not read VIN from ECU.\nEnter VIN manually (17 chars):')
                    if not ok or len(vin) != 17:
                        qw.QMessageBox.warning(self, 'Invalid VIN', 'VIN must be 17 characters.')
                        return
            except Exception as exc:
                qw.QMessageBox.critical(self, 'ECU Error', f'Error communicating with ECU:\n{exc}')
                return

            # Run pre-flash safety checks
            try:
                prereq = mf.check_flash_prerequisites(vin, output_file)
            except Exception as exc:
                qw.QMessageBox.critical(self, 'Safety Check Error', f'Error running safety checks:\n{exc}')
                return

            if not prereq.get('all_checks_passed', False):
                errors = '\n'.join(prereq.get('errors', []))
                reply = qw.QMessageBox.warning(
                    self,
                    'Safety Checks Failed',
                    f'Pre-flash safety checks failed:\n{errors}\n\n'
                    'Do you want to override and proceed anyway?\n'
                    '(DANGEROUS - only do this if you understand the risks)',
                    qw.QMessageBox.StandardButton.Yes | qw.QMessageBox.StandardButton.No,
                    qw.QMessageBox.StandardButton.No
                )
                if reply != qw.QMessageBox.StandardButton.Yes:
                    return

            # Final confirmation
            confirm_msg = (
                f'About to flash:\n{output_file.name}\n\n'
                f'To ECU with VIN: {vin}\n\n'
                f'Patches applied: {applied}/{total}\n'
                f'CRC zones updated: {crc_count}\n'
            )
            if boost_info.get('applied', False):
                confirm_msg += f'Boost target: {boost_info.get("max_boost_bar", "?")} bar\n'

            confirm_msg += '\nThis cannot be undone without a backup!\n\nType "FLASH" to confirm:'

            text, ok = qw.QInputDialog.getText(self, 'Final Confirmation', confirm_msg)
            if not ok or text != 'FLASH':
                qw.QMessageBox.information(self, 'Cancelled', 'Flash operation cancelled.')
                return

            # Execute flash
            progress_dialog = qw.QProgressDialog('Flashing to ECU...', 'Cancel', 0, 100, self)
            progress_dialog.setWindowTitle('Tune & Flash')
            progress_dialog.setModal(True)
            progress_dialog.show()

            def progress_cb(msg: str, pct: int):
                progress_dialog.setValue(pct)
                progress_dialog.setLabelText(msg)
                qw.QApplication.processEvents()

            try:
                flash_result = mf.flash_map(
                    map_file=output_file,
                    vin=vin,
                    safety_confirmed=True,
                    progress_callback=progress_cb
                )
                progress_dialog.close()

                if flash_result.get('success', False):
                    duration = flash_result.get('duration_seconds', 0)
                    verified = flash_result.get('verification', {}).get('verified', False)
                    verify_str = 'Verified' if verified else 'Verification inconclusive'

                    qw.QMessageBox.information(
                        self,
                        'Flash Successful',
                        f'FLASH SUCCESSFUL!\n\n'
                        f'Duration: {duration:.1f} seconds\n'
                        f'{verify_str}\n\n'
                        f'Next steps:\n'
                        f'1. Turn ignition OFF, wait 10 seconds\n'
                        f'2. Turn ignition ON (do not start)\n'
                        f'3. Clear adaptations if needed\n'
                        f'4. Start engine and monitor for issues'
                    )
                else:
                    error = flash_result.get('error', 'Unknown error')
                    qw.QMessageBox.critical(
                        self,
                        'Flash Failed',
                        f'Flash operation failed:\n{error}\n\n'
                        f'ECU may still have original calibration.\n'
                        f'If unresponsive, restore from backup.'
                    )

            except Exception as exc:
                progress_dialog.close()
                qw.QMessageBox.critical(self, 'Flash Error', f'Error during flash:\n{exc}\n\nCheck ECU status immediately!')

    return _Widget(parent)
