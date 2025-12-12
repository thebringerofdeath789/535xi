#!/usr/bin/env python3
"""
BMW N54 Native Protocol Implementation - Direct CAN Communication
==================================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Direct implementation of BMW diagnostic protocols for N54 ECU
    (MSD80/MSD81). Uses direct CAN/UDS communication with python-can
    library for standalone, cross-platform operation.
    
    Implements BMW diagnostic protocols per ISO standards and BMW specifications.

Implemented Protocols:
    - KWP2000 over CAN (ISO 14230 - older BMW protocol)
    - UDS over CAN (ISO 14229 - modern protocol)
    - BMW-specific diagnostic services
    - N54-specific data identifiers

Classes:
    BMWCAN - CAN bus configuration constants
    N54DataIdentifier(IntEnum) - BMW-specific data identifiers
    N54Routine(IntEnum) - Diagnostic routine identifiers
    UDSService(IntEnum) - UDS service identifiers (ISO 14229)
    DiagnosticSession(IntEnum) - Session types
    SecurityLevel(IntEnum) - Security access levels
    ECUReset(IntEnum) - Reset types
    N54DiagnosticData - Diagnostic data container
    BMWN54Protocol - Main protocol handler

Functions:
    None (class-based module)

Variables (Module-level):
    CAN_AVAILABLE: bool - python-can library availability
    logger: logging.Logger - Module logger
"""

import struct
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import IntEnum

try:
    import can
    from can import Message
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False
    can = None
    Message = None

logger = logging.getLogger(__name__)


# =============================================================================
# BMW N54 MSD80/MSD81 CAN Configuration
# =============================================================================

class BMWCAN:
    """BMW N54 CAN bus configuration."""
    # CAN IDs for DME/ECU communication
    ECU_TX_ID = 0x6F1  # Tester → ECU
    ECU_RX_ID = 0x6F9  # ECU → Tester
    
    # CAN bus speed
    BITRATE = 500000  # 500 kbps (PT-CAN)
    
    # Timing
    P2_TIMEOUT = 0.150  # 150ms normal response
    P2_STAR_TIMEOUT = 2.0  # 2s extended response
    TESTER_PRESENT_INTERVAL = 2.0  # Keep-alive every 2s


# =============================================================================
# BMW Data Identifiers (DIDs) - N54 Specific
# =============================================================================

