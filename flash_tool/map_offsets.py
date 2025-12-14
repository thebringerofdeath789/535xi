#!/usr/bin/env python3
"""
BMW Map Offsets - XDF Validated Memory Addresses
================================================

Author: Gregory King
Date: November 3, 2025
Updated: For I8A0S OS, based on Corbanistan XDF (I8A0S_Custom_Corbanistan.xdf). For non-I8A0S OS variants (IJE0S, IKM0S, INA0S, etc.), authoritative offsets are derived from the Zarboz XDF family (IJE0S_zarboz.xdf, IKM0S_zarboz.xdf, INA0S_zarboz.xdf).
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Central registry of ECU memory offsets for various tuning parameters.
    VALIDATED against the authoritative XDF for the OS family (Corbanistan for I8A0S; Zarboz variants for non-I8A0S).
    
    CRITICAL: Many offsets in this file target I8A0S MSD81 (2MB flash) and are NOT valid for other ECU variants. Always consult the appropriate OS-specific XDF for offsets and sizes.

XDF Validation Source:
    maps/xdf_definitions/github/I8A0S_Custom_Corbanistan.xdf

Validated Offset Categories:
    - VMAX (Speed Limiter): 3 offsets (master, array, disable flag)
    - RPM Limiters: 10 gear-specific tables (floor/ceiling by trans type)
    - Antilag/Launch Control: 14+ offsets (enable, timing, fuel, safety)
    - DTC/Codewords: Feature enable flags (binary diff analysis)
    - Burbles/Pops: Timing tables (binary diff analysis)

Classes:
    OffsetRange - Memory address range definition

Functions:
    get_all_modifiable_offsets() -> Dict[str, List[OffsetRange]]
    print_offset_map() -> None
    validate_offset_coverage(bin_size: int) -> bool
"""

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class OffsetRange:
    """Represents an offset or offset range in flash"""
    start: int
    size: int = 1
    description: str = ""
    
    def __repr__(self):
        if self.size == 1:
            return f"0x{self.start:08X}"
        else:
            return f"0x{self.start:08X}-0x{self.start + self.size:08X} ({self.size} bytes)"


# ============================================================================
# VMAX (Speed Limiter) Offsets - CORBANISTAN XDF VALIDATED
# ============================================================================

# Binary diff offsets (may vary by ECU variant - NOT VALIDATED)
VMAX_OFFSETS_BINARY_DIFF = [
    OffsetRange(0x000093A0, 2, "VMAX (binary diff) - UNVALIDATED"),
    OffsetRange(0x0000B240, 2, "VMAX secondary (binary diff) - UNVALIDATED"),
]

# Corbanistan XDF-validated offsets (I8A0S_Custom_Corbanistan.xdf - PREFERRED)
VMAX_OFFSETS_XDF = [
    OffsetRange(0x00042E00, 2, "Speed Limiter (Master) - 16-bit, scale: X/161.29 for MPH"),
    OffsetRange(0x00042E0A, 4, "Speed Limiter (array) - 4 x 8-bit, scale: X/1.609 for MPH"),
    OffsetRange(0x00042E12, 1, "Speed Limiter Disable Flag - 0=enabled, 1=disabled"),
]

# Use XDF-validated offsets as primary
VMAX_OFFSETS = VMAX_OFFSETS_XDF

VMAX_STOCK_VALUE = 180  # km/h
VMAX_DELETE_VALUE = 255  # km/h (effectively no limit)
VMAX_DISABLE_FLAG_OFFSET = 0x00042E12  # Set to 1 to disable limiter
VMAX_MASTER_OFFSET = 0x00042E00  # Main speed limit value


# ============================================================================
# RPM Limiter Offsets - CORBANISTAN XDF VALIDATED
# ============================================================================

# Binary diff offsets (may be auxiliary limiters or different ECU variant - NOT VALIDATED)
RPM_LIMITER_OFFSETS_BINARY_DIFF = [
    OffsetRange(0x000048CB, 2, "RPM limiter (binary diff 1) - UNVALIDATED"),
    OffsetRange(0x00004C43, 2, "RPM limiter (binary diff 2) - UNVALIDATED"),
    OffsetRange(0x00005881, 2, "RPM limiter (binary diff 3) - UNVALIDATED"),
    OffsetRange(0x00005F7C, 2, "RPM limiter (binary diff 4) - UNVALIDATED"),
    OffsetRange(0x00009363, 2, "RPM limiter (binary diff 5) - UNVALIDATED"),
    OffsetRange(0x00009372, 2, "RPM limiter (binary diff 6) - UNVALIDATED"),
    OffsetRange(0x00009452, 2, "RPM limiter (binary diff 7) - UNVALIDATED"),
    OffsetRange(0x00009464, 2, "RPM limiter (binary diff 8) - UNVALIDATED"),
    OffsetRange(0x00009530, 2, "RPM limiter (binary diff 9) - UNVALIDATED"),
    OffsetRange(0x00009540, 2, "RPM limiter (binary diff 10) - UNVALIDATED"),
]

