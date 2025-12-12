"""PCAN adapter using a real python-can PCAN backend.

This adapter is intentionally *not* a stub: ``connect()`` only succeeds
when the ``python-can`` package is available and a PCAN bus can be
created. If the CAN stack or drivers are missing, ``connect()`` raises
an exception instead of pretending to be connected. This aligns with
the project's "no demo mode" policy – production code must not silently
fall back to non-functional adapters.
"""
from typing import Optional


class PCANAdapter:
    def __init__(self, channel: str, bitrate: int = 500000):
        self.channel = channel
        self.bitrate = bitrate
        self.connected = False
        self._bus = None

    def connect(self) -> bool:
        """Connect to a real PCAN interface via python-can.

        Raises:
            RuntimeError: if python-can is not installed or the PCAN bus
                cannot be created.
        """
        # Require python-can; do not allow stubbed connects.
        try:
            import can  # type: ignore
        except Exception as exc:
            self.connected = False
            raise RuntimeError("python-can is required for PCANAdapter but is not installed") from exc

        try:
            # Try to create a PCAN bus; surface failures as hard errors.
            self._bus = can.interface.Bus(channel=self.channel, bustype='pcan', bitrate=self.bitrate)
        except Exception as exc:
            self._bus = None
            self.connected = False
            raise RuntimeError(f"Failed to create PCAN bus on channel {self.channel}: {exc}") from exc

        self.connected = True
        return True

    def disconnect(self) -> None:
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None
        self.connected = False

    def send(self, arb_id: int, data: bytes) -> None:
        if self._bus is not None:
            import can
            msg = can.Message(arbitration_id=arb_id, data=data)
            try:
                self._bus.send(msg)
            except Exception:
                pass

    def recv(self, timeout: float = 1.0):
        if self._bus is not None:
            try:
                return self._bus.recv(timeout)
            except Exception:
                return None
        return None