class N54DataIdentifier(IntEnum):
    """BMW N54 data identifiers for Read Data By ID service (UDS 0x22).
    
    Based on BMW diagnostic specifications and binary analysis.
    Standard UDS DIDs (0xF000-0xFFFF) follow ISO 14229.
    BMW-specific DIDs (0x0000-0x0FFF) are manufacturer-defined.
    """
    
    # Standard UDS Identification DIDs (ISO 14229)
    VIN = 0xF190                    # Vehicle Identification Number
    SW_VERSION = 0xF189             # Software version (e.g., I8A0S)
    HW_VERSION = 0xF19D             # Hardware version
    ECU_SERIAL = 0xF18C             # ECU serial number
    SUPPLIER_ID = 0xF18A            # ECU supplier
    BUILD_DATE = 0xF199             # ECU manufacturing date
    
    # Additional UDS Identification DIDs
    UDS_ID_F181 = 0xF181            # UDS identification parameter
    UDS_ID_F186 = 0xF186            # UDS identification parameter
    UDS_ID_F19C = 0xF19C            # UDS identification parameter
    UDS_ID_F19E = 0xF19E            # UDS identification parameter
    UDS_ID_F1A1 = 0xF1A1            # UDS identification parameter
    UDS_ID_F1BD = 0xF1BD            # UDS identification parameter
    
    # Basic Engine Sensors
    COOLANT_TEMP = 0x0005           # Coolant temperature
    BOOST_PRESSURE = 0x000B         # Turbo boost pressure
    ENGINE_RPM = 0x000F             # Engine speed
    
    # VANOS (Variable Valve Timing)
    VANOS_INTAKE_TARGET = 0x0031    # Intake VANOS target position
    VANOS_EXHAUST_TARGET = 0x0033   # Exhaust VANOS target position
    VANOS_INTAKE_ACTUAL = 0x0034    # Intake VANOS actual position
    VANOS_EXHAUST_ACTUAL = 0x0039   # Exhaust VANOS actual position
    VANOS_ALT = 0x003B              # Alternative VANOS parameter
    
    # Wastegate/Boost Control
    WGDC_TARGET = 0x0041            # Wastegate duty cycle target
    WGDC_ACTUAL = 0x004A            # Wastegate duty cycle actual
    
    # N54 Injector System
    INJECTOR_CODES = 0x0600         # Individual injector correction codes (IKS)
    INJECTOR_DATA_606 = 0x0606      # Injector data
    INJECTOR_DATA_610 = 0x0610      # Injector-related parameter
    
    # N54 Engine Management
    ENGINE_PARAM_62C = 0x062C       # Engine parameter
    
    # N54 Sensors
    SENSOR_DATA_652 = 0x0652        # Sensor data
    SENSOR_DATA_657 = 0x0657        # Sensor data
    
    # N54 Fuel System
    FUEL_PARAM_8C = 0x008C          # Fuel system parameter
    FUEL_PARAM_6B5 = 0x06B5         # Fuel parameter
    FUEL_PARAM_6B9 = 0x06B9         # Fuel parameter
    
    # Temperatures
    TEMP_SENSOR_B8 = 0x00B8         # Temperature sensor
    
    # BMW Parameters
    BMW_PARAM_D1 = 0x00D1           # BMW parameter
    
    # N54 Miscellaneous
    N54_PARAM_6CD = 0x06CD          # N54 parameter
    N54_PARAM_6E6 = 0x06E6          # N54 parameter
    
    # Lambda Sensors
    LAMBDA_BANK1 = 0x0024           # Lambda sensor bank 1
    LAMBDA_BANK2 = 0x0025           # Lambda sensor bank 2
    
    # Fault Codes
    DTC_STATUS = 0x0401             # Diagnostic trouble code status
    DTC_SNAPSHOT = 0x0402           # Freeze frame data


# =============================================================================
# BMW Routine Identifiers - N54 Specific
# =============================================================================

class N54Routine(IntEnum):
    """BMW N54 routine identifiers for Routine Control service."""
    CLEAR_DTC = 0xFF00  # Clear all diagnostic trouble codes
    CLEAR_ADAPTATIONS = 0xFF01  # Clear all adaptive values
    INJECTOR_TEST = 0x0201  # Injector cylinder cutout test
    VANOS_TEST = 0x0202  # VANOS actuation test
    WGDC_TEST = 0x0203  # Wastegate duty cycle test


# =============================================================================
# UDS Service Implementation
# =============================================================================

class UDSService(IntEnum):
    """UDS Service IDs (ISO 14229)."""
    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    SECURITY_ACCESS = 0x27
    COMMUNICATION_CONTROL = 0x28
    TESTER_PRESENT = 0x3E
    READ_DATA_BY_ID = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    READ_SCALING_DATA_BY_ID = 0x24
    WRITE_DATA_BY_ID = 0x2E
    WRITE_MEMORY_BY_ADDRESS = 0x3D
    CLEAR_DTC = 0x14
    READ_DTC = 0x19
    IO_CONTROL_BY_ID = 0x2F
    ROUTINE_CONTROL = 0x31
    REQUEST_DOWNLOAD = 0x34
    REQUEST_UPLOAD = 0x35
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37


