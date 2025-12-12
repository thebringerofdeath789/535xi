#!/usr/bin/env python3
"""
BMW N54 Universal Boost Modification - Multi-Version Support
=============================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Universal boost modification module for BMW N54 ECUs with
    multi-version support. Auto-detects software version and loads
    correct boost table offsets from XDF definitions.

Supported Software Versions:
    - MSD81: I8A0S, IJE0S, IKM0S, INA0S (2MB flash)
    - MSD80: Early N54 (512KB flash)

Features:
    - Automatic software version detection
    - XDF-based offset lookup
    - Stage 1 boost increase preset
    - Preview/comparison mode
    - Unit conversion (raw ↔ PSI/bar)

Classes:
    None (functional module)

Functions:
    get_boost_tables_for_bin(bin_data: bytes) -> Tuple[Optional[str], Optional[Dict]]
    read_table(bin_data: bytes, table_name: str, boost_tables: Optional[Dict]) -> List[List[int]]
    write_table(bin_data: bytearray, table_name: str, values: List[List[int]], boost_tables: Optional[Dict]) -> None
    raw_to_real(value: int, table_name: str, boost_tables: Optional[Dict]) -> float
    real_to_raw(value: float, table_name: str, boost_tables: Optional[Dict]) -> int
    increase_boost_stage1(bin_data: bytes, boost_increase_psi: float) -> bytearray
    preview_boost_changes(bin_data: bytes) -> Dict[str, Tuple[List[float], str]]

Variables (Module-level):
    logger: logging.Logger - Module logger
    _boost_tables_cache: Dict - Software version boost table cache

WARNING: Modifying boost can damage your engine! Use at your own risk.
Recommended boost levels:
- Stock: 7-9 PSI (0.5-0.6 bar)
- Stage 1: 15-17 PSI (1.0-1.2 bar) - Safe for stock turbos
- Stage 2+: 18-21 PSI (1.25-1.45 bar) - Requires upgraded turbos
"""

import struct
from pathlib import Path
from typing import Dict, Tuple, List, Optional
import logging
from . import software_detector

logger = logging.getLogger(__name__)

# Global cache for loaded boost tables
_boost_tables_cache = {}


