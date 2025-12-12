#!/usr/bin/env python3
"""
BMW Map Manager - ECU Map File Management and Validation
========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Handles browsing, validation, and metadata extraction for ECU map files.
    Organizes maps by VIN with separate backup and tuned subdirectories.
    Provides file size validation and integrity checking for MSD80/MSD81.

Directory Structure:
    maps/
    ├── <VIN>/
    │   ├── backup_<timestamp>.bin
    │   └── tuned/<name>.bin

Classes:
    MapValidationError(Exception) - Map file validation errors
    MapManager - Main map file manager

Functions:
    None (class-based module)

Variables (Module-level):
    logger: logging.Logger - Module logger
    DEFAULT_MAPS_DIR: Path - Default maps directory
    EXPECTED_SIZES: Dict[str, int] - Expected file sizes by ECU type
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Default maps directory structure: maps/<VIN>/backup_<timestamp>.bin
#                                   maps/<VIN>/tuned/<name>.bin
DEFAULT_MAPS_DIR = Path(__file__).parent.parent / "maps"

# Expected canonical file sizes for MSD80/MSD81
# Use 1MB and 2MB as the canonical full-flash sizes discovered in repo heuristics
EXPECTED_SIZES = {
    'MSD80': 0x100000,  # 1 MB
    'MSD81': 0x200000,  # 2 MB
}

# Try to import BMW checksum utilities implemented in `bmw_checksum.py`.
# Use absolute import when running as a package, fall back to relative import
# when executed as a script.
try:
    from flash_tool.bmw_checksum import (
        calculate_crc16,
        calculate_crc32,
        calculate_zone_checksums,
    )
except Exception:
    try:
        from .bmw_checksum import (
            calculate_crc16,
            calculate_crc32,
            calculate_zone_checksums,
        )
    except Exception:
        calculate_crc16 = None
        calculate_crc32 = None
        calculate_zone_checksums = None
        logger.warning("bmw_checksum utilities not importable; checksum features disabled")

# Try to import crc_zones (preferred canonical, zone-aware helpers)
try:
    from flash_tool.crc_zones import (
        get_zones_for_ecu,
        verify_all_crcs,
        calculate_zone_crc,
        update_zone_crc,
        update_all_affected_crcs,
        find_affected_zones,
        CRCZone,
    )
except Exception:
    try:
        from .crc_zones import (
            get_zones_for_ecu,
            verify_all_crcs,
            calculate_zone_crc,
            update_zone_crc,
            update_all_affected_crcs,
            find_affected_zones,
            CRCZone,
        )
    except Exception:
        # Keep names defined so callers can test availability
        get_zones_for_ecu = None
        verify_all_crcs = None
        calculate_zone_crc = None
        update_zone_crc = None
        update_all_affected_crcs = None
        find_affected_zones = None
        CRCZone = None
        logger.warning("crc_zones utilities not importable; zone-aware checksum features disabled")

class MapValidationError(Exception):
    """Raised when map validation fails"""
    pass


class MapManager:
    """
    Manages ECU map files with VIN-based organization.
    """
    
    def __init__(self, maps_dir: Optional[Path] = None):
        """
        Initialize MapManager.
        
        Args:
            maps_dir: Custom maps directory (uses default if None)
        """
        self.maps_dir = Path(maps_dir) if maps_dir else DEFAULT_MAPS_DIR
        self.maps_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"MapManager initialized: {self.maps_dir}")
    
    def list_available_maps(self, vin: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all .bin files in maps directory.
        
        Args:
            vin: Filter by specific VIN (lists all if None)
            
        Returns:
            List of map file metadata dictionaries
            
        Example:
            >>> mgr = MapManager()
            >>> maps = mgr.list_available_maps()
            >>> for m in maps:
            ...     print(f"{m['name']}: {m['size']} bytes")
        """
        logger.info(f"Listing available maps (VIN filter: {vin or 'All'})...")
        
        maps = []
        search_dir = self.maps_dir / vin if vin else self.maps_dir
        
        if not search_dir.exists():
            logger.warning(f"Maps directory does not exist: {search_dir}")
            return []
        
        # Recursively find all .bin files
        for bin_file in search_dir.rglob('*.bin'):
            try:
                metadata = self.get_map_metadata(bin_file)
                maps.append(metadata)
            except Exception as e:
                logger.warning(f"Skipping {bin_file.name}: {e}")
        
        logger.info(f"Found {len(maps)} map files")
        return maps
    
    def select_map_interactive(self) -> Optional[Path]:
        """
        Display numbered list of maps for user selection.
        
        Returns:
            Path to selected map file or None if cancelled
            
        Example:
            >>> mgr = MapManager()
            >>> selected = mgr.select_map_interactive()
            >>> if selected:
            ...     print(f"Selected: {selected}")
        """
        maps = self.list_available_maps()
        
        if not maps:
            print("\nNo map files found.")
            print(f"Place .bin files in: {self.maps_dir}")
            return None
        
        print("\n=== Available Map Files ===")
        print(f"{'#':<3} {'Filename':<40} {'Size':<12} {'Modified'}")
        print("="*80)
        
        for idx, map_info in enumerate(maps, 1):
            size_kb = map_info['size'] / 1024
            modified = map_info['modified'].strftime('%Y-%m-%d %H:%M')
            filename = map_info['name'][:38] + ".." if len(map_info['name']) > 40 else map_info['name']
            print(f"{idx:<3} {filename:<40} {size_kb:>8.1f} KB  {modified}")
        
        print("\nOptions:")
        print("  - Enter number (1-{}) to select map".format(len(maps)))
        print("  - Enter 'C' for custom file path")
        print("  - Enter 'Q' to cancel")
        
        while True:
            choice = input("\nYour choice: ").strip().upper()
            
            if choice == 'Q':
                return None
            elif choice == 'C':
                custom_path = input("Enter full path to .bin file: ").strip()
                custom_path = Path(custom_path)
                if custom_path.exists() and custom_path.suffix.lower() == '.bin':
                    return custom_path
                else:
                    print("Invalid file path or not a .bin file.")
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(maps):
                        return Path(maps[idx]['path'])
                    else:
                        print(f"Please enter a number between 1 and {len(maps)}.")
                except ValueError:
                    print("Invalid input.")
    
    def validate_map_file(self, file_path: Union[Path, str]) -> Tuple[bool, List[str]]:
        """
        Validate map file format and integrity.
        
        Args:
            file_path: Path to .bin file (can be string or Path object)
            
        Returns:
            Tuple of (is_valid: bool, issues: List[str])
            
        Example:
            >>> valid, issues = mgr.validate_map_file(Path("map.bin"))
            >>> if not valid:
            ...     print(f"Issues: {issues}")
        """
        # Convert string to Path if needed
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        
        logger.info(f"Validating map file: {file_path}")
        issues = []
        
        # Check file exists
        if not file_path.exists():
            issues.append("File does not exist")
            return False, issues
        
        # Check file is readable
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            issues.append(f"Cannot read file: {e}")
            return False, issues
        
        file_size = len(data)
        
        # Check file size
        valid_sizes = list(EXPECTED_SIZES.values())
        if file_size not in valid_sizes:
            issues.append(
                f"Unexpected file size: {file_size} bytes. "
                f"Expected {' or '.join(str(s) for s in valid_sizes)}"
            )
        
        # Check for obvious corruption markers
        if len(set(data)) < 10:
            issues.append("File appears to contain only repetitive data (possibly corrupted)")

        # Zone-aware checksum verification: prefer canonical `crc_zones` helpers
        ecu_type = 'MSD81' if file_size >= EXPECTED_SIZES.get('MSD81', 0x200000) else 'MSD80'

        if verify_all_crcs is not None and get_zones_for_ecu is not None:
            try:
                results = verify_all_crcs(data, ecu_type)
                zones_def = get_zones_for_ecu(ecu_type)

                for zone in zones_def:
                    valid = results.get(zone.name, False)
                    if not valid:
                        # Try to calculate and read stored CRC for reporting
                        try:
                            calc = calculate_zone_crc(data, zone) if calculate_zone_crc else None
                        except Exception:
                            calc = None

                        try:
                            if zone.crc_type == 'CRC16':
                                stored = int.from_bytes(data[zone.crc_offset:zone.crc_offset+2], 'little')
                                if calc is not None:
                                    issues.append(f"Checksum mismatch in {zone.name}: calculated 0x{calc:04X}, stored 0x{stored:04X}")
                                else:
                                    issues.append(f"Checksum mismatch in {zone.name}: stored 0x{stored:04X}")
                            elif zone.crc_type == 'CRC32':
                                stored = int.from_bytes(data[zone.crc_offset:zone.crc_offset+4], 'little')
                                if calc is not None:
                                    issues.append(f"Checksum mismatch in {zone.name}: calculated 0x{calc:08X}, stored 0x{stored:08X}")
                                else:
                                    issues.append(f"Checksum mismatch in {zone.name}: stored 0x{stored:08X}")
                            else:
                                issues.append(f"Checksum mismatch in {zone.name}: unknown CRC type")
                        except Exception:
                            issues.append(f"Checksum mismatch in {zone.name}: unable to read stored CRC")

            except Exception as e:
                logger.warning(f"crc_zones verification failed: {e}")
                issues.append("WARNING: Zone-aware checksum validation failed (crc_zones)")

        else:
            # Fallback to the legacy MapValidator-based verification when crc_zones
            # helpers are not available. This preserves previous behavior.
            try:
                try:
                    # Package import when running as package
                    from flash_tool.map_validator import MapValidator
                except Exception:
                    # Relative import when running as script
                    from .map_validator import MapValidator

                try:
                    validator = MapValidator(file_path)
                    try:
                        zone_results = validator.validate_bmw_zones('MSD80' if validator.file_size in (0x100000, 0x200000) else 'MSD80')
                    except Exception:
                        zone_results = validator.validate_all_regions()

                    if isinstance(zone_results, dict):
                        if 'zones' in zone_results:
                            for z in zone_results['zones']:
                                if not z.get('valid'):
                                    calc = z.get('calculated')
                                    stored = z.get('stored')
                                    issues.append(
                                        f"Checksum mismatch in {z.get('zone_name')}: calculated 0x{calc:04X}, stored 0x{stored:04X}"
                                    )
                        if 'crc16_regions' in zone_results:
                            for r in zone_results['crc16_regions']:
                                if not r.get('valid'):
                                    calc = r.get('calculated')
                                    stored = r.get('stored')
                                    start, end = r.get('region', (None, None))
                                    issues.append(
                                        f"Checksum mismatch in region 0x{start:06X}-0x{end:06X}: calculated 0x{calc:04X}, stored 0x{stored:04X}"
                                    )

                except Exception as e:
                    logger.warning(f"Zone-aware checksum validation failed: {e}")
                    issues.append("WARNING: Zone-aware checksum validation failed")

            except Exception:
                logger.warning("map_validator not available; skipping zone-aware checksum verification")
                issues.append("WARNING: Zone-aware checksum verification not available")
        
        is_valid = len([i for i in issues if not i.startswith('WARNING')]) == 0
        
        if is_valid:
            logger.info("Map file basic validation passed (checksums not verified)")
        else:
            logger.warning(f"Map file validation failed: {len(issues)} issues")
        
        return is_valid, issues
    
    def get_map_metadata(self, file_path: Union[Path, str]) -> Dict[str, Any]:
        """
        Extract metadata from map file.
        
        Args:
            file_path: Path to .bin file (can be string or Path object)
            
        Returns:
            Dictionary with metadata (size, checksums, date, etc.)
            
        Example:
            >>> metadata = mgr.get_map_metadata(Path("map.bin"))
            >>> print(f"MD5: {metadata['md5']}")
        """
        # Convert string to Path if needed
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        
        logger.info(f"Reading metadata from: {file_path}")
        
        stat = file_path.stat()
        
        # Calculate checksums and zone summaries when available
        with open(file_path, 'rb') as f:
            data = f.read()
            md5 = hashlib.md5(data).hexdigest()
            sha256 = hashlib.sha256(data).hexdigest()

            try:
                crc16 = calculate_crc16(data) if calculate_crc16 else None
            except Exception:
                crc16 = None

            try:
                crc32 = calculate_crc32(data) if calculate_crc32 else None
            except Exception:
                crc32 = None

            # Zone summaries (MSD80/MSD81) using canonical crc_zones when available
            try:
                guessed_type = 'MSD81' if len(data) >= EXPECTED_SIZES.get('MSD81', 0x200000) else 'MSD80'

                if get_zones_for_ecu is not None and calculate_zone_crc is not None:
                    zones_raw = get_zones_for_ecu(guessed_type)
                    zones = []
                    for z in zones_raw:
                        try:
                            calc = calculate_zone_crc(data, z)
                            if z.crc_type == 'CRC16':
                                stored = int.from_bytes(data[z.crc_offset:z.crc_offset+2], 'little')
                                valid = (calc == stored)
                                zones.append({
                                    'zone_name': z.name,
                                    'start': z.start_offset,
                                    'end': z.end_offset,
                                    'crc_type': z.crc_type,
                                    'calculated': calc,
                                    'stored': stored,
                                    'valid': valid,
                                })
                            else:
                                stored = int.from_bytes(data[z.crc_offset:z.crc_offset+4], 'little')
                                valid = (calc == stored)
                                zones.append({
                                    'zone_name': z.name,
                                    'start': z.start_offset,
                                    'end': z.end_offset,
                                    'crc_type': z.crc_type,
                                    'calculated': calc,
                                    'stored': stored,
                                    'valid': valid,
                                })
                        except Exception as e:
                            zones.append({'zone_name': z.name, 'error': str(e)})

                elif calculate_zone_checksums:
                    guessed_type = 'MSD81' if len(data) >= 0x200000 else 'MSD80'
                    zones = calculate_zone_checksums(data, ecu_type=guessed_type)
                else:
                    zones = None
            except Exception:
                zones = None
        
        # Try to extract embedded version/calibration ID
        # Format varies by ECU, this is placeholder logic
        version = "Unknown"
        calibration_id = "Unknown"
        
        # BLOCKED: Full metadata extraction requires reverse engineering
        # MSD80 map structure is not publicly documented
        
        metadata = {
            'path': str(file_path),
            'name': file_path.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'md5': md5,
            'sha256': sha256,
            'crc16': f"0x{crc16:04X}" if (crc16 is not None) else None,
            'crc32': f"0x{crc32:08X}" if (crc32 is not None) else None,
            'zones': zones,
            'version': version,
            'calibration_id': calibration_id
        }
        
        logger.info(f"Metadata extracted: {file_path.name} ({stat.st_size} bytes)")
        return metadata
    
    def compare_maps(self, file1: Union[Path, str], file2: Union[Path, str]) -> Dict[str, Any]:
        """
        Compare two map files and show differences.
        
        Args (can be strings or Path objects):
            file1: First map file
            file2: Second map file
            
        Returns:
            Dictionary with comparison results
            
        Example:
            >>> diff = mgr.compare_maps(Path("stock.bin"), Path("tuned.bin"))
            >>> print(f"Difference: {diff['changed_bytes']} bytes")
        """
        # Convert strings to Path if needed
        if not isinstance(file1, Path):
            file1 = Path(file1)
        if not isinstance(file2, Path):
            file2 = Path(file2)
        
        logger.info(f"Comparing {file1.name} vs {file2.name}...")
        
        with open(file1, 'rb') as f:
            data1 = f.read()
        
        with open(file2, 'rb') as f:
            data2 = f.read()
        
        if len(data1) != len(data2):
            return {
                'identical': False,
                'error': 'Files have different sizes',
                'size1': len(data1),
                'size2': len(data2)
            }
        
        # Count changed bytes
        changed = sum(1 for a, b in zip(data1, data2) if a != b)
        changed_percent = (changed / len(data1)) * 100
        
        # Find changed regions
        regions = []
        in_region = False
        region_start = 0
        
        for i, (a, b) in enumerate(zip(data1, data2)):
            if a != b and not in_region:
                region_start = i
                in_region = True
            elif a == b and in_region:
                regions.append((region_start, i - 1))
                in_region = False
        
        if in_region:
            regions.append((region_start, len(data1) - 1))
        
        result = {
            'identical': changed == 0,
            'total_bytes': len(data1),
            'changed_bytes': changed,
            'changed_percent': changed_percent,
            'changed_regions': len(regions),
            'regions': regions[:10]  # First 10 regions
        }
        
        logger.info(f"Comparison: {changed_percent:.2f}% different ({changed}/{len(data1)} bytes)")
        return result
    
    def set_maps_directory(self, path: str) -> bool:
        """
        Configure custom maps directory location.
        
        Args:
            path: New maps directory path
            
        Returns:
            True if set successfully
            
        Example:
            >>> mgr.set_maps_directory("D:\\\\BMW_Maps")
        """
        try:
            new_dir = Path(path)
            new_dir.mkdir(parents=True, exist_ok=True)
            
            # Save to config
            config_file = Path(__file__).parent.parent / "config" / "map_directory.ini"
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w') as f:
                f.write(f"maps_directory={path}\n")
            
            self.maps_dir = new_dir
            logger.info(f"Maps directory set to: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set maps directory: {e}")
            return False


if __name__ == "__main__":
    """Test MapManager"""
    print("=== Map Manager Test ===\n")
    
    mgr = MapManager()
    print(f"Maps directory: {mgr.maps_dir}\n")
    
    # List available maps
    maps = mgr.list_available_maps()
    if maps:
        print(f"Found {len(maps)} map file(s):\n")
        for m in maps:
            print(f"  {m['name']}")
            print(f"    Size: {m['size']} bytes")
            print(f"    MD5: {m['md5']}")
            print()
    else:
        print("No map files found.")
        print(f"Place .bin files in: {mgr.maps_dir}")
