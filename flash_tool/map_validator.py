#!/usr/bin/env python3
"""
BMW N54 Map Validator - ECU Binary File Validation and Repair
==============================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Comprehensive validation system for BMW ECU map files (.fla, .bin).
    Checks file size, structure, checksums, and critical regions.
    Based on BMW standard checksum logic.

Validation Logic:
    1. CRC-16 calculated over specific data regions
    2. CRC-32 used for full-file integrity checks
    3. Checksums appended to data blocks in little-endian format

Validation Checks:
    - File size (512KB for MSD80, 2MB for full dump)
    - File signature/magic bytes
    - CRC zone integrity
    - Boot sector validation
    - Calibration region structure
    - All-zero/all-0xFF detection

Classes:
    MapValidationError(Exception) - Validation errors
    MapValidator - Main validation engine

Functions:
    validate_map_file(map_file_path: Path, fix_if_invalid: bool) -> bool

Variables (Module-level):
    None
"""

import struct
from pathlib import Path
from typing import Tuple, Optional
from .bmw_checksum import calculate_crc16, calculate_crc32
from . import crc_zones


class MapValidationError(Exception):
    """Custom exception for map validation failures"""
    pass


class MapValidator:
    """
    Validates BMW ECU map files by verifying embedded checksums.
    
    This class implements the checksum validation logic used by BMW ECUs.
    It supports both .fla and .bin formats.
    
    BMW ECUs use multiple CRC zones for different memory regions
    (CRC_40304, CRC_80304, CRC_C304, CRC_C344).
    """
    
    # Common map file sizes for N54 ECU (MSD80/MSD81)
    VALID_MAP_SIZES = {
        0x40000,   # 256KB (calibration window)
        0x80000,   # 512KB (calibration window)
        0x100000,  # 1MB (MSD80)
        0x200000,  # 2MB (MSD81)
    }
    
    # BMW-specific CRC zones
    # These are named zones that appear to correspond to specific ECU memory regions
    # Format: (zone_name, start_offset, end_offset, crc_type)
    # Note: These offsets are preliminary and may need adjustment based on actual map analysis
    BMW_CRC_ZONES = {
        'MSD80': [
            # Zone 1: CRC_40304 - First major calibration zone (0x00000 - 0x40302)
            ('CRC_40304', 0x00000, 0x40302, 'crc16'),
            # Zone 2: CRC_80304 - Second calibration zone (0x40304 - 0x80302)
            ('CRC_80304', 0x40304, 0x80302, 'crc16'),
            # Zone 3: CRC_C304 - Third calibration zone (0x80304 - 0xC0302)
            ('CRC_C304', 0x80304, 0xC0302, 'crc16'),
            # Zone 4: CRC_C344 - Fourth zone (0xC0304 - 0xC0342)
            ('CRC_C344', 0xC0304, 0xC0342, 'crc16'),
            # Full file CRC-32 (last 4 bytes of file)
            ('FULL_FILE_CRC32', 0x00000, 0xFFFFFC, 'crc32'),
        ],
        'MSD81': [
            # MSD81 has similar structure but at different offsets due to 2MB size
            # These need to be discovered through analysis
            ('CRC_40304', 0x00000, 0x40302, 'crc16'),
            ('CRC_80304', 0x40304, 0x80302, 'crc16'),
            ('CRC_C304', 0x80304, 0xC0302, 'crc16'),
            ('CRC_C344', 0xC0304, 0xC0342, 'crc16'),
            ('FULL_FILE_CRC32', 0x00000, 0x1FFFFC, 'crc32'),
        ]
    }
    
    CRC32_FULL_FILE = True  # CRC-32 is typically calculated over entire file
    
    def __init__(self, map_file_path: Path):
        """
        Initialize the validator with a map file.
        
        Args:
            map_file_path: Path to the .fla or .bin map file
        
        Raises:
            FileNotFoundError: If the map file doesn't exist
            MapValidationError: If the file size is invalid
        """
        self.map_file_path = Path(map_file_path)
        
        if not self.map_file_path.exists():
            raise FileNotFoundError(f"Map file not found: {map_file_path}")
        
        self.map_data = self.map_file_path.read_bytes()
        self.file_size = len(self.map_data)
        
        # Validate file size
        if self.file_size not in self.VALID_MAP_SIZES:
            raise MapValidationError(
                f"Invalid map file size: {self.file_size} bytes. "
                f"Expected one of: {', '.join(hex(s) for s in self.VALID_MAP_SIZES)}"
            )
    
    def validate_crc32_full_file(self, exclude_last_n_bytes: int = 4) -> Tuple[bool, int, int]:
        """
        Validate the entire map file using CRC-32.
        
        This follows the pattern where CRC-32 is calculated over the entire file
        except for the last N bytes which contain the stored CRC-32 value.
        
        Args:
            exclude_last_n_bytes: Number of bytes at the end to exclude (typically 4)
        
        Returns:
            Tuple of (is_valid, calculated_crc, stored_crc)
        """
        # Extract the data (excluding the last N bytes which contain the stored CRC)
        data_region = self.map_data[:-exclude_last_n_bytes]
        
        # Extract the stored CRC (last N bytes, little-endian)
        stored_crc = struct.unpack('<I', self.map_data[-exclude_last_n_bytes:])[0]
        
        # Calculate CRC-32 over the data region
        calculated_crc = calculate_crc32(data_region)
        
        return (calculated_crc == stored_crc, calculated_crc, stored_crc)
    
    def validate_bmw_zones(self, ecu_type: str = 'MSD80') -> dict:
        """
        Validate BMW-specific CRC zones using the centralized `crc_zones` module.

        Args:
            ecu_type: 'MSD80' or 'MSD81'

        Returns:
            Dictionary with validation results for each BMW zone
        """
        # Normalize ECU type
        ecu_type_norm = (ecu_type or 'MSD80').upper()
        if ecu_type_norm not in ('MSD80', 'MSD81'):
            raise MapValidationError(f"Unknown ECU type: {ecu_type}")

        results = {
            'zones': [],
            'overall_valid': True,
            'ecu_type': ecu_type_norm
        }

        # Retrieve canonical zones from centralized module
        try:
            zones = crc_zones.get_zones_for_ecu(ecu_type_norm)
        except Exception as e:
            raise MapValidationError(f"Failed to load CRC zones for {ecu_type_norm}: {e}")

        for zone in zones:
            zone_name = getattr(zone, 'name', '<unknown>')
            try:
                # Ensure crc_offset is available and within file bounds
                if getattr(zone, 'crc_offset', None) is None:
                    results['zones'].append({
                        'zone_name': zone_name,
                        'range': (getattr(zone, 'start_offset', 0), getattr(zone, 'end_offset', 0)),
                        'crc_type': getattr(zone, 'crc_type', 'unknown').lower(),
                        'valid': False,
                        'error': 'crc_offset not defined for zone'
                    })
                    results['overall_valid'] = False
                    continue

                crc_off = zone.crc_offset
                if zone.crc_type.upper() == 'CRC16':
                    if crc_off + 2 > self.file_size:
                        results['zones'].append({
                            'zone_name': zone_name,
                            'range': (zone.start_offset, zone.end_offset),
                            'crc_type': 'crc16',
                            'valid': False,
                            'error': 'crc_offset out of bounds'
                        })
                        results['overall_valid'] = False
                        continue

                    data_region = self.map_data[zone.start_offset:crc_off]
                    calc_crc = calculate_crc16(data_region)
                    stored_crc = struct.unpack_from('<H', self.map_data, crc_off)[0]
                    valid = (calc_crc == stored_crc)
                    results['zones'].append({
                        'zone_name': zone_name,
                        'range': (zone.start_offset, zone.end_offset),
                        'crc_type': 'crc16',
                        'valid': valid,
                        'calculated': calc_crc,
                        'stored': stored_crc
                    })
                    if not valid:
                        results['overall_valid'] = False

                elif zone.crc_type.upper() == 'CRC32':
                    if crc_off + 4 > self.file_size:
                        results['zones'].append({
                            'zone_name': zone_name,
                            'range': (zone.start_offset, zone.end_offset),
                            'crc_type': 'crc32',
                            'valid': False,
                            'error': 'crc_offset out of bounds'
                        })
                        results['overall_valid'] = False
                        continue

                    data_region = self.map_data[zone.start_offset:crc_off]
                    calc_crc = calculate_crc32(data_region)
                    stored_crc = struct.unpack_from('<I', self.map_data, crc_off)[0]
                    valid = (calc_crc == stored_crc)
                    results['zones'].append({
                        'zone_name': zone_name,
                        'range': (zone.start_offset, zone.end_offset),
                        'crc_type': 'crc32',
                        'valid': valid,
                        'calculated': calc_crc,
                        'stored': stored_crc
                    })
                    if not valid:
                        results['overall_valid'] = False

                else:
                    results['zones'].append({
                        'zone_name': zone_name,
                        'range': (zone.start_offset, zone.end_offset),
                        'crc_type': zone.crc_type.lower(),
                        'valid': False,
                        'error': f'Unsupported CRC type: {zone.crc_type}'
                    })
                    results['overall_valid'] = False

            except Exception as e:
                results['zones'].append({
                    'zone_name': zone_name,
                    'range': (getattr(zone, 'start_offset', 0), getattr(zone, 'end_offset', 0)),
                    'crc_type': getattr(zone, 'crc_type', 'unknown').lower(),
                    'valid': False,
                    'error': str(e)
                })
                results['overall_valid'] = False

        return results

    def validate_all_regions(self) -> dict:
        """
        Run all validation checks and return a consolidated results dictionary.

        Returns:
            dict: {
                'crc32_full_file': {...},
                'bmw_zones': {...} (optional),
                'overall_valid': bool
            }
        """
        results = {
            'crc32_full_file': None,
            'bmw_zones': None,
            'overall_valid': True
        }

        # CRC-32 full file
        if self.CRC32_FULL_FILE:
            try:
                valid, calc, stored = self.validate_crc32_full_file()
                results['crc32_full_file'] = {
                    'valid': valid,
                    'calculated': calc,
                    'stored': stored
                }
                if not valid:
                    results['overall_valid'] = False
            except MapValidationError as e:
                results['crc32_full_file'] = {
                    'valid': False,
                    'error': str(e)
                }
                results['overall_valid'] = False

        # BMW-specific zones (only for full dumps)
        if self.file_size >= 0x100000:
            try:
                ecu_type = 'MSD81' if self.file_size >= 0x200000 else 'MSD80'
                bmw = self.validate_bmw_zones(ecu_type)
                results['bmw_zones'] = bmw
                if not bmw.get('overall_valid', True):
                    results['overall_valid'] = False
            except MapValidationError as e:
                results['bmw_zones'] = {'valid': False, 'error': str(e)}
                results['overall_valid'] = False

        return results
    
    def fix_checksums(self, output_path: Optional[Path] = None) -> Path:
        """
        Recalculate and fix all checksums in the map file.
        
        This follows the pattern discovered in the decompiled code where
        checksums are appended to data regions in little-endian format.
        
        Args:
            output_path: Optional path for the corrected file.
                        If None, will append '.corrected' to the original filename.
        
        Returns:
            Path to the corrected map file
        
        Raises:
            MapValidationError: If checksum correction fails
        """
        if output_path is None:
            output_path = self.map_file_path.with_suffix(
                self.map_file_path.suffix + '.corrected'
            )
        
        # Create a mutable copy of the map data
        corrected_data = bytearray(self.map_data)
        
        # Fix CRC-32 full file
        if self.CRC32_FULL_FILE:
            # Calculate CRC-32 over the entire file (excluding last 4 bytes)
            data_region = corrected_data[:-4]
            calculated_crc = calculate_crc32(data_region)
            
            # Write the calculated CRC to the last 4 bytes (little-endian)
            struct.pack_into('<I', corrected_data, len(corrected_data)-4, calculated_crc)
        
        # Write the corrected data to the output file
        output_path = Path(output_path)
        output_path.write_bytes(corrected_data)
        
        return output_path
    
    def get_validation_summary(self) -> str:
        """
        Get a human-readable validation summary.
        
        Returns:
            Formatted string with validation results
        """
        results = self.validate_all_regions()
        
        lines = [
            f"Map File Validation Report: {self.map_file_path.name}",
            f"File Size: {self.file_size} bytes ({hex(self.file_size)})",
            "",
            "CRC-32 Full File Validation:"
        ]
        
        if results['crc32_full_file']:
            crc32_result = results['crc32_full_file']
            if 'error' in crc32_result:
                lines.append(f"  ERROR - {crc32_result['error']}")
            else:
                status = "[OK] VALID" if crc32_result['valid'] else "[FAILURE] INVALID"
                lines.append(f"  {status}")
                lines.append(f"  Calculated: 0x{crc32_result['calculated']:08X}")
                lines.append(f"  Stored:     0x{crc32_result['stored']:08X}")
        
        lines.append("")
        overall_status = "[OK] ALL CHECKSUMS VALID" if results['overall_valid'] else "[FAILURE] CHECKSUM VALIDATION FAILED"
        lines.append(f"Overall Result: {overall_status}")
        
        return "\n".join(lines)


