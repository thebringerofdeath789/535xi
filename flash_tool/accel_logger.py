#!/usr/bin/env python3
"""
Acceleration Logger for BMW N54 tool

Features:
- Monitor vehicle speed and RPM
- Auto-detect acceleration runs using configurable delta threshold
- Record run samples to CSV and write JSON metadata
- Minimal, dependency-free implementation for unit testing and CLI integration

Design notes:
- The module supports two modes: manual start/stop and automatic detection.
- For testability this module accepts `speed_reader` and `rpm_reader` callables.
  If `connection` is provided instead, the module will attempt to read
  PIDs via `flash_tool.obd_reader.read_pid_data` for standard Mode 01 PIDs.

"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from . import settings_manager
from typing import Callable, Optional, Any, List, Dict
import csv
import json
import datetime
import logging

from . import obd_session_manager

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    start_time: str
    end_time: Optional[str]
    start_speed: Optional[float]
    end_speed: Optional[float]
    peak_speed: Optional[float]
    peak_rpm: Optional[float]
    samples: int
    csv_file: str
    meta_file: str


class AccelLogger:
    """Acceleration logger.

    Parameters
    - speed_reader: callable -> float (km/h). If None and `connection` is
      provided, the logger will attempt to read PID '0D' via `read_pid_data`.
    - rpm_reader: callable -> float (RPM). If None and `connection` provided,
      reads PID '0C'.
    - connection: optional OBD connection object. If present and readers are
      omitted, the logger will use `flash_tool.obd_reader.read_pid_data`.
    - interval: sampling interval in seconds (default 0.05)
    - output_dir: Path where CSV/metadata files are written
    - filename_prefix: prefix for generated files

    This implementation uses a single polling thread (no background DataLogger)
    which makes behaviour deterministic and simple to test.
    """

    def __init__(
        self,
        speed_reader: Optional[Callable[[], Any]] = None,
        rpm_reader: Optional[Callable[[], Any]] = None,
        connection: Optional[Any] = None,
        interval: float = 0.05,
        output_dir: Optional[Path] = None,
        filename_prefix: str = "accel",
        start_delta_kmh: float = 10.0,
        min_start_speed: float = 5.0,
        min_samples_for_detection: int = 3,
    ) -> None:
        self.interval = float(interval)
        self._connection = connection
        self._speed_reader = speed_reader
        self._rpm_reader = rpm_reader
        if output_dir is None:
            try:
                mgr = settings_manager.get_settings_manager()
                logs_dir = mgr.get_setting("PATHS", "logs_directory", "logs")
                output_dir = Path(logs_dir) / "accel"
            except Exception:
                output_dir = Path("logs") / "accel"
        self.output_dir = Path(output_dir) if output_dir else Path("logs") / "accel"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.filename_prefix = filename_prefix

        # Auto-detect parameters
        self.start_delta_kmh = float(start_delta_kmh)
        self.min_start_speed = float(min_start_speed)
        self.min_samples_for_detection = int(min_samples_for_detection)

        # Internal state
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._monitor_lock = threading.Lock()

        self._recent_speeds: deque[float] = deque(maxlen=5)
        self._run_active = False
        self._current_samples: List[Dict[str, Any]] = []
        self._run_start_time: Optional[float] = None
        self._peak_speed: Optional[float] = None
        self._peak_rpm: Optional[float] = None

        self._history: List[RunSummary] = []

    # ------------------ Reader helpers ------------------
    def _default_speed(self) -> float:
        # If a custom reader is provided, use it
        if self._speed_reader:
            return float(self._safe_call(self._speed_reader, 0.0))

        # If connection provided, attempt to use obd_reader
        if self._connection is not None:
            try:
                from . import obd_reader
                res = obd_reader.read_pid_data(["0D"], connection=self._connection)
                val = res.get("0D", {}).get("value")
                return float(val) if val is not None else 0.0
            except Exception:
                return 0.0

        return 0.0

    def _default_rpm(self) -> float:
        if self._rpm_reader:
            return float(self._safe_call(self._rpm_reader, 0.0))

        if self._connection is not None:
            try:
                from . import obd_reader
                res = obd_reader.read_pid_data(["0C"], connection=self._connection)
                val = res.get("0C", {}).get("value")
                return float(val) if val is not None else 0.0
            except Exception:
                return 0.0

        return 0.0

    def _safe_call(self, fn: Callable[[], Any], default: Any = None) -> Any:
        try:
            return fn()
        except Exception:
            return default

    # ------------------ Monitoring & run control ------------------
    def start_monitor(self, auto_detect: bool = True) -> None:
        """Start the monitor thread. If `auto_detect` is True, runs will be
        auto-detected according to configured thresholds."""
        with self._monitor_lock:
            if self._monitor_thread and self._monitor_thread.is_alive():
                return
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(auto_detect,), daemon=True)
            self._monitor_thread.start()

    def stop_monitor(self) -> None:
        """Stop monitor thread and stop any active run."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        if self._run_active:
            self.stop_run()

    def _monitor_loop(self, auto_detect: bool) -> None:
        logger.debug("AccelLogger monitor started")
        while not self._stop_event.is_set():
            ts = datetime.datetime.utcnow().isoformat()
            speed = self._default_speed()
            rpm = self._default_rpm()

            # maintain recent speeds for delta-based detection
            self._recent_speeds.append(speed)

            # auto-detect start
            if not self._run_active and auto_detect and len(self._recent_speeds) >= self.min_samples_for_detection:
                min_recent = min(self._recent_speeds)
                if (speed - min_recent) >= self.start_delta_kmh and speed >= self.min_start_speed:
                    logger.info(f"Auto-detected run start: speed={speed} km/h delta={speed-min_recent}")
                    self.start_run()

            # if running, collect sample
            if self._run_active:
                # append sample
                self._current_samples.append({
                    'timestamp': ts,
                    'speed_kmh': speed,
                    'rpm': rpm
                })

                # update peaks
                if self._peak_speed is None or (speed is not None and speed > self._peak_speed):
                    self._peak_speed = speed
                if self._peak_rpm is None or (rpm is not None and rpm > self._peak_rpm):
                    self._peak_rpm = rpm

            time.sleep(self.interval)

        logger.debug("AccelLogger monitor stopped")

    def start_run(self) -> None:
        """Manually start a run. If already running, this is a no-op."""
        if self._run_active:
            return
        self._run_active = True
        self._current_samples = []
        self._run_start_time = time.time()
        self._peak_speed = 0.0
        self._peak_rpm = 0.0
        logger.info("Accel run started")
        # Take an immediate sample to ensure deterministic minimum sample
        # count during tests that rely on short sleeps. This avoids flaky
        # failures caused by thread scheduling delays in the monitor loop.
        try:
            ts = datetime.datetime.utcnow().isoformat()
            speed = self._default_speed()
            rpm = self._default_rpm()
            self._current_samples.append({
                'timestamp': ts,
                'speed_kmh': speed,
                'rpm': rpm
            })
            # update peaks based on immediate sample
            if speed is not None and (self._peak_speed is None or speed > self._peak_speed):
                self._peak_speed = speed
            if rpm is not None and (self._peak_rpm is None or rpm > self._peak_rpm):
                self._peak_rpm = rpm
        except Exception:
            # best-effort only; do not let sampling errors block starting the run
            pass

    def stop_run(self) -> Optional[RunSummary]:
        """Stop the active run, write CSV and metadata, and return a RunSummary.
        If no run is active, returns None."""
        if not self._run_active:
            return None

        end_time = time.time()
        start_ts = datetime.datetime.fromtimestamp(self._run_start_time, tz=datetime.timezone.utc).isoformat() if self._run_start_time else datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        end_ts = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc).isoformat()
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        # Prepare file names
        csv_name = f"{self.filename_prefix}_{timestamp}.csv"
        meta_name = f"{self.filename_prefix}_{timestamp}.json"
        csv_path = self.output_dir / csv_name
        meta_path = self.output_dir / meta_name

        # Write CSV
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'speed_kmh', 'rpm'])
                for s in self._current_samples:
                    writer.writerow([s.get('timestamp'), s.get('speed_kmh'), s.get('rpm')])
        except Exception as e:
            logger.error(f"Failed to write CSV: {e}")

        # Build metadata
        meta = {
            'start_time': start_ts,
            'end_time': end_ts,
            'start_speed': float(self._current_samples[0]['speed_kmh']) if self._current_samples else 0.0,
            'end_speed': float(self._current_samples[-1]['speed_kmh']) if self._current_samples else 0.0,
            'peak_speed': float(self._peak_speed),
            'peak_rpm': float(self._peak_rpm),
            'samples': len(self._current_samples),
            'csv_file': str(csv_path.name)
        }

        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write metadata: {e}")

        summary = RunSummary(
            start_time=meta['start_time'],
            end_time=meta['end_time'],
            start_speed=meta['start_speed'],
            end_speed=meta['end_speed'],
            peak_speed=meta['peak_speed'],
            peak_rpm=meta['peak_rpm'],
            samples=meta['samples'],
            csv_file=str(csv_path.name),
            meta_file=str(meta_path.name),
        )

        self._history.append(summary)

        # Reset run state
        self._run_active = False
        self._current_samples = []
        self._run_start_time = None
        self._peak_speed = None
        self._peak_rpm = None

        logger.info(f"Accel run stopped. Samples: {summary.samples}, CSV: {summary.csv_file}")
        return summary

    # ------------------ Utilities ------------------
    def is_monitoring(self) -> bool:
        return bool(self._monitor_thread and self._monitor_thread.is_alive())

    def is_running(self) -> bool:
        return bool(self._run_active)

    def get_history(self) -> List[RunSummary]:
        return list(self._history)


__all__ = ["AccelLogger", "RunSummary"]