class DiagnosticSession(IntEnum):
    """Diagnostic session types (UDS Service 0x10).
    
    BMW N54 MSD80/MSD81 session types:
    - 0x87: BMW Extended Session
    - 0x02: Programming Session
    """
    DEFAULT = 0x01
    PROGRAMMING = 0x02
    EXTENDED_DIAGNOSTIC = 0x03
    SAFETY_SYSTEM = 0x04
    BMW_FLASH = 0x85  # BMW-specific: suppress positive response + programming
    BMW_EXTENDED = 0x87  # BMW-specific extended diagnostic


class SecurityLevel(IntEnum):
    """BMW Security Access Levels (UDS Service 0x27).
    
    BMW N54 MSD80/MSD81 security access levels:
    - 0x27 0x01: Request Seed Level 1
    - 0x27 0x02: Send Key Level 1
    - 0x27 0x03: Request Seed Level 3
    - 0x27 0x11: Request Seed Level 17 (Programming)
    - 0x27 0x12: Send Key Level 17 (Programming)
    
    Seed/Key Algorithm Mapping:
    - Level 1: XOR with 'MH' (0x4D48) + cross-XOR (algorithm_v1)
    - Level 3: Byte swap + 'MH' XOR variant (algorithm_v2)
    - Level 17: XOR with 'BM' (0x424D) for programming (algorithm_v3)
    """
    # Request seed levels (odd numbers)
    DIAGNOSTIC_LEVEL_1 = 0x01      # Basic diagnostic security
    DIAGNOSTIC_LEVEL_3 = 0x03      # Enhanced diagnostic security
    PROGRAMMING_LEVEL_17 = 0x11    # Programming/flash security (CRITICAL)
    
    # Send key levels (even numbers = request + 1)
    DIAGNOSTIC_KEY_1 = 0x02        # Key for level 1
    DIAGNOSTIC_KEY_3 = 0x04        # Key for level 3
    PROGRAMMING_KEY_17 = 0x12      # Key for level 17


class ECUReset(IntEnum):
    """ECU reset types."""
    HARD_RESET = 0x01
    KEY_OFF_ON = 0x02
    SOFT_RESET = 0x03
    ENABLE_RAPID_SHUTDOWN = 0x04
    DISABLE_RAPID_SHUTDOWN = 0x05


@dataclass
@dataclass
class N54DiagnosticData:
    """Container for N54 diagnostic data."""
    vin: Optional[str] = None
    sw_version: Optional[str] = None
    hw_version: Optional[str] = None
    supplier: Optional[str] = None
    build_date: Optional[str] = None
    injector_codes: Optional[List[float]] = None
    runtime_hours: Optional[float] = None
    flash_count: Optional[int] = None


# =============================================================================
# Main BMW Protocol Class
# =============================================================================

