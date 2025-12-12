#!/usr/bin/env python3
"""
BMW N54 Stock ECU Values - Extracted from I8A0S_original.bin
=============================================================

Author: Gregory King
Date: December 2, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Stock (factory) values extracted from a known-good I8A0S binary.
    These values serve as defaults and can be reverted to at any time.
    All values use LITTLE-ENDIAN format as per the XDF definition.

Source Binary:
    - File: maps/reference_bins/I8A0S_original.bin
    - Size: 2MB (2,097,152 bytes)
    - ECU: MSD80/MSD81

XDF Reference:
    - maps/xdf_definitions/I8A0S_Corbanistan.xdf
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import struct

# ============================================================================
# SPEED LIMITER - Stock Values
# ============================================================================

@dataclass
class SpeedLimiterStock:
    """Stock speed limiter values from I8A0S_original.bin"""
    # Offset 0x42E00 - 16-bit, scale: raw/161.29 = MPH
    master: int = 25500  # ~158 MPH (~254 km/h)
    
    # Offset 0x42E0A - 4 bytes
    array: List[int] = field(default_factory=lambda: [206, 235, 250, 243])
    
    # Offset 0x42E12 - 8-bit, 0=enabled, 1=disabled
    disable: int = 0
    
    @property
    def master_mph(self) -> float:
        return self.master / 161.29
    
    @property
    def master_kmh(self) -> float:
        return self.master_mph * 1.60934


# ============================================================================
# REV LIMITER - Stock Values
# ============================================================================

@dataclass
class RevLimiterStock:
    """Stock rev limiter values from I8A0S_original.bin"""
    # Gear axis - 9 values (P, R, N, 1, 2, 3, 4, 5, 6) or (0-8)
    gear_axis: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6, 7, 8])
    
    # Clutch Pressed - 8 x 16-bit @ 0x55464
    clutch_pressed: List[int] = field(default_factory=lambda: [6800, 6800, 6800, 6800, 6800, 6800, 6800, 6800])
    
    # Floor/Ceiling for Manual Transmission @ 0x508B8, 0x508E0
    floor_mt: List[int] = field(default_factory=lambda: [6800, 6980, 6980, 6980, 6980, 6980, 6980, 6400, 6400])
    ceiling_mt: List[int] = field(default_factory=lambda: [6802, 6982, 6982, 6982, 6982, 6982, 6982, 6600, 6600])
    
    # Floor/Ceiling for Automatic Transmission @ 0x508A4, 0x508CC
    floor_at: List[int] = field(default_factory=lambda: [6400, 7000, 7000, 7000, 7000, 7000, 7000, 6400, 6400])
    ceiling_at: List[int] = field(default_factory=lambda: [6600, 7100, 7100, 7100, 7100, 7000, 7000, 6600, 6600])
    
    # AT in Manual Mode @ 0x508F4, 0x50908  
    ceiling_at_manual: List[int] = field(default_factory=lambda: [6802, 6982, 6982, 6982, 6982, 6982, 6982, 6600, 6600])
    floor_at_manual: List[int] = field(default_factory=lambda: [6800, 6980, 6980, 6980, 6980, 6980, 6980, 6400, 6400])
    
    # Time between bumps (in 0.1s units) @ 0x50A5C, 0x50A70, 0x50A84
    time_between_bumps_at: List[int] = field(default_factory=lambda: [1, 12, 12, 12, 12, 10, 1, 1, 1])
    time_between_bumps_at_manual: List[int] = field(default_factory=lambda: [1, 1, 1, 1, 1, 1, 1, 1, 1])
    time_between_bumps_mt: List[int] = field(default_factory=lambda: [1, 1, 1, 1, 1, 1, 1, 1, 1])


# ============================================================================
# ANTILAG / LAUNCH CONTROL - Stock Values
# ============================================================================

@dataclass
class AntilagStock:
    """Stock antilag/launch control values from I8A0S_original.bin
    Note: All values are 0 (disabled) from factory.
    """
    # Enable flag @ 0x7E783
    enable: int = 0
    
    # Boost target @ 0x7E77E (scale: raw/831.52 = PSI)
    boost_target: int = 0
    
    # Cooldown timer @ 0x7E782 (seconds)
    cooldown_timer: int = 0
    
    # Fuel target @ 0x7E82A (scale: raw/4096*14.7 = AFR)
    fuel_target: int = 0
    
    # Safety limits
    coolant_min: int = 0  # °C * 100
    coolant_max: int = 0  # °C * 100
    egt_max: int = 0  # °C * 10
    
    # Timing table axes (8 values each)
    timing_rpm_axis: List[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0, 0])
    timing_boost_axis: List[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0, 0])
    
    # Timing base table (8x8 = 64 values)
    timing_base: List[int] = field(default_factory=lambda: [0] * 64)


# ============================================================================
# RECOMMENDED TUNED VALUES (Safe Starting Points)
# ============================================================================

@dataclass
class SpeedLimiterTuned:
    """Recommended tuned speed limiter values"""
    # Disabled limit (255 mph / 410 km/h - effectively unlimited)
    master: int = 41129  # ~255 MPH
    array: List[int] = field(default_factory=lambda: [255, 255, 255, 255])
    disable: int = 1  # Disabled


@dataclass
class RevLimiterTuned:
    """Recommended tuned rev limiter values - conservative Stage 1"""
    gear_axis: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6, 7, 8])
    
    # Raised to 7200 RPM (safe for stock internals)
    clutch_pressed: List[int] = field(default_factory=lambda: [7200, 7200, 7200, 7200, 7200, 7200, 7200, 7200])
    
    floor_mt: List[int] = field(default_factory=lambda: [7200, 7200, 7200, 7200, 7200, 7200, 7200, 6800, 6800])
    ceiling_mt: List[int] = field(default_factory=lambda: [7400, 7400, 7400, 7400, 7400, 7400, 7400, 7000, 7000])
    
    floor_at: List[int] = field(default_factory=lambda: [7000, 7200, 7200, 7200, 7200, 7200, 7200, 6800, 6800])
    ceiling_at: List[int] = field(default_factory=lambda: [7200, 7400, 7400, 7400, 7400, 7200, 7200, 7000, 7000])
    
    ceiling_at_manual: List[int] = field(default_factory=lambda: [7400, 7400, 7400, 7400, 7400, 7400, 7400, 7000, 7000])
    floor_at_manual: List[int] = field(default_factory=lambda: [7200, 7200, 7200, 7200, 7200, 7200, 7200, 6800, 6800])
    
    # Keep same timing
    time_between_bumps_at: List[int] = field(default_factory=lambda: [1, 12, 12, 12, 12, 10, 1, 1, 1])
    time_between_bumps_at_manual: List[int] = field(default_factory=lambda: [1, 1, 1, 1, 1, 1, 1, 1, 1])
    time_between_bumps_mt: List[int] = field(default_factory=lambda: [1, 1, 1, 1, 1, 1, 1, 1, 1])


@dataclass
class AntilagTuned:
    """Recommended antilag/launch control values - conservative"""
    enable: int = 1  # Enabled
    
    # ~15 PSI boost target
    boost_target: int = 12473  # 12473/831.52 = 15 PSI
    
    cooldown_timer: int = 5  # 5 seconds
    
    # 11.5:1 AFR
    fuel_target: int = 3200  # 3200/4096*14.7 = 11.5 AFR
    
    # Safety limits
    coolant_min: int = 7000  # 70°C
    coolant_max: int = 11000  # 110°C
    egt_max: int = 9000  # 900°C
    
    # RPM axis: 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500
    timing_rpm_axis: List[int] = field(default_factory=lambda: [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500])
    
    # Boost axis (mbar): 0, 200, 400, 600, 800, 1000, 1200, 1400
    timing_boost_axis: List[int] = field(default_factory=lambda: [0, 200, 400, 600, 800, 1000, 1200, 1400])
    
    # Conservative timing retard table (8x8)
    # More retard at high boost/RPM
    timing_base: List[int] = field(default_factory=lambda: [
        0, 0, 0, 0, 0, 0, 0, 0,          # 0 mbar
        0, 0, 0, 0, 0, 0, 0, 0,          # 200 mbar
        -2, -2, -2, -2, -3, -3, -3, -3,  # 400 mbar (values * 10 for 0.1° resolution)
        -3, -3, -3, -4, -4, -4, -5, -5,  # 600 mbar
        -4, -4, -5, -5, -6, -6, -7, -7,  # 800 mbar
        -5, -5, -6, -7, -8, -8, -9, -9,  # 1000 mbar
        -6, -7, -8, -9, -10, -10, -11, -11,  # 1200 mbar
        -8, -9, -10, -11, -12, -12, -13, -13,  # 1400 mbar
    ])


# ============================================================================
# GLOBAL STOCK VALUES INSTANCES
# ============================================================================

STOCK_SPEED_LIMITER = SpeedLimiterStock()
STOCK_REV_LIMITER = RevLimiterStock()
STOCK_ANTILAG = AntilagStock()

# Tuned presets
TUNED_SPEED_LIMITER = SpeedLimiterTuned()
TUNED_REV_LIMITER = RevLimiterTuned()
TUNED_ANTILAG = AntilagTuned()


# ============================================================================
# OFFSET DEFINITIONS (from Corbanistan XDF)
# ============================================================================

class MapOffset:
    """Memory offset definitions for each tunable parameter"""
    
    # Speed Limiter
    SPEED_LIMITER_MASTER = 0x42E00
    SPEED_LIMITER_ARRAY = 0x42E0A
    SPEED_LIMITER_DISABLE = 0x42E12
    
    # Rev Limiter
    REV_GEAR_AXIS = 0x4F2A5
    REV_CLUTCH_PRESSED = 0x55464
    REV_FLOOR_MT = 0x508B8
    REV_CEILING_MT = 0x508E0
    REV_FLOOR_AT = 0x508A4
    REV_CEILING_AT = 0x508CC
    REV_CEILING_AT_MANUAL = 0x508F4
    REV_FLOOR_AT_MANUAL = 0x50908
    REV_TIME_BUMPS_AT = 0x50A5C
    REV_TIME_BUMPS_AT_MANUAL = 0x50A70
    REV_TIME_BUMPS_MT = 0x50A84
    
    # Antilag / Launch Control
    ANTILAG_BOOST_TARGET = 0x7E77E
    ANTILAG_COOLDOWN = 0x7E782
    ANTILAG_ENABLE = 0x7E783
    ANTILAG_TIMING_RPM_AXIS = 0x7E78A
    ANTILAG_TIMING_BOOST_AXIS = 0x7E79A
    ANTILAG_TIMING_BASE = 0x7E7AA
    ANTILAG_FUEL_TARGET = 0x7E82A
    ANTILAG_COOLANT_MIN = 0x7E82C
    ANTILAG_COOLANT_MAX = 0x7E82E
    ANTILAG_EGT_MAX = 0x7E830


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def read_speed_limiter_from_bin(data: bytes) -> SpeedLimiterStock:
    """Read speed limiter values from binary data"""
    return SpeedLimiterStock(
        master=struct.unpack('<H', data[MapOffset.SPEED_LIMITER_MASTER:MapOffset.SPEED_LIMITER_MASTER+2])[0],
        array=list(data[MapOffset.SPEED_LIMITER_ARRAY:MapOffset.SPEED_LIMITER_ARRAY+4]),
        disable=data[MapOffset.SPEED_LIMITER_DISABLE]
    )


def read_rev_limiter_from_bin(data: bytes) -> RevLimiterStock:
    """Read rev limiter values from binary data"""
    return RevLimiterStock(
        gear_axis=list(data[MapOffset.REV_GEAR_AXIS:MapOffset.REV_GEAR_AXIS+9]),
        clutch_pressed=list(struct.unpack('<8H', data[MapOffset.REV_CLUTCH_PRESSED:MapOffset.REV_CLUTCH_PRESSED+16])),
        floor_mt=list(struct.unpack('<9H', data[MapOffset.REV_FLOOR_MT:MapOffset.REV_FLOOR_MT+18])),
        ceiling_mt=list(struct.unpack('<9H', data[MapOffset.REV_CEILING_MT:MapOffset.REV_CEILING_MT+18])),
        floor_at=list(struct.unpack('<9H', data[MapOffset.REV_FLOOR_AT:MapOffset.REV_FLOOR_AT+18])),
        ceiling_at=list(struct.unpack('<9H', data[MapOffset.REV_CEILING_AT:MapOffset.REV_CEILING_AT+18])),
        ceiling_at_manual=list(struct.unpack('<9H', data[MapOffset.REV_CEILING_AT_MANUAL:MapOffset.REV_CEILING_AT_MANUAL+18])),
        floor_at_manual=list(struct.unpack('<9H', data[MapOffset.REV_FLOOR_AT_MANUAL:MapOffset.REV_FLOOR_AT_MANUAL+18])),
        time_between_bumps_at=list(struct.unpack('<9H', data[MapOffset.REV_TIME_BUMPS_AT:MapOffset.REV_TIME_BUMPS_AT+18])),
        time_between_bumps_at_manual=list(struct.unpack('<9H', data[MapOffset.REV_TIME_BUMPS_AT_MANUAL:MapOffset.REV_TIME_BUMPS_AT_MANUAL+18])),
        time_between_bumps_mt=list(struct.unpack('<9H', data[MapOffset.REV_TIME_BUMPS_MT:MapOffset.REV_TIME_BUMPS_MT+18])),
    )


def read_antilag_from_bin(data: bytes) -> AntilagStock:
    """Read antilag/launch control values from binary data"""
    return AntilagStock(
        enable=data[MapOffset.ANTILAG_ENABLE],
        boost_target=struct.unpack('<H', data[MapOffset.ANTILAG_BOOST_TARGET:MapOffset.ANTILAG_BOOST_TARGET+2])[0],
        cooldown_timer=data[MapOffset.ANTILAG_COOLDOWN],
        fuel_target=struct.unpack('<H', data[MapOffset.ANTILAG_FUEL_TARGET:MapOffset.ANTILAG_FUEL_TARGET+2])[0],
        coolant_min=struct.unpack('<H', data[MapOffset.ANTILAG_COOLANT_MIN:MapOffset.ANTILAG_COOLANT_MIN+2])[0],
        coolant_max=struct.unpack('<H', data[MapOffset.ANTILAG_COOLANT_MAX:MapOffset.ANTILAG_COOLANT_MAX+2])[0],
        egt_max=struct.unpack('<H', data[MapOffset.ANTILAG_EGT_MAX:MapOffset.ANTILAG_EGT_MAX+2])[0],
        timing_rpm_axis=list(struct.unpack('<8H', data[MapOffset.ANTILAG_TIMING_RPM_AXIS:MapOffset.ANTILAG_TIMING_RPM_AXIS+16])),
        timing_boost_axis=list(struct.unpack('<8H', data[MapOffset.ANTILAG_TIMING_BOOST_AXIS:MapOffset.ANTILAG_TIMING_BOOST_AXIS+16])),
        timing_base=list(struct.unpack('<64H', data[MapOffset.ANTILAG_TIMING_BASE:MapOffset.ANTILAG_TIMING_BASE+128])),
    )


def write_speed_limiter_to_bin(data: bytearray, values: SpeedLimiterStock) -> None:
    """Write speed limiter values to binary data (in-place)"""
    struct.pack_into('<H', data, MapOffset.SPEED_LIMITER_MASTER, values.master)
    data[MapOffset.SPEED_LIMITER_ARRAY:MapOffset.SPEED_LIMITER_ARRAY+4] = bytes(values.array)
    data[MapOffset.SPEED_LIMITER_DISABLE] = values.disable


def write_rev_limiter_to_bin(data: bytearray, values: RevLimiterStock) -> None:
    """Write rev limiter values to binary data (in-place)"""
    data[MapOffset.REV_GEAR_AXIS:MapOffset.REV_GEAR_AXIS+9] = bytes(values.gear_axis)
    struct.pack_into('<8H', data, MapOffset.REV_CLUTCH_PRESSED, *values.clutch_pressed)
    struct.pack_into('<9H', data, MapOffset.REV_FLOOR_MT, *values.floor_mt)
    struct.pack_into('<9H', data, MapOffset.REV_CEILING_MT, *values.ceiling_mt)
    struct.pack_into('<9H', data, MapOffset.REV_FLOOR_AT, *values.floor_at)
    struct.pack_into('<9H', data, MapOffset.REV_CEILING_AT, *values.ceiling_at)
    struct.pack_into('<9H', data, MapOffset.REV_CEILING_AT_MANUAL, *values.ceiling_at_manual)
    struct.pack_into('<9H', data, MapOffset.REV_FLOOR_AT_MANUAL, *values.floor_at_manual)
    struct.pack_into('<9H', data, MapOffset.REV_TIME_BUMPS_AT, *values.time_between_bumps_at)
    struct.pack_into('<9H', data, MapOffset.REV_TIME_BUMPS_AT_MANUAL, *values.time_between_bumps_at_manual)
    struct.pack_into('<9H', data, MapOffset.REV_TIME_BUMPS_MT, *values.time_between_bumps_mt)


def write_antilag_to_bin(data: bytearray, values: AntilagStock) -> None:
    """Write antilag/launch control values to binary data (in-place)"""
    data[MapOffset.ANTILAG_ENABLE] = values.enable
    struct.pack_into('<H', data, MapOffset.ANTILAG_BOOST_TARGET, values.boost_target)
    data[MapOffset.ANTILAG_COOLDOWN] = values.cooldown_timer
    struct.pack_into('<H', data, MapOffset.ANTILAG_FUEL_TARGET, values.fuel_target)
    struct.pack_into('<H', data, MapOffset.ANTILAG_COOLANT_MIN, values.coolant_min)
    struct.pack_into('<H', data, MapOffset.ANTILAG_COOLANT_MAX, values.coolant_max)
    struct.pack_into('<H', data, MapOffset.ANTILAG_EGT_MAX, values.egt_max)
    struct.pack_into('<8H', data, MapOffset.ANTILAG_TIMING_RPM_AXIS, *values.timing_rpm_axis)
    struct.pack_into('<8H', data, MapOffset.ANTILAG_TIMING_BOOST_AXIS, *values.timing_boost_axis)
    struct.pack_into('<64H', data, MapOffset.ANTILAG_TIMING_BASE, *values.timing_base)


def get_stock_values_summary() -> Dict[str, Any]:
    """Return a summary of all stock values for display"""
    return {
        'speed_limiter': {
            'master_raw': STOCK_SPEED_LIMITER.master,
            'master_mph': STOCK_SPEED_LIMITER.master_mph,
            'master_kmh': STOCK_SPEED_LIMITER.master_kmh,
            'disable': STOCK_SPEED_LIMITER.disable,
        },
        'rev_limiter': {
            'clutch_pressed': STOCK_REV_LIMITER.clutch_pressed,
            'floor_mt': STOCK_REV_LIMITER.floor_mt,
            'ceiling_mt': STOCK_REV_LIMITER.ceiling_mt,
        },
        'antilag': {
            'enable': STOCK_ANTILAG.enable,
            'boost_target_psi': STOCK_ANTILAG.boost_target / 831.52 if STOCK_ANTILAG.boost_target else 0,
        }
    }


if __name__ == "__main__":
    print("Stock Values Summary:")
    print("=" * 60)
    summary = get_stock_values_summary()
    
    print("\nSpeed Limiter:")
    print(f"  Master: {summary['speed_limiter']['master_mph']:.1f} mph / {summary['speed_limiter']['master_kmh']:.1f} km/h")
    print(f"  Disabled: {bool(summary['speed_limiter']['disable'])}")
    
    print("\nRev Limiter (MT):")
    print(f"  Clutch Pressed: {summary['rev_limiter']['clutch_pressed']} RPM")
    print(f"  Floor: {summary['rev_limiter']['floor_mt']} RPM")
    print(f"  Ceiling: {summary['rev_limiter']['ceiling_mt']} RPM")
    
    print("\nAntilag:")
    print(f"  Enabled: {bool(summary['antilag']['enable'])}")
    print(f"  Boost Target: {summary['antilag']['boost_target_psi']:.1f} PSI")
