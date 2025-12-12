#!/usr/bin/env python3
"""Helpers to build DataLogger channels from N54 PID definitions.

This module bridges the generic DataLogger engine to the existing
OBD/UDS live-data stack:

- Uses n54_pids to resolve PID metadata (name/unit/category).
- Uses obd_session_manager + obd_reader.read_pid_data to retrieve values.
- Avoids any mock or placeholder behaviour; all reads go through the
  production OBD/UDS code paths.

Typical usage (CLI):

    from flash_tool.data_logger import DataLogger
    from flash_tool import logger_integration

    pid_ids = ["0C", "0D", "BOOST_ACTUAL"]
    channels = logger_integration.build_channels_for_pids(pid_ids, interval=0.2)
    dl = DataLogger(channels=channels, interval=0.2)
    dl.start(session_name="road_test", duration=30.0)

The per-channel read functions share a single internal sampler object so
that each polling cycle performs at most one PID batch read.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import time

from .data_logger import Channel
from . import obd_reader
from . import obd_session_manager
from . import n54_pids


class _PIDSampler:
    """Shared sampler for a set of PIDs.

    This helper performs batched reads via obd_reader.read_pid_data and
    caches the most recent results for a short window so that individual
    channel read functions can reuse the same data within a single
    DataLogger polling cycle.
    """

    def __init__(
        self,
        pid_ids: List[str],
        interval: float,
        connection: Optional[Any] = None,
    ) -> None:
        self._pid_ids: List[str] = list(pid_ids)
        self._interval: float = float(interval) if interval > 0 else 0.5
        self._connection: Optional[Any] = connection
        self._last_read_ts: float = 0.0
        self._last_values: Dict[str, Dict[str, Any]] = {}

    def _ensure_connection(self) -> None:
        """Attach to an existing OBD session if no connection is set.

        This NEVER auto-opens a new connection or infers ports; it only
        reuses an already-active session, mirroring how other GUI/CLI
        components behave.
        """

        if self._connection is not None:
            return

        try:
            session = obd_session_manager.get_session()
            if session.is_connected():
                from flash_tool.obd_session_manager import get_active_connection  # type: ignore

                conn = get_active_connection()
                if conn is not None:
                    self._connection = conn
        except Exception:
            # Best-effort only; if we cannot attach, reads will return None.
            self._connection = None

    def _refresh_if_needed(self) -> None:
        """Refresh cached PID values if the cache is stale.

        The cache is refreshed at most once per configured interval.
        """

        self._ensure_connection()

        now = time.time()
        if self._connection is None:
            # No active connection; clear values but avoid spamming logs.
            self._last_values = {}
            self._last_read_ts = now
            return

        if self._last_values and (now - self._last_read_ts) < self._interval:
            return

        try:
            data = obd_reader.read_pid_data(self._pid_ids, connection=self._connection)
            if isinstance(data, dict):
                self._last_values = data
            else:
                self._last_values = {}
        except Exception:
            self._last_values = {}
        finally:
            self._last_read_ts = now

    def get_value(self, pid_id: str) -> Any:
        """Return the most recent value for a PID or None.

        If no data is available (unknown PID, connection failure, etc.),
        returns None without raising.
        """

        self._refresh_if_needed()
        entry = self._last_values.get(pid_id)
        if not isinstance(entry, dict):
            return None
        return entry.get("value")


def build_channels_for_pids(
    pid_ids: List[str],
    interval: float,
    connection: Optional[Any] = None,
) -> List[Channel]:
    """Create DataLogger channels for the given PID IDs.

    Args:
        pid_ids: List of N54 PID identifiers (e.g. ["0C", "0D", "BOOST_ACTUAL"]).
        interval: Sampling interval in seconds; used as a hint for sampler
            cache freshness.
        connection: Optional existing OBD connection object. If None, the
            sampler will attempt to reuse any active session managed by
            obd_session_manager.

    Returns:
        List of Channel objects suitable for passing to DataLogger.
        Unknown PIDs are skipped.
    """

    # Filter to known PIDs and preserve order.
    known_ids: List[str] = []
    for pid in pid_ids:
        if n54_pids.get_pid_by_id(pid) is not None:
            known_ids.append(pid)

    if not known_ids:
        return []

    sampler = _PIDSampler(known_ids, interval=interval, connection=connection)
    channels: List[Channel] = []

    for pid in known_ids:
        pid_def = n54_pids.get_pid_by_id(pid)
        if pid_def is None:
            continue

        name = pid_def.name or pid

        def _make_read_func(pid_key: str) -> Any:
            def _read() -> Any:
                return sampler.get_value(pid_key)

            return _read

        channels.append(Channel(name=name, read_func=_make_read_func(pid)))

    return channels


__all__ = ["build_channels_for_pids"]
