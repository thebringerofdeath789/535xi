#!/usr/bin/env python3
"""
BMW N54 Module Scanner - Multi-Module Diagnostic Scanner
=========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    BMW-specific diagnostic functions for scanning and reading DTCs from
    multiple control modules beyond OBD-II. Uses direct UDS over CAN to
    access ECUs for comprehensive diagnostics.

Supported Modules:
    - DME (Engine Control)
    - DDE (Diesel Engine Control)
    - EGS (Transmission)
    - ABS/DSC (Brakes)
    - SZL (Steering Column)
    - KOMBI (Instrument Cluster)
    - CAS (Car Access System)
    - And 20+ more BMW modules

Classes:
    ModuleScanError(Exception) - Module scanning errors

Functions:
    scan_all_modules() -> Dict[str, Any]
    read_module_dtcs(module_id: str) -> List[Dict[str, str]]
    read_all_module_dtcs() -> Dict[str, List[Dict[str, str]]]
    clear_module_dtcs(module_id: str) -> bool
    clear_all_module_dtcs() -> Dict[str, bool]
    get_module_info(module_id: str) -> Dict[str, str]
    parse_dtc_results(results: Dict) -> List[Dict[str, str]]
    get_module_list() -> Dict[str, Dict[str, str]]

Variables (Module-level):
    logger: logging.Logger - Module logger
    BMW_MODULES: Dict[str, Dict[str, str]] - Module definitions
"""

import logging
from typing import Dict, List, Optional, Any
from . import bmw_modules
from . import obd_reader
from .uds_client import UDSClient

# Configure logging
logger = logging.getLogger(__name__)


class ModuleScanError(Exception):
    """Raised when module scanning fails"""
    pass


# BMW Module definitions for E60/E90 chassis (2008 535xi)
BMW_MODULES = {
    'DME': {
        'name': 'Digital Motor Electronics',
        'description': 'Engine Control Unit',
        'prg_file': 'MSD80.prg',
        'address': 0x12
    },
    'DSC': {
        'name': 'Dynamic Stability Control',
        'description': 'ABS/Traction Control',
        'prg_file': 'MK60E5.prg',
        'address': 0x34
    },
    'SZL': {
        'name': 'Steering Column Electronics',
        'description': 'Steering wheel controls',
        'prg_file': 'SZL.prg',
        'address': 0x72
    },
    'IHKA': {
        'name': 'Climate Control',
        'description': 'Heating/AC Control',
        'prg_file': 'IHKA.prg',
        'address': 0x5B
    },
    'CAS': {
        'name': 'Car Access System',
        'description': 'Immobilizer/Key Control',
        'prg_file': 'CAS.prg',
        'address': 0x00
    },
    'EGS': {
        'name': 'Electronic Transmission',
        'description': 'Transmission Control',
        'prg_file': 'EGS.prg',
        'address': 0x18
    },
    'ARS': {
        'name': 'Active Roll Stabilization',
        'description': 'Dynamic Drive (if equipped)',
        'prg_file': 'ARS.prg',
        'address': 0x71
    },
    'SAS': {
        'name': 'Airbag System',
        'description': 'Safety System',
        'prg_file': 'ACSM.prg',
        'address': 0x65
    }
}


