#!/usr/bin/env python3
"""Simple, robust data-logger for the 535xi CLI tool.

Features:
- Channel abstraction (`Channel`) with a read function
- Timed polling loop with configurable interval
- CSV output with timestamped rows and header
- Session naming, output directory control, file rotation by size
- Lightweight, dependency-free (works with mock readers); can be integrated with `python-can` adapters

This module is designed for CLI use and unit testing.
"""
from __future__ import annotations

import threading
import time
import csv
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Any
import datetime
import logging

logger = logging.getLogger(__name__)
import logging

try:
    # lazy import settings manager (optional)
    from flash_tool import settings_manager
except Exception as exc:
    logging.getLogger(__name__).exception("Failed to import settings_manager; falling back to defaults", exc_info=exc)
    settings_manager = None


@dataclass
class Channel:
    """A single named channel with a callable that returns a value.

    The `read_func` should be a callable with no arguments that returns a
    JSON-serializable / CSV-serializable value (str/number/None).
    """

    name: str
    read_func: Callable[[], Any]


class DataLogger:
    """Core data-logging engine.

    Usage (simple):
        ch = Channel('rpm', lambda: 1234)
        dl = DataLogger(channels=[ch], interval=0.5)
        dl.start(session_name='mysession', duration=10)

    The logger writes CSV files into `output_dir` (default: settings 'logs_directory' or './logs').
    """

    def __init__(
        self,
        channels: Optional[List[Channel]] = None,
        interval: float = 0.5,
        output_dir: Optional[Path] = None,
        filename_prefix: str = "datalog",
        max_file_size_mb: float = 50.0,
        rotate: bool = True,
        fmt: str = "csv",
    ) -> None:
        self.channels = channels or []
        self.interval = float(interval)
        self.filename_prefix = filename_prefix
        self.max_file_size_mb = float(max_file_size_mb)
        self.rotate = bool(rotate)
        self.fmt = fmt

        if output_dir is None:
            if settings_manager:
                try:
                    mgr = settings_manager.get_settings_manager()
                    logs_dir = mgr.get_setting("PATHS", "logs_directory", "logs")
                    output_dir = Path(logs_dir)
                except Exception as exc:
                    logger.exception("Failed to read logs_directory from settings; using ./logs", exc_info=exc)
                    output_dir = Path("logs")
            else:
                output_dir = Path("logs")

        self.output_dir: Path = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._current_file = None
        self._writer = None
        self._file_path: Optional[Path] = None
        self._session_name: Optional[str] = None
        self._session_start: Optional[datetime.datetime] = None

    def add_channel(self, channel: Channel) -> None:
        self.channels.append(channel)

    def start(self, session_name: Optional[str] = None, duration: Optional[float] = None) -> None:
        """Start logging in a background thread.

        Args:
            session_name: optional user-readable session name
            duration: optional duration in seconds (stop after N seconds)
        """
        self._session_name = session_name or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self._session_start = datetime.datetime.now()
        self._open_file()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(duration,), daemon=True)
        self._thread.start()

    def stop(self, wait: bool = True) -> None:
        """Signal the logger to stop and close the file."""
        self._stop.set()
        if wait and self._thread:
            self._thread.join(timeout=5.0)
        self._close_file()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _open_file(self) -> None:
        fname = f"{self.filename_prefix}_{self._session_name}_{uuid.uuid4().hex[:8]}.{self.fmt}"
        self._file_path = self.output_dir / fname
        self._current_file = open(self._file_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._current_file)
        header = ["timestamp"] + [c.name for c in self.channels]
        self._writer.writerow(header)
        self._current_file.flush()

    def _close_file(self) -> None:
        if self._current_file:
            try:
                self._current_file.flush()
                self._current_file.close()
            finally:
                self._current_file = None
                self._writer = None

    def _rotate_if_needed(self) -> None:
        if not self.rotate or not self._file_path or not self._file_path.exists():
            return
        size_mb = self._file_path.stat().st_size / (1024.0 * 1024.0)
        if size_mb >= self.max_file_size_mb:
            self._close_file()
            self._open_file()

    def _run(self, duration: Optional[float]) -> None:
        start = time.time()
        while not self._stop.is_set():
            now = datetime.datetime.utcnow().isoformat()
            row = [now]
            for ch in self.channels:
                try:
                    val = ch.read_func()
                except Exception as exc:
                    logger.exception("Channel read failed", exc_info=exc)
                    val = None
                row.append(val)

            if self._writer:
                try:
                    self._writer.writerow(row)
                    self._current_file.flush()
                except Exception as exc:
                    logger.exception("Failed to write log row", exc_info=exc)
                    return

            self._rotate_if_needed()
            if duration and (time.time() - start) >= duration:
                break
            time.sleep(self.interval)


__all__ = ["Channel", "DataLogger"]
