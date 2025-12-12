"""UDS client with full ISO-TP (ISO 15765-2) multi-frame support.

This module provides a `UDSClient` class that implements complete ISO-TP
segmented message transport over CAN bus. It supports:
- Single Frame (SF): payloads ≤ 7 bytes
- First Frame (FF) + Consecutive Frames (CF): payloads > 7 bytes
- Flow Control (FC): proper handshaking for multi-frame transfers

Works with real CAN hardware via `python-can`.
"""
import logging
import time
import struct
from typing import Optional, Tuple
from .can_adapter import create_bus, Message, CAN_AVAILABLE

logger = logging.getLogger(__name__)


# ISO-TP Frame Types (upper nibble of PCI byte)
ISOTP_SINGLE_FRAME = 0x00
ISOTP_FIRST_FRAME = 0x10
ISOTP_CONSECUTIVE_FRAME = 0x20
ISOTP_FLOW_CONTROL = 0x30

# Flow Control Status
FC_CONTINUE_TO_SEND = 0x00
FC_WAIT = 0x01
FC_OVERFLOW = 0x02


class UDSClient:
    """UDS client with full ISO-TP multi-frame support.

    Implements ISO 15765-2 transport protocol for UDS communication over CAN.
    Supports arbitrarily large UDS requests/responses via segmented transfers.

    Usage:
        client = UDSClient(bus=None)  # will create adapter bus (mock if python-can missing)
        resp = client.send_request(0x27, b"\\x01")  # single-frame
        resp = client.send_request(0x36, large_data)  # multi-frame automatic
    """

    ECU_TX_ID_DEFAULT = 0x6F1
    ECU_RX_ID_DEFAULT = 0x6F9

    # Timing parameters (ISO 15765-2 compliant)
    N_AS_TIMEOUT = 1.0  # Transmitter timeout for Flow Control
    N_AR_TIMEOUT = 1.0  # Receiver timeout for Consecutive Frames
    N_BS_TIMEOUT = 1.0  # Sender wait for Flow Control
    N_CR_TIMEOUT = 1.0  # Receiver wait for Consecutive Frames
    CF_DELAY = 0.001    # Delay between consecutive frames (1ms, can be adjusted by FC)

    def __init__(self, bus=None, tx_id: int = ECU_TX_ID_DEFAULT, rx_id: int = ECU_RX_ID_DEFAULT,
                 bitrate: int = 500000, interface: str = 'pcan', channel: str = 'PCAN_USBBUS1'):
        """Initialize UDS client.

        Args:
            bus: Optional CAN bus instance. If None, creates one via can_adapter.
            tx_id: CAN arbitration ID for transmitting to ECU (Tester → ECU)
            rx_id: CAN arbitration ID for receiving from ECU (ECU → Tester)
            bitrate: CAN bus bitrate (default 500000 for BMW PT-CAN)
            interface: CAN interface type when creating bus
            channel: CAN channel when creating bus
        """
        if bus is None:
            # create a bus via adapter factory (mock if python-can not installed)
            self.bus = create_bus(interface=interface, channel=channel, bitrate=bitrate)
        else:
            self.bus = bus

        self.tx_id = tx_id
        self.rx_id = rx_id
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate

        adapter = "python-can" if CAN_AVAILABLE else "mock"
        logger.info(f"UDSClient initialized (adapter={adapter}) tx=0x{tx_id:03X} rx=0x{rx_id:03X}")

    def send_request(self, service: int, data: bytes = b'', timeout: float = 0.5) -> Optional[bytes]:
        """Send a UDS request and receive the response.

        Automatically uses single-frame or multi-frame ISO-TP based on payload size.

        Args:
            service: UDS service ID (e.g., 0x27 for Security Access)
            data: Service-specific data bytes
            timeout: Response timeout in seconds

        Returns:
            Response data (excluding positive response SID) or None on timeout/error.
            For positive response, returns data after the response SID.
            For negative response, returns [service_id, NRC] bytes.
        """
        payload = bytes([service]) + data

        # Choose single-frame or multi-frame based on payload size
        if len(payload) <= 7:
            self._send_single_frame(payload)
        else:
            self._send_multi_frame(payload)

        # Receive response (may be single or multi-frame)
        return self._receive_response(timeout)

    def _send_single_frame(self, payload: bytes) -> None:
        """Send a single-frame ISO-TP message.

        Single Frame format: [PCI | Data]
        PCI = 0x0N where N = data length (1-7)
        """
        if len(payload) > 7:
            raise ValueError(f"Single frame payload too large: {len(payload)} bytes (max 7)")

        # Build frame: PCI byte + payload + padding
        pci = ISOTP_SINGLE_FRAME | len(payload)
        frame_data = bytes([pci]) + payload
        frame_data = frame_data + b'\x00' * (8 - len(frame_data))  # Pad to 8 bytes

        msg = Message(arbitration_id=self.tx_id, data=frame_data, is_extended_id=False)
        self.bus.send(msg)
        logger.debug(f"→ TX SF: 0x{self.tx_id:03X} [{' '.join(f'{b:02X}' for b in frame_data)}]")

    def _send_multi_frame(self, payload: bytes) -> None:
        """Send a multi-frame ISO-TP message with Flow Control handling.

        Multi-frame format:
        - First Frame: [PCI_HI | PCI_LO | Data[0:6]]
          PCI = 0x1NNN where NNN = total data length (12-bit)
        - Consecutive Frames: [PCI | Data[0:7]]
          PCI = 0x2N where N = sequence number (0-F, wraps)
        """
        total_length = len(payload)
        if total_length > 4095:
            raise ValueError(f"Payload too large for standard ISO-TP: {total_length} bytes (max 4095)")

        # First Frame: 2 PCI bytes + 6 data bytes
        ff_pci_hi = ISOTP_FIRST_FRAME | ((total_length >> 8) & 0x0F)
        ff_pci_lo = total_length & 0xFF
        ff_data = payload[:6]
        first_frame = bytes([ff_pci_hi, ff_pci_lo]) + ff_data
        first_frame = first_frame + b'\x00' * (8 - len(first_frame))

        msg = Message(arbitration_id=self.tx_id, data=first_frame, is_extended_id=False)
        self.bus.send(msg)
        logger.debug(f"→ TX FF: 0x{self.tx_id:03X} [{' '.join(f'{b:02X}' for b in first_frame)}]")

        # Wait for Flow Control from receiver
        fc_result = self._wait_for_flow_control()
        if fc_result is None:
            raise RuntimeError("No Flow Control received after First Frame")

        fc_status, block_size, st_min = fc_result
        if fc_status == FC_OVERFLOW:
            raise RuntimeError("Receiver signaled buffer overflow")

        # Handle FC Wait
        while fc_status == FC_WAIT:
            time.sleep(0.001)
            fc_result = self._wait_for_flow_control()
            if fc_result is None:
                raise RuntimeError("Timeout waiting for Flow Control after Wait")
            fc_status, block_size, st_min = fc_result

        # Calculate separation time from STmin
        separation_time = self._decode_stmin(st_min)

        # Send Consecutive Frames
        remaining_data = payload[6:]
        sequence = 1
        frames_in_block = 0

        while remaining_data:
            # Handle block size (0 = unlimited)
            if block_size > 0 and frames_in_block >= block_size:
                # Wait for next Flow Control
                fc_result = self._wait_for_flow_control()
                if fc_result is None:
                    raise RuntimeError("No Flow Control received after block complete")
                fc_status, block_size, st_min = fc_result
                separation_time = self._decode_stmin(st_min)
                frames_in_block = 0

            # Build Consecutive Frame
            chunk = remaining_data[:7]
            remaining_data = remaining_data[7:]

            cf_pci = ISOTP_CONSECUTIVE_FRAME | (sequence & 0x0F)
            cf_data = bytes([cf_pci]) + chunk
            cf_data = cf_data + b'\x00' * (8 - len(cf_data))

            msg = Message(arbitration_id=self.tx_id, data=cf_data, is_extended_id=False)
            self.bus.send(msg)
            logger.debug(f"→ TX CF: 0x{self.tx_id:03X} [{' '.join(f'{b:02X}' for b in cf_data)}] seq={sequence}")

            sequence = (sequence + 1) % 16
            frames_in_block += 1

            # Apply separation time between frames
            if remaining_data and separation_time > 0:
                time.sleep(separation_time)

    def _wait_for_flow_control(self, timeout: float = None) -> Optional[Tuple[int, int, int]]:
        """Wait for Flow Control frame from receiver.

        Args:
            timeout: Timeout in seconds (default: N_BS_TIMEOUT)

        Returns:
            Tuple of (FC_status, block_size, STmin) or None on timeout.
            FC_status: 0=ContinueToSend, 1=Wait, 2=Overflow
            block_size: Number of CFs to send before waiting for next FC (0=unlimited)
            STmin: Separation time minimum (raw byte value)
        """
        if timeout is None:
            timeout = self.N_BS_TIMEOUT

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                msg = self.bus.recv(timeout=0.1)
            except TypeError:
                msg = self.bus.recv()

            if not msg:
                continue

            if msg.arbitration_id != self.rx_id:
                continue

            frame_type = msg.data[0] & 0xF0
            if frame_type == ISOTP_FLOW_CONTROL:
                fc_status = msg.data[0] & 0x0F
                block_size = msg.data[1]
                st_min = msg.data[2]
                logger.debug(f"← RX FC: 0x{msg.arbitration_id:03X} status={fc_status} BS={block_size} STmin={st_min}")
                return (fc_status, block_size, st_min)

        logger.warning(f"Flow Control timeout after {timeout}s")
        return None

    def _send_flow_control(self, status: int = FC_CONTINUE_TO_SEND, block_size: int = 0, st_min: int = 0) -> None:
        """Send Flow Control frame to transmitter.

        Args:
            status: FC status (0=CTS, 1=Wait, 2=Overflow)
            block_size: Number of CFs to accept before next FC (0=unlimited)
            st_min: Separation time minimum (0-127 = ms, 0xF1-0xF9 = 100-900us)
        """
        fc_pci = ISOTP_FLOW_CONTROL | (status & 0x0F)
        fc_data = bytes([fc_pci, block_size, st_min]) + b'\x00' * 5

        msg = Message(arbitration_id=self.tx_id, data=fc_data, is_extended_id=False)
        self.bus.send(msg)
        logger.debug(f"→ TX FC: 0x{self.tx_id:03X} [{' '.join(f'{b:02X}' for b in fc_data)}]")

    def _receive_response(self, timeout: float) -> Optional[bytes]:
        """Receive ISO-TP response (single or multi-frame).

        Args:
            timeout: Overall timeout for complete message reception

        Returns:
            Complete response payload or None on timeout/error
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                msg = self.bus.recv(timeout=0.1)
            except TypeError:
                msg = self.bus.recv()

            if not msg:
                continue

            if msg.arbitration_id != self.rx_id:
                continue

            frame_type = msg.data[0] & 0xF0

            # Single Frame response
            if frame_type == ISOTP_SINGLE_FRAME:
                length = msg.data[0] & 0x0F
                data = bytes(msg.data[1:1 + length])
                logger.debug(f"← RX SF: 0x{msg.arbitration_id:03X} [{' '.join(f'{b:02X}' for b in msg.data)}]")
                return data

            # First Frame of multi-frame response
            elif frame_type == ISOTP_FIRST_FRAME:
                total_length = ((msg.data[0] & 0x0F) << 8) | msg.data[1]
                data = bytearray(msg.data[2:8])  # First 6 bytes of payload
                logger.debug(f"← RX FF: 0x{msg.arbitration_id:03X} len={total_length} [{' '.join(f'{b:02X}' for b in msg.data)}]")

                # Send Flow Control to allow sender to continue
                self._send_flow_control(status=FC_CONTINUE_TO_SEND, block_size=0, st_min=0)

                # Receive Consecutive Frames
                expected_sequence = 1
                cf_timeout = time.time() + self.N_CR_TIMEOUT

                while len(data) < total_length:
                    if time.time() > cf_timeout:
                        logger.warning("Consecutive Frame timeout")
                        return None

                    try:
                        cf_msg = self.bus.recv(timeout=0.1)
                    except TypeError:
                        cf_msg = self.bus.recv()

                    if not cf_msg:
                        continue

                    if cf_msg.arbitration_id != self.rx_id:
                        continue

                    cf_type = cf_msg.data[0] & 0xF0
                    if cf_type != ISOTP_CONSECUTIVE_FRAME:
                        continue

                    sequence = cf_msg.data[0] & 0x0F
                    if sequence != expected_sequence:
                        logger.warning(f"Sequence mismatch: expected {expected_sequence}, got {sequence}")
                        # Continue anyway; some ECUs may skip or repeat

                    # Calculate how many bytes to take from this frame
                    remaining = total_length - len(data)
                    chunk_len = min(7, remaining)
                    data.extend(cf_msg.data[1:1 + chunk_len])

                    logger.debug(f"← RX CF: 0x{cf_msg.arbitration_id:03X} seq={sequence} [{' '.join(f'{b:02X}' for b in cf_msg.data)}]")

                    expected_sequence = (expected_sequence + 1) % 16
                    cf_timeout = time.time() + self.N_CR_TIMEOUT  # Reset timeout after each CF

                return bytes(data)

        logger.debug(f"Response timeout after {timeout}s")
        return None

    def _decode_stmin(self, st_min: int) -> float:
        """Decode STmin byte to separation time in seconds.

        Args:
            st_min: Raw STmin byte value

        Returns:
            Separation time in seconds
        """
        if st_min <= 127:
            # 0-127: value in milliseconds
            return st_min / 1000.0
        elif 0xF1 <= st_min <= 0xF9:
            # 0xF1-0xF9: 100-900 microseconds
            return (st_min - 0xF0) * 100 / 1000000.0
        else:
            # Reserved values: use minimum delay
            return self.CF_DELAY

    def shutdown(self) -> None:
        """Shutdown the CAN bus connection."""
        if hasattr(self.bus, 'shutdown'):
            self.bus.shutdown()
            logger.info("UDSClient shutdown complete")

    def read_data_by_identifier(self, module, did: int) -> Optional[bytes]:
        """Read Data By Identifier (0x22).

        Args:
            module: BMWModule object (ignored for now, uses client's tx_id)
            did: Data Identifier (2 bytes standard, or 4 bytes for RAM address)

        Supports standard 2-byte DIDs and extended 4-byte DIDs (used for RAM reading).
        """
        if did > 0xFFFF:
            # 4-byte DID (e.g. RAM address)
            did_bytes = struct.pack('>I', did)
        else:
            # Standard 2-byte DID
            did_bytes = struct.pack('>H', did)

        response = self.send_request(0x22, did_bytes)

        if response and response[0] == 0x62:
            # Positive response: 62 [DID...] [DATA...]
            # We need to strip the DID from the response to get just the data
            # The DID length in response matches request
            did_len = len(did_bytes)
            if len(response) >= 1 + did_len:
                return response[1 + did_len:]
        return None

    def read_memory_by_address(self, address: int, size: int) -> Optional[bytes]:
        """Read Memory By Address (0x23)."""
        # Address and length format (4 bytes address, 4 bytes length)
        # Format byte: high nibble = length size, low nibble = address size
        # 0x44 = 4 byte length, 4 byte address
        addr_len_format = bytes([0x44])
        addr_bytes = struct.pack('>I', address)
        size_bytes = struct.pack('>I', size)

        response = self.send_request(0x23, addr_len_format + addr_bytes + size_bytes)

        if response and response[0] == 0x63:
            # Positive response: 63 [DATA...]
            return response[1:]
        return None


__all__ = ["UDSClient"]