# Corbanistan XDF-validated offsets (I8A0S_Custom_Corbanistan.xdf - PREFERRED)
# All gear tables: 9 values x 16-bit = 18 bytes per table
RPM_LIMITER_OFFSETS_XDF = [
    # Clutch-pressed limiter - speed-based table (X axis at 0x4EFF1)
    OffsetRange(0x0004EFF1, 8, "Rev Limit (Clutch Pressed) X axis - 8 x 8-bit km/h"),
    OffsetRange(0x00055464, 16, "Rev Limit (Clutch Pressed) - 8 x 16-bit RPM"),
    
    # Gear-based floor limits (soft limit / downshift protection)
    OffsetRange(0x0004F2A5, 9, "Rev Limit Gear Axis (common) - 9 x 8-bit gear indices"),
    OffsetRange(0x000508A4, 18, "Rev Limit by Gear Floor (AT) - 9 x 16-bit RPM"),
    OffsetRange(0x000508B8, 18, "Rev Limit by Gear Floor (MT) - 9 x 16-bit RPM"),
    OffsetRange(0x00050908, 18, "Rev Limit by Gear Floor (AT Manual Mode) - 9 x 16-bit RPM"),
    
    # Gear-based ceiling limits (hard limit / upshift trigger)
    OffsetRange(0x000508CC, 18, "Rev Limit by Gear Ceiling (AT) - 9 x 16-bit RPM"),
    OffsetRange(0x000508E0, 18, "Rev Limit by Gear Ceiling (MT) - 9 x 16-bit RPM"),
    OffsetRange(0x000508F4, 18, "Rev Limit by Gear Ceiling (AT Manual Mode) - 9 x 16-bit RPM"),
    
    # Time between rev limit bumps (fuel cut intervals)
    OffsetRange(0x00050A5C, 18, "Time Between Rev Limit Bumps (AT) - 9 x 16-bit, scale: X/10 sec"),
    OffsetRange(0x00050A70, 18, "Time Between Rev Limit Bumps (AT Manual) - 9 x 16-bit, scale: X/10 sec"),
    OffsetRange(0x00050A84, 18, "Time Between Rev Limit Bumps (MT) - 9 x 16-bit, scale: X/10 sec"),
]

# Use XDF-validated offsets as primary
RPM_LIMITER_OFFSETS = RPM_LIMITER_OFFSETS_XDF

# Quick-access offsets for common operations
REV_LIMIT_FLOOR_AT_OFFSET = 0x000508A4
REV_LIMIT_FLOOR_MT_OFFSET = 0x000508B8
REV_LIMIT_CEILING_AT_OFFSET = 0x000508CC
REV_LIMIT_CEILING_MT_OFFSET = 0x000508E0
REV_LIMIT_CLUTCH_PRESSED_OFFSET = 0x00055464
REV_LIMIT_GEAR_AXIS_OFFSET = 0x0004F2A5

RPM_STOCK_SOFT_LIMIT = 7000  # RPM (floor / downshift protection)
RPM_STOCK_HARD_LIMIT = 7200  # RPM (ceiling / fuel cut)


# ============================================================================
# DTC/Codeword Offsets (Feature Enable/Disable Flags)
# ============================================================================

# These are single-byte codewords that enable/disable features
# 551 total codeword changes found - these are the most significant

DTC_CODEWORD_OFFSETS = [
    OffsetRange(0x00000705, 1, "Codeword byte 1"),
    OffsetRange(0x00000749, 1, "Codeword byte 2"),
    OffsetRange(0x00000761, 1, "Codeword byte 3"),
    OffsetRange(0x00000806, 1, "Codeword byte 4"),
    OffsetRange(0x00000811, 1, "Codeword byte 5"),
    OffsetRange(0x00000921, 1, "Codeword byte 6"),
    OffsetRange(0x00000A00, 1, "Feature enable 1"),
    OffsetRange(0x00000A02, 1, "Feature enable 2"),
    OffsetRange(0x00000A04, 1, "Feature enable 3"),
    OffsetRange(0x00000A14, 1, "Feature enable 4"),
]

