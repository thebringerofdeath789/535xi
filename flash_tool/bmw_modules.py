"""
BMW Module Registry - E60/N54 Diagnostic Modules

Defines BMW vehicle modules with their addresses, protocols, and capabilities.
Used for multi-module scanning and diagnostics.

Created: November 3, 2025
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class Protocol(Enum):
    """Communication protocol for module"""
    UDS_CAN = "UDS (CAN)"
    KWP2000_KLINE = "KWP2000 (K-line)"
    BOTH = "UDS + KWP2000"


class ModuleCapability(Enum):
    """Capabilities supported by module"""
    DTC_READ = "DTC Reading"
    DTC_CLEAR = "DTC Clearing"
    LIVE_DATA = "Live Data"
    ADAPTATIONS = "Adaptations"
    CODING = "Coding"
    FLASH = "Flash Programming"
    SERVICE_RESET = "Service Reset"
    FREEZE_FRAME = "Freeze Frame"


@dataclass
class BMWModule:
    """
    Represents a BMW vehicle module
    
    Attributes:
        name: Full module name
        abbreviation: Short module ID (e.g., DME, EGS)
        can_id: CAN bus ID (None if not on CAN)
        kline_address: K-line address (None if not on K-line)
        protocol: Communication protocol
        capabilities: List of supported functions
        description: Brief module description
        critical: Whether module is safety-critical
    """
    name: str
    abbreviation: str
    can_id: Optional[int]
    kline_address: Optional[int]
    protocol: Protocol
    capabilities: List[ModuleCapability]
    description: str
    critical: bool = False
    
    @property
    def can_request_id(self) -> Optional[int]:
        """Calculate CAN request ID (0x600 + module_id)"""
        if self.can_id is not None:
            return 0x600 + self.can_id
        return None
    
    @property
    def can_response_id(self) -> Optional[int]:
        """Calculate CAN response ID (request_id + 0x08)"""
        if self.can_request_id is not None:
            return self.can_request_id + 0x08
        return None
    
    def __repr__(self) -> str:
        return f"BMWModule({self.abbreviation}, {self.protocol.value})"


# E60/N54 Module Definitions
E60_N54_MODULES = [
    # Primary Engine/Transmission Modules
    BMWModule(
        name="Digital Motor Electronics",
        abbreviation="DME",
        can_id=0x12,
        kline_address=0x12,
        protocol=Protocol.BOTH,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.LIVE_DATA,
            ModuleCapability.ADAPTATIONS,
            ModuleCapability.FLASH,
            ModuleCapability.FREEZE_FRAME,
            ModuleCapability.CODING,
        ],
        description="N54 Engine Control (MSD80/MSD81)",
        critical=True
    ),
    
    BMWModule(
        name="Electronic Transmission Control",
        abbreviation="EGS",
        can_id=0x13,
        kline_address=0x18,
        protocol=Protocol.BOTH,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.LIVE_DATA,
            ModuleCapability.ADAPTATIONS,
        ],
        description="Automatic Transmission Control",
        critical=True
    ),
    
    # Safety Systems
    BMWModule(
        name="Anti-lock Braking System / Dynamic Stability Control",
        abbreviation="ABS/DSC",
        can_id=0x34,
        kline_address=0x34,
        protocol=Protocol.BOTH,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.LIVE_DATA,
        ],
        description="Brake and Stability Control",
        critical=True
    ),
    
    BMWModule(
        name="Supplemental Restraint System",
        abbreviation="SRS",
        can_id=0x20,
        kline_address=0x20,
        protocol=Protocol.BOTH,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
        ],
        description="Airbag System",
        critical=True
    ),
    
    # Comfort/Convenience Modules
    BMWModule(
        name="Instrument Cluster",
        abbreviation="KOMBI",
        can_id=0x80,
        kline_address=0xF6,
        protocol=Protocol.BOTH,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.SERVICE_RESET,
            ModuleCapability.CODING,
        ],
        description="Dashboard/Instrument Cluster (CBS resets)",
        critical=False
    ),
    
    BMWModule(
        name="Car Access System",
        abbreviation="CAS",
        can_id=0x00,
        kline_address=0xE0,
        protocol=Protocol.BOTH,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.CODING,
        ],
        description="Central Locking/Immobilizer",
        critical=True
    ),
    
    BMWModule(
        name="Footwell Module",
        abbreviation="FRM",
        can_id=0x08,
        kline_address=None,
        protocol=Protocol.UDS_CAN,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.SERVICE_RESET,
            ModuleCapability.CODING,
        ],
        description="Lighting Control (DRL coding)",
        critical=False
    ),
    
    BMWModule(
        name="Intelligent Battery Sensor",
        abbreviation="IBS",
        can_id=None,
        kline_address=0x44,
        protocol=Protocol.KWP2000_KLINE,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
            ModuleCapability.LIVE_DATA,
            ModuleCapability.SERVICE_RESET,
        ],
        description="Battery Management (registration)",
        critical=False
    ),
    
    # Additional Comfort Systems
    BMWModule(
        name="Integrated Heating/Air Conditioning",
        abbreviation="IHKA",
        can_id=0x5B,
        kline_address=None,
        protocol=Protocol.UDS_CAN,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
        ],
        description="Climate Control",
        critical=False
    ),
    
    BMWModule(
        name="Park Distance Control",
        abbreviation="PDC",
        can_id=0x60,
        kline_address=None,
        protocol=Protocol.UDS_CAN,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
        ],
        description="Parking Sensors",
        critical=False
    ),
    
    BMWModule(
        name="Rain/Light Sensor",
        abbreviation="RLS",
        can_id=0x70,
        kline_address=None,
        protocol=Protocol.UDS_CAN,
        capabilities=[
            ModuleCapability.DTC_READ,
            ModuleCapability.DTC_CLEAR,
        ],
        description="Auto Lights/Wipers",
        critical=False
    ),
]


def get_module_by_abbreviation(abbreviation: str) -> Optional[BMWModule]:
    """
    Get module by abbreviation (e.g., 'DME', 'EGS')
    
    Args:
        abbreviation: Module abbreviation (case-insensitive)
    
    Returns:
        BMWModule if found, None otherwise
    """
    abbreviation = abbreviation.upper()
    for module in E60_N54_MODULES:
        if module.abbreviation == abbreviation:
            return module
    return None


def get_module_by_can_id(can_id: int) -> Optional[BMWModule]:
    """
    Get module by CAN ID
    
    Args:
        can_id: CAN bus ID (e.g., 0x12 for DME)
    
    Returns:
        BMWModule if found, None otherwise
    """
    for module in E60_N54_MODULES:
        if module.can_id == can_id:
            return module
    return None


def get_module_by_kline_address(address: int) -> Optional[BMWModule]:
    """
    Get module by K-line address
    
    Args:
        address: K-line address (e.g., 0xF6 for KOMBI)
    
    Returns:
        BMWModule if found, None otherwise
    """
    for module in E60_N54_MODULES:
        if module.kline_address == address:
            return module
    return None


def get_can_modules() -> List[BMWModule]:
    """Get all modules accessible via CAN bus"""
    return [m for m in E60_N54_MODULES if m.can_id is not None]


def get_kline_modules() -> List[BMWModule]:
    """Get all modules accessible via K-line"""
    return [m for m in E60_N54_MODULES if m.kline_address is not None]


def get_modules_with_capability(capability: ModuleCapability) -> List[BMWModule]:
    """
    Get all modules that support a specific capability
    
    Args:
        capability: Capability to search for
    
    Returns:
        List of modules supporting the capability
    """
    return [m for m in E60_N54_MODULES if capability in m.capabilities]


def get_critical_modules() -> List[BMWModule]:
    """Get all safety-critical modules"""
    return [m for m in E60_N54_MODULES if m.critical]


# Quick reference dictionaries
MODULE_NAMES = {m.abbreviation: m.name for m in E60_N54_MODULES}
CAN_IDS = {m.abbreviation: m.can_id for m in E60_N54_MODULES if m.can_id is not None}
KLINE_ADDRESSES = {m.abbreviation: m.kline_address for m in E60_N54_MODULES if m.kline_address is not None}