def scan_all_modules() -> Dict[str, Any]:
    """
    Scan all known BMW modules for availability and DTCs.
    
    Returns:
        Dictionary with scan results:
        {
            'modules_found': int,
            'modules_with_codes': int,
            'total_dtcs': int,
            'modules': Dict[str, Dict]  # module_id -> module_info
        }
    
    Example:
        >>> scan = scan_all_modules()
        >>> print(f"Found {scan['total_dtcs']} DTCs in {scan['modules_with_codes']} modules")
    """
    logger.info("Starting full vehicle module scan...")
    
    results = {
        'modules_found': 0,
        'modules_with_codes': 0,
        'total_dtcs': 0,
        'modules': {}
    }
    
    for module_id, module_def in BMW_MODULES.items():
        logger.info(f"Scanning {module_id} ({module_def['name']})...")
        
        try:
            # Attempt to read DTCs from this module
            module_dtcs = read_module_dtcs(module_id)
            
            # Module responded - it's present
            results['modules_found'] += 1
            
            module_info = {
                'name': module_def['name'],
                'description': module_def['description'],
                'status': 'ok',
                'dtc_count': len(module_dtcs),
                'dtcs': module_dtcs
            }
            
            if len(module_dtcs) > 0:
                results['modules_with_codes'] += 1
                results['total_dtcs'] += len(module_dtcs)
                module_info['status'] = 'codes_present'
            
            results['modules'][module_id] = module_info
        
        except Exception as e:
            # Module not responding or error
            logger.debug(f"{module_id} not available: {e}")
            results['modules'][module_id] = {
                'name': module_def['name'],
                'description': module_def['description'],
                'status': 'not_available',
                'dtc_count': 0,
                'dtcs': []
            }
    
    logger.info(f"Scan complete: {results['modules_found']} modules found, "
                f"{results['total_dtcs']} DTCs in {results['modules_with_codes']} modules")
    
    return results


def read_module_dtcs(module_id: str) -> List[Dict[str, str]]:
    """
    Read diagnostic trouble codes from a specific module.
    
    Args:
        module_id: Module identifier (e.g., 'DME', 'DSC', 'IHKA')
    
    Returns:
        List of DTCs as dictionaries with 'code' and 'description' keys
    
    Raises:
        ModuleScanError: If module cannot be accessed or read fails
    
    Example:
        >>> dtcs = read_module_dtcs('DME')
        >>> for dtc in dtcs:
        ...     print(f"{dtc['code']}: {dtc['description']}")
    """
    if module_id not in BMW_MODULES:
        raise ModuleScanError(f"Unknown module: {module_id}")
    
    logger.info(f"Reading DTCs from {module_id} via UDS/CAN...")
    module = bmw_modules.get_module_by_abbreviation(module_id)
    if not module:
        raise ModuleScanError(f"Unknown module: {module_id}")

    uds = UDSClient()
    try:
        if not uds.connect():
            raise ModuleScanError("Unable to connect to ECU over CAN")
        dtc_dicts = obd_reader.read_dtcs_from_module(module, uds_client=uds)
        return [{'code': d.get('code', 'UNKNOWN'), 'description': d.get('description', 'No description')} for d in dtc_dicts]
    finally:
        try:
            uds.disconnect()
        except Exception:
            pass


def read_all_module_dtcs() -> Dict[str, List[Dict[str, str]]]:
    """
    Read DTCs from all available modules.
    
    Returns:
        Dictionary mapping module_id to list of DTCs
    
    Example:
        >>> all_dtcs = read_all_module_dtcs()
        >>> for module, dtcs in all_dtcs.items():
        ...     print(f"{module}: {len(dtcs)} codes")
    """
    logger.info("Reading DTCs from all modules...")
    
    all_dtcs = {}
    
    multi = {}
    uds = UDSClient()
    try:
        if uds.connect():
            multi = obd_reader.read_all_module_dtcs(protocol="CAN", uds_client=uds)
    finally:
        try:
            uds.disconnect()
        except Exception:
            pass

    # Convert to the simple shape expected by this module
    for module_abbr, dtcs in multi.items():
        all_dtcs[module_abbr] = [
            {'code': d.get('code', 'UNKNOWN'), 'description': d.get('description', 'No description')}
            for d in dtcs
        ]
    
    total = sum(len(dtcs) for dtcs in all_dtcs.values())
    logger.info(f"Read DTCs from {len(all_dtcs)} modules, {total} total codes")
    
    return all_dtcs


