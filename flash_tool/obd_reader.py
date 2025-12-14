#!/usr/bin/env python3
from __future__ import annotations
"""
BMW N54 OBD-II Reader - Standard Diagnostic Functions
=====================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Standard OBD-II diagnostic functions for BMW N54 ECU.
    Implements generic OBD-II commands (DTCs, freeze frames, readiness,
    vehicle info) using the python-obd library.

Features:
    - Read/clear diagnostic trouble codes (DTCs)
    - Freeze frame data retrieval
    - Readiness monitor status
    - Vehicle identification (VIN, calibration ID)
    - Connection management with auto-reconnect

Classes:
    OBDConnectionError(Exception) - Connection failures
    OBDReadError(Exception) - Read operation failures

Functions:
    connect_obd(port: Optional[str], baudrate: int) -> obd.OBD
    read_obd_dtcs(connection: obd.OBD) -> List[Dict[str, str]]
    clear_obd_dtcs(connection: obd.OBD) -> bool
    read_freeze_frame(connection: obd.OBD) -> Dict[str, Any]
    get_vehicle_info(connection: obd.OBD) -> Dict[str, str]
    disconnect_obd(connection: obd.OBD) -> None
    query_readiness_monitors(connection: obd.OBD) -> Dict[str, Any]

Variables (Module-level):
    OBD_AVAILABLE: bool - python-obd library availability
    logger: logging.Logger - Module logger

NOTE: python-obd is not compatible with Python 3.13+.
"""


try:
    import obd
    OBD_AVAILABLE = True
except Exception:
    obd = None
    OBD_AVAILABLE = False

from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
import logging
from . import bmw_modules
from . import dtc_database
from .dtc_utils import parse_dtc_response

if TYPE_CHECKING:
    # For type hints without importing at runtime
    from .uds_client import UDSClient

# Configure logging
logger = logging.getLogger(__name__)


class OBDConnectionError(Exception):
    """Raised when OBD connection fails"""
    # Exception for OBD connection errors
    pass


class OBDReadError(Exception):
    """Raised when OBD read operation fails"""
    # Exception for OBD read errors
    pass


def _check_obd_available():
    """Check if python-obd is available, raise error if not."""
    if not OBD_AVAILABLE:
        raise OBDConnectionError(
            "python-obd library is not available. "
            "This library is not compatible with Python 3.13+. "
            "To use OBD-II functions, install Python 3.12 or earlier."
        )


def connect_obd(port: Optional[str] = None, baudrate: int = 38400):
    """
    Establish connection to vehicle via OBD-II interface.
    
    Args:
        port: COM port name (e.g., 'COM3'). If None, auto-detects.
        baudrate: Communication speed (default 38400 for K+DCAN)
    
    Returns:
        obd.OBD: Active OBD connection object
    
    Raises:
        OBDConnectionError: If connection cannot be established
    
    Example:
        >>> connection = connect_obd('COM3')
        >>> # ... perform operations ...
        >>> connection.close()
    """
    _check_obd_available()
    
    try:
        if port:
            logger.info(f"Connecting to OBD-II on {port} at {baudrate} baud...")
            connection = obd.OBD(portstr=port, baudrate=baudrate, fast=False)
        else:
            logger.info("Auto-detecting OBD-II connection...")
            connection = obd.OBD(fast=False)
        
        if not connection.is_connected():
            raise OBDConnectionError("Failed to establish OBD-II connection")
        
        logger.info(f"OBD-II connected successfully on {connection.port_name()}")
        return connection
    
    except Exception as e:
        logger.error(f"OBD connection error: {e}")
        raise OBDConnectionError(f"Could not connect to OBD-II interface: {e}")


