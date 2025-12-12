#!/usr/bin/env python3
"""
BMW N54 Runtime Map Patching Engine - Multi-Map Modification System
====================================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Comprehensive map patching system for applying multiple ECU
    modifications in a single operation. Applies changes to flash
    data in memory before writing to ECU, with automatic CRC
    recalculation and validation.

Features:
    - Apply multiple map patches atomically
    - Automatic CRC recalculation for affected zones
    - Pre/post-patch validation and safety checks
    - Preset system for common tuning stages
    - Rollback capability on validation failure
    - Map offset database from MHD binary analysis

Classes:
    PatchError(Exception) - Patching operation errors
    MapPatch - Individual map patch definition
    PatchSet - Collection of patches to apply
    MapPatcher - Main patching engine

Functions:
    apply_patches_to_file(input_file: Path, output_file: Path, patch_set: PatchSet, verify: bool) -> Dict[str, Any]

Variables (Module-level):
    logger: logging.Logger - Module logger
"""

import logging
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

from . import map_offsets
from . import crc_zones
from . import validated_maps
from . import bmw_checksum
# During migration, use `tuning_parameters` as the canonical presets source
from . import tuning_parameters

logger = logging.getLogger(__name__)


class PatchError(Exception):
    """Raised when a patch operation fails"""
    pass


@dataclass
class MapPatch:
    """Represents a single map modification operation"""
    name: str
    offset: int
    size: int
    data: bytes
    description: str = ""
    category: str = "custom"  # vmax, rpm, boost, fuel, timing, dtc, burbles
    validate: bool = True
    
    def __post_init__(self):
        if len(self.data) != self.size:
            raise ValueError(f"Data size ({len(self.data)}) doesn't match declared size ({self.size})")
    
    def __repr__(self):
        return f"MapPatch({self.name}, @0x{self.offset:08X}, {self.size} bytes, {self.category})"


@dataclass
class PatchSet:
    """Collection of patches with metadata"""
    name: str
    description: str
    patches: List[MapPatch] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_patch(self, patch: MapPatch):
        """Add a patch to the set"""
        self.patches.append(patch)
        logger.debug(f"Added patch '{patch.name}' to set '{self.name}'")
    
    def remove_patch(self, name: str) -> bool:
        """Remove a patch by name"""
        original_len = len(self.patches)
        self.patches = [p for p in self.patches if p.name != name]
        removed = len(self.patches) < original_len
        if removed:
            logger.debug(f"Removed patch '{name}' from set '{self.name}'")
        return removed
    
    def get_patch(self, name: str) -> Optional[MapPatch]:
        """Get a patch by name"""
        for patch in self.patches:
            if patch.name == name:
                return patch
        return None
    
    def __len__(self):
        return len(self.patches)
    
    def __repr__(self):
        return f"PatchSet({self.name}, {len(self.patches)} patches)"


