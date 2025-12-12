"""Full UDS-over-ISO-TP integration using `isotp` and `udsoncan`.

This module provides a complete, production-grade multi-frame UDS client
by integrating `python-isotp` (ISO 15765-2 transport) and `udsoncan`
(ISO 14229 application layer) libraries.

When these dependencies are available, `IsoTpUdsClient` provides:
- Full ISO-TP segmentation (multi-kilobyte transfers)
- UDS service abstraction with proper response parsing
- NRC handling and timeout management
- Configurable CAN IDs for different ECUs

When dependencies are not available, gracefully falls back to the
built-in `UDSClient` from `flash_tool.uds_client` which has native
multi-frame ISO-TP support.

Installation:
    pip install udsoncan isotp python-can

Usage:
    from flash_tool.uds_isotp_client import IsoTpUdsClient, dependencies_available

    if dependencies_available():
        client = IsoTpUdsClient(tx_id=0x6F1, rx_id=0x6F9)
        client.open()
        response = client.send_service(0x22, b'\\xF1\\x90')  # ReadDataById VIN
        client.close()
    else:
        # Fallback to native UDSClient
        from flash_tool.uds_client import UDSClient
        client = UDSClient()
        response = client.send_request(0x22, b'\\xF1\\x90')
"""
from typing import Optional, Union, Dict, Any
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Try to detect optional dependencies
HAS_ISOTP = False
HAS_UDSONCAN = False
HAS_PYTHON_CAN = False

try:
    import can as _can  # type: ignore
    HAS_PYTHON_CAN = True
except ImportError:
    _can = None  # type: ignore

try:
    import isotp as _isotp  # type: ignore
    HAS_ISOTP = True
except ImportError:
    _isotp = None  # type: ignore

try:
    import udsoncan as _udsoncan  # type: ignore
    from udsoncan.client import Client as _UdsClient  # type: ignore
    from udsoncan.connections import BaseConnection  # type: ignore
    from udsoncan import Response, Request, services  # type: ignore
    HAS_UDSONCAN = True
except ImportError:
    _udsoncan = None  # type: ignore
    _UdsClient = None  # type: ignore
    BaseConnection = object


def dependencies_available() -> bool:
    """Return True if both `isotp` and `udsoncan` are importable.

    This lets tests and runtime code decide whether to instantiate the
    full udsoncan-based client or fall back to the native UDSClient.
    """
    return HAS_ISOTP and HAS_UDSONCAN and HAS_PYTHON_CAN


