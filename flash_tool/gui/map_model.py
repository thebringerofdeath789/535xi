"""Lightweight map model used by GUI editors.

This model isolates map editing logic from Qt widgets so it can be
unit-tested without GUI dependencies. It stores map data as a
`bytearray` and supports single-cell edits, a simple undo/redo stack,
uniform scaling, and export to bytes.

Supports both 8-bit (1 byte per cell) and 16-bit (2 bytes per cell) maps.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple


class MapModel:
    def __init__(self, rows: int, cols: int, data: Optional[bytes] = None, bytes_per_cell: int = 0):
        """Initialize a map model.
        
        Args:
            rows: Number of rows in the map
            cols: Number of columns in the map
            data: Raw map data bytes (optional, creates zeros if not provided)
            bytes_per_cell: Bytes per cell value. If 0, auto-detect from data length:
                           - If data length == rows*cols: 1 byte per cell
                           - If data length == rows*cols*2: 2 bytes per cell (16-bit)
        """
        self.rows = int(rows)
        self.cols = int(cols)
        total_cells = self.rows * self.cols
        
        # Auto-detect bytes per cell from data length if not specified
        if bytes_per_cell == 0:
            if data is not None:
                if len(data) == total_cells:
                    bytes_per_cell = 1
                elif len(data) == total_cells * 2:
                    bytes_per_cell = 2
                else:
                    raise ValueError(f"data length {len(data)} does not match rows*cols ({total_cells}) or rows*cols*2 ({total_cells*2})")
            else:
                bytes_per_cell = 1  # Default to 8-bit if no data
        
        self.bytes_per_cell = bytes_per_cell
        expected_len = total_cells * bytes_per_cell
        
        if data is not None:
            if len(data) != expected_len:
                raise ValueError(f"data length {len(data)} does not match expected {expected_len} (rows*cols*bytes_per_cell)")
            self._data = bytearray(data)
        else:
            self._data = bytearray([0] * expected_len)

        # undo/redo stacks store tuples of (idx, previous_value)
        self._undo_stack: List[Tuple[Tuple[int, int], ...]] = []
        self._redo_stack: List[Tuple[Tuple[int, int], ...]] = []
        
        # Max value based on bytes per cell
        self._max_value = 255 if bytes_per_cell == 1 else 65535

    def _idx(self, r: int, c: int) -> int:
        """Get byte offset for a cell (for 16-bit, this is the offset to first byte)."""
        if r < 0 or c < 0 or r >= self.rows or c >= self.cols:
            raise IndexError("cell out of range")
        return (r * self.cols + c) * self.bytes_per_cell

    def get(self, r: int, c: int) -> int:
        """Get cell value. For 16-bit maps, returns the full 16-bit value (little-endian)."""
        idx = self._idx(r, c)
        if self.bytes_per_cell == 1:
            return int(self._data[idx])
        else:
            # 16-bit little-endian
            return struct.unpack_from('<H', self._data, idx)[0]

    def set(self, r: int, c: int, value: int, record_undo: bool = True) -> None:
        """Set cell value. For 16-bit maps, stores as little-endian."""
        if value < 0:
            value = 0
        if value > self._max_value:
            value = self._max_value
        
        idx = self._idx(r, c)
        prev = self.get(r, c)  # Get previous value using get() method
        
        if self.bytes_per_cell == 1:
            self._data[idx] = int(value)
        else:
            # 16-bit little-endian
            struct.pack_into('<H', self._data, idx, int(value))
        
        if record_undo:
            # For undo, store cell index (not byte index) and previous value
            cell_idx = r * self.cols + c
            self._undo_stack.append(((cell_idx, prev),))
            self._redo_stack.clear()

    def apply_scale(self, factor: float) -> int:
        """Scale all values by factor. Returns count of changed cells."""
        changes: List[Tuple[int, int]] = []
        for r in range(self.rows):
            for c in range(self.cols):
                old = self.get(r, c)
                new = int(round(old * factor))
                if new < 0:
                    new = 0
                if new > self._max_value:
                    new = self._max_value
                if new != old:
                    cell_idx = r * self.cols + c
                    changes.append((cell_idx, old))
                    self.set(r, c, new, record_undo=False)
        if changes:
            self._undo_stack.append(tuple(changes))
            self._redo_stack.clear()
        return len(changes)

    def export_bytes(self) -> bytes:
        return bytes(self._data)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        step = self._undo_stack.pop()
        redo: List[Tuple[int, int]] = []
        for cell_idx, old in step:
            r = cell_idx // self.cols
            c = cell_idx % self.cols
            cur = self.get(r, c)
            redo.append((cell_idx, cur))
            self.set(r, c, old, record_undo=False)
        self._redo_stack.append(tuple(redo))
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        step = self._redo_stack.pop()
        undo_record: List[Tuple[int, int]] = []
        for cell_idx, val in step:
            r = cell_idx // self.cols
            c = cell_idx % self.cols
            cur = self.get(r, c)
            undo_record.append((cell_idx, cur))
            self.set(r, c, val, record_undo=False)
        self._undo_stack.append(tuple(undo_record))
        return True

    def shape(self) -> Tuple[int, int]:
        return self.rows, self.cols

    def size(self) -> int:
        """Return total bytes in the map data."""
        return len(self._data)
    
    def cell_count(self) -> int:
        """Return number of cells (rows * cols)."""
        return self.rows * self.cols

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def patch_info(self) -> dict:
        """Return small metadata about the current export payload.

        Returns a dict with `length` (bytes) and `crc` (uint32).
        """
        import zlib

        b = self.export_bytes()
        return {
            'length': len(b),
            'crc': zlib.crc32(b) & 0xFFFFFFFF,
        }
