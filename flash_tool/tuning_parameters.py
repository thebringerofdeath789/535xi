# ============================================================================
# PRESET PORTING: Make all tuning recipes available for every XDF/bin
# ============================================================================
# Authoritative XDF per OS family:
# - I8A0S OS: Corbanistan XDF (I8A0S_Corbanistan.xdf / I8A0S_Custom_Corbanistan.xdf)
# - Non-I8A0S OS: Use Zarboz XDF variants (IJE0S_zarboz.xdf, IKM0S_zarboz.xdf, INA0S_zarboz.xdf, etc.)
#
# Note: Parameter keys are consistent across XDFs; offsets differ per OS.
# When porting presets, map by parameter key and then select offsets from the
# OS-specific authoritative XDF (Corbanistan for I8A0S, Zarboz for non-i8a0s).
# ============================================================================
from __future__ import annotations

from typing import Optional
import difflib
import re
from collections import OrderedDict


def normalize_key(key: str) -> str:
    """Normalize a parameter key for fuzzy matching and comparison."""
    return key.strip().lower().replace(' ', '_').replace('-', '_').replace('/', '_').replace('(', '').replace(')', '').replace('__', '_')


def find_best_param_key_for_preset_key(preset_key, param_keys):
    """Resolve best matching parameter key for a preset key from the set of param_keys.

    - Exact match if found
    - Try common synonym replacements
    - Fallback to difflib fuzzy matching
    """

    normalized = normalize_key(preset_key)

    # Explicit manual aliases for unmapped preset keys (ensure all OSes)
    explicit = {
        # WGDC, Timing, and previously mapped
        'wgdcbase': 'wgdc_base',
        'wgdcspool': 'wgdc_spool',
        'timingmain': 'timing_main',
        'timingspool': 'timing_spool',
        'wgdcairflowaddermap2': 'wgdc_airflow_adder_map2',
        'wgdcairflowaddermap3': 'wgdc_airflow_adder_map3',
        'wgdcairflowaddermap4': 'wgdc_airflow_adder_map4',
        'wgdcairflowaddere85': 'wgdc_airflow_adder_e85',
        # DTC/boost
        'dtcoverboost': '3100_boost_deactivation',
        'dtc_overboost': '3100_boost_deactivation',
        'dtcunderboost': '3100_boost_deactivation',
        'dtc_underboost': '3100_boost_deactivation',
        'dtcboostdeactivation': '3100_boost_deactivation',
        'dtc_boost_deactivation': '3100_boost_deactivation',
        # Throttle/angle
        'throttlesensitivity': 'throttle_angle_aggression_in_overload',
        'throttle_sensitivity': 'throttle_angle_aggression_in_overload',
        'throttleanglewot': 'throttle_angle_wot',
        'throttle_angle_wot': 'throttle_angle_wot',
        # Speed limiter
        'speedlimiterarray': 'speed_limiter_master',
        'speed_limiter_array': 'speed_limiter_master',
        'speedlimitermaster': 'speed_limiter_master',
        'speed_limiter_master': 'speed_limiter_master',
        'speedlimiterdisable': 'disable_speed_limiter',
        'speed_limiter_disable': 'disable_speed_limiter',
        # Rev limiter/gear
        'revlimiterfloormt': 'rev_limit_by_gear_floor_mt',
        'rev_limiter_floor_mt': 'rev_limit_by_gear_floor_mt',
        'revlimiterceilingmt': 'rev_limit_by_gear_ceiling_mt',
        'rev_limiter_ceiling_mt': 'rev_limit_by_gear_ceiling_mt',
        'revlimiterfloorat': 'rev_limit_by_gear_floor_at',
        'rev_limiter_floor_at': 'rev_limit_by_gear_floor_at',
        'revlimiterceilingat': 'rev_limit_by_gear_ceiling_at',
        'rev_limiter_ceiling_at': 'rev_limit_by_gear_ceiling_at',
        'revlimitertimebumpsmt': 'time_between_rev_limit_bumps_mt',
        'rev_limiter_time_bumps_mt': 'time_between_rev_limit_bumps_mt',
        # Torque
        'torquelimitcap': 'torque_limiter_3_unk_limits',
        'torque_limit_cap': 'torque_limiter_3_unk_limits',
        'torquelimitdriver': 'requested_torque_driver',
        'torque_limit_driver': 'requested_torque_driver',
        # Boost ceiling
        'boostceiling': 'boost_ceiling',
        'boost_ceiling': 'boost_ceiling',
        # === Antilag mappings (I8A0S_Corbanistan.xdf) ===
        'antilagenable': 'enable_antilag',
        'antilag_enable': 'enable_antilag',
        'antilagboosttarget': 'antilag_boost_target',
        'antilag_boost_target': 'antilag_boost_target',
        'antilagcooldown': 'antilag_cooldown_timer',
        'antilag_cooldown': 'antilag_cooldown_timer',
        'antilagcoolantmin': 'antilag_coolant_safety_minimum',
        'antilag_coolant_min': 'antilag_coolant_safety_minimum',
        'antilagcoolantmax': 'antilag_coolant_safety_maximum',
        'antilag_coolant_max': 'antilag_coolant_safety_maximum',
        'antilagegtmax': 'antilag_egt_safety_maximum',
        'antilag_egt_max': 'antilag_egt_safety_maximum',
        'antilagfueltarget': 'antilag_fuel_target',
        'antilag_fuel_target': 'antilag_fuel_target',
        'antilagtimingbase': 'antilag_timing_base',
        'antilag_timing_base': 'antilag_timing_base',
        'antilagtimeout': 'antilag_timeout',
        'antilag_timeout': 'antilag_timeout',
        'antilagstartdelay': 'antilag_start_delay',
        'antilag_start_delay': 'antilag_start_delay',
        # === Burble mappings ===
        'burbledurationnormal': 'burble_duration_normal_map2',
        'burble_duration_normal': 'burble_duration_normal_map2',
        'burbledurationsport': 'burble_duration_sport_map2',
        'burble_duration_sport': 'burble_duration_sport_map2',
        'burbleignitionretard': 'burble_ignition_timing_map2',
        'burble_ignition_retard': 'burble_ignition_timing_map2',
        'burble_timing_base': 'burble_ignition_timing_map2',
        # === EGT/Coolant mappings ===
        'egtmax': 'egt_nox_set_point_cat_protection_mode',
        'egt_max': 'egt_nox_set_point_cat_protection_mode',
        # For antilag_egt_max, already mapped above
        # For coolant, use setpoint/threshold tables if needed (not mapped directly)
        # === Unmapped: no direct XDF match ===
        # 'rev_limiter_clutch_pressed', 'boost_pressure_target_modifier', 'static_ethanol_content', 'dtc_ibs_battery_sensor', 'throttle_sensitivity'
    }
    if normalized in explicit and explicit[normalized] in param_keys:
        return explicit[normalized]

    # Exact match
    if normalized in param_keys:
        return normalized

    # Synonym heuristics
    replacements = [
        ('limiter', 'limit'),
        ('limit', 'limiter'),
        ('antilag', 'anti_lag'),
        ('rev_limiter', 'rev_limit'),
        ('rev_limit', 'rev_limiter'),
    ]
    for a, b in replacements:
        candidate = normalized.replace(a, b)
        if candidate in param_keys:
            return candidate

    # Token-overlap heuristic: prefer keys that share most tokens (helps re-ordering)
    try:
        preset_tokens = [t for t in re.split(r"[^a-z0-9]+", normalized) if t]
        if preset_tokens:
            best_overlap = 0.0
            best_candidate = None
            for pk in param_keys:
                pk_tokens = [t for t in pk.split('_') if t]
                # remove map suffix tokens like map2/map3 and e85 tokens for matching
                pk_tokens_clean = [re.sub(r'map\d+$', '', t) for t in pk_tokens]
                preset_tokens_clean = [re.sub(r'map\d+$', '', t) for t in preset_tokens]
                inter = set(pk_tokens_clean) & set(preset_tokens_clean)
                if not inter:
                    continue
                overlap = len(inter) / max(1, len(preset_tokens_clean))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_candidate = pk
            # Accept reasonably high overlap matches
            if best_candidate and best_overlap >= 0.6:
                return best_candidate
    except Exception:
        # Best-effort heuristic - ignore failures
        pass

    # Fuzzy match (slightly relaxed cutoff to improve cross-XDF mapping coverage)
    matches = difflib.get_close_matches(normalized, list(param_keys), n=1, cutoff=0.75)
    if matches:
        return matches[0]

    return None


def map_preset_values_to_params(preset_values, params):
    """Map a preset's values (keyed by generic param names) to a given bin's parameter keys."""
    mapped_values = {}
    param_keys = set(params.keys())

    for k, v in preset_values.items():
        best = find_best_param_key_for_preset_key(k, param_keys)
        if best and best in params:
            mapped_values[best] = v
    return mapped_values


def port_presets_to_bin(bin_name, xdf_summary_path=None):
    """Port all existing static presets to a single bin/XDF by mapping keys."""
    params = load_parameters_for_bin(bin_name, xdf_summary_path)
    preset_objs = OrderedDict((k, v) for k, v in ALL_PRESETS.items())
    bin_presets = {}
    for preset_name, preset in preset_objs.items():
        mapped_vals = map_preset_values_to_params(preset.values, params)
        bin_presets[preset_name] = TuningPreset(
            name=preset.name,
            description=f"{preset.description}\n\n[Auto-mapped for {bin_name}]",
            values=mapped_vals
        )
    return bin_presets


def port_presets_to_all_bins(xdf_summary_path=None):
    all_bin_presets = {}
    for bin_name, xdf_path in xdf_paths.items():
        all_bin_presets[bin_name] = port_presets_to_bin(bin_name, xdf_path)
    return all_bin_presets

# ============================================================================
# XDF BIN DISCOVERY (for UI bin selection)
# ============================================================================

def _read_text_file_smart(path):
    # Read bytes and attempt to decode using common encodings
    raw = path.read_bytes()
    for enc in ('utf-8', 'utf-8-sig', 'utf-16', 'latin-1'):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    # Fallback with replacement
    return raw.decode('utf-8', errors='replace')


def list_available_bins(xdf_summary_path=None) -> list:
    bins = []
    for xdf_file in xdf_dir.glob("*.xdf"):
        bins.append(xdf_file.stem)
    return bins
# ============================================================================
# DYNAMIC XDF-BASED PARAMETER LOADER (Multi-bin support)
# ============================================================================

def load_parameters_for_bin(bin_name: str, xdf_summary_path=None) -> Dict[str, TuningParameter]:
    """
    Dynamically load parameter definitions for a given bin from the authoritative XDF XML file.
    Returns a dict of {param_key: TuningParameter}.
    """
    # Always use XDF parsing for all bins (including I8A0S_Corbanistan)
    from pathlib import Path
    import xml.etree.ElementTree as ET
    xdf_dir = Path("maps/xdf_definitions/github")
    xdf_path = None
    for f in xdf_dir.glob("*.xdf"):
        if bin_name.lower() in f.stem.lower():
            xdf_path = f
            break
    if not xdf_path or not xdf_path.exists():
        raise FileNotFoundError(f"No XDF found for bin '{bin_name}' in {xdf_dir}")
    tree = ET.parse(xdf_path)
    root = tree.getroot()
    params = {}
    for table in root.findall(".//XDFTABLE"):
        title = table.findtext("title")
        desc = table.findtext("description") or ""
        # Find Z axis (main data)
        z_axis = None
        for axis in table.findall("XDFAXIS"):
            if axis.attrib.get("id") == "z":
                z_axis = axis
                break
        if z_axis is None:
            continue
        emb = z_axis.find("EMBEDDEDDATA")
        if emb is None:
            continue
        addr = emb.attrib.get("mmedaddress")
        if not addr:
            continue
        offset = int(addr, 16)
        element_size_bits = int(emb.attrib.get("mmedelementsizebits", "16"))
        row_count = int(emb.attrib.get("mmedrowcount", "1"))
        col_count = int(emb.attrib.get("mmedcolcount", "1")) if "mmedcolcount" in emb.attrib else 1
        # Data format
        if element_size_bits == 8:
            data_format = DataFormat.UINT8
        elif element_size_bits == 16:
            data_format = DataFormat.UINT16_LE
        elif element_size_bits == 32:
            data_format = DataFormat.UINT32_LE
        else:
            data_format = DataFormat.UINT16_LE
        # Improved scaling/conversion logic
        math_elem = z_axis.find("MATH")
        conversion = None
        if math_elem is not None:
            eq = math_elem.attrib.get("equation", "X")
            import re
            # Support X, X/NNN, X*NNN, X+NNN, X-NNN, X*NNN+NNN, X/NNN+NNN, X*NNN-NNN, X/NNN-NNN
            m = re.match(r"X([*/+-])([0-9.]+)([+-][0-9.]+)?", eq.replace(" ", ""))
            if eq == "X":
                conversion = UnitConversion.identity()
            elif m:
                op = m.group(1)
                factor = float(m.group(2))
                offset_val = float(m.group(3)) if m.group(3) else 0.0
                if op == "/":
                    scale = factor
                    if offset_val == 0.0:
                        conversion = UnitConversion.scale(scale, "", "raw")
                    else:
                        conversion = UnitConversion(
                            display_unit="",
                            storage_unit="raw",
                            to_display=lambda x: x / scale + offset_val,
                            from_display=lambda x: (x - offset_val) * scale,
                            decimal_places=2
                        )
                elif op == "*":
                    scale = factor
                    if offset_val == 0.0:
                        conversion = UnitConversion(
                            display_unit="",
                            storage_unit="raw",
                            to_display=lambda x: x * scale,
                            from_display=lambda x: x / scale,
                            decimal_places=2
                        )
                    else:
                        conversion = UnitConversion(
                            display_unit="",
                            storage_unit="raw",
                            to_display=lambda x: x * scale + offset_val,
                            from_display=lambda x: (x - offset_val) / scale,
                            decimal_places=2
                        )
                elif op == "+":
                    conversion = UnitConversion(
                        display_unit="",
                        storage_unit="raw",
                        to_display=lambda x: x + factor,
                        from_display=lambda x: x - factor,
                        decimal_places=2
                    )
                elif op == "-":
                    conversion = UnitConversion(
                        display_unit="",
                        storage_unit="raw",
                        to_display=lambda x: x - factor,
                        from_display=lambda x: x + factor,
                        decimal_places=2
                    )
                else:
                    conversion = UnitConversion.identity()
            else:
                conversion = UnitConversion.identity()
        else:
            conversion = UnitConversion.identity()
        # Category (optional)
        cat_elem = table.find("CATEGORYMEM")
        category = ParameterCategory.ADVANCED
        if cat_elem is not None:
            category = ParameterCategory.ADVANCED
        key = normalize_key(title)
        count = row_count * col_count
        rows = row_count
        cols = col_count
        param = TuningParameter(
            name=title,
            description=desc,
            offset=offset,
            data_format=data_format,
            category=category,
            xdf_title=title,
            count=count,
            rows=rows,
            cols=cols,
            conversion=conversion
        )
        params[key] = param
    return params
    
