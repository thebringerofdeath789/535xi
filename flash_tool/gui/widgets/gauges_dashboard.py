"""Enhanced Live Gauges Widget for GUI.

Provides real-time visual gauges for boost, RPM, speed, and other parameters.
Features analog-style gauges with needle indicators and digital readouts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import math

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, QTimer
    from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
        from PyQt5.QtCore import pyqtSignal as Signal, QTimer
        from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
    except Exception as exc:
        raise ImportError('Qt bindings not available for Gauges Widget') from exc


class AnalogGauge(QtWidgets.QWidget):
    """A single analog gauge with needle and scale."""
    
    def __init__(self, title: str = "Gauge", unit: str = "", 
                 min_val: float = 0, max_val: float = 100,
                 warning_val: Optional[float] = None,
                 danger_val: Optional[float] = None,
                 parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.warning_val = warning_val
        self.danger_val = danger_val
        self.value = min_val
        self.setMinimumSize(180, 180)
    
    def setValue(self, value: float):
        self.value = max(self.min_val, min(self.max_val, value))
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate dimensions
        side = min(self.width(), self.height())
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(side / 200, side / 200)
        
        # Draw outer ring
        painter.setPen(QPen(QColor(60, 60, 60), 3))
        painter.setBrush(QBrush(QColor(30, 30, 35)))
        painter.drawEllipse(-90, -90, 180, 180)
        
        # Draw scale arc
        start_angle = 225  # degrees
        span_angle = -270  # degrees (clockwise)
        
        # Draw colored zones
        if self.danger_val is not None:
            self._draw_zone(painter, self.danger_val, self.max_val, QColor(200, 50, 50), start_angle, span_angle)
        if self.warning_val is not None:
            warn_end = self.danger_val if self.danger_val else self.max_val
            self._draw_zone(painter, self.warning_val, warn_end, QColor(200, 150, 50), start_angle, span_angle)
        
        # Draw tick marks
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        num_ticks = 10
        for i in range(num_ticks + 1):
            angle = math.radians(start_angle + (span_angle * i / num_ticks))
            inner_r = 70 if i % 2 == 0 else 75
            outer_r = 82
            x1 = math.cos(angle) * inner_r
            y1 = -math.sin(angle) * inner_r
            x2 = math.cos(angle) * outer_r
            y2 = -math.sin(angle) * outer_r
            painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
            
            # Draw numbers for major ticks
            if i % 2 == 0:
                val = self.min_val + (self.max_val - self.min_val) * i / num_ticks
                text_r = 55
                tx = math.cos(angle) * text_r - 10
                ty = -math.sin(angle) * text_r + 5
                painter.setFont(QFont("Arial", 8))
                painter.drawText(QtCore.QRectF(tx, ty, 25, 15), 
                               QtCore.Qt.AlignmentFlag.AlignCenter, 
                               f"{val:.0f}")
        
        # Draw needle
        needle_angle = start_angle + span_angle * (self.value - self.min_val) / (self.max_val - self.min_val)
        needle_rad = math.radians(needle_angle)
        
        # Needle color based on value
        if self.danger_val and self.value >= self.danger_val:
            needle_color = QColor(255, 50, 50)
        elif self.warning_val and self.value >= self.warning_val:
            needle_color = QColor(255, 180, 50)
        else:
            needle_color = QColor(255, 100, 100)
        
        painter.setPen(QPen(needle_color, 3))
        painter.setBrush(QBrush(needle_color))
        
        # Draw needle
        needle_length = 65
        nx = math.cos(needle_rad) * needle_length
        ny = -math.sin(needle_rad) * needle_length
        painter.drawLine(QtCore.QPointF(0, 0), QtCore.QPointF(nx, ny))
        
        # Draw center cap
        painter.setBrush(QBrush(QColor(80, 80, 90)))
        painter.drawEllipse(-8, -8, 16, 16)
        
        # Draw title and value
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(QtCore.QRectF(-50, 25, 100, 20), 
                        QtCore.Qt.AlignmentFlag.AlignCenter, 
                        self.title)
        
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(QtCore.QRectF(-50, 45, 100, 25), 
                        QtCore.Qt.AlignmentFlag.AlignCenter, 
                        f"{self.value:.1f} {self.unit}")
    
    def _draw_zone(self, painter: QPainter, start_val: float, end_val: float, 
                   color: QColor, start_angle: float, span_angle: float):
        """Draw a colored zone on the gauge arc."""
        range_total = self.max_val - self.min_val
        start_frac = (start_val - self.min_val) / range_total
        end_frac = (end_val - self.min_val) / range_total
        
        zone_start = start_angle + span_angle * start_frac
        zone_span = span_angle * (end_frac - start_frac)
        
        painter.setPen(QPen(color, 8))
        painter.drawArc(-85, -85, 170, 170, int(zone_start * 16), int(zone_span * 16))


class DigitalReadout(QtWidgets.QFrame):
    """Digital LCD-style readout for a single value."""
    
    def __init__(self, title: str = "", unit: str = "", 
                 decimals: int = 1, parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.decimals = decimals
        self.value = 0.0
        
        self.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Sunken)
        self.setStyleSheet("background: #1a1a1a; border: 2px solid #333; border-radius: 5px;")
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet("color: #888; font-size: 10px;")
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        self.value_label = QtWidgets.QLabel("0.0")
        self.value_label.setStyleSheet("color: #0f0; font-size: 24px; font-family: 'Courier New', monospace;")
        self.value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        
        self.unit_label = QtWidgets.QLabel(unit)
        self.unit_label.setStyleSheet("color: #888; font-size: 10px;")
        self.unit_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.unit_label)
        
        self.setMinimumSize(100, 80)
    
    def setValue(self, value: float):
        self.value = value
        self.value_label.setText(f"{value:.{self.decimals}f}")


class GaugesDashboard(QtWidgets.QWidget):
    """Full dashboard with multiple gauges for vehicle data."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Gauge profile configuration: maps profile names to logical keys
        # and visual scaling for each of the three analog gauges.
        self._profiles = {
            "Boost / RPM / Speed": {
                'left': ('boost', "BOOST", "PSI", -15.0, 30.0, 20.0, 25.0),
                'center': ('rpm', "RPM", "x1000", 0.0, 8.0, 6.5, 7.2),
                'right': ('speed', "SPEED", "MPH", 0.0, 180.0, None, None),
            },
            "Safety (Coolant / Oil / Boost)": {
                'left': ('coolant', "COOLANT", "°F", 120.0, 260.0, 230.0, 245.0),
                'center': ('oil_temp', "OIL TEMP", "°F", 150.0, 280.0, 250.0, 265.0),
                'right': ('boost', "BOOST", "PSI", -15.0, 30.0, 20.0, 25.0),
            },
            "Fuel & AFR (AFR / Fuel / RPM)": {
                'left': ('afr', "AFR", "", 8.0, 20.0, None, None),
                'center': ('fuel_pressure', "FUEL PRES", "PSI", 500.0, 3000.0, None, None),
                'right': ('rpm', "RPM", "x1000", 0.0, 8.0, 6.5, 7.2),
            },
        }
        self._current_profile: str = "Boost / RPM / Speed"
        self._gauge_map: Dict[str, str] = {}
        self._setup_ui()
        self._demo_mode = False
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._update_demo)
        self._demo_angle = 0

        # Live OBD streaming support (shared with OBD Logger controller
        # so we reuse the same session and safety logic).
        self._obd_timer = QTimer(self)
        self._obd_timer.timeout.connect(self._poll_obd)
        self._obd_controller: Optional[Any] = None
        self._pid_ids: Dict[str, str] = {}
        self._init_obd_support()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Add help button (top right)
        help_btn = QtWidgets.QPushButton('Help')
        help_btn.setToolTip('Show help and usage instructions for the Gauges Dashboard.')
        help_btn.setFixedWidth(60)
        help_btn.clicked.connect(self._show_help_dialog)
        hlayout = QtWidgets.QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(help_btn)
        layout.addLayout(hlayout)

        # Title bar
        title_bar = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Live Vehicle Dashboard")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        title.setToolTip("Displays real-time vehicle data using analog and digital gauges.")
        title_bar.addWidget(title)
        # Gauge profile selector
        title_bar.addStretch()
        self.profile_combo = QtWidgets.QComboBox()
        for name in sorted(self._profiles.keys()):
            self.profile_combo.addItem(name)
        try:
            idx = self.profile_combo.findText(self._current_profile)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        except Exception:
            pass
        self.profile_combo.setToolTip("Select which set of gauges to display (Boost/RPM/Speed, Safety, Fuel & AFR)")
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        title_bar.addWidget(QtWidgets.QLabel("Profile:"))
        title_bar.addWidget(self.profile_combo)

        self.demo_btn = QtWidgets.QPushButton("▶ Demo Mode")
        self.demo_btn.setCheckable(True)
        self.demo_btn.setToolTip("Toggle simulated demo mode for gauges.")
        self.demo_btn.toggled.connect(self._toggle_demo)
        title_bar.addWidget(self.demo_btn)

        self.connect_btn = QtWidgets.QPushButton("Connect OBD")
        self.connect_btn.setToolTip("Connect to the vehicle's OBD-II port and stream live data.")
        self.connect_btn.clicked.connect(self._on_connect)
        title_bar.addWidget(self.connect_btn)

        layout.addLayout(title_bar)
        
        # Main gauges area
        gauges_layout = QtWidgets.QHBoxLayout()
        
        # Left side - Boost gauge (large)
        boost_frame = QtWidgets.QFrame()
        boost_frame.setStyleSheet("background: #1e1e1e; border-radius: 10px;")
        boost_layout = QtWidgets.QVBoxLayout(boost_frame)
        
        self.boost_gauge = AnalogGauge(
            title="BOOST", unit="PSI",
            min_val=-15, max_val=30,
            warning_val=20, danger_val=25
        )
        self.boost_gauge.setMinimumSize(220, 220)
        self.boost_gauge.setToolTip("Shows current boost/vacuum pressure in PSI.")
        boost_layout.addWidget(self.boost_gauge)
        gauges_layout.addWidget(boost_frame)
        
        # Center - RPM gauge (large)
        rpm_frame = QtWidgets.QFrame()
        rpm_frame.setStyleSheet("background: #1e1e1e; border-radius: 10px;")
        rpm_layout = QtWidgets.QVBoxLayout(rpm_frame)
        
        self.rpm_gauge = AnalogGauge(
            title="RPM", unit="x1000",
            min_val=0, max_val=8,
            warning_val=6.5, danger_val=7.2
        )
        self.rpm_gauge.setMinimumSize(220, 220)
        self.rpm_gauge.setToolTip("Shows engine speed in thousands of RPM.")
        rpm_layout.addWidget(self.rpm_gauge)
        gauges_layout.addWidget(rpm_frame)
        
        # Right side - Speed gauge
        speed_frame = QtWidgets.QFrame()
        speed_frame.setStyleSheet("background: #1e1e1e; border-radius: 10px;")
        speed_layout = QtWidgets.QVBoxLayout(speed_frame)
        
        self.speed_gauge = AnalogGauge(
            title="SPEED", unit="MPH",
            min_val=0, max_val=180,
            warning_val=None, danger_val=None
        )
        self.speed_gauge.setMinimumSize(220, 220)
        self.speed_gauge.setToolTip("Shows vehicle speed in miles per hour.")
        speed_layout.addWidget(self.speed_gauge)
        gauges_layout.addWidget(speed_frame)
        
        layout.addLayout(gauges_layout)
        
        # Digital readouts row
        digital_layout = QtWidgets.QHBoxLayout()
        
        self.iat_readout = DigitalReadout("IAT", "°F", 0)
        self.iat_readout.setToolTip("Intake Air Temperature in Fahrenheit.")
        digital_layout.addWidget(self.iat_readout)

        self.coolant_readout = DigitalReadout("COOLANT", "°F", 0)
        self.coolant_readout.setToolTip("Engine coolant temperature in Fahrenheit.")
        digital_layout.addWidget(self.coolant_readout)

        self.oil_readout = DigitalReadout("OIL TEMP", "°F", 0)
        self.oil_readout.setToolTip("Engine oil temperature in Fahrenheit.")
        digital_layout.addWidget(self.oil_readout)

        self.afr_readout = DigitalReadout("AFR", "", 2)
        self.afr_readout.setToolTip("Air-fuel ratio (lambda) value.")
        digital_layout.addWidget(self.afr_readout)

        self.timing_readout = DigitalReadout("TIMING", "°", 1)
        self.timing_readout.setToolTip("Ignition timing advance in degrees.")
        digital_layout.addWidget(self.timing_readout)

        self.fuel_readout = DigitalReadout("FUEL PRES", "PSI", 0)
        self.fuel_readout.setToolTip("Fuel rail pressure in PSI.")
        digital_layout.addWidget(self.fuel_readout)
        
        layout.addLayout(digital_layout)
        
        # Status bar
        self.status_label = QtWidgets.QLabel("Disconnected - Click 'Connect OBD' or enable Demo Mode")
        self.status_label.setStyleSheet("color: #888; padding: 5px;")
        self.status_label.setToolTip("Shows the current connection status and error messages.")
        layout.addWidget(self.status_label)
            def _show_help_dialog(self):
                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle('Gauges Dashboard Help')
                msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
                msg.setText(
                    '<b>Gauges Dashboard Help</b><br><br>'
                    '<b>Purpose:</b> Display real-time vehicle data using analog and digital gauges.<br>'
                    '<ul>'
                    '<li><b>Profile:</b> Select which set of gauges to display (Boost/RPM/Speed, Safety, Fuel & AFR).</li>'
                    '<li><b>Demo Mode:</b> Simulate live data for demonstration and testing.</li>'
                    '<li><b>Connect OBD:</b> Connect to the vehicle and stream live data to the gauges.</li>'
                    '<li><b>Status Bar:</b> Shows connection state and error messages.</li>'
                    '<li><b>Tooltips:</b> Hover over any gauge or control for more information.</li>'
                    '</ul>'
                    '<b>Tips:</b> Use the help button for guidance at any time.'
                )
                msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
                msg.exec()
        
        # Set dark background
        self.setStyleSheet("background: #121212;")

        # Apply default gauge profile now that gauges are constructed.
        self._apply_profile(self._current_profile)

    def _configure_gauge(self, gauge: AnalogGauge, title: str, unit: str,
                          min_val: float, max_val: float,
                          warning_val: Optional[float], danger_val: Optional[float]) -> None:
        gauge.title = title
        gauge.unit = unit
        gauge.min_val = min_val
        gauge.max_val = max_val
        gauge.warning_val = warning_val
        gauge.danger_val = danger_val
        gauge.update()

    def update_value(self, gauge_id: str, value: float) -> bool:
        """Update a gauge value by ID.
        
        Args:
            gauge_id: One of 'boost', 'rpm', 'speed', 'iat', 'coolant', 'oil', 'afr', 'fuel', 'timing'
            value: Numeric value to display
        
        Returns:
            True if gauge exists and updated, False otherwise
        """
        gauge_map = {
            'boost': self.boost_gauge, 'rpm': self.rpm_gauge, 'speed': self.speed_gauge,
            'iat': self.iat_readout, 'coolant': self.coolant_readout, 'oil': self.oil_readout,
            'afr': self.afr_readout, 'fuel': self.fuel_readout, 'timing': self.timing_readout
        }
        gauge = gauge_map.get(gauge_id.lower())
        if gauge and hasattr(gauge, 'setValue'):
            gauge.setValue(value)
            return True
        return False

    def _apply_profile(self, name: str) -> None:
        profile = self._profiles.get(name)
        if not profile:
            return
        self._current_profile = name
        # Update logical mapping and visual configuration
        self._gauge_map = {}
        for pos, cfg in profile.items():
            key, title, unit, mn, mx, warn, danger = cfg
            self._gauge_map[pos] = key
            if pos == 'left':
                self._configure_gauge(self.boost_gauge, title, unit, mn, mx, warn, danger)
            elif pos == 'center':
                self._configure_gauge(self.rpm_gauge, title, unit, mn, mx, warn, danger)
            elif pos == 'right':
                self._configure_gauge(self.speed_gauge, title, unit, mn, mx, warn, danger)

    def _on_profile_changed(self, name: str) -> None:
        self._apply_profile(name)

    def _init_obd_support(self) -> None:
        """Initialize OBD logging controller and map required PIDs.

        This function is best-effort: if anything fails (missing modules,
        no PID catalog, etc.) the gauges will still work in Demo Mode and
        the Connect button will show a clear error instead of a placeholder.
        """
        try:
            # Import here to avoid circular Qt imports: the controller
            # itself does not depend on Qt.
            from flash_tool.gui.widgets.obd_logger import OBDLoggerController  # type: ignore

            self._obd_controller = OBDLoggerController()
        except Exception:
            self._obd_controller = None
            self._pid_ids = {}
            return

        try:
            from flash_tool import n54_pids as _pids  # type: ignore
        except Exception:
            self._pid_ids = {}
            return

        desired = {
            'rpm': "Engine RPM",
            'speed': "Vehicle Speed",
            'boost': "Actual Boost Pressure",
            'iat': "Intake Air Temperature",
            'coolant': "Coolant Temperature",
            'oil_temp': "Engine Oil Temperature",
            'afr': "Lambda Bank 1",
            'timing': "Ignition Timing Cyl 1",
            'fuel_pressure': "Fuel Rail Pressure",
        }

        pid_ids: Dict[str, str] = {}
        for key, name in desired.items():
            try:
                pid_def = _pids.get_pid_by_name(name)
            except Exception:
                pid_def = None
            if pid_def is not None and getattr(pid_def, 'pid', None):
                pid_ids[key] = pid_def.pid  # type: ignore[assignment]

        self._pid_ids = pid_ids
    
    def _toggle_demo(self, checked: bool):
        self._demo_mode = checked
        if checked:
            self.demo_btn.setText("Stop Demo")
            self._demo_timer.start(50)  # 20 FPS
            self.status_label.setText("Demo Mode Active")
        else:
            self.demo_btn.setText("Demo Mode")
            self._demo_timer.stop()
            self.status_label.setText("Demo Mode Stopped")
    
    def _update_demo(self):
        """Update gauges with simulated data."""
        import math
        self._demo_angle += 0.05
        
        # Simulate acceleration/deceleration
        t = self._demo_angle
        rpm = 3500 + 2500 * math.sin(t * 0.5) + 500 * math.sin(t * 2)
        rpm = max(800, min(7500, rpm))
        
        speed = 40 + 60 * math.sin(t * 0.3) + 20 * math.sin(t * 0.8)
        speed = max(0, min(160, speed))
        
        # Boost correlates with RPM
        boost = -10 + 25 * (rpm / 7500) + 5 * math.sin(t * 0.7)
        boost = max(-15, min(28, boost))
        
        # Update gauges
        self.rpm_gauge.setValue(rpm / 1000)
        self.speed_gauge.setValue(speed)
        self.boost_gauge.setValue(boost)
        
        # Update digital readouts
        self.iat_readout.setValue(85 + 30 * math.sin(t * 0.1))
        self.coolant_readout.setValue(190 + 10 * math.sin(t * 0.05))
        self.oil_readout.setValue(210 + 20 * math.sin(t * 0.08))
        self.afr_readout.setValue(12.5 + 2 * math.sin(t * 0.6))
        self.timing_readout.setValue(15 + 10 * math.sin(t * 0.4))
        self.fuel_readout.setValue(2000 + 500 * math.sin(t * 0.5))
    
    def _on_connect(self):
        # If demo mode is running, turn it off before attempting a
        # real OBD session so the two don't compete.
        if self._demo_mode:
            self.demo_btn.setChecked(False)
            self._toggle_demo(False)

        if self._obd_controller is None or not self._pid_ids:
            QtWidgets.QMessageBox.warning(
                self,
                "Live Gauges",
                "Live OBD gauges are not available because the OBD logger "
                "or PID catalog could not be initialized.\n\n"
                "Check that python-obd and N54 PID definitions are installed.",
            )
            return

        # Toggle: if already streaming, treat as disconnect.
        if self._obd_timer.isActive():
            self._obd_timer.stop()
            try:
                self._obd_controller.disconnect()  # type: ignore[union-attr]
            except Exception:
                pass
            self.connect_btn.setText("Connect OBD")
            self.status_label.setText("Disconnected - Click 'Connect OBD' or enable Demo Mode")
            return

        # Start or attach to shared OBD session via the logger controller.
        try:
            res = self._obd_controller.connect(port=None, baudrate=38400)  # type: ignore[union-attr]
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Connect Failed", str(exc))
            self.status_label.setText(f"Connect failed: {exc}")
            return

        if not isinstance(res, dict) or not res.get('success'):
            err = res.get('error') if isinstance(res, dict) else "unknown error"
            QtWidgets.QMessageBox.warning(self, "Connect Failed", str(err))
            self.status_label.setText(f"Connect failed: {err}")
            return

        port = res.get('port') or 'OBD'
        self.connect_btn.setText("⏹ Disconnect")
        self.status_label.setText(f"Connected on {port} - streaming live data")
        # Poll a few times per second for smooth gauges.
        self._obd_timer.start(200)
    
    def update_values(self, data: Dict[str, float]):
        """Update gauges with real OBD data."""
        # Analog gauges follow the active profile mapping.
        for pos, gauge in (('left', self.boost_gauge),
                           ('center', self.rpm_gauge),
                           ('right', self.speed_gauge)):
            key = self._gauge_map.get(pos)
            if not key or key not in data:
                continue
            val = data[key]
            try:
                v = float(val)
            except Exception:
                continue
            if key == 'rpm':
                v = v / 1000.0
            gauge.setValue(v)
        if 'iat' in data:
            self.iat_readout.setValue(data['iat'])
        if 'coolant' in data:
            self.coolant_readout.setValue(data['coolant'])
        if 'oil_temp' in data:
            self.oil_readout.setValue(data['oil_temp'])
        if 'afr' in data:
            self.afr_readout.setValue(data['afr'])
        if 'timing' in data:
            self.timing_readout.setValue(data['timing'])
        if 'fuel_pressure' in data:
            self.fuel_readout.setValue(data['fuel_pressure'])

    def _poll_obd(self) -> None:
        """Poll current OBD session and push values into gauges."""
        if self._obd_controller is None or not self._pid_ids:
            self._obd_timer.stop()
            return

        try:
            pid_list = list(self._pid_ids.values())
            if not pid_list:
                return
            res = self._obd_controller.read_pids(pid_list)  # type: ignore[union-attr]
        except Exception as exc:
            self.status_label.setText(f"Read error: {exc}")
            self._obd_timer.stop()
            return

        if not isinstance(res, dict) or not res.get('success'):
            err = res.get('error') if isinstance(res, dict) else "unknown error"
            self.status_label.setText(f"PID read error: {err}")
            return

        raw = res.get('data') or {}
        values: Dict[str, float] = {}
        for logical_key, pid_id in self._pid_ids.items():
            try:
                v = raw.get(pid_id, {}).get('value')
            except Exception:
                v = None
            if v is None:
                continue
            try:
                values[logical_key] = float(v)
            except Exception:
                continue

        if values:
            self.update_values(values)


class GaugesController:
    """Controller for the gauges dashboard."""
    
    def __init__(self, log_controller: Optional[Any] = None):
        self.log_controller = log_controller


def create_qt_widget(controller: Optional[GaugesController] = None, parent=None):
    if controller is None:
        controller = GaugesController()
    return GaugesDashboard(parent)