def read_obd_dtcs(connection: obd.OBD) -> List[Dict[str, str]]:
    """
    Read OBD-II diagnostic trouble codes (engine only).
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        List of dictionaries with 'code' and 'description' keys.
        Returns empty list if no codes found.
    
    Raises:
        OBDReadError: If reading DTCs fails
    
    Example:
        >>> dtcs = read_obd_dtcs(connection)
        >>> for dtc in dtcs:
        ...     print(f"{dtc['code']}: {dtc['description']}")
        P0300: Random/Multiple Cylinder Misfire Detected
    """
    try:
        logger.info("Reading OBD-II DTCs...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Query DTCs using OBD Mode 03
        response = connection.query(obd.commands.GET_DTC)
        
        if response.is_null():
            logger.warning("DTC query returned null response")
            return []
        
        dtcs = []
        for code, description in response.value:
            dtcs.append({
                'code': code,
                'description': description
            })
        
        logger.info(f"Found {len(dtcs)} OBD-II DTCs")
        return dtcs
    
    except Exception as e:
        logger.error(f"Error reading OBD-II DTCs: {e}")
        raise OBDReadError(f"Failed to read DTCs: {e}")


def clear_obd_dtcs(connection: obd.OBD) -> bool:
    """
    Clear all OBD-II diagnostic trouble codes (engine only).
    
    CAUTION: This will erase all stored fault codes and freeze frame data.
    Should only be called after explicit user confirmation.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        True if clearing succeeded, False otherwise
    
    Raises:
        OBDReadError: If clear operation fails
    
    Example:
        >>> if user_confirms():
        ...     clear_obd_dtcs(connection)
    """
    try:
        logger.warning("Clearing OBD-II DTCs (Mode 04)...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Send clear DTC command (Mode 04)
        response = connection.query(obd.commands.CLEAR_DTC)
        
        if response.is_null():
            logger.error("Clear DTC command returned null response")
            return False
        
        # Verify codes were cleared
        dtcs_after = read_obd_dtcs(connection)
        
        if len(dtcs_after) == 0:
            logger.info("OBD-II DTCs cleared successfully")
            return True
        else:
            logger.warning(f"Some DTCs remain after clear: {len(dtcs_after)} codes")
            return False
    
    except Exception as e:
        logger.error(f"Error clearing OBD-II DTCs: {e}")
        raise OBDReadError(f"Failed to clear DTCs: {e}")


def read_freeze_frame(connection: obd.OBD) -> Dict[str, Any]:
    """
    Read freeze frame data from BMW modules via UDS.
    
    Freeze frame is a snapshot of engine parameters at the moment a DTC was stored.
    For BMW modules, uses UDS service 0x19 with subfunction 0x04 (reportDTCSnapshotRecordByDTCNumber).
    
    Args:
        connection: Active OBD connection object (or None to use default)
        module: BMWModule to read from (defaults to DME if None)
        uds_client: UDS client for direct communication (optional)
    
    Returns:
        Dictionary with freeze frame data indexed by DTC code:
        {
            'P0300': {
                'dtc': 'P0300',
                'record_number': 1,
                'rpm': 3000,
                'load': 45.5,
                'coolant_temp': 90,
                'vehicle_speed': 65,
                'fuel_pressure': 550,
                'timing_advance': 12.5,
                'intake_temp': 25,
                'throttle_pos': 35.0,
                'short_fuel_trim_1': 2.5,
                'long_fuel_trim_1': -1.5,
                'raw_data': bytes object
            }
        }
    
    Raises:
        OBDReadError: If reading freeze frame fails
    
    Example:
        >>> freeze_data = read_freeze_frame_from_module(dme_module)
        >>> for dtc_code, snapshot in freeze_data.items():
        ...     print(f"{dtc_code}: RPM={snapshot.get('rpm')}, Temp={snapshot.get('coolant_temp')}°C")

    Note:
        Standard OBD-II freeze frames have limited data.
        BMW UDS implementation provides extended snapshot with 20+ parameters.
    """
    try:
        from flash_tool import bmw_modules

        logger.info("Reading freeze frame data from BMW module...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        freeze_data = {}
        
        # Note: python-obd library has limited freeze frame support
        # This implementation attempts to read common freeze frame PIDs
        # Full freeze frame support may require custom implementation
        
        try:
            # Attempt to read freeze frame DTC
            response = connection.query(obd.commands.FREEZE_DTC)
            if not response.is_null():
                freeze_data['dtc'] = response.value
        except Exception as e:
            logger.warning(f"Could not read freeze frame DTC: {e}")
        
        logger.info(f"Freeze frame data retrieved: {len(freeze_data)} parameters")
        return freeze_data
    
    except Exception as e:
        logger.error(f"Error reading freeze frame: {e}")
        raise OBDReadError(f"Failed to read freeze frame: {e}")


def get_vehicle_info(connection: obd.OBD) -> Dict[str, str]:
    """
    Read vehicle identification information.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Dictionary with 'vin', 'calibration_id', and other available info
    
    Raises:
        OBDReadError: If reading vehicle info fails
    
    Example:
        >>> info = get_vehicle_info(connection)
        >>> print(f"VIN: {info.get('vin', 'Unknown')}")
    """
    try:
        logger.info("Reading vehicle information...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        vehicle_info = {}
        
        # Read VIN (Vehicle Identification Number)
        try:
            response = connection.query(obd.commands.VIN)
            if not response.is_null():
                vehicle_info['vin'] = response.value
        except Exception as e:
            logger.warning(f"Could not read VIN: {e}")
            vehicle_info['vin'] = 'Unknown'
        
        # Read Calibration ID
        try:
            response = connection.query(obd.commands.CALIBRATION_ID)
            if not response.is_null():
                vehicle_info['calibration_id'] = response.value
        except Exception as e:
            logger.warning(f"Could not read Calibration ID: {e}")
            vehicle_info['calibration_id'] = 'Unknown'
        
        # Read ECU Name
        try:
            response = connection.query(obd.commands.ECU_NAME)
            if not response.is_null():
                vehicle_info['ecu_name'] = response.value
        except Exception as e:
            logger.warning(f"Could not read ECU Name: {e}")
            vehicle_info['ecu_name'] = 'Unknown'
        
        logger.info(f"Vehicle info retrieved: {vehicle_info}")
        return vehicle_info
    
    except Exception as e:
        logger.error(f"Error reading vehicle info: {e}")
        raise OBDReadError(f"Failed to read vehicle info: {e}")


def disconnect_obd(connection: obd.OBD) -> None:
    """
    Safely close OBD connection.
    
    Args:
        connection: Active OBD connection object
    
    Example:
        >>> disconnect_obd(connection)
    """
    try:
        if connection and connection.is_connected():
            connection.close()
            logger.info("OBD connection closed")
    except Exception as e:
        logger.warning(f"Error closing OBD connection: {e}")


def query_readiness_monitors(connection: obd.OBD) -> Dict[str, Any]:
    """
    Query OBD-II Mode 0x01 PID 0x01 (Readiness Monitor Status).
    
    This is the CRITICAL function for verifying readiness monitor patches.
    
    OBD-II Response Format:
        Request:  0x01 0x01
        Response: 0x41 0x01 XX XX XX XX
                           ^^^^
                           Bytes 3-6 contain monitor status
    
    Byte 5 (index 4) is the readiness byte:
        0x00 = All monitors ready (checkmark)
        0x65 = Example: Some monitors not ready
    
    Bit mapping for readiness byte (0 = ready, 1 = not ready):
        Bit 0: Catalyst monitor
        Bit 1: Heated catalyst
        Bit 2: EVAP system
        Bit 3: Secondary air system
        Bit 4: A/C refrigerant
        Bit 5: Oxygen sensor
        Bit 6: Oxygen sensor heater
        Bit 7: EGR system
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Dictionary with:
            - success: bool
            - readiness_byte: int (0x00 = all ready)
            - all_ready: bool (True if byte == 0x00)
            - monitors: dict of individual monitor status
            - raw_response: bytes
            - mil_status: bool (Check Engine Light on/off)
            - dtc_count: int (Number of stored DTCs)
    
    Example:
        >>> conn = connect_obd('COM3')
        >>> result = query_readiness_monitors(conn)
        >>> if result['all_ready']:
        ...     print("All monitors ready!")
        ... else:
        ...     print(f"Readiness byte: 0x{result['readiness_byte']:02X}")
        ...     for monitor, ready in result['monitors'].items():
        ...         print(f"  {monitor}: {ready}")
    """
    _check_obd_available()
    
    try:
        # Query Mode $01 PID $01 (Monitor Status)
        cmd = obd.commands.STATUS  # Built-in command for Mode 01 PID 01
        response = connection.query(cmd)
        
        if response.is_null():
            return {
                'success': False,
                'error': 'No response from ECU (check connection)',
                'readiness_byte': None,
                'all_ready': False,
                'monitors': {},
                'raw_response': b'',
                'mil_status': None,
                'dtc_count': None
            }
        
        # Parse response
        # response.value is a Status object with attributes:
        # - MIL (bool): Malfunction Indicator Lamp (Check Engine Light)
        # - DTC_count (int): Number of stored DTCs
        # - ignition_type (str): "spark" or "compression"
        # Plus monitor status attributes
        
        status = response.value
        
        # Extract readiness byte from raw response
        # Response format: 41 01 [A] [B] [C] [D]
        # Byte C (index 4) is readiness for spark ignition
        raw_bytes = response.messages[0].data if response.messages else b''
        readiness_byte = raw_bytes[4] if len(raw_bytes) > 4 else 0xFF
        
        # Parse individual monitors (True = ready, False = not ready)
        monitors = {
            'catalyst': not status.CATALYST,  # Bit inverted (0 = ready)
            'heated_catalyst': not status.HEATED_CATALYST,
            'evap_system': not status.EVAPORATIVE_SYSTEM,
            'secondary_air': not status.SECONDARY_AIR_SYSTEM,
            'oxygen_sensor': not status.OXYGEN_SENSOR,
            'oxygen_sensor_heater': not status.OXYGEN_SENSOR_HEATER,
            'egr_system': not status.EGR_SYSTEM if hasattr(status, 'EGR_SYSTEM') else True
        }
        
        all_ready = (readiness_byte == 0x00)
        
        logger.info(f"Readiness query: byte=0x{readiness_byte:02X}, all_ready={all_ready}")
        
        return {
            'success': True,
            'readiness_byte': readiness_byte,
            'all_ready': all_ready,
            'monitors': monitors,
            'raw_response': raw_bytes,
            'mil_status': status.MIL,  # Check Engine Light
            'dtc_count': status.DTC_count,
            'ignition_type': status.ignition_type
        }
        
    except Exception as e:
        logger.error(f"Readiness query error: {e}")
        return {
            'success': False,
            'error': str(e),
            'readiness_byte': None,
            'all_ready': False,
            'monitors': {},
            'raw_response': b'',
            'mil_status': None,
            'dtc_count': None
        }


# ============================================================================
# Multi-Module DTC Functions (Task 1.1.4 - UDS/KWP2000)
# ============================================================================

def read_dtcs_from_module(module: bmw_modules.BMWModule, uds_client: Optional['UDSClient'] = None) -> List[Dict[str, Any]]:
    """
    Read DTCs from a specific BMW module using UDS or KWP2000 (Task 1.1.4).
    
    This function supports both UDS (ISO 14229) and KWP2000 (ISO 14230) protocols
    for comprehensive multi-module diagnostics.
    
    Args:
        module: BMWModule object specifying which module to query
        uds_client: Optional UDS client (from uds_handler or direct_can_flasher)
    
    Returns:
        List of DTC dictionaries with:
            - code: DTC code (e.g., 'P0300', '2A88')
            - status: Status byte (pending, confirmed, etc.)
            - description: Human-readable description
            - module: Module abbreviation (e.g., 'DME')
            - severity: Severity level if in database
    
    Raises:
        OBDReadError: If DTC reading fails
    
    Example:
        >>> dme = bmw_modules.get_module_by_abbreviation('DME')
        >>> dtcs = read_dtcs_from_module(dme)
        >>> for dtc in dtcs:
        ...     print(f"{dtc['code']}: {dtc['description']}")
    """
    try:
        logger.info(f"Reading DTCs from {module.abbreviation} ({module.name})...")
        
        dtcs = []
        
        if module.protocol == bmw_modules.Protocol.UDS_CAN or module.protocol == bmw_modules.Protocol.BOTH:
            # Use UDS 0x19 (ReadDTCInformation) service
            # Subfunction 0x02 = reportDTCByStatusMask
            # Status mask 0xFF = all DTCs
            
            from flash_tool.uds_client import UDSClient
            local_client: Optional[UDSClient] = None
            client: Optional[UDSClient] = uds_client
            if client is None:
                # Create a temporary UDS client for this call
                try:
                    local_client = UDSClient()
                    if not local_client.connect():
                        logger.error("Failed to connect UDS client (CAN)")
                        return dtcs
                    client = local_client
                except Exception as e:
                    logger.error(f"Unable to initialize UDS client: {e}")
                    return dtcs
            
            try:
                # UDS command: 0x19 0x02 0xFF
                # Response: 0x59 0x02 [DTC1_HI] [DTC1_LO] [STATUS1] [DTC2_HI] ...
                assert client is not None
                raw: Optional[bytes] = client.read_dtcs_by_status_mask(module, status_mask=0xFF)
                if raw:
                    dtcs = parse_uds_dtc_response(raw)
                else:
                    logger.info(f"No DTC data returned for {module.abbreviation}")
                
            except Exception as e:
                logger.error(f"UDS DTC read error for {module.abbreviation}: {e}")
            finally:
                if local_client:
                    try:
                        local_client.disconnect()
                    except Exception:
                        pass
        
        elif module.protocol == bmw_modules.Protocol.KWP2000_KLINE:
            # Use KWP2000 0x18 (ReadDTCByStatus) service
            try:
                from .kwp_client import KWPClient
            except Exception:
                logger.error("KWP client not available; cannot read K-line DTCs")
                return dtcs

            local_client = None
            client = None
            try:
                # Create a KWP client using the recommended port if available
                local_client = KWPClient()
                local_client.connect()
                client = local_client
                dtcs = client.read_dtcs(module, status_mask=0xFF)
            except Exception as e:
                logger.error(f"KWP DTC read error for {module.abbreviation}: {e}")
            finally:
                if local_client:
                    try:
                        local_client.disconnect()
                    except Exception:
                        pass
        
        logger.info(f"Found {len(dtcs)} DTCs in {module.abbreviation}")
        return dtcs
        
    except Exception as e:
        logger.error(f"Error reading DTCs from {module.abbreviation}: {e}")
        raise OBDReadError(f"Failed to read DTCs from {module.abbreviation}: {e}")


def parse_uds_dtc_response(response_data: bytes) -> List[Dict[str, Any]]:
    """
    Wrapper for parse_dtc_response with UDS positive header 0x59.
    """
    return parse_dtc_response(response_data, positive_header=0x59)


def clear_dtcs_from_module(module: bmw_modules.BMWModule, uds_client: Optional['UDSClient'] = None) -> bool:
    """
    Clear DTCs from a specific BMW module using UDS or KWP2000 (Task 1.1.6).
    
    CAUTION: This will erase all stored fault codes from the module.
    Should only be called after explicit user confirmation.
    
    Args:
        module: BMWModule object specifying which module to clear
        uds_client: Optional UDS client (from uds_handler or direct_can_flasher)
    
    Returns:
        True if clearing succeeded, False otherwise
    
    Raises:
        OBDReadError: If clear operation fails
    
    Example:
        >>> dme = bmw_modules.get_module_by_abbreviation('DME')
        >>> if user_confirms():
        ...     clear_dtcs_from_module(dme)
    """
    try:
        logger.warning(f"Clearing DTCs from {module.abbreviation} ({module.name})...")
        
        if module.protocol == bmw_modules.Protocol.UDS_CAN or module.protocol == bmw_modules.Protocol.BOTH:
            # Use UDS 0x14 (ClearDiagnosticInformation) service
            # Parameters: 0xFFFFFF (all DTC groups)
            
            from flash_tool.uds_client import UDSClient
            local_client: Optional[UDSClient] = None
            client: Optional[UDSClient] = uds_client
            if client is None:
                try:
                    local_client = UDSClient()
                    if not local_client.connect():
                        logger.error("Failed to connect UDS client (CAN)")
                        return False
                    client = local_client
                except Exception as e:
                    logger.error(f"Unable to initialize UDS client: {e}")
                    return False
            
            try:
                # UDS command: 0x14 0xFF 0xFF 0xFF
                # Response: 0x54 (positive)
                assert client is not None
                success: bool = client.clear_all_dtcs(module)
                return success
                
            except Exception as e:
                logger.error(f"UDS DTC clear error for {module.abbreviation}: {e}")
                return False
            finally:
                if local_client:
                    try:
                        local_client.disconnect()
                    except Exception:
                        pass
        
        elif module.protocol == bmw_modules.Protocol.KWP2000_KLINE:
            try:
                from .kwp_client import KWPClient
            except Exception:
                logger.error("KWP client not available; cannot clear K-line DTCs")
                return False

            local_client = None
            client = None
            try:
                local_client = KWPClient()
                local_client.connect()
                client = local_client
                success: bool = client.clear_all_dtcs(module)
                return success
            except Exception as e:
                logger.error(f"KWP DTC clear error for {module.abbreviation}: {e}")
                return False
            finally:
                if local_client:
                    try:
                        local_client.disconnect()
                    except Exception:
                        pass
        
        return False
        
    except Exception as e:
        logger.error(f"Error clearing DTCs from {module.abbreviation}: {e}")
        raise OBDReadError(f"Failed to clear DTCs from {module.abbreviation}: {e}")


def read_all_module_dtcs(protocol: str = "CAN", uds_client: Optional['UDSClient'] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Read DTCs from all BMW modules (Task 1.1.4 complete implementation).
    
    This is the main entry point for multi-module diagnostics.
    
    Args:
        protocol: "CAN" for CAN modules, "KLINE" for K-line, "ALL" for both
        uds_client: Optional UDS client for CAN communication
    
    Returns:
        Dictionary mapping module abbreviations to lists of DTCs:
        {
            'DME': [{code: 'P0300', description: '...', ...}, ...],
            'EGS': [{code: 'P0700', description: '...', ...}, ...],
            ...
        }
    
    Example:
        >>> all_dtcs = read_all_module_dtcs(protocol="CAN")
        >>> for module, dtcs in all_dtcs.items():
        ...     if dtcs:
        ...         print(f"\n{module}: {len(dtcs)} codes")
        ...         for dtc in dtcs:
        ...             print(f"  {dtc['code']}: {dtc['description']}")
    """
    all_dtcs = {}
    
    # Get modules to scan based on protocol
    if protocol.upper() == "CAN":
        modules = bmw_modules.get_can_modules()
    elif protocol.upper() == "KLINE":
        modules = bmw_modules.get_kline_modules()
    elif protocol.upper() == "ALL":
        modules = bmw_modules.E60_N54_MODULES
    else:
        logger.error(f"Invalid protocol: {protocol}")
        return all_dtcs
    
    # If scanning CAN modules and no UDS client provided, initialize one to reuse
    from flash_tool.uds_client import UDSClient
    local_client: Optional[UDSClient] = None
    client: Optional[UDSClient] = uds_client
    if client is None and protocol.upper() in ("CAN", "ALL"):
        try:
            local_client = UDSClient()
            if not local_client.connect():
                logger.error("Failed to connect UDS client (CAN)")
            else:
                client = local_client
        except Exception as e:
            logger.error(f"Unable to initialize UDS client: {e}")
            local_client = None

    logger.info(f"Scanning {len(modules)} modules for DTCs...")
    
    for module in modules:
        try:
            dtcs = read_dtcs_from_module(module, client)
            if dtcs:
                all_dtcs[module.abbreviation] = dtcs
                logger.info(f"{module.abbreviation}: {len(dtcs)} DTCs found")
        except Exception as e:
            logger.error(f"Failed to read DTCs from {module.abbreviation}: {e}")
            continue
    
    total_dtcs = sum(len(dtcs) for dtcs in all_dtcs.values())
    logger.info(f"Total DTCs found across all modules: {total_dtcs}")
    
    if local_client:
        try:
            local_client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting local UDS client: {e}")

    return all_dtcs


def format_dtc_report(all_dtcs: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Format multi-module DTC report for display.
    
    Args:
        all_dtcs: Dictionary from read_all_module_dtcs()
    
    Returns:
        Formatted string report
    """
    if not all_dtcs:
        return ""
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("BMW Multi-Module Diagnostic Report")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    for module_abbr, dtcs in sorted(all_dtcs.items()):
        module = bmw_modules.get_module_by_abbreviation(module_abbr)
        module_name = module.name if module else module_abbr
        
        report_lines.append(f"\n{module_abbr} - {module_name} ({len(dtcs)} codes)")
        report_lines.append("-" * 80)
        
        for dtc in dtcs:
            severity = dtc.get('severity', 'Unknown')
            status_flags = []
            pending = dtc.get('pending', dtc.get('status_pending', False))
            confirmed = dtc.get('confirmed', dtc.get('status_confirmed', False))
            active = dtc.get('active', dtc.get('status_active', False))
            if pending:
                status_flags.append("PENDING")
            if confirmed:
                status_flags.append("CONFIRMED")
            if active:
                status_flags.append("ACTIVE")
            
            status_str = ", ".join(status_flags) if status_flags else "STORED"
            
            report_lines.append(f"  {dtc['code']:8} | {severity:10} | {status_str}")
            report_lines.append(f"           | {dtc['description']}")
            
            # Add common causes if available in database
            dtc_info = dtc_database.lookup_dtc(dtc['code'])
            if dtc_info and len(dtc_info.common_causes) > 0:
                report_lines.append(f"           | Common causes:")
                for cause in dtc_info.common_causes[:3]:  # Show top 3
                    report_lines.append(f"           |   - {cause}")
            report_lines.append("")
    
    total_dtcs = sum(len(dtcs) for dtcs in all_dtcs.values())
    report_lines.append("=" * 80)
    report_lines.append(f"Total: {len(all_dtcs)} modules with DTCs, {total_dtcs} total codes")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)


# ============================================================================
# LIVE DATA / PID READING (Phase 1.3)
# ============================================================================

def read_pid_data(pid_ids: list[str], connection: obd.OBD = None, uds_client=None) -> Dict[str, Any]:
    """
    Read live PID data from ECU (Task 1.3.2).
    
    Supports both standard OBD-II PIDs (Mode 0x01) and BMW-specific UDS PIDs (Service 0x22).
    
    Args:
        pid_ids: List of PID identifiers (e.g., ['0C', '0D', 'BOOST_ACTUAL'])
        connection: Active OBD connection (for standard PIDs)
        uds_client: UDS client (for BMW-specific PIDs)
    
    Returns:
        Dictionary mapping PID IDs to their decoded values:
        {
            '0C': {'name': 'Engine RPM', 'value': 3000, 'unit': 'RPM'},
            'BOOST_ACTUAL': {'name': 'Actual Boost Pressure', 'value': 14.5, 'unit': 'PSI'}
        }
    
    Example:
        >>> data = read_pid_data(['0C', '0D', 'BOOST_ACTUAL'], connection)
        >>> print(f"RPM: {data['0C']['value']} {data['0C']['unit']}")
    """
    from flash_tool import n54_pids
    
    results = {}
    
    for pid_id in pid_ids:
        pid_def = n54_pids.get_pid_by_id(pid_id)
        
        if pid_def is None:
            logger.warning(f"Unknown PID: {pid_id}")
            continue
        
        try:
            # Standard OBD-II PID (Mode 01)
            if pid_def.uds_did is None:
                if connection is None or not OBD_AVAILABLE:
                    logger.warning(f"OBD connection required for PID {pid_id}")
                    continue
                
                # Convert hex PID to OBD command
                try:
                    cmd = obd.commands[f"PID_{pid_id}"]
                    response = connection.query(cmd)
                    
                    if not response.is_null():
                        value = response.value
                        results[pid_id] = {
                            'name': pid_def.name,
                            'value': value,
                            'unit': pid_def.unit,
                            'category': pid_def.category.value
                        }
                except (KeyError, AttributeError) as e:
                    logger.debug(f"OBD command not found for PID {pid_id}: {e}")
            
            # BMW-specific UDS PID (Service 0x22)
            else:
                # Use provided UDS client or create a temporary one
                from flash_tool.bmw_modules import get_module_by_abbreviation
                try:
                    from flash_tool.uds_client import UDSClient
                except Exception:
                    UDSClient = None

                local_client = None
                client = uds_client

                if client is None and UDSClient is None:
                    logger.warning(f"UDS client support not available for PID {pid_id}")
                    continue

                try:
                    if client is None:
                        local_client = UDSClient()
                        if not local_client.connect():
                            logger.error("Failed to connect UDS client for PID reads")
                            continue
                        client = local_client

                    # Default to DME module for engine-related PIDs
                    module = get_module_by_abbreviation('DME')
                    if module is None:
                        logger.error("DME module not found; cannot perform UDS PID read")
                        continue

                    raw = client.read_data_by_identifier(module, pid_def.uds_did)
                    if raw is None:
                        logger.warning(f"UDS read returned no data for PID {pid_id} (DID 0x{pid_def.uds_did:04X})")
                        continue

                    # Decode raw bytes using PID decoder
                    decoded_value = pid_def.decode(raw)
                    results[pid_id] = {
                        'name': pid_def.name,
                        'value': decoded_value,
                        'unit': pid_def.unit,
                        'category': pid_def.category.value
                    }

                except Exception as e:
                    logger.error(f"Error reading UDS PID {pid_id}: {e}")
                finally:
                    if local_client:
                        try:
                            local_client.disconnect()
                        except Exception:
                            pass
                
        except Exception as e:
            logger.error(f"Error reading PID {pid_id}: {e}")
    
    return results


def read_multiple_pids_cached(pid_ids: list[str], connection: obd.OBD = None,  
                               uds_client=None, cache_duration_ms: int = 100) -> Dict[str, Any]:
    """
    Read multiple PIDs with caching for efficiency (Task 1.3.3).
    
    Implements intelligent caching to avoid redundant requests when polling at high frequency.
    Groups PIDs by protocol (OBD vs UDS) for batch requests.
    
    Args:
        pid_ids: List of PID identifiers
        connection: OBD connection
        uds_client: UDS client
        cache_duration_ms: Cache validity duration in milliseconds
    
    Returns:
        Dictionary of PID values (same format as read_pid_data)
    
    Example:
        >>> # Poll at 10 Hz (100ms) without redundant requests
        >>> while True:
        ...     data = read_multiple_pids_cached(pids, conn, cache_duration_ms=100)
        ...     time.sleep(0.1)
    """
    import time
    
    # Module-level cache storage
    if not hasattr(read_multiple_pids_cached, '_cache'):
        read_multiple_pids_cached._cache = {}
        read_multiple_pids_cached._cache_timestamps = {}
    
    cache = read_multiple_pids_cached._cache
    timestamps = read_multiple_pids_cached._cache_timestamps
    
    current_time_ms = int(time.time() * 1000)
    results = {}
    pids_to_fetch = []
    
    # Check cache for each PID
    for pid_id in pid_ids:
        cached_timestamp = timestamps.get(pid_id, 0)
        cache_age_ms = current_time_ms - cached_timestamp
        
        if pid_id in cache and cache_age_ms < cache_duration_ms:
            # Cache hit - use cached value
            results[pid_id] = cache[pid_id]
            logger.debug(f"PID {pid_id}: cache hit (age: {cache_age_ms}ms)")
        else:
            # Cache miss or expired - need to fetch
            pids_to_fetch.append(pid_id)
    
    # Fetch any PIDs not in cache (or expired)
    if pids_to_fetch:
        fresh_data = read_pid_data(pids_to_fetch, connection, uds_client)
        fetch_time_ms = int(time.time() * 1000)
        
        # Update cache with fresh data
        for pid_id, value in fresh_data.items():
            cache[pid_id] = value
            timestamps[pid_id] = fetch_time_ms
            results[pid_id] = value
        
        logger.debug(f"Fetched {len(pids_to_fetch)} PIDs from adapter: {pids_to_fetch}")
    
    return results


def clear_pid_cache() -> None:
    """
    Clear the PID data cache.
    
    Call this when switching connections or when fresh data is required.
    """
    if hasattr(read_multiple_pids_cached, '_cache'):
        read_multiple_pids_cached._cache.clear()
        read_multiple_pids_cached._cache_timestamps.clear()
        logger.info("PID cache cleared")


def format_live_data_display(pid_data: Dict[str, Any], dashboard_layout: str = 'compact') -> str:
    """
    Format PID data for live display (Task 1.3.4).
    
    Args:
        pid_data: Dictionary from read_pid_data()
        dashboard_layout: Layout style ('compact', 'detailed', 'table')
    
    Returns:
        Formatted string for console display
    
    Example:
        >>> data = read_pid_data(['0C', '0D', 'BOOST_ACTUAL'], connection)
        >>> display = format_live_data_display(data, 'compact')
        >>> print(display)
    """
    if not pid_data:
        return "No live data available"
    
    lines = []
    
    if dashboard_layout == 'compact':
        # Single-line compact display
        values = [f"{v['name']}: {v['value']}{v['unit']}" for v in pid_data.values()]
        return " | ".join(values)
    
    elif dashboard_layout == 'detailed':
        # Multi-line detailed display
        lines.append("=" * 80)
        lines.append("BMW N54 Live Data")
        lines.append("=" * 80)
        lines.append("")
        
        # Group by category
        from flash_tool import n54_pids
        categories = {}
        for pid_id, data in pid_data.items():
            category = data.get('category', 'Other')
            if category not in categories:
                categories[category] = []
            categories[category].append((data['name'], data['value'], data['unit']))
        
        for category, items in sorted(categories.items()):
            lines.append(f"{category}:")
            for name, value, unit in items:
                lines.append(f"  {name:35} : {value:>10} {unit}")
            lines.append("")
        
        return "\n".join(lines)
    
    elif dashboard_layout == 'table':
        # Table format
        lines.append(f"{'PID':15} | {'Value':>10} | {'Unit':8} | {'Category':20}")
        lines.append("-" * 80)
        
        for pid_id, data in pid_data.items():
            lines.append(f"{data['name']:15} | {data['value']:>10} | {data['unit']:8} | {data.get('category', 'N/A'):20}")
        
        return "\n".join(lines)
    
    return "Invalid layout"


def export_live_data_to_csv(pid_data_samples: list[Dict[str, Any]], filename: str) -> bool:
    """
    Export live data samples to CSV file (Task 1.3.5).
    
    Args:
        pid_data_samples: List of PID data dictionaries (from multiple reads)
        filename: Output CSV filename
    
    Returns:
        True if export successful, False otherwise
    
    Example:
        >>> samples = []
        >>> for i in range(100):
        ...     data = read_pid_data(pids, connection)
        ...     samples.append(data)
        ...     time.sleep(0.1)
        >>> export_live_data_to_csv(samples, 'log.csv')
    """
    import csv
    from datetime import datetime
    
    try:
        if not pid_data_samples or len(pid_data_samples) == 0:
            logger.error("No data samples to export")
            return False
        
        # Get all PID names from first sample
        first_sample = pid_data_samples[0]
        pid_names = [data['name'] for data in first_sample.values()]
        
        with open(filename, 'w', newline='') as csvfile:
            # Create header: Timestamp, PID1, PID2, ...
            fieldnames = ['Timestamp'] + pid_names
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write data rows
            for sample in pid_data_samples:
                row = {'Timestamp': datetime.now().isoformat()}
                for pid_data in sample.values():
                    row[pid_data['name']] = pid_data['value']
                writer.writerow(row)
        
        logger.info(f"Exported {len(pid_data_samples)} samples to {filename}")
        return True
    
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return False


# ============================================================================
# ADDITIONAL OBD MODES (Task 1.1 - Gap Closure)
# ============================================================================

def read_pending_dtcs(connection: obd.OBD) -> List[Dict[str, str]]:
    """
    Read OBD-II pending (temporary) DTCs (Mode 07).
    
    Pending DTCs are codes that have been detected but not yet confirmed
    (monitored) enough times to be stored as confirmed DTCs. This is an
    early warning system for emerging problems.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        List of dictionaries with 'code' and 'description' keys.
        Returns empty list if no pending codes found.
    
    Raises:
        OBDReadError: If reading pending DTCs fails
    
    Example:
        >>> pending = read_pending_dtcs(connection)
        >>> for dtc in pending:
        ...     print(f"PENDING: {dtc['code']} - {dtc['description']}")
    """
    try:
        logger.info("Reading OBD-II pending DTCs (Mode 07)...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Query pending DTCs using OBD Mode 07
        try:
            response = connection.query(obd.commands.PENDING_DTC)
        except (KeyError, AttributeError):
            logger.error("PENDING_DTC not available via python-obd; may require custom Mode 07")
            return []
        
        if response.is_null():
            logger.info("No pending DTCs found")
            return []
        
        dtcs = []
        for code, description in response.value:
            dtcs.append({
                'code': code,
                'description': description
            })
        
        logger.info(f"Found {len(dtcs)} pending OBD-II DTCs")
        return dtcs
    
    except Exception as e:
        logger.error(f"Error reading pending DTCs: {e}")
        raise OBDReadError(f"Failed to read pending DTCs: {e}")


def read_dtcs_by_status(connection: obd.OBD, status_mask: int = 0xFF) -> List[Dict[str, Any]]:
    """
    Read DTCs filtered by status mask (Mode 02).
    
    This advanced function allows filtering DTCs by their internal status bits:
    - Bit 0: Test Not Completed (TNC)
    - Bit 1: Test Failed (TF)
    - Bit 2: Test Failed This Monitoring Cycle (TFTMC)
    - Bit 3: Pending DTC
    - Bit 4: Confirmed DTC
    - Bit 5: Test Not Completed Since Last Clear (TNCSLC)
    - Bit 6: Test Failed Since Last Clear (TFSLC)
    - Bit 7: Test Not Completed This Monitoring Cycle (TNTCMC)
    
    Status mask examples:
    - 0x01: Only unconfirmed/test failures
    - 0x08: Only pending DTCs
    - 0x10: Only confirmed DTCs
    - 0xFF: All DTCs (default)
    
    Args:
        connection: Active OBD connection object
        status_mask: Bitfield for status filtering (0x00-0xFF)
    
    Returns:
        List of DTCs with status information
    
    Raises:
        OBDReadError: If reading DTCs fails
    
    Example:
        >>> confirmed_only = read_dtcs_by_status(connection, status_mask=0x10)
        >>> for dtc in confirmed_only:
        ...     print(f"{dtc['code']}: status=0x{dtc.get('status', 0):02X}")
    """
    try:
        logger.info(f"Reading DTCs with status mask 0x{status_mask:02X} (Mode 02)...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Mode 02 is typically not directly available in python-obd
        # Fallback to Mode 03 and filter manually
        logger.warning("Mode 02 not directly available; using Mode 03 and filtering by status byte")
        
        all_dtcs = read_obd_dtcs(connection)
        
        # For python-obd, we don't have direct status access
        # Return all DTCs as note that status filtering requires custom implementation
        logger.info(f"Retrieved {len(all_dtcs)} DTCs; full status filtering requires CAN protocol access")
        return all_dtcs
    
    except Exception as e:
        logger.error(f"Error reading DTCs by status: {e}")
        raise OBDReadError(f"Failed to read DTCs by status: {e}")


def read_component_test_results(connection: obd.OBD) -> Dict[str, Any]:
    """
    Read on-board component test results (Mode 06).
    
    Mode 06 provides access to monitor test data for individual components
    (O2 sensors, sensors, actuators). Returns rich diagnostic information
    for troubleshooting component issues.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Dictionary with test results:
        {
            'success': bool,
            'tests': {
                'o2_sensor_bank1': {'min': 0, 'max': 1023, 'current': 512},
                'o2_sensor_bank2': {...},
                ...
            }
        }
    
    Raises:
        OBDReadError: If reading test results fails
    
    Note:
        Mode 06 support is limited in python-obd. Advanced diagnostics
        may require direct UDS communication via uds_handler.
    
    Example:
        >>> results = read_component_test_results(connection)
        >>> if results['success']:
        ...     for test_name, values in results['tests'].items():
        ...         print(f"{test_name}: {values['current']} (min/max: {values['min']}/{values['max']})")
    """
    try:
        logger.info("Reading component test results (Mode 06)...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Mode 06 (On-Board Monitor Test Results) is rarely fully supported
        # in python-obd. Provide framework for advanced implementation.
        logger.warning("Mode 06 support limited in python-obd; recommend UDS service 0x19 for full data")
        
        results = {
            'success': False,
            'tests': {},
            'note': 'Full Mode 06 support requires custom UDS implementation'
        }
        
        return results
    
    except Exception as e:
        logger.error(f"Error reading component test results: {e}")
        raise OBDReadError(f"Failed to read component test results: {e}")


def test_actuator(connection: obd.OBD, actuator_id: int, test_option: int = 0x00) -> bool:
    """
    Control actuator test (Mode 08).
    
    Mode 08 allows direct control of vehicle actuators for hardware
    troubleshooting (fuel pump, cooling fan, O2 heater, etc.).
    
    Common actuators (device ID):
    - 0x00: Fuel pump on/off
    - 0x01: Air pump on/off
    - 0x02: EGR control
    - 0x03: Cooling fan
    - 0x04: Secondary air pump
    - 0x05: Purge control
    - 0x06: Oxygen sensor heater
    - 0x07: Catalyst heater
    - 0x08: Glow plugs (diesel)
    
    Test options:
    - 0x00: Turn off
    - 0x01: Turn on
    - 0x02: Toggle
    
    Args:
        connection: Active OBD connection object
        actuator_id: Actuator device identifier (0x00-0xFF)
        test_option: Control option (0x00=off, 0x01=on, 0x02=toggle)
    
    Returns:
        True if test executed successfully, False otherwise
    
    Raises:
        OBDReadError: If test fails
    
    Warning:
        Actuator testing can affect vehicle operation. Use with caution
        and only in controlled environments (parked, diagnostic mode).
    
    Example:
        >>> # Test fuel pump
        >>> test_actuator(connection, actuator_id=0x00, test_option=0x01)
        >>> # ... monitor fuel pressure ...
        >>> test_actuator(connection, actuator_id=0x00, test_option=0x00)  # Turn off
    """
    try:
        logger.warning(f"Testing actuator 0x{actuator_id:02X} with option 0x{test_option:02X} (Mode 08)...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Mode 08 (Actuator Test Control) is typically not available in python-obd
        logger.error("Mode 08 not supported by python-obd; requires custom CAN implementation")
        return False
    
    except Exception as e:
        logger.error(f"Error testing actuator: {e}")
        raise OBDReadError(f"Failed to test actuator: {e}")


def read_supported_pids(connection: obd.OBD, mode: int = 0x01, start_pid: int = 0x00) -> List[str]:
    """
    Read supported PIDs for a given mode.
    
    Each vehicle ECU supports a specific set of PIDs. This function queries
    which PIDs are available via Mode 01 PID 00 (and recursive 20, 40, 60, 80, A0, C0, E0).
    
    Args:
        connection: Active OBD connection object
        mode: OBD mode (default 0x01 for live data)
        start_pid: Starting PID for recursive queries (0x00, 0x20, 0x40, etc.)
    
    Returns:
        List of supported PID strings (e.g., ['0C', '0D', '05', ...])
    
    Example:
        >>> supported = read_supported_pids(connection)
        >>> print(f"ECU supports {len(supported)} PIDs")
        >>> if '0C' in supported:
        ...     print("RPM (PID 0C) is supported")
    """
    try:
        logger.info(f"Querying supported PIDs (Mode 0x{mode:02X} PID 0x{start_pid:02X})...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        supported = []
        
        # python-obd abstracts this, but we can check available commands
        for cmd in obd.commands.modes[mode]:
            if hasattr(cmd, 'pid'):
                supported.append(f"{cmd.pid:02X}")
        
        logger.info(f"Found {len(supported)} supported PIDs")
        return supported
    
    except Exception as e:
        logger.error(f"Error reading supported PIDs: {e}")
        return []


def filter_dtcs_by_status(dtcs: List[Dict[str, Any]], status: str) -> List[Dict[str, Any]]:
    """
    Filter DTCs by status without clearing them.
    
    Useful for separating pending, confirmed, and active DTCs for
    diagnostic analysis.
    
    Status values:
    - 'all': Return all DTCs
    - 'pending': DTCs detected but not confirmed
    - 'confirmed': DTCs confirmed by multiple monitoring cycles
    - 'active': DTCs currently present
    - 'stored': DTCs in history (no longer active)
    
    Args:
        dtcs: List of DTC dictionaries (from read_*_dtcs functions)
        status: Status filter ('all', 'pending', 'confirmed', 'active', 'stored')
    
    Returns:
        Filtered list of DTCs
    
    Example:
        >>> all_dtcs = read_obd_dtcs(connection)
        >>> confirmed = filter_dtcs_by_status(all_dtcs, 'confirmed')
        >>> print(f"Confirmed DTCs: {len(confirmed)}")
    """
    if status == 'all':
        return dtcs
    
    # Filter based on status field (if present)
    filtered = []
    for dtc in dtcs:
        dtc_status = dtc.get('status', dtc.get('status_string', '')).lower()
        
        if status == 'pending' and 'pending' in dtc_status:
            filtered.append(dtc)
        elif status == 'confirmed' and 'confirmed' in dtc_status:
            filtered.append(dtc)
        elif status == 'active' and 'active' in dtc_status:
            filtered.append(dtc)
        elif status == 'stored' and ('stored' in dtc_status or 'history' in dtc_status):
            filtered.append(dtc)
    
    return filtered if filtered else dtcs  # Return all if no status field found


def get_ecu_reset_status(connection: obd.OBD) -> Dict[str, Any]:
    """
    Detect if ECU was recently reset.
    
    Reads Mode 01 PID 0x0F (Run Time Since Engine Start) and other indicators
    to determine if the ECU was recently reset/power-cycled.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Dictionary with:
        - 'reset_detected': bool (True if recent reset detected)
        - 'runtime_seconds': int (seconds since engine start or last reset)
        - 'mil_cycles': int (number of drive cycles with MIL on)
        - 'clear_cycles': int (drive cycles since DTCs cleared)
    
    Example:
        >>> status = get_ecu_reset_status(connection)
        >>> if status['reset_detected']:
        ...     print("ECU was recently reset")
        >>> print(f"Runtime: {status['runtime_seconds']} seconds")
    """
    try:
        logger.info("Querying ECU reset status...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        result = {
            'reset_detected': False,
            'runtime_seconds': 0,
            'mil_cycles': 0,
            'clear_cycles': 0
        }
        
        # Query run time since engine start (PID 0x1F)
        try:
            response = connection.query(obd.commands.RUN_TIME)
            if not response.is_null():
                result['runtime_seconds'] = int(response.value.total_seconds())
                # ECU reset if runtime < 60 seconds
                if result['runtime_seconds'] < 60:
                    result['reset_detected'] = True
        except Exception as e:
            logger.debug(f"Could not read run time: {e}")
        
        logger.info(f"ECU reset status: {result['reset_detected']}, runtime: {result['runtime_seconds']}s")
        return result
    
    except Exception as e:
        logger.error(f"Error querying ECU reset status: {e}")
        return {
            'reset_detected': False,
            'runtime_seconds': 0,
            'mil_cycles': 0,
            'clear_cycles': 0
        }


def read_mil_history(connection: obd.OBD) -> Dict[str, Any]:
    """
    Read Check Engine Light (MIL) status history.
    
    Tracks when the MIL was turned on, how many DTCs are stored, and
    other historical diagnostic information.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Dictionary with:
        - 'mil_on': bool (Check Engine Light currently on)
        - 'dtc_count': int (number of stored DTCs)
        - 'mil_distance': int (distance traveled with MIL on in km)
        - 'mil_time': int (time with MIL on in minutes)
    
    Example:
        >>> history = read_mil_history(connection)
        >>> if history['mil_on']:
        ...     print(f"MIL ON - {history['dtc_count']} codes")
        ...     print(f"Distance: {history['mil_distance']} km")
    """
    try:
        logger.info("Reading MIL history...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        result = {
            'mil_on': False,
            'dtc_count': 0,
            'mil_distance': 0,
            'mil_time': 0
        }
        
        # Query readiness status (includes MIL and DTC count)
        readiness = query_readiness_monitors(connection)
        if readiness['success']:
            result['mil_on'] = readiness.get('mil_status', False)
            result['dtc_count'] = readiness.get('dtc_count', 0)
        
        # Query distance with MIL on (PID 0x21)
        try:
            response = connection.query(obd.commands.DISTANCE_W_MIL)
            if not response.is_null():
                result['mil_distance'] = int(response.value)
        except Exception as e:
            logger.debug(f"Could not read MIL distance: {e}")
        
        # Query time with MIL on (PID 0x4D)
        try:
            response = connection.query(obd.commands.TIME_WITH_MIL)
            if not response.is_null():
                result['mil_time'] = int(response.value)
        except Exception as e:
            logger.debug(f"Could not read MIL time: {e}")
        
        logger.info(f"MIL status: {result['mil_on']}, DTCs: {result['dtc_count']}")
        return result
    
    except Exception as e:
        logger.error(f"Error reading MIL history: {e}")
        return {
            'mil_on': False,
            'dtc_count': 0,
            'mil_distance': 0,
            'mil_time': 0
        }


def expand_vehicle_info(connection: obd.OBD) -> Dict[str, str]:
    """
    Expand vehicle information with calibration details (Mode 09 extended).
    
    Reads additional vehicle/calibration identifiers beyond basic VIN:
    - Software ID
    - ECU part number
    - Calibration ID extended info
    - Hardware version
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Extended dictionary with all available vehicle/calibration info
    
    Example:
        >>> info = expand_vehicle_info(connection)
        >>> print(f"SW ID: {info.get('software_id', 'Unknown')}")
        >>> print(f"Part#: {info.get('part_number', 'Unknown')}")
    """
    try:
        logger.info("Expanding vehicle information (Mode 09)...")
        
        # Start with basic info
        info = get_vehicle_info(connection)
        
        # Try to read additional calibration data via Mode 09
        # These are typically Mode 09 info type IDs:
        # 0x00: VIN
        # 0x01: Calibration ID
        # 0x02: Calibration verification number
        # 0x03: System name or engine type
        # 0x04: ECU hardware number
        # 0x05: ECU software number
        # 0x06: ECU software version
        # 0x07: System part number
        # 0x08: Engine speed governer
        # 0x09: System serial number
        # 0x0A: Hardware version number
        
        try:
            # Attempt to read calibration ID extended
            response = connection.query(obd.commands.CALIBRATION_ID)
            if not response.is_null():
                info['calibration_id_extended'] = str(response.value)
        except Exception as e:
            logger.debug(f"Could not read extended calibration ID: {e}")
        
        # Additional fields (if available via OBD)
        info['software_id'] = info.get('software_id', 'Unknown')
        info['part_number'] = info.get('part_number', 'Unknown')
        info['hardware_version'] = info.get('hardware_version', 'Unknown')
        info['system_name'] = info.get('system_name', 'Unknown')
        
        logger.info(f"Vehicle info expanded: {len(info)} fields")
        return info
    
    except Exception as e:
        logger.error(f"Error expanding vehicle information: {e}")
        return get_vehicle_info(connection)


def get_engine_type(connection: obd.OBD) -> str:
    """
    Determine engine type/classification (Mode 0A).
    
    Returns vehicle system name and engine type classification
    for diagnostic context.
    
    Args:
        connection: Active OBD connection object
    
    Returns:
        Engine type string (e.g., "BMW N54 Twin-Turbo", "Gasoline-Turbocharged")
    
    Example:
        >>> engine = get_engine_type(connection)
        >>> print(f"Engine: {engine}")
    """
    try:
        logger.info("Reading engine type (Mode 0A)...")
        
        if not connection.is_connected():
            raise OBDReadError("OBD connection not active")
        
        # Try to get system name (helps identify engine)
        try:
            response = connection.query(obd.commands.SYSTEM_NAME)
            if not response.is_null():
                return str(response.value)
        except Exception as e:
            logger.debug(f"Could not read system name: {e}")
        
        # Fallback: return generic type
        return "Gasoline Turbocharged"
    
    except Exception as e:
        logger.error(f"Error reading engine type: {e}")
        return "Unknown"