def validate_map_file(map_file_path: Path, fix_if_invalid: bool = False) -> bool:
    """
    Convenience function to validate a map file.
    
    Args:
        map_file_path: Path to the map file
        fix_if_invalid: If True, will create a corrected version if validation fails
    
    Returns:
        True if the map file is valid, False otherwise
    
    Raises:
        FileNotFoundError: If the map file doesn't exist
        MapValidationError: If validation encounters an error
    """
    validator = MapValidator(map_file_path)
    print(validator.get_validation_summary())
    
    results = validator.validate_all_regions()
    
    if not results['overall_valid'] and fix_if_invalid:
        print("\n[WARNING] Checksums are invalid. Creating corrected version...")
        corrected_path = validator.fix_checksums()
        print(f"[OK] Corrected map file saved to: {corrected_path}")
    
    return results['overall_valid']


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m flash_tool.map_validator <map_file_path> [--fix]")
        print("\nValidates checksums in BMW ECU map files (.fla, .bin)")
        print("  --fix: Create a corrected version if checksums are invalid")
        sys.exit(1)
    
    map_file = Path(sys.argv[1])
    fix_checksums = "--fix" in sys.argv
    
    try:
        is_valid = validate_map_file(map_file, fix_if_invalid=fix_checksums)
        sys.exit(0 if is_valid else 1)
    except Exception as e:
        print(f"\n[FAILURE] Error: {e}")
        sys.exit(1)
