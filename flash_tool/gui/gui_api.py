"""Programmatic GUI API wrappers for flash_tool core functions.

This module provides a thin, testable layer between the GUI and the
core flashing/connection modules. The implementation prefers concrete
adapters (`DirectCANFlasher`, `PCANAdapter`) via the `ConnectionManager`
when available, and falls back to safe stubs for unit tests and CI.
"""
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, List


class GUIAPIError(Exception):
    pass


class ConnectionError(GUIAPIError):
    pass


class AuthError(GUIAPIError):
    pass


class FlashError(GUIAPIError):
    pass


ProgressCallback = Optional[Callable[[float, str], None]]


@dataclass
class ConnectionInfo:
    interface: str
    channel: Optional[str]
    params: Dict[str, Any] = None


class CancelToken:
    def __init__(self):
        self._cancel = False

    def request_cancel(self):
        self._cancel = True

    def is_cancelled(self) -> bool:
        return self._cancel


class ConnectionHandle:
    """Opaque connection handle returned to the GUI.

    Attributes:
        interface: adapter type (e.g., 'pcan', 'virtual')
        channel: adapter channel or port
        params: user-supplied params
        flasher: DirectCANFlasher instance when available
        adapter: low-level adapter instance (PCANAdapter) when used
    """

    def __init__(self, interface: str, channel: Optional[str], params: Dict[str, Any] = None,
                 flasher: Optional[object] = None, adapter: Optional[object] = None):
        self.interface = interface
        self.channel = channel
        self.params = params or {}
        self.flasher = flasher
        self.adapter = adapter
        self.connected = True

    def disconnect(self):
        try:
            if getattr(self, 'flasher', None) is not None:
                try:
                    self.flasher.disconnect()
                except Exception:
                    pass
            if getattr(self, 'adapter', None) is not None:
                try:
                    self.adapter.disconnect()
                except Exception:
                    pass
        finally:
            self.connected = False


def list_adapters() -> List[Dict[str, Any]]:
    """Enumerate system adapters (conservative; falls back to static list).

    Returns a list of dicts with keys like `name`, `type`, and `description`.
    """
    try:
        from flash_tool import com_scanner

        ports = com_scanner.scan_com_ports()
        kdcan = {p[0].device for p in com_scanner.detect_kdcan_cable(ports)}
        adapters: List[Dict[str, Any]] = []
        for p in ports:
            name = getattr(p, 'device', str(p))
            desc = getattr(p, 'description', '') or ''
            typ = 'pcan' if name in kdcan else 'serial'
            adapters.append({"name": name, "type": typ, "description": desc})

        if not adapters:
            return [{"name": "pcan", "channels": ["PCAN_USBBUS1", "PCAN_USBBUS2"]}, {"name": "virtual", "channels": ["VIRTUAL0"]}]
        return adapters
    except Exception:
        return [{"name": "pcan", "channels": ["PCAN_USBBUS1", "PCAN_USBBUS2"]}, {"name": "virtual", "channels": ["VIRTUAL0"]}]


def connect(conn: ConnectionInfo, progress_cb: ProgressCallback = None, cancel_token: CancelToken = None) -> ConnectionHandle:
    """Connect to a hardware adapter or return a virtual handle.

    Behavior:
    - Prefer `DirectCANFlasher` when available and python-can is installed.
    - Fall back to `PCANAdapter` (safe stub) when flasher is unavailable.
    - Do not raise on missing hardware in typical test runs; instead
      return a lightweight virtual handle only when appropriate.
    """
    if progress_cb:
        progress_cb(0.0, "Starting connection")

    if cancel_token and cancel_token.is_cancelled():
        raise ConnectionError("Connection cancelled")

    iface = (conn.interface or '').lower()

    # PCAN / Direct CAN path
    if iface == 'pcan':
        # Figure out the port/channel: prefer explicit channel, then params, then saved preference
        port = conn.channel or (conn.params or {}).get('port')
        try:
            from flash_tool import connection_manager
            cm = connection_manager.get_manager()
            if not port:
                port = cm.get_saved_port()
        except Exception:
            cm = None

        if not port:
            port = (conn.params or {}).get('can_channel') or 'PCAN_USBBUS1'

        # Respect an explicit 'test' flag; default to False to avoid blocking tests
        test = bool((conn.params or {}).get('test', False))
        if cm is not None:
            try:
                cm.set_active_port(port, test=test)
            except Exception:
                # Non-fatal - continue with best-effort
                pass

        # Try to use the DirectCANFlasher when available
        try:
            from flash_tool.direct_can_flasher import DirectCANFlasher

            can_iface = (conn.params or {}).get('can_interface', 'pcan')
            can_channel = (conn.params or {}).get('can_channel', port)
            flasher = DirectCANFlasher(interface=can_iface, channel=can_channel)
            try:
                connected = flasher.connect()
            except Exception:
                connected = False

            if connected:
                if progress_cb:
                    progress_cb(1.0, 'Connected (DirectCANFlasher)')
                return ConnectionHandle(interface='pcan', channel=can_channel, params=conn.params, flasher=flasher)
        except Exception:
            pass

        # Fallback: try the PCANAdapter (safe stub)
        try:
            from flash_tool.adapters.pcan_adapter import PCANAdapter

            adapter = PCANAdapter(channel=port, bitrate=(conn.params or {}).get('bitrate', 500000))
            adapter.connect()
            if progress_cb:
                progress_cb(1.0, 'Connected (PCANAdapter)')
            return ConnectionHandle(interface='pcan', channel=port, params=conn.params, adapter=adapter)
        except Exception as e:
            raise ConnectionError(f'Failed to connect to PCAN interface: {e}')

    # Virtual adapter (test-friendly)
    if iface == 'virtual':
        if progress_cb:
            progress_cb(1.0, 'Connected (virtual)')
        return ConnectionHandle(interface='virtual', channel=conn.channel or 'VIRTUAL0', params=conn.params)

    raise ConnectionError(f'Unsupported interface: {conn.interface}')


