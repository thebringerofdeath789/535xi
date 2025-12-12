#!/usr/bin/env python3
"""
BMW N54 COM Port Scanner - K+DCAN Cable Hardware Detection
===========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Hardware detection module for K+DCAN and PCAN USB interfaces.
    Enumerates COM ports, identifies FTDI-based cables, and manages
    port preferences with persistent configuration storage.

Features:
    - Auto-detect FTDI-based K+DCAN cables (VID: 0x0403)
    - Interactive port selection with validation
    - Save/load port preferences (JSON config)
    - Connection state tracking

Classes:
    None (functional module)

Functions:
    scan_com_ports() -> List[serial.tools.list_ports.ListPortInfo]
    identify_kdcan_ports(ports: List) -> List[Dict[str, Any]]
    scan_and_display() -> List[Dict[str, Any]]
    select_port_interactive() -> Optional[str]
    save_port_preference(port: str) -> bool
    load_port_preference() -> Optional[str]
    validate_port(port: str) -> bool

Variables (Module-level):
    FTDI_VID: int = 0x0403 - FTDI Vendor ID
    FTDI_PID_FT232: int = 0x6001 - FT232R/RL Product ID
    FTDI_PID_FT232H: int = 0x6014 - FT232H Product ID
    CONFIG_DIR: Path - Configuration directory path
    PORT_CONFIG_FILE: Path - Port preferences JSON file
"""

import serial
import serial.tools.list_ports
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any


# FTDI USB-to-Serial chip identifiers (used in K+DCAN cables)
FTDI_VID = 0x0403  # FTDI Vendor ID
FTDI_PID_FT232 = 0x6001  # FT232R/FT232RL Product ID (common in K+DCAN)
FTDI_PID_FT232H = 0x6014  # FT232H Product ID (alternative)

# Configuration file path
CONFIG_DIR = Path(__file__).parent.parent / "config"
PORT_CONFIG_FILE = CONFIG_DIR / "port_preferences.json"


def scan_com_ports() -> List[Any]:
    """
    Scan system for all available COM ports.
    
    Returns:
        List of ListPortInfo objects containing port details
        
    Example:
        >>> ports = scan_com_ports()
        >>> for port in ports:
        ...     print(f"{port.device}: {port.description}")
    """
    try:
        ports = serial.tools.list_ports.comports()
        return sorted(ports, key=lambda p: p.device)
    except Exception as e:
        print(f"Error scanning COM ports: {e}")
        return []


def get_port_details(port: Any) -> Dict[str, str]:
    """
    Extract detailed information from a COM port.
    
    Args:
        port: ListPortInfo object from pyserial
        
    Returns:
        Dictionary with port details (device, description, VID, PID, etc.)
    """
    return {
        "device": port.device,
        "description": port.description or "Unknown",
        "manufacturer": port.manufacturer or "Unknown",
        "vid": f"0x{port.vid:04X}" if port.vid else "N/A",
        "pid": f"0x{port.pid:04X}" if port.pid else "N/A",
        "serial_number": port.serial_number or "N/A",
        "location": port.location or "N/A"
    }


def detect_kdcan_cable(ports: List[Any]) -> List[Tuple[Any, str]]:
    """
    Identify K+DCAN cables from list of COM ports.
    
    K+DCAN cables typically use FTDI FT232RL chips.
    This function looks for FTDI VID/PID combinations.
    
    Args:
        ports: List of available COM ports
        
    Returns:
        List of tuples: (port_info, detection_reason)
        
    Example:
        >>> ports = scan_com_ports()
        >>> kdcan_ports = detect_kdcan_cable(ports)
        >>> if kdcan_ports:
        ...     print(f"Found K+DCAN on {kdcan_ports[0][0].device}")
    """
    candidates = []
    
    for port in ports:
        # Check for FTDI chips (requires VID/PID)
        if port.vid is not None and port.pid is not None:
            if port.vid == FTDI_VID:
                if port.pid == FTDI_PID_FT232:
                    reason = "FTDI FT232R/RL chip (typical K+DCAN)"
                    candidates.append((port, reason))
                elif port.pid == FTDI_PID_FT232H:
                    reason = "FTDI FT232H chip (possible K+DCAN)"
                    candidates.append((port, reason))
                else:
                    reason = f"FTDI chip (VID: 0x{port.vid:04X}, PID: 0x{port.pid:04X})"
                    candidates.append((port, reason))
        
        # Also check for common K+DCAN keywords in description (works without VID/PID)
        desc_lower = port.description.lower() if port.description else ""
        if any(keyword in desc_lower for keyword in ["kdcan", "k+dcan", "k-line", "bmw"]):
            reason = f"Description contains K+DCAN keyword: {port.description}"
            # Avoid duplicates
            if not any(p[0].device == port.device for p in candidates):
                candidates.append((port, reason))
    
    return candidates


