#!/usr/bin/env python3
"""
BMW N54 Map Options - User Tuning Configuration Classes
========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Defines user-configurable tuning options for N54 ECU maps.
    Provides data classes for burbles, VMAX, DTCs, launch control,
    rev limiter, and boost settings with preset configurations.
    All options modify calibration data before flashing.

Features:
    - Type-safe option definitions using dataclasses
    - Preset configurations (Stock, Stage 1, Stage 2, Stage 3)
    - Validation and serialization support
    - Interactive configuration builder

Classes:
    BurbleMode(Enum) - Burble/pops intensity modes
    TransmissionMode(Enum) - Auto/Manual transmission types
    BurbleOptions - Burble/pops configuration
    VMAXOptions - Speed limiter configuration
    DTCOptions - Diagnostic code management
    LaunchControlOptions - Launch control settings
    RevLimiterOptions - RPM limiter configuration
    BoostOptions - Boost pressure settings
    MapOptions - Complete tuning configuration container

Functions:
    get_preset(name: str) -> Optional[MapOptions]
    list_presets() -> List[str]

Variables (Module-level):
    PRESET_MAP: Dict[str, Callable] - Preset configuration factory
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from flash_tool.tuning_parameters import TuningPreset

class BurbleMode(Enum):
    """Burble/pops intensity modes"""
    DISABLED = "disabled"
    NORMAL = "normal"
    SPORT = "sport"
    CUSTOM = "custom"

class TransmissionMode(Enum):
    """Transmission type"""
    MANUAL = "manual"
    AUTOMATIC = "automatic"

@dataclass
class BurbleOptions:
    """Exhaust burbles/pops configuration"""
    enabled: bool = False
    mode: BurbleMode = BurbleMode.NORMAL
    min_rpm: int = 2000
    max_rpm: int = 7000
    min_ect: int = 60  # Engine coolant temp (°C)
    min_speed: int = 0  # km/h
    max_speed: int = 250  # km/h
    max_egt_turbo: int = 950  # °C
    max_egt_cat: int = 900  # °C
    lambda_target: float = 0.85  # Rich for burbles
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'mode': self.mode.value,
            'min_rpm': self.min_rpm,
            'max_rpm': self.max_rpm,
            'min_ect': self.min_ect,
            'min_speed': self.min_speed,
            'max_speed': self.max_speed,
            'max_egt_turbo': self.max_egt_turbo,
            'max_egt_cat': self.max_egt_cat,
            'lambda_target': self.lambda_target
        }

@dataclass
class VMAXOptions:
    """Speed limiter configuration"""
    enabled: bool = False  # True = remove/raise limit
    limit_kmh: int = 255  # 255 = effectively no limit
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'limit_kmh': self.limit_kmh
        }

@dataclass
class DTCOptions:
    """DTC/CEL configuration"""
    disable_cat_codes: bool = False  # P0420/P0430
    disable_o2_codes: bool = False   # Secondary O2 sensors
    disable_evap_codes: bool = False  # EVAP system
    disable_knock_cel: bool = False   # Keep knock detection but no CEL
    custom_codes: List[str] = None    # Manual DTC list
    
    def __post_init__(self):
        if self.custom_codes is None:
            self.custom_codes = []
    
    def to_dict(self) -> dict:
        return {
            'disable_cat_codes': self.disable_cat_codes,
            'disable_o2_codes': self.disable_o2_codes,
            'disable_evap_codes': self.disable_evap_codes,
            'disable_knock_cel': self.disable_knock_cel,
            'custom_codes': self.custom_codes
        }

@dataclass
class LaunchControlOptions:
    """Launch control/antilag configuration"""
    enabled: bool = False
    timing_retard: int = -10  # Degrees
    boost_target: float = 1.5  # bar (relative)
    rpm_threshold: int = 4000
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'timing_retard': self.timing_retard,
            'boost_target': self.boost_target,
            'rpm_threshold': self.rpm_threshold
        }

@dataclass
class RevLimiterOptions:
    """Rev limiter configuration"""
    enabled: bool = False  # True = raise/remove
    soft_limit: int = 7200  # RPM
    hard_limit: int = 7500  # RPM
    per_gear_limits: bool = False
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'soft_limit': self.soft_limit,
            'hard_limit': self.hard_limit,
            'per_gear_limits': self.per_gear_limits
        }

@dataclass
class BoostOptions:
    """Boost pressure configuration"""
    enabled: bool = False  # True = increase limits
    max_boost_bar: float = 1.4  # Absolute (relative to atmospheric)
    per_gear_limits: bool = True
    overboost_duration: int = 10  # seconds
    
    def to_dict(self) -> dict:
        return {
            'enabled': self.enabled,
            'max_boost_bar': self.max_boost_bar,
            'per_gear_limits': self.per_gear_limits,
            'overboost_duration': self.overboost_duration
        }

@dataclass
class MapOptions:
    """
    Complete map options configuration.
    All options are applied via runtime patching before flash.
    """
    burbles: BurbleOptions = None
    vmax: VMAXOptions = None
    dtc: DTCOptions = None
    launch_control: LaunchControlOptions = None
    rev_limiter: RevLimiterOptions = None
    boost: BoostOptions = None
    
    # Metadata
    transmission: TransmissionMode = TransmissionMode.MANUAL
    octane: int = 93  # Fuel octane rating
    ethanol_content: int = 0  # E0, E10, E30, E85 etc.
    
    def __post_init__(self):
        if self.burbles is None:
            self.burbles = BurbleOptions()
        if self.vmax is None:
            self.vmax = VMAXOptions()
        if self.dtc is None:
            self.dtc = DTCOptions()
        if self.launch_control is None:
            self.launch_control = LaunchControlOptions()
        if self.rev_limiter is None:
            self.rev_limiter = RevLimiterOptions()
        if self.boost is None:
            self.boost = BoostOptions()
    
    def to_dict(self) -> dict:
        """Export all options to dictionary"""
        return {
            'burbles': self.burbles.to_dict(),
            'vmax': self.vmax.to_dict(),
            'dtc': self.dtc.to_dict(),
            'launch_control': self.launch_control.to_dict(),
            'rev_limiter': self.rev_limiter.to_dict(),
            'boost': self.boost.to_dict(),
            'transmission': self.transmission.value,
            'octane': self.octane,
            'ethanol_content': self.ethanol_content
        }
    
    def get_enabled_options(self) -> List[str]:
        """Get list of enabled option names"""
        enabled = []
        if self.burbles.enabled:
            enabled.append(f"Burbles ({self.burbles.mode.value})")
        if self.vmax.enabled:
            enabled.append(f"VMAX ({self.vmax.limit_kmh} km/h)")
        if any([self.dtc.disable_cat_codes, self.dtc.disable_o2_codes, 
                self.dtc.disable_evap_codes, self.dtc.disable_knock_cel,
                self.dtc.custom_codes]):
            enabled.append("DTC Disable")
        if self.launch_control.enabled:
            enabled.append("Launch Control")
        if self.rev_limiter.enabled:
            enabled.append(f"Rev Limiter ({self.rev_limiter.hard_limit} RPM)")
        if self.boost.enabled:
            enabled.append(f"Boost ({self.boost.max_boost_bar} bar)")
        
        return enabled
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate option configuration
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Burbles validation
        if self.burbles.enabled:
            if self.burbles.min_rpm >= self.burbles.max_rpm:
                errors.append("Burbles: min_rpm must be < max_rpm")
            if self.burbles.lambda_target < 0.7 or self.burbles.lambda_target > 1.0:
                errors.append("Burbles: lambda_target must be 0.7-1.0")
        
        # VMAX validation
        if self.vmax.enabled:
            if self.vmax.limit_kmh < 100 or self.vmax.limit_kmh > 350:
                errors.append("VMAX: limit must be 100-350 km/h")
        
        # Launch control validation
        if self.launch_control.enabled:
            if self.launch_control.timing_retard > 0:
                errors.append("Launch control: timing_retard must be negative")
            if self.launch_control.boost_target < 1.0 or self.launch_control.boost_target > 2.5:
                errors.append("Launch control: boost_target must be 1.0-2.5 bar")
        
        # Rev limiter validation
        if self.rev_limiter.enabled:
            if self.rev_limiter.soft_limit >= self.rev_limiter.hard_limit:
                errors.append("Rev limiter: soft_limit must be < hard_limit")
            if self.rev_limiter.hard_limit > 8000:
                errors.append("Rev limiter: hard_limit max 8000 RPM (safety)")
        
        # Boost validation
        if self.boost.enabled:
            if self.boost.max_boost_bar < 1.0 or self.boost.max_boost_bar > 2.0:
                errors.append("Boost: max_boost must be 1.0-2.0 bar")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def from_tuning_preset(cls, preset: 'TuningPreset') -> 'MapOptions':
        """
        Convert a TuningPreset to a MapOptions object.
        
        This bridges the tuning_parameters preset system (raw parameter values)
        with the map_options system (high-level tuning configuration).
        
        Args:
            preset: TuningPreset object with parameter values
            
        Returns:
            MapOptions object configured to match the preset
            
        Example:
            >>> from flash_tool.tuning_parameters import PRESET_STAGE1
            >>> map_opts = MapOptions.from_tuning_preset(PRESET_STAGE1)
            >>> patcher.create_patchset_from_map_options(map_opts)
        """
        values = preset.values
        
        # Helper function to get scalar value from parameter (may be list or scalar)
        def get_scalar(key: str, default=0):
            val = values.get(key, default)
            if isinstance(val, list) and len(val) > 0:
                # Recursively extract if nested lists
                while isinstance(val, list) and len(val) > 0:
                    val = val[0]
                return val if val is not None else default
            elif isinstance(val, list):
                return default
            return val
        
        # Extract burble settings
        burble_normal = get_scalar('burble_duration_normal', 0)
        burble_sport = get_scalar('burble_duration_sport', 0)
        burbles = BurbleOptions(
            enabled=bool(burble_normal > 0 or burble_sport > 0),
            mode=BurbleMode.SPORT if burble_sport > 100 else BurbleMode.NORMAL,
            min_rpm=2000,
            max_rpm=7000,
            lambda_target=0.85
        )
        
        # Extract VMAX settings (infer from speed limiter disable)
        speed_disable = get_scalar('speed_limiter_disable', 0)
        vmax = VMAXOptions(
            enabled=bool(speed_disable > 0),
            limit_kmh=255 if speed_disable > 0 else 250
        )
        
        # Extract DTC settings
        dtc = DTCOptions(
            disable_cat_codes=get_scalar('dtc_overboost', 0xFFFF) == 0x0000,
            disable_o2_codes=get_scalar('dtc_underboost', 0xFFFF) == 0x0000,
            disable_evap_codes=get_scalar('dtc_boost_deactivation', 0xFFFF) == 0x0000,
            disable_knock_cel=False  # Never auto-disable knock
        )
        
        # Extract launch control settings (from antilag params)
        antilag_en = get_scalar('antilag_enable', 0)
        antilag_threshold = get_scalar('antilag_boost_target', 4000)
        launch_control = LaunchControlOptions(
            enabled=bool(antilag_en),
            rpm_threshold=int(antilag_threshold),
            boost_target=1.2,  # Default safe value
            timing_retard=-10
        )
        
        # Extract rev limiter settings
        rev_ceiling_mt = values.get('rev_limiter_ceiling_mt')
        if rev_ceiling_mt and isinstance(rev_ceiling_mt, list) and len(rev_ceiling_mt) > 0:
            max_rev = max(rev_ceiling_mt)
            rev_limiter = RevLimiterOptions(
                enabled=max_rev > 7000,
                soft_limit=max_rev - 200,
                hard_limit=max_rev
            )
        else:
            rev_limiter = RevLimiterOptions(enabled=False)
        
        # Infer boost settings from WGDC values
        wgdc_base = values.get('wgdc_base', [])
        if wgdc_base and isinstance(wgdc_base, list):
            # Flatten nested lists (2D arrays) to calculate average
            flat_wgdc = []
            for item in wgdc_base:
                if isinstance(item, list):
                    flat_wgdc.extend(item)
                else:
                    flat_wgdc.append(item)
            avg_wgdc = sum(flat_wgdc) / len(flat_wgdc) if flat_wgdc else 0
            # Rough conversion: stock ~40-50%, stage1 ~55-65%, stage2 ~70-80%
            if avg_wgdc > 65:
                boost_bar = 1.35  # Stage 2 level
            elif avg_wgdc > 52:
                boost_bar = 1.15  # Stage 1 level
            else:
                boost_bar = 0.95  # Stock
            
            boost = BoostOptions(
                enabled=avg_wgdc > 52,
                max_boost_bar=boost_bar
            )
        else:
            boost = BoostOptions(enabled=False)
        
        # Determine octane from ethanol content
        ethanol = values.get('static_ethanol_content', 0)
        if ethanol >= 85:
            octane = 105  # E85
        elif ethanol >= 30:
            octane = 95  # E30 mix
        else:
            octane = 93  # Pump gas
        
        return cls(
            burbles=burbles,
            vmax=vmax,
            dtc=dtc,
            launch_control=launch_control,
            rev_limiter=rev_limiter,
            boost=boost,
            transmission=TransmissionMode.MANUAL,
            octane=octane,
            ethanol_content=ethanol
        )


# ========================================
# PRESET SYSTEM REFERENCE
# ========================================
# NOTE: Presets are now defined in tuning_parameters.py:
#   - PRESET_STOCK (Stage 0 equivalent)
#   - PRESET_STAGE1 (Stage 1)
#   - PRESET_STAGE2 (Stage 2)
#   - PRESET_STAGE25 (Stage 2.5 - intermediate)
#   - PRESET_STAGE3 (Stage 3)
#
# To use tuning_parameters presets with MapPatcher:
#   from flash_tool.tuning_parameters import PRESET_STAGE1
#   map_opts = MapOptions.from_tuning_preset(PRESET_STAGE1)
#   patcher.create_patchset_from_map_options(map_opts)
#
# This consolidates preset definitions to a single source of truth
# while maintaining MapOptions as a high-level interface for map_patcher.

# Legacy preset mapping for backwards compatibility
# These are lazy-loaded from tuning_parameters on first access
PRESET_MAP: Dict[str, MapOptions] = {}

# Hardware requirements by stage
# Note: Uses tuning_parameters preset names (stock, stage1, stage2, stage2.5, stage3)
HARDWARE_REQUIREMENTS = {
    "stock": [
        "Stock hardware only",
        "No modifications required"
    ],
    "stage1": [
        "✅ Stock hardware compatible",
        "Recommended: upgraded air filter",
        "Optional: oil catch can"
    ],
    "stage2": [
        "⚠️ REQUIRED: Upgraded FMIC (front mount intercooler)",
        "⚠️ REQUIRED: Upgraded charge pipe (plastic stock fails at this boost)",
        "⚠️ REQUIRED: Catless downpipes (for DTC disable to work)",
        "Recommended: upgraded inlets, oil catch can, spark plugs (1-step colder)",
        "Manual trans: upgraded clutch recommended"
    ],
    "stage2.5": [
        "⚠️ REQUIRED: All Stage 2 hardware",
        "⚠️ REQUIRED: Upgraded valve springs (for 7300 RPM)",
        "Recommended: upgraded clutch (manual), built transmission (auto)"
    ],
    "stage3": [
        "⚠️ REQUIRED: All Stage 2 hardware",
        "⚠️ REQUIRED: Upgraded turbos OR pure turbos (Stage 3 singles)",
        "⚠️ REQUIRED: Port injection (DI + PI)",
        "⚠️ REQUIRED: Upgraded fuel pump (LPFP + HPFP)",
        "⚠️ REQUIRED: Upgraded valve springs + retainers (for 7500 RPM)",
        "⚠️ REQUIRED: Heavy-duty clutch (manual) or built transmission (auto)",
        "Recommended: methanol injection, upgraded oil cooler, upgraded transmission cooler"
    ]
}

# Power targets by stage (flywheel HP/TQ estimates)
# Note: Uses tuning_parameters preset names (stock, stage1, stage2, stage2.5, stage3)
POWER_TARGETS = {
    "stock": "300 HP / 300 lb-ft (factory N54 spec)",
    "stage1": "350-360 HP / 360-370 lb-ft (+50-60 HP / +60-70 TQ)",
    "stage2": "400-420 HP / 420-440 lb-ft (+100-120 HP / +120-140 TQ)",
    "stage2.5": "425-450 HP / 445-470 lb-ft (+125-150 HP / +145-170 TQ)",
    "stage3": "450-480 HP / 470-500 lb-ft (+150-180 HP / +170-200 TQ)"
}



def get_preset(name: str) -> Optional[MapOptions]:
    """Get preset configuration by name
    
    Lazy-loads presets from tuning_parameters on first access.
    
    Args:
        name: Preset name - supports both formats:
              - "Stage 0", "Stage 1", "Stage 2", "Stage 3" (legacy)
              - "stock", "stage1", "stage2", "stage2.5", "stage3" (tuning_parameters)
    
    Returns:
        MapOptions object or None if not found
    """
    # Normalize name
    name_lower = name.lower().replace(" ", "")
    
    # Map legacy names to tuning_parameters names
    name_map = {
        "stage0": "stock",
        "stage1": "stage1",
        "stage2": "stage2",
        "stage2.5": "stage2.5",
        "stage3": "stage3",
        "stock": "stock",
    }
    
    preset_key = name_map.get(name_lower)
    if not preset_key:
        return None
    
    # Lazy-load from tuning_parameters
    try:
        from flash_tool.tuning_parameters import ALL_PRESETS
        tuning_preset = ALL_PRESETS.get(preset_key)
        if tuning_preset:
            return MapOptions.from_tuning_preset(tuning_preset)
    except ImportError:
        pass
    
    return None


def list_presets() -> List[str]:
    """Get list of available preset names
    
    Returns:
        List of preset names from tuning_parameters: stock, stage1, stage2, stage2.5, stage3
    """
    try:
        from flash_tool.tuning_parameters import ALL_PRESETS
        return list(ALL_PRESETS.keys())
    except ImportError:
        return ["stock", "stage1", "stage2", "stage3"]  # Fallback


def get_hardware_requirements(preset_name: str) -> List[str]:
    """Get hardware requirements for a specific preset
    
    Args:
        preset_name: Name of the preset
    
    Returns:
        List of hardware requirement strings
    """
    return HARDWARE_REQUIREMENTS.get(preset_name, ["Unknown preset"])


def get_power_target(preset_name: str) -> str:
    """Get power target description for a specific preset
    
    Args:
        preset_name: Name of the preset
    
    Returns:
        Power target description string
    """
    return POWER_TARGETS.get(preset_name, "Unknown preset")


def get_stage_summary(preset_name: str) -> str:
    """Get comprehensive summary of a stage including specs, hardware, and power
    
    Args:
        preset_name: Name of the preset
    
    Returns:
        Multi-line formatted summary string
    """
    preset = get_preset(preset_name)
    if not preset:
        return f"Unknown preset: {preset_name}"
    
    hardware = get_hardware_requirements(preset_name)
    power = get_power_target(preset_name)
    
    summary = f"\n{'='*70}\n"
    summary += f"{preset_name}\n"
    summary += f"{'='*70}\n\n"
    
    # Power targets
    summary += f"💥 POWER TARGET: {power}\n\n"
    
    # Tuning specs
    summary += "⚙️ TUNING SPECIFICATIONS:\n"
    if preset.boost.enabled:
        summary += f"  • Boost: {preset.boost.max_boost_bar:.2f} bar ({preset.boost.max_boost_bar * 14.5:.1f} psi)\n"
    else:
        summary += f"  • Boost: Stock (~0.9 bar / 13 psi)\n"
    
    if preset.rev_limiter.enabled:
        summary += f"  • Rev Limit: {preset.rev_limiter.hard_limit} RPM\n"
    else:
        summary += f"  • Rev Limit: Stock (7000 RPM)\n"
    
    summary += f"  • Octane: {preset.octane}+ minimum\n"
    
    if preset.burbles.enabled:
        summary += f"  • Burbles: {preset.burbles.mode.value} mode\n"
    
    if preset.vmax.enabled:
        summary += f"  • VMAX: Removed (set to {preset.vmax.limit_kmh} km/h)\n"
    
    if preset.launch_control.enabled:
        summary += f"  • Launch Control: Enabled ({preset.launch_control.boost_target:.2f} bar target)\n"
    
    # Hardware requirements
    summary += f"\n🔧 HARDWARE REQUIREMENTS:\n"
    for req in hardware:
        summary += f"  {req}\n"
    
    # DTC status
    summary += f"\n⚠️ DTC MONITORING:\n"
    if preset.dtc.disable_cat_codes:
        summary += "  • Catalyst: DISABLED (catless downpipes)\n"
    else:
        summary += "  • Catalyst: ENABLED (stock cats)\n"
    
    if preset.dtc.disable_o2_codes:
        summary += "  • O2 Sensors: DISABLED\n"
    else:
        summary += "  • O2 Sensors: ENABLED\n"
    
    if preset.dtc.disable_knock_cel:
        summary += "  • Knock Sensors: DISABLED CEL (NOT RECOMMENDED)\n"
    else:
        summary += "  • Knock Sensors: ENABLED (CEL active on knock)\n"
    
    summary += f"\n{'='*70}\n"
    
    return summary