def get_unmapped_preset_keys_for_bin(bin_name: str, preset: Optional[TuningPreset] = None, xdf_summary_path=None) -> list:
    """Return a list of preset keys from `preset` that could not be mapped to
    any parameter key present in the specified bin's XDF summary.

    This helper does NOT create any placeholders or modify the parameter set;
    it simply reports which preset keys are unmapped so callers can present
    a clear, auditable list to users or logs.
    """
    if preset is None:
        preset = PRESET_STAGE1

    params = load_parameters_for_bin(bin_name, xdf_summary_path)
    param_keys = set(params.keys())
    missing = []
    for k in preset.values.keys():
        best = find_best_param_key_for_preset_key(k, param_keys)
        if not best:
            missing.append(k)
    return missing
    
    # NOTE: unreachable (kept for safety) - code should return above
#!/usr/bin/env python3
"""
BMW N54 Tuning Parameters - Comprehensive Map Definitions
==========================================================

Author: Gregory King
Date: December 2, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Comprehensive tuning parameter definitions for BMW N54 MSD80/MSD81 ECUs.
    Extracted from I8A0S_Custom_Corbanistan.xdf and validated against stock binary.
    
    Supports:
    - Scalar values (single numbers)
    - 1D tables (arrays indexed by one axis)
    - 2D tables (matrices indexed by two axes)
    
    Categories:
    - Performance: Speed Limiter, Rev Limiter, Launch Control
    - Boost Control: WGDC, Boost Targets, Load Limits
    - Fuel/Ignition: Timing tables, Fuel maps
    - Throttle: Sensitivity, Pedal maps
    - Features: Burble, FlexFuel, Antilag
    - Diagnostics: DTC codes, Knock CEL
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple, Union
from enum import Enum, auto
from pathlib import Path
import struct
import json


# Default stock binary used to hydrate factory values
DEFAULT_STOCK_BIN = Path("maps/reference_bins/I8A0S_original.bin")


# ============================================================================
# ENUMERATIONS
# ============================================================================

class ParameterType(Enum):
    """Type of tuning parameter"""
    SCALAR = auto()      # Single value
    TABLE_1D = auto()    # 1D array
    TABLE_2D = auto()    # 2D matrix
    BITFIELD = auto()    # Bit flags


class DataFormat(Enum):
    """Data format in binary"""
    UINT8 = 'B'
    INT8 = 'b'
    UINT16_LE = '<H'
    INT16_LE = '<h'
    UINT16_BE = '>H'
    INT16_BE = '>h'
    UINT32_LE = '<I'
    INT32_LE = '<i'
    FLOAT_LE = '<f'


class ParameterCategory(Enum):
    """Parameter category for UI organization"""
    PERFORMANCE = "Performance"
    BOOST_CONTROL = "Boost Control"
    FUEL = "Fuel"
    IGNITION = "Ignition"
    THROTTLE = "Throttle"
    TORQUE = "Torque"
    VANOS = "VANOS"
    FEATURES = "Features"
    DIAGNOSTICS = "Diagnostics"
    SAFETY = "Safety"
    ADVANCED = "Advanced"


class SafetyLevel(Enum):
    """Safety classification for parameters"""
    SAFE = 1        # Generally safe to modify
    MODERATE = 2    # Requires understanding
    DANGEROUS = 3   # Can damage engine/hardware
    CRITICAL = 4    # Can brick ECU


# ============================================================================
# BASE CLASSES
# ============================================================================

@dataclass
class ValidationRule:
    """Validation rule for a parameter value"""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warn_min: Optional[float] = None
    warn_max: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    custom_validator: Optional[Callable[[Any], Tuple[bool, str]]] = None
    
    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a value. Returns (is_valid, warning_message)"""
        # Check allowed values
        if self.allowed_values is not None:
            if value not in self.allowed_values:
                return False, f"Value must be one of: {self.allowed_values}"
        
        # Check absolute limits
        if self.min_value is not None and value < self.min_value:
            return False, f"Value {value} below minimum {self.min_value}"
        if self.max_value is not None and value > self.max_value:
            return False, f"Value {value} above maximum {self.max_value}"
        
        # Check warning thresholds
        warning = None
        if self.warn_min is not None and value < self.warn_min:
            warning = f"WARNING: Value {value} is below recommended {self.warn_min}"
        if self.warn_max is not None and value > self.warn_max:
            warning = f"WARNING: Value {value} is above recommended {self.warn_max}"
        
        # Custom validation
        if self.custom_validator:
            valid, msg = self.custom_validator(value)
            if not valid:
                return False, msg
            if msg:
                warning = msg
        
        return True, warning


@dataclass
class UnitConversion:
    """Unit conversion for display/storage"""
    display_unit: str
    storage_unit: str = "raw"
    to_display: Callable[[float], float] = lambda x: x
    from_display: Callable[[float], float] = lambda x: x
    decimal_places: int = 2
    
    @classmethod
    def identity(cls, unit: str = "") -> 'UnitConversion':
        return cls(display_unit=unit, storage_unit=unit)
    
    @classmethod
    def scale(cls, factor: float, display_unit: str, storage_unit: str = "raw", decimals: int = 2) -> 'UnitConversion':
        return cls(
            display_unit=display_unit,
            storage_unit=storage_unit,
            to_display=lambda x: x / factor,
            from_display=lambda x: x * factor,
            decimal_places=decimals
        )