# Known codeword values
CATALYST_DTC_DISABLE = {
    0x00000705: 0x31,  # Stock: 0x33, Modified: 0x31
    0x00000749: 0x31,  # Stock: 0x33, Modified: 0x31
}

O2_SENSOR_DTC_DISABLE = {
    0x00000A00: 0x84,  # Stock: 0x5A, Modified: 0x84
    0x00000A02: 0x84,  # Stock: 0x5A, Modified: 0x84
}


# ============================================================================
# Burbles/Pops Timing Table Offsets
# ============================================================================

# These are larger timing table modifications for burbles/pops
BURBLES_TIMING_TABLES = [
    OffsetRange(0x00002332, 30, "Burbles timing table 1"),
    OffsetRange(0x00002A62, 19, "Burbles timing table 2"),
    OffsetRange(0x00002AAE, 17, "Burbles timing table 3"),
    OffsetRange(0x00002D0A, 30, "Burbles timing table 4"),
    OffsetRange(0x00003145, 20, "Burbles timing table 5"),
    OffsetRange(0x000033EC, 20, "Burbles timing table 6"),
    OffsetRange(0x0000366F, 20, "Burbles timing table 7"),
    OffsetRange(0x00003706, 17, "Burbles timing table 8"),
]

# Smaller timing map adjustments
BURBLES_TIMING_MAPS = [
    OffsetRange(0x00000304, 4, "Timing adjustment 1"),
    OffsetRange(0x00002999, 4, "Timing adjustment 2"),
    OffsetRange(0x00002B61, 4, "Timing adjustment 3"),
    OffsetRange(0x00002C0E, 4, "Timing adjustment 4"),
]

# Reference burbles data from MSD81 analysis (I8A0S_MSD81_2MB.bin)
# This is the "modified" data that enables burbles
BURBLES_REFERENCE_DATA = {
    # Timing tables (30, 19, 17, 30, 20, 20, 20, 17 bytes)
    0x00002332: bytes.fromhex("144f420f3c09144fc21f370f68f014203f0f0380023f344f021f8b042002"),
    0x00002A62: bytes.fromhex("f00f54ff9bf0ff0f260f96f374ff58022e830d"),
    0x00002AAE: bytes.fromhex("b7ff660f07f04eff840f08ff6703900f"),
    0x00002D0A: bytes.fromhex("54ff0bfe3220e8feb20f84f072ff88ff47ffa1020bfe44f0ca0f50f092f0"),
    0x00003145: bytes.fromhex("74fffefc7fff45fb540f480f5aff40001a009cff"),
    0x000033EC: bytes.fromhex("34ff12ff04ffc2fe00ff84ff94ff18fe4c0ff600"),
    0x0000366F: bytes.fromhex("04fe34fec4fe34ff16ffe20f7aff22000c0f0400"),
    0x00003706: bytes.fromhex("580096ffb20ffefc02ff160074feb7ff"),
    # Timing maps (4 bytes each)
    0x00000304: bytes.fromhex("3c090cff"),
    0x00002999: bytes.fromhex("401ff60f"),
    0x00002B61: bytes.fromhex("901fc010"),
    0x00002C0E: bytes.fromhex("82128210"),
}


# ============================================================================
# Boost Limit Offsets
# ============================================================================

# Not yet fully identified - need more analysis
# Look for values in 800-2000 mbar range (0x0320-0x07D0)
BOOST_OFFSET_CANDIDATES = [
    # To be determined from further analysis
]


# ============================================================================
# Launch Control / Antilag Offsets - CORBANISTAN XDF VALIDATED
# ============================================================================