def disconnect(handle: ConnectionHandle) -> bool:
    """Disconnect and clear ConnectionManager active port when possible."""
    try:
        if handle is not None:
            handle.disconnect()
    finally:
        try:
            from flash_tool import connection_manager
            connection_manager.get_manager().clear_active_port()
        except Exception:
            pass
    return True


def read_region(handle: ConnectionHandle, offset: int, size: int, progress_cb: ProgressCallback = None, cancel_token: CancelToken = None) -> bytes:
    """Read a memory region using an attached flasher.

    This function no longer falls back to any stub implementation. A
    missing or non-flasher handle is treated as a hard error so GUI
    flows can never silently read "fake" data.
    """
    if handle is None or not getattr(handle, 'connected', False):
        raise ConnectionError('Handle not connected')
    if cancel_token and cancel_token.is_cancelled():
        raise ConnectionError('Read cancelled')

    # Require a DirectCANFlasher instance
    if getattr(handle, 'flasher', None) is None:
        raise ConnectionError('No flasher attached to handle; read_region requires a real ECU connection')

    data = handle.flasher.read_memory(offset, size)
    if data is None:
        raise ConnectionError('Read failed')
    return data


def write_region(handle: ConnectionHandle, offset: int, data: bytes, verify: bool = True, progress_cb: ProgressCallback = None, cancel_token: CancelToken = None) -> Dict[str, Any]:
    """Write region through a flasher when available, otherwise delegate to `map_flasher`.

    This function is conservative: destructive write operations prefer the
    DirectCANFlasher API which performs safety checks. When a flasher is not
    present we fall back to the safe `map_flasher.flash_map` pipeline.
    """
    if cancel_token and cancel_token.is_cancelled():
        raise FlashError('Write cancelled')

    # If the provided handle is a flasher-like object (implements flash_calibration)
    # prefer calling it directly. This keeps tests simple (FakeFlasher objects).
    if handle is not None and hasattr(handle, 'flash_calibration') and callable(getattr(handle, 'flash_calibration')):
        try:
            result = handle.flash_calibration(data, progress_callback=(lambda m, p: progress_cb(p, m) if progress_cb else None) if progress_cb else None)
            if isinstance(result, bool):
                ok = result
            else:
                try:
                    from flash_tool.direct_can_flasher import WriteResult
                    ok = (result == WriteResult.SUCCESS)
                except Exception:
                    ok = bool(result)
            return {'success': bool(ok)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # If we have a ConnectionHandle with a DirectCANFlasher instance, prefer it
    if getattr(handle, 'flasher', None) is not None:
        try:
            result = handle.flasher.flash_calibration(data, progress_callback=(lambda m, p: progress_cb(p, m) if progress_cb else None) if progress_cb else None)
            if isinstance(result, bool):
                ok = result
            else:
                try:
                    from flash_tool.direct_can_flasher import WriteResult
                    ok = (result == WriteResult.SUCCESS)
                except Exception:
                    ok = bool(result)
            return {'success': bool(ok)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Fallback: write bytes to a temp file and call map_flasher.flash_map
    try:
        import tempfile
        from pathlib import Path
        from flash_tool import map_flasher

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(data)
        tmp.flush()
        tmp.close()
        tmp_path = Path(tmp.name)

        vin = None
        try:
            if handle is not None and hasattr(handle, 'flasher') and handle.flasher is not None and hasattr(handle.flasher, 'read_vin'):
                vin = handle.flasher.read_vin()
        except Exception:
            vin = None

        res = map_flasher.flash_map(tmp_path, vin=vin if vin else '', safety_confirmed=False, progress_callback=progress_cb)
        try:
            tmp_path.unlink()
        except Exception:
            pass
        return res
    except Exception as e:
        return {'success': False, 'error': str(e)}


def unlock_ecu(handle: ConnectionHandle, methods: Optional[List[str]] = None, progress_cb: ProgressCallback = None) -> Dict[str, Any]:
    """Perform ECU security access via the active flasher.

    This call requires a real DirectCANFlasher on the handle. There is
    intentionally no stub fallback so that authentication can never be
    reported as successful without talking to an actual ECU.
    """
    if handle is None:
        return {'success': False, 'error': 'no handle provided'}

    if getattr(handle, 'flasher', None) is None:
        return {'success': False, 'error': 'no flasher attached to handle; unlock_ecu requires a real ECU connection'}

    try:
        ok = handle.flasher.unlock_ecu(try_all_algorithms=True, try_all_levels=True)
        return {'success': bool(ok)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def validate_map(data: bytes, offset: int, size: int) -> Dict[str, Any]:
    try:
        from flash_tool.validated_maps import is_offset_safe
        safe, reason = is_offset_safe(offset, size)
        return {'valid': bool(safe), 'warnings': [] if safe else [reason]}
    except Exception:
        return {'valid': False, 'warnings': ['validation unavailable']}


def live_control(handle: ConnectionHandle, did: int, param: int, state: Optional[List[int]] = None) -> Dict[str, Any]:
    """Send InputOutputControlByLocalIdentifier (0x30) request."""
    if handle is None or not getattr(handle, 'connected', False):
        return {'success': False, 'error': 'Not connected'}
        
    if getattr(handle, 'flasher', None) is not None:
        try:
            return handle.flasher.input_output_control_by_id(did, param, state)
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    return {'success': False, 'error': 'Flasher not available'}


def live_write(handle: ConnectionHandle, address: int, data: bytes) -> Dict[str, Any]:
    """Write memory by address (0x3D) for live tuning."""
    if handle is None or not getattr(handle, 'connected', False):
        return {'success': False, 'error': 'Not connected'}
        
    if getattr(handle, 'flasher', None) is not None:
        try:
            ok = handle.flasher.write_memory_by_address(address, data)
            return {'success': ok}
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    return {'success': False, 'error': 'Flasher not available'}


def start_live_session(handle: ConnectionHandle) -> Dict[str, Any]:
    """
    Enter BMW Extended Session, Unlock ECU, and start TesterPresent.
    Required for Live Control (0x30) and Live Tuning (0x3D).
    """
    if handle is None or not getattr(handle, 'connected', False):
        return {'success': False, 'error': 'Not connected'}

    if getattr(handle, 'flasher', None) is not None:
        try:
            # 1. Enter BMW Extended Session (0x87)
            if not handle.flasher.enter_bmw_extended_session():
                return {'success': False, 'error': 'Failed to enter Extended Session (0x87)'}
            
            # 2. Unlock ECU (Security Access)
            # Try all algorithms/levels as 0x30/0x3D might require specific levels
            try:
                handle.flasher.unlock_ecu(try_all_algorithms=True, try_all_levels=True)
            except Exception as e:
                return {'success': False, 'error': f'Security Access failed: {e}'}

            # 3. Start TesterPresent (Keep-Alive)
            handle.flasher.start_tester_present()
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'Flasher not available'}


def stop_live_session(handle: ConnectionHandle) -> Dict[str, Any]:
    """
    Stop TesterPresent and return to Default Session.
    """
    if handle is None:
        return {'success': False, 'error': 'No handle'}

    if getattr(handle, 'flasher', None) is not None:
        try:
            # 1. Stop TesterPresent
            handle.flasher.stop_tester_present()
            
            # 2. Return to Default Session (0x01) via DiagnosticSessionControl
            from flash_tool.direct_can_flasher import UDSService, DiagnosticSession
            handle.flasher.send_uds_request(UDSService.DIAGNOSTIC_SESSION_CONTROL, bytes([DiagnosticSession.DEFAULT]))
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'Flasher not available'}