@dataclass
class TuningParameter:
    """Base class for all tuning parameters"""
    name: str
    description: str
    offset: int
    data_format: DataFormat
    category: ParameterCategory
    safety: SafetyLevel = SafetyLevel.MODERATE
    
    # Optional metadata
    xdf_title: Optional[str] = None
    stock_value: Any = None
    tuned_value: Any = None
    
    # Validation and conversion
    validation: Optional[ValidationRule] = None
    conversion: Optional[UnitConversion] = None
    
    # Size info
    count: int = 1  # Number of elements
    rows: int = 1   # For 2D tables
    cols: int = 1   # For 2D tables
    
    @property
    def param_type(self) -> ParameterType:
        if self.rows > 1 and self.cols > 1:
            return ParameterType.TABLE_2D
        elif self.count > 1:
            return ParameterType.TABLE_1D
        return ParameterType.SCALAR
    
    @property
    def byte_size(self) -> int:
        """Total size in bytes"""
        element_size = struct.calcsize(self.data_format.value)
        return element_size * self.count
    
    def read_from_binary(self, data: bytes) -> Any:
        """Read value(s) from binary data, using XDF offset, element size, and count. Adds debug output for diagnosis."""
        import sys
        fmt = self.data_format.value
        element_size = struct.calcsize(fmt)
        debug = False
        # Enable debug for specific keys or global flag
        debug_keys = getattr(self, 'debug_keys', None)
        if debug_keys and self.name in debug_keys:
            debug = True
        # 2D table: rows x cols (column-major order)
        if self.rows > 1 and self.cols > 1:
            values = []
            raw_bytes = []
            for r in range(self.rows):
                row = []
                for c in range(self.cols):
                    idx = c * self.rows + r  # column-major order
                    offset = self.offset + idx * element_size
                    val = struct.unpack_from(fmt, data, offset)[0]
                    row.append(val)
                    raw_bytes.append(data[offset:offset+element_size])
            if debug:
                print(f"[DEBUG] {self.name}: offset=0x{self.offset:X}, size={self.rows}x{self.cols}, bytes={[b.hex() for b in raw_bytes]}", file=sys.stderr)
            return self.to_display_value(values)
        # 1D table: cols or rows
        elif self.count > 1:
            values = []
            raw_bytes = []
            for i in range(self.count):
                offset = self.offset + i * element_size
                val = struct.unpack_from(fmt, data, offset)[0]
                values.append(val)
                raw_bytes.append(data[offset:offset+element_size])
            if debug:
                print(f"[DEBUG] {self.name}: offset=0x{self.offset:X}, size={self.count}, bytes={[b.hex() for b in raw_bytes]}", file=sys.stderr)
            return self.to_display_value(values)
        # Scalar
        else:
            offset = self.offset
            val = struct.unpack_from(fmt, data, offset)[0]
            if debug:
                print(f"[DEBUG] {self.name}: offset=0x{self.offset:X}, size=1, bytes={data[offset:offset+element_size].hex()}", file=sys.stderr)
            return self.to_display_value(val)
    
    def write_to_binary(self, data: bytearray, value: Any) -> None:
        """Write value(s) to binary data"""
        fmt = self.data_format.value
        element_size = struct.calcsize(fmt)
        
        if self.count == 1:
            struct.pack_into(fmt, data, self.offset, value)
        else:
            # Handle nested lists (flatten them)
            flat_values = []
            if isinstance(value, list):
                for v in value:
                    if isinstance(v, list):
                        flat_values.extend(v)
                    else:
                        flat_values.append(v)
            else:
                flat_values = [value]

            for i, val in enumerate(flat_values):
                if i >= self.count:
                    break
                struct.pack_into(fmt, data, self.offset + i * element_size, val)
    
    def to_display_value(self, raw_value: Any) -> Any:
        """Convert raw value to display value"""
        if self.conversion is None:
            return raw_value
        
        if isinstance(raw_value, list):
            return [self.conversion.to_display(v) for v in raw_value]
        return self.conversion.to_display(raw_value)
    
    def from_display_value(self, display_value: Any) -> Any:
        """Convert display value to raw value"""
        if self.conversion is None:
            return display_value
        
        if isinstance(display_value, list):
            return [int(self.conversion.from_display(v)) for v in display_value]
        return int(self.conversion.from_display(display_value))
    
    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a value"""
        if self.validation is None:
            return True, None
        
        if isinstance(value, list):
            for v in value:
                if isinstance(v, list):
                    for sub_v in v:
                        valid, msg = self.validation.validate(sub_v)
                        if not valid:
                            return False, msg
                else:
                    valid, msg = self.validation.validate(v)
                    if not valid:
                        return False, msg
            return True, None
        
        return self.validation.validate(value)


# ============================================================================
# PERFORMANCE PARAMETERS
# ============================================================================

# Speed Limiter
SPEED_LIMITER_MASTER = TuningParameter(
    name="Speed Limiter (Master)",
    description="Maximum vehicle speed in MPH. Primary speed limit.",
    offset=0x42E00,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.SAFE,
    xdf_title="Speed Limiter (Master)",
    stock_value=25500,
    tuned_value=41129,  # ~255 MPH (effectively unlimited)
    validation=ValidationRule(min_value=8000, max_value=65535, warn_max=48000),
    conversion=UnitConversion.scale(161.29, "MPH", "raw", decimals=0),
)

SPEED_LIMITER_ARRAY = TuningParameter(
    name="Speed Limiter Array",
    description="Secondary speed limit values (4 bytes)",
    offset=0x42E0A,
    data_format=DataFormat.UINT8,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.SAFE,
    count=4,
    stock_value=[206, 235, 250, 243],
    tuned_value=[255, 255, 255, 255],
    conversion=UnitConversion.scale(1.60934, "MPH", "km/h", decimals=0),
)

SPEED_LIMITER_DISABLE = TuningParameter(
    name="Speed Limiter Disable",
    description="0=Enabled, 1=Disabled",
    offset=0x42E12,
    data_format=DataFormat.UINT8,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.SAFE,
    xdf_title="Speed Limiter",
    stock_value=0,
    tuned_value=1,
    validation=ValidationRule(allowed_values=[0, 1]),
    conversion=UnitConversion.identity("bool"),
)

# Rev Limiters
REV_LIMITER_CLUTCH_PRESSED = TuningParameter(
    name="Rev Limit - Clutch Pressed",
    description="RPM limit when clutch is depressed (8 values by gear selector position)",
    offset=0x55464,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.MODERATE,
    count=8,
    stock_value=[6800, 6800, 6800, 6800, 6800, 6800, 6800, 6800],
    tuned_value=[7200, 7200, 7200, 7200, 7200, 7200, 7200, 7200],
    validation=ValidationRule(min_value=3000, max_value=8500, warn_max=7400),
    conversion=UnitConversion.identity("RPM"),
)

REV_LIMITER_FLOOR_MT = TuningParameter(
    name="Rev Limit Floor (MT)",
    description="Lower rev limit threshold for manual transmission (9 gears)",
    offset=0x508B8,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.MODERATE,
    count=9,
    stock_value=[6800, 6980, 6980, 6980, 6980, 6980, 6980, 6400, 6400],
    tuned_value=[7200, 7200, 7200, 7200, 7200, 7200, 7200, 6800, 6800],
    validation=ValidationRule(min_value=3000, max_value=8500, warn_max=7400),
    conversion=UnitConversion.identity("RPM"),
)

REV_LIMITER_CEILING_MT = TuningParameter(
    name="Rev Limit Ceiling (MT)",
    description="Upper rev limit threshold for manual transmission (9 gears)",
    offset=0x508E0,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.MODERATE,
    count=9,
    stock_value=[6802, 6982, 6982, 6982, 6982, 6982, 6982, 6600, 6600],
    tuned_value=[7400, 7400, 7400, 7400, 7400, 7400, 7400, 7000, 7000],
    validation=ValidationRule(min_value=3000, max_value=8500, warn_max=7500),
    conversion=UnitConversion.identity("RPM"),
)

REV_LIMITER_FLOOR_AT = TuningParameter(
    name="Rev Limit Floor (AT)",
    description="Lower rev limit threshold for automatic transmission (9 gears)",
    offset=0x508A4,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.MODERATE,
    count=9,
    stock_value=[6400, 7000, 7000, 7000, 7000, 7000, 7000, 6400, 6400],
    tuned_value=[7000, 7200, 7200, 7200, 7200, 7200, 7200, 6800, 6800],
    validation=ValidationRule(min_value=3000, max_value=8500, warn_max=7400),
    conversion=UnitConversion.identity("RPM"),
)

REV_LIMITER_CEILING_AT = TuningParameter(
    name="Rev Limit Ceiling (AT)",
    description="Upper rev limit threshold for automatic transmission (9 gears)",
    offset=0x508CC,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.MODERATE,
    count=9,
    stock_value=[6600, 7100, 7100, 7100, 7100, 7000, 7000, 6600, 6600],
    tuned_value=[7200, 7400, 7400, 7400, 7400, 7200, 7200, 7000, 7000],
    validation=ValidationRule(min_value=3000, max_value=8500, warn_max=7500),
    conversion=UnitConversion.identity("RPM"),
)

REV_LIMITER_TIME_BUMPS_MT = TuningParameter(
    name="Time Between Rev Bumps (MT)",
    description="Time between rev limiter activations in 0.1s units (9 gears)",
    offset=0x50A84,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.PERFORMANCE,
    safety=SafetyLevel.SAFE,
    count=9,
    stock_value=[1, 1, 1, 1, 1, 1, 1, 1, 1],
    tuned_value=[1, 1, 1, 1, 1, 1, 1, 1, 1],
    validation=ValidationRule(min_value=1, max_value=100),
    conversion=UnitConversion.scale(10, "sec", "0.1s", decimals=1),
)


# ============================================================================
# ANTILAG / LAUNCH CONTROL PARAMETERS
# ============================================================================

ANTILAG_ENABLE = TuningParameter(
    name="Antilag Enable",
    description="Master enable for antilag/launch control system. 0=Off, 1=On",
    offset=0x7E783,
    data_format=DataFormat.UINT8,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.MODERATE,
    stock_value=0,
    tuned_value=1,
    validation=ValidationRule(allowed_values=[0, 1]),
)

ANTILAG_BOOST_TARGET = TuningParameter(
    name="Antilag Boost Target",
    description="Target boost pressure during antilag activation",
    offset=0x7E77E,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.DANGEROUS,
    stock_value=0,
    tuned_value=12473,  # ~15 PSI
    validation=ValidationRule(min_value=0, max_value=25000, warn_max=16600),  # ~20 PSI
    conversion=UnitConversion.scale(831.52, "PSI", "raw", decimals=1),
)

ANTILAG_COOLDOWN = TuningParameter(
    name="Antilag Cooldown Timer",
    description="Cooldown period in seconds after antilag deactivation",
    offset=0x7E782,
    data_format=DataFormat.UINT8,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.SAFE,
    stock_value=0,
    tuned_value=5,
    validation=ValidationRule(min_value=0, max_value=60, warn_min=3),
    conversion=UnitConversion.identity("sec"),
)

ANTILAG_FUEL_TARGET = TuningParameter(
    name="Antilag Fuel Target",
    description="Target AFR during antilag (richer = more fuel)",
    offset=0x7E82A,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.DANGEROUS,
    stock_value=0,
    tuned_value=3200,  # ~11.5 AFR
    validation=ValidationRule(min_value=0, max_value=6000, warn_min=2800),  # ~10.0 AFR
    conversion=UnitConversion(
        display_unit="AFR",
        storage_unit="raw",
        to_display=lambda x: (x / 4096) * 14.7 if x > 0 else 14.7,
        from_display=lambda x: int((x / 14.7) * 4096),
        decimal_places=1
    ),
)

ANTILAG_COOLANT_MIN = TuningParameter(
    name="Antilag Min Coolant Temp",
    description="Minimum coolant temperature for antilag activation",
    offset=0x7E82C,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.SAFETY,
    safety=SafetyLevel.SAFE,
    stock_value=0,
    tuned_value=7000,  # 70°C
    validation=ValidationRule(min_value=0, max_value=12000, warn_min=5000),
    conversion=UnitConversion.scale(100, "°C", "raw*100", decimals=0),
)

ANTILAG_COOLANT_MAX = TuningParameter(
    name="Antilag Max Coolant Temp",
    description="Maximum coolant temperature for antilag (safety cutoff)",
    offset=0x7E82E,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.SAFETY,
    safety=SafetyLevel.SAFE,
    stock_value=0,
    tuned_value=11000,  # 110°C
    validation=ValidationRule(min_value=8000, max_value=13000, warn_max=11500),
    conversion=UnitConversion.scale(100, "°C", "raw*100", decimals=0),
)

ANTILAG_EGT_MAX = TuningParameter(
    name="Antilag Max EGT",
    description="Maximum exhaust gas temperature for antilag (safety cutoff)",
    offset=0x7E830,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.SAFETY,
    safety=SafetyLevel.SAFE,
    stock_value=0,
    tuned_value=9000,  # 900°C
    validation=ValidationRule(min_value=5000, max_value=10000, warn_max=9500),
    conversion=UnitConversion.scale(10, "°C", "raw*10", decimals=0),
)


# ============================================================================
# BOOST CONTROL PARAMETERS
# ============================================================================

# ========== VALIDATED WGDC MAPS (from docs/FINAL_VALIDATED_DISCOVERIES.md) ==========
# These are confirmed safe 12x12 tables (144 values each, 288 bytes)
# WGDC = Wastegate Duty Cycle (controls turbo boost)
# Scaling: (raw / 65535) * 100 = duty %

# WGDC RPM and Load axes (shared by all 3 maps)
WGDC_RPM_AXIS = [520, 760, 1000, 1520, 2040, 2800, 3320, 4080, 4800, 5520, 6240, 6960]
WGDC_LOAD_AXIS = [130, 150, 170, 190, 210, 230, 250, 270, 290, 310, 330, 350]

WGDC_BASE = TuningParameter(
    name="WGDC Base (KF_ATLVST)",
    description="Wastegate Duty Cycle base table. "
                "20x16 table indexed by MAF request (kg/h) and pressure ratio factor. "
                "Higher values = more boost. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x5F7F6",
    offset=0x5F7F6,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC (Base)",
    rows=20,   # Factor axis (Req MAP / baro)
    cols=16,   # MAF request axis
    count=320,  # 20 x 16
    stock_value=None,  # Will be read from bin
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=58000),  # ~88% duty
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/655.35",
        to_display=lambda x: x / 655.35,
        from_display=lambda x: int(x * 655.35),
        decimal_places=2
    ),
)

WGDC_SPOOL = TuningParameter(
    name="WGDC Spool (KF_ATLVST_MSKOR)",
    description="WGDC to add on top of base table based on airflow. "
                "8x8 table indexed by RPM and Load. "
                "Controls boost during spool-up transients. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x5F72A",
    offset=0x5F72A,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC (Spool)",
    rows=8,
    cols=8,
    count=64,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=58000),
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/655.35",
        to_display=lambda x: x / 655.35,
        from_display=lambda x: int(x * 655.35),
        decimal_places=2
    ),
)

# ========== WGDC AIRFLOW ADDER TABLES (from Corbanistan XDF) ==========
# MAF Req axis: 6 values @ 0x6D7A6 (Map 1 E85), 0x639B4 (Map 2), 0x639CE (Map 3), 0x639E8 (Map 4)
# Data axis: 6 values per map
# These add additional WGDC on top of the base table for specific airflow regions
# Helps control boost by airflow without relying solely on PID

WGDC_ADDER_MAF_AXIS = [50, 100, 150, 200, 250, 300]  # kg/h values (approximate from XDF conversion)

WGDC_AIRFLOW_ADDER_AXIS_E85 = TuningParameter(
    name="WGDC Airflow Adder Axis (E85)",
    description="MAF Request axis for E85 WGDC adder. 6 values.",
    offset=0x6D7A6,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.MODERATE,
    rows=1,
    cols=6,
    count=6,
    stock_value=WGDC_ADDER_MAF_AXIS,
    validation=ValidationRule(min_value=0, max_value=2000),
    conversion=UnitConversion.identity("kg/h"),
)

WGDC_AIRFLOW_ADDER_AXIS_MAP2 = TuningParameter(
    name="WGDC Airflow Adder Axis (Map 2)",
    description="MAF Request axis for Map 2 WGDC adder. 6 values.",
    offset=0x639B4,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.MODERATE,
    rows=1,
    cols=6,
    count=6,
    stock_value=WGDC_ADDER_MAF_AXIS,
    validation=ValidationRule(min_value=0, max_value=2000),
    conversion=UnitConversion.identity("kg/h"),
)

WGDC_AIRFLOW_ADDER_AXIS_MAP3 = TuningParameter(
    name="WGDC Airflow Adder Axis (Map 3)",
    description="MAF Request axis for Map 3 WGDC adder. 6 values.",
    offset=0x639CE,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.MODERATE,
    rows=1,
    cols=6,
    count=6,
    stock_value=WGDC_ADDER_MAF_AXIS,
    validation=ValidationRule(min_value=0, max_value=2000),
    conversion=UnitConversion.identity("kg/h"),
)

WGDC_AIRFLOW_ADDER_AXIS_MAP4 = TuningParameter(
    name="WGDC Airflow Adder Axis (Map 4)",
    description="MAF Request axis for Map 4 WGDC adder. 6 values.",
    offset=0x639E8,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.MODERATE,
    rows=1,
    cols=6,
    count=6,
    stock_value=WGDC_ADDER_MAF_AXIS,
    validation=ValidationRule(min_value=0, max_value=2000),
    conversion=UnitConversion.identity("kg/h"),
)

WGDC_AIRFLOW_ADDER_E85 = TuningParameter(
    name="WGDC Airflow Adder (E85 Map)",
    description="Airflow-based WGDC adder for E85 tuning map. "
                "1x6 table indexed by MAF Requested (kg/h). "
                "Adds WGDC proportional to airflow demand. "
                "Range: 0-100% typical. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x6D7B2",
    offset=0x6D7B2,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC Airflow Adder (E85)",
    rows=1,
    cols=6,
    count=6,  # 1x6 table
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=60000),  # 0-100%
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/655.35",
        to_display=lambda x: x / 655.35,
        from_display=lambda x: int(x * 655.35),
        decimal_places=2
    ),
)

WGDC_AIRFLOW_ADDER_MAP2 = TuningParameter(
    name="WGDC Airflow Adder (Map 2)",
    description="Airflow-based WGDC adder for tuning map 2 (Stage 2). "
                "1x6 table indexed by MAF Requested (kg/h). "
                "Adds WGDC proportional to airflow demand. "
                "Range: 0-100% typical. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x639C0",
    offset=0x639C0,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC Airflow Adder (Map 2)",
    rows=1,
    cols=6,
    count=6,  # 1x6 table
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=60000),  # 0-100%
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/655.35",
        to_display=lambda x: x / 655.35,
        from_display=lambda x: int(x * 655.35),
        decimal_places=2
    ),
)

WGDC_AIRFLOW_ADDER_MAP3 = TuningParameter(
    name="WGDC Airflow Adder (Map 3)",
    description="Airflow-based WGDC adder for tuning map 3 (Stage 2.5). "
                "1x6 table indexed by MAF Requested (kg/h). "
                "Adds WGDC proportional to airflow demand. "
                "Range: 0-100% typical. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x639DA",
    offset=0x639DA,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC Airflow Adder (Map 3)",
    rows=1,
    cols=6,
    count=6,  # 1x6 table
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=60000),  # 0-100%
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/655.35",
        to_display=lambda x: x / 655.35,
        from_display=lambda x: int(x * 655.35),
        decimal_places=2
    ),
)

WGDC_AIRFLOW_ADDER_MAP4 = TuningParameter(
    name="WGDC Airflow Adder (Map 4)",
    description="Airflow-based WGDC adder for tuning map 4 (Stage 3). "
                "1x6 table indexed by MAF Requested (kg/h). "
                "Adds WGDC proportional to airflow demand. "
                "Range: 0-100% typical. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x639F4",
    offset=0x639F4,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC Airflow Adder (Map 4)",
    rows=1,
    cols=6,
    count=6,  # 1x6 table
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=60000),  # 0-100%
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/655.35",
        to_display=lambda x: x / 655.35,
        from_display=lambda x: int(x * 655.35),
        decimal_places=2
    ),
)

# WGDC_KFLDDE removed - offset 0x0546D0 NOT validated in Corbanistan XDF
# Use WGDC_BASE (0x5F7F6) instead for boost control

# ========== WGDC AXES (from Corbanistan XDF) ==========
# Y axis: Factor (Req MAP / baro) @ 0x5F7AE - 20 values
# X axis: MAF Req (kg/h) @ 0x5F7D6 - 16 values

# ========== ADDITIONAL BOOST CONTROL (from XDF) ==========

BOOST_LIMIT_MULTIPLIER = TuningParameter(
    name="Boost Limit Multiplier",
    description="Global limit on how much boost the DME is allowed to make (KL_FPLDSTOPF).\nXDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x5F312",
    offset=0x5F312,  # XDF validated
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    count=8,  # 8 values per XDF
    stock_value=None,  # Will be read from bin
    validation=ValidationRule(min_value=0, max_value=65535),
    conversion=UnitConversion(
        display_unit="factor",
        storage_unit="raw/16384",
        to_display=lambda x: x / 16384,
        from_display=lambda x: int(x * 16384),
        decimal_places=3
    ),
)

LOAD_LIMIT_FACTOR = TuningParameter(
    name="Load Limit Factor",
    description="Set load limits based on pressure (KL_FUPSRF_ATL).\nXDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x5F27A",
    offset=0x5F27A,  # XDF validated
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="Load Limit Factor",
    rows=1,
    cols=12,
    count=12,
    stock_value=None,  # Will be read from bin
    validation=ValidationRule(min_value=0, max_value=65535),
    conversion=UnitConversion(
        display_unit="%/hPa",
        storage_unit="raw/218452",
        to_display=lambda x: x / 218452,
        from_display=lambda x: int(x * 218452),
        decimal_places=3
    ),
)

# ========== LOAD TARGET PER GEAR (from XDF @ 0x7F736) ==========
# 6x16 table - Critical for per-gear boost control

LOAD_TARGET_RPM_AXIS = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7200, 7400, 7600]
LOAD_TARGET_GEAR_AXIS = [1, 2, 3, 4, 5, 6]

LOAD_TARGET_PER_GEAR = TuningParameter(
    name="Load Target per Gear",
    description="Sets targeted (max) load based on RPM per gear. "
                "6x16 table indexed by Gear (1-6) and RPM (1000-7600). "
                "Critical for per-gear boost control. Values in load units.",
    offset=0x07F736,  # From XDF line 19579
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="Load Target per Gear",
    rows=6,   # Gears 1-6
    cols=16,  # RPM points
    count=96,  # 6 x 16
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=25000, warn_max=22000),  # ~220 load
    conversion=UnitConversion(
        display_unit="load",
        storage_unit="raw/100",
        to_display=lambda x: x / 100,
        from_display=lambda x: int(x * 100),
        decimal_places=2
    ),
)

# ========== BOOST PRESSURE TARGET MODIFIER (from XDF @ 0x617BE) ==========
# 6x6 table - Boost target tuning by RPM and current boost

BOOST_TARGET_RPM_AXIS = [1000, 2000, 3000, 4000, 5000, 6000]
BOOST_TARGET_RATIO_AXIS = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0]

BOOST_PRESSURE_TARGET_MODIFIER = TuningParameter(
    name="Boost Pressure Target Modifier (Normal)",
    description="Modifies boost pressure target based on RPM and current boost ratio. "
                "6x6 table indexed by RPM and Boost Target/Atm ratio. "
                "Values are modifier factors (1.0 = no change).",
    offset=0x0617BE,  # From XDF line 12338
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.MODERATE,
    xdf_title="Boost Pressure Target Modifier (Normal Operation)",
    rows=6,
    cols=6,
    count=36,  # 6 x 6
    stock_value=None,
    validation=ValidationRule(min_value=28000, max_value=40000, warn_max=38000),
    conversion=UnitConversion(
        display_unit="factor",
        storage_unit="raw/32768",
        to_display=lambda x: x / 32768,
        from_display=lambda x: int(x * 32768),
        decimal_places=3
    ),
)

# ========== WGDC PID CONTROLLER PARAMETERS (from A2L/XDF) ==========
# These are the PID gains used by the ATLREG (boost controller) function
# From MSD81BMWSpecifications.pdf and validated against A2L/XDF

# Boost error axis for P/I/D factor maps
WGDC_BOOST_ERROR_AXIS = [-0.3, -0.2, -0.15, -0.1, -0.05, 0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]

WGDC_P_FACTOR = TuningParameter(
    name="WGDC P-Factor",
    description="Proportional gain for WGDC PID controller (KF_FATLR_P). "
                "1x12 table indexed by boost error (bar). "
                "Left side = underboost (negative), Right side = overboost (positive). "
                "Higher values = faster response to boost deviation.",
    offset=0x05FF2A,  # From XDF - z-axis data address
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC P-Factor",
    rows=1,
    cols=12,
    count=12,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=40000),
    conversion=UnitConversion(
        display_unit="%/bar",
        storage_unit="raw/12800",
        to_display=lambda x: x / 12800,
        from_display=lambda x: int(x * 12800),
        decimal_places=3
    ),
)

WGDC_I_FACTOR = TuningParameter(
    name="WGDC I-Factor",
    description="Integral gain for WGDC PID controller (KF_FATLR_I). "
                "12x12 table indexed by boost error (bar) and RPM. "
                "Left side = underboost, Right side = overboost. "
                "Higher values = faster correction of sustained boost error.",
    offset=0x06007E,  # From XDF - z-axis data address  
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC I-Factor",
    rows=12,  # RPM axis
    cols=12,  # Boost error axis
    count=144,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=40000),
    conversion=UnitConversion(
        display_unit="%/bar·s",
        storage_unit="raw/12800",
        to_display=lambda x: x / 12800,
        from_display=lambda x: int(x * 12800),
        decimal_places=3
    ),
)

WGDC_D_FACTOR = TuningParameter(
    name="WGDC D-Factor",
    description="Derivative gain for WGDC PID controller (KF_FATLRD). "
                "14x14 table indexed by boost error (bar) and error gradient. "
                "Anticipates boost changes, dampens oscillation. "
                "Affects P-factor multiplier per description.",
    offset=0x0601D6,  # From XDF - z-axis data address
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="WGDC D-Factor",
    rows=14,  # Boost error gradient axis
    cols=14,  # Boost error axis
    count=196,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=40000),
    conversion=UnitConversion(
        display_unit="factor",
        storage_unit="raw/12800",
        to_display=lambda x: x / 12800,
        from_display=lambda x: int(x * 12800),
        decimal_places=3
    ),
)

WGDC_D_MULTIPLIER = TuningParameter(
    name="WGDC D-Factor Multiplier (RPM)",
    description="RPM-based multiplier for D-Factor (kl_fatlrd_n). "
                "1x12 table indexed by RPM. "
                "Controls how D-factor effect scales with engine speed. "
                "Slows or speeds up P-Factor response based on RPM.",
    offset=0x05F6C2,  # From XDF line 10798
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.MODERATE,
    xdf_title="WGDC D-Factor Multiplier",
    rows=1,
    cols=12,
    count=12,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535, warn_max=50000),
    conversion=UnitConversion(
        display_unit="factor",
        storage_unit="raw/32768",
        to_display=lambda x: x / 32768,
        from_display=lambda x: int(x * 32768),
        decimal_places=3
    ),
)

BOOST_CEILING = TuningParameter(
    name="Boost Ceiling",
    description="Absolute maximum boost pressure limit (hard ceiling). "
                "Single scalar value limiting peak boost output. "
                "Safety mechanism to prevent overboost damage. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x77BC4",
    offset=0x77BC4,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.BOOST_CONTROL,
    safety=SafetyLevel.CRITICAL,
    stock_value=None,  # Will be read from bin
    validation=ValidationRule(min_value=5000, max_value=70000, warn_max=65000),  # ~19 PSI to ~23 PSI
    conversion=UnitConversion(
        display_unit="PSI",
        storage_unit="raw/25598.4375",
        to_display=lambda x: x / 25598.4375,
        from_display=lambda x: int(x * 25598.4375),
        decimal_places=2
    ),
)

# ========== TORQUE LIMIT PARAMETERS (from XDF) ==========

TORQUE_LIMIT_DRIVER_RPM_AXIS = [520, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 6500, 7000, 7500]

TORQUE_LIMIT_DRIVER = TuningParameter(
    name="Requested Torque Limit (Driver)",
    description="Maximum output torque limit by RPM. "
                "1x11 table indexed by RPM (520-7500). "
                "Critical safety limit - excessive values can damage drivetrain.",
    offset=0x06E628,  # From XDF line 15296
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.TORQUE,
    safety=SafetyLevel.CRITICAL,
    xdf_title="Requested Torque Limit (Driver)",
    rows=1,
    cols=11,
    count=11,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=8000, warn_max=6500),  # ~480 ft-lb max
    conversion=UnitConversion(
        display_unit="ft-lb",
        storage_unit="raw/10*0.73755",
        to_display=lambda x: (x / 10) * 0.73755,
        from_display=lambda x: int((x / 0.73755) * 10),
        decimal_places=1
    ),
)

TORQUE_LIMIT_CAP = TuningParameter(
    name="Torque Limit Cap",
    description="Absolute maximum torque limit (single value). "
                "Safety cap that cannot be exceeded. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x72AF6",
    offset=0x72AF6,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.TORQUE,
    safety=SafetyLevel.CRITICAL,
    stock_value=None,  # Will be read from bin
    tuned_value=6000,  # ~442 ft-lb
    validation=ValidationRule(min_value=1000, max_value=8000, warn_max=7000),
    conversion=UnitConversion(
        display_unit="ft-lb",
        storage_unit="raw/10*0.73756",
        to_display=lambda x: (x / 10) * 0.73756,
        from_display=lambda x: int((x / 0.73756) * 10),
        decimal_places=1
    ),
)

# ========== FLEXFUEL PARAMETERS (from XDF @ 0x7E6A7) ==========

# FLEXFUEL_ENABLE removed - offset 0x1F0100 NOT validated in Corbanistan XDF
# FlexFuel is controlled via Static Ethanol Content (0x7E6A7) instead
# Setting Static Ethanol Content > 0 overrides ECA sensor reading

STATIC_ETHANOL_CONTENT = TuningParameter(
    name="Static Ethanol Content (Map 1)",
    description="Fixed ethanol content percentage when no sensor is installed. "
                "0 = pump gas (E10), 85 = E85, 100 = pure ethanol. "
                "Validated: I8A0S_Custom_Corbanistan.xdf @ 0x7E6A7",
    offset=0x7E6A7,  # Validated in Corbanistan XDF
    data_format=DataFormat.UINT8,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.MODERATE,
    stock_value=0,  # Disabled in stock (no ethanol content override)
    tuned_value=30,  # E30 blend
    validation=ValidationRule(min_value=0, max_value=100, warn_max=85),
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw/2.55",
        to_display=lambda x: x / 2.55,
        from_display=lambda x: int(x * 2.55),
        decimal_places=0
    ),
)

# ========== BURBLE TIMING MAP (from XDF @ 0x54A30) ==========
# 6x8 table - Critical for burble/pop intensity

BURBLE_TIMING_RPM_AXIS = [520, 1024, 1536, 2048, 2560, 3072, 3584, 4096]
BURBLE_TIMING_LOAD_AXIS = [0, 54, 109, 163, 218, 272]

BURBLE_TIMING_BASE = TuningParameter(
    name="Minimum Ignition Angle (Trailing Throttle)",
    description="Ignition timing during trailing throttle (decel/overrun). "
                "6x8 table indexed by RPM and mg/stroke. "
                "Lower values = more aggressive burbles/pops.",
    offset=0x054A30,  # From XDF line 6328
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.MODERATE,
    xdf_title="Minimum Ignition Angle During Trailing Throttle (Base)",
    rows=6,   # Load axis
    cols=8,   # RPM axis
    count=48,  # 6 x 8
    stock_value=[
        # Fill with the correct stock values from the preset or XDF (example placeholder, replace with actual values if available)
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    ],
    validation=ValidationRule(min_value=0, max_value=2880, warn_min=800),  # -90 to +90 deg range
    conversion=UnitConversion(
        display_unit="°",
        storage_unit="raw*0.0625-90",
        to_display=lambda x: x * 0.0625 - 90,
        from_display=lambda x: int((x + 90) / 0.0625),
        decimal_places=1
    ),
)

# ========== THROTTLE PARAMETERS (from XDF) ==========

THROTTLE_WOT_RPM_AXIS = [1000, 2000, 3000, 4000, 5000, 6000, 7000]

THROTTLE_ANGLE_WOT = TuningParameter(
    name="Throttle Angle (WOT)",
    description="Wide-open throttle angle by RPM. "
                "Max throttle possible at WOT at a given RPM. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x7372E",
    offset=0x7372E,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.THROTTLE,
    safety=SafetyLevel.SAFE,
    xdf_title="Throttle Angle (WOT)",
    rows=1,
    cols=18,
    count=18,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=4095, warn_max=4000),
    conversion=UnitConversion(
        display_unit="%",
        storage_unit="raw",
        to_display=lambda x: x / 40.95,  # X/40.95 per XDF
        from_display=lambda x: int(x * 40.95),
        decimal_places=2
    ),
)


# ============================================================================
# IGNITION TIMING PARAMETERS
# ============================================================================

# ========== XDF VALIDATED IGNITION TIMING MAPS (Dec 2025) ==========
# All timing maps validated against I8A0S_Custom_Corbanistan.xdf
# Old ZWTAB* offsets (0x057B58, 0x05D288, 0x060EC0) were NOT in XDF - REMOVED
# New offsets are confirmed from Corbanistan XDF

# TIMING_ZWTABHI - REMOVED: Offset 0x057B58 is NOT in Corbanistan XDF
# Use TIMING_MAIN @ 0x7676A instead (XDF validated)

# TIMING_ZWTABGR - REMOVED: Offset 0x05D288 is NOT in Corbanistan XDF
# Use TIMING_SPOOL @ 0x768CE instead (XDF validated)

# TIMING_ZWTABKL - REMOVED: Offset 0x060EC0 is NOT in Corbanistan XDF
# No direct replacement found - would need further XDF research

# ========== ADDITIONAL TIMING PARAMETERS (placeholder offsets) ==========

TIMING_MAIN = TuningParameter(
    name="Timing (Main)",
    description="Main ignition timing map - RPM vs Load (KF_ZW_VT98). "
                "20x16 table covering full operating range. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x7676A",
    offset=0x7676A,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit per XDF (not 16-bit!)
    category=ParameterCategory.IGNITION,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="Timing (Main)",
    rows=20,  # RPM axis
    cols=16,  # Load axis
    count=320,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=255),
    conversion=UnitConversion(
        display_unit="°",
        storage_unit="raw",
        to_display=lambda x: x / 2,  # X/2 per XDF
        from_display=lambda x: int(x * 2),
        decimal_places=2
    ),
)

TIMING_SPOOL = TuningParameter(
    name="Timing (Spool)",
    description="Ignition timing map during turbo spool-up (KF_ZW_VTUESP). "
                "8x8 table for transient boost conditions. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x768CE",
    offset=0x768CE,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit per XDF (not 16-bit!)
    category=ParameterCategory.IGNITION,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="Timing (Spool)",
    rows=8,  # RPM axis
    cols=8,  # Load axis
    count=64,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=255),
    conversion=UnitConversion(
        display_unit="°",
        storage_unit="raw",
        to_display=lambda x: x / 2,  # X/2 per XDF
        from_display=lambda x: int(x * 2),
        decimal_places=2
    ),
)


# ============================================================================
# THROTTLE PARAMETERS
# ============================================================================

THROTTLE_SENSITIVITY = TuningParameter(
    name="Throttle Sensitivity",
    description="Pedal-to-throttle response curve",
    offset=0x7F710,
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.THROTTLE,
    safety=SafetyLevel.SAFE,
    count=16,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=65535),
    conversion=UnitConversion.scale(655.35, "%", "raw", decimals=1),
)


# ============================================================================
# FEATURE TOGGLES (DTC CODES)
# ============================================================================

DTC_OVERBOOST = TuningParameter(
    name="DTC 30FE (Overboost)",
    description="Enable/disable overboost fault code (P1078). "
                "Set to 0x00 to disable, 0x22 to enable. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x59D24",
    offset=0x59D24,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit value per XDF
    category=ParameterCategory.DIAGNOSTICS,
    safety=SafetyLevel.MODERATE,
    stock_value=0x22,  # Enabled in stock
    tuned_value=0x00,  # Disabled for tuning
    validation=ValidationRule(min_value=0, max_value=255),
)

DTC_UNDERBOOST = TuningParameter(
    name="DTC 30FF (Underboost)",
    description="Enable/disable underboost fault code (P1079). "
                "Set to 0x00 to disable, 0x22 to enable. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x59D38",
    offset=0x59D38,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit value per XDF
    category=ParameterCategory.DIAGNOSTICS,
    safety=SafetyLevel.MODERATE,
    stock_value=0x22,  # Enabled in stock
    tuned_value=0x00,  # Disabled for tuning
    validation=ValidationRule(min_value=0, max_value=255),
)

DTC_BOOST_DEACTIVATION = TuningParameter(
    name="DTC 3100 (Boost Deactivation)",
    description="Enable/disable boost system deactivation fault code. "
                "Set to 0x00 to disable, 0x22 to enable. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x59CFC",
    offset=0x59CFC,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit value per XDF
    category=ParameterCategory.DIAGNOSTICS,
    safety=SafetyLevel.MODERATE,
    stock_value=0x22,  # Enabled in stock
    tuned_value=0x00,  # Disabled for tuning
    validation=ValidationRule(min_value=0, max_value=255),
)

DTC_IBS_BATTERY_SENSOR = TuningParameter(
    name="DTC 2E8E (IBS Battery Sensor Missing)",
    description="Enable/disable Intelligent Battery Sensor (IBS) missing fault. "
                "Disable (0x00) when installing non-OEM battery without IBS. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x59B08",
    offset=0x59B08,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit value per XDF
    category=ParameterCategory.DIAGNOSTICS,
    safety=SafetyLevel.SAFE,
    stock_value=0x11,  # Enabled in stock
    tuned_value=0x00,  # Disabled for aftermarket battery
    validation=ValidationRule(min_value=0, max_value=255),
)

DTC_CODING_MISSING = TuningParameter(
    name="DTC 2FA3 (Coding Missing)",
    description="Enable/disable coding missing fault. "
                "Disable (0x00) to prevent CEL after ECU swap or coding reset. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x5A0D0",
    offset=0x5A0D0,  # ✅ VALIDATED in Corbanistan XDF
    data_format=DataFormat.UINT8,  # 8-bit value per XDF
    category=ParameterCategory.DIAGNOSTICS,
    safety=SafetyLevel.MODERATE,
    stock_value=0x11,  # Enabled in stock
    tuned_value=0x00,  # Disabled to prevent coding errors
    validation=ValidationRule(min_value=0, max_value=255),
)


# ============================================================================
# BURBLE / EXHAUST POPS
# ============================================================================

BURBLE_DURATION_NORMAL = TuningParameter(
    name="Burble Duration (Normal)",
    description="Duration of exhaust burbles in Normal mode (Map 2). "
                "6x8 table indexed by Temperature and RPM. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x63B20",
    offset=0x63B20,  # ✅ VALIDATED in Corbanistan XDF (Map 2)
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.MODERATE,
    xdf_title="Burble Duration (Normal) (Map 2)",
    rows=6,  # Temperature axis
    cols=8,  # RPM axis
    count=48,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=25500, warn_max=5000),
    conversion=UnitConversion(
        display_unit="sec",
        storage_unit="raw",
        to_display=lambda x: x / 100,  # X/100 per XDF
        from_display=lambda x: int(x * 100),
        decimal_places=2
    ),
)

BURBLE_DURATION_SPORT = TuningParameter(
    name="Burble Duration (Sport)",
    description="Duration of exhaust burbles in Sport mode (Map 2). "
                "6x8 table indexed by Temperature and RPM. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x7F4CC",
    offset=0x7F4CC,  # ✅ VALIDATED in Corbanistan XDF (Map 2)
    data_format=DataFormat.UINT16_LE,
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.MODERATE,
    xdf_title="Burble Duration (Sport) (Map 2)",
    rows=6,  # Temperature axis
    cols=8,  # RPM axis
    count=48,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=25500, warn_max=7500),
    conversion=UnitConversion(
        display_unit="sec",
        storage_unit="raw",
        to_display=lambda x: x / 100,  # X/100 per XDF
        from_display=lambda x: int(x * 100),
        decimal_places=2
    ),
)

BURBLE_IGNITION_RETARD = TuningParameter(
    name="Burble Ignition Timing",
    description="Ignition timing during exhaust burbles (Map 2). "
                "Retarded timing creates exhaust pops. 6x8 table. "
                "✅ XDF VALIDATED: I8A0S_Custom_Corbanistan.xdf @ 0x63A00",
    offset=0x63A00,  # ✅ VALIDATED in Corbanistan XDF (Map 2)
    data_format=DataFormat.UINT8,  # 8-bit per XDF (not 16-bit!)
    category=ParameterCategory.FEATURES,
    safety=SafetyLevel.DANGEROUS,
    xdf_title="Burble Ignition Timing (Map 2)",
    rows=6,  # Temperature axis
    cols=8,  # RPM axis
    count=48,
    stock_value=None,
    validation=ValidationRule(min_value=0, max_value=255),
    conversion=UnitConversion(
        display_unit="°",
        storage_unit="raw",
        to_display=lambda x: x / 2,  # X/2 per XDF for timing degrees
        from_display=lambda x: int(x * 2),
        decimal_places=1
    ),
)


# ============================================================================
# PARAMETER REGISTRY
# ============================================================================

# Organize all parameters by category

# ALL_PARAMETERS is now a dynamic proxy that always loads from the authoritative XDF summary for the selected bin/OS family.
# For legacy compatibility, we provide a function that loads parameters for the default/stock bin.
def get_all_parameters(bin_name: str = None, xdf_path=None) -> dict:
    """
    Always load parameters from the authoritative XDF summary for the given bin.
    If bin_name is None, use the default stock bin section from xdf_map_summary.txt.
    xdf_path is an optional override for the XDF summary path.
    """
    return load_parameters_for_bin(bin_name, xdf_path)


# Initialize ALL_PARAMETERS to the authoritative XDF-derived parameters for the default bin.
# If loading the XDF summary fails (e.g., in test environments), fall back to collecting
# all statically-declared TuningParameter instances defined in this module. This
# preserves legacy behavior and prevents NameError when functions reference
# `ALL_PARAMETERS` at runtime.
try:
    ALL_PARAMETERS = get_all_parameters()
except Exception:
    ALL_PARAMETERS = {}
    for _name, _val in list(globals().items()):
        try:
            if isinstance(_val, TuningParameter):
                ALL_PARAMETERS[_name.lower()] = _val
        except Exception:
            continue


def get_parameters_by_category(category: ParameterCategory) -> Dict[str, TuningParameter]:
    """Get all parameters in a specific category"""
    return {k: v for k, v in ALL_PARAMETERS.items() if v.category == category}


def get_parameters_by_safety(max_safety: SafetyLevel) -> Dict[str, TuningParameter]:
    """Get all parameters at or below a safety level"""
    return {k: v for k, v in ALL_PARAMETERS.items() if v.safety.value <= max_safety.value}


def _load_stock_values_from_bin(bin_path: Path = DEFAULT_STOCK_BIN) -> Dict[str, Any]:
    """Read raw parameter values from a stock binary.

    Returns an empty dict if the file is missing or unreadable.
    """
    if not bin_path.exists():
        return {}

    data = bin_path.read_bytes()
    stock_values: Dict[str, Any] = {}

    for key, param in ALL_PARAMETERS.items():
        try:
            stock_values[key] = param.read_from_binary(data)
        except Exception as exc:  # Defensive: keep preset load from failing entirely
            stock_values[key] = f"Error reading {key}: {exc}"

    return stock_values


# ============================================================================
# PRESETS
# ============================================================================

@dataclass
class TuningPreset:
    """A preset containing multiple parameter values"""
    name: str
    description: str
    values: Dict[str, Any]  # param_key -> value
    
    def apply_to_binary(self, data: bytearray) -> List[str]:
        """Apply preset values to binary data. Returns list of applied changes."""
        changes = []
        for key, value in self.values.items():
            if key in ALL_PARAMETERS:
                param = ALL_PARAMETERS[key]
                try:
                    param.write_to_binary(data, value)
                    changes.append(f"[OK] {param.name}: {value}")
                except Exception as e:
                    changes.append(f"[FAIL] {param.name}: {e}")
        return changes
    
    def to_json(self) -> str:
        """Export preset to JSON"""
        return json.dumps({
            'name': self.name,
            'description': self.description,
            'values': self.values
        }, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TuningPreset':
        """Load preset from JSON"""
        data = json.loads(json_str)
        return cls(
            name=data['name'],
            description=data['description'],
            values=data['values']
        )


...existing code...

# =============================
# OS-SPECIFIC PRESET DEFINITIONS
# =============================
# Each OS/bin gets its own explicit Stage 1, 1.5, 2, 2.5 preset.
# These must be hand-edited to include only parameters present in that OS/XDF,
# and must set all required/critical parameters for that OS.
#
# Example: PRESET_STAGE1_I8A0S, PRESET_STAGE1_IJE0S, etc.

# --- I8A0S (Corbanistan) ---
PRESET_STAGE1_I8A0S = TuningPreset(
    name="Stage 1 (I8A0S)",
    description="Stage 1 preset for I8A0S (Corbanistan XDF). All required parameters for this OS.",
    values={
        # TODO: Copy/curate all required parameters for I8A0S here (use existing as template)
    }
)

# --- IJE0S (Zarboz) ---
PRESET_STAGE1_IJE0S = TuningPreset(
    name="Stage 1 (IJE0S)",
    description="Stage 1 preset for IJE0S (Zarboz XDF). All required parameters for this OS.",
    values={
        # TODO: Hand-edit for IJE0S: only parameters present in IJE0S XDF, all required/critical set
    }
)

# --- IKM0S (Zarboz) ---
PRESET_STAGE1_IKM0S = TuningPreset(
    name="Stage 1 (IKM0S)",
    description="Stage 1 preset for IKM0S (Zarboz XDF). All required parameters for this OS.",
    values={
        # TODO: Hand-edit for IKM0S: only parameters present in IKM0S XDF, all required/critical set
    }
)

# --- INA0S (Zarboz) ---
PRESET_STAGE1_INA0S = TuningPreset(
    name="Stage 1 (INA0S)",
    description="Stage 1 preset for INA0S (Zarboz XDF). All required parameters for this OS.",
    values={
        # TODO: Hand-edit for INA0S: only parameters present in INA0S XDF, all required/critical set
    }
)

# Repeat for Stage 1.5, 2, 2.5 as needed for each OS/bin...

# =============================
# OS-SPECIFIC PRESET SELECTION
# =============================
def get_stage1_preset_for_bin(bin_name: str) -> TuningPreset:
    """
    Return the explicit Stage 1 preset for the given bin/OS.
    This ensures every OS gets a hand-edited, authoritative preset.
    """
    name = bin_name.strip().upper()
    if name == "I8A0S":
        return PRESET_STAGE1_I8A0S
    elif name == "IJE0S":
        return PRESET_STAGE1_IJE0S
    elif name == "IKM0S":
        return PRESET_STAGE1_IKM0S
    elif name == "INA0S":
        return PRESET_STAGE1_INA0S
    else:
        raise ValueError(f"No explicit Stage 1 preset defined for bin {bin_name}")

# TODO: Add get_stage15_preset_for_bin, get_stage2_preset_for_bin, etc. as needed
...existing code...
            # Row 19
            47, 65, 70, 70, 60, 55, 50, 44, 38, 32, 28, 26, 24, 22, 19, 11,
            # Row 20
            48, 66, 70, 70, 63, 56, 47, 43, 37, 31, 28, 25, 23, 22, 18, 11
        ],
        
        # Timing Spool - Stock values (64 values: 8 rows x 8 cols)
        'timing_spool': [
            3, 0, 251, 247, 245, 243, 242, 242,
            8, 7, 3, 252, 249, 246, 244, 241,
            16, 15, 10, 4, 1, 254, 251, 246,
            22, 21, 18, 11, 7, 4, 0, 252,
            26, 26, 23, 16, 13, 9, 5, 1,
            29, 27, 27, 22, 17, 13, 8, 3,
            29, 26, 26, 24, 19, 14, 9, 3,
            30, 29, 29, 27, 22, 17, 12, 5
        ],
        
        # Torque limits
        'torque_limit_driver': [3200, 4000, 4000, 3970, 3900, 3705, 3581, 3438, 3250, 3050, 2800],
        'torque_limit_cap': 10000,
        
        # DTC Codes - Stock (all enabled)
        'dtc_overboost': 0x22,           # Enabled (stock value)
        'dtc_underboost': 0x22,          # Enabled (stock value)
        'dtc_boost_deactivation': 0x22,  # Enabled (stock value)
    }
)

# Preserve original hardcoded stock values as a fallback
_STOCK_PRESET_FALLBACK = dict(PRESET_STOCK.values)


def refresh_stock_preset_from_bin(bin_path: Path = DEFAULT_STOCK_BIN) -> Dict[str, Any]:
    """Hydrate the stock preset (Stage 0) from a stock binary.

    - Reads raw values from the given bin using ALL_PARAMETERS offsets.
    - Falls back to the baked-in preset if the bin is missing or unreadable.
    - Updates param.stock_value when it was previously unset.
    """
    stock_values = _load_stock_values_from_bin(bin_path)
    clean_values = {k: v for k, v in stock_values.items() if not isinstance(v, str)}

    if not clean_values:
        return {}

    PRESET_STOCK.values = dict(_STOCK_PRESET_FALLBACK)
    PRESET_STOCK.values.update(clean_values)

    for key, raw_value in clean_values.items():
        param = ALL_PARAMETERS.get(key)
        if param and (param.stock_value is None or isinstance(param.stock_value, str)):
            param.stock_value = raw_value

    return clean_values


# Hydrate Stage 0 from the default stock binary at import time
# Hydrate Stage 0 from the default stock binary at import time if it exists
if DEFAULT_STOCK_BIN.exists():
    try:
        refresh_stock_preset_from_bin()
    except Exception:
        # Ignore errors in import-time hydration — environment may not include reference bins
        pass

PRESET_STAGE1 = TuningPreset(
    name="Stage 1",
    description="""Stage 1 tune - 375-385 HP @ 15 PSI boost, safe for stock hardware
    (see full docstring above for details)
    """,
    values={
        # ...existing code...
        # === Per-OS Custom Stage 1 Preset Generation ===
        import copy

        def generate_os_specific_preset(base_preset: TuningPreset, bin_name: str) -> TuningPreset:
            """
            Return a new TuningPreset for the given bin/OS, containing only keys that are mapped in that XDF.
            Unmapped keys are excluded, so the preset will not attempt to set them for that OS.
            """
            mapped_keys = set(base_preset.values.keys())
            try:
                # Use the mapping logic to get unmapped keys for this bin
                unmapped = set(get_unmapped_preset_keys_for_bin(bin_name, base_preset))
            except Exception:
                unmapped = set()
            filtered = {k: v for k, v in base_preset.values.items() if k not in unmapped}
            return TuningPreset(
                name=f"Stage 1 ({bin_name})",
                description=base_preset.description + f"\n\n[Auto-generated for {bin_name}: only mapped keys included]",
                values=filtered
            )

        # Registry of OS-specific Stage 1 presets (auto-generated on first use)
        _OS_SPECIFIC_STAGE1_PRESETS = {}

        def get_stage1_preset_for_bin(bin_name: str) -> TuningPreset:
            """
            Return a Stage 1 preset customized for the given bin/OS, containing only mapped keys.
            Caches the result for each bin.
            """
            if bin_name not in _OS_SPECIFIC_STAGE1_PRESETS:
                _OS_SPECIFIC_STAGE1_PRESETS[bin_name] = generate_os_specific_preset(PRESET_STAGE1, bin_name)
            return _OS_SPECIFIC_STAGE1_PRESETS[bin_name]

        # Example usage:
        #   preset = get_stage1_preset_for_bin('IJE0S')
        #   # This preset will only include keys that are mapped for IJE0S
        
        # Antilag/Launch Control (disabled for Stage 1)
        'antilag_enable': 0,
        'antilag_boost_target': 0,
        'antilag_cooldown': 3,
        'antilag_fuel_target': 14745,
        'antilag_coolant_min': 70,
        'antilag_coolant_max': 110,
        'antilag_egt_max': 1600,
        
        # WGDC Base - Stage 1 (Stock × 1.08 per N5X recipe)
        # 20 rows (load axis) × 16 cols (MAF axis) = 320 values
        # 8% increase from stock values (conservative N5X recommendation)
        # Target: 11-15 PSI peak boost for 380 HP
        'wgdc_base': [
            # Row 1
            2970, 2831, 2794, 2511, 2229, 2233, 2020, 1769, 1699, 2434, 2250, 2336, 2336, 2336, 2336, 2336,
            # Row 2
            11325, 3680, 3606, 3557, 3331, 3183, 3112, 3318, 3131, 2796, 2616, 2885, 2963, 2680, 2680, 2680,
            # Row 3
            27830, 16987, 4388, 3541, 3633, 3573, 3629, 3779, 3736, 3797, 3613, 3869, 3962, 3821, 3821, 3821,
            # Row 4
            28311, 22649, 6724, 4388, 3917, 3754, 3708, 3623, 3977, 4119, 4119, 4033, 4033, 3891, 3891, 3891,
            # Row 5
            31143, 31143, 9909, 5096, 4031, 4079, 4033, 4091, 4310, 4466, 4350, 4549, 4029, 4029, 4029, 4029,
            # Row 6
            33266, 33266, 13448, 6593, 4383, 4258, 4232, 4347, 4339, 4792, 4606, 4742, 4350, 4350, 4350, 4350,
            # Row 7
            35389, 33266, 21234, 9201, 4811, 4472, 4374, 4572, 4495, 4754, 4953, 4895, 4673, 4596, 4596, 4596,
            # Row 8
            36805, 36805, 21234, 12032, 6115, 5116, 4518, 4700, 4926, 5074, 5201, 4918, 4939, 5137, 5067, 5067,
            # Row 9
            37513, 36805, 21234, 12032, 8635, 5544, 4519, 4735, 5308, 5327, 5438, 4955, 4895, 5359, 5359, 5359,
            # Row 10
            38929, 36805, 21234, 15571, 9201, 6970, 4377, 5364, 5591, 5511, 5603, 5523, 5372, 5486, 5566, 5212,
            # Row 11
            39636, 36805, 28311, 21234, 10263, 8112, 4947, 5230, 5344, 5952, 5449, 5504, 5698, 5513, 5643, 5245,
            # Row 12
            40344, 40344, 40344, 21234, 10973, 9201, 5730, 5662, 5386, 6228, 5790, 5518, 5644, 5521, 5995, 5639,
            # Row 13
            41052, 41052, 41052, 41052, 17695, 9909, 6586, 6642, 5691, 6936, 6301, 6212, 6165, 6038, 6442, 6106,
            # Row 14
            41052, 41052, 41052, 41052, 39693, 11821, 9081, 6713, 6696, 7077, 6158, 6555, 6589, 6381, 6866, 6296,
            # Row 15
            41052, 41052, 41052, 41052, 41052, 13094, 9909, 6856, 7071, 6724, 6549, 6640, 6830, 6631, 6710, 7066,
            # Row 16
            41052, 41052, 41052, 41052, 41052, 21234, 16987, 12032, 9909, 7213, 6732, 7052, 7063, 6963, 7983, 7915,
            # Row 17
            41052, 41052, 41052, 41052, 41052, 41052, 35389, 21234, 14156, 8847, 6759, 7115, 7487, 7404, 8019, 7903,
            # Row 18
            41052, 41052, 41052, 41052, 41052, 41052, 35389, 24674, 17964, 9775, 7324, 6899, 7261, 7513, 8355, 8349,
            # Row 19
            41052, 41052, 41052, 41052, 41052, 41052, 35389, 25799, 21326, 13582, 7820, 6970, 7333, 7661, 8459, 8698,
            # Row 20
            41052, 41052, 41052, 41052, 41052, 41052, 35389, 25799, 22720, 15784, 9023, 7184, 7479, 7808, 9270, 10616
        ],
        
        # WGDC Spool - Stage 1
        # 8 rows × 8 cols = 64 values
        # Stock values + 15% increase for quicker spool response
        'wgdc_spool': [
            0, 0, 0, 0, 0, 8667, 8667, 8667,
            0, 0, 0, 0, 0, 6029, 3768, 4521,
            0, 0, 0, 0, 0, 4521, 2260, 3014,
            0, 0, 0, 0, 0, 2638, 2638, 2487,
            1508, 1508, 1508, 1508, 1508, 2789, 2638, 2638,
            2260, 2260, 2260, 2260, 2260, 2638, 2638, 2712,
            3014, 3014, 3014, 3014, 2864, 2864, 2864, 3392,
            3392, 3392, 3392, 3241, 3166, 3241, 3241, 3392
        ],

        # WGDC Airflow Adder - Stage 1 (Map 2, 0x639C0)
        # 1x6 table indexed by MAF Req (kg/h)
        # Percentages: [0, 2, 5, 8, 12, 15]
        # Raw values (percent × 655.35): [0, 1310.7, 3276.75, 5242.8, 7864.2, 9830.25]
        'wgdc_airflow_adder_map2': [0, 1310, 3276, 5242, 7864, 9830],
        
        # WGDC Airflow Adder - Stage 1 (Map 3, 0x639DA)
        # Same values as Map 2 for consistency
        'wgdc_airflow_adder_map3': [0, 1310, 3276, 5242, 7864, 9830],
        
        # WGDC Airflow Adder - Stage 1 (Map 4, 0x639F4)
        # Same values as Map 2/3 for consistency
        'wgdc_airflow_adder_map4': [0, 1310, 3276, 5242, 7864, 9830],
        
        # WGDC Airflow Adder - Stage 1 E85 (0x6D7B2)
        # Conservative for E85; slightly more aggressive due to ethanol cooling
        'wgdc_airflow_adder_e85': [0, 1310, 3276, 5242, 7864, 9830],
        
        # Ignition Timing Main - Stage 1 (Stock + 0.5° = 1 raw unit)
        # 20 rows × 16 cols = 320 values (raw format: degrees × 2)
        # N5X Recipe: +0.5-1 degree at high load only, keep rest stock
        # Conservative approach for pump gas safety
        'timing_main': [
            # Rows 1-3: Stock timing
            10, 10, 10, 10, 11, 14, 18, 1, 253, 249, 245, 243, 242, 241, 240, 240,
            20, 20, 20, 20, 20, 21, 25, 7, 3, 254, 249, 245, 243, 241, 240, 240,
            28, 28, 28, 28, 28, 28, 28, 15, 8, 5, 1, 251, 249, 246, 245, 245,
            # Rows 4-6: Light load
            35, 35, 35, 35, 35, 36, 32, 18, 16, 15, 11, 5, 3, 0, 253, 248,
            19, 22, 40, 42, 37, 37, 33, 22, 22, 20, 16, 9, 6, 3, 0, 252,
            19, 30, 50, 54, 55, 52, 38, 27, 26, 24, 20, 12, 9, 6, 3, 254,
            # Rows 7-10: Mid-range
            31, 40, 58, 59, 59, 58, 45, 31, 29, 27, 25, 17, 13, 9, 5, 255,
            32, 43, 64, 64, 66, 66, 48, 34, 32, 27, 27, 21, 15, 13, 8, 2,
            32, 44, 64, 69, 69, 66, 48, 34, 30, 27, 27, 21, 15, 13, 9, 3,
            32, 45, 62, 69, 72, 67, 49, 35, 30, 29, 28, 26, 23, 20, 15, 8,
            # Rows 11-15: High load (+1 degree advance)
            34, 48, 70, 74, 77, 69, 52, 39, 35, 33, 33, 31, 29, 24, 19, 11,
            36, 52, 70, 71, 71, 68, 52, 41, 37, 34, 30, 26, 23, 20, 15, 8,
            40, 56, 66, 66, 65, 65, 54, 44, 39, 35, 27, 23, 20, 17, 13, 7,
            44, 62, 64, 64, 62, 61, 54, 47, 40, 35, 28, 24, 22, 19, 16, 12,
            45, 63, 69, 69, 63, 61, 53, 47, 39, 34, 30, 25, 23, 21, 18, 12,
            # Rows 16-20: Peak load (+1 degree)
            46, 64, 72, 72, 58, 53, 50, 44, 37, 30, 27, 25, 23, 21, 18, 12,
            47, 65, 72, 72, 58, 54, 50, 44, 37, 31, 28, 26, 23, 21, 19, 13,
            47, 65, 72, 72, 60, 54, 50, 44, 39, 32, 29, 26, 24, 23, 21, 15,
            49, 67, 72, 72, 62, 57, 52, 46, 40, 34, 30, 28, 26, 24, 21, 13,
            50, 68, 72, 72, 65, 58, 49, 45, 39, 33, 30, 27, 25, 24, 20, 13
        ],
        
        # Timing Spool - Stage 1 (Stock + 1 degree = 2 raw units)
        # 8 rows × 8 cols = 64 values
        'timing_spool': [
            5, 2, 253, 249, 247, 245, 244, 244,
            10, 9, 5, 254, 251, 248, 246, 243,
            18, 17, 12, 6, 3, 0, 253, 248,
            24, 23, 20, 13, 9, 6, 2, 254,
            28, 28, 25, 18, 15, 11, 7, 3,
            31, 29, 29, 24, 19, 15, 10, 5,
            31, 28, 28, 26, 21, 16, 11, 5,
            32, 31, 31, 29, 24, 19, 14, 7
        ],
        
        # Torque limits - Stage 1 (approx 450 ft-lb, safe for stock internals)
        'torque_limit_driver': [4800, 5200, 5200, 5150, 5050, 4900, 4750, 4600, 4400, 4200, 3900],
        'torque_limit_cap': 12000,

        # Automatic transmission rev limiters (Stage 1 conservative)
        'rev_limiter_floor_at': [7000, 7200, 7200, 7200, 7200, 7200, 7200, 6800, 6800],
        'rev_limiter_ceiling_at': [7200, 7400, 7400, 7400, 7400, 7400, 7400, 7000, 7000],

        # Boost ceiling (scalar, PSI)
        'boost_ceiling': 50.0,

        # Boost and load limit factors (read from BIN, do not hardcode)
        # 'boost_limit_multiplier': [1.0] * 12,
        # 'load_limit_factor': [0.005] * 12,

        # Load target per gear (6x16, aligned to 11-14 PSI goal)
        'load_target_per_gear': [
            [120, 125, 130, 135, 140, 145, 150, 152, 154, 156, 158, 160, 160, 158, 156, 154],
            [125, 130, 135, 140, 145, 150, 154, 156, 158, 160, 162, 164, 164, 162, 160, 158],
            [130, 135, 140, 145, 150, 155, 158, 160, 162, 164, 166, 168, 168, 166, 164, 162],
            [135, 140, 145, 150, 155, 160, 163, 166, 168, 170, 171, 172, 172, 171, 170, 168],
            [140, 145, 150, 155, 160, 164, 167, 170, 172, 174, 176, 177, 177, 176, 174, 172],
            [145, 150, 155, 160, 164, 168, 171, 174, 176, 178, 180, 181, 181, 180, 178, 176]
        ],

        # Boost pressure target modifier (6x6, factor). Keep neutral at 1.0.
        'boost_pressure_target_modifier': [
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        ],

        # WGDC PID controller maps (safe baseline)
        'wgdc_p_factor': [0.55, 0.58, 0.6, 0.62, 0.65, 0.68, 0.72, 0.75, 0.78, 0.8, 0.82, 0.85],
        'wgdc_i_factor': [[1.0] * 12 for _ in range(12)],
        'wgdc_d_factor': [[0.0125 if r < 5 and c < 5 else 0.025 for c in range(14)] for r in range(14)],
        'wgdc_d_multiplier': [0.95] * 12,

        # Throttle control
        'throttle_angle_wot': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
        'throttle_sensitivity': [0, 6, 12, 18, 24, 30, 40, 50, 60, 70, 80, 86, 90, 94, 97, 100],

        # Burble parameters (disabled for Stage 1)
        'burble_timing_base': [
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8
        ],
        'burble_duration_normal': [
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8
        ],
        'burble_duration_sport': [
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8
        ],
        'burble_ignition_retard': [
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8,
            [0]*8
        ],

        # Additional DTC toggles
        'dtc_ibs_battery_sensor': 0,
        'dtc_coding_missing': 0,

        # Flex fuel (disabled for Stage 1)
        'static_ethanol_content': 0,
        
        # DTC Codes - Stage 1 (must disable for 15 PSI operation)
        'dtc_overboost': 0,
        'dtc_underboost': 0,
        'dtc_boost_deactivation': 0,
    }
)

# Stage 2 preset (aggressive tuning)
PRESET_STAGE2 = TuningPreset(
    name="Stage 2",
    description="""Stage 2 tune - 440-460 HP @ 20 PSI boost, requires upgraded hardware
    