# Corbanistan XDF-validated Antilag/Launch Control offsets
LAUNCH_CONTROL_OFFSETS_XDF = [
    # Core enable/disable and parameters
    OffsetRange(0x0007E77E, 2, "Antilag Boost Target - 16-bit, scale: X/831.52 for psi"),
    OffsetRange(0x0007E782, 1, "Antilag Cooldown Timer - 8-bit, seconds before reuse"),
    OffsetRange(0x0007E783, 1, "Enable Antilag - 0=disabled, 1=enabled"),
    OffsetRange(0x0007E784, 2, "Antilag Timing Ramp Rate - 16-bit, scale: X/10 *crk/10ms"),
    OffsetRange(0x0007E786, 2, "Antilag Timing Ramp Rate (crk<0) - 16-bit, scale: X/10"),
    
    # Antilag Timing Base 2D Table (8x8 = 64 cells, 16-bit each = 128 bytes)
    # X axis: Boost target (8 values @ 0x7E79A)
    # Y axis: RPM (8 values @ 0x7E78A)
    # Z values: Timing retard (64 values @ 0x7E7AA)
    OffsetRange(0x0007E78A, 16, "Antilag Timing - Y axis (RPM) - 8 x 16-bit"),
    OffsetRange(0x0007E79A, 16, "Antilag Timing - X axis (Boost psi) - 8 x 16-bit, scale: X/831.52"),
    OffsetRange(0x0007E7AA, 128, "Antilag Timing Base - 8x8 table, 16-bit, scale: X/10 *crk"),
    
    # Fuel and safety limits
    OffsetRange(0x0007E82A, 2, "Antilag Fuel Target - 16-bit, scale: X/4096*14.7 for AFR"),
    OffsetRange(0x0007E82C, 2, "Antilag Coolant Safety Min - 16-bit, scale: X/100 °C"),
    OffsetRange(0x0007E82E, 2, "Antilag Coolant Safety Max - 16-bit, scale: X/100 °C"),
    OffsetRange(0x0007E830, 2, "Antilag EGT Safety Max - 16-bit, scale: X/10 °C"),
]

# Use XDF-validated offsets
LAUNCH_CONTROL_OFFSETS = LAUNCH_CONTROL_OFFSETS_XDF

# Quick-access addresses for common operations
ANTILAG_ENABLE_OFFSET = 0x0007E783        # 8-bit: 0=off, 1=on
ANTILAG_BOOST_TARGET_OFFSET = 0x0007E77E  # 16-bit: X/831.52 = psi
ANTILAG_COOLDOWN_OFFSET = 0x0007E782      # 8-bit: seconds
ANTILAG_TIMING_TABLE_OFFSET = 0x0007E7AA  # 128 bytes: 8x8 timing table
ANTILAG_TIMING_RPM_AXIS = 0x0007E78A      # 16 bytes: RPM breakpoints
ANTILAG_TIMING_BOOST_AXIS = 0x0007E79A    # 16 bytes: Boost breakpoints
ANTILAG_FUEL_TARGET_OFFSET = 0x0007E82A   # 16-bit: AFR target
ANTILAG_COOLANT_MIN_OFFSET = 0x0007E82C   # 16-bit: Min ECT for activation
ANTILAG_COOLANT_MAX_OFFSET = 0x0007E82E   # 16-bit: Max ECT safety cutoff
ANTILAG_EGT_MAX_OFFSET = 0x0007E830       # 16-bit: Max EGT safety cutoff


# ============================================================================
# CRC Checksum Zones
# ============================================================================

# These zones need to be recalculated after modifications
# Exact boundaries require decompilation of:
# - 0x0186ccb1 (CRC_40304)
# - 0x0186ccbd (CRC_40404)

CRC_ZONES = [
    # Format: (start, end, crc_offset)
    # Placeholder values
    (0x00000000, 0x0007FFFF, 0x00100000),  # Zone 1 (estimated)
    (0x00080000, 0x000FFFFF, 0x00100004),  # Zone 2 (estimated)
]


# ============================================================================
# Helper Functions
# ============================================================================

