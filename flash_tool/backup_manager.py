#!/usr/bin/env python3
"""
BMW N54 Backup Manager - ECU Backup Management and Verification
================================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Manages ECU backup files with VIN-based organization, integrity
    verification, and metadata extraction. Implements comprehensive
    backup lifecycle management from creation through verification.

Backup File Naming Convention:
    Format: backup_YYYYMMDD_HHMMSS_VIN_ECUTYPE.bin
    Example: backup_20251101_143022_WBADT63452CX12345_MSD80.bin

Directory Structure:
    backups/
    ├── WBADT63452CX12345/          # VIN-based folders
    │   ├── backup_20251101_143022_WBADT63452CX12345_MSD80.bin
    │   └── backup_20251101_150000_WBADT63452CX12345_MSD80.bin
    └── WBAXYZ98765AB98765/
        └── backup_20251101_120000_WBAXYZ98765AB98765_MSD81.bin

Classes:
    BackupError(Exception) - Backup operation errors

Functions:
    get_backups_directory() -> Path
    ensure_backups_directory() -> Path
    ensure_vin_directory(vin: str) -> Path
    generate_backup_filename(vin: str, ecu_type: str) -> str
    parse_backup_filename(filename: str) -> Dict[str, str]
    calculate_checksum(data: bytes, algorithm: str) -> str
    verify_backup(backup_file: Path) -> Dict[str, Any]
    get_backup_info(backup_file: Path) -> Dict[str, Any]
    list_backups(vin: Optional[str], directory: Optional[Path]) -> List[Dict[str, Any]]
    get_latest_backup(vin: str, directory: Optional[Path]) -> Optional[Dict[str, Any]]
    format_backup_list(backups: List[Dict[str, Any]], detailed: bool) -> str

Variables (Module-level):
    logger: logging.Logger - Module logger
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import struct

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Raised when backup operation fails"""
    pass


def get_backups_directory() -> Path:
    """
    Get the default backups directory path.
    
    Returns:
        Path object pointing to backups/ directory
    """
    # Backups directory is at project root
    return Path(__file__).parent.parent / "backups"


def ensure_backups_directory() -> Path:
    """
    Ensure backups directory exists, create if necessary.
    
    Returns:
        Path to backups directory
    """
    backups_dir = get_backups_directory()
    backups_dir.mkdir(exist_ok=True)
    logger.info(f"Backups directory: {backups_dir}")
    return backups_dir


def ensure_vin_directory(vin: str) -> Path:
    """
    Ensure VIN-specific subdirectory exists.
    
    Args:
        vin: Vehicle Identification Number
    
    Returns:
        Path to VIN-specific directory
    
    Raises:
        ValueError: If VIN is empty or invalid
    """
    if not vin or len(vin) < 10:
        raise ValueError(f"Invalid VIN: {vin}")
    
    backups_dir = ensure_backups_directory()
    vin_dir = backups_dir / vin
    vin_dir.mkdir(exist_ok=True)
    logger.info(f"VIN directory: {vin_dir}")
    return vin_dir