def test_port_connection(port_name: str, baudrate: int = 9600, timeout: float = 1.0) -> Tuple[bool, str]:
    """
    Test if a COM port can be opened successfully.
    
    Args:
        port_name: COM port name (e.g., "COM3")
        baudrate: Baud rate for testing (default: 9600)
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (success: bool, message: str)
        
    Example:
        >>> success, msg = test_port_connection("COM3")
        >>> if success:
        ...     print(f"Port is accessible: {msg}")
    """
    try:
        with serial.Serial(port_name, baudrate=baudrate, timeout=timeout) as ser:
            if ser.is_open:
                return True, f"Port {port_name} opened successfully"
            else:
                return False, f"Port {port_name} failed to open"
    except serial.SerialException as e:
        return False, f"SerialException: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def select_port_interactive(ports: List[Any]) -> Optional[str]:
    """
    Present numbered list of COM ports for user selection.
    
    Args:
        ports: List of available COM ports
        
    Returns:
        Selected port name (e.g., "COM3") or None if cancelled
        
    Example:
        >>> ports = scan_com_ports()
        >>> selected = select_port_interactive(ports)
        >>> if selected:
        ...     print(f"User selected: {selected}")
    """
    if not ports:
        print("No COM ports available.")
        return None
    
    # Detect K+DCAN candidates
    kdcan_candidates = detect_kdcan_cable(ports)
    kdcan_devices = {p[0].device for p in kdcan_candidates}
    
    print("\n=== Available COM Ports ===")
    print(f"{'#':<3} {'Port':<8} {'Description':<30} {'VID:PID':<12} {'Status'}")
    print("="*80)
    
    for idx, port in enumerate(ports, 1):
        details = get_port_details(port)
        vid_pid = f"{details['vid']}:{details['pid']}"
        
        # Mark K+DCAN candidates
        status = ""
        if port.device in kdcan_devices:
            status = "★ K+DCAN Detected"
        
        # Truncate long descriptions
        desc = details['description'][:28] + ".." if len(details['description']) > 30 else details['description']
        
        print(f"{idx:<3} {port.device:<8} {desc:<30} {vid_pid:<12} {status}")
    
    print("\n" + "="*80)
    if kdcan_candidates:
        print("★ = K+DCAN cable detected (FTDI chip)")
        print(f"\nRecommended: Port #{[i+1 for i, p in enumerate(ports) if p.device == kdcan_candidates[0][0].device][0]} ({kdcan_candidates[0][0].device})")
    
    print("\nOptions:")
    print("  - Enter number (1-{}) to select port".format(len(ports)))
    print("  - Enter 'M' for manual port entry")
    print("  - Enter 'Q' to cancel")
    
    while True:
        choice = input("\nYour choice: ").strip().upper()
        
        if choice == 'Q':
            return None
        elif choice == 'M':
            return set_port_manual()
        else:
            try:
                port_idx = int(choice) - 1
                if 0 <= port_idx < len(ports):
                    selected = ports[port_idx].device
                    print(f"\nSelected: {selected}")
                    
                    # Test the connection
                    print("Testing connection...", end="", flush=True)
                    success, msg = test_port_connection(selected)
                    print(f" {msg}")
                    
                    if success:
                        return selected
                    else:
                        retry = input("Port test failed. Use anyway? (y/N): ").strip().upper()
                        if retry == 'Y':
                            return selected
                        print("Please select a different port.")
                else:
                    print(f"Invalid number. Please enter 1-{len(ports)}.")
            except ValueError:
                print("Invalid input. Please enter a number, 'M', or 'Q'.")


def set_port_manual(port_name: Optional[str] = None) -> Optional[str]:
    """
    Manually specify a COM port name.
    
    Args:
        port_name: Port name to use (if None, prompts user)
        
    Returns:
        Port name if valid, None otherwise
        
    Example:
        >>> port = set_port_manual("COM5")
        >>> print(f"Manually set to: {port}")
    """
    if port_name is None:
        port_name = input("Enter COM port name (e.g., COM3): ").strip().upper()
    
    # Validate format (COMx where x is a number)
    if not port_name.startswith("COM"):
        print(f"Invalid port name: {port_name}. Must start with 'COM'.")
        return None
    
    try:
        # Extract number part
        int(port_name[3:])
    except ValueError:
        print(f"Invalid port name: {port_name}. Format should be COMx (e.g., COM3).")
        return None
    
    # Test the connection
    print(f"Testing {port_name}...", end="", flush=True)
    success, msg = test_port_connection(port_name)
    print(f" {msg}")
    
    if success:
        return port_name
    else:
        retry = input("Port test failed. Use anyway? (y/N): ").strip().upper()
        if retry == 'Y':
            return port_name
        return None


