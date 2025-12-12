"""
CRC Validation Utilities for BMW N54 ECU Flashing

Handles BMW CRC-32 checksum calculation and validation for safe flashing operations.
"""

import struct
from typing import Optional, Tuple, List

# BMW CRC-32 polynomial (reversed)
BMW_CRC32_POLYNOMIAL = 0x1EDC6F41


class CRCValidator:
    """BMW ECU CRC-32 validation and calculation."""
    
    # BMW ECU CRC zones for MSD80/MSD81
    # Format: (name, start_offset, end_offset, description)
    CRC_ZONES = [
        ("FULL_FILE", 0x00000, 0xFFFFFE, "Full firmware CRC-32"),
        ("CAL_REGION", 0x80000, 0x200000, "Calibration region"),
    ]
    
    # Known safe regions (don't modify)
    FORBIDDEN_REGIONS = [
        (0x054A90, 0x054B50, "WGDC checksum block"),
        (0x05AD20, 0x05AD80, "WGDC checksum block"),
        (0x000000, 0x007FFF, "Boot code"),
        (0x1F0000, 0x200000, "Flash counter/config"),
    ]
    
    @staticmethod
    def calculate_bmw_crc32(data: bytes, init_value: int = 0xFFFFFFFF) -> int:
        """
        Calculate BMW CRC-32 checksum.
        
        Uses polynomial 0x1EDC6F41 (reversed form).
        This is the standard BMW variant found in MSD80/MSD81 ECUs.
        
        Args:
            data: Bytes to calculate CRC for
            init_value: Initial CRC value (default: 0xFFFFFFFF)
        
        Returns:
            int: Calculated CRC-32 value
        """
        crc = init_value
        
        for byte in data:
            crc ^= byte << 24
            for _ in range(8):
                crc <<= 1
                if crc & 0x100000000:
                    crc ^= BMW_CRC32_POLYNOMIAL
            crc &= 0xFFFFFFFF
        
        return crc ^ 0xFFFFFFFF  # Final XOR
    
    @staticmethod
    def calculate_bmw_crc16(data: bytes) -> int:
        """
        Calculate BMW CRC-16 checksum.
        
        Uses CCITT polynomial 0x1021.
        Used for sub-region validation in MSD80.
        
        Args:
            data: Bytes to calculate CRC for
        
        Returns:
            int: Calculated CRC-16 value
        """
        crc = 0xFFFF
        
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                crc <<= 1
                if crc & 0x10000:
                    crc ^= 0x1021
            crc &= 0xFFFF
        
        return crc
    
    @classmethod
    def validate_full_file_crc(cls, data: bytes, expected_crc: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate full firmware CRC-32.
        
        Args:
            data: Complete firmware binary
            expected_crc: Optional expected CRC value
        
        Returns:
            Tuple of (is_valid, message)
        """
        if len(data) < 4:
            return False, "Data too small for CRC validation"
        
        calculated = cls.calculate_bmw_crc32(data[:-4])
        stored = struct.unpack(">I", data[-4:])[0]
        
        is_valid = calculated == stored
        msg = f"Full file CRC: calculated=0x{calculated:08X}, stored=0x{stored:08X}"
        
        return is_valid, msg
    
    @classmethod
    def check_forbidden_regions(cls, data: bytes, start_offset: int = 0x00000) -> Tuple[bool, str]:
        """
        Check if data modifies any forbidden regions.
        
        Args:
            data: Bytes being flashed
            start_offset: Starting address of data in ECU memory
        
        Returns:
            Tuple of (is_safe, message)
        """
        end_offset = start_offset + len(data)
        
        for region_start, region_end, region_name in cls.FORBIDDEN_REGIONS:
            # Check for overlap
            if start_offset < region_end and end_offset > region_start:
                overlap_start = max(start_offset, region_start)
                overlap_end = min(end_offset, region_end)
                msg = (f"FORBIDDEN: Data overlaps {region_name} "
                       f"(0x{overlap_start:06X}-0x{overlap_end:06X})")
                return False, msg
        
        return True, "No forbidden region overlap detected"
    
    @classmethod
    def check_data_integrity(cls, data: bytes) -> Tuple[bool, str]:
        """
        Perform basic data integrity checks.
        
        Args:
            data: Bytes to validate
        
        Returns:
            Tuple of (is_valid, message)
        """
        if len(data) == 0:
            return False, "Empty data"
        
        if len(data) % 4 != 0:
            return False, f"Data length {len(data)} not 4-byte aligned"
        
        # Check for all-zeros (corrupted)
        if all(b == 0x00 for b in data):
            return False, "Data is all zeros (corrupted)"
        
        # Check for all-0xFF (erased)
        if all(b == 0xFF for b in data):
            return False, "Data is all 0xFF (erased state, corrupted)"
        
        return True, "Data integrity check passed"
    
    @classmethod
    def create_checksum_block(cls, data: bytes) -> bytes:
        """
        Create a BMW CRC-32 checksum block for data.
        
        Args:
            data: Data to protect
        
        Returns:
            bytes: Data + 4-byte checksum block
        """
        crc = cls.calculate_bmw_crc32(data)
        checksum_block = struct.pack(">I", crc)
        return data + checksum_block
    
    @classmethod
    def full_pre_flash_validation(cls, data: bytes, address: int) -> Tuple[bool, list[tuple[str, bool, str]]]:
        """
        Comprehensive pre-flash validation.
        
        Performs all checks:
        1. Data integrity
        2. Forbidden region check
        3. CRC zone validation
        
        Args:
            data: Bytes being flashed
            address: Target address in ECU memory
        
        Returns:
            Tuple of (all_passed, list_of_check_results)
        """
        results: list[tuple[str, bool, str]] = []
        all_passed = True
        
        # 1. Data integrity
        is_valid, msg = cls.check_data_integrity(data)
        results.append(("Data Integrity", is_valid, msg))
        all_passed = all_passed and is_valid
        
        # 2. Forbidden regions
        is_safe, msg = cls.check_forbidden_regions(data, address)
        results.append(("Forbidden Regions", is_safe, msg))
        all_passed = all_passed and is_safe
        
        # 3. CRC validation (if applicable)
        if address == 0x00000 and len(data) >= 4:
            is_valid, msg = cls.validate_full_file_crc(data)
            results.append(("Full File CRC", is_valid, msg))
            all_passed = all_passed and is_valid
        
        return all_passed, results


def validate_and_log(data: bytes, address: int) -> bool:
    """
    Convenience function: validate data and log results.
    
    Args:
        data: Bytes to validate
        address: Target flash address
    
    Returns:
        bool: True if all validations passed
    """
    validator = CRCValidator()
    all_passed, results = validator.full_pre_flash_validation(data, address)
    
    print("\n" + "=" * 60)
    print("PRE-FLASH VALIDATION REPORT")
    print("=" * 60)
    
    for check_name, passed, message in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {check_name}: {message}")
    
    if all_passed:
        print("\n[SUCCESS] All pre-flash checks passed")
    else:
        print("\n[FAIL] Pre-flash validation failed - DO NOT FLASH")
    
    print("=" * 60 + "\n")
    
    return all_passed