def get_boost_tables_for_bin(bin_data: bytes) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Auto-detect software version and load boost tables.
    
    Args:
        bin_data: Binary file data
        
    Returns:
        Tuple of (software_version, boost_tables_dict)
    """
    # Detect software version
    sw_version = software_detector.detect_software_version(bin_data)
    
    if not sw_version:
        logger.error("Could not detect software version from bin file")
        return None, None
    
    logger.info(f"Detected software version: {sw_version}")
    
    # Check cache
    if sw_version in _boost_tables_cache:
        return sw_version, _boost_tables_cache[sw_version]
    
    # Load XDF tables
    xdf_dir = Path(__file__).parent.parent / 'maps' / 'xdf_definitions'
    all_tables = software_detector.load_boost_tables_for_version(sw_version, xdf_dir)
    
    if not all_tables:
        logger.error(f"No XDF available for {sw_version}")
        return sw_version, None
    
    # Filter for primary boost tables
    primary_tables = software_detector.get_primary_boost_tables(all_tables)
    
    logger.info(f"Loaded {len(primary_tables)} primary boost tables for {sw_version}")
    
    # Cache for future use
    _boost_tables_cache[sw_version] = primary_tables
    
    return sw_version, primary_tables


# Verified table definitions for I8A0S (from XDF validation)
BOOST_TABLES_I8A0S = {
    'WGDC_BASE': {
        'address': 0x0005F7F6,
        'rows': 20,
        'cols': 16,
        'formula': 'X/655.35',  # Raw to percent
        'inverse': 'X*655.35',  # Percent to raw
        'units': 'WGDC %',
        'description': 'WGDC (Base) - Primary wastegate duty cycle control'
    },
    'WGDC_SPOOL': {
        'address': 0x0005FAB2,
        'rows': 16,
        'cols': 12,
        'formula': 'X/655.35',  # Raw to percent
        'inverse': 'X*655.35',  # Percent to raw
        'units': 'WGDC %',
        'description': 'WGDC (Spool) - Spool-up control'
    },
    'LOAD_TARGET_MAIN': {
        'address': 0x0007F736,
        'rows': 6,
        'cols': 16,
        'formula': 'X/100',  # Raw to Load Act.
        'inverse': 'X*100',  # Load Act. to raw
        'units': 'Load Act.',
        'description': 'Load Target per Gear - Main boost target'
    },
    'BOOST_CEILING_MAP1': {
        'address': 0x0007E6D6,
        'rows': 6,
        'cols': 14,
        'formula': 'X/831.52',  # Raw to PSI
        'inverse': 'X*831.52',  # PSI to raw
        'units': 'psi',
        'description': 'Boost Ceiling (Relative) (Gear x RPM) (Map 1)'
    },
    'WGDC_P_FACTOR': {
        'address': 0x0005FF2A,
        'rows': 12,
        'cols': 12,
        'formula': 'X/1024',
        'inverse': 'X*1024',
        'units': 'Factor',
        'description': 'WGDC P-Factor - Proportional boost control'
    },
    'BOOST_LIMIT_MULTIPLIER': {
        'address': 0x0005F312,
        'rows': 1,
        'cols': 16,
        'formula': 'X/16384',
        'inverse': 'X*16384',
        'units': 'Factor',
        'description': 'Boost Limit Multiplier - Overall boost ceiling'
    },
    'OVERBOOST_DISABLE': {
        'address': 0x0006836A,
        'rows': 1,
        'cols': 4,
        'formula': 'X',
        'inverse': 'X',
        'units': 'Flag',
        'description': 'Overboost Disable - Prevents overboost fault codes'
    }
}


def read_table(bin_data: bytes, table_name: str, boost_tables: Optional[Dict] = None) -> List[List[int]]:
    """
    Read a boost table from binary data.
    
    Args:
        bin_data: Full binary file data
        table_name: Name of table
        boost_tables: Table definitions dict (auto-detected if None)
        
    Returns:
        2D list of raw integer values [row][col]
        
    Raises:
        KeyError: If table_name not found
        ValueError: If table extends beyond binary size
        IndexError: If address is out of bounds
    """
    if boost_tables is None:
        _, boost_tables = get_boost_tables_for_bin(bin_data)
        if not boost_tables:
            logger.warning("Could not auto-detect boost tables, falling back to I8A0S definitions")
            boost_tables = BOOST_TABLES_I8A0S
    
    if table_name not in boost_tables:
        raise KeyError(f"Table '{table_name}' not found in boost tables")
    
    table = boost_tables[table_name]
    address = table['address']
    rows = table['rows']
    cols = table['cols']
    
    # Validate table dimensions
    if rows <= 0 or cols <= 0:
        raise ValueError(f"Invalid table dimensions: {rows}x{cols}")
    
    # Calculate total size needed
    table_size = rows * cols * 2  # 2 bytes per element
    
    # Validate address and size
    if address < 0 or address >= len(bin_data):
        raise IndexError(f"Table address 0x{address:06X} is out of bounds (bin size: 0x{len(bin_data):06X})")
    
    if address + table_size > len(bin_data):
        raise ValueError(f"Table extends beyond binary: needs {table_size} bytes at 0x{address:06X}, bin ends at 0x{len(bin_data):06X}")
    
    # Each element is 16-bit (2 bytes), big-endian
    values = []
    offset = address
    
    for row in range(rows):
        row_values = []
        for col in range(cols):
            raw_value = struct.unpack('>H', bin_data[offset:offset+2])[0]  # Big-endian uint16
            row_values.append(raw_value)
            offset += 2
        values.append(row_values)
    
    return values


def write_table(bin_data: bytearray, table_name: str, values: List[List[int]], boost_tables: Optional[Dict] = None) -> None:
    """
    Write a boost table to binary data.
    
    Args:
        bin_data: Full binary file data (will be modified in-place)
        table_name: Name of table from boost_tables dict
        values: 2D list of raw integer values [row][col]
        boost_tables: Table definitions dict (auto-detected if None)
        
    Raises:
        KeyError: If table_name not found
        ValueError: If dimensions mismatch or values out of range
        IndexError: If address is out of bounds
    """
    if boost_tables is None:
        logger.warning("No boost tables provided, using I8A0S defaults")
        boost_tables = BOOST_TABLES_I8A0S
    
    if table_name not in boost_tables:
        raise KeyError(f"Table '{table_name}' not found in boost tables")
    
    table = boost_tables[table_name]
    address = table['address']
    rows = table['rows']
    cols = table['cols']
    
    # Validate input dimensions
    if not values or not values[0]:
        raise ValueError(f"Cannot write empty table '{table_name}'")
    
    if len(values) != rows or len(values[0]) != cols:
        raise ValueError(f"Table dimensions mismatch: expected {rows}x{cols}, got {len(values)}x{len(values[0])}")
    
    # Validate all values are in uint16 range
    for row_idx, row in enumerate(values):
        for col_idx, val in enumerate(row):
            if not isinstance(val, int) or val < 0 or val > 65535:
                raise ValueError(f"Invalid value at [{row_idx}][{col_idx}]: {val} (must be 0-65535)")
    
    # Validate address
    table_size = rows * cols * 2
    if address < 0 or address + table_size > len(bin_data):
        raise IndexError(f"Table write would exceed binary bounds: 0x{address:06X} + {table_size} bytes")
    
    # Write each element as 16-bit big-endian
    offset = address
    for row in range(rows):
        for col in range(cols):
            bin_data[offset:offset+2] = struct.pack('>H', values[row][col])
            offset += 2


def _safe_formula_eval(formula: str, X: float) -> float:
    """
    Safely evaluate formula with restricted operations.
    
    Only allows basic arithmetic operations: +, -, *, /, ()
    
    Args:
        formula: Formula string (e.g., 'X/655.35' or 'X*831.52')
        X: Input value
        
    Returns:
        Calculated result
        
    Raises:
        ValueError: If formula contains unsafe operations
    """
    # Validate formula contains only safe characters
    allowed_chars = set('0123456789.+-*/() X')
    if not all(c in allowed_chars for c in formula):
        raise ValueError(f"Formula contains unsafe characters: {formula}")
    
    # Replace X with actual value and evaluate safely
    try:
        # Create safe namespace with only basic math operations
        safe_namespace = {'X': X, '__builtins__': {}}
        result = eval(formula, safe_namespace, {})
        return float(result)
    except Exception as e:
        raise ValueError(f"Failed to evaluate formula '{formula}' with X={X}: {e}")


def raw_to_real(value: int, table_name: str, boost_tables: Optional[Dict] = None) -> float:
    """
    Convert raw table value to real-world units.
    
    Args:
        value: Raw integer value from table
        table_name: Name of table
        boost_tables: Table definitions (auto-detected if None)
        
    Returns:
        Value in real-world units (PSI, %, etc.)
        
    Raises:
        KeyError: If table_name not found
        ValueError: If formula evaluation fails
    """
    if boost_tables is None:
        boost_tables = BOOST_TABLES_I8A0S
    
    if table_name not in boost_tables:
        raise KeyError(f"Table '{table_name}' not found in boost tables")
    
    formula = boost_tables[table_name]['formula']
    return _safe_formula_eval(formula, float(value))


def real_to_raw(value: float, table_name: str, boost_tables: Optional[Dict] = None) -> int:
    """
    Convert real-world value to raw table format.
    
    Args:
        value: Real-world value (PSI, %, etc.)
        table_name: Name of table
        boost_tables: Table definitions (auto-detected if None)
        
    Returns:
        Raw integer value (0-65535)
        
    Raises:
        KeyError: If table_name not found
        ValueError: If formula evaluation fails or value out of range
    """
    if boost_tables is None:
        boost_tables = BOOST_TABLES_I8A0S
    
    if table_name not in boost_tables:
        raise KeyError(f"Table '{table_name}' not found in boost tables")
    
    formula = boost_tables[table_name]['inverse']
    result = _safe_formula_eval(formula, value)
    
    # Clamp to uint16 range and validate
    raw_value = int(result)
    if raw_value < 0 or raw_value > 65535:
        logger.warning(f"Value {value} converted to {raw_value}, clamping to uint16 range")
    
    return max(0, min(65535, raw_value))


def increase_boost_stage1(bin_data: bytes, boost_increase_psi: float = 8.0) -> bytearray:
    """
    Apply Stage 1 boost increase modifications.
    
    Safe for stock N54 turbos: Increases boost from ~9 PSI stock to ~17 PSI.
    
    Modifications applied:
    - WGDC (Base): +10 percentage points (additive, not multiplicative)
    - Load Target: +18% (correlates to ~8 PSI boost increase)
    - Boost Ceiling: +boost_increase_psi + 3 PSI safety margin
    - Boost Limit Multiplier: +15%
    
    Args:
        bin_data: Original binary file data (minimum 512KB)
        boost_increase_psi: Target boost increase in PSI (default 8.0 for Stage 1)
        
    Returns:
        Modified binary data
        
    Raises:
        ValueError: If boost_increase_psi is unsafe or bin_data is too small
        KeyError: If required tables are missing
    """
    # Validate input
    if len(bin_data) < 524288:  # 512KB minimum for MSD80
        raise ValueError(f"Binary too small: {len(bin_data)} bytes (need minimum 512KB)")
    
    if boost_increase_psi < 0 or boost_increase_psi > 15:
        raise ValueError(f"Unsafe boost increase: {boost_increase_psi} PSI (safe range: 0-15 PSI)")
    
    logger.info(f"Applying Stage 1 boost modification (+{boost_increase_psi} PSI)")
    
    # Auto-detect software version and load appropriate tables
    sw_version, boost_tables = get_boost_tables_for_bin(bin_data)
    
    if not boost_tables:
        raise ValueError(f"Cannot modify boost: No tables available for detected version '{sw_version}'")
    
    logger.info(f"Using boost tables for {sw_version}")
    
    modified = bytearray(bin_data)
    
    # 1. Increase WGDC Base table by 8-12% to achieve higher boost
    logger.info("Modifying WGDC (Base) table...")
    
    try:
        wgdc_base = read_table(modified, 'WGDC_BASE', boost_tables)
    except (KeyError, ValueError, IndexError) as e:
        raise ValueError(f"Failed to read WGDC_BASE table: {e}")
    
    for row in range(len(wgdc_base)):
        for col in range(len(wgdc_base[0])):
            old_raw = wgdc_base[row][col]
            old_pct = raw_to_real(old_raw, 'WGDC_BASE', boost_tables)
            
            # Add 10 percentage points to duty cycle (e.g., 50% -> 60%)
            # NOT multiplicative (50% * 1.10 = 55%) but additive (50% + 10% = 60%)
            # Stock WGDC typically 40-65%, Stage 1 typically 50-75%
            new_pct = old_pct + 10.0
            new_pct = min(new_pct, 95.0)  # Safety cap at 95% (100% = fully closed wastegate)
            
            new_raw = real_to_raw(new_pct, 'WGDC_BASE', boost_tables)
            wgdc_base[row][col] = new_raw
    
    write_table(modified, 'WGDC_BASE', wgdc_base, boost_tables)
    logger.info("WGDC (Base) increased by +10 percentage points")
    
    # 2. Raise load targets (boost targets)
    logger.info("Modifying Load Target per Gear...")
    
    try:
        load_target = read_table(modified, 'LOAD_TARGET_MAIN', boost_tables)
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"Could not modify LOAD_TARGET_MAIN: {e}")
        load_target = None
    
    if load_target:
        for row in range(len(load_target)):
            for col in range(len(load_target[0])):
                old_raw = load_target[row][col]
                old_load = raw_to_real(old_raw, 'LOAD_TARGET_MAIN', boost_tables)
                
                # Increase load target by 18%
                # Load Act = actual load (pressure ratio): (MAP + baro) / baro
                # Stock: ~1.6 load (9 PSI = 1.61 bar absolute = 0.61 bar gauge)
                # Stage 1: ~2.2 load (17 PSI = 2.17 bar absolute = 1.17 bar gauge)
                # Formula: 1.6 * 1.18 = 1.888, with WGDC increase = ~2.0-2.2 actual
                new_load = old_load * 1.18
                new_load = min(new_load, 2.5)  # Safety limit (2.5 = ~21 PSI)
                
                new_raw = real_to_raw(new_load, 'LOAD_TARGET_MAIN', boost_tables)
                load_target[row][col] = new_raw
        
        write_table(modified, 'LOAD_TARGET_MAIN', load_target, boost_tables)
        logger.info("Load Target increased by 18%")
    
    # 3. Raise boost ceiling to prevent overboost codes
    logger.info("Modifying Boost Ceiling...")
    
    try:
        boost_ceiling = read_table(modified, 'BOOST_CEILING_MAP1', boost_tables)
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"Could not modify BOOST_CEILING_MAP1: {e}")
        boost_ceiling = None
    
    if boost_ceiling:
        for row in range(len(boost_ceiling)):
            for col in range(len(boost_ceiling[0])):
                old_raw = boost_ceiling[row][col]
                old_psi = raw_to_real(old_raw, 'BOOST_CEILING_MAP1', boost_tables)
                
                # Raise ceiling by boost increase + safety margin
                # Formula verified: X/831.52 = PSI (gauge pressure)
                # Stock ceiling: ~18-20 PSI, Stage 1 ceiling: ~28-30 PSI
                new_psi = old_psi + boost_increase_psi + 3.0  # +3 PSI safety margin
                new_psi = min(new_psi, 30.0)  # Absolute safety limit for stock turbos (was 25, now 30)
                
                new_raw = real_to_raw(new_psi, 'BOOST_CEILING_MAP1', boost_tables)
                boost_ceiling[row][col] = new_raw
        
        write_table(modified, 'BOOST_CEILING_MAP1', boost_ceiling, boost_tables)
        logger.info(f"Boost Ceiling raised by {boost_increase_psi + 3.0} PSI")
    
    # 4. Increase boost limit multiplier
    logger.info("Modifying Boost Limit Multiplier...")
    
    try:
        boost_limit = read_table(modified, 'BOOST_LIMIT_MULTIPLIER', boost_tables)
    except (KeyError, ValueError, IndexError) as e:
        logger.warning(f"Could not modify BOOST_LIMIT_MULTIPLIER: {e}")
        boost_limit = None
    
    if boost_limit:
        for col in range(len(boost_limit[0])):
            old_raw = boost_limit[0][col]
            old_factor = raw_to_real(old_raw, 'BOOST_LIMIT_MULTIPLIER', boost_tables)
            
            # Increase limit factor by 15%
            new_factor = old_factor * 1.15
            new_factor = min(new_factor, 1.5)  # Safety cap
            
            new_raw = real_to_raw(new_factor, 'BOOST_LIMIT_MULTIPLIER', boost_tables)
            boost_limit[0][col] = new_raw
        
        write_table(modified, 'BOOST_LIMIT_MULTIPLIER', boost_limit, boost_tables)
        logger.info("Boost Limit Multiplier increased by 15%")
    
    logger.info("Stage 1 boost modification complete!")
    logger.info("Expected boost: ~17 PSI (1.2 bar) - SAFE FOR STOCK TURBOS")
    logger.info("WARNING: Monitor AFR, knock, and EGT during initial testing!")
    
    return modified


def preview_boost_changes(bin_data: bytes) -> Dict[str, Tuple[List[float], str]]:
    """
    Preview current boost table values in human-readable format.
    
    Args:
        bin_data: Binary file data
        
    Returns:
        Dict mapping table names to (sample values, units)
    """
    preview = {}
    
    # Auto-detect software and load tables
    sw_version, boost_tables = get_boost_tables_for_bin(bin_data)
    
    if not boost_tables:
        logger.warning(f"No boost tables available for {sw_version}")
        return preview
    
    # Preview first few tables only (to avoid overwhelming output)
    for table_name, table_info in list(boost_tables.items())[:6]:
        try:
            raw_values = read_table(bin_data, table_name, boost_tables)
            
            # Convert first row to real units for preview
            real_values = [raw_to_real(val, table_name, boost_tables) for val in raw_values[0][:5]]  # First 5 values
            units = table_info['units']
            
            preview[table_name] = (real_values, units)
        except Exception as e:
            logger.warning(f"Could not preview {table_name}: {e}")
    
    return preview


