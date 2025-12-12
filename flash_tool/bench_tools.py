"""Bench utilities: export patch + manifest from a calibration binary.

This module provides a small, testable helper to extract a map region
from a calibration image and write a `patch.bin` and `patch.json` manifest
to a specified output directory. It is purposely non-GUI so it can be used
in CI and bench scripts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import os

from flash_tool import validated_maps
from flash_tool.gui.map_model import MapModel
from flash_tool.gui.patch_manifest import make_manifest, write_manifest


def export_patch_with_manifest(binfile: str, mapdef: Any, out_dir: str, absolute_offset: Optional[int] = None, vin: str = "", require_safe: bool = True) -> Dict[str, str]:
    """Extract the map region and write patch.bin + patch.json into `out_dir`.

    Args:
        binfile: path to the calibration binary image
        mapdef: object with attributes `offset`, `rows`, `cols`, `name`
        out_dir: directory to write patch.bin and patch.json
        absolute_offset: optional explicit absolute offset to read from; if
            omitted the function will attempt to use `validated_maps.to_absolute_offset`.
        vin: optional VIN string to include in the manifest

    Returns:
        dict with keys `bin` and `manifest` containing the output paths.
    """
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    rows = int(getattr(mapdef, "rows", 0))
    cols = int(getattr(mapdef, "cols", 0))
    size = rows * cols

    # Safety check: by default refuse to export patches that map into
    # forbidden/rejected regions. Callers may override with `require_safe=False`.
    if require_safe:
        try:
            safe, reason = validated_maps.is_offset_safe(getattr(mapdef, "offset", 0), size)
        except Exception:
            safe, reason = False, "safety check failed"
        if not safe:
            raise ValueError(f"Refusing to export unsafe offset: {reason}")

    if absolute_offset is None:
        try:
            absolute_offset = validated_maps.to_absolute_offset(mapdef.offset)
        except Exception:
            absolute_offset = int(getattr(mapdef, "offset", 0))

    # read bytes
    with open(binfile, "rb") as fh:
        fh.seek(int(absolute_offset))
        data = fh.read(size)

    if len(data) != size:
        raise ValueError(f"Read {len(data)} bytes, expected {size} bytes for map {getattr(mapdef,'name', '')}")

    model = MapModel(rows, cols, data=data)

    bin_path = outp / "patch.bin"
    with open(bin_path, "wb") as bf:
        bf.write(model.export_bytes())

    manifest = make_manifest(mapdef, model, vin=vin, absolute_offset=absolute_offset)
    meta_path = outp / "patch.json"
    write_manifest(manifest, str(meta_path))

    return {"bin": str(bin_path), "manifest": str(meta_path)}
