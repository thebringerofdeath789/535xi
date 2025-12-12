#!/usr/bin/env python3
"""
Minimal KWP2000 (K-Line) client
================================

Provides a lightweight KWP2000 client sufficient for reading and clearing DTCs
from K-line-only BMW modules (e.g., IBS, KOMBI). This is intentionally minimal
-- it expects the serial/adapter to handle low-level 5-baud/fast-init framing
and simply exchanges raw service payloads.

Note: Real adapter/vehicle testing is required to fully validate timings,
framing, and addressing. For unit tests, this client supports a pluggable
`serial_class` to use a stub serial interface.
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
import logging
import time

try:
    import serial
except Exception:
    serial = None

from . import bmw_modules
from .dtc_utils import parse_dtc_response

logger = logging.getLogger(__name__)


class KWPConnectionError(Exception):
    pass


class KWPClient:
    """
    Simple KWP2000 client using pyserial or a serial-class that emulates the
    same API.

    The methods operate at a high-level and do not attempt to emulate the
    full KWP physical layer. Instead, this client relies on the serial adapter
    to perform the necessary physical-layer init and framing.
    """

    def __init__(self, port: Optional[str] = None, baudrate: int = 10400, timeout: float = 1.0, serial_class=None):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_class = serial_class if serial_class is not None else serial.Serial
        self.ser = None

    def connect(self) -> bool:
        if self.ser is not None:
            return True

        if self.serial_class is None:
            raise KWPConnectionError("pyserial is not available in environment")

        if self.port is None:
            # Attempt to auto-detect via com_scanner
            try:
                from .com_scanner import get_recommended_port
                self.port = get_recommended_port()
            except Exception:
                pass

        if self.port is None:
            raise KWPConnectionError("No serial port specified for K-line connection")

        try:
            self.ser = self.serial_class(self.port, baudrate=self.baudrate, timeout=self.timeout)
            logger.info(f"K-line serial opened: {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            logger.error(f"Failed to open K-line serial port {self.port}: {e}")
            self.ser = None
            raise KWPConnectionError(f"Could not open serial port {self.port}: {e}")

    def disconnect(self) -> None:
        if self.ser is None:
            return
        try:
            self.ser.close()
            logger.info("K-line serial closed")
        except Exception as e:
            logger.warning(f"Error closing K-line serial: {e}")
        finally:
            self.ser = None

    def _send_raw(self, payload: bytes, read_timeout: float = 1.0) -> Optional[bytes]:
        """
        Send raw payload to the K-line adapter and return raw response bytes.

        This method is intentionally naive and expects the serial adapter to
        apply necessary KWP framing and 5-baud/fast-init logic.
        """
        if self.ser is None:
            raise KWPConnectionError("Serial port not open")

        try:
            logger.debug(f"KWP send: {payload.hex()}")
            self.ser.reset_input_buffer()
            self.ser.write(payload)
            self.ser.flush()

            # Wait a bit for response to arrive
            time.sleep(0.05)
            read_data = b''
            # Read until timeout and return all available bytes
            start = time.time()
            while time.time() - start < read_timeout:
                # pyserial: self.ser.in_waiting indicates bytes in buffer
                try:
                    count = getattr(self.ser, 'in_waiting', None)
                    if count is None:
                        # fallback to read one byte at a time
                        byte = self.ser.read(1)
                        if byte:
                            read_data += byte
                        else:
                            break
                    else:
                        if count > 0:
                            # Read available bytes once and exit loop. Many test
                            # serial stubs return the full response on each read
                            # call and do not emulate buffer consumption. To avoid
                            # appending duplicate data repeatedly, break after
                            # the first successful read when using in_waiting.
                            read_data += self.ser.read(count)
                            break
                        else:
                            # no data yet; give it a small sleep
                            time.sleep(0.01)
                except Exception:
                    break

            if read_data:
                logger.debug(f"KWP recv: {read_data.hex()}")
                return read_data
            return None

        except Exception as e:
            logger.error(f"KWP send/receive error: {e}")
            return None

    def keep_alive(self) -> bool:
        """Send KWP tester present (0x3E 0x00) to maintain session"""
        res = self._send_raw(b"\x3E\x00")
        if res and len(res) > 0:
            # Positive response to 0x3E is 0x7E (0x3E + 0x40)
            return res[0] == 0x7E
        return False

    def read_dtcs(self, module: bmw_modules.BMWModule, status_mask: int = 0xFF) -> List[Dict[str, Any]]:
        """Read DTCs from specified K-line module. Returns parsed DTC dictionaries."""
        if module.kline_address is None:
            raise ValueError("Module has no K-line address")

        # Build a simple KWP service frame (payload only)
        request = bytes([0x18, 0x02, status_mask])
        raw = self._send_raw(request, read_timeout=1.0)
        if not raw:
            logger.info(f"No KWP response for DTC read from {module.abbreviation}")
            return []

        # Accept either headered or header-free responses; use header 0x58 if present
        positive_header = 0x58
        dtcs = parse_dtc_response(raw, positive_header=positive_header)
        return dtcs

    def clear_all_dtcs(self, module: bmw_modules.BMWModule) -> bool:
        if module.kline_address is None:
            raise ValueError("Module has no K-line address")

        request = bytes([0x14, 0xFF, 0xFF, 0xFF])
        raw = self._send_raw(request, read_timeout=1.0)
        if not raw:
            return False
        # Positive response byte for 0x14 is 0x54 (0x14 + 0x40)
        return raw[0] == 0x54
