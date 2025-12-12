"""Map Editor controller and lazy Qt widget.

This is a lightweight scaffold for a future map editor tab. It provides a
framework-agnostic `MapEditorController` and a `create_qt_widget` function
that delegates to a Qt-backed implementation when requested. The controller
is intentionally small so unit tests can exercise it without GUI
dependencies.
"""
from typing import Any, Dict, List, Optional

from flash_tool import validated_maps
from flash_tool.gui.map_model import MapModel


class MapEditorController:
    def __init__(self, log_controller: Optional[Any] = None):
        # controller is intentionally GUI-agnostic; it talks to validated_maps
        # and the simple MapModel so unit tests can exercise behavior.
        self.log_controller = log_controller

    def list_maps(self) -> List[str]:
        try:
            maps = validated_maps.get_all_safe_maps()
            return [m.name for m in maps]
        except Exception:
            return []

    def _resolve_mapdef(self, identifier: str):
        # allow lookup by name or by hex/dec offset
        if not identifier:
            return None
        # direct name match
        for m in validated_maps.get_all_safe_maps():
            if m.name == identifier:
                return m
        # try numeric parse (hex or dec)
        try:
            if identifier.lower().startswith('0x'):
                num = int(identifier, 16)
            else:
                num = int(identifier)
            md = validated_maps.get_map_info(num)
            return md
        except Exception:
            return None

    def load_map(self, identifier: str) -> Dict[str, Any]:
        """Load a validated map definition and return a small response.

        This function does NOT read from device or disk; it returns a
        `MapModel` populated with zeros sized according to the map
        definition so UI code can preview/edit safely in-memory.
        """
        try:
            md = self._resolve_mapdef(identifier)
            if md is None:
                return {'success': False, 'error': 'map not found'}
            rows = int(md.rows or 0)
            cols = int(md.cols or 0)
            size = int(md.size_bytes or (rows * cols))
            # create zero-filled model matching expected size
            data = bytes([0] * size)
            model = MapModel(rows, cols, data=data)
            return {'success': True, 'mapdef': md, 'model': model}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def load_map_from_file(self, identifier: str, file_path: str) -> Dict[str, Any]:
        """Load the validated map bytes from a local calibration `file_path`.

        Returns a dict containing `success`, `mapdef`, `model`, and
        `orig_bytes` (the raw bytes read from the file) on success.
        """
        try:
            md = self._resolve_mapdef(identifier)
            if md is None:
                return {'success': False, 'error': 'map not found'}

            rows = int(md.rows or 0)
            cols = int(md.cols or 0)
            size = int(md.size_bytes or (rows * cols))

            # compute file-relative offset when possible
            try:
                file_offset = validated_maps.to_absolute_offset(md.offset)
            except Exception:
                file_offset = md.offset

            with open(file_path, 'rb') as fh:
                fh.seek(file_offset)
                data = fh.read(size)

            if len(data) != size:
                return {'success': False, 'error': f'read size mismatch: expected {size}, got {len(data)}', 'read_len': len(data)}

            model = MapModel(rows, cols, data=data)
            return {'success': True, 'mapdef': md, 'model': model, 'orig_bytes': data, 'file_path': file_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def save_map(self, identifier: str, data: Any) -> Dict[str, Any]:
        """Save map changes. This is a safe placeholder; it does not write
        to any ECU or calibration image, but validates sizes and returns
        a success indicator so UI workflows can proceed in tests.
        """
        try:
            md = self._resolve_mapdef(identifier)
            if md is None:
                return {'success': False, 'error': 'map not found'}
            # accept MapModel-like objects or raw bytes
            if hasattr(data, 'export_bytes'):
                payload = data.export_bytes()
            elif isinstance(data, (bytes, bytearray)):
                payload = bytes(data)
            else:
                return {'success': False, 'error': 'unsupported payload type'}

            expected = int(md.size_bytes or (md.rows * md.cols))
            if len(payload) != expected:
                return {'success': False, 'error': 'size mismatch'}

            # Non-destructive placeholder: do not write to disk or ECU.
            return {'success': True, 'message': 'saved (in-memory placeholder)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


def create_qt_widget(controller: MapEditorController, parent: Optional[Any] = None):
    # Lazy-load the Qt-backed implementation to avoid importing Qt at module import time.
    try:
        from . import map_editor_widget as _widget_mod
    except Exception as exc:
        raise ImportError('Map Editor Qt widget backend not available') from exc
    return _widget_mod.create_qt_widget(controller, parent)