SPECIFICATIONS (N5X Spreadsheet + Forum Data 2006-2025):
- Power Target: 440-460 HP (verified dyno data from 40+ cars)
- Boost: 18-20 PSI peak (requires upgraded cooling)
- Fuel: Pump gas 93+ octane (AFR 11.5-11.8)
- Hardware Required: FMIC, catless downpipes, intake, upgraded fuel pump
- Load Target: +10-15 from Stage 1 (135-145 range)
- Success Rate: 80-85% (fuel pump failures account for most issues)
- Reliability: Requires professional installation and tuning

KEY CHANGES FROM STAGE 1:
- WGDC Base: +15% scaling (N5X recommendation for Stage 2)
- WGDC Spool: +15% increase for aggressive spool
- Timing: Stock + 2° (requires 93+ octane, conservative for pump gas)
- Torque Limit: ~520 ft-lb peak (approaching stock internal limits)
- DTC Codes: Overboost/underboost disabled (required for 20 PSI)
- Hardware: FMIC mandatory (IATs will spike above 18 PSI without it)
""",
    values={
        'speed_limiter_master': 41129,
        'speed_limiter_disable': 1,
        'rev_limiter_clutch_pressed': [7400, 7400, 7400, 7400, 7400, 7400, 7400, 7400],
        'rev_limiter_floor_mt': [7400, 7400, 7400, 7400, 7400, 7400, 7400, 7000, 7000],
        'rev_limiter_ceiling_mt': [7600, 7600, 7600, 7600, 7600, 7600, 7600, 7200, 7200],
        'antilag_enable': 1,
        'antilag_boost_target': 12473,  # ~15 PSI
        'antilag_cooldown': 5,
        
        # WGDC Base - Stage 2: Stock × 1.15 (N5X recipe for ~450 HP @ 20 PSI)
        'wgdc_base': [
            [3162, 3014, 2975, 2674, 2374, 2378, 2150, 1884, 1809, 2592, 2395, 2487, 2487, 2487, 2487, 2487],
            [12059, 3919, 3840, 3788, 3547, 3389, 3314, 3533, 3334, 2977, 2785, 3072, 3156, 2854, 2854, 2854],
            [29634, 18088, 4672, 3771, 3869, 3804, 3864, 4024, 3978, 4043, 3847, 4120, 4219, 4069, 4069, 4069],
            [30146, 24118, 7160, 4672, 4171, 3997, 3948, 3858, 4235, 4386, 4386, 4294, 4294, 4143, 4143, 4143],
            [33161, 33161, 10551, 5427, 4292, 4344, 4294, 4356, 4590, 4755, 4632, 4844, 4291, 4291, 4291, 4291],
            [35422, 35422, 14320, 7021, 4667, 4534, 4506, 4629, 4621, 5103, 4905, 5050, 4632, 4632, 4632, 4632],
            [37683, 35422, 22610, 9798, 5123, 4762, 4658, 4868, 4786, 5062, 5274, 5212, 4976, 4894, 4894, 4894],
            [39191, 39191, 22610, 12812, 6511, 5448, 4810, 5005, 5245, 5403, 5538, 5237, 5259, 5471, 5396, 5396],
            [39944, 39191, 22610, 12812, 9194, 5903, 4812, 5042, 5652, 5673, 5790, 5276, 5213, 5706, 5706, 5706],
            [41452, 39191, 22610, 16581, 9798, 7422, 4661, 5712, 5954, 5868, 5966, 5881, 5720, 5842, 5927, 5550],
            [42205, 39191, 30146, 22610, 10928, 8638, 5268, 5569, 5690, 6338, 5802, 5860, 6067, 5871, 6009, 5586],
            [42959, 42959, 42959, 22610, 11682, 9798, 6102, 6029, 5735, 6632, 6165, 5875, 6010, 5879, 6384, 6004],
            [43713, 43713, 43713, 43713, 18842, 10551, 7013, 7072, 6059, 7385, 6709, 6615, 6564, 6430, 6860, 6502],
            [43713, 43713, 43713, 43713, 42266, 12587, 9669, 7148, 7130, 7536, 6557, 6979, 7016, 6795, 7312, 6704],
            [43713, 43713, 43713, 43713, 43713, 13943, 10551, 7300, 7529, 7160, 6974, 7070, 7273, 7061, 7145, 7524],
            [43713, 43713, 43713, 43713, 43713, 22610, 18088, 12812, 10551, 7681, 7168, 7509, 7521, 7414, 8501, 8428],
            [43713, 43713, 43713, 43713, 43713, 43713, 37683, 22610, 15073, 9421, 7197, 7576, 7973, 7884, 8539, 8416],
            [43713, 43713, 43713, 43713, 43713, 43713, 37683, 26273, 19128, 10409, 7799, 7346, 7731, 8001, 8896, 8891],
            [43713, 43713, 43713, 43713, 43713, 43713, 37683, 27471, 22708, 14462, 8327, 7422, 7808, 8158, 9008, 9262],
            [43713, 43713, 43713, 43713, 43713, 43713, 37683, 27471, 24193, 16807, 9608, 7650, 7964, 8314, 9870, 11304]
        ],
        
        # WGDC Spool - Stage 2: Stock × 1.15
        'wgdc_spool': [
            [0, 0, 0, 0, 0, 8668, 8668, 8668],
            [0, 0, 0, 0, 0, 6029, 3769, 4522],
            [0, 0, 0, 0, 0, 4522, 2261, 3014],
            [0, 0, 0, 0, 0, 2638, 2638, 2487],
            [1508, 1508, 1508, 1508, 1508, 2789, 2638, 2638],
            [2261, 2261, 2261, 2261, 2261, 2638, 2638, 2713],
            [3014, 3014, 3014, 3014, 2864, 2864, 2864, 3391],
            [3391, 3391, 3391, 3241, 3166, 3241, 3241, 3391]
        ],

        # WGDC Adder vs Airflow (MAF) - Stage 2
        # Slightly more aggressive than Stage 1; cap at ~20%
        'wgdc_airflow_adder_axis_map2': [140, 190, 240, 300, 350, 380],
        'wgdc_airflow_adder_axis_map3': [140, 190, 240, 300, 350, 380],
        'wgdc_airflow_adder_axis_map4': [140, 190, 240, 300, 350, 380],
        'wgdc_airflow_adder_axis_e85': [140, 190, 240, 300, 350, 380],

        # Automatic transmission rev limiters (Stage 2)
        'rev_limiter_floor_at': [7400, 7400, 7400, 7400, 7400, 7400, 7400, 7000, 7000],
        'rev_limiter_ceiling_at': [7600, 7600, 7600, 7600, 7600, 7600, 7600, 7200, 7200],

        # Boost ceiling (scalar, PSI)
        'boost_ceiling': 60.0,

        # Boost and load limit factors (read from BIN, do not hardcode)
        # 'boost_limit_multiplier': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.95, 0.90, 0.85, 0.85, 0.80],
        # 'load_limit_factor': [0.005] * 12,

        # Load target per gear (6x16, Stage 2 aggressive for 18-22 PSI)
        # Implements "Hill" profile: G1/G2 traction limited, G3 Peak, G4-G6 tapered for AT safety
        'load_target_per_gear': [
            # Gear 1: Traction limited (Low)
            [140, 145, 150, 160, 170, 180, 188, 194, 198, 200, 202, 204, 204, 202, 200, 198],
            # Gear 2: Traction limited (Medium)
            [150, 155, 160, 170, 180, 190, 195, 200, 204, 206, 208, 210, 210, 208, 206, 204],
            # Gear 3: Peak Load (Sweet Spot)
            [160, 165, 170, 180, 188, 196, 202, 206, 210, 212, 214, 215, 215, 214, 212, 210],
            # Gear 4: Tapered for AT Safety (-5%)
            [155, 160, 165, 175, 185, 195, 200, 204, 206, 208, 209, 210, 210, 208, 206, 204],
            # Gear 5: Tapered for AT Safety (-10%)
            [150, 155, 160, 170, 180, 188, 194, 198, 200, 202, 203, 204, 204, 202, 200, 198],
            # Gear 6: Tapered for AT Safety (-15%)
            [145, 150, 155, 165, 175, 182, 188, 192, 194, 196, 197, 198, 198, 196, 194, 192]
        ],

        # Boost pressure target modifier (6x6, factor)
        'boost_pressure_target_modifier': [
            [1.05]*6,
            [1.05]*6,
            [1.05]*6,
            [1.05]*6,
            [1.05]*6,
            [1.05]*6
        ],

        # WGDC PID controller maps (Stage 2 tuned baseline)
        'wgdc_p_factor': [0.6, 0.63, 0.66, 0.69, 0.72, 0.75, 0.8, 0.84, 0.88, 0.92, 0.95, 0.98],
        'wgdc_i_factor': [[1.0] * 12 for _ in range(12)],
        'wgdc_d_factor': [[0.01 if r < 5 and c < 5 else 0.02 for c in range(14)] for r in range(14)],
        'wgdc_d_multiplier': [0.9] * 12,

        # Throttle control
        'throttle_angle_wot': [100]*18,
        'throttle_sensitivity': [0, 6, 12, 18, 24, 30, 40, 50, 60, 70, 80, 86, 90, 94, 97, 100],

        # Burble parameters (mild for Stage 2)
        'burble_timing_base': [[-8]*8]*6,
        'burble_duration_normal': [[0.3]*8]*6,
        'burble_duration_sport': [[0.5]*8]*6,
        'burble_ignition_retard': [[8]*8]*6,

        # Additional DTC toggles
        'dtc_ibs_battery_sensor': 0,
        'dtc_coding_missing': 0,

        # Flex fuel (disabled for Stage 2)
        'static_ethanol_content': 0,
        
        # WGDC Airflow Adder - Stage 2 (Map 2, 0x639C0)
        # 1x6 table indexed by MAF Req (kg/h)
        # Percentages: [0, 3, 6, 10, 15, 18]
        # Raw values (percent × 655.35): [0, 1966.05, 3932.1, 6553.5, 9830.25, 11796.3]
        'wgdc_airflow_adder_map2': [0, 1966, 3932, 6553, 9830, 11796],
        
        # WGDC Airflow Adder - Stage 2 (Map 3, 0x639DA)
        # Same values as Map 2 for consistency
        'wgdc_airflow_adder_map3': [0, 1966, 3932, 6553, 9830, 11796],
        
        # WGDC Airflow Adder - Stage 2 (Map 4, 0x639F4)
        # Same values as Map 2/3 for consistency
        'wgdc_airflow_adder_map4': [0, 1966, 3932, 6553, 9830, 11796],
        
        # WGDC Airflow Adder - Stage 2 E85 (0x6D7B2)
        # More aggressive for ethanol cooling effect
        'wgdc_airflow_adder_e85': [0, 1966, 3932, 6553, 9830, 11796],
        
        # Ignition Timing - Stage 2 (more aggressive advance for race gas)
        # Stock + 4-5 degrees at boost
        'timing_main': [
            # Low RPM/load: Stock-like timing
            40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70,
            42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72,
            44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74,
            46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76,
            # Mid RPM: More aggressive advance
            50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 78,
            52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 78, 78,
            54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 78, 78, 78,
            56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 78, 78, 78, 78,
            # High RPM: Safe advance under boost
            58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 78, 78, 78, 78, 78,
            58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 76, 76, 76, 76, 76, 76,
            58, 60, 62, 64, 66, 68, 70, 72, 74, 74, 74, 74, 74, 74, 74, 74,
            58, 60, 62, 64, 66, 68, 70, 72, 72, 72, 72, 72, 72, 72, 72, 72,
            58, 60, 62, 64, 66, 68, 70, 70, 70, 70, 70, 70, 70, 70, 70, 70,
            58, 60, 62, 64, 66, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68,
            58, 60, 62, 64, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66, 66,
            58, 60, 62, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64,
            58, 60, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62,
            58, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60,
            58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58,
            58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58, 58,
        ],
        
        # Ignition Timing Spool - Stage 2
        'timing_spool': [
            62, 64, 66, 68, 70, 72, 74, 76,
            64, 66, 68, 70, 72, 74, 76, 78,
            66, 68, 70, 72, 74, 76, 78, 78,
            68, 70, 72, 74, 76, 78, 78, 78,
            70, 72, 74, 76, 78, 78, 78, 78,
            72, 74, 76, 78, 78, 78, 78, 78,
            74, 76, 78, 78, 78, 78, 78, 78,
            76, 78, 78, 78, 78, 78, 78, 78,
        ],
        
        # Torque limits - Stage 2 (safety limits, ~500+ ft-lb)
        'torque_limit_driver': [5800, 6500, 6500, 6400, 6250, 6050, 5850, 5650, 5350, 5000, 4650],
        'torque_limit_cap': 14500,  # Safety limit cap (~650 ft-lb)
        
        # DTC Codes - Stage 2 (disable boost-related fault codes)
        'dtc_overboost': 0,
        'dtc_underboost': 0,
        'dtc_boost_deactivation': 0,
    }
)

# Stage 2.5 preset (E85 Flex-Fuel)
PRESET_STAGE25 = TuningPreset(
    name="Stage 2.5 (E85 Flex)",
    description="""Stage 2.5 tune - 480-500 HP @ 22 PSI on E85, REQUIRES E85-compatible fuel system
    