def clear_module_dtcs(module_id: str) -> bool:
    """
    Clear all DTCs from a specific module.
    
    CAUTION: This erases fault memory. Should only be called after explicit
    user confirmation.
    
    Args:
        module_id: Module identifier (e.g., 'DME', 'DSC')
    
    Returns:
        True if clearing succeeded, False otherwise
    
    Raises:
        ModuleScanError: If module cannot be accessed or clear fails
    
    Example:
        >>> if user_confirms():
        ...     clear_module_dtcs('DME')
    """
    if module_id not in BMW_MODULES:
        raise ModuleScanError(f"Unknown module: {module_id}")
    
    logger.warning(f"Clearing DTCs from {module_id} via UDS/CAN...")
    module = bmw_modules.get_module_by_abbreviation(module_id)
    if not module:
        raise ModuleScanError(f"Unknown module: {module_id}")

    uds = UDSClient()
    try:
        if uds.connect():
            ok = obd_reader.clear_dtcs_from_module(module, uds_client=uds)
            if not ok:
                return False
            dtcs_after = obd_reader.read_dtcs_from_module(module, uds_client=uds)
            return len(dtcs_after) == 0
        return False
    finally:
        try:
            uds.disconnect()
        except Exception:
            pass


def clear_all_module_dtcs() -> Dict[str, bool]:
    """
    Clear DTCs from all modules.
    
    DANGER: This clears fault codes from ALL modules in the vehicle.
    Should require multiple confirmations before execution.
    
    Returns:
        Dictionary mapping module_id to success status (bool)
    
    Example:
        >>> if user_types_CLEAR_ALL():
        ...     results = clear_all_module_dtcs()
        ...     for module, success in results.items():
        ...         print(f"{module}: {'OK' if success else 'FAILED'}")
    """
    logger.warning("Clearing DTCs from ALL modules...")
    
    results = {}
    
    for module_id in BMW_MODULES.keys():
        try:
            success = clear_module_dtcs(module_id)
            results[module_id] = success
        except ModuleScanError as e:
            logger.debug(f"Could not clear DTCs from {module_id}: {e}")
            results[module_id] = False
            continue
    
    cleared_count = sum(1 for success in results.values() if success)
    logger.info(f"Cleared DTCs from {cleared_count} modules")
    
    return results


def get_module_info(module_id: str) -> Dict[str, str]:
    """
    Get identification information from a specific module.
    
    Args:
        module_id: Module identifier (e.g., 'DME', 'DSC')
    
    Returns:
        Dictionary with module info:
        {
            'name': str,
            'part_number': str,
            'software_version': str,
            'hardware_version': str,
            'coding': str
        }
    
    Raises:
        ModuleScanError: If module cannot be accessed
    
    Example:
        >>> info = get_module_info('DME')
        >>> print(f"DME Software: {info['software_version']}")
    """
    if module_id not in BMW_MODULES:
        raise ModuleScanError(f"Unknown module: {module_id}")
    
    module_def = BMW_MODULES[module_id]
    logger.info(f"Reading identification from {module_id} via UDS...")
    info = {
        'name': module_def['name'],
        'part_number': 'Unknown',
        'software_version': 'Unknown',
        'hardware_version': 'Unknown',
        'coding': 'Unknown'
    }
    try:
        # If DME, try VIN via UDS for basic verification
        if module_id == 'DME':
            uds = UDSClient()
            try:
                if uds.connect():
                    module = bmw_modules.get_module_by_abbreviation('DME')
                    if module:
                        vin_bytes = uds.read_data_by_identifier(module, 0xF190)
                        if vin_bytes:
                            info['coding'] = (vin_bytes.decode('ascii', errors='ignore').strip() or 'Unknown')
            finally:
                try:
                    uds.disconnect()
                except Exception:
                    pass
        logger.info(f"Retrieved basic info from {module_id}")
        return info
    except Exception as e:
        raise ModuleScanError(f"Unexpected error reading {module_id} info: {e}")


# Note: DTC parsing uses native UDS responses; normalized dict format returned


def get_module_list() -> Dict[str, Dict[str, str]]:
    """
    Get list of all known BMW modules with descriptions.
    
    Returns:
        Dictionary of module definitions
    
    Example:
        >>> modules = get_module_list()
        >>> for module_id, module_def in modules.items():
        ...     print(f"{module_id}: {module_def['name']}")
    """
    return BMW_MODULES.copy()
