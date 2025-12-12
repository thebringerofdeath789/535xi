#!/usr/bin/env python3
"""
N54 Software Version Detection and XDF Table Extraction

Detects ECU software version from bin files and extracts boost table
definitions from the corresponding XDF file.

Supports:
- MSD80 (512KB): Older N54 ECUs
- MSD81 (2MB): Newer N54 ECUs (I8A0S, IJE0S, IKM0S, INA0S)
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import struct
import re

# Known N54 software versions with their characteristics
N54_SOFTWARE_VERSIONS = {
    'I8A0S': {
        'ecu_type': 'MSD81',
        'size': 2097152,
        'description': '2008-2010 N54 LCI (MSD81)',
        'xdf_file': 'I8A0S.xdf'
    },
    'IJE0S': {
        'ecu_type': 'MSD81',
        'size': 2097152,
        'description': '2007-2008 N54 Pre-LCI (MSD81)',
        'xdf_file': 'IJE0S.xdf'
    },
    'IKM0S': {
        'ecu_type': 'MSD81',
        'size': 2097152,
        'description': '2009-2010 N54 (MSD81)',
        'xdf_file': 'IKM0S.xdf'
    },
    'INA0S': {
        'ecu_type': 'MSD81',
        'size': 2097152,
        'description': '2007-2010 N54 (MSD81)',
        'xdf_file': 'INA0S.xdf'
    },
    'MSD80': {
        'ecu_type': 'MSD80',
        'size': 524288,
        'description': 'Early N54 (MSD80)',
        'xdf_file': None  # No XDF available for MSD80 yet
    }
}


def detect_ecu_type_from_size(file_size: int) -> str:
    """
    Detect ECU type from binary file size.
    
    Args:
        file_size: Size of binary file in bytes
        
    Returns:
        ECU type string ('MSD80' or 'MSD81')
        
    Raises:
        ValueError: If file size doesn't match any known ECU
    """
    if file_size == 2097152:
        return 'MSD81'  # 2 MB
    elif file_size == 524288:
        return 'MSD80'  # 512 KB
    else:
        raise ValueError(f"Unknown ECU flash size: {file_size} bytes. Expected 524288 (MSD80) or 2097152 (MSD81)")


def detect_software_version(bin_data: bytes) -> Optional[str]:
    """
    Detect software version from bin file data.
    
    Searches for software ID patterns in the binary data.
    N54 software IDs are typically 5 characters ending in 'S'.
    
    Args:
        bin_data: Binary file data
        
    Returns:
        Software version string (e.g., 'I8A0S') or None if not found
    """
    # Pattern: 5 uppercase alphanumeric chars ending in 'S'
    pattern = rb'[A-Z][A-Z0-9]{3}S'
    
    # Search entire file and count occurrences
    matches = re.findall(pattern, bin_data)
    
    if not matches:
        # Fallback: detect by file size
        file_size = len(bin_data)
        try:
            ecu_type = detect_ecu_type_from_size(file_size)
            return 'I8A0S' if ecu_type == 'MSD81' else 'MSD80'
        except ValueError:
            return None
    
    # Count occurrences of each match
    sw_counts = {}
    for match_bytes in matches:
        sw_id = match_bytes.decode('ascii')
        # Only count if it's a known version
        if sw_id in N54_SOFTWARE_VERSIONS:
            sw_counts[sw_id] = sw_counts.get(sw_id, 0) + 1
    
    if not sw_counts:
        # No known versions found, try to find the most common 5-char S-ending pattern
        all_counts = {}
        for match_bytes in matches:
            sw_id = match_bytes.decode('ascii')
            all_counts[sw_id] = all_counts.get(sw_id, 0) + 1
        
        # Return the one with most occurrences (likely the software ID)
        # Filter for ones that appear at least 5 times
        candidates = {sw: count for sw, count in all_counts.items() if count >= 5}
        if candidates:
            return max(candidates.items(), key=lambda x: x[1])[0]
        
        return None
    
    # Return the known version with most occurrences
    return max(sw_counts.items(), key=lambda x: x[1])[0]


def get_software_info(sw_version: str) -> Dict:
    """Get information about a software version."""
    return N54_SOFTWARE_VERSIONS.get(sw_version, {
        'ecu_type': 'Unknown',
        'size': 0,
        'description': 'Unknown',
        'xdf_file': None
    })


def detect_software_from_bin(bin_file_path: str) -> Dict:
    """
    Unified detection: reads binary file and returns complete software information.
    
    Consolidates size-based ECU detection with version detection to eliminate 
    hardcoded size checks throughout CLI.
    
    Args:
        bin_file_path: Path to binary file
        
    Returns:
        Dict with keys:
            - 'ecu_type': 'MSD80' or 'MSD81'
            - 'size_bytes': File size in bytes
            - 'software_version': Detected software ID (e.g., 'I8A0S') or None
            - 'software_info': Dict with ecu_type, description, xdf_file, etc.
            - 'is_valid': bool indicating if file size is recognized
            - 'error': None or error message if detection failed
            
    Raises:
        FileNotFoundError: If bin file doesn't exist
        IOError: If file can't be read
    """
    result = {
        'ecu_type': None,
        'size_bytes': 0,
        'software_version': None,
        'software_info': {},
        'is_valid': False,
        'error': None
    }
    
    try:
        bin_path = Path(bin_file_path)
        if not bin_path.exists():
            result['error'] = f"File not found: {bin_file_path}"
            return result
        
        # Read file
        with open(bin_path, 'rb') as f:
            bin_data = f.read()
        
        result['size_bytes'] = len(bin_data)
        
        # Detect ECU type from size
        try:
            result['ecu_type'] = detect_ecu_type_from_size(len(bin_data))
            result['is_valid'] = True
        except ValueError as e:
            result['error'] = str(e)
            result['is_valid'] = False
            return result
        
        # Detect software version
        sw_version = detect_software_version(bin_data)
        result['software_version'] = sw_version
        
        if sw_version:
            result['software_info'] = get_software_info(sw_version)
        else:
            # Provide minimal info if version not detected
            result['software_info'] = {
                'ecu_type': result['ecu_type'],
                'size': result['size_bytes'],
                'description': f"Unknown {result['ecu_type']} software",
                'xdf_file': None
            }
        
        return result
        
    except (IOError, OSError) as e:
        result['error'] = f"Failed to read file: {str(e)}"
        return result
    except Exception as e:
        result['error'] = f"Unexpected error during software detection: {str(e)}"
        return result


def extract_boost_tables_from_xdf(xdf_file: Path) -> Dict[str, Dict]:
    """
    Extract boost table definitions from XDF file.
    
    Args:
        xdf_file: Path to XDF definition file
        
    Returns:
        Dict mapping table names to table definitions
    """
    if not xdf_file.exists():
        raise FileNotFoundError(f"XDF file not found: {xdf_file}")
    
    tree = ET.parse(xdf_file)
    root = tree.getroot()
    
    # Keywords to identify boost-related tables
    boost_keywords = [
        'wgdc', 'wastegate', 'boost', 'overboost', 'underboost',
        'load target', 'boost ceiling', 'boost limit'
    ]
    
    boost_tables = {}
    
    for table in root.findall('.//XDFTABLE'):
        title_elem = table.find('title')
        if title_elem is None or not title_elem.text:
            continue
        
        title = title_elem.text
        title_lower = title.lower()
        
        # Skip if not boost-related
        if not any(kw in title_lower for kw in boost_keywords):
            continue
        
        # Skip axis/breakpoint tables
        if '(autogen)' in title or 'breakpoint' in title_lower:
            continue
        
        # Get Z-axis (main table data)
        z_axis = table.find('.//XDFAXIS[@id="z"]')
        if z_axis is None:
            continue
        
        embedded = z_axis.find('EMBEDDEDDATA')
        if embedded is None or embedded.get('mmedaddress') is None:
            continue
        
        try:
            addr_str = embedded.get('mmedaddress')
            address = int(addr_str, 16)
            
            rows = int(embedded.get('mmedrowcount', '1'))
            cols = int(embedded.get('mmedcolcount', '1'))
            elem_bits = int(embedded.get('mmedelementsizebits', '16'))
            
            # Get units and conversion formula
            units_elem = z_axis.find('units')
            units = units_elem.text if units_elem is not None and units_elem.text else 'N/A'
            
            math_elem = z_axis.find('MATH')
            formula = math_elem.get('equation') if math_elem is not None else 'X'
            
            # Create safe table name
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', title.upper())
            safe_name = re.sub(r'_+', '_', safe_name).strip('_')
            
            # Calculate inverse formula (best effort)
            inverse_formula = calculate_inverse_formula(formula)
            
            boost_tables[safe_name] = {
                'address': address,
                'rows': rows,
                'cols': cols,
                'element_bits': elem_bits,
                'formula': formula,
                'inverse': inverse_formula,
                'units': units,
                'description': title,
                'size_bytes': rows * cols * (elem_bits // 8)
            }
        except (ValueError, TypeError) as e:
            continue
    
    return boost_tables


def calculate_inverse_formula(formula: str) -> str:
    """
    Calculate inverse formula for converting real values back to raw.
    
    Args:
        formula: Forward conversion formula (e.g., "X/655.35")
        
    Returns:
        Inverse formula (e.g., "X*655.35")
    """
    # Common patterns
    if formula == 'X':
        return 'X'
    
    # Division: X/N -> X*N
    div_match = re.match(r'^X/([0-9.]+)$', formula)
    if div_match:
        divisor = div_match.group(1)
        return f'X*{divisor}'
    
    # Multiplication: X*N -> X/N
    mul_match = re.match(r'^X\*([0-9.]+)$', formula)
    if mul_match:
        multiplier = mul_match.group(1)
        return f'X/{multiplier}'
    
    # Complex formula with division: (X/A)*B -> X/(A*B) or X*(A/B)
    complex_div = re.match(r'^\(X/([0-9.]+)\)\*([0-9.]+)$', formula)
    if complex_div:
        a = float(complex_div.group(1))
        b = float(complex_div.group(2))
        result = a / b
        return f'X*{result}'
    
    # Default: assume identity
    return 'X'


def load_boost_tables_for_version(sw_version: str, xdf_dir: Path) -> Optional[Dict[str, Dict]]:
    """
    Load boost tables for a specific software version.
    
    Args:
        sw_version: Software version (e.g., 'I8A0S')
        xdf_dir: Directory containing XDF files
        
    Returns:
        Dict of boost tables or None if XDF not available
    """
    sw_info = get_software_info(sw_version)
    xdf_filename = sw_info.get('xdf_file')
    
    if not xdf_filename:
        return None
    
    xdf_file = xdf_dir / xdf_filename
    
    if not xdf_file.exists():
        return None
    
    return extract_boost_tables_from_xdf(xdf_file)


def get_primary_boost_tables(all_tables: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Filter for primary boost modification targets.
    
    Args:
        all_tables: All boost tables
        
    Returns:
        Filtered dict of primary tables for modification
    """
    # Keywords for primary tables
    primary_keywords = [
        'wgdc_base', 'wgdc__base',
        'load_target_per_gear', 'load_target',
        'boost_ceiling', 'boost_limit',
        'wgdc_p_factor', 'wgdc_i_factor'
    ]
    
    primary = {}
    
    for name, table_info in all_tables.items():
        name_lower = name.lower()
        
        # Check if it's a primary table
        if any(kw in name_lower for kw in primary_keywords):
            # Skip 1D axis tables
            if table_info['rows'] == 1 and table_info['cols'] < 20:
                continue
            if table_info['cols'] == 1 and table_info['rows'] < 20:
                continue
            
            primary[name] = table_info
    
    return primary