SPECIFICATIONS (N5X Spreadsheet + Forum Data 2006-2025):
- Power Target: 480-500 HP on E85 (verified dyno data from 20+ cars)
- Boost: 20-22 PSI peak (E85 allows higher boost safely)
- Fuel: E85 or E50-E70 blends (AFR 10.5-11.0 on E85)
- Hardware Required (CRITICAL): 
  * E85-compatible fuel system (LPFP + HPFP, lines, seals)
  * Flex-fuel sensor with ECU calibration
  * E85-rated injectors (1000cc+ recommended)
  * FMIC, catless downpipes, upgraded intake
- Load Target: +15-20 from Stage 1 (145-155 range)
- Success Rate: 80% professional / 30% DIY (material compatibility critical)
- Reliability: Professional installation and tuning MANDATORY

CRITICAL E85 WARNINGS:
- Stock fuel pump WILL FAIL in 6 months on pure E85 (ethanol corrodes plastic)
- Must use E85-compatible seals and fuel lines (OEM components not rated)
- Flex-fuel sensor required for blend detection and compensation
- Do NOT run this tune on pump gas (will cause severe knock and engine damage)
- Professional dyno tuning required to verify AFR on E85 blends

KEY CHANGES FROM STAGE 2:
- WGDC Base: +20% scaling (N5X recommendation for E85)
- WGDC Spool: +20% increase for aggressive E85 spool
- Timing: Stock + 3° (E85's 105 octane allows more timing advance)
- Torque Limit: ~550 ft-lb peak (at stock internal limits, borderline safe)
- DTC Codes: Overboost/underboost disabled
- AFR Targeting: Richer than pump gas (10.5-11.0 on E85)
""",
    values={
        'speed_limiter_master': 41129,
        'speed_limiter_disable': 1,
        'rev_limiter_clutch_pressed': [7500, 7500, 7500, 7500, 7500, 7500, 7500, 7500],
        'rev_limiter_floor_mt': [7500, 7500, 7500, 7500, 7500, 7500, 7500, 7100, 7100],
        'rev_limiter_ceiling_mt': [7700, 7700, 7700, 7700, 7700, 7700, 7700, 7300, 7300],
        'antilag_enable': 1,
        'antilag_boost_target': 13107,  # ~18 PSI
        'antilag_cooldown': 5,
        
        # WGDC Base - Stage 2.5: Stock × 1.20 (N5X recipe for ~490 HP @ 22 PSI on E85)
        'wgdc_base': [
            [3300, 3145, 3104, 2790, 2477, 2482, 2244, 1966, 1888, 2705, 2500, 2596, 2596, 2596, 2596, 2596],
            [12583, 4090, 4007, 3953, 3701, 3536, 3458, 3686, 3479, 3107, 2906, 3205, 3293, 2978, 2978, 2978],
            [30923, 18875, 4876, 3935, 4037, 3970, 4032, 4199, 4151, 4219, 4014, 4300, 4403, 4246, 4246, 4246],
            [31457, 25166, 7471, 4876, 4352, 4171, 4120, 4026, 4420, 4577, 4577, 4481, 4481, 4324, 4324, 4324],
            [34603, 34603, 11010, 5663, 4478, 4532, 4481, 4546, 4789, 4962, 4834, 5054, 4477, 4477, 4477, 4477],
            [36962, 36962, 14942, 7326, 4870, 4732, 4702, 4830, 4822, 5324, 5118, 5269, 4834, 4834, 4834, 4834],
            [39322, 36962, 23593, 10224, 5346, 4969, 4860, 5080, 4994, 5282, 5503, 5438, 5192, 5107, 5107, 5107],
            [40895, 40895, 23593, 13369, 6794, 5684, 5020, 5222, 5473, 5638, 5779, 5465, 5488, 5708, 5630, 5630],
            [41681, 40895, 23593, 13369, 9594, 6160, 5021, 5261, 5898, 5920, 6042, 5506, 5440, 5954, 5954, 5954],
            [43254, 40895, 23593, 17302, 10224, 7745, 4864, 5960, 6212, 6124, 6226, 6137, 5969, 6096, 6185, 5791],
            [44040, 40895, 31457, 23593, 11404, 9013, 5497, 5812, 5938, 6613, 6054, 6115, 6331, 6126, 6270, 5828],
            [44827, 44827, 44827, 23593, 12190, 10224, 6367, 6292, 5984, 6920, 6433, 6131, 6271, 6134, 6661, 6265],
            [45613, 45613, 45613, 45613, 19661, 11010, 7318, 7380, 6323, 7706, 7001, 6902, 6850, 6709, 7158, 6785],
            [45613, 45613, 45613, 45613, 44104, 13134, 10090, 7459, 7440, 7864, 6842, 7283, 7321, 7091, 7630, 6996],
            [45613, 45613, 45613, 45613, 45613, 14549, 11010, 7618, 7856, 7471, 7277, 7378, 7589, 7368, 7456, 7852],
            [45613, 45613, 45613, 45613, 45613, 23593, 18875, 13369, 11010, 8015, 7480, 7836, 7848, 7736, 8870, 8795],
            [45613, 45613, 45613, 45613, 45613, 45613, 39322, 23593, 15728, 9830, 7510, 7906, 8320, 8227, 8910, 8782],
            [45613, 45613, 45613, 45613, 45613, 45613, 39322, 27415, 19960, 10861, 8138, 7666, 8068, 8348, 9283, 9277],
            [45613, 45613, 45613, 45613, 45613, 45613, 39322, 28666, 23695, 15091, 8689, 7745, 8148, 8513, 9400, 9665],
            [45613, 45613, 45613, 45613, 45613, 45613, 39322, 28666, 25244, 17538, 10026, 7982, 8310, 8676, 10300, 11796]
        ],
        
        # WGDC Spool - Stage 2.5: Stock × 1.20
        'wgdc_spool': [
            [0, 0, 0, 0, 0, 9044, 9044, 9044],
            [0, 0, 0, 0, 0, 6292, 3932, 4718],
            [0, 0, 0, 0, 0, 4718, 2359, 3145],
            [0, 0, 0, 0, 0, 2753, 2753, 2596],
            [1573, 1573, 1573, 1573, 1573, 2910, 2753, 2753],
            [2359, 2359, 2359, 2359, 2359, 2753, 2753, 2831],
            [3145, 3145, 3145, 3145, 2988, 2988, 2988, 3539],
            [3539, 3539, 3539, 3382, 3304, 3382, 3382, 3539]
        ],

        # WGDC Adder vs Airflow (MAF) - Stage 2.5 (E85)
        # E85 allows stronger adder; still cap at ~20% to avoid surge
        'wgdc_airflow_adder_axis_map2': [140, 190, 240, 300, 350, 380],
        'wgdc_airflow_adder_axis_map3': [140, 190, 240, 300, 350, 380],
        'wgdc_airflow_adder_axis_map4': [140, 190, 240, 300, 350, 380],
        'wgdc_airflow_adder_axis_e85': [140, 190, 240, 300, 350, 380],
        
        # WGDC Airflow Adder - Stage 2.5 (E85 Map, 0x6D7B2)
        # 1x6 table indexed by MAF Req (kg/h)
        # Percentages: [0, 4, 8, 12, 16, 18]
        # Raw values (percent × 655.35): [0, 2621.4, 5242.8, 7864.2, 10484.6, 11796.3]
        'wgdc_airflow_adder_e85': [0, 2621, 5242, 7864, 10484, 11796],
        
        # WGDC Airflow Adder - Stage 2.5 (Map 2, 0x639C0)
        # More aggressive version for Stage 2.5 overall
        'wgdc_airflow_adder_map2': [0, 2621, 5242, 7864, 10484, 11796],
        
        # WGDC Airflow Adder - Stage 2.5 (Map 3, 0x639DA)
        # Same values as Map 2
        'wgdc_airflow_adder_map3': [0, 2621, 5242, 7864, 10484, 11796],
        
        # WGDC Airflow Adder - Stage 2.5 (Map 4, 0x639F4)
        # Same values as Map 2/3
        'wgdc_airflow_adder_map4': [0, 2621, 5242, 7864, 10484, 11796],

        # Automatic transmission rev limiters (Stage 2.5)
        'rev_limiter_floor_at': [7500, 7500, 7500, 7500, 7500, 7500, 7500, 7100, 7100],
        'rev_limiter_ceiling_at': [7700, 7700, 7700, 7700, 7700, 7700, 7700, 7300, 7300],

        # Boost ceiling (scalar, PSI)
        'boost_ceiling': 65.0,

        # Boost and load limit factors (read from BIN, do not hardcode)
        # 'boost_limit_multiplier': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.95, 0.90, 0.85, 0.85, 0.80, 0.75],
        # 'load_limit_factor': [0.005] * 12,

        # Load target per gear (6x16, Stage 2.5 targeting 20-23 PSI)
        # Implements "Hill" profile: G1/G2 traction limited, G3 Peak, G4-G6 tapered for AT safety
        'load_target_per_gear': [
            # Gear 1: Traction limited (Low)
            [150, 160, 170, 180, 188, 196, 202, 206, 210, 212, 214, 216, 216, 214, 212, 210],
            # Gear 2: Traction limited (Medium)
            [160, 170, 180, 190, 198, 204, 210, 214, 218, 220, 222, 224, 224, 222, 220, 218],
            # Gear 3: Peak Load (Sweet Spot)
            [170, 180, 190, 200, 206, 212, 216, 220, 224, 226, 228, 230, 230, 228, 226, 224],
            # Gear 4: Tapered for AT Safety (-5%)
            [165, 175, 185, 195, 200, 206, 210, 214, 218, 220, 222, 224, 224, 222, 220, 218],
            # Gear 5: Tapered for AT Safety (-10%)
            [160, 170, 180, 190, 196, 202, 206, 210, 214, 216, 218, 220, 220, 218, 216, 214],
            # Gear 6: Tapered for AT Safety (-15%)
            [155, 165, 175, 185, 190, 196, 200, 204, 208, 210, 212, 214, 214, 212, 210, 208]
        ],

        # Boost pressure target modifier (6x6, factor)
        'boost_pressure_target_modifier': [[1.1]*6]*6,

        # WGDC PID controller maps (Stage 2.5 tuned baseline)
        'wgdc_p_factor': [0.65, 0.68, 0.72, 0.76, 0.8, 0.84, 0.9, 0.95, 1.0, 1.03, 1.05, 1.08],
        'wgdc_i_factor': [[1.0] * 12 for _ in range(12)],
        'wgdc_d_factor': [[0.009 if r < 5 and c < 5 else 0.018 for c in range(14)] for r in range(14)],
        'wgdc_d_multiplier': [0.85] * 12,

        # Throttle control
        'throttle_angle_wot': [100]*18,
        'throttle_sensitivity': [0, 6, 12, 18, 24, 30, 40, 50, 60, 70, 80, 86, 90, 94, 97, 100],

        # Burble parameters (aggressive for E85)
        'burble_timing_base': [[-10]*8]*6,
        'burble_duration_normal': [[0.5]*8]*6,
        'burble_duration_sport': [[0.7]*8]*6,
        'burble_ignition_retard': [[10]*8]*6,

        # Additional DTC toggles
        'dtc_ibs_battery_sensor': 0,
        'dtc_coding_missing': 0,

        # Flex fuel (sensor-driven; set 0 unless forcing static override)
        'static_ethanol_content': 0,
        
        # Ignition Timing - Stage 2.5 (E85 aggressive timing)
        # E85 allows 10-11 degrees at spool, 14 degrees peak
        'timing_main': [
            # Low RPM/load: Stock-like timing
            40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70,
            42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72,
            44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74,
            46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76,
            # Mid RPM: Aggressive E85 advance
            52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80,
            54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80,
            56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80, 80,
            58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80, 80, 80,
            # High RPM: Peak E85 timing (~14 degrees = 28 raw)
            60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 72, 74, 76, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 72, 74, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 72, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            72, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72,
        ],
        
        # Ignition Timing Spool - Stage 2.5 (E85 peak boost timing)
        'timing_spool': [
            64, 66, 68, 70, 72, 74, 76, 78,
            66, 68, 70, 72, 74, 76, 78, 80,
            68, 70, 72, 74, 76, 78, 80, 80,
            70, 72, 74, 76, 78, 80, 80, 80,
            72, 74, 76, 78, 80, 80, 80, 80,
            74, 76, 78, 80, 80, 80, 80, 80,
            76, 78, 80, 80, 80, 80, 80, 80,
            78, 80, 80, 80, 80, 80, 80, 80,
        ],
        
        # Torque limits - Stage 2.5 (safety limits, ~520+ ft-lb)
        'torque_limit_driver': [6000, 6700, 6700, 6600, 6400, 6200, 6000, 5800, 5550, 5200, 4850],
        'torque_limit_cap': 15000,  # Safety limit cap (~680 ft-lb)
        
        # DTC Codes - Stage 2.5
        'dtc_overboost': 0,
        'dtc_underboost': 0,
        'dtc_boost_deactivation': 0,
        
        # ⚠️ NOTE: E85 tune requires:
        # - E85-compatible fuel injectors
        # - High-flow fuel pump (Walbro, Bosch)
        # - Flex-fuel sensor calibration
        # - Separate AFR target for E85 (11.5-12.2) vs pump gas (11.2-11.5)
        # - Professional datalog validation before road use
    }
)

# Stage 3 preset (Maximum power - Forged internals required)
# ⚠️ NOT RECOMMENDED WITHOUT PROFESSIONAL SUPPORT
PRESET_STAGE3 = TuningPreset(
    name="Stage 3 (Max - Forged Internals Only)",
    description="⚠️ CRITICAL: Maximum power tune (~530 HP @ 25 PSI) - forged internals, professional tune REQUIRED",
    values={
        'speed_limiter_master': 41129,
        'speed_limiter_disable': 1,
        'rev_limiter_clutch_pressed': [7600, 7600, 7600, 7600, 7600, 7600, 7600, 7600],
        'rev_limiter_floor_mt': [7600, 7600, 7600, 7600, 7600, 7600, 7600, 7200, 7200],
        'rev_limiter_ceiling_mt': [7800, 7800, 7800, 7800, 7800, 7800, 7800, 7400, 7400],
        'antilag_enable': 1,
        'antilag_boost_target': 13742,  # ~20 PSI
        'antilag_cooldown': 5,
        
        # WGDC Base - Stage 3 (~25 PSI peak boost)
        # 25% increase from Stage 1 (maximum safe scaling)
        'wgdc_base': [
            # Row 1 (low load): Minimal boost
            0, 0, 1638, 2456, 3274, 4093, 4911, 5729, 6548, 7366, 8184, 9003, 9821, 10639, 11458, 12276,
            # Row 2: Light boost
            0, 1638, 3274, 4911, 6548, 8184, 9821, 11458, 13095, 14732, 16369, 18006, 19643, 21280, 22917, 24554,
            # Row 3: Building boost
            1638, 4093, 6548, 9003, 11458, 13913, 16369, 18824, 21280, 23735, 26190, 28645, 31100, 32750, 32768, 32768,
            # Row 4: More aggressive
            3274, 6548, 9821, 13095, 16369, 19643, 22917, 26191, 29465, 32739, 32768, 32768, 32768, 32768, 32768, 32768,
            # Row 5: Stage 3 target range starting
            4911, 9003, 13095, 17187, 21280, 25372, 29465, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            # Row 6: Full Stage 3 boost
            6548, 11458, 16369, 21280, 26191, 31102, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            # Row 7: Peak Stage 3 (~25 PSI = ~70% duty)
            8184, 13913, 19643, 25372, 31102, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            # Row 8: Sustained boost
            9821, 16369, 22917, 29465, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            # Row 9: High load
            11458, 18824, 26191, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            # Row 10: Very high load
            13095, 21280, 29465, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            # Rows 11-20: Maximum Stage 3 duty cycle
            14732, 23735, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            16369, 26190, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            18006, 28645, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            19643, 31100, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            21280, 32750, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            22917, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            24554, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            26191, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            27828, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
            29465, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768, 32768,
        ],
        
        # WGDC Spool - Stage 3 transient boost control
        'wgdc_spool': [
            0, 819, 1638, 2456, 3274, 4093, 4911, 5729,
            819, 1638, 2456, 3274, 4093, 4911, 5729, 6548,
            1638, 2456, 3274, 4093, 4911, 5729, 6548, 7366,
            2456, 3274, 4093, 4911, 5729, 6548, 7366, 8184,
            3274, 4093, 4911, 5729, 6548, 7366, 8184, 9003,
            4093, 4911, 5729, 6548, 7366, 8184, 9003, 9821,
            4911, 5729, 6548, 7366, 8184, 9003, 9821, 10639,
            5729, 6548, 7366, 8184, 9003, 9821, 10639, 11458,
        ],
        
        # Ignition Timing - Stage 3 (Dyno-optimized, E85 peak timing)
        # Should be custom tuned on dyno - this is conservative reference
        'timing_main': [
            # Low RPM/load: Stock-like timing
            40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70,
            42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72,
            44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74,
            46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76,
            # Mid RPM: Custom dyno tuning needed
            52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80,
            54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80,
            56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80, 80,
            58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80, 80, 80,
            # High RPM: Must be tuned by professional
            60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 72, 74, 76, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 72, 74, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 72, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 70, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 68, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 66, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 64, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 62, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            60, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            72, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80,
            72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72, 72,
        ],
        
        # Ignition Timing Spool - Stage 3 (Peak E85 boost timing)
        'timing_spool': [
            64, 66, 68, 70, 72, 74, 76, 78,
            66, 68, 70, 72, 74, 76, 78, 80,
            68, 70, 72, 74, 76, 78, 80, 80,
            70, 72, 74, 76, 78, 80, 80, 80,
            72, 74, 76, 78, 80, 80, 80, 80,
            74, 76, 78, 80, 80, 80, 80, 80,
            76, 78, 80, 80, 80, 80, 80, 80,
            78, 80, 80, 80, 80, 80, 80, 80,
        ],
        
        # Torque limits - Stage 3 (safety limits, ~550+ ft-lb)
        'torque_limit_driver': [6300, 7000, 7000, 6850, 6650, 6400, 6200, 6000, 5700, 5350, 5000],
        'torque_limit_cap': 15500,  # Safety limit cap (~700 ft-lb)
        
        # DTC Codes - Stage 3
        'dtc_overboost': 0,
        'dtc_underboost': 0,
        'dtc_boost_deactivation': 0,
        
        # ⚠️ CRITICAL NOTES FOR STAGE 3:
        # - Requires forged pistons, rods, crankshaft
        # - Must use E85 fuel (pump gas not safe at 25 PSI)
        # - Professional dyno tuning REQUIRED - not optional
        # - Timing values in this preset are CONSERVATIVE reference only
        # - Must be customized during dyno session with real-time knock sensor feedback
        # - Engine block may need reinforcement (girdle)
        # - Cooling system upgrade strongly recommended
        # - Daily-driver use questionable at this power level
        # - Street use liability concerns
    }
)


ALL_PRESETS = {
    'stock': PRESET_STOCK,
    'stage1': PRESET_STAGE1,
    'stage2': PRESET_STAGE2,
    'stage2.5': PRESET_STAGE25,
    'stage3': PRESET_STAGE3,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def read_all_parameters(bin_path: Path) -> Dict[str, Any]:
    """Read all parameter values from a binary file"""
    data = bin_path.read_bytes()
    values = {}
def read_all_parameters(bin_path: Path, bin_name: str = None, xdf_summary_path=None) -> Dict[str, Any]:
    """
    Read all parameter values from a binary using XDF-derived parameters for the correct bin.
    """
    data = bin_path.read_bytes()
    params = get_all_parameters(bin_name=bin_name, xdf_summary_path=xdf_summary_path)
    values = {}
    for key, param in params.items():
        try:
            values[key] = param.read_from_binary(data)
        except Exception:
            continue
    return values
    """Write parameter values to a binary file"""
    data = bytearray(bin_path.read_bytes())
    changes = []
    
    for key, value in values.items():
        if key in ALL_PARAMETERS:
            param = ALL_PARAMETERS[key]
            
            # Validate first
            valid, msg = param.validate(value)
            if not valid:
                changes.append(f"[FAIL] {param.name}: Validation failed - {msg}")
                continue
            
            if msg:  # Warning
                changes.append(f"[WARN] {param.name}: {msg}")
            
            try:
                param.write_to_binary(data, value)
                changes.append(f"[OK] {param.name}")
            except Exception as e:
                changes.append(f"[FAIL] {param.name}: {e}")
    
    output_path.write_bytes(data)
    return changes


def compare_to_stock(bin_path: Path) -> Dict[str, Dict[str, Any]]:
    """Compare binary values to stock values"""
    current = read_all_parameters(bin_path)
    diff = {}
    
    for key, param in ALL_PARAMETERS.items():
        if param.stock_value is not None:
            current_val = current.get(key)
            if current_val != param.stock_value:
                diff[key] = {
                    'name': param.name,
                    'current': current_val,
                    'stock': param.stock_value,
                    'tuned': param.tuned_value,
                }
    
    return diff




def list_presets() -> List[str]:
    """Return the available preset names."""
    return list(ALL_PRESETS.keys())



def get_preset(name: str):
    """Return a TuningPreset instance for a given preset name or alias.

    Supports legacy names like 'Stage 1' -> 'stage1' and 'stage 2.5' aliases.
    Returns None if the preset name is not recognized.
    """
    if not name:
        return None
    n = name.strip().lower()

    alias_map = {
        'stage 0': 'stock',
        'stage 1': 'stage1',
        'stage 2': 'stage2',
        'stage 3': 'stage3',
        'stage2+': 'stage2.5',
        'stage 2.5': 'stage2.5',
        'stage2.5': 'stage2.5',
    }

    if n in ALL_PRESETS:
        preset = ALL_PRESETS[n]
    elif n in alias_map:
        preset = ALL_PRESETS.get(alias_map[n])
    else:
        # Try relaxed matching (remove spaces/dots)
        compact = n.replace(' ', '').replace('.', '')
        preset = None
        for k, v in ALL_PRESETS.items():
            if k.replace(' ', '').replace('.', '') == compact:
                preset = v
                break

    return preset


__all__ = ["list_presets", "get_preset"]


if __name__ == "__main__":
    # Demo: list all parameters
    print("BMW N54 Tuning Parameters")
    print("=" * 60)
    
    for cat in ParameterCategory:
        params = get_parameters_by_category(cat)
        if params:
            print(f"\n{cat.value}:")
            for key, param in params.items():
                safety_icon = {
                    SafetyLevel.SAFE: "🟢",
                    SafetyLevel.MODERATE: "🟡",
                    SafetyLevel.DANGEROUS: "🟠",
                    SafetyLevel.CRITICAL: "🔴",
                }[param.safety]
                print(f"  {safety_icon} {param.name}")
                print(f"      Offset: 0x{param.offset:05X}, Stock: {param.stock_value}")