def get_all_modifiable_offsets() -> Dict[str, List[OffsetRange]]:
    """Return all known modifiable offsets grouped by category"""
    return {
        "vmax": VMAX_OFFSETS,
        "rpm_limiter": RPM_LIMITER_OFFSETS,
        "dtc_codewords": DTC_CODEWORD_OFFSETS,
        "burbles_timing_tables": BURBLES_TIMING_TABLES,
        "burbles_timing_maps": BURBLES_TIMING_MAPS,
        "launch_control": LAUNCH_CONTROL_OFFSETS,
        # Boost/WGDC maps used by presets
        "boost_wgdc": [
            OffsetRange(0x0005F7F6, 640, "WGDC Base (20x16, 16-bit)"),
            OffsetRange(0x0005F72A, 128, "WGDC Spool (8x8, 16-bit)"),
        ],
        "boost_airflow_adders": [
            OffsetRange(0x0006D7A6, 12, "WGDC Airflow Adder Axis (E85)"),
            OffsetRange(0x000639B4, 12, "WGDC Airflow Adder Axis (Map2)"),
            OffsetRange(0x000639CE, 12, "WGDC Airflow Adder Axis (Map3)"),
            OffsetRange(0x000639E8, 12, "WGDC Airflow Adder Axis (Map4)"),
            OffsetRange(0x0006D7B2, 12, "WGDC Airflow Adder (E85)"),
            OffsetRange(0x000639C0, 12, "WGDC Airflow Adder (Map2)"),
            OffsetRange(0x000639DA, 12, "WGDC Airflow Adder (Map3)"),
            OffsetRange(0x000639F4, 12, "WGDC Airflow Adder (Map4)"),
        ],
        "boost_pid": [
            OffsetRange(0x0005FF2A, 24, "WGDC P-Factor (12 values, 16-bit)"),
            OffsetRange(0x0006007E, 288, "WGDC I-Factor (12x12, 16-bit)"),
            OffsetRange(0x000601D6, 392, "WGDC D-Factor (14x14, 16-bit)"),
            OffsetRange(0x0005F6C2, 24, "WGDC D Multiplier vs RPM (12 values, 16-bit)"),
            OffsetRange(0x00077BC4, 2, "Boost Ceiling (scalar, 16-bit)"),
        ],
        "boost_load": [
            OffsetRange(0x00066D3E, 24, "Boost Limit Multiplier (12 values, 16-bit)"),
            OffsetRange(0x0005F27A, 24, "Load Limit Factor (12 values, 16-bit)"),
            OffsetRange(0x0007F736, 192, "Load Target per Gear (6x16, 16-bit)"),
            OffsetRange(0x000617BE, 72, "Boost Pressure Target Modifier (6x6, 16-bit)"),
        ],
        "ignition_timing": [
            OffsetRange(0x0007676A, 320, "Timing Main (20x16, 8-bit)"),
            OffsetRange(0x000768CE, 64, "Timing Spool (8x8, 8-bit)"),
        ],
        "torque_limits": [
            OffsetRange(0x0006E628, 22, "Torque Limit Driver Demand (11 values, 16-bit)"),
            OffsetRange(0x00072AF6, 2, "Torque Limit Cap (scalar, 16-bit)"),
        ],
        "throttle": [
            OffsetRange(0x0007372E, 36, "Throttle Angle WOT (18 values, 16-bit)"),
            OffsetRange(0x0007F710, 32, "Throttle Sensitivity (16 values, 16-bit)"),
        ],
        "flexfuel": [
            OffsetRange(0x0007E6A7, 1, "Static Ethanol Content (8-bit)")
        ],
        "dtc_tuning": [
            OffsetRange(0x00059D24, 1, "DTC 30FE Overboost"),
            OffsetRange(0x00059D38, 1, "DTC 30FF Underboost"),
            OffsetRange(0x00059CFC, 1, "DTC 3100 Boost Deactivation"),
            OffsetRange(0x00059B08, 1, "DTC 2E8E IBS Battery Sensor"),
            OffsetRange(0x0005A0D0, 1, "DTC 2FA3 Coding Missing"),
        ],
        "burble_maps": [
            OffsetRange(0x00054A30, 96, "Burble Timing Base (6x8, 16-bit)"),
            OffsetRange(0x00063B20, 96, "Burble Duration Normal (6x8, 16-bit)"),
            OffsetRange(0x0007F4CC, 96, "Burble Duration Sport (6x8, 16-bit)"),
            OffsetRange(0x00063A00, 48, "Burble Ignition Retard (6x8, 8-bit)"),
        ],
    }


def print_offset_map():
    """Print all known offsets for documentation"""
    print("="*80)
    print("MSD81 Map Offset Map")
    print("="*80)
    
    all_offsets = get_all_modifiable_offsets()
    
    for category, offsets in all_offsets.items():
        print(f"\n{category.upper().replace('_', ' ')} ({len(offsets)} offsets):")
        for offset in offsets:
            print(f"  {offset} - {offset.description}")
    
    print("\n" + "="*80)


def validate_offset_coverage(bin_size: int = 0x200000) -> bool:
    """Validate that all offsets are within valid range"""
    all_offsets = get_all_modifiable_offsets()
    valid = True
    
    for category, offsets in all_offsets.items():
        for offset in offsets:
            if offset.start + offset.size > bin_size:
                print(f"⚠️  {category}: Offset {offset} exceeds bin size {bin_size:#x}")
                valid = False
    
    return valid


if __name__ == "__main__":
    print_offset_map()
    print()
    if validate_offset_coverage():
        print("✓ All offsets validated!")
    else:
        print("✗ Some offsets out of range!")