def generate_backup_filename(vin: str, ecu_type: str = "MSD80") -> str:
    """
    Generate standardized backup filename with timestamp.
    
    Format: backup_YYYYMMDD_HHMMSS_VIN_ECUTYPE.bin
    
    Args:
        vin: Vehicle Identification Number
        ecu_type: ECU type (default: MSD80)
    
    Returns:
        Filename string
    
    Example:
        >>> generate_backup_filename("WBADT63452CX12345", "MSD80")
        'backup_20251101_143022_WBADT63452CX12345_MSD80.bin'
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}_{vin}_{ecu_type}.bin"
    logger.debug(f"Generated filename: {filename}")
    return filename


def parse_backup_filename(filename: str) -> Dict[str, str]:
    """
    Parse backup filename to extract metadata.
    
    Args:
        filename: Backup filename
    
    Returns:
        Dictionary with parsed metadata:
        {
            'timestamp': str,    # YYYYMMDD_HHMMSS
            'vin': str,          # Vehicle Identification Number
            'ecu_type': str,     # ECU type (MSD80, MSD81, etc.)
            'date': str,         # YYYY-MM-DD
            'time': str          # HH:MM:SS
        }
    
    Raises:
        ValueError: If filename doesn't match expected format
    
    Example:
        >>> info = parse_backup_filename("backup_20251101_143022_WBADT63452CX12345_MSD80.bin")
        >>> info['vin']
        'WBADT63452CX12345'
    """
    # Remove .bin extension if present
    base_name = filename.replace('.bin', '')
    
    # Expected format: backup_YYYYMMDD_HHMMSS_VIN_ECUTYPE
    parts = base_name.split('_')
    
    if len(parts) < 5 or parts[0] != 'backup':
        raise ValueError(f"Invalid backup filename format: {filename}")
    
    date_part = parts[1]  # YYYYMMDD
    time_part = parts[2]  # HHMMSS
    vin = parts[3]
    ecu_type = parts[4]
    
    # Format date and time
    try:
        formatted_date = f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
        formatted_time = f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
    except IndexError:
        raise ValueError(f"Invalid date/time format in filename: {filename}")
    
    return {
        'timestamp': f"{date_part}_{time_part}",
        'vin': vin,
        'ecu_type': ecu_type,
        'date': formatted_date,
        'time': formatted_time
    }


def calculate_checksum(data: bytes, algorithm: str = 'sha256') -> str:
    """
    Calculate checksum for binary data.
    
    Args:
        data: Binary data to checksum
        algorithm: Hash algorithm (sha256, md5, sha1)
    
    Returns:
        Hexadecimal checksum string
    
    Example:
        >>> with open('backup.bin', 'rb') as f:
        ...     data = f.read()
        >>> checksum = calculate_checksum(data)
        >>> print(checksum)
        'a1b2c3d4e5f6...'
    """
    if algorithm == 'sha256':
        hasher = hashlib.sha256()
    elif algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    hasher.update(data)
    checksum = hasher.hexdigest()
    logger.debug(f"Calculated {algorithm} checksum: {checksum[:16]}...")
    return checksum


def verify_backup(backup_file: Path) -> Dict[str, Any]:
    """
    Validate backup file integrity.
    
    Performs multiple checks:
    - File exists and is readable
    - File size is reasonable for ECU memory (256KB - 2MB)
    - Checksum calculation succeeds
    - Metadata extraction from filename works
    
    Args:
        backup_file: Path to backup file
    
    Returns:
        Dictionary with verification results:
        {
            'valid': bool,
            'file_size': int,
            'checksum': str,
            'metadata': dict,
            'errors': List[str]
        }
    
    Example:
        >>> result = verify_backup(Path('backups/VIN123/backup_20251101_143022_VIN123_MSD80.bin'))
        >>> if result['valid']:
        ...     print("Backup is valid")
    """
    result = {
        'valid': False,
        'file_size': 0,
        'checksum': None,
        'metadata': {},
        'errors': []
    }
    
    # Check file exists
    if not backup_file.exists():
        result['errors'].append(f"File not found: {backup_file}")
        return result
    
    # Check file is readable
    if not backup_file.is_file():
        result['errors'].append(f"Not a file: {backup_file}")
        return result
    
    try:
        # Get file size
        file_size = backup_file.stat().st_size
        result['file_size'] = file_size
        
        # Validate size (ECU memory is typically 512KB to 1MB for MSD80)
        # Allow range of 256KB to 2MB to accommodate different ECU types
        min_size = 256 * 1024  # 256KB
        max_size = 2 * 1024 * 1024  # 2MB
        
        if file_size < min_size:
            result['errors'].append(f"File too small ({file_size} bytes, minimum {min_size})")
        elif file_size > max_size:
            result['errors'].append(f"File too large ({file_size} bytes, maximum {max_size})")
        
        # Read and checksum file
        with open(backup_file, 'rb') as f:
            data = f.read()
            checksum = calculate_checksum(data)
            result['checksum'] = checksum
        
        # Parse metadata from filename
        try:
            metadata = parse_backup_filename(backup_file.name)
            result['metadata'] = metadata
        except ValueError as e:
            result['errors'].append(f"Filename parse error: {e}")
        
        # If no errors, mark as valid
        if not result['errors']:
            result['valid'] = True
            logger.info(f"Backup verified: {backup_file.name} ({file_size} bytes, checksum: {checksum[:16]}...)")
        else:
            # Many existing project binaries (stock, mapswitch, MOD) live in
            # the backups folder but do not follow the strict
            # backup_YYYYMMDD_HHMMSS_VIN_ECUTYPE.bin naming convention. They
            # are still useful reference files and should be listed in the UI
            # as "invalid" without spamming the console on every refresh.
            #
            # Downgrade per-file verification failures to INFO so the
            # Backup & Recovery GUI remains clean while full details are
            # still available when running with a more verbose log level.
            logger.info(
                "Backup verification failed: %s, errors: %s",
                backup_file.name,
                result['errors'],
            )
        
    except Exception as e:
        result['errors'].append(f"Verification error: {e}")
        logger.exception(f"Error verifying backup: {backup_file}")
    
    return result


def get_backup_info(backup_file: Path) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from backup file.
    
    Args:
        backup_file: Path to backup file
    
    Returns:
        Dictionary with backup information:
        {
            'filename': str,
            'filepath': str,
            'file_size': int,
            'file_size_mb': float,
            'checksum': str,
            'timestamp': str,
            'vin': str,
            'ecu_type': str,
            'date': str,
            'time': str,
            'verification': dict  # Result of verify_backup()
        }
    
    Example:
        >>> info = get_backup_info(Path('backups/VIN123/backup_20251101_143022_VIN123_MSD80.bin'))
        >>> print(f"VIN: {info['vin']}, Size: {info['file_size_mb']:.2f} MB")
    """
    # Verify backup first
    verification = verify_backup(backup_file)
    
    info = {
        'filename': backup_file.name,
        'filepath': str(backup_file.absolute()),
        'file_size': verification['file_size'],
        'file_size_mb': verification['file_size'] / (1024 * 1024),
        'checksum': verification['checksum'],
        'verification': verification
    }
    
    # Add parsed metadata
    if verification['metadata']:
        info.update(verification['metadata'])
    
    return info


