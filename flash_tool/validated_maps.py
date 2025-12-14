"""Validated maps registry and safety helpers.

This module provides a deterministic registry of XDF-VALIDATED maps used by
unit tests and several CLI helpers. It reuses CRC-zone utilities when
available and exposes a backward-compatible surface that other modules
and tests expect (names like `VALIDATED_MAPS`, `REJECTED_MAPS`, and
functions such as `to_absolute_offset`, `is_offset_safe`, etc.).

IMPORTANT: Maps in this registry are verified against the authoritative XDF for the OS family:
- For I8A0S OS, the Corbanistan XDF is authoritative (I8A0S_Custom_Corbanistan.xdf / I8A0S_Corbanistan.xdf).
- For non-I8A0S OS variants (IJE0S, IKM0S, INA0S, etc.), use the Zarboz XDF variants (IJE0S_zarboz.xdf, IKM0S_zarboz.xdf, INA0S_zarboz.xdf).

Previous binary-diff derived offsets were removed where they are not present in the authoritative XDF for the given OS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Dict, List, Optional, Tuple, Sequence

logger = logging.getLogger(__name__)

# Constants (file-relative calibration image)
ECU_BASE = 0x800000
# Calibration adjustment used to map a relative offset into the file image.
# Historically some offsets are reported relative to a 0x810000 base while
# others are provided as file-relative addresses. The helper `to_absolute_offset`
# adds `CALIB_ADJUST` for relative candidates so that both representations
# normalize to the same file-relative value.
CALIB_ADJUST = 0x010000
BIN_SIZE = 0x200000  # 2MB calibration image


class MapCategory(Enum):
    IGNITION = "IGNITION"
    WGDC = "WGDC"
    VMAX = "VMAX"
    RPM = "RPM"
    OTHER = "OTHER"


class ValidationStatus(Enum):
    PASSED = "PASSED"
    CONDITIONAL = "CONDITIONAL"
    FAILED = "FAILED"


@dataclass
class Axis:
    values: List[float] = field(default_factory=list)


@dataclass
class MapDefinition:
    name: str
    offset: int
    size_bytes: int
    rows: int = 0
    cols: int = 0
    rpm_axis: Optional[Axis] = None
    load_axis: Optional[Axis] = None
    description: str = ""
    warnings: List[str] = field(default_factory=list)
    category: MapCategory = MapCategory.OTHER
    status: ValidationStatus = ValidationStatus.PASSED
    confidence: int = 100


# Backwards-compatible alias used by older tests
MapDef = MapDefinition


# ---------------------------------------------------------------------------
# XDF-Validated Maps Registry (I8A0S_Custom_Corbanistan.xdf)
# ---------------------------------------------------------------------------
# NOTE: Only offsets verified against the Corbanistan XDF are included here.
# Previous binary-diff derived offsets (0x057B58, 0x05D288, 0x060EC0, 0x051580,
# 0x051DA0, 0x0546D0) were REMOVED because they are NOT in the XDF.
# ---------------------------------------------------------------------------
VALIDATED_MAPS: Dict[int, MapDefinition] = {
    # WGDC Maps - XDF Validated
    # All 3 maps below are verified via:
    # 1. Present in I8A0S.xdf (Corbanistan XDF)
    # 2. Data at offsets contains sensible WGDC percentages (2-60% stock)
    # 3. 0x05F7F6 and 0x05FAB2 are the ONLY regions modified in stage1 tuned bin
    0x05F72A: MapDefinition(
        name="WGDC (Pre-Control A)",
        offset=0x05F72A,
        size_bytes=128,  # 8x8 x 16-bit
        rows=8,
        cols=8,
        description="WGDC during low load (KF_ATLVST_GD) - XDF validated",
        category=MapCategory.WGDC,
        confidence=100,
    ),
    0x05F7F6: MapDefinition(
        name="WGDC (Base)",
        offset=0x05F7F6,
        size_bytes=640,  # 20x16 x 16-bit
        rows=20,
        cols=16,
        description="Wastegate Duty Cycle base table (KF_ATLVST) - XDF validated, MODIFIED IN TUNED BIN",
        category=MapCategory.WGDC,
        confidence=100,
    ),
    0x05FAB2: MapDefinition(
        name="WGDC (Spool)",
        offset=0x05FAB2,
        size_bytes=384,  # 16x12 x 16-bit = 192 values
        rows=16,
        cols=12,
        description="Wastegate Duty Cycle during spool - XDF validated, MODIFIED IN TUNED BIN (stock: 2-58%, tuned: 0.2-100%)",
        category=MapCategory.WGDC,
        confidence=100,
    ),
    # NOTE: Burble Ignition Timing maps (0x063A00, 0x063A60, etc.) are in the XDF
    # but contain axis/placeholder data in stock bins - only valid after MHD+ modification.
    # They are intentionally excluded from the validated maps registry.
}


REJECTED_MAPS: Dict[int, MapDefinition] = {
    0x054A90: MapDefinition(
        name="Checksum_Block_A",
        offset=0x054A90,
        size_bytes=0xC0,
        description="Checksum block - DO NOT WRITE",
        warnings=["Checksum block - WILL BRICK ECU"],
        category=MapCategory.OTHER,
        status=ValidationStatus.FAILED,
    ),
    0x05AD20: MapDefinition(
        name="Checksum_Block_B",
        offset=0x05AD20,
        size_bytes=0x60,
        description="Checksum block - DO NOT WRITE",
        warnings=["Checksum block - WILL BRICK ECU"],
        category=MapCategory.OTHER,
        status=ValidationStatus.FAILED,
    ),
}


CONDITIONAL_MAPS: Dict[int, MapDefinition] = {}


# Forbidden regions expressed as (start_inclusive, end_exclusive, reason)
FORBIDDEN_REGIONS: List[Tuple[int, int, str]] = [
    (0x000000, 0x008000, "Boot code area"),
    (0x054A90, 0x054B50, "WGDC checksum block A"),
    (0x05AD20, 0x05AD80, "WGDC checksum block B"),
    (0x1F0000, 0x200000, "Flash counter / config"),
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def to_absolute_offset(candidate: int) -> int:
    """Normalize `candidate` (ECU absolute or relative offset) to a
    file-relative offset in 0 .. BIN_SIZE-1.

    Rules:
      - If candidate >= ECU_BASE (0x800000), treat as ECU absolute and
        return candidate - ECU_BASE.
      - Otherwise treat as relative calibration offset and return
        candidate + CALIB_ADJUST.

    Raises ValueError when the resulting offset is outside the file.
    """
    if candidate >= ECU_BASE:
        file_off = candidate - ECU_BASE
    else:
        file_off = candidate + CALIB_ADJUST

    if file_off < 0 or file_off >= BIN_SIZE:
        raise ValueError(f"Offset maps outside valid file range: 0x{file_off:06X}")

    return file_off


def is_offset_safe(offset: int, size: int = 0) -> Tuple[bool, str]:
    """Return (is_safe, reason).

    If `offset` is already a file-relative address (0 <= offset < BIN_SIZE)
    it is used as-is. Otherwise the function attempts to normalize the
    candidate using `to_absolute_offset()`.
    """
    # Build a set of plausible file-relative interpretations for the
    # provided `offset`. We accept inputs in several coordinate systems:
    # - ECU absolute (>= ECU_BASE) -> converted to file-relative by
    #   subtracting `ECU_BASE`.
    # - File-relative (0 <= offset < BIN_SIZE) -> used as-is.
    # - Calibration-relative (common small offsets) -> converted using
    #   `to_absolute_offset()` (adds `CALIB_ADJUST`).
    candidates: List[int] = []

    # ECU absolute
    if offset >= ECU_BASE:
        candidates.append(offset - ECU_BASE)
    else:
        # file-relative candidate when it lies within the image
        if 0 <= offset < BIN_SIZE:
            candidates.append(offset)

        # calibration-relative candidate (may raise ValueError)
        try:
            fo_rel = to_absolute_offset(offset)
        except ValueError:
            fo_rel = None

        if fo_rel is not None and fo_rel not in candidates:
            candidates.append(fo_rel)

    if not candidates:
        return False, f"Offset maps outside valid file range: 0x{offset:06X}"

    # Helper to test a single file-relative candidate against forbidden
    # regions and rejected maps. We conservatively reject if ANY plausible
    # interpretation indicates an unsafe region.
    for fo in candidates:
        if size < 0 or fo + size > BIN_SIZE:
            return False, f"Write region out of bounds: 0x{fo:06X}+{size}"

        # Check forbidden regions. Interpret each declared forbidden region
        # in both common coordinate representations (file-relative and
        # calibration-relative) before testing overlap. This makes the
        # detection robust against mixed conventions in the registry.
        for start, end, reason in FORBIDDEN_REGIONS:
            region_variants: List[Tuple[int, int]] = []

            # Variant A: treat region as file-relative if it lies inside file
            if 0 <= start < BIN_SIZE:
                rs = start
                re = min(end, BIN_SIZE)
                if rs < re:
                    region_variants.append((rs, re))

            # Variant B: treat region as calibration-relative and convert
            rs2 = start + CALIB_ADJUST
            re2 = min(end + CALIB_ADJUST, BIN_SIZE)
            if rs2 < re2:
                region_variants.append((rs2, re2))

            for region_start, region_end in region_variants:
                if fo < region_end and (fo + size) > region_start:
                    return False, f"Forbidden region: {reason} (0x{start:06X}-0x{end-1:06X})"

        # Check rejected maps in both interpretations (relative and
        # file-relative) as well
        for rdef in REJECTED_MAPS.values():
            r_offsets = [rdef.offset, rdef.offset + CALIB_ADJUST]
            for rfo in set(r_offsets):
                if 0 <= rfo < BIN_SIZE:
                    if fo < (rfo + rdef.size_bytes) and (fo + size) > rfo:
                        return False, f"Rejected map: {rdef.description}"

    return True, "OK"


def get_all_safe_maps() -> List[MapDefinition]:
    """Return a stable list of registered safe maps."""
    return list(VALIDATED_MAPS.values())


def get_maps_by_category(cat: MapCategory) -> List[MapDefinition]:
    return [m for m in VALIDATED_MAPS.values() if m.category == cat]


def get_map_info(offset: int) -> Optional[MapDefinition]:
    """Return the MapDefinition whose normalized offset matches `offset`.

    Returns None if unknown.
    """
    # Accept multiple plausible interpretations for `offset` (ECU-absolute,
    # file-relative, calibration-relative) and match against registered
    # `MapDefinition` entries. This mirrors the tolerant normalization used
    # in `is_offset_safe()` and helps callers that provide offsets in mixed
    # conventions.
    candidates: List[int] = []

    if offset >= ECU_BASE:
        candidates.append(offset - ECU_BASE)
    else:
        if 0 <= offset < BIN_SIZE:
            candidates.append(offset)
        try:
            fo_rel = to_absolute_offset(offset)
        except Exception:
            fo_rel = None
        if fo_rel is not None and fo_rel not in candidates:
            candidates.append(fo_rel)

    for m in VALIDATED_MAPS.values():
        # Allow matching against the map's stored offset (assumed
        # calibration-relative) and its file-relative equivalent.
        m_rel = m.offset
        m_file = m.offset + CALIB_ADJUST
        for c in candidates:
            if c == m_rel or c == m_file:
                return m

    return None


def find_affected_crc_zones(offset: int, size: int, ecu_type: str = "MSD81") -> Sequence[object]:
    """Return CRC zones (from `crc_zones`) affected by a modification.

    The returned objects are the `CRCZone` dataclass instances defined in
    `flash_tool.crc_zones` so callers can inspect `name`, `start_offset`,
    `end_offset`, `crc_offset` and `crc_type`.
    """
    try:
        import flash_tool.crc_zones as crc_zones
    except Exception:
        logger.debug("crc_zones module not available; cannot find affected zones")
        return []

    fo = to_absolute_offset(offset)
    return crc_zones.find_affected_zones(fo, size, ecu_type)


def update_checksums_for_modifications(data: bytearray, modifications: List[Tuple[int, int]], ecu_type: str = "MSD81") -> int:
    """Update CRCs for all zones affected by `modifications`.

    `modifications` is a list of (offset, size) tuples where offsets may be
    specified in ECU absolute or relative form. Returns the number of zones
    updated.
    """
    try:
        import flash_tool.crc_zones as crc_zones
    except Exception:
        logger.debug("crc_zones module not available; cannot update checksums")
        return 0

    # Normalize modifications into file-relative coordinates
    mod_norm: List[Tuple[int, int]] = []
    for off, sz in modifications:
        try:
            mod_norm.append((to_absolute_offset(off), sz))
        except Exception:
            logger.warning(f"Skipping modification with invalid offset: {off}")

    return crc_zones.update_all_affected_crcs(data, mod_norm, ecu_type)


def print_map_summary() -> None:
    print(f"Safe Maps: {len(VALIDATED_MAPS)}")
    print(f"Rejected Maps: {len(REJECTED_MAPS)}")
    print(f"Forbidden Regions: {len(FORBIDDEN_REGIONS)}")


def load_validated_maps_from_offsets() -> int:
    """Enrich VALIDATED_MAPS registry using entries from `flash_tool.map_offsets`.

    Returns the number of entries added. This function is non-fatal and will
    quietly skip on import errors so tests and CLI remain resilient.
    """
    try:
        import flash_tool.map_offsets as map_offsets
    except Exception:
        logger.debug("map_offsets not available; skipping validated_maps enrichment")
        return 0

    added = 0
    category_map = {
        "vmax": MapCategory.VMAX,
        "rpm_limiter": MapCategory.RPM,
        "dtc_codewords": MapCategory.OTHER,
        "burbles_timing_tables": MapCategory.OTHER,
        "burbles_timing_maps": MapCategory.OTHER,
    }

    try:
        all_offsets = map_offsets.get_all_modifiable_offsets()
    except Exception:
        logger.debug("map_offsets.get_all_modifiable_offsets() not available")
        return 0

    for cat_key, offsets in all_offsets.items():
        mapped_cat = category_map.get(cat_key, MapCategory.OTHER)
        for off in offsets:
            try:
                start = getattr(off, "start", None) or getattr(off, "offset", None)
                size = getattr(off, "size", getattr(off, "size_bytes", 1))
                desc = getattr(off, "description", "") or str(off)
                if start is None:
                    continue
                if start in VALIDATED_MAPS or start in REJECTED_MAPS:
                    continue
                # Skip offsets that are not safe (forbidden regions, rejected maps, out-of-bounds)
                try:
                    safe, reason = is_offset_safe(start, int(size))
                except Exception:
                    safe, reason = False, "invalid offset"
                if not safe:
                    logger.debug("Skipping offset %s due to safety check: %s", hex(start), reason)
                    continue
                name = f"{cat_key}:{start:#06X}"
                md = MapDefinition(
                    name=name,
                    offset=start,
                    size_bytes=int(size),
                    description=desc,
                    category=mapped_cat,
                    confidence=80,
                )
                VALIDATED_MAPS[start] = md
                added += 1
            except Exception as e:
                logger.debug("Skipping offset from map_offsets: %s", e)

    logger.info("Enriched VALIDATED_MAPS from map_offsets: %d entries", added)
    return added


# Try to enrich registry at import time (non-fatal)
try:
    load_validated_maps_from_offsets()
except Exception:
    pass


__all__ = [
    'MapDefinition', 'MapDef', 'MapCategory', 'ValidationStatus', 'Axis',
    'VALIDATED_MAPS', 'REJECTED_MAPS', 'CONDITIONAL_MAPS', 'FORBIDDEN_REGIONS',
    'to_absolute_offset', 'is_offset_safe', 'get_all_safe_maps', 'get_maps_by_category',
    'get_map_info', 'print_map_summary', 'find_affected_crc_zones', 'update_checksums_for_modifications'
]
 