if __name__ == '__main__':
    """Test software detection and XDF extraction"""
    import sys
    
    workspace = Path(__file__).parent.parent
    xdf_dir = workspace / 'maps' / 'xdf_definitions'
    
    # Test all reference bins
    reference_bins = workspace / 'maps' / 'reference_bins'
    
    if reference_bins.exists():
        print("="*80)
        print("TESTING SOFTWARE DETECTION")
        print("="*80)
        print()
        
        for bin_file in reference_bins.glob('*.bin'):
            print(f"File: {bin_file.name}")
            
            bin_data = bin_file.read_bytes()
            sw_version = detect_software_version(bin_data)
            
            if sw_version:
                sw_info = get_software_info(sw_version)
                print(f"  Detected: {sw_version}")
                print(f"  ECU Type: {sw_info['ecu_type']}")
                print(f"  Description: {sw_info['description']}")
                print(f"  Size: {len(bin_data):,} bytes (expected: {sw_info['size']:,})")
                
                # Try loading boost tables
                tables = load_boost_tables_for_version(sw_version, xdf_dir)
                if tables:
                    primary = get_primary_boost_tables(tables)
                    print(f"  Boost Tables: {len(tables)} total, {len(primary)} primary")
                else:
                    print(f"  Boost Tables: XDF not available")
            else:
                print(f"  Detected: Unknown")
            
            print()