class BMWN54Protocol:
    """
    Native BMW N54 protocol implementation.
    
    Implements direct CAN communication with MSD80/MSD81 ECU using:
    - ISO-TP (ISO 15765-2) transport layer
    - UDS (ISO 14229) diagnostic services
    - BMW-specific data identifiers
    
    Uses python-can library for cross-platform CAN communication.
    
    Example:
        >>> from flash_tool.bmw_protocol import BMWN54Protocol
        >>> 
        >>> ecu = BMWN54Protocol('pcan', 'PCAN_USBBUS1')
        >>> ecu.connect()
        >>> 
        >>> # Read VIN
        >>> vin = ecu.read_vin()
        >>> print(f"VIN: {vin}")
        >>> 
        >>> # Read software version
        >>> sw = ecu.read_software_version()
        >>> print(f"Software: {sw}")
        >>> 
        >>> # Read injector codes
        >>> codes = ecu.read_injector_codes()
        >>> for i, code in enumerate(codes, 1):
        ...     print(f"Cylinder {i}: {code:.2f}")
        >>> 
        >>> # Read live data
        >>> rpm = ecu.read_rpm()
        >>> boost = ecu.read_boost_pressure()
        >>> print(f"RPM: {rpm}, Boost: {boost:.2f} bar")
        >>> 
        >>> ecu.disconnect()
    """
    
    def __init__(self, interface: str = 'pcan', channel: str = 'PCAN_USBBUS1'):
        """
        Initialize BMW N54 protocol handler.
        
        Args:
            interface: CAN interface type ('pcan', 'socketcan', etc.)
            channel: CAN channel identifier
        """
        if not CAN_AVAILABLE:
            raise ImportError(
                "python-can not installed. Install with: pip install python-can"
            )
        
        self.interface = interface
        self.channel = channel
        self.bus: Optional[object] = None
        self.session_active = False
        self.last_tester_present = 0.0
        
        # Import ISO-TP functionality from direct_can_flasher
        from . import direct_can_flasher
        self.flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        logger.info(f"BMW N54 Protocol initialized: {interface} {channel}")
    
    def connect(self) -> bool:
        """
        Connect to ECU via CAN bus.
        
        Returns:
            bool: True if connected successfully
        """
        return self.flasher.connect()
    
    def disconnect(self):
        """Disconnect from CAN bus."""
        self.flasher.disconnect()
        self.session_active = False
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def start_diagnostic_session(self, session_type: DiagnosticSession = DiagnosticSession.EXTENDED_DIAGNOSTIC) -> bool:
        """
        Start diagnostic session.
        
        Args:
            session_type: Type of diagnostic session
            
        Returns:
            bool: True if session started successfully
        """
        if not self.flasher.bus:
            logger.error("Cannot start diagnostic session: Not connected to ECU")
            return False
        
        logger.info(f"Starting diagnostic session: {session_type.name}")
        
        response = self.flasher.send_uds_request(
            UDSService.DIAGNOSTIC_SESSION_CONTROL,
            bytes([session_type])
        )
        
        if response and response[0]:
            self.session_active = True
            logger.info("Diagnostic session started")
            return True
        
        logger.error("Failed to start diagnostic session")
        return False
    
    def send_tester_present(self) -> bool:
        """
        Send tester present keep-alive message.
        
        Should be called periodically (every 2-3 seconds) during
        extended diagnostic operations.
        
        Returns:
            bool: True if acknowledged
        """
        if not self.flasher.bus:
            logger.warning("Cannot send tester present: Not connected to ECU")
            return False
        
        response = self.flasher.send_uds_request(
            UDSService.TESTER_PRESENT,
            bytes([0x00])  # No response required
        )
        
        self.last_tester_present = time.time()
        
        if response is not None:
            logger.debug("Tester present acknowledged")
            return True
        
        logger.debug("Tester present not acknowledged (may be normal)")
        return False
    
    # =========================================================================
    # ECU Identification
    # =========================================================================
    
    def read_data_by_id(self, did: int) -> Optional[bytes]:
        """
        Read data by identifier (generic).
        
        Args:
            did: Data identifier
            
        Returns:
            bytes: Response data or None if failed
        """
        if not self.flasher.bus:
            logger.error(f"Cannot read DID 0x{did:04X}: Not connected to ECU")
            return None
        
        response = self.flasher.send_uds_request(
            UDSService.READ_DATA_BY_ID,
            struct.pack('>H', did)
        )
        
        if response and response[0]:
            # Response format: [service+0x40, DID_high, DID_low, ...data...]
            if len(response[1]) < 3:
                logger.error(f"Invalid response for DID 0x{did:04X} (too short: {len(response[1])} bytes)")
                return None
            return response[1][3:]  # Skip service echo and DID
        
        logger.debug(f"Failed to read DID 0x{did:04X}")
        return None
    
    def read_vin(self) -> Optional[str]:
        """
        Read Vehicle Identification Number.
        
        Returns:
            str: 17-character VIN or None if failed
        """
        logger.info("Reading VIN...")
        data = self.read_data_by_id(N54DataIdentifier.VIN)
        
        if data and len(data) >= 17:
            vin = data[:17].decode('ascii', errors='ignore').strip()
            
            # Validate VIN format (17 alphanumeric characters)
            if len(vin) == 17 and vin.isalnum():
                logger.info(f"VIN: {vin}")
                return vin
            else:
                logger.warning(f"Invalid VIN format received: {vin} (length: {len(vin)})")
                return None
        
        logger.error(f"Failed to read VIN (received {len(data) if data else 0} bytes)")
        return None
    
    def read_software_version(self) -> Optional[str]:
        """
        Read ECU software version (e.g., I8A0S).
        
        Returns:
            str: Software version or None if failed
        """
        logger.info("Reading software version...")
        data = self.read_data_by_id(N54DataIdentifier.SW_VERSION)
        
        if data:
            sw_version = data.decode('ascii', errors='ignore').strip()
            logger.info(f"Software: {sw_version}")
            return sw_version
        
        logger.error("Failed to read software version")
        return None
    
    def read_hardware_version(self) -> Optional[str]:
        """
        Read ECU hardware version.
        
        Returns:
            str: Hardware version or None if failed
        """
        logger.info("Reading hardware version...")
        data = self.read_data_by_id(N54DataIdentifier.HW_VERSION)
        
        if data:
            hw_version = data.decode('ascii', errors='ignore').strip()
            logger.info(f"Hardware: {hw_version}")
            return hw_version
        
        return None
    
    def read_ecu_identification(self) -> N54DiagnosticData:
        """
        Read complete ECU identification.
        
        Returns:
            N54DiagnosticData: Complete identification data
        """
        logger.info("Reading ECU identification...")
        
        ident = N54DiagnosticData()
        ident.vin = self.read_vin()
        ident.sw_version = self.read_software_version()
        ident.hw_version = self.read_hardware_version()
        
        # Read supplier
        supplier_data = self.read_data_by_id(N54DataIdentifier.SUPPLIER_ID)
        if supplier_data:
            ident.supplier = supplier_data.decode('ascii', errors='ignore').strip()
        
        # Read build date
        date_data = self.read_data_by_id(N54DataIdentifier.BUILD_DATE)
        if date_data:
            ident.build_date = date_data.decode('ascii', errors='ignore').strip()
        
        return ident
    
    # =========================================================================
    # N54-Specific Data
    # =========================================================================
    
    def read_injector_codes(self) -> Optional[List[float]]:
        """
        Read N54 injector correction codes (IKS).
        
        Each cylinder has an individual flow correction value.
        
        Returns:
            List[float]: 6 injector codes (cylinders 1-6) or None if failed
        """
        logger.info("Reading injector codes...")
        data = self.read_data_by_id(N54DataIdentifier.INJECTOR_CODES)
        
        if data and len(data) >= 12:  # 6 cylinders × 2 bytes each
            codes = []
            for i in range(6):
                # Each code is a signed 16-bit value
                raw_value = struct.unpack('>h', data[i*2:i*2+2])[0]
                # Convert to percentage (typical range: -10% to +10%)
                code = raw_value / 100.0
                
                # Validate reasonable range (BMW spec: typically -30% to +30%)
                if abs(code) > 50.0:
                    logger.warning(f"Cylinder {i+1} injector code out of range: {code:.2f}%")
                
                codes.append(code)
            
            logger.info(f"Injector codes: {codes}")
            return codes
        
        logger.error(f"Failed to read injector codes (received {len(data) if data else 0} bytes, expected 12)")
        return None
    
    def read_flash_counter(self) -> Optional[int]:
        """
        Read ECU flash counter from memory.
        
        MSD80 tracks the number of times it's been flashed in a counter
        at memory offset 0x1F0000 (4 bytes, big-endian).
        
        Returns:
            int: Flash count (0-4294967295) or None if failed
        """
        logger.info("Reading flash counter from memory...")
        
        try:
            # Read 4 bytes from flash counter location
            address = 0x1F0000
            size = 4
            data = self.flasher.read_memory(address, size)
            
            if data and len(data) >= size:
                counter = int.from_bytes(data[:size], 'big')
                
                # Sanity check: flash counter should be reasonable (0-10000)
                # 0xFFFFFFFF indicates unprogrammed/erased memory
                if counter == 0xFFFFFFFF:
                    logger.warning("Flash counter appears unprogrammed (0xFFFFFFFF)")
                    return 0
                elif counter > 10000:
                    logger.warning(f"Flash counter suspiciously high: {counter} (possible data corruption)")
                
                logger.info(f"Flash counter: {counter}")
                return counter
            
            logger.error(f"Failed to read flash counter data (received {len(data) if data else 0} bytes)")
            return None
        except Exception as e:
            logger.error(f"Flash counter read error: {e}")
            return None
    
    def read_engine_runtime(self) -> Optional[float]:
        """
        Read total engine runtime from ECU.
        
        Reads DID 0x0610 which contains injector-related data that may
        include engine runtime information. Data format is 16 bytes.
        
        Returns:
            float: Runtime in hours or None if data unavailable
        """
        logger.info("Reading engine runtime data...")
        data = self.read_data_by_id(N54DataIdentifier.INJECTOR_DATA_610)
        
        if data and len(data) >= 16:
            logger.info(f"Runtime data received (16 bytes): {data.hex()}")
            # Attempt to parse runtime from bytes 0-3 (common format: seconds as uint32)
            try:
                runtime_seconds = int.from_bytes(data[0:4], 'big')
                
                # Sanity check: runtime should be reasonable
                # Max realistic: 100,000 hours = 11.4 years continuous running
                if runtime_seconds == 0xFFFFFFFF:
                    logger.warning("Runtime appears unprogrammed (0xFFFFFFFF)")
                    return None
                
                runtime_hours = runtime_seconds / 3600.0
                
                if runtime_hours > 100000:
                    logger.warning(f"Runtime suspiciously high: {runtime_hours:.1f} hours (possible wrong interpretation)")
                
                logger.info(f"Engine runtime: {runtime_hours:.1f} hours ({runtime_hours/24:.1f} days)")
                return runtime_hours
            except Exception as e:
                logger.warning(f"Failed to parse runtime data: {e}")
                return None
        
        logger.error(f"Failed to read engine runtime (received {len(data) if data else 0} bytes, expected 16)")
        return None
    
    # =========================================================================
    # Live Sensor Data
    # =========================================================================
    
    def read_rpm(self) -> Optional[int]:
        """
        Read current engine RPM.
        
        Returns:
            int: RPM or None if failed
        """
        data = self.read_data_by_id(N54DataIdentifier.ENGINE_RPM)
        
        if data and len(data) >= 2:
            rpm = struct.unpack('>H', data[:2])[0]
            
            # Validate RPM is in reasonable range (N54 redline: ~7000 RPM)
            if rpm > 9000:
                logger.warning(f"RPM out of expected range: {rpm} (possible data error)")
            
            return rpm
        
        return None
    
    def read_coolant_temp(self) -> Optional[float]:
        """
        Read coolant temperature.
        
        Returns:
            float: Temperature in °C or None if failed
        """
        data = self.read_data_by_id(N54DataIdentifier.COOLANT_TEMP)
        
        if data and len(data) >= 1:
            # Typically: value - 40 = °C
            temp = data[0] - 40
            
            # Validate temperature is reasonable (-40°C to 150°C)
            if temp < -40 or temp > 150:
                logger.warning(f"Coolant temp out of range: {temp}°C (possible sensor error)")
            
            return float(temp)
        
        return None
    
    def read_boost_pressure(self) -> Optional[float]:
        """
        Read turbo boost pressure.
        
        Returns:
            float: Pressure in bar or None if failed
        """
        data = self.read_data_by_id(N54DataIdentifier.BOOST_PRESSURE)
        
        if data and len(data) >= 2:
            # Typical encoding: value / 100 = bar
            pressure_raw = struct.unpack('>H', data[:2])[0]
            pressure = pressure_raw / 100.0
            
            # Validate pressure is reasonable (N54: -1 bar to +2.5 bar typical)
            if pressure < -1.5 or pressure > 3.0:
                logger.warning(f"Boost pressure out of expected range: {pressure:.2f} bar")
            
            return pressure
        
        return None
    
    def read_vanos_data(self) -> Optional[Dict[str, float]]:
        """
        Read VANOS actuator positions.
        
        Returns:
            dict: VANOS data (intake/exhaust actual/target) or None if failed
        """
        vanos = {}
        
        intake_actual = self.read_data_by_id(N54DataIdentifier.VANOS_INTAKE_ACTUAL)
        if intake_actual and len(intake_actual) >= 2:
            vanos['intake_actual'] = struct.unpack('>h', intake_actual[:2])[0] / 10.0
        
        intake_target = self.read_data_by_id(N54DataIdentifier.VANOS_INTAKE_TARGET)
        if intake_target and len(intake_target) >= 2:
            vanos['intake_target'] = struct.unpack('>h', intake_target[:2])[0] / 10.0
        
        exhaust_actual = self.read_data_by_id(N54DataIdentifier.VANOS_EXHAUST_ACTUAL)
        if exhaust_actual and len(exhaust_actual) >= 2:
            vanos['exhaust_actual'] = struct.unpack('>h', exhaust_actual[:2])[0] / 10.0
        
        exhaust_target = self.read_data_by_id(N54DataIdentifier.VANOS_EXHAUST_TARGET)
        if exhaust_target and len(exhaust_target) >= 2:
            vanos['exhaust_target'] = struct.unpack('>h', exhaust_target[:2])[0] / 10.0
        
        # Validate VANOS values are in reasonable range (-90° to +90°)
        for key, value in vanos.items():
            if abs(value) > 90:
                logger.warning(f"VANOS {key} out of range: {value:.1f}° (typical: -50° to +50°)")
        
        return vanos if vanos else None
    
    def read_boost_control_data(self) -> Optional[Dict[str, float]]:
        """
        Read wastegate/boost control data.
        
        Returns:
            dict: Boost control data or None if failed
        """
        boost = {}
        
        wgdc_actual = self.read_data_by_id(N54DataIdentifier.WGDC_ACTUAL)
        if wgdc_actual and len(wgdc_actual) >= 1:
            boost['wgdc_actual'] = wgdc_actual[0] / 2.55  # Convert to %
        
        wgdc_target = self.read_data_by_id(N54DataIdentifier.WGDC_TARGET)
        if wgdc_target and len(wgdc_target) >= 1:
            boost['wgdc_target'] = wgdc_target[0] / 2.55
        
        # Note: Boost target pressure DID not yet verified
        # DID 0x004A appears to be WGDC_ACTUAL, not boost target pressure
        
        return boost if boost else None
    
    # =========================================================================
    # Diagnostic Trouble Codes (DTCs)
    # =========================================================================
    
    def read_dtcs(self) -> Optional[List[Dict[str, Any]]]:
        """
        Read diagnostic trouble codes.
        
        Returns:
            List[dict]: List of DTCs with code and status or None if failed
        """
        logger.info("Reading DTCs...")
        
        # UDS Service 0x19: Read DTC Information
        # Sub-function 0x02: Report DTC by status mask
        response = self.flasher.send_uds_request(
            UDSService.READ_DTC,
            bytes([0x02, 0xFF])  # All DTCs
        )
        
        if not response or not response[0]:
            logger.error("Failed to read DTCs (no response from ECU)")
            return None
        
        if len(response[1]) < 2:
            logger.error(f"Invalid DTC response (too short: {len(response[1])} bytes)")
            return None
        
        data = response[1][2:]  # Skip service echo and sub-function
        
        dtcs = []
        i = 0
        while i < len(data) - 3:
            # DTC format: 3 bytes (DTC code) + 1 byte (status)
            dtc_bytes = data[i:i+3]
            status = data[i+3]
            
            # Convert to standard format (P0XXX, etc.)
            dtc_code = self._decode_dtc(dtc_bytes)
            
            dtcs.append({
                'code': dtc_code,
                'status': status,
                'active': (status & 0x01) != 0,
                'pending': (status & 0x04) != 0
            })
            
            i += 4
        
        logger.info(f"Found {len(dtcs)} DTCs")
        return dtcs
    
    def clear_dtcs(self) -> bool:
        """
        Clear all diagnostic trouble codes.
        
        Returns:
            bool: True if cleared successfully
        """
        logger.info("Clearing DTCs...")
        
        # UDS Service 0x14: Clear Diagnostic Information
        response = self.flasher.send_uds_request(
            UDSService.CLEAR_DTC,
            bytes([0xFF, 0xFF, 0xFF])  # Clear all groups
        )
        
        if response and response[0]:
            logger.info("DTCs cleared")
            return True
        
        logger.error("Failed to clear DTCs")
        return False
    
    def _decode_dtc(self, dtc_bytes: bytes) -> str:
        """
        Decode 3-byte DTC to string format (PXXXX, CXXXX, etc.).
        
        Args:
            dtc_bytes: 3-byte DTC code
            
        Returns:
            str: Decoded DTC string
        """
        if len(dtc_bytes) != 3:
            return "INVALID"
        
        # First 2 bits determine prefix
        prefix_map = {0: 'P', 1: 'C', 2: 'B', 3: 'U'}
        prefix = prefix_map[(dtc_bytes[0] >> 6) & 0x03]
        
        # Remaining bits form the numeric code
        code = ((dtc_bytes[0] & 0x3F) << 8) | dtc_bytes[1]
        sub_code = dtc_bytes[2]
        
        return f"{prefix}{code:04X}{sub_code:02X}"
    
    # =========================================================================
    # Routine Control
    # =========================================================================
    
    def execute_routine(self, routine_id: int, params: bytes = b'') -> Optional[bytes]:
        """
        Execute ECU routine.
        
        Args:
            routine_id: Routine identifier (0x0000-0xFFFF)
            params: Optional routine parameters (max 255 bytes recommended)
            
        Returns:
            bytes: Routine response or None if failed
        """
        if not self.flasher.bus:
            logger.error(f"Cannot execute routine 0x{routine_id:04X}: Not connected to ECU")
            return None
        
        if len(params) > 255:
            logger.warning(f"Routine params very long ({len(params)} bytes), may fail")
        
        logger.info(f"Executing routine 0x{routine_id:04X}...")
        
        # Sub-function 0x01 = Start Routine
        request = bytes([0x01]) + struct.pack('>H', routine_id) + params
        
        response = self.flasher.send_uds_request(
            UDSService.ROUTINE_CONTROL,
            request
        )
        
        if response and response[0]:
            logger.info("Routine executed")
            return response[1][4:]  # Skip echo and routine ID
        
        logger.error("Routine failed")
        return None
    
    # =========================================================================
    # ECU Reset
    # =========================================================================
    
    def reset_ecu(self, reset_type: ECUReset = ECUReset.SOFT_RESET) -> bool:
        """
        Reset ECU.
        
        Args:
            reset_type: Type of reset to perform
            
        Returns:
            bool: True if reset initiated successfully
        """
        logger.info(f"Resetting ECU: {reset_type.name}")
        
        response = self.flasher.send_uds_request(
            UDSService.ECU_RESET,
            bytes([reset_type])
        )
        
        if response and response[0]:
            logger.info("ECU reset initiated")
            time.sleep(2.0)  # Wait for ECU to reset
            return True
        
        logger.error("ECU reset failed")
        return False