class IsoTpConnection(BaseConnection if HAS_UDSONCAN else object):
    """ISO-TP connection using python-isotp for udsoncan integration.

    This class bridges `python-isotp` with `udsoncan` by implementing
    the `BaseConnection` interface that udsoncan expects.
    """

    def __init__(self, bus: Any, tx_id: int, rx_id: int,
                 tx_padding: int = 0x00, rx_padding: Optional[int] = None):
        """Initialize ISO-TP connection.

        Args:
            bus: python-can Bus instance
            tx_id: CAN ID for transmitting to ECU
            rx_id: CAN ID for receiving from ECU
            tx_padding: Padding byte for TX frames (default 0x00)
            rx_padding: Padding byte for RX frames (None = accept any)
        """
        if not (HAS_ISOTP and HAS_PYTHON_CAN):
            raise ImportError("python-isotp and python-can are required")

        # Call parent init if we have udsoncan
        if HAS_UDSONCAN and hasattr(super(), '__init__'):
            super().__init__(name=f"IsoTp_{tx_id:03X}_{rx_id:03X}")

        self.bus = bus
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.tx_padding = tx_padding
        self.rx_padding = rx_padding

        # ISO-TP layer configuration
        self._isotp_layer: Optional[Any] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._opened = False

    def open(self) -> 'IsoTpConnection':
        """Open the ISO-TP connection."""
        if self._opened:
            return self

        # Configure ISO-TP address
        isotp_address = _isotp.Address(
            addressing_mode=_isotp.AddressingMode.Normal_11bits,
            txid=self.tx_id,
            rxid=self.rx_id
        )

        # ISO-TP parameters
        isotp_params = _isotp.Params()
        isotp_params.tx_padding = self.tx_padding
        isotp_params.rx_consecutive_frame_timeout = 1.0
        isotp_params.tx_data_length = 8
        isotp_params.stmin = 0  # No minimum separation time from our side

        # Create the ISO-TP layer
        self._isotp_layer = _isotp.CanStack(
            bus=self.bus,
            address=isotp_address,
            params=isotp_params
        )

        # Start the receive thread for ISO-TP state machine
        self._stop_event.clear()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

        self._opened = True
        logger.info(f"IsoTpConnection opened: tx=0x{self.tx_id:03X} rx=0x{self.rx_id:03X}")
        return self

    def close(self) -> None:
        """Close the ISO-TP connection."""
        if not self._opened:
            return

        self._stop_event.set()
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=2.0)

        self._isotp_layer = None
        self._opened = False
        logger.info("IsoTpConnection closed")

    def _rx_loop(self) -> None:
        """Background thread to process ISO-TP state machine."""
        while not self._stop_event.is_set():
            if self._isotp_layer:
                try:
                    self._isotp_layer.process()
                except Exception as e:
                    logger.warning(f"ISO-TP process error: {e}")
            time.sleep(0.001)  # 1ms loop

    def send(self, data: bytes, timeout: Optional[float] = None) -> None:
        """Send data via ISO-TP.

        Args:
            data: UDS message bytes to send
            timeout: Optional timeout (not used, for interface compatibility)
        """
        if not self._opened or not self._isotp_layer:
            raise RuntimeError("Connection not opened")

        self._isotp_layer.send(data)

        # Wait for transmission to complete
        start = time.time()
        tx_timeout = timeout or 5.0
        while self._isotp_layer.transmitting():
            if time.time() - start > tx_timeout:
                raise TimeoutError("ISO-TP transmission timeout")
            time.sleep(0.001)

    def wait_frame(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Wait for and receive an ISO-TP frame.

        Args:
            timeout: Receive timeout in seconds

        Returns:
            Received data bytes or None on timeout
        """
        if not self._opened or not self._isotp_layer:
            raise RuntimeError("Connection not opened")

        rx_timeout = timeout or 2.0
        start = time.time()

        while time.time() - start < rx_timeout:
            if self._isotp_layer.available():
                return self._isotp_layer.recv()
            time.sleep(0.001)

        return None

    def empty_rxqueue(self) -> None:
        """Clear the receive queue."""
        if self._isotp_layer:
            while self._isotp_layer.available():
                self._isotp_layer.recv()

    def is_open(self) -> bool:
        """Check if connection is open."""
        return self._opened

    def __enter__(self) -> 'IsoTpConnection':
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class IsoTpUdsClient:
    """Full-featured UDS client with ISO-TP transport.

    When `udsoncan` and `isotp` are installed, this provides a complete
    UDS client with proper NRC handling, service abstraction, and multi-
    kilobyte transfer support.

    When dependencies are not available, this class will raise an
    ImportError with instructions to install the required packages.
    Alternatively, use `dependencies_available()` to check first and
    fall back to `UDSClient` from `flash_tool.uds_client`.

    Usage:
        client = IsoTpUdsClient(tx_id=0x6F1, rx_id=0x6F9)
        client.open()
        try:
            # Read VIN
            response = client.send_service(0x22, b'\\xF1\\x90')
            if response.positive:
                print(f"VIN: {response.data.decode('ascii')}")
        finally:
            client.close()
    """

    def __init__(self, *, bus: Optional[object] = None, tx_id: int = 0x6F1,
                 rx_id: int = 0x6F9, bitrate: int = 500000,
                 interface: str = 'pcan', channel: str = 'PCAN_USBBUS1'):
        """Initialize UDS client.

        Args:
            bus: Optional python-can Bus. If None, creates one.
            tx_id: CAN ID for transmitting to ECU (Tester → ECU)
            rx_id: CAN ID for receiving from ECU (ECU → Tester)
            bitrate: CAN bus bitrate
            interface: CAN interface type (pcan, socketcan, etc.)
            channel: CAN channel identifier
        """
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.bitrate = bitrate
        self.interface = interface
        self.channel = channel
        self._external_bus = bus is not None
        self._bus = bus
        self._connection: Optional[IsoTpConnection] = None
        self._uds_client: Optional[Any] = None
        self._opened = False

        # Check dependencies
        if not dependencies_available():
            missing = []
            if not HAS_PYTHON_CAN:
                missing.append("python-can")
            if not HAS_ISOTP:
                missing.append("isotp")
            if not HAS_UDSONCAN:
                missing.append("udsoncan")

            raise ImportError(
                f"IsoTpUdsClient requires: {', '.join(missing)}. Install with:\n"
                f"    pip install {' '.join(missing)}"
            )

    def open(self) -> 'IsoTpUdsClient':
        """Open the UDS connection."""
        if self._opened:
            return self

        # Create CAN bus if not provided
        if not self._bus:
            self._bus = _can.Bus(
                interface=self.interface,
                channel=self.channel,
                bitrate=self.bitrate
            )

        # Create ISO-TP connection
        self._connection = IsoTpConnection(
            bus=self._bus,
            tx_id=self.tx_id,
            rx_id=self.rx_id
        )
        self._connection.open()

        # Create udsoncan client with default config
        config = _udsoncan.configs.default_client_config.copy()
        config['exception_on_negative_response'] = False
        config['exception_on_invalid_response'] = False
        config['exception_on_unexpected_response'] = False
        config['p2_timeout'] = 2.0
        config['p2_star_timeout'] = 5.0

        self._uds_client = _UdsClient(self._connection, config=config)
        self._uds_client.open()

        self._opened = True
        logger.info(f"IsoTpUdsClient opened: tx=0x{self.tx_id:03X} rx=0x{self.rx_id:03X}")
        return self

    def close(self) -> None:
        """Close the UDS connection."""
        if not self._opened:
            return

        if self._uds_client:
            try:
                self._uds_client.close()
            except Exception:
                pass
            self._uds_client = None

        if self._connection:
            self._connection.close()
            self._connection = None

        if self._bus and not self._external_bus:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None

        self._opened = False
        logger.info("IsoTpUdsClient closed")

    def send_service(self, service_id: int, data: bytes = b'',
                     timeout: Optional[float] = None) -> 'UdsResponse':
        """Send a raw UDS service request.

        This is the low-level method that sends arbitrary UDS service requests.
        For common services, use the convenience methods like `read_did()`,
        `security_access()`, etc.

        Args:
            service_id: UDS service ID (e.g., 0x22 for ReadDataByIdentifier)
            data: Service-specific data bytes
            timeout: Optional timeout override

        Returns:
            UdsResponse with parsed result
        """
        if not self._opened:
            raise RuntimeError("Client not opened")

        # Build and send raw request
        request_data = bytes([service_id]) + data
        self._connection.send(request_data)

        # Receive response
        rx_timeout = timeout or 2.0
        response_data = self._connection.wait_frame(timeout=rx_timeout)

        if response_data is None:
            return UdsResponse(
                positive=False,
                service_id=service_id,
                data=b'',
                nrc=None,
                raw=None,
                error="Timeout waiting for response"
            )

        # Parse response
        if len(response_data) < 1:
            return UdsResponse(
                positive=False,
                service_id=service_id,
                data=b'',
                nrc=None,
                raw=response_data,
                error="Empty response"
            )

        response_sid = response_data[0]

        # Positive response (SID + 0x40)
        if response_sid == service_id + 0x40:
            return UdsResponse(
                positive=True,
                service_id=service_id,
                data=response_data[1:],
                nrc=None,
                raw=response_data
            )

        # Negative response (0x7F)
        if response_sid == 0x7F and len(response_data) >= 3:
            failed_service = response_data[1]
            nrc = response_data[2]
            return UdsResponse(
                positive=False,
                service_id=failed_service,
                data=b'',
                nrc=nrc,
                raw=response_data,
                error=f"NRC 0x{nrc:02X}"
            )

        return UdsResponse(
            positive=False,
            service_id=service_id,
            data=response_data[1:] if len(response_data) > 1 else b'',
            nrc=None,
            raw=response_data,
            error=f"Unexpected response SID 0x{response_sid:02X}"
        )

    # ========================================================================
    # Convenience methods for common UDS services
    # ========================================================================

    def read_did(self, did: int) -> 'UdsResponse':
        """Read Data By Identifier (UDS 0x22).

        Args:
            did: 16-bit Data Identifier (e.g., 0xF190 for VIN)

        Returns:
            UdsResponse with DID data
        """
        did_bytes = did.to_bytes(2, 'big')
        return self.send_service(0x22, did_bytes)

    def write_did(self, did: int, data: bytes) -> 'UdsResponse':
        """Write Data By Identifier (UDS 0x2E).

        Args:
            did: 16-bit Data Identifier
            data: Data to write

        Returns:
            UdsResponse
        """
        did_bytes = did.to_bytes(2, 'big')
        return self.send_service(0x2E, did_bytes + data)

    def diagnostic_session_control(self, session: int) -> 'UdsResponse':
        """Diagnostic Session Control (UDS 0x10).

        Args:
            session: Session type (0x01=default, 0x02=programming, 0x03=extended)

        Returns:
            UdsResponse
        """
        return self.send_service(0x10, bytes([session]))

    def security_access_seed(self, level: int) -> 'UdsResponse':
        """Security Access - Request Seed (UDS 0x27 odd level).

        Args:
            level: Security level (1, 3, 5, etc.)

        Returns:
            UdsResponse with seed in data
        """
        return self.send_service(0x27, bytes([level]))

    def security_access_key(self, level: int, key: bytes) -> 'UdsResponse':
        """Security Access - Send Key (UDS 0x27 even level).

        Args:
            level: Security level + 1 (2, 4, 6, etc.)
            key: Calculated security key

        Returns:
            UdsResponse
        """
        return self.send_service(0x27, bytes([level]) + key)

    def tester_present(self, suppress_response: bool = True) -> 'UdsResponse':
        """Tester Present (UDS 0x3E).

        Args:
            suppress_response: If True, ECU won't send a response

        Returns:
            UdsResponse
        """
        sub = 0x80 if suppress_response else 0x00
        return self.send_service(0x3E, bytes([sub]))

    def ecu_reset(self, reset_type: int) -> 'UdsResponse':
        """ECU Reset (UDS 0x11).

        Args:
            reset_type: 0x01=hard, 0x02=keyOffOn, 0x03=soft

        Returns:
            UdsResponse
        """
        return self.send_service(0x11, bytes([reset_type]))

    def read_memory(self, address: int, size: int,
                    address_size: int = 4, length_size: int = 2) -> 'UdsResponse':
        """Read Memory By Address (UDS 0x23).

        Args:
            address: Memory address
            size: Number of bytes to read
            address_size: Address field size in bytes (1-4)
            length_size: Length field size in bytes (1-4)

        Returns:
            UdsResponse with memory data
        """
        # Address and length format byte
        format_byte = ((length_size & 0x0F) << 4) | (address_size & 0x0F)

        # Pack address and length
        addr_bytes = address.to_bytes(address_size, 'big')
        len_bytes = size.to_bytes(length_size, 'big')

        return self.send_service(0x23, bytes([format_byte]) + addr_bytes + len_bytes)

    def request_download(self, address: int, size: int,
                         data_format: int = 0x00) -> 'UdsResponse':
        """Request Download (UDS 0x34) - prepare ECU for receiving data.

        Args:
            address: Memory address
            size: Data size to download
            data_format: Compression/encryption (0x00 = none)

        Returns:
            UdsResponse with max block size info
        """
        # Fixed 4-byte address, 4-byte length
        format_byte = 0x44
        addr_bytes = address.to_bytes(4, 'big')
        size_bytes = size.to_bytes(4, 'big')

        return self.send_service(
            0x34,
            bytes([data_format, format_byte]) + addr_bytes + size_bytes
        )

    def transfer_data(self, block_sequence: int, data: bytes) -> 'UdsResponse':
        """Transfer Data (UDS 0x36).

        Args:
            block_sequence: Block sequence counter (1-255, wraps to 0)
            data: Data block

        Returns:
            UdsResponse
        """
        return self.send_service(0x36, bytes([block_sequence]) + data)

    def request_transfer_exit(self) -> 'UdsResponse':
        """Request Transfer Exit (UDS 0x37).

        Returns:
            UdsResponse
        """
        return self.send_service(0x37, b'')

    def routine_control(self, control_type: int, routine_id: int,
                        data: bytes = b'') -> 'UdsResponse':
        """Routine Control (UDS 0x31).

        Args:
            control_type: 0x01=start, 0x02=stop, 0x03=request results
            routine_id: 16-bit routine identifier
            data: Optional routine data

        Returns:
            UdsResponse
        """
        routine_bytes = routine_id.to_bytes(2, 'big')
        return self.send_service(0x31, bytes([control_type]) + routine_bytes + data)

    def __enter__(self) -> 'IsoTpUdsClient':
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class UdsResponse:
    """Container for UDS response data.

    Attributes:
        positive: True if response was positive (SID + 0x40)
        service_id: The service ID that was requested
        data: Response data (excluding SID for positive, empty for negative)
        nrc: Negative Response Code (None for positive responses)
        raw: Raw response bytes
        error: Error message if applicable
    """

    def __init__(self, positive: bool, service_id: int, data: bytes,
                 nrc: Optional[int], raw: Optional[bytes] = None,
                 error: Optional[str] = None):
        self.positive = positive
        self.service_id = service_id
        self.data = data
        self.nrc = nrc
        self.raw = raw
        self.error = error

    def __bool__(self) -> bool:
        return self.positive

    def __repr__(self) -> str:
        if self.positive:
            return f"UdsResponse(positive=True, service=0x{self.service_id:02X}, data={self.data.hex()})"
        else:
            nrc_str = f"0x{self.nrc:02X}" if self.nrc is not None else "None"
            return f"UdsResponse(positive=False, service=0x{self.service_id:02X}, nrc={nrc_str}, error={self.error})"


def get_client(tx_id: int = 0x6F1, rx_id: int = 0x6F9,
               **kwargs) -> Union[IsoTpUdsClient, 'UDSClient']:
    """Factory function that returns the best available UDS client.

    When `udsoncan` and `isotp` are installed, returns an IsoTpUdsClient.
    Otherwise, returns the native UDSClient with built-in multi-frame support.

    Args:
        tx_id: CAN ID for transmitting to ECU
        rx_id: CAN ID for receiving from ECU
        **kwargs: Additional arguments passed to client constructor

    Returns:
        Either IsoTpUdsClient or UDSClient
    """
    if dependencies_available():
        logger.info("Using IsoTpUdsClient (udsoncan + isotp)")
        return IsoTpUdsClient(tx_id=tx_id, rx_id=rx_id, **kwargs)
    else:
        logger.info("Falling back to native UDSClient (udsoncan/isotp not installed)")
        from .uds_client import UDSClient
        return UDSClient(tx_id=tx_id, rx_id=rx_id, **kwargs)


__all__ = [
    "dependencies_available",
    "IsoTpUdsClient",
    "IsoTpConnection",
    "UdsResponse",
    "get_client",
]
