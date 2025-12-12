"""
BMW DTC (Diagnostic Trouble Code) Database

Diagnostic Trouble Code database for BMW vehicles.
Includes OBD-II standard codes and BMW-specific codes with descriptions and common causes.
Expandable database - add more codes as discovered.

Created: November 3, 2025
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum


class DTCSystem(Enum):
    """System categories for DTCs"""
    POWERTRAIN = "P"  # Engine, transmission
    CHASSIS = "C"     # ABS, suspension, steering
    BODY = "B"        # Body control, lighting, HVAC
    NETWORK = "U"     # Communication, network
    

class DTCSeverity(Enum):
    """DTC severity levels"""
    CRITICAL = "Critical"  # Safety issue, drive carefully
    HIGH = "High"          # Performance issue, should fix soon
    MEDIUM = "Medium"      # Comfort/convenience issue
    LOW = "Low"            # Information, minor issue


@dataclass
class DTC:
    """
    Diagnostic Trouble Code
    
    Attributes:
        code: DTC code (e.g., 'P0300', '2A88')
        description: Short description
        details: Detailed explanation
        system: System category (P/C/B/U)
        severity: Severity level
        common_causes: List of common root causes
        modules: List of modules that can report this code
    """
    code: str
    description: str
    details: str
    system: DTCSystem
    severity: DTCSeverity
    common_causes: List[str]
    modules: List[str]
    
    def __repr__(self) -> str:
        return f"DTC({self.code}: {self.description})"


# BMW DTC Database
BMW_DTCS: Dict[str, DTC] = {
    # ========== ENGINE / DME ==========
    
    # Misfires
    "P0300": DTC(
        code="P0300",
        description="Random/Multiple Cylinder Misfire Detected",
        details="Multiple cylinders misfiring or random misfire pattern",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Bad spark plugs",
            "Faulty ignition coils",
            "Low fuel pressure",
            "Vacuum leaks",
            "Carbon buildup on valves"
        ],
        modules=["DME"]
    ),
    
    "P0301": DTC(
        code="P0301",
        description="Cylinder 1 Misfire Detected",
        details="Misfire detected specifically in cylinder 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=["Bad spark plug #1", "Faulty ignition coil #1", "Injector #1 issue"],
        modules=["DME"]
    ),
    
    "P0302": DTC(
        code="P0302",
        description="Cylinder 2 Misfire Detected",
        details="Misfire detected specifically in cylinder 2",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=["Bad spark plug #2", "Faulty ignition coil #2", "Injector #2 issue"],
        modules=["DME"]
    ),
    
    "P0303": DTC(
        code="P0303",
        description="Cylinder 3 Misfire Detected",
        details="Misfire detected specifically in cylinder 3",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=["Bad spark plug #3", "Faulty ignition coil #3", "Injector #3 issue"],
        modules=["DME"]
    ),
    
    "P0304": DTC(
        code="P0304",
        description="Cylinder 4 Misfire Detected",
        details="Misfire detected specifically in cylinder 4",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=["Bad spark plug #4", "Faulty ignition coil #4", "Injector #4 issue"],
        modules=["DME"]
    ),
    
    "P0305": DTC(
        code="P0305",
        description="Cylinder 5 Misfire Detected",
        details="Misfire detected specifically in cylinder 5",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=["Bad spark plug #5", "Faulty ignition coil #5", "Injector #5 issue"],
        modules=["DME"]
    ),
    
    "P0306": DTC(
        code="P0306",
        description="Cylinder 6 Misfire Detected",
        details="Misfire detected specifically in cylinder 6",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=["Bad spark plug #6", "Faulty ignition coil #6", "Injector #6 issue"],
        modules=["DME"]
    ),
    
    # Fuel System
    "P0087": DTC(
        code="P0087",
        description="Fuel Rail Pressure Too Low",
        details="Low fuel pressure detected",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "Failing HPFP (High Pressure Fuel Pump)",
            "LPFP (Low Pressure Fuel Pump) weak",
            "Fuel pressure regulator failure",
            "Fuel filter clogged"
        ],
        modules=["DME"]
    ),
    
    "P0088": DTC(
        code="P0088",
        description="Fuel Rail Pressure Too High",
        details="Excessive fuel pressure detected",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Stuck fuel pressure regulator",
            "HPFP overpressure",
            "Fuel pressure sensor fault"
        ],
        modules=["DME"]
    ),
    
    "P1080": DTC(
        code="P1080",
        description="HPFP (High Pressure Fuel Pump) Performance",
        details="HPFP not meeting pressure targets",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "HPFP failure",
            "HPFP seal leaking",
            "Low voltage to HPFP"
        ],
        modules=["DME"]
    ),
    
    # Turbo / Boost
    "P0234": DTC(
        code="P0234",
        description="Turbocharger Overboost Condition",
        details="Boost pressure exceeded safe limit",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "Stuck wastegate",
            "Boost leak",
            "Failed N75 valve",
            "Tune with excessive boost",
            "WGDC solenoid failure"
        ],
        modules=["DME"]
    ),
    
    "P0299": DTC(
        code="P0299",
        description="Turbocharger Underboost Condition",
        details="Boost pressure below target",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Boost leak (charge pipes, intercooler)",
            "Wastegate rattle/failure",
            "Turbo failure",
            "Vacuum leak",
            "WGDC solenoid issue"
        ],
        modules=["DME"]
    ),
    
    "P0016": DTC(
        code="P0016",
        description="Crankshaft/Camshaft Position Correlation",
        details="Timing mismatch between crank and cam sensors (VANOS issue)",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "VANOS solenoid failure",
            "Timing chain stretch",
            "Low oil pressure",
            "Oil screen clogged",
            "VANOS oil line leak"
        ],
        modules=["DME"]
    ),
    
    # VANOS
    "P1014": DTC(
        code="P1014",
        description="Intake VANOS Position Sensor Fault",
        details="Intake camshaft position sensor issue",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "VANOS solenoid failure",
            "Sensor wiring issue",
            "Oil pressure low",
            "VANOS unit mechanical failure"
        ],
        modules=["DME"]
    ),
    
    "P1017": DTC(
        code="P1017",
        description="Exhaust VANOS Position Sensor Fault",
        details="Exhaust camshaft position sensor issue",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "VANOS solenoid failure",
            "Sensor wiring issue",
            "Oil pressure low",
            "VANOS unit mechanical failure"
        ],
        modules=["DME"]
    ),
    
    # Oxygen Sensors
    "P0171": DTC(
        code="P0171",
        description="System Too Lean (Bank 1)",
        details="Fuel mixture too lean on bank 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Vacuum leak",
            "MAF sensor dirty/faulty",
            "Injector clog",
            "Fuel pressure low",
            "O2 sensor failure"
        ],
        modules=["DME"]
    ),
    
    "P0174": DTC(
        code="P0174",
        description="System Too Lean (Bank 2)",
        details="Fuel mixture too lean on bank 2",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Vacuum leak",
            "MAF sensor dirty/faulty",
            "Injector clog",
            "Fuel pressure low",
            "O2 sensor failure"
        ],
        modules=["DME"]
    ),
    
    "P0172": DTC(
        code="P0172",
        description="System Too Rich (Bank 1)",
        details="Fuel mixture too rich on bank 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Leaking injectors",
            "MAF sensor faulty",
            "HPFP overpressure",
            "O2 sensor failure",
            "Air filter dirty"
        ],
        modules=["DME"]
    ),
    
    "P0175": DTC(
        code="P0175",
        description="System Too Rich (Bank 2)",
        details="Fuel mixture too rich on bank 2",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Leaking injectors",
            "MAF sensor faulty",
            "HPFP overpressure",
            "O2 sensor failure",
            "Air filter dirty"
        ],
        modules=["DME"]
    ),
    
    # ========== TRANSMISSION / EGS ==========
    
    "P0700": DTC(
        code="P0700",
        description="Transmission Control System Malfunction",
        details="General transmission fault, check EGS for specific codes",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Transmission fluid low/old",
            "Mechatronic failure",
            "Solenoid failure",
            "Check EGS module for specific fault"
        ],
        modules=["EGS", "DME"]
    ),
    
    "P0715": DTC(
        code="P0715",
        description="Input/Turbine Speed Sensor Circuit",
        details="Transmission input speed sensor fault",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Speed sensor failure",
            "Wiring harness damage",
            "Mechatronic unit fault"
        ],
        modules=["EGS"]
    ),
    
    # ========== ABS / DSC ==========
    
    "C1200": DTC(
        code="C1200",
        description="ABS Control Unit Internal Fault",
        details="Internal fault in ABS module",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "ABS module failure",
            "Voltage issue",
            "Module needs replacement"
        ],
        modules=["ABS/DSC"]
    ),
    
    "C1241": DTC(
        code="C1241",
        description="Wheel Speed Sensor Fault",
        details="One or more wheel speed sensors not reading correctly",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Wheel speed sensor failure",
            "Sensor wiring damaged",
            "Tone ring damaged",
            "Hub bearing failure"
        ],
        modules=["ABS/DSC"]
    ),
    
    # ========== BMW-SPECIFIC CODES ==========
    
    "2A88": DTC(
        code="2A88",
        description="VANOS System Fault (DME internal)",
        details="Internal DME error, may require replacement or reset",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "DME software corruption",
            "Failed flash attempt",
            "Voltage spike damage",
            "DME may need replacement"
        ],
        modules=["DME"]
    ),
    
    "2A87": DTC(
        code="2A87",
        description="VANOS, DME Programming Fault",
        details="DME programming/calibration issue",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Incomplete flash",
            "Corrupted calibration",
            "Wrong software version",
            "Need to reflash DME"
        ],
        modules=["DME"]
    ),
    
    # ========== ADDITIONAL OBD CODES ==========
    
    "P0011": DTC(
        code="P0011",
        description="Camshaft Position Timing Over-Advanced (Intake)",
        details="Intake camshaft timing is too far advanced",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "VANOS solenoid failure",
            "Oil viscosity wrong",
            "Timing chain stretch",
            "Sensor wiring issue"
        ],
        modules=["DME"]
    ),
    
    "P0014": DTC(
        code="P0014",
        description="Camshaft Position Timing Over-Retarded (Exhaust)",
        details="Exhaust camshaft timing is too far retarded",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "VANOS solenoid failure",
            "Low oil pressure",
            "Timing chain stretch",
            "Sensor wiring issue"
        ],
        modules=["DME"]
    ),
    
    "P0101": DTC(
        code="P0101",
        description="Mass Air Flow (MAF) Sensor Range/Performance",
        details="MAF sensor reading inconsistent with engine operation",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "MAF sensor dirty or contaminated",
            "Air leak in intake",
            "MAF sensor failure",
            "Engine air filter clogged",
            "Vacuum leak"
        ],
        modules=["DME"]
    ),
    
    "P0102": DTC(
        code="P0102",
        description="Mass Air Flow (MAF) Sensor Low",
        details="MAF sensor signal below normal range",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "MAF sensor failure",
            "Air intake leak",
            "Damaged air filter housing",
            "Vacuum leak"
        ],
        modules=["DME"]
    ),
    
    "P0103": DTC(
        code="P0103",
        description="Mass Air Flow (MAF) Sensor High",
        details="MAF sensor signal above normal range",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "MAF sensor failure",
            "Intake air leak",
            "Air filter removed",
            "Failed ignition coil"
        ],
        modules=["DME"]
    ),
    
    "P0112": DTC(
        code="P0112",
        description="Intake Air Temperature (IAT) Sensor Low",
        details="IAT sensor reading below normal range",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "IAT sensor failure",
            "Wiring short to ground",
            "Sensor connector issue",
            "Air intake leak"
        ],
        modules=["DME"]
    ),
    
    "P0113": DTC(
        code="P0113",
        description="Intake Air Temperature (IAT) Sensor High",
        details="IAT sensor reading above normal range",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "IAT sensor failure",
            "Open circuit in sensor wiring",
            "Sensor connector loose",
            "Wiring open to sensor"
        ],
        modules=["DME"]
    ),
    
    "P0117": DTC(
        code="P0117",
        description="Engine Coolant Temperature (ECT) Sensor Low",
        details="ECT sensor reading below normal range",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "ECT sensor failure",
            "Wiring shorted to ground",
            "Sensor connector issue",
            "Failed water pump"
        ],
        modules=["DME"]
    ),
    
    "P0118": DTC(
        code="P0118",
        description="Engine Coolant Temperature (ECT) Sensor High",
        details="ECT sensor reading above normal range",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "ECT sensor failure",
            "Open circuit in wiring",
            "Sensor connector loose",
            "Engine overheating"
        ],
        modules=["DME"]
    ),
    
    "P0128": DTC(
        code="P0128",
        description="Coolant Thermostat (Coolant Temp Regulation) Performance",
        details="Engine coolant temperature not reaching normal operating temperature",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Faulty thermostat",
            "Failed water pump",
            "Cooling fan stuck on",
            "Low coolant level",
            "ECT sensor failure"
        ],
        modules=["DME"]
    ),
    
    "P0130": DTC(
        code="P0130",
        description="Oxygen Sensor Circuit (Bank 1)",
        details="O2 sensor circuit malfunction on bank 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "O2 sensor failure",
            "Wiring damaged or loose",
            "Air leak in exhaust",
            "Failed catalytic converter"
        ],
        modules=["DME"]
    ),
    
    "P0133": DTC(
        code="P0133",
        description="Oxygen Sensor Response Slow (Bank 1)",
        details="O2 sensor not responding fast enough on bank 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "O2 sensor aging",
            "Contaminated O2 sensor",
            "Exhaust leak",
            "Engine running too cold"
        ],
        modules=["DME"]
    ),
    
    "P0161": DTC(
        code="P0161",
        description="O2 Sensor Heater Circuit Bank 2",
        details="Oxygen sensor heater malfunction on bank 2",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "O2 sensor heater failure",
            "Wiring open or shorted",
            "Fuse blown",
            "ECU issue"
        ],
        modules=["DME"]
    ),
    
    "P0200": DTC(
        code="P0200",
        description="Injector Circuit Malfunction",
        details="General fuel injector circuit problem",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Failed fuel injector",
            "Injector wiring damaged",
            "Fuel rail pressure issue",
            "ECU control circuit fault"
        ],
        modules=["DME"]
    ),
    
    "P0261": DTC(
        code="P0261",
        description="Cylinder 1 Injector Circuit Low",
        details="Fuel injector circuit voltage low on cylinder 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Injector shorted to ground",
            "Wiring shorted",
            "Injector failure",
            "ECU output circuit problem"
        ],
        modules=["DME"]
    ),
    
    "P0262": DTC(
        code="P0262",
        description="Cylinder 1 Injector Circuit High",
        details="Fuel injector circuit voltage high on cylinder 1",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Injector connector loose",
            "Open wiring circuit",
            "Injector failure",
            "ECU output open circuit"
        ],
        modules=["DME"]
    ),
    
    "P0335": DTC(
        code="P0335",
        description="Crankshaft Position Sensor Circuit",
        details="Crankshaft position sensor malfunction",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "Crankshaft sensor failure",
            "Sensor wiring damaged",
            "Sensor connector loose",
            "Reluctor ring damaged"
        ],
        modules=["DME"]
    ),
    
    "P0340": DTC(
        code="P0340",
        description="Camshaft Position Sensor Circuit",
        details="Camshaft position sensor malfunction",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "Camshaft sensor failure",
            "Sensor wiring damaged",
            "Sensor connector loose",
            "Reluctor ring damaged"
        ],
        modules=["DME"]
    ),
    
    "P0401": DTC(
        code="P0401",
        description="EGR (Exhaust Gas Recirculation) Flow Insufficient",
        details="EGR system flow below target",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "EGR valve stuck closed",
            "EGR passage clogged",
            "Vacuum leak",
            "DPNR valve failure"
        ],
        modules=["DME"]
    ),
    
    "P0441": DTC(
        code="P0441",
        description="Evaporative Emission Control System Flow",
        details="EVAP system flow malfunction",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.LOW,
        common_causes=[
            "Purge solenoid failure",
            "Charcoal canister clogged",
            "Hose disconnect/leak",
            "Valve stuck"
        ],
        modules=["DME"]
    ),
    
    "P0500": DTC(
        code="P0500",
        description="Vehicle Speed Sensor Malfunction",
        details="Vehicle speed sensor not reading correctly",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Speed sensor failure",
            "Wheel speed sensor issue",
            "Wiring open or shorted",
            "ABS module problem"
        ],
        modules=["DME", "ABS/DSC"]
    ),
    
    "P0505": DTC(
        code="P0505",
        description="Idle Air Control System Malfunction",
        details="Engine idle speed not controlled properly",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.MEDIUM,
        common_causes=[
            "Vacuum leak",
            "IAC valve stuck",
            "MAF sensor dirty",
            "Air intake leak",
            "Engine carbon buildup"
        ],
        modules=["DME"]
    ),
    
    "P0606": DTC(
        code="P0606",
        description="PCM/ECM Processor Fault",
        details="Internal ECU processor error",
        system=DTCSystem.POWERTRAIN,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "ECU software corruption",
            "ECU hardware failure",
            "Power supply issue",
            "Reflash required"
        ],
        modules=["DME"]
    ),
    
    "C0035": DTC(
        code="C0035",
        description="ABS Wheel Speed Sensor Circuit Range/Performance",
        details="ABS wheel speed sensor inconsistent",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Wheel speed sensor failure",
            "Sensor wiring damaged",
            "Reluctor ring damaged",
            "Hub bearing failure"
        ],
        modules=["ABS/DSC"]
    ),
    
    "C0050": DTC(
        code="C0050",
        description="ABS Hydraulic Unit Solenoid Valve Fault",
        details="ABS pump/solenoid valve malfunction",
        system=DTCSystem.CHASSIS,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "Solenoid valve failure",
            "ABS pump failure",
            "Hydraulic pressure loss",
            "ABS control module fault"
        ],
        modules=["ABS/DSC"]
    ),
    
    "U1000": DTC(
        code="U1000",
        description="CAN Communication Bus Off",
        details="Vehicle CAN bus communication failure",
        system=DTCSystem.NETWORK,
        severity=DTCSeverity.CRITICAL,
        common_causes=[
            "CAN bus shorted",
            "Module communication failure",
            "Wiring damaged",
            "ECU connection issue"
        ],
        modules=["Multiple"]
    ),
    
    "U1001": DTC(
        code="U1001",
        description="CAN Communication Bus Error",
        details="CAN bus error detected",
        system=DTCSystem.NETWORK,
        severity=DTCSeverity.HIGH,
        common_causes=[
            "Module communication issue",
            "Wiring harness problem",
            "ECU connector loose",
            "Module software mismatch"
        ],
        modules=["Multiple"]
    ),
}


def lookup_dtc(code: str) -> Optional[DTC]:
    """
    Look up DTC by code
    
    Args:
        code: DTC code (e.g., 'P0300', '2A88')
    
    Returns:
        DTC object if found, None otherwise
    """
    code = code.strip()
    return BMW_DTCS.get(code)


def search_dtcs(keyword: str) -> List[DTC]:
    """
    Search DTCs by keyword in description or details
    
    Args:
        keyword: Search term (case-insensitive)
    
    Returns:
        List of matching DTCs
    """
    keyword = keyword.lower()
    results = []
    
    for dtc in BMW_DTCS.values():
        if (keyword in dtc.description.lower() or 
            keyword in dtc.details.lower() or
            any(keyword in cause.lower() for cause in dtc.common_causes)):
            results.append(dtc)
    
    return results


def get_dtcs_by_system(system: DTCSystem) -> List[DTC]:
    """Get all DTCs for a specific system"""
    return [dtc for dtc in BMW_DTCS.values() if dtc.system == system]


def get_dtcs_by_module(module: str) -> List[DTC]:
    """Get all DTCs that can be reported by a specific module"""
    return [dtc for dtc in BMW_DTCS.values() if module in dtc.modules]


def get_critical_dtcs() -> List[DTC]:
    """Get all critical severity DTCs"""
    return [dtc for dtc in BMW_DTCS.values() if dtc.severity == DTCSeverity.CRITICAL]


if __name__ == "__main__":
    print("=" * 80)
    print("BMW DTC Database")
    print("=" * 80)
    print(f"\nTotal DTCs in database: {len(BMW_DTCS)}\n")
    
    # Show by system
    for system in DTCSystem:
        dtcs = get_dtcs_by_system(system)
        if dtcs:
            print(f"\n{system.value} - {system.name} Codes ({len(dtcs)}):")
            print("-" * 80)
            for dtc in sorted(dtcs, key=lambda x: x.code):
                print(f"{dtc.code:6} | {dtc.description}")
    
    # Show critical
    print(f"\nCRITICAL DTCs ({len(get_critical_dtcs())}):")
    print("-" * 80)
    for dtc in get_critical_dtcs():
        print(f"{dtc.code:6} | {dtc.description}")
    
    # Example searches
    print("\n\nExample Searches:")
    print("-" * 80)
    print("\nMisfire codes:")
    for dtc in search_dtcs("misfire"):
        print(f"  {dtc.code}: {dtc.description}")
    
    print("\nFuel codes:")
    for dtc in search_dtcs("fuel"):
        print(f"  {dtc.code}: {dtc.description}")
    
    print("\nVANOS codes:")
    for dtc in search_dtcs("vanos"):
        print(f"  {dtc.code}: {dtc.description}")