def list_backups(vin: Optional[str] = None, directory: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    List all backup files with metadata.
    
    Args:
        vin: Optional VIN to filter by (lists all VINs if None)
        directory: Optional custom backups directory (uses default if None)
    
    Returns:
        List of dictionaries, each containing backup metadata
        Sorted by timestamp (newest first)
    
    Example:
        >>> backups = list_backups()
        >>> for backup in backups:
        ...     print(f"{backup['vin']}: {backup['date']} {backup['time']}")
        
        >>> # List backups for specific VIN
        >>> vin_backups = list_backups(vin="WBADT63452CX12345")
    """
    backups_list = []
    
    # Use default directory if not specified
    if directory is None:
        directory = get_backups_directory()
    
    # If directory doesn't exist, return empty list
    if not directory.exists():
        logger.info(f"Backups directory does not exist: {directory}")
        return []
    
    # Determine which directories to scan
    if vin:
        # Scan specific VIN directory
        vin_dir = directory / vin
        if vin_dir.exists() and vin_dir.is_dir():
            scan_dirs = [vin_dir]
        else:
            logger.warning(f"VIN directory not found: {vin_dir}")
            return []
    else:
        # Scan all VIN directories
        scan_dirs = [d for d in directory.iterdir() if d.is_dir()]
    
    # Scan each directory for .bin files
    for scan_dir in scan_dirs:
        for backup_file in scan_dir.glob("*.bin"):
            try:
                # Get full backup info
                info = get_backup_info(backup_file)
                backups_list.append(info)
            except Exception as e:
                logger.warning(f"Error reading backup {backup_file}: {e}")
                continue
    
    # Sort by timestamp (newest first)
    backups_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    logger.info(f"Found {len(backups_list)} backup(s)" + (f" for VIN {vin}" if vin else ""))
    return backups_list


def get_latest_backup(vin: str, directory: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Get the most recent backup for a specific VIN.
    
    Args:
        vin: Vehicle Identification Number
        directory: Optional custom backups directory
    
    Returns:
        Backup info dictionary or None if no backups found
    
    Example:
        >>> latest = get_latest_backup("WBADT63452CX12345")
        >>> if latest:
        ...     print(f"Latest backup: {latest['date']} {latest['time']}")
    """
    backups = list_backups(vin=vin, directory=directory)
    if backups:
        return backups[0]  # Already sorted newest first
    return None


def format_backup_list(backups: List[Dict[str, Any]], detailed: bool = False) -> str:
    """
    Format backup list for display.
    
    Args:
        backups: List of backup info dictionaries
        detailed: Include detailed information (checksum, file path)
    
    Returns:
        Formatted string for console display
    
    Example:
        >>> backups = list_backups()
        >>> print(format_backup_list(backups))
    """
    if not backups:
        return "No backups found."
    
    lines = []
    lines.append(f"\nFound {len(backups)} backup(s):\n")
    lines.append("="*80)
    
    for i, backup in enumerate(backups, 1):
        lines.append(f"\n{i}. {backup['filename']}")
        lines.append(f"   VIN: {backup.get('vin', 'Unknown')}")
        lines.append(f"   ECU: {backup.get('ecu_type', 'Unknown')}")
        lines.append(f"   Date: {backup.get('date', 'Unknown')} {backup.get('time', 'Unknown')}")
        lines.append(f"   Size: {backup.get('file_size_mb', 0):.2f} MB ({backup.get('file_size', 0):,} bytes)")
        
        # Verification status
        verification = backup.get('verification', {})
        if verification.get('valid'):
            lines.append(f"   Status: ✓ Valid")
        else:
            errors = verification.get('errors', [])
            lines.append(f"   Status: ✗ Invalid - {', '.join(errors)}")
        
        if detailed:
            lines.append(f"   Path: {backup.get('filepath', 'Unknown')}")
            checksum = backup.get('checksum', '')
            if checksum:
                lines.append(f"   SHA256: {checksum[:32]}...")
    
    lines.append("\n" + "="*80)
    return "\n".join(lines)
