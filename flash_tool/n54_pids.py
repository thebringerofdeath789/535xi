"""
BMW N54 Engine-Specific PIDs and Live Data Parameters

Defines BMW-specific PIDs for N54 twin-turbo engine diagnostics.
Includes boost pressure, VANOS position, fuel pressure, and other N54-specific parameters.

Created: November 3, 2025
Reference: BMW N54 MSD80/MSD81 DME specification
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Any


class PIDCategory(Enum):
    """PID categories for organization"""
    ENGINE_BASIC = "Engine Basics"
    BOOST_TURBO = "Boost/Turbo"
    FUEL_SYSTEM = "Fuel System"
    VANOS = "VANOS/Timing"
    IGNITION = "Ignition"
    SENSORS = "Sensors"
    TRANSMISSION = "Transmission"
    EMISSIONS = "Emissions"


@dataclass
class N54PID:
    """
    Represents a BMW N54 PID (Parameter ID)
    
    Attributes:
        pid: PID identifier (UDS: 0x22 service, OBD: Mode 01 PID)
        name: Human-readable name
        description: Full description
        unit: Measurement unit
        category: PID category
        decoder: Function to decode raw bytes to value
        min_value: Minimum expected value
        max_value: Maximum expected value
        formula: Text description of conversion formula
        uds_did: UDS Data Identifier (for 0x22 service)
        verified: Whether this PID/DID mapping has been verified against
                  known documentation or tooling (not necessarily bench-tested)
    """
    pid: str
    name: str
    description: str
    unit: str
    category: PIDCategory
    decoder: Optional[Callable[[bytes], Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    formula: Optional[str] = None
    uds_did: Optional[int] = None
    verified: bool = False
    
    def decode(self, data: bytes) -> Any:
        """Decode raw PID data to human-readable value"""
        if self.decoder:
            return self.decoder(data)
        return data.hex()
    
    def __repr__(self) -> str:
        return f"N54PID({self.pid}, {self.name})"


# ============================================================================
# DECODER FUNCTIONS
# ============================================================================

def decode_rpm(data: bytes) -> int:
    """Decode RPM: ((A*256)+B)/4"""
    if len(data) < 2:
        return 0
    return ((data[0] * 256) + data[1]) // 4


def decode_percent(data: bytes) -> float:
    """Decode percentage: A*100/255"""
    if len(data) < 1:
        return 0.0
    return round(data[0] * 100.0 / 255.0, 1)


def decode_temp_celsius(data: bytes) -> int:
    """Decode temperature: A-40 (Celsius) - internal use"""
    if len(data) < 1:
        return -40
    return data[0] - 40


def decode_temp(data: bytes) -> float:
    """Decode temperature to Fahrenheit for US users: (A-40)*9/5+32"""
    if len(data) < 1:
        return -40.0
    celsius = data[0] - 40
    return round(celsius * 9.0 / 5.0 + 32.0, 1)


def decode_fuel_pressure_kpa(data: bytes) -> int:
    """Decode fuel pressure: ((A*256)+B)*10 (kPa) - internal use"""
    if len(data) < 2:
        return 0
    return ((data[0] * 256) + data[1]) * 10


def decode_signed_percent(data: bytes) -> float:
    """Decode signed percentage from int16: value * 100 / 32768"""
    if len(data) < 2:
        return 0.0
    # Little-endian signed int16
    import struct
    value = struct.unpack('<h', data[:2])[0]
    return round(value * 100.0 / 32768.0, 2)


def decode_signed_16bit(data: bytes) -> int:
    """Decode signed 16-bit integer (little-endian)"""
    if len(data) < 2:
        return 0
    import struct
    return struct.unpack('<h', data[:2])[0]


def decode_fuel_pressure(data: bytes) -> float:
    """Decode fuel pressure to PSI for US users: ((A*256)+B)*10 / 6.895"""
    if len(data) < 2:
        return 0.0
    kpa = ((data[0] * 256) + data[1]) * 10
    return round(kpa / 6.89476, 1)


def decode_boost_pressure(data: bytes) -> float:
    """Decode boost pressure from UDS/OBD data.

    Preferred encoding (BMW UDS, e.g. DIDs 0x000B, 0x0042):
        raw = (A*256)+B, value_bar = raw/100

    Fallback for older 1-byte encodings:
        value_bar = A/100

    Returned value is in PSI for easier logging/graphing.
    """
    if not data:
        return 0.0

    if len(data) >= 2:
        raw = (data[0] * 256) + data[1]
    else:
        raw = data[0]

    bar = raw / 100.0
    psi = bar * 14.5038
    return round(psi, 2)


def decode_vanos_position(data: bytes) -> float:
    """Decode VANOS position from UDS data.

    Preferred encoding (BMW UDS VANOS targets/actuals, e.g. 0x0031/0x0033):
        signed = int16_be(A,B), value_deg = signed/10

    This replaces the older 1-byte heuristic and matches the
    read_vanos_data implementation in bmw_protocol.
    """
    if len(data) < 2:
        return 0.0

    raw = (data[0] << 8) | data[1]
    if raw & 0x8000:
        raw -= 0x10000
    return round(raw / 10.0, 1)


def decode_fuel_trim(data: bytes) -> float:
    """Decode fuel trim: (A-128)*100/128 (%)"""
    if len(data) < 1:
        return 0.0
    return round((data[0] - 128) * 100.0 / 128.0, 1)


def decode_timing_advance(data: bytes) -> float:
    """Decode timing advance: (A-128)/2 (degrees)"""
    if len(data) < 1:
        return 0.0
    return round((data[0] - 128) / 2.0, 1)


def decode_speed_kmh(data: bytes) -> int:
    """Decode vehicle speed: A (km/h) - internal use"""
    if len(data) < 1:
        return 0
    return data[0]


def decode_speed(data: bytes) -> float:
    """Decode vehicle speed to mph for US users: A * 0.621371"""
    if len(data) < 1:
        return 0.0
    return round(data[0] * 0.621371, 1)


def decode_map_kpa(data: bytes) -> float:
    """Decode manifold absolute pressure to PSI: A / 6.895"""
    if len(data) < 1:
        return 0.0
    return round(data[0] / 6.89476, 2)


def decode_voltage(data: bytes) -> float:
    """Decode voltage: ((A*256)+B)/1000 (V)"""
    if len(data) < 2:
        return 0.0
    return round(((data[0] * 256) + data[1]) / 1000.0, 2)


def decode_lambda(data: bytes) -> float:
    """Decode lambda/AFR: ((A*256)+B)/32768"""
    if len(data) < 2:
        return 0.0
    return round(((data[0] * 256) + data[1]) / 32768.0, 3)


def decode_injector_pulse(data: bytes) -> float:
    """Decode injector pulse width: ((A*256)+B)/100 (ms)"""
    if len(data) < 2:
        return 0.0
    return round(((data[0] * 256) + data[1]) / 100.0, 2)


def decode_maf_gps(data: bytes) -> float:
    """Decode MAF air flow: ((A*256)+B)/100 (grams/sec)."""
    if len(data) < 2:
        return 0.0
    return round(((data[0] * 256) + data[1]) / 100.0, 2)


def decode_distance_km(data: bytes) -> int:
    """Decode distance (km): ((A*256)+B) - internal use."""
    if len(data) < 2:
        return 0
    return (data[0] * 256) + data[1]


def decode_distance(data: bytes) -> float:
    """Decode distance to miles for US users: ((A*256)+B) * 0.621371."""
    if len(data) < 2:
        return 0.0
    km = (data[0] * 256) + data[1]
    return round(km * 0.621371, 1)


def decode_fuel_rate(data: bytes) -> float:
    """Decode fuel rate to gal/h for US users: ((A*256)+B)/20 / 3.78541."""
    if len(data) < 2:
        return 0.0
    lph = ((data[0] * 256) + data[1]) / 20.0
    return round(lph / 3.78541, 2)


def decode_bar_to_psi(data: bytes) -> float:
    """Decode pressure from bar to PSI: ((A*256)+B)/10 * 14.5038."""
    if len(data) < 2:
        return 0.0
    bar = ((data[0] * 256) + data[1]) / 10.0
    return round(bar * 14.5038, 1)


# ============================================================================
# STANDARD OBD-II PIDs (Mode 01)
# ============================================================================

STANDARD_PIDS = [
    N54PID(
        pid="0C",
        name="Engine RPM",
        description="Engine rotational speed",
        unit="RPM",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_rpm,
        min_value=0,
        max_value=7500,
        formula="((A*256)+B)/4"
    ),
    
    N54PID(
        pid="0D",
        name="Vehicle Speed",
        description="Vehicle speed sensor",
        unit="mph",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_speed,
        min_value=0,
        max_value=160,
        formula="A * 0.621371"
    ),
    
    N54PID(
        pid="05",
        name="Coolant Temperature",
        description="Engine coolant temperature",
        unit="°F",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_temp,
        min_value=-40,
        max_value=420,
        formula="(A-40)*9/5+32"
    ),
    
    N54PID(
        pid="0F",
        name="Intake Air Temperature",
        description="Intake air temperature sensor",
        unit="°F",
        category=PIDCategory.SENSORS,
        decoder=decode_temp,
        min_value=-40,
        max_value=420,
        formula="(A-40)*9/5+32"
    ),
    
    N54PID(
        pid="04",
        name="Engine Load",
        description="Calculated engine load value",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),
    
    N54PID(
        pid="11",
        name="Throttle Position",
        description="Absolute throttle position",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),
    
    N54PID(
        pid="06",
        name="Short Fuel Trim Bank 1",
        description="Short term fuel trim - Bank 1",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_fuel_trim,
        min_value=-100,
        max_value=99.2,
        formula="(A-128)*100/128"
    ),
    
    N54PID(
        pid="07",
        name="Long Fuel Trim Bank 1",
        description="Long term fuel trim - Bank 1",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_fuel_trim,
        min_value=-100,
        max_value=99.2,
        formula="(A-128)*100/128"
    ),
    
    N54PID(
        pid="08",
        name="Short Fuel Trim Bank 2",
        description="Short term fuel trim - Bank 2",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_fuel_trim,
        min_value=-100,
        max_value=99.2,
        formula="(A-128)*100/128"
    ),
    
    N54PID(
        pid="09",
        name="Long Fuel Trim Bank 2",
        description="Long term fuel trim - Bank 2",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_fuel_trim,
        min_value=-100,
        max_value=99.2,
        formula="(A-128)*100/128"
    ),
    
    N54PID(
        pid="0E",
        name="Timing Advance",
        description="Ignition timing advance",
        unit="°",
        category=PIDCategory.IGNITION,
        decoder=decode_timing_advance,
        min_value=-64,
        max_value=63.5,
        formula="(A-128)/2"
    ),

    # Additional common OBD-II PIDs for production-grade logging
    N54PID(
        pid="0B",
        name="Intake Manifold Absolute Pressure",
        description="Intake manifold absolute pressure sensor",
        unit="PSI",
        category=PIDCategory.BOOST_TURBO,
        decoder=decode_map_kpa,
        min_value=0,
        max_value=37,
        formula="A / 6.895"
    ),

    N54PID(
        pid="10",
        name="MAF Air Flow Rate",
        description="Mass air flow sensor",
        unit="g/s",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_maf_gps,
        min_value=0,
        max_value=655.35,
        formula="((A*256)+B)/100"
    ),

    N54PID(
        pid="2E",
        name="Commanded Evaporative Purge",
        description="Commanded evaporative purge duty cycle",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="2F",
        name="Fuel Tank Level",
        description="Fuel level input",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    # Broader generic OBD-II PIDs (Mode 01) for production-grade logging
    N54PID(
        pid="0A",
        name="Fuel Pressure",
        description="Fuel pressure (gauge)",
        unit="PSI",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=lambda data: round(3 * data[0] / 6.89476, 1) if data else 0.0,
        min_value=0,
        max_value=111,
        formula="3*A / 6.895"
    ),

    # O2 sensor voltages and short-term trims (Bank 1/2, Sensor 1/2)
    N54PID(
        pid="14",
        name="O2 Sensor 1 Bank 1",
        description="O2 sensor Bank 1 Sensor 1 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="15",
        name="O2 Sensor 2 Bank 1",
        description="O2 sensor Bank 1 Sensor 2 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="16",
        name="O2 Sensor 1 Bank 2",
        description="O2 sensor Bank 2 Sensor 1 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="17",
        name="O2 Sensor 2 Bank 2",
        description="O2 sensor Bank 2 Sensor 2 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="18",
        name="O2 Sensor 3 Bank 1",
        description="O2 sensor Bank 1 Sensor 3 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="19",
        name="O2 Sensor 4 Bank 1",
        description="O2 sensor Bank 1 Sensor 4 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="1A",
        name="O2 Sensor 3 Bank 2",
        description="O2 sensor Bank 2 Sensor 3 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    N54PID(
        pid="1B",
        name="O2 Sensor 4 Bank 2",
        description="O2 sensor Bank 2 Sensor 4 voltage/trim",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=1.275,
        formula="A/200"
    ),

    # Run time and distance metrics
    N54PID(
        pid="1F",
        name="Run Time Since Start",
        description="Engine run time since start",
        unit="s",
        category=PIDCategory.ENGINE_BASIC,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)"
    ),

    N54PID(
        pid="21",
        name="Distance With MIL On",
        description="Distance travelled with MIL on",
        unit="mi",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_distance,
        min_value=0,
        max_value=None,
        formula="((A*256)+B) * 0.621371"
    ),

    N54PID(
        pid="31",
        name="Distance Since DTC Cleared",
        description="Distance travelled since DTCs cleared",
        unit="mi",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_distance,
        min_value=0,
        max_value=None,
        formula="((A*256)+B) * 0.621371"
    ),

    # EGR related
    N54PID(
        pid="2C",
        name="Commanded EGR",
        description="Commanded EGR",
        unit="%",
        category=PIDCategory.EMISSIONS,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="2D",
        name="EGR Error",
        description="EGR error",
        unit="%",
        category=PIDCategory.EMISSIONS,
        decoder=decode_fuel_trim,
        min_value=-100,
        max_value=99.2,
        formula="(A-128)*100/128"
    ),

    # O2 equivalence ratio and current (wideband sensors)
    N54PID(
        pid="24",
        name="O2 Equiv Ratio Bank 1 S1",
        description="Lambda and current for Bank 1 Sensor 1",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="25",
        name="O2 Equiv Ratio Bank 1 S2",
        description="Lambda and current for Bank 1 Sensor 2",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="26",
        name="O2 Equiv Ratio Bank 1 S3",
        description="Lambda and current for Bank 1 Sensor 3",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="27",
        name="O2 Equiv Ratio Bank 1 S4",
        description="Lambda and current for Bank 1 Sensor 4",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="28",
        name="O2 Equiv Ratio Bank 2 S1",
        description="Lambda and current for Bank 2 Sensor 1",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="29",
        name="O2 Equiv Ratio Bank 2 S2",
        description="Lambda and current for Bank 2 Sensor 2",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="2A",
        name="O2 Equiv Ratio Bank 2 S3",
        description="Lambda and current for Bank 2 Sensor 3",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="2B",
        name="O2 Equiv Ratio Bank 2 S4",
        description="Lambda and current for Bank 2 Sensor 4",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    # Electrical and load-related
    N54PID(
        pid="42",
        name="Control Module Voltage",
        description="ECU supply voltage",
        unit="V",
        category=PIDCategory.SENSORS,
        decoder=decode_voltage,
        min_value=0,
        max_value=25,
        formula="((A*256)+B)/1000"
    ),

    N54PID(
        pid="43",
        name="Absolute Load Value",
        description="Absolute engine load value",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=None,
        min_value=0,
        max_value=25700/255*100,
        formula="((A*256)+B)*100/255"
    ),

    N54PID(
        pid="44",
        name="Commanded Equivalence Ratio",
        description="Commanded equivalence ratio",
        unit="-",
        category=PIDCategory.EMISSIONS,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/32768"
    ),

    N54PID(
        pid="45",
        name="Relative Throttle Position",
        description="Relative throttle position",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="46",
        name="Ambient Air Temperature",
        description="Ambient air temperature",
        unit="°F",
        category=PIDCategory.SENSORS,
        decoder=decode_temp,
        min_value=-40,
        max_value=420,
        formula="(A-40)*9/5+32"
    ),

    N54PID(
        pid="47",
        name="Absolute Throttle Position B",
        description="Absolute throttle position B",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="48",
        name="Absolute Throttle Position C",
        description="Absolute throttle position C",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="49",
        name="Accelerator Pedal Position D",
        description="Accelerator pedal position D",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="4C",
        name="Commanded Throttle Actuator",
        description="Commanded throttle actuator position",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="4D",
        name="Time Run With MIL On",
        description="Time run with MIL on",
        unit="min",
        category=PIDCategory.ENGINE_BASIC,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)"
    ),

    N54PID(
        pid="4E",
        name="Time Since DTC Cleared",
        description="Time since trouble codes cleared",
        unit="min",
        category=PIDCategory.ENGINE_BASIC,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)"
    ),

    N54PID(
        pid="4F",
        name="Max MAF Value",
        description="Maximum MAF air flow value",
        unit="g/s",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_maf_gps,
        min_value=0,
        max_value=655.35,
        formula="((A*256)+B)/100"
    ),

    N54PID(
        pid="52",
        name="Ethanol Fuel Percentage",
        description="Ethanol content in fuel",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255"
    ),

    N54PID(
        pid="5E",
        name="Engine Fuel Rate",
        description="Engine fuel consumption rate",
        unit="L/h",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=None,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)/20"
    ),
]


# ============================================================================
# BMW N54-SPECIFIC PIDs (UDS 0x22 Service)
# ============================================================================

N54_SPECIFIC_PIDS = [
    # Boost/Turbo
    N54PID(
        pid="BOOST_ACTUAL",
        name="Actual Boost Pressure",
        description="Current turbo boost pressure (both turbos)",
        unit="PSI",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0x3010,  # Example DID - needs verification
        decoder=decode_boost_pressure,
        min_value=0,
        max_value=25,
        formula="(A/100)*14.5038 [bar to PSI]"
    ),
    
    N54PID(
        pid="BOOST_TARGET",
        name="Target Boost Pressure",
        description="ECU requested boost pressure",
        unit="PSI",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0x3011,
        decoder=decode_boost_pressure,
        min_value=0,
        max_value=25
    ),
    
    N54PID(
        pid="WGDC_BANK1",
        name="Wastegate Duty Cycle Bank 1",
        description="Wastegate control - Turbo 1",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0x3020,
        decoder=decode_percent,
        min_value=0,
        max_value=100
    ),
    
    N54PID(
        pid="WGDC_BANK2",
        name="Wastegate Duty Cycle Bank 2",
        description="Wastegate control - Turbo 2",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0x3021,
        decoder=decode_percent,
        min_value=0,
        max_value=100
    ),
    
    # VANOS
    N54PID(
        pid="VANOS_INTAKE_ACTUAL",
        name="Intake VANOS Position",
        description="Actual intake camshaft position",
        unit="°",
        category=PIDCategory.VANOS,
        uds_did=0x3030,
        decoder=decode_vanos_position,
        min_value=-64,
        max_value=63.5
    ),
    
    N54PID(
        pid="VANOS_INTAKE_TARGET",
        name="Intake VANOS Target",
        description="Target intake camshaft position",
        unit="°",
        category=PIDCategory.VANOS,
        uds_did=0x3031,
        decoder=decode_vanos_position,
        min_value=-64,
        max_value=63.5
    ),
    
    N54PID(
        pid="VANOS_EXHAUST_ACTUAL",
        name="Exhaust VANOS Position",
        description="Actual exhaust camshaft position",
        unit="°",
        category=PIDCategory.VANOS,
        uds_did=0x3032,
        decoder=decode_vanos_position,
        min_value=-64,
        max_value=63.5
    ),
    
    N54PID(
        pid="VANOS_EXHAUST_TARGET",
        name="Exhaust VANOS Target",
        description="Target exhaust camshaft position",
        unit="°",
        category=PIDCategory.VANOS,
        uds_did=0x3033,
        decoder=decode_vanos_position,
        min_value=-64,
        max_value=63.5
    ),
    
    # Fuel System
    N54PID(
        pid="FUEL_PRESSURE_LOW",
        name="Low Pressure Fuel",
        description="Low pressure fuel pump output",
        unit="kPa",
        category=PIDCategory.FUEL_SYSTEM,
        uds_did=0x3040,
        decoder=decode_fuel_pressure,
        min_value=0,
        max_value=1000
    ),
    
    N54PID(
        pid="FUEL_PRESSURE_HIGH",
        name="High Pressure Fuel",
        description="High pressure fuel pump (HPFP) output",
        unit="bar",
        category=PIDCategory.FUEL_SYSTEM,
        uds_did=0x3041,
        decoder=lambda data: ((data[0] * 256) + data[1]) / 10 if len(data) >= 2 else 0,
        min_value=0,
        max_value=200,
        formula="((A*256)+B)/10"
    ),
    
    N54PID(
        pid="FUEL_PRESSURE_TARGET",
        name="Target Fuel Pressure",
        description="ECU requested fuel rail pressure",
        unit="bar",
        category=PIDCategory.FUEL_SYSTEM,
        uds_did=0x3042,
        decoder=lambda data: ((data[0] * 256) + data[1]) / 10 if len(data) >= 2 else 0,
        min_value=0,
        max_value=200
    ),
    
    N54PID(
        pid="INJECTOR_PULSE_BANK1",
        name="Injector Pulse Width Bank 1",
        description="Fuel injector pulse duration - Bank 1",
        unit="ms",
        category=PIDCategory.FUEL_SYSTEM,
        uds_did=0x3050,
        decoder=decode_injector_pulse,
        min_value=0,
        max_value=25
    ),
    
    N54PID(
        pid="INJECTOR_PULSE_BANK2",
        name="Injector Pulse Width Bank 2",
        description="Fuel injector pulse duration - Bank 2",
        unit="ms",
        category=PIDCategory.FUEL_SYSTEM,
        uds_did=0x3051,
        decoder=decode_injector_pulse,
        min_value=0,
        max_value=25
    ),
    
    # Ignition/Timing
    N54PID(
        pid="KNOCK_RETARD_CYL1",
        name="Knock Retard Cyl 1",
        description="Ignition timing retard due to knock - Cylinder 1",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3060,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),
    
    # Lambda/O2 Sensors
    N54PID(
        pid="LAMBDA_BANK1",
        name="Lambda Bank 1",
        description="Oxygen sensor reading - Bank 1",
        unit="λ",
        category=PIDCategory.EMISSIONS,
        uds_did=0x3070,
        decoder=decode_lambda,
        min_value=0.5,
        max_value=1.5
    ),
    
    N54PID(
        pid="LAMBDA_BANK2",
        name="Lambda Bank 2",
        description="Oxygen sensor reading - Bank 2",
        unit="λ",
        category=PIDCategory.EMISSIONS,
        uds_did=0x3071,
        decoder=decode_lambda,
        min_value=0.5,
        max_value=1.5
    ),

    # UDS mirror DIDs for core OBD-II engine sensors (from validate_all_dids.KNOWN_DIDS)
    N54PID(
        pid="UDS_ECT",
        name="Coolant Temperature (UDS)",
        description="Engine coolant temperature via UDS DID 0x0005",
        unit="°C",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_temp,
        min_value=-40,
        max_value=215,
        formula="A-40",
        uds_did=0x0005,
        verified=True,
    ),

    N54PID(
        pid="UDS_IAT",
        name="Intake Air Temperature (UDS)",
        description="Intake air temperature via UDS DID 0x000F",
        unit="°C",
        category=PIDCategory.SENSORS,
        decoder=decode_temp,
        min_value=-40,
        max_value=215,
        formula="A-40",
        uds_did=0x000F,
        verified=True,
    ),

    N54PID(
        pid="UDS_MAP",
        name="MAP (UDS)",
        description="Intake manifold absolute pressure via UDS DID 0x000B",
        unit="kPa",
        category=PIDCategory.BOOST_TURBO,
        decoder=decode_map_kpa,
        min_value=0,
        max_value=255,
        formula="A",
        uds_did=0x000B,
        verified=True,
    ),

    N54PID(
        pid="UDS_MAF",
        name="MAF (UDS)",
        description="Mass air flow via UDS DID 0x0010",
        unit="g/s",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_maf_gps,
        min_value=0,
        max_value=655.35,
        formula="((A*256)+B)/100",
        uds_did=0x0010,
        verified=True,
    ),

    N54PID(
        pid="UDS_THROTTLE",
        name="Throttle Position (UDS)",
        description="Throttle position via UDS DID 0x0011",
        unit="%",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255",
        uds_did=0x0011,
        verified=True,
    ),

    N54PID(
        pid="UDS_VEH_SPEED",
        name="Vehicle Speed (UDS)",
        description="Vehicle speed via UDS DID 0x000D",
        unit="km/h",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_speed,
        min_value=0,
        max_value=255,
        formula="A",
        uds_did=0x000D,
        verified=True,
    ),

    N54PID(
        pid="UDS_RPM",
        name="Engine RPM (UDS)",
        description="Engine speed via UDS DID 0x000C",
        unit="RPM",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_rpm,
        min_value=0,
        max_value=7500,
        formula="((A*256)+B)/4",
        uds_did=0x000C,
        verified=True,
    ),

    N54PID(
        pid="UDS_TIMING",
        name="Timing Advance (UDS)",
        description="Ignition timing advance via UDS DID 0x000E",
        unit="°",
        category=PIDCategory.IGNITION,
        decoder=decode_timing_advance,
        min_value=-64,
        max_value=63.5,
        formula="(A-128)/2",
        uds_did=0x000E,
        verified=True,
    ),

    N54PID(
        pid="UDS_FUEL_LEVEL",
        name="Fuel Tank Level (UDS)",
        description="Fuel tank level via UDS DID 0x002F",
        unit="%",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255",
        uds_did=0x002F,
        verified=True,
    ),

    N54PID(
        pid="UDS_DIST_MIL",
        name="Distance With MIL On (UDS)",
        description="Distance travelled with MIL on via UDS DID 0x0021",
        unit="km",
        category=PIDCategory.ENGINE_BASIC,
        decoder=decode_distance_km,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)",
        uds_did=0x0021,
        verified=True,
    ),

    # High-value engine/fuel DIDs from DID validation report
    N54PID(
        pid="UDS_FUEL_RAIL_PRESSURE",
        name="Fuel Rail Pressure (UDS)",
        description="Fuel rail absolute pressure via UDS DID 0x0022",
        unit="kPa",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_fuel_pressure,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)*10",
        uds_did=0x0022,
        verified=True,
    ),

    N54PID(
        pid="UDS_FUEL_RAIL_GAUGE",
        name="Fuel Rail Gauge Pressure (UDS)",
        description="Fuel rail gauge pressure via UDS DID 0x0023",
        unit="kPa",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=decode_fuel_pressure,
        min_value=0,
        max_value=None,
        formula="((A*256)+B)*10",
        uds_did=0x0023,
        verified=True,
    ),

    N54PID(
        pid="UDS_LAMBDA_B1",
        name="Lambda Bank 1 (UDS)",
        description="Lambda sensor Bank 1 via UDS DID 0x0024",
        unit="λ",
        category=PIDCategory.EMISSIONS,
        decoder=decode_lambda,
        min_value=0.5,
        max_value=1.5,
        uds_did=0x0024,
        verified=True,
    ),

    N54PID(
        pid="UDS_LAMBDA_B2",
        name="Lambda Bank 2 (UDS)",
        description="Lambda sensor Bank 2 via UDS DID 0x0025",
        unit="λ",
        category=PIDCategory.EMISSIONS,
        decoder=decode_lambda,
        min_value=0.5,
        max_value=1.5,
        uds_did=0x0025,
        verified=True,
    ),

    # High-value boost/VANOS control DIDs from DID validation report
    N54PID(
        pid="UDS_WGDC_TARGET",
        name="Wastegate Duty Cycle Target (UDS)",
        description="ECU wastegate duty cycle target via UDS DID 0x0041",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255",
        uds_did=0x0041,
        verified=True,
    ),

    N54PID(
        pid="UDS_BOOST_TARGET",
        name="Boost Pressure Target (UDS)",
        description="Boost pressure target via UDS DID 0x0042",
        unit="PSI",
        category=PIDCategory.BOOST_TURBO,
        decoder=decode_boost_pressure,
        min_value=0,
        max_value=25,
        formula="((A*256)+B)/100 * 14.5038",
        uds_did=0x0042,
        verified=True,
    ),

    N54PID(
        pid="UDS_VANOS_INTAKE_TARGET",
        name="VANOS Intake Cam Target (UDS)",
        description="Intake camshaft target position via UDS DID 0x0031",
        unit="°",
        category=PIDCategory.VANOS,
        decoder=decode_vanos_position,
        min_value=-64,
        max_value=63.5,
        formula="int16(A,B)/10",
        uds_did=0x0031,
        verified=True,
    ),

    N54PID(
        pid="UDS_VANOS_EXHAUST_TARGET",
        name="VANOS Exhaust Cam Target (UDS)",
        description="Exhaust camshaft target position via UDS DID 0x0033",
        unit="°",
        category=PIDCategory.VANOS,
        decoder=decode_vanos_position,
        min_value=-64,
        max_value=63.5,
        formula="int16(A,B)/10",
        uds_did=0x0033,
        verified=True,
    ),

    # O2 Sensor DIDs (validated from MHD scan)
    N54PID(
        pid="UDS_O2_B1S2",
        name="O2 Sensor Bank 1 Sensor 2 (UDS)",
        description="Post-cat O2 sensor Bank 1 Sensor 2 via UDS DID 0x0014",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=lambda data: round(data[0] / 200.0, 3) if data else 0.0,
        min_value=0,
        max_value=1.275,
        formula="A/200",
        uds_did=0x0014,
        verified=True,
    ),

    N54PID(
        pid="UDS_O2_B2S2",
        name="O2 Sensor Bank 2 Sensor 2 (UDS)",
        description="Post-cat O2 sensor Bank 2 Sensor 2 via UDS DID 0x0016",
        unit="V",
        category=PIDCategory.EMISSIONS,
        decoder=lambda data: round(data[0] / 200.0, 3) if data else 0.0,
        min_value=0,
        max_value=1.275,
        formula="A/200",
        uds_did=0x0016,
        verified=True,
    ),

    # Evaporative system
    N54PID(
        pid="UDS_EVAP_PURGE",
        name="Commanded Evaporative Purge (UDS)",
        description="Evap purge valve duty via UDS DID 0x002E",
        unit="%",
        category=PIDCategory.EMISSIONS,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255",
        uds_did=0x002E,
        verified=True,
    ),

    # N54 Injector system DIDs
    N54PID(
        pid="UDS_INJECTOR_CODES",
        name="Injector Correction Codes (UDS)",
        description="Individual injector correction codes via UDS DID 0x0600",
        unit="-",
        category=PIDCategory.FUEL_SYSTEM,
        decoder=lambda data: data.hex() if data else "",
        min_value=None,
        max_value=None,
        uds_did=0x0600,
        verified=True,
    ),

    N54PID(
        pid="UDS_ENGINE_RUNTIME",
        name="Engine Runtime / Injector Data (UDS)",
        description="Engine runtime hours and injector data via UDS DID 0x0610",
        unit="hrs",
        category=PIDCategory.ENGINE_BASIC,
        decoder=lambda data: ((data[0] << 8) | data[1]) if len(data) >= 2 else 0,
        min_value=0,
        max_value=None,
        uds_did=0x0610,
        verified=True,
    ),

    N54PID(
        pid="UDS_FLASH_COUNTER",
        name="Flash Counter (UDS)",
        description="Number of ECU flash cycles via UDS DID 0x0620",
        unit="-",
        category=PIDCategory.ENGINE_BASIC,
        decoder=lambda data: data[0] if data else 0,
        min_value=0,
        max_value=255,
        uds_did=0x0620,
        verified=True,
    ),

    # Per-cylinder knock retard (example DIDs; bench validation required)
    N54PID(
        pid="KNOCK_RETARD_CYL2",
        name="Knock Retard Cyl 2",
        description="Ignition timing retard due to knock - Cylinder 2",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3061,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL3",
        name="Knock Retard Cyl 3",
        description="Ignition timing retard due to knock - Cylinder 3",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3062,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL4",
        name="Knock Retard Cyl 4",
        description="Ignition timing retard due to knock - Cylinder 4",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3063,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL5",
        name="Knock Retard Cyl 5",
        description="Ignition timing retard due to knock - Cylinder 5",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3064,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL6",
        name="Knock Retard Cyl 6",
        description="Ignition timing retard due to knock - Cylinder 6",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3065,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    # ========================================================================
    # WGDC PID Controller Components (from MSD81BMWSpecifications.pdf)
    # These are live RAM values from the ATL Regulator (ATLREG) function
    # A2L addresses in 0xd000xxxx range are RAM addresses for CCP/XCP
    # ========================================================================
    
    N54PID(
        pid="WGDC_TOTAL",
        name="WGDC Total (Atlr)",
        description="Total wastegate duty cycle from controller output. "
                    "Sum of feedforward (Atlvst) + PID correction. "
                    "RAM address: 0xd00069e8",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069E8,  # Full RAM address for ReadMemoryByAddress
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        formula="A*100/255 (uint16 scaled)",
        verified=True,  # Verified from A2L file 80B37E0E.a2l
    ),
    
    N54PID(
        pid="WGDC_P_COMPONENT",
        name="WGDC P Component (Atlr_p)",
        description="Proportional component of WGDC PID controller. "
                    "Responds directly to boost error. "
                    "RAM address: 0xd00069fa",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069FA,
        decoder=decode_signed_percent,
        min_value=-100,
        max_value=100,
        formula="signed int16 to % (P gain contribution)",
        verified=True,
    ),
    
    N54PID(
        pid="WGDC_I_COMPONENT",
        name="WGDC I Component (Atlr_i)",
        description="Integral component of WGDC PID controller. "
                    "Accumulates boost error over time. Limited by K_ATLRI_MN/MX. "
                    "RAM address: 0xd00069ea",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069EA,
        decoder=decode_signed_percent,
        min_value=-100,
        max_value=100,
        formula="signed int16 to % (I gain contribution)",
        verified=True,
    ),
    
    N54PID(
        pid="WGDC_D_COMPONENT",
        name="WGDC D Component (Atlr_d)",
        description="Derivative component of WGDC PID controller. "
                    "Responds to rate of change of boost error. "
                    "RAM address: 0xd00069fe",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069FE,
        decoder=decode_signed_percent,
        min_value=-100,
        max_value=100,
        formula="signed int16 to % (D gain contribution)",
        verified=True,
    ),
    
    N54PID(
        pid="WGDC_PI_SUM",
        name="WGDC P+I Sum (Atlr_pi)",
        description="Sum of P and I components from WGDC controller. "
                    "RAM address: 0xd00069fc",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069FC,
        decoder=decode_signed_percent,
        min_value=-100,
        max_value=100,
        verified=True,
    ),
    
    N54PID(
        pid="WGDC_FEEDFORWARD",
        name="WGDC Feedforward (Atlvst)",
        description="Feedforward (pre-control) component of WGDC. "
                    "Comes from KF_ATLVST maps. Open-loop base value. "
                    "RAM address: 0xd00069e4",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069E4,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        verified=True,
    ),
    
    N54PID(
        pid="WGDC_NO_ADAPT",
        name="WGDC without Adaptation (Atlr_oad)",
        description="WGDC before adaptation factor applied. "
                    "RAM address: 0xd0007070",
        unit="%",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD0007070,
        decoder=decode_percent,
        min_value=0,
        max_value=100,
        verified=True,
    ),
    
    N54PID(
        pid="ATL_REGULATOR_STATUS",
        name="ATL Regulator Status (St_atlreg)",
        description="Status word for ATL (turbo) regulator. "
                    "Bit 0: WG control active. "
                    "RAM address: 0xd00069ee",
        unit="",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0xD00069EE,
        decoder=lambda d: d[0] if len(d) >= 1 else 0,
        min_value=0,
        max_value=255,
        verified=True,
    ),
    
    N54PID(
        pid="BOOST_DEVIATION",
        name="Boost Deviation (Pld_diff)",
        description="Difference between target and actual boost. "
                    "Positive = under-boosting, Negative = over-boosting. "
                    "RAM address in ATLSTAT function.",
        unit="hPa",
        category=PIDCategory.BOOST_TURBO,
        uds_did=0x6A10,  # Approximate - needs verification
        decoder=decode_signed_16bit,
        min_value=-2560,
        max_value=2560,
    ),

    # Per-cylinder knock retard (example DIDs; bench validation required)
    N54PID(
        pid="KNOCK_RETARD_CYL2",
        name="Knock Retard Cyl 2",
        description="Ignition timing retard due to knock - Cylinder 2",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3061,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL3",
        name="Knock Retard Cyl 3",
        description="Ignition timing retard due to knock - Cylinder 3",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3062,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL4",
        name="Knock Retard Cyl 4",
        description="Ignition timing retard due to knock - Cylinder 4",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3063,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL5",
        name="Knock Retard Cyl 5",
        description="Ignition timing retard due to knock - Cylinder 5",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3064,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),

    N54PID(
        pid="KNOCK_RETARD_CYL6",
        name="Knock Retard Cyl 6",
        description="Ignition timing retard due to knock - Cylinder 6",
        unit="°",
        category=PIDCategory.IGNITION,
        uds_did=0x3065,
        decoder=decode_timing_advance,
        min_value=-20,
        max_value=0
    ),
]


# ============================================================================
# PID LOOKUP AND HELPER FUNCTIONS
# ============================================================================

# Combined PID registry
ALL_PIDS = STANDARD_PIDS + N54_SPECIFIC_PIDS

# Quick lookup dictionaries
PID_BY_ID = {pid.pid: pid for pid in ALL_PIDS}
PID_BY_NAME = {pid.name: pid for pid in ALL_PIDS}
PID_BY_UDS_DID = {pid.uds_did: pid for pid in N54_SPECIFIC_PIDS if pid.uds_did}


def get_pid_by_id(pid_id: str) -> Optional[N54PID]:
    """Get PID definition by ID"""
    return PID_BY_ID.get(pid_id)


def get_pid_by_name(name: str) -> Optional[N54PID]:
    """Get PID definition by name (case-insensitive)"""
    for pid_name, pid in PID_BY_NAME.items():
        if pid_name.lower() == name.lower():
            return pid
    return None


def get_pid_by_uds_did(did: int) -> Optional[N54PID]:
    """Get PID definition by UDS DID"""
    return PID_BY_UDS_DID.get(did)


def get_pids_by_category(category: PIDCategory) -> list[N54PID]:
    """Get all PIDs in a category"""
    return [pid for pid in ALL_PIDS if pid.category == category]


def get_common_dashboard_pids() -> list[N54PID]:
    """Get common PIDs for dashboard display"""
    common_names = [
        "Engine RPM",
        "Vehicle Speed",
        "Coolant Temperature",
        "Actual Boost Pressure",
        "High Pressure Fuel",
        "Throttle Position",
        "Engine Load",
        "Intake VANOS Position",
        "Exhaust VANOS Position"
    ]
    return [PID_BY_NAME[name] for name in common_names if name in PID_BY_NAME]


def get_boost_monitoring_pids() -> list[N54PID]:
    """Get PIDs for boost/turbo monitoring"""
    return get_pids_by_category(PIDCategory.BOOST_TURBO)


def get_fuel_monitoring_pids() -> list[N54PID]:
    """Get PIDs for fuel system monitoring"""
    return get_pids_by_category(PIDCategory.FUEL_SYSTEM)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == '__main__':
    print("BMW N54 PID Database")
    print("=" * 80)
    
    print(f"\nTotal PIDs: {len(ALL_PIDS)}")
    print(f"  Standard OBD-II: {len(STANDARD_PIDS)}")
    print(f"  N54-Specific (UDS): {len(N54_SPECIFIC_PIDS)}")
    
    print("\nPIDs by Category:")
    for category in PIDCategory:
        pids = get_pids_by_category(category)
        print(f"  {category.value:20} - {len(pids)} PIDs")
    
    print("\nCommon Dashboard PIDs:")
    for pid in get_common_dashboard_pids():
        print(f"  {pid.name:30} | {pid.unit:8} | {pid.pid}")
    
    print("\nBoost Monitoring PIDs:")
    for pid in get_boost_monitoring_pids():
        print(f"  {pid.name:35} | {pid.unit:8} | UDS DID: 0x{pid.uds_did:04X}")
    
    print("\nTest Decoders:")
    # Test RPM decoder
    rpm_data = bytes([0x1A, 0xF0])  # Should be ~1724 RPM
    rpm_pid = get_pid_by_id("0C")
    print(f"  RPM: {rpm_pid.decode(rpm_data)} {rpm_pid.unit}")
    
    # Test boost decoder
    boost_data = bytes([0x64])  # 1.0 bar = ~14.5 PSI
    boost_pid = get_pid_by_id("BOOST_ACTUAL")
    print(f"  Boost: {boost_pid.decode(boost_data)} {boost_pid.unit}")
    
    # Test VANOS decoder
    vanos_data = bytes([0x90])  # Should be ~12 degrees
    vanos_pid = get_pid_by_id("VANOS_INTAKE_ACTUAL")
    print(f"  VANOS: {vanos_pid.decode(vanos_data)} {vanos_pid.unit}")
