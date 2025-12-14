"""CAN adapter abstraction layer.

This module provides a `create_bus` factory that returns a python-can Bus
instance. It exposes `Message` and `BusABC` to be imported by callers so
the rest of the codebase doesn't import `python-can` directly at module
import time.

Requires python-can library to be installed.
"""

CAN_AVAILABLE = False

try:
    import can as _can  # type: ignore
    CAN_AVAILABLE = True
except ImportError:
    _can = None
    CAN_AVAILABLE = False
    # python-can not installed — allow import to succeed but raise on create_bus call

# Export python-can's Message and Bus implementations
Message = _can.Message
BusABC = getattr(_can, 'BusABC', object)


def create_bus(interface: str, channel: str, bitrate: int):
    """Create and return a python-can Bus instance.

    Args:
        interface: CAN interface type ('pcan', 'socketcan', 'kvaser', etc.)
        channel: CAN channel identifier (e.g., 'PCAN_USBBUS1', 'can0')
        bitrate: CAN bus bitrate in bits/second (typically 500000 for BMW)

    Returns:
        can.Bus: Configured CAN bus instance

    Raises:
        ImportError: If python-can is not installed
        OSError: If CAN interface/channel not found
        ValueError: If parameters are invalid

    Example:
        >>> bus = create_bus('pcan', 'PCAN_USBBUS1', 500000)
        >>> bus.send(Message(arbitration_id=0x123, data=b'\x01\x02'))
    """
    if not CAN_AVAILABLE:
        raise ImportError("python-can library required but not installed")

    try:
        return _can.Bus(interface=interface, channel=channel, bitrate=bitrate)
    except Exception as e:
        raise OSError(
            f"Failed to create CAN bus: {e}\n"
            f"Interface: {interface}, Channel: {channel}, Bitrate: {bitrate}\n"
            f"Ensure CAN adapter is connected and drivers are installed."
        ) from e


__all__ = ["create_bus", "Message", "BusABC", "CAN_AVAILABLE"]
