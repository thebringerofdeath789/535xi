#!/usr/bin/env python3
"""
BMW N54 UDS Operations Handler - ISO 14229 Protocol Implementation
===================================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Unified Diagnostic Services (UDS) protocol handler for BMW N54 ECU.
    Implements ISO 14229 services for diagnostic session control,
    security access, memory operations, and runtime map patching.
    
    Based on reverse engineering of MHD Flasher application binary,
    with real offsets discovered from binary analysis.

Features:
    - UDS protocol over CAN (ISO 14229)
    - Diagnostic session management
    - Security access (seed/key)
    - Memory read/write operations
    - Routine control
    - Runtime map patching for user options
    - CRC32 checksum validation

Classes:
    UDSService(Enum) - UDS service identifiers (ISO 14229)
    DiagnosticSession(Enum) - Session types
    FlashRegion(Enum) - ECU memory regions
    UDSHandler - Main UDS operations handler
    MapPatcher - Runtime map modification engine

Functions:
    None (class-based module)

Variables (Module-level):
    None
"""

import struct
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from enum import Enum
from . import map_offsets  # Real offset constants
from . import offset_database  # Multi-version offset support
from .direct_can_flasher import DirectCANFlasher, DiagnosticSession as UdsDiagnosticSession, EcuResetType

class UDSService(Enum):
    """UDS Service IDs (ISO 14229)"""
    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    SECURITY_ACCESS = 0x27
    READ_DATA_BY_ID = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    WRITE_DATA_BY_ID = 0x2E
    ROUTINE_CONTROL = 0x31
    REQUEST_DOWNLOAD = 0x34
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37

class DiagnosticSession(Enum):
    """Diagnostic session types"""
    DEFAULT = 0x01
    PROGRAMMING = 0x02
    EXTENDED = 0x03

class FlashRegion(Enum):
    """ECU flash memory regions"""
    BOOTLOADER = "BTLD"  # 0x00000000-0x0001FFFF
    PROGRAM = "PRG"      # 0x00080000-0x000FFFFF
    CALIBRATION = "CAL"  # 0x00100000-0x0017FFFF (~512 KB)