def save_port_preference(port_name: str) -> bool:
    """
    Save selected COM port to configuration file for future sessions.
    
    Args:
        port_name: COM port name to save
        
    Returns:
        True if saved successfully, False otherwise
        
    Example:
        >>> if save_port_preference("COM3"):
        ...     print("Preference saved")
    """
    try:
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create new
        config = {}
        if PORT_CONFIG_FILE.exists():
            with open(PORT_CONFIG_FILE, 'r') as f:
                config = json.load(f)
        
        # Update port preference
        config['preferred_port'] = port_name
        config['last_updated'] = str(Path(__file__).stat().st_mtime)
        
        # Save to file
        with open(PORT_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Port preference saved: {port_name}")
        return True
        
    except Exception as e:
        print(f"Error saving port preference: {e}")
        return False


def get_saved_port() -> Optional[str]:
    """
    Retrieve previously saved COM port preference.
    
    Returns:
        Saved port name or None if no preference exists
        
    Example:
        >>> saved = get_saved_port()
        >>> if saved:
        ...     print(f"Previous selection: {saved}")
    """
    try:
        if not PORT_CONFIG_FILE.exists():
            return None
        
        with open(PORT_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        return config.get('preferred_port')
        
    except Exception as e:
        print(f"Error loading port preference: {e}")
        return None


def get_current_connection() -> Dict[str, str]:
    """
    Get current connection settings including saved port and its status.
    
    Returns:
        Dictionary with connection information
        
    Example:
        >>> info = get_current_connection()
        >>> print(f"Current port: {info.get('port', 'None')}")
    """
    saved_port = get_saved_port()
    
    if not saved_port:
        return {
            "port": "None",
            "status": "No saved preference",
            "available": False
        }
    
    # Test if saved port is still available
    success, msg = test_port_connection(saved_port)
    
    return {
        "port": saved_port,
        "status": msg,
        "available": success
    }


# Task 2.0 Required Functions
def get_recommended_port() -> Optional[str]:
    """
    Get the recommended port (first detected K+DCAN cable) - Task 2.0 requirement.
    
    Prioritizes accessible K+DCAN cables over inaccessible ones.
    
    Returns:
        Recommended port name or None if no K+DCAN cable found
    """
    ports = scan_com_ports()
    kdcan_ports = detect_kdcan_cable(ports)
    
    if kdcan_ports:
        # First try to find an accessible K+DCAN port
        for port, reason in kdcan_ports:
            success, msg = test_port_connection(port.device)
            if success:
                return port.device
        
        # If no accessible ports, return first K+DCAN port anyway
        return kdcan_ports[0][0].device
    
    return None


def format_port_display(port_info: Dict[str, str], numbered: bool = False, index: int = 0) -> str:
    """
    Format port information for display in the CLI - Task 2.0 requirement.
    
    Args:
        port_info: Dictionary containing port information (from get_port_details)
        numbered: If True, prefix with a number
        index: Index number to display (1-based)
    
    Returns:
        Formatted string for display
    """
    device = port_info['device']
    desc = port_info['description']
    vid_pid = f"[VID:{port_info['vid']} PID:{port_info['pid']}]" if port_info['vid'] != 'N/A' else ""
    
    # Add K+DCAN indicator if applicable
    kdcan_indicator = ""
    if port_info['vid'] == '0403' and port_info['pid'] == '6001':
        kdcan_indicator = " [K+DCAN]"
    
    # Build final string
    if numbered:
        return f"{index}. {device} - {desc} {vid_pid}{kdcan_indicator}"
    else:
        return f"{device} - {desc} {vid_pid}{kdcan_indicator}"


if __name__ == "__main__":
    # Command-line testing interface
    print("=== COM Port Scanner Test ===")
    print("\nScanning for ports...")
    
    ports = scan_com_ports()
    print(f"Found {len(ports)} port(s)\n")
    
    if ports:
        # Show detailed information
        for port in ports:
            details = get_port_details(port)
            print(f"Port: {details['device']}")
            print(f"  Description: {details['description']}")
            print(f"  Manufacturer: {details['manufacturer']}")
            print(f"  VID:PID: {details['vid']}:{details['pid']}")
            print(f"  Serial Number: {details['serial_number']}")
            print()
        
        # Detect K+DCAN
        kdcan = detect_kdcan_cable(ports)
        if kdcan:
            print("\n*** K+DCAN Cable Detected ***")
            for port, reason in kdcan:
                print(f"  {port.device}: {reason}")
        
        # Interactive port selection
        print("\n" + "="*80)
        selected = select_port_interactive(ports)
        if selected:
            print(f"\nYou selected: {selected}")
            if input("Save this as preferred port? (Y/n): ").strip().upper() != 'N':
                save_port_preference(selected)
    else:
        print("No COM ports found on this system.")