class MapPatcher:
    """Main map patching engine"""
    
    def __init__(self, ecu_type: str = "MSD81"):
        """
        Initialize map patcher.
        
        Args:
            ecu_type: ECU type ('MSD80' or 'MSD81')
        """
        self.ecu_type = ecu_type
        self.crc_zones = crc_zones.get_zones_for_ecu(ecu_type)
        logger.info(f"Initialized MapPatcher for {ecu_type} ({len(self.crc_zones)} CRC zones)")
    
    def apply_patch(self, data: bytearray, patch: MapPatch, update_crc: bool = True) -> Dict[str, Any]:
        """
        Apply a single patch to flash data.
        
        Args:
            data: Flash binary data (modified in-place)
            patch: MapPatch to apply
            update_crc: Whether to update affected CRC zones
            
        Returns:
            Dict with patch results
        """
        logger.info(f"Applying patch: {patch.name} @ 0x{patch.offset:08X} ({patch.size} bytes)")
        
        # Validation
        if patch.validate:
            validation = self._validate_patch(data, patch)
            if not validation['valid']:
                raise PatchError(f"Patch validation failed: {', '.join(validation['errors'])}")
        
        # Find affected CRC zones before modification
        affected_zones = crc_zones.find_affected_zones(patch.offset, patch.size, self.ecu_type)
        
        # Apply the patch
        data[patch.offset:patch.offset + patch.size] = patch.data
        logger.info(f"✓ Wrote {patch.size} bytes @ 0x{patch.offset:08X}")
        
        # Update CRCs if requested
        updated_zones = []
        if update_crc and affected_zones:
            for zone in affected_zones:
                crc_zones.update_zone_crc(data, zone)
                updated_zones.append(zone.name)
        
        return {
            'success': True,
            'patch_name': patch.name,
            'offset': patch.offset,
            'size': patch.size,
            'affected_zones': [z.name for z in affected_zones],
            'updated_crcs': updated_zones
        }
    
    def apply_patch_set(self, data: bytearray, patch_set: PatchSet, 
                        progress_callback: Optional[Callable[[str, int], None]] = None,
                        update_crcs: bool = True) -> Dict[str, Any]:
        """
        Apply multiple patches from a PatchSet.
        
        Args:
            data: Flash binary data (modified in-place)
            patch_set: PatchSet containing patches to apply
            progress_callback: Optional callback(message, percent)
            
        Returns:
            Dict with results for all patches
        """
        logger.info(f"Applying patch set: '{patch_set.name}' ({len(patch_set)} patches)")
        
        if progress_callback:
            progress_callback(f"Starting patch set: {patch_set.name}", 0)
        
        results = {
            'success': True,
            'patch_set_name': patch_set.name,
            'total_patches': len(patch_set),
            'applied_patches': [],
            'failed_patches': [],
            'affected_zones': set(),
            'errors': []
        }
        
        # Apply each patch (without updating CRCs yet)
        for i, patch in enumerate(patch_set.patches):
            try:
                if progress_callback:
                    pct = int((i / len(patch_set)) * 90)  # Reserve last 10% for CRC
                    progress_callback(f"Applying: {patch.name}", pct)
                
                result = self.apply_patch(data, patch, update_crc=False)
                results['applied_patches'].append(result)
                results['affected_zones'].update(result['affected_zones'])
                
            except Exception as e:
                logger.error(f"Failed to apply patch '{patch.name}': {e}")
                results['failed_patches'].append({'name': patch.name, 'error': str(e)})
                results['errors'].append(f"{patch.name}: {e}")
                results['success'] = False
        
        # Update all affected CRC zones once at the end (optional)
        if update_crcs and results['affected_zones']:
            if progress_callback:
                progress_callback("Updating CRC checksums...", 90)
            
            logger.info(f"Updating {len(results['affected_zones'])} affected CRC zones...")
            
            # Convert modifications to format expected by update_all_affected_crcs
            modifications = [(p.offset, p.size) for p in patch_set.patches if p in 
                           [patch_set.patches[i] for i in range(len(results['applied_patches']))]]
            
            updated_count = crc_zones.update_all_affected_crcs(data, modifications, self.ecu_type)
            results['updated_crc_count'] = updated_count
        
        if progress_callback:
            progress_callback("Patch set complete!", 100)
        
        # Convert set to list for JSON serialization
        results['affected_zones'] = list(results['affected_zones'])
        
        logger.info(f"✓ Patch set complete: {len(results['applied_patches'])}/{results['total_patches']} applied")
        return results

    def apply_boost_from_patchset(self, data: bytearray, patch_set: PatchSet) -> Dict[str, Any]:
                """Apply boost-related changes based on TuningPreset/canonical preset metadata in a PatchSet.

                This uses the universal boost_patcher module to modify WGDC, load
                targets, boost ceiling, and boost limit multiplier tables based on
                the requested ``boost.max_boost_bar`` setting in the preset values.

                Notes:
                - Only runs when ``patch_set.metadata['values']['boost']['enabled']``
                    is True.
                - Requires a supported software version with XDF-derived boost tables
                    (see boost_patcher.get_boost_tables_for_bin).
                - Returns a dict with details and a list of (offset, size) tuples for
                    CRC recalculation.
                """

        # For legacy patchsets, 'options' may exist; canonical patchsets use 'values'.
        options_meta = patch_set.metadata.get("values") if isinstance(patch_set.metadata, dict) else None
        if not isinstance(options_meta, dict):
            return {"success": False, "applied": False, "reason": "no tuning preset metadata"}

        boost_cfg = options_meta.get("boost") or {}
        if not boost_cfg.get("enabled"):
            return {"success": True, "applied": False, "reason": "boost disabled"}

        try:
            max_boost_bar = float(boost_cfg.get("max_boost_bar", 0.0))
        except Exception as exc:  # pragma: no cover - defensive
            raise PatchError(f"Invalid boost.max_boost_bar in options metadata: {exc}")

        # Canonical preset validation already enforces 1.0-2.0 bar for enabled boost,
        # but clamp defensively here as well.
        if max_boost_bar < 1.0 or max_boost_bar > 2.0:
            raise PatchError(f"Boost max_boost_bar out of range: {max_boost_bar}")

        # Approximate stock N54 boost is ~0.6 bar (7-9 PSI). Compute the
        # requested increase relative to this baseline and convert to PSI
        # for the underlying boost_patcher, which operates in PSI.
        STOCK_BOOST_BAR = 0.6
        PSI_PER_BAR = 14.5038

        delta_bar = max_boost_bar - STOCK_BOOST_BAR
        if delta_bar <= 0.0:
            logger.info("Requested boost target not above stock; skipping boost patching")
            return {"success": True, "applied": False, "reason": "target not above stock"}

        boost_increase_psi = delta_bar * PSI_PER_BAR
        # Keep within a conservative safety envelope (roughly Stage 1-3)
        boost_increase_psi = max(2.0, min(15.0, boost_increase_psi))

        logger.info(
            "Applying boost from tuning preset: target %.2f bar (~%.1f psi), delta ~%.1f psi",
            max_boost_bar,
            max_boost_bar * PSI_PER_BAR,
            boost_increase_psi,
        )

        # Import lazily to avoid circular imports at module import time
        from . import boost_patcher

        # Detect software version and boost table definitions for CRC tracking
        sw_version, boost_tables = boost_patcher.get_boost_tables_for_bin(bytes(data))
        if not sw_version or not boost_tables:
            logger.warning(
                "BoostOptions enabled but no boost tables found for this binary; "
                "skipping boost modifications for safety",
            )
            return {
                "success": False,
                "applied": False,
                "reason": "no boost tables for software version",
                "software_version": sw_version,
                "modifications": [],
            }

        modifications: List[Tuple[int, int]] = []
        modified_tables: List[str] = []
        for table_name in ("WGDC_BASE", "LOAD_TARGET_MAIN", "BOOST_CEILING_MAP1", "BOOST_LIMIT_MULTIPLIER"):
            table = boost_tables.get(table_name)
            if not table:
                continue
            address = table["address"]
            size_bytes = int(table["rows"]) * int(table["cols"]) * 2
            modifications.append((address, size_bytes))
            modified_tables.append(table_name)

        if not modifications:
            logger.warning(
                "BoostOptions enabled but required boost tables were not present in definitions; "
                "skipping boost modifications",
            )
            return {
                "success": False,
                "applied": False,
                "reason": "required boost tables missing",
                "software_version": sw_version,
                "modifications": [],
            }

        # Apply Stage 1-style boost increase with the computed delta.
        modified = boost_patcher.increase_boost_stage1(bytes(data), boost_increase_psi=boost_increase_psi)
        data[:] = modified

        # Record what we did in metadata for traceability
        meta = patch_set.metadata.setdefault("boost_applied", {})
        meta.update(
            {
                "software_version": sw_version,
                "max_boost_bar": max_boost_bar,
                "boost_increase_psi": boost_increase_psi,
                "tables_modified": modified_tables,
            }
        )

        logger.info(
            "Boost modifications applied for %s; tables: %s",
            sw_version,
            ", ".join(modified_tables) or "(none)",
        )

        return {
            "success": True,
            "applied": True,
            "software_version": sw_version,
            "max_boost_bar": max_boost_bar,
            "boost_increase_psi": boost_increase_psi,
            "modifications": modifications,
        }
    
    def _validate_patch(self, data: bytes, patch: MapPatch) -> Dict[str, Any]:
        """Validate a patch before applying"""
        errors = []
        warnings = []
        
        # Check offset bounds
        if patch.offset + patch.size > len(data):
            errors.append(f"Patch exceeds flash size: 0x{patch.offset + patch.size:08X} > 0x{len(data):08X}")
        
        # Check for forbidden regions (format: (start, end, name))
        for forbidden in validated_maps.FORBIDDEN_REGIONS:
            start, end, name = forbidden
            if (patch.offset < end and patch.offset + patch.size > start):
                errors.append(f"Patch overlaps FORBIDDEN region: {name}")
        
        # Check for boot code region
        if patch.offset < 0x8000:
            errors.append("Patch in boot code region (0x0000-0x7FFF) - WILL BRICK ECU")
        
        # Check for flash counter region
        if patch.offset >= 0x1F0000 and patch.offset < 0x200000:
            warnings.append("Patch in flash counter region - may cause flash counter issues")
        
        # Check for all-zero or all-FF data (suspicious)
        if all(b == 0x00 for b in patch.data):
            warnings.append("Patch data is all zeros - may be incorrect")
        if all(b == 0xFF for b in patch.data):
            warnings.append("Patch data is all 0xFF - may be incorrect")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def create_vmax_patch(self, limit_kmh: int, name: str = "VMAX Limit") -> MapPatch:
        """Create patch to set speed limiter to a specific value."""
        vmax_data = struct.pack('>H', int(limit_kmh))  # Big-endian uint16

        return MapPatch(
            name=name,
            offset=map_offsets.VMAX_OFFSETS[0].start,  # Primary VMAX scalar
            size=2,
            data=vmax_data,
            description=f"Set speed limiter to {limit_kmh} km/h",
            category="vmax",
        )

    def create_vmax_removal_patch(self, name: str = "VMAX Removal") -> MapPatch:
        """Create patch to remove/raise speed limiter to delete value."""
        return self.create_vmax_patch(map_offsets.VMAX_DELETE_VALUE, name=name)
    
    def create_rpm_limiter_patch(self, rpm_limit: int = 7200, name: str = "RPM Limit Increase",
                                    transmission: str = "both") -> PatchSet:
        """
        Create patch set to increase RPM limiter using Corbanistan XDF-validated offsets.
        
        The N54 has gear-based rev limit tables:
        - 9 gear positions (P, R, N, 1, 2, 3, 4, 5, 6)
        - Separate floor (soft) and ceiling (hard) limits
        - Different tables for AT, MT, and AT Manual Mode
        
        Args:
            rpm_limit: Target RPM limit (default 7200, max recommended 7500)
            name: Patch set name
            transmission: "at", "mt", or "both" (default)
        
        Returns:
            PatchSet with all applicable RPM limiter patches
        """
        patch_set = PatchSet(
            name=name,
            description=f"Increase RPM limit to {rpm_limit}",
            metadata={'rpm_limit': rpm_limit, 'transmission': transmission}
        )
        
        # Select which tables to patch based on transmission type
        tables_to_patch = []
        for offset_range in map_offsets.RPM_LIMITER_OFFSETS:
            desc = offset_range.description.lower()
            
            # Skip axis tables - these are breakpoints, not limits
            if "axis" in desc or "gear axis" in desc:
                continue
                
            # Skip time tables - these control fuel cut intervals, not RPM limits
            if "time between" in desc:
                continue
            
            # Filter by transmission type
            if transmission == "both":
                tables_to_patch.append(offset_range)
            elif transmission == "at" and ("(at)" in desc or "manual mode" in desc):
                tables_to_patch.append(offset_range)
            elif transmission == "mt" and "(mt)" in desc:
                tables_to_patch.append(offset_range)
        
        # Apply patches to selected tables
        for i, offset_range in enumerate(tables_to_patch):
            desc = offset_range.description.lower()
            size = offset_range.size
            
            # Generate patch data based on table type and size
            if "clutch" in desc:
                # Clutch-pressed RPM table: 8 x 16-bit = 16 bytes
                num_values = size // 2
                patch_data = struct.pack(f'>{num_values}H', *([rpm_limit] * num_values))
            elif size == 18:
                # 9-gear table: 9 x 16-bit = 18 bytes
                patch_data = struct.pack('>9H', *([rpm_limit] * 9))
            else:
                # Fallback: create appropriate size with RPM value
                num_values = size // 2
                if num_values > 0:
                    patch_data = struct.pack(f'>{num_values}H', *([rpm_limit] * num_values))
                else:
                    # Single byte value (unlikely for RPM)
                    patch_data = bytes([min(255, rpm_limit // 100)] * size)
            
            patch = MapPatch(
                name=f"RPM_Limiter_{i+1}",
                offset=offset_range.start,
                size=offset_range.size,
                data=patch_data,
                description=offset_range.description,
                category="rpm"
            )
            patch_set.add_patch(patch)
        
        return patch_set
    
    def create_burbles_patch(self, name: str = "Burbles/Pops Enable") -> PatchSet:
        """Create patch set to enable burbles/pops"""
        patch_set = PatchSet(
            name=name,
            description="Enable aggressive burbles/pops on deceleration",
            metadata={'feature': 'burbles'}
        )
        
        # Apply all burbles reference data
        for offset, ref_data in map_offsets.BURBLES_REFERENCE_DATA.items():
            # Find the corresponding offset range for description
            desc = "Burbles data"
            for timing_table in map_offsets.BURBLES_TIMING_TABLES:
                if timing_table.start == offset:
                    desc = timing_table.description
                    break
            for timing_map in map_offsets.BURBLES_TIMING_MAPS:
                if timing_map.start == offset:
                    desc = timing_map.description
                    break
            
            patch = MapPatch(
                name=f"Burbles_0x{offset:08X}",
                offset=offset,
                size=len(ref_data),
                data=ref_data,
                description=desc,
                category="burbles"
            )
            patch_set.add_patch(patch)
        
        return patch_set
    
    def create_dtc_disable_patch(self, name: str = "DTC Disable") -> PatchSet:
        """Create patch set to disable common DTC codes"""
        patch_set = PatchSet(
            name=name,
            description="Disable catalyst and O2 sensor DTCs",
            metadata={'feature': 'dtc_disable'}
        )
        
        # Catalyst DTC disable
        for offset, value in map_offsets.CATALYST_DTC_DISABLE.items():
            patch = MapPatch(
                name=f"CAT_DTC_0x{offset:08X}",
                offset=offset,
                size=1,
                data=bytes([value]),
                description="Disable catalyst DTC",
                category="dtc"
            )
            patch_set.add_patch(patch)
        
        # O2 sensor DTC disable
        for offset, value in map_offsets.O2_SENSOR_DTC_DISABLE.items():
            patch = MapPatch(
                name=f"O2_DTC_0x{offset:08X}",
                offset=offset,
                size=1,
                data=bytes([value]),
                description="Disable O2 sensor DTC",
                category="dtc"
            )
            patch_set.add_patch(patch)
        
        return patch_set

    def create_restore_to_stock_patchset(
        self,
        stock_data: bytes,
        features: Optional[List[str]] = None,
        name: str = "Restore Selected Calibrations to Stock"
    ) -> PatchSet:
        """Create a patch set that restores selected calibrations to stock.

        Args:
            stock_data: Reference binary (known-good stock) as bytes
            features: List of feature groups to restore. Supported:
                      ["vmax", "rpm", "burbles", "dtc", "wgdc"]
            name: Optional name for the patch set

        Returns:
            PatchSet that, when applied, copies stock bytes for the selected
            calibration regions into the target binary.
        """
        if features is None:
            features = ["vmax", "rpm", "burbles", "dtc", "wgdc"]

        patch_set = PatchSet(
            name=name,
            description="Restore previously changed settings to original values using stock reference",
            metadata={
                'features': features,
                'mode': 'restore_to_stock'
            }
        )

        def _add_patch(offset: int, size: int, desc: str, category: str):
            # Bounds check defensively
            if offset + size > len(stock_data):
                logger.warning(f"Stock reference too small for {category} @0x{offset:08X} size {size}")
                return
            data_slice = stock_data[offset:offset + size]
            patch = MapPatch(
                name=f"Restore_{category}_0x{offset:08X}",
                offset=offset,
                size=size,
                data=data_slice,
                description=f"Restore {desc}",
                category=category
            )
            patch_set.add_patch(patch)

        # VMAX (speed limiter scalars)
        if "vmax" in features:
            try:
                for rng in map_offsets.VMAX_OFFSETS:
                    size = 2  # uint16 scaler
                    desc = getattr(rng, 'description', 'VMAX')
                    _add_patch(rng.start, size, desc, "vmax")
            except Exception as e:
                logger.warning(f"VMAX restore skipped: {e}")

        # RPM limiters (soft/hard and per-gear entries)
        if "rpm" in features:
            try:
                for rng in map_offsets.RPM_LIMITER_OFFSETS:
                    size = 2  # uint16 scaler
                    desc = getattr(rng, 'description', 'RPM limiter')
                    _add_patch(rng.start, size, desc, "rpm")
            except Exception as e:
                logger.warning(f"RPM restore skipped: {e}")

        # Burbles (timing tables/maps cluster; use reference mapping sizes)
        if "burbles" in features:
            try:
                for offset, ref_data in map_offsets.BURBLES_REFERENCE_DATA.items():
                    size = len(ref_data)
                    _add_patch(offset, size, "Burbles data", "burbles")
            except Exception as e:
                logger.warning(f"Burbles restore skipped: {e}")

        # DTC masks/behavior bytes (cat/O2 families we toggle)
        if "dtc" in features:
            try:
                for offset in list(map_offsets.CATALYST_DTC_DISABLE.keys()):
                    _add_patch(offset, 1, "Catalyst DTC behavior", "dtc")
                for offset in list(map_offsets.O2_SENSOR_DTC_DISABLE.keys()):
                    _add_patch(offset, 1, "O2 sensor DTC behavior", "dtc")
            except Exception as e:
                logger.warning(f"DTC restore skipped: {e}")

        # WGDC/boost maps - use validated map definitions to avoid forbidden regions
        if "wgdc" in features:
            try:
                wgdc_maps = validated_maps.get_maps_by_category(validated_maps.MapCategory.WGDC)
                for m in wgdc_maps:
                    _add_patch(m.offset, m.size_bytes, "WGDC map", "boost")
            except Exception as e:
                logger.warning(f"WGDC restore skipped: {e}")

        logger.info(f"Created restore-to-stock patch set with {len(patch_set)} patches for features: {features}")
        return patch_set
    

    def create_patchset_from_preset(
        self,
        preset: "tuning_parameters.TuningPreset",
        name: str = "Tuning Preset",
        description: str = "Applied from TuningPreset configuration",
    ) -> PatchSet:
        """Build a PatchSet from a TuningPreset (canonical model).

        Args:
            preset: TuningPreset instance (from ALL_PRESETS or get_preset)
            name: PatchSet name
            description: PatchSet description

        Returns:
            PatchSet with all relevant patches for the preset
        """
        values = getattr(preset, "values", preset)
        # Defensive: allow passing a dict of values
        if not isinstance(values, dict):
            raise PatchError("TuningPreset must have a .values dict")

        patch_set = PatchSet(
            name=name,
            description=description,
            metadata={
                "source": "TuningPreset",
                "preset_name": getattr(preset, "name", name),
                "values": values,
            },
        )

        # VMAX / speed limiter
        vmax = values.get("vmax", {})
        if vmax.get("enabled"):
            limit = int(vmax.get("limit_kmh", map_offsets.VMAX_DELETE_VALUE))
            vmax_patch = self.create_vmax_patch(limit, name=f"VMAX_{limit}kmh")
            patch_set.add_patch(vmax_patch)
            logger.info(f"Added VMAX patch for {limit} km/h")

        # RPM limiter
        rev_limiter = values.get("rev_limiter", {})
        if rev_limiter.get("enabled"):
            rpm_limit = int(rev_limiter.get("hard_limit", map_offsets.RPM_STOCK_HARD_LIMIT))
            rpm_patches = self.create_rpm_limiter_patch(rpm_limit, name=f"RPM_{rpm_limit}")
            for p in rpm_patches.patches:
                patch_set.add_patch(p)
            logger.info(f"Added RPM limiter patch set for {rpm_limit} RPM")

        # Burbles / pops
        burbles = values.get("burbles", {})
        if burbles.get("enabled"):
            burble_ps = self.create_burbles_patch(name="Burbles_Enable")
            for p in burble_ps.patches:
                patch_set.add_patch(p)
            logger.info("Added burbles patch set from reference data")

        # DTC disable
        dtc = values.get("dtc", {})
        if dtc.get("disable_cat_codes") or dtc.get("disable_o2_codes"):
            dtc_ps = self.create_dtc_disable_patch(name="DTC_Disable_Cat_O2")
            for p in dtc_ps.patches:
                patch_set.add_patch(p)
            logger.info("Added DTC disable patch set (catalyst/O2)")

        # Launch control and boost handling (metadata only)
        launch_control = values.get("launch_control", {})
        if launch_control.get("enabled"):
            patch_set.metadata["launch_control_note"] = (
                "Launch control enabled in configuration, but launch-control "
                "offsets are still BLOCKED / TBD; no binary patches applied."
            )
            logger.warning("Launch control options enabled but offsets are not yet mapped; skipping patches")

        boost = values.get("boost", {})
        if boost.get("enabled"):
            patch_set.metadata["boost_note"] = (
                "Boost configuration enabled; concrete boost table changes "
                "will be applied via boost_patcher when this PatchSet is "
                "applied to a binary file."
            )
            logger.info("Boost options enabled; boost_patcher will be used during file patching")

        return patch_set
    
    def save_patch_set(self, patch_set: PatchSet, filepath: Path) -> None:
        """Save a patch set to JSON file"""
        data = {
            'name': patch_set.name,
            'description': patch_set.description,
            'created': patch_set.created,
            'metadata': patch_set.metadata,
            'patches': [
                {
                    'name': p.name,
                    'offset': p.offset,
                    'size': p.size,
                    'data': p.data.hex(),
                    'description': p.description,
                    'category': p.category,
                    'validate': p.validate
                }
                for p in patch_set.patches
            ]
        }
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved patch set '{patch_set.name}' to {filepath}")
    
    def load_patch_set(self, filepath: Path) -> PatchSet:
        """Load a patch set from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        patch_set = PatchSet(
            name=data['name'],
            description=data['description'],
            metadata=data.get('metadata', {}),
            created=data.get('created', datetime.now().isoformat())
        )
        
        for p in data['patches']:
            patch = MapPatch(
                name=p['name'],
                offset=p['offset'],
                size=p['size'],
                data=bytes.fromhex(p['data']),
                description=p.get('description', ''),
                category=p.get('category', 'custom'),
                validate=p.get('validate', True)
            )
            patch_set.add_patch(patch)
        
        logger.info(f"Loaded patch set '{patch_set.name}' from {filepath} ({len(patch_set)} patches)")
        return patch_set


# ============================================================================
# Convenience Functions
# ============================================================================

def apply_patches_to_file(input_file: Path, output_file: Path, patch_set: PatchSet, 
                          ecu_type: str = "MSD81") -> Dict[str, Any]:
    """
    Apply patches to a binary file and save result.
    
    Args:
        input_file: Input flash file
        output_file: Output flash file
        patch_set: Patches to apply
        ecu_type: ECU type
        
    Returns:
        Results dict
    """
    logger.info(f"Applying patches: {input_file} -> {output_file}")
    
    # Read input
    data = bytearray(input_file.read_bytes())

    patcher = MapPatcher(ecu_type)

    # First, apply any boost-related changes driven by tuning preset metadata.
    boost_result: Dict[str, Any] = {}
    boost_modifications: List[Tuple[int, int]] = []
    try:
        boost_result = patcher.apply_boost_from_patchset(data, patch_set)
        boost_modifications = boost_result.get("modifications", []) or []
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(f"Boost application failed: {exc}")
        boost_result = {"success": False, "error": str(exc), "applied": False}

    # Apply the explicit MapPatch entries without updating CRCs yet so we can
    # recalculate in a single pass for both MapPatch and boost changes.
    results = patcher.apply_patch_set(data, patch_set, update_crcs=False)

    # Collect all modified ranges for CRC updates.
    patch_modifications: List[Tuple[int, int]] = [
        (p.offset, p.size) for p in patch_set.patches
    ]
    all_modifications = patch_modifications + boost_modifications

    if all_modifications:
        updated_count = crc_zones.update_all_affected_crcs(data, all_modifications, ecu_type)
        results["updated_crc_count"] = updated_count
    else:
        results["updated_crc_count"] = 0

    if boost_result:
        results["boost"] = boost_result

    # Save output
    output_file.write_bytes(data)
    logger.info(f"✓ Saved patched file: {output_file}")
    
    results['input_file'] = str(input_file)
    results['output_file'] = str(output_file)
    
    return results


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("="*80)
    print("BMW N54 Map Patcher - Examples")
    print("="*80)

    patcher = MapPatcher("MSD81")

    # Example 1: Create Stage 1 preset using canonical system
    print("\n1. Creating Stage 1 preset (canonical system)...")
    from flash_tool.tuning_parameters import get_preset
    preset = get_preset("stage1")
    if preset is not None:
        stage1 = patcher.create_patchset_from_preset(preset, name="stage1", description="Stage 1 preset (canonical)")
        print(f"   {stage1}")
        print(f"   Patches: {len(stage1)} total")
        for patch in stage1.patches[:3]:  # Show first 3
            print(f"     - {patch}")
    else:
        print("   Failed to load stage1 preset from canonical system.")

    # Example 2: Create burbles patch set
    print("\n2. Creating burbles patch set...")
    burbles = patcher.create_burbles_patch()
    print(f"   {burbles}")
    print(f"   Patches: {len(burbles)} total")

    # Example 3: Save preset to file
    print("\n3. Saving preset to file...")
    preset_dir = Path(__file__).parent.parent / 'presets'
    preset_file = preset_dir / 'stage1_conservative.json'
    patcher.save_patch_set(stage1, preset_file)
    print(f"   Saved: {preset_file}")

    print("\n" + "="*80)
    print("✓ Examples complete!")
    print("\nTo apply patches:")
    print("  from flash_tool.map_patcher import apply_patches_to_file")
    print("  results = apply_patches_to_file(input_bin, output_bin, stage1)")
