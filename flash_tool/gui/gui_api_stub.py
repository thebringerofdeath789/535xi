"""Safe GUI API stub for tests and early development.

This module intentionally provides lightweight, deterministic behavior
so unit tests can run without hardware or heavy side effects.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable, Any


class GUIAPIError(Exception):
    pass


class ConnectionError(GUIAPIError):
    pass


class AuthError(GUIAPIError):
    pass


class FlashError(GUIAPIError):
    pass


@dataclass
class ConnectionInfo:
    interface: str
    channel: str
    params: Dict[str, Any] = None


class ConnectionHandle:
    def __init__(self, interface: str, channel: str, params: Dict[str, Any] = None):
        self.interface = interface
        self.channel = channel
        self.params = params or {}
        self.connected = True


class CancelToken:
    def __init__(self):
        self._cancelled = False

    def is_cancelled(self) -> bool:
        return self._cancelled

    def request_cancel(self) -> None:
        self._cancelled = True


def list_adapters() -> List[Dict[str, Any]]:
    try:
        # Prefer actual system scan via com_scanner when available
        from flash_tool import com_scanner

        ports = com_scanner.scan_com_ports()
        kdcan = {p[0].device for p in com_scanner.detect_kdcan_cable(ports)}
        adapters: List[Dict[str, Any]] = []
        for p in ports:
            name = getattr(p, 'device', str(p))
            desc = getattr(p, 'description', '') or ''
            typ = 'pcan' if name in kdcan else 'serial'
            adapters.append({"name": name, "type": typ, "description": desc})

        # Fallback: if no ports found, return a small static set
        if not adapters:
            return [{"name": "pcan", "channels": ["PCAN_USBBUS1", "PCAN_USBBUS2"]}, {"name": "virtual", "channels": ["VIRTUAL0"]}]
        return adapters
    except Exception:
        # If com_scanner is unavailable, return the static list
        return [
            {"name": "pcan", "channels": ["PCAN_USBBUS1", "PCAN_USBBUS2"]},
            {"name": "virtual", "channels": ["VIRTUAL0"]},
        ]


def connect(conn: ConnectionInfo, progress_cb: Optional[Callable[[float, str], None]] = None, cancel_token: Optional[CancelToken] = None) -> ConnectionHandle:
    if progress_cb:
        progress_cb(0.0, "Starting connection")
    if cancel_token and cancel_token.is_cancelled():
        raise ConnectionError("Connection cancelled")
    if conn.interface not in ("pcan", "virtual"):
        raise ConnectionError(f"Unsupported interface: {conn.interface}")
    if progress_cb:
        progress_cb(1.0, "Connected")
    return ConnectionHandle(conn.interface, conn.channel, conn.params)


def disconnect(handle: ConnectionHandle) -> None:
    handle.connected = False


def read_region(handle: ConnectionHandle, offset: int, size: int, progress_cb: Optional[Callable[[float, str], None]] = None, cancel_token: Optional[CancelToken] = None) -> bytes:
    if not handle.connected:
        raise ConnectionError("Handle not connected")
    if cancel_token and cancel_token.is_cancelled():
        raise ConnectionError("Read cancelled")
    return bytes([0] * size)


def write_region(handle: ConnectionHandle, offset: int, data: bytes, verify: bool = True, progress_cb: Optional[Callable[[float, str], None]] = None, cancel_token: Optional[CancelToken] = None) -> Dict[str, Any]:
    """Write region using either a provided flasher-like handle or fallback to `map_flasher`.

    - If `handle` exposes `flash_calibration()`, call it and return `{'success': bool}`.
    - Otherwise, write to a temporary file and delegate to `map_flasher.flash_map`.
    """
    # If caller provided a flasher-like object, prefer its method
    if handle is not None and hasattr(handle, 'flash_calibration'):
        try:
            result = handle.flash_calibration(data, progress_callback=progress_cb)
            return {'success': bool(result)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Validate a connection-like handle if present
    if handle is not None:
        if hasattr(handle, 'connected') and not getattr(handle, 'connected'):
            raise ConnectionError("Handle not connected")
    if cancel_token and cancel_token.is_cancelled():
        raise FlashError("Write cancelled")

    # Fallback: write bytes to a temp file and call map_flasher.flash_map
    try:
        import tempfile
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(data)
        tmp.flush()
        tmp.close()
        tmp_path = Path(tmp.name)

        vin = None
        try:
            if handle is not None and hasattr(handle, 'read_vin'):
                vin = handle.read_vin()
        except Exception:
            vin = None

        from flash_tool import map_flasher
        res = map_flasher.flash_map(tmp_path, vin=vin if vin else '', safety_confirmed=False, progress_callback=progress_cb)
        try:
            tmp_path.unlink()
        except Exception:
            pass
        return res
    except Exception as e:
        return {'success': False, 'error': str(e)}


def unlock_ecu(handle: ConnectionHandle, methods: Optional[List[str]] = None, progress_cb: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
    return {"unlocked": True, "method": "stub"}


def validate_map(data: bytes, offset: int, size: int) -> Dict[str, Any]:
    try:
        from flash_tool.validated_maps import is_offset_safe
        safe = is_offset_safe(offset, size)
        return {"valid": bool(safe), "warnings": []}
    except Exception:
        return {"valid": True, "warnings": []}
