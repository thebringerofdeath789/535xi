"""Helpers to create and write a small JSON manifest for map patch files.

The manifest is written alongside the binary patch file and is intended for
bench validation, logging, and human inspection. It is NOT consumed by the
flashing pipeline, which still expects a raw binary image.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List
import json
import zlib
from flash_tool import validated_maps


def make_manifest(mapdef: Any, model: Any, vin: str = "", absolute_offset: Optional[int] = None) -> Dict[str, Any]:
    """Build a small manifest describing the patch payload.

    Args:
        mapdef: object with attributes `name`, `offset`, `rows`, `cols` (map definition)
        model: `MapModel`-like object exposing `export_bytes()`
        vin: optional VIN string read from the ECU
        absolute_offset: optional absolute file offset (if known)

    Returns:
        dict with keys: map_name, map_offset, absolute_offset, rows, cols, length, crc, vin
    """
    data = model.export_bytes()

    # Attempt to include affected CRC zones (best-effort). If the
    # `crc_zones` helper module is unavailable, include an empty list.
    zones_info: List[Dict[str, Optional[int]]] = []
    try:
        zones = validated_maps.find_affected_crc_zones(getattr(mapdef, 'offset', 0), len(data))
        for z in zones:
            zones_info.append({
                'name': getattr(z, 'name', None),
                'start_offset': getattr(z, 'start_offset', None),
                'end_offset': getattr(z, 'end_offset', None),
                'crc_offset': getattr(z, 'crc_offset', None),
                'crc_type': getattr(z, 'crc_type', None),
            })
    except Exception:
        zones_info = []

    # Merge zones info into manifest
    base = {
        "map_name": getattr(mapdef, "name", ""),
        "map_offset": int(getattr(mapdef, "offset", 0)) if getattr(mapdef, "offset", None) is not None else None,
        "absolute_offset": int(absolute_offset) if absolute_offset is not None else (int(getattr(mapdef, "offset", 0)) if getattr(mapdef, "offset", None) is not None else None),
        "rows": int(getattr(mapdef, "rows", 0)),
        "cols": int(getattr(mapdef, "cols", 0)),
        "length": len(data),
        "crc": zlib.crc32(data) & 0xFFFFFFFF,
        "vin": vin or "",
        "affected_crc_zones": zones_info,
    }

    return base


def write_manifest(manifest: Dict[str, Any], path: str) -> None:
    """Write the manifest as pretty JSON to `path`."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
