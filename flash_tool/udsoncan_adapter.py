"""Adapter providing a udsoncan-style BaseConnection backed by
`DirectCANFlasher`'s ISO-TP helpers.

This adapter lets you use the project's existing ISO-TP send/receive
implementation as a transport for `udsoncan` clients without requiring
the external `isotp` package. It implements the minimal
`BaseConnection` interface udsoncan expects by delegating to the
flasher's internal send/receive helpers.
"""
from typing import Optional
import logging

try:
    # Import the udsoncan BaseConnection if available to keep API parity
    from udsoncan.connections import BaseConnection  # type: ignore
    HAS_UDSONCAN = True
except Exception:
    BaseConnection = object
    HAS_UDSONCAN = False

from .direct_can_flasher import DirectCANFlasher

logger = logging.getLogger(__name__)


class DirectFlasherConnection(BaseConnection):
    """BaseConnection-compatible wrapper around a `DirectCANFlasher`.

    The connection uses the flasher's `_send_single_frame` /
    `_send_multi_frame` helpers to transmit and `_receive_isotp_message`
    to receive UDS responses.
    """

    def __init__(self, flasher: DirectCANFlasher, name: Optional[str] = None):
        # If udsoncan is present, call the BaseConnection initializer
        if HAS_UDSONCAN:
            super().__init__(name)
        else:
            # Provide logger attribute for compatibility
            self.logger = logging.getLogger(name or 'DirectFlasherConnection')

        self.flasher = flasher
        self.opened = False

    def open(self) -> "DirectFlasherConnection":
        # Ensure CAN bus is available on the flasher
        if not getattr(self.flasher, 'bus', None):
            self.flasher.connect()
        self.opened = True
        self.logger.info('DirectFlasherConnection opened')
        return self

    def close(self) -> None:
        self.opened = False
        self.logger.info('DirectFlasherConnection closed')

    def is_open(self) -> bool:
        return self.opened

    def empty_rxqueue(self) -> None:
        # No queued rx buffer used here
        return None

    def specific_send(self, payload: bytes, timeout: Optional[float] = None) -> None:
        # Send using flasher's ISO-TP helpers
        if len(payload) <= self.flasher.MAX_TRANSFER_SIZE and len(payload) <= 7:
            self.flasher._send_single_frame(payload)
        else:
            self.flasher._send_multi_frame(payload)

    def specific_wait_frame(self, timeout: Optional[float] = None) -> Optional[bytes]:
        # Receive using flasher's ISO-TP receive helper
        return self.flasher._receive_isotp_message(timeout)


__all__ = ["DirectFlasherConnection", "HAS_UDSONCAN"]