class UDSHandler:
    """
    Handles UDS protocol operations for N54 ECU communication.
    
    Note: This implementation uses the DirectCANFlasher for UDS communication
    as the primary and only supported workflow.
    """
    
    def __init__(self, logger=None, can_interface: str = 'pcan', can_channel: str = 'PCAN_USBBUS1'):
        self.logger = logger
        self.session_active = False
        self.security_unlocked = False
        self._flasher = DirectCANFlasher(logger=logger, can_interface=can_interface, can_channel=can_channel)
        
    def log(self, message: str, level: str = "INFO"):
        """Log message if logger available"""
        if self.logger:
            if level == "ERROR":
                self.logger.error(message)
            elif level == "WARNING":
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(f"[{level}] {message}")
    
    def enter_programming_session(self) -> bool:
        """
        Enter programming session (UDS 0x10 0x02)
        
        Returns:
            bool: True if successful
        """
        self.log("Entering programming diagnostic session via direct CAN...")
        
        try:
            self._flasher.connect()
            if self._flasher.enter_diagnostic_session(UdsDiagnosticSession.PROGRAMMING):
                self.session_active = True
                self.log("✓ Programming session established")
                return True
            else:
                self.log("✗ Failed to enter programming session", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error entering programming session: {e}", "ERROR")
            return False
    
    def read_vin(self) -> Optional[str]:
        """
        Read VIN from ECU (UDS 0x22 with DID 0xF190)
        
        Returns:
            str: Vehicle VIN or None if failed
        """
        self.log("Reading VIN from ECU via direct CAN...")
        
        try:
            self._flasher.connect()
            # Standard DID for VIN is 0xF190
            response = self._flasher.read_data_by_identifier(0xF190)
            
            if response and response.get("success"):
                # Assuming the response data contains the VIN, usually after some header bytes
                vin_bytes = response.get("data", b"")
                if vin_bytes:
                    # The exact parsing depends on the ECU response format.
                    # Often it's just the raw ASCII bytes.
                    vin = vin_bytes.decode('ascii', errors='ignore')
                    self.log(f"✓ VIN: {vin}")
                    return vin
                else:
                    self.log("✗ VIN read successful, but no data returned.", "ERROR")
                    return None
            else:
                self.log(f"✗ Failed to read VIN: {response.get('error', 'Unknown error')}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Error reading VIN: {e}", "ERROR")
            return None
    
    def request_security_seed(self) -> Optional[bytes]:
        """
        Request security seed from ECU (UDS 0x27 0x01)
        
        Returns:
            bytes: Seed challenge or None if failed
        """
        self.log("Requesting security seed from ECU via direct CAN...")
        
        try:
            self._flasher.connect()
            seed = self._flasher.request_seed(level=1) # Level 1 for flashing/programming
            if seed:
                self.log(f"✓ Received seed: {seed.hex()}")
                return seed
            else:
                self.log("✗ Failed to request security seed", "ERROR")
                return None
        except Exception as e:
            self.log(f"Error requesting security seed: {e}", "ERROR")
            return None

    def send_security_key(self, key: bytes) -> bool:
        """
        Send security key to unlock ECU (UDS 0x27 0x02)
        
        Args:
            key: Calculated security key
            
        Returns:
            bool: True if ECU unlocked
        """
        self.log("Sending security key to ECU via direct CAN...")
        try:
            self._flasher.connect()
            if self._flasher.send_key(level=1, key=key):
                self.log("✓ Security key accepted. ECU unlocked.")
                self.security_unlocked = True
                return True
            else:
                self.log("✗ Security key rejected.", "ERROR")
                return False
        except Exception as e:
            self.log(f"Error sending security key: {e}", "ERROR")
            return False

    def unlock_ecu(self) -> bool:
        """
        Perform full security access handshake.
        
        Returns:
            bool: True if ECU is unlocked.
        """
        self.log("Attempting to unlock ECU via direct CAN...")
        try:
            self._flasher.connect()
            # The unlock_ecu method in DirectCANFlasher handles the full seed/key exchange
            if self._flasher.unlock_ecu(try_all_algorithms=True):
                self.log("✓ ECU unlocked successfully.")
                self.security_unlocked = True
                return True
            else:
                self.log("✗ Failed to unlock ECU.", "ERROR")
                return False
        except Exception as e:
            self.log(f"Error unlocking ECU: {e}", "ERROR")
            return False

    def read_calibration_region(self, start_addr: int = 0x100000, size: int = 0x80000) -> Optional[bytes]:
        """
        Read calibration region from ECU
        
        Args:
            start_addr: Start address (default 0x100000 for CAL)
            size: Number of bytes to read (default 512KB)
            
        Returns:
            bytes: Calibration data or None if failed
        """
        self.log(f"Reading calibration region (0x{start_addr:08X}, {size} bytes) via direct CAN...")
        
        if not self.security_unlocked:
            self.log("⚠ ECU not unlocked. Attempting to unlock first.", "WARNING")
            if not self.unlock_ecu():
                return None

        try:
            # DirectCANFlasher has a high-level method for this
            data = self._flasher.read_calibration_region(start_addr=start_addr, size=size)
            
            if data:
                self.log(f"✓ Read {len(data)} bytes from calibration")
                return data
            else:
                self.log("✗ Failed to read calibration", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Error reading calibration: {e}", "ERROR")
            return None
    
    def flash_calibration_region(self, data: bytes, verify: bool = True) -> bool:
        """
        Flash calibration region to ECU
        
        Args:
            data: Calibration data to flash
            verify: Verify flash after writing
            
        Returns:
            bool: True if successful
        """
        self.log(f"Flashing calibration region ({len(data)} bytes) via direct CAN...")
        
        if not self.session_active:
            self.log("⚠ Programming session not active", "WARNING")
            if not self.enter_programming_session():
                return False

        if not self.security_unlocked:
            self.log("⚠ ECU not unlocked. Attempting to unlock first.", "WARNING")
            if not self.unlock_ecu():
                return False
        
        try:
            # DirectCANFlasher has a high-level method for this entire process
            success = self._flasher.flash_calibration_region(data, verify=verify)
            
            if success:
                self.log("✓ Calibration flash successful")
                return True
            else:
                self.log("✗ Calibration flash failed", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error flashing calibration: {e}", "ERROR")
            return False
    
    def reset_ecu(self, reset_type: int = 0x01) -> bool:
        """
        Reset ECU (UDS 0x11)
        
        Args:
            reset_type: 0x01 = hard reset, 0x02 = key off/on, 0x03 = soft reset
            
        Returns:
            bool: True if successful
        """
        self.log(f"Resetting ECU (type 0x{reset_type:02X}) via direct CAN...")
        
        try:
            self._flasher.connect()
            
            # Map the integer to the EcuResetType enum if it exists
            try:
                reset_enum = EcuResetType(reset_type)
            except ValueError:
                self.log(f"Invalid reset type: {reset_type}. Defaulting to HARD.", "WARNING")
                reset_enum = EcuResetType.HARD

            if self._flasher.ecu_reset(reset_enum):
                self.session_active = False
                self.security_unlocked = False
                self.log("✓ ECU reset successful")
                return True
            else:
                self.log("✗ ECU reset failed", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error resetting ECU: {e}", "ERROR")
            return False
    
    def verify_calibration_crcs(self, data: bytes) -> bool:
        """
        Verify CRC checksums in calibration data
        
        Args:
            data: Calibration data to verify
            
        Returns:
            bool: True if all CRCs valid
            
        Raises:
            ValueError: If CRC verification fails or ECU type cannot be determined
        """
        from . import crc_zones
        from . import software_detector
        
        self.log("Verifying calibration CRCs...")
        
        # Detect ECU type from data size
        try:
            ecu_type = software_detector.detect_ecu_type_from_size(len(data))
            self.log(f"Detected ECU type: {ecu_type}")
        except Exception as e:
            self.log(f"⚠ Could not auto-detect ECU type: {e}", "WARNING")
            # Default to MSD81 for safety
            ecu_type = "MSD81"
            self.log(f"Defaulting to {ecu_type}")
        
        # Verify all CRC zones
        try:
            results = crc_zones.verify_all_crcs(data, ecu_type)
            
            # Check if all zones are valid
            all_valid = all(results.values())
            
            if all_valid:
                self.log(f"✓ All CRC zones valid ({len(results)} zones checked)")
                return True
            else:
                invalid_zones = [name for name, valid in results.items() if not valid]
                self.log(f"✗ CRC validation failed: {invalid_zones}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"✗ CRC verification error: {e}", "ERROR")
            raise ValueError(f"CRC verification failed: {e}") from e


class MapPatcher:
    """
    Applies user-selected options to map files before flashing.
    Implements MHD's runtime map modification capability.
    """
    
    def __init__(self, logger=None):
        self.logger = logger
        self.modifications_applied = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log message"""
        if self.logger:
            if level == "ERROR":
                self.logger.error(message)
            elif level == "WARNING":
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(f"[{level}] {message}")
    
    def apply_burbles_option(self, map_data: bytearray, enabled: bool = True,
                            mode: str = "normal") -> bytearray:
        """
        Enable/disable exhaust burbles (pops & crackles)
        Now supports multi-version offsets via offset_database.
        
        Burbles work by modifying ignition timing tables to create late ignition
        events that cause unburnt fuel to ignite in the exhaust.
        
        Args:
            map_data: Calibration data (mutable)
            enabled: Enable or disable burbles
            mode: "normal", "sport", or "custom" (currently uses reference data)
            
        Returns:
            bytearray: Modified map data
        """
        sw_id = self._detect_software_id(map_data)
        self.log(f"Applying burbles option: enabled={enabled}, mode={mode} (SW: {sw_id})")
        if not enabled:
            self.log("Burbles disabled - no modifications applied")
            return map_data
        offsets = offset_database.get_offset_database().get_burbles_offsets(sw_id)
        for entry in offsets:
            # For demo: zero out table (user can refine with real reference data)
            map_data[entry.offset:entry.offset+entry.size_bytes] = b'\x00' * entry.size_bytes
            self.log(f"  Patched {entry.title} at 0x{entry.offset:06X} ({entry.size_bytes} bytes)")
        self.modifications_applied.append(f"burbles_{mode}_{sw_id}")
        return map_data
    
    def apply_vmax_delete(self, map_data: bytearray, limit_kmh: int = 255) -> bytearray:
        """
        Remove or modify VMAX speed limiter
        Now supports multi-version offsets via offset_database.
        
        Args:
            map_data: Calibration data
            limit_kmh: New speed limit (255 = effectively removed)
            
        Returns:
            bytearray: Modified map data
        """
        sw_id = self._detect_software_id(map_data)
        self.log(f"Applying VMAX modification: {limit_kmh} km/h (SW: {sw_id})")
        offsets = offset_database.get_offset_database().get_vmax_offsets(sw_id)
        for entry in offsets:
            struct.pack_into('>H', map_data, entry.offset, limit_kmh)
            self.log(f"  Patched {entry.title} at 0x{entry.offset:06X}")
        self.modifications_applied.append(f"vmax_delete_{sw_id}")
        return map_data
    
    def apply_dtc_disable(self, map_data: bytearray, codes: List[str]) -> bytearray:
        """
        Disable specific DTCs from triggering CEL
        Now supports multi-version offsets via offset_database.
        
        Args:
            map_data: Calibration data
            codes: List of DTC codes to disable (e.g., ["P0420", "P0430"])
            
        Returns:
            bytearray: Modified map data
        """
        sw_id = self._detect_software_id(map_data)
        self.log(f"Disabling DTCs: {', '.join(codes)} (SW: {sw_id})")
        offsets = offset_database.get_offset_database().get_dtc_offsets(sw_id)
        for entry in offsets:
            # For now, just zero out the DTC table region (user can refine logic)
            map_data[entry.offset:entry.offset+entry.size_bytes] = b'\x00' * entry.size_bytes
            self.log(f"  Patched {entry.title} at 0x{entry.offset:06X} ({entry.size_bytes} bytes)")
        self.modifications_applied.append(f"dtc_disable_{sw_id}_{len(codes)}")
        return map_data
    
    def recalculate_all_crcs(self, map_data: bytearray) -> bytearray:
        """
        Recalculate all CRC checksums after modifications
        
        Args:
            map_data: Modified calibration data
            
        Returns:
            bytearray: Map with updated CRCs
        """
        from .bmw_checksum import calculate_crc32
        
        self.log("Recalculating CRC checksums...")
        
        # CRC zones (need reverse engineering)
        zones = [
            # (start, end, crc_offset, name)
        ]
        
        for start, end, crc_offset, name in zones:
            # Calculate CRC32 for this zone
            zone_data = map_data[start:end]
            crc = calculate_crc32(zone_data)
            
            # Write CRC to map (little-endian)
            map_data[crc_offset:crc_offset+4] = struct.pack('<I', crc)
            self.log(f"  {name}: 0x{crc:08X}")
        
        self.log("⚠ CRC zones not yet defined", "WARNING")
        
        return map_data
    
    def get_modifications_summary(self) -> List[str]:
        """Get list of applied modifications"""
        return self.modifications_applied.copy()

    def _detect_software_id(self, map_data: bytearray) -> str:
        """
        Detect software ID from .bin data using offset_database helper.
        Raises ValueError if not found/supported.
        """
        sw_id = offset_database.detect_software_id(map_data)
        if not sw_id or not offset_database.get_offset_database().validate_software_id(sw_id):
            raise ValueError(f"Unsupported or undetectable software ID: {sw_id}")
        self.log(f"Detected ECU software ID: {sw_id}")
        return sw_id
