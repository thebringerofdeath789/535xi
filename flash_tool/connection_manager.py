#!/usr/bin/env python3
"""
BMW N54 Connection Manager - Persistent Session Management
===========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Manages persistent COM port connections across application lifecycle.
    Provides session state tracking, connection validation, and automatic
    reconnection with saved preferences.

Classes:
    ConnectionManager - Singleton connection state manager

Functions:
    get_manager() -> ConnectionManager
    save_connection_config(port: str, settings: Dict) -> bool
    load_connection_config() -> Dict[str, Any]

Variables (Module-level):
    _connection_manager: ConnectionManager - Singleton instance
"""

import os
import configparser
from typing import Optional, Dict, Any, List, Tuple, TypedDict, Protocol
from dataclasses import dataclass
from datetime import datetime
import logging
from . import com_scanner
from . import bmw_modules
from .uds_client import UDSClient
from .direct_can_flasher import UDSService

logger = logging.getLogger(__name__)


class Adapter(Protocol):
    """Protocol for connection adapters that can be managed.
    
    Any adapter (CAN bus, OBD connection, etc.) should implement either:
    - close() method (python-can convention)
    - disconnect() method (custom convention)
    - shutdown() method (alternative convention)
    """
    def close(self) -> None:
        """Close the adapter connection."""
        ...


class ConnectionManager:
    """
    Manages the active COM port connection for the flash tool session.
    
    This class maintains state about the currently selected/active port
    and provides methods to check connection status, change ports, etc.
    
    - Persistent storage of port preferences in config/connection.ini
    - Baudrate and timeout configuration
    - Last used timestamp tracking
    """
    
    def __init__(self, config_dir: str = "config"):
        """Initialize connection manager with no active connection."""
        self._active_port: Optional[str] = None
        self._connection_tested: bool = False
        self._config_dir = config_dir
        self._config_file = os.path.join(config_dir, "connection.ini")
        self._baudrate = 38400
        # Adapter registry for lifecycle management
        self._adapters: Dict[str, Any] = {}  # name -> adapter instance
        self._ensure_config_dir()
        self._load_settings()
        # Do NOT auto-activate saved port on init; tests expect a cold start
    
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        if not os.path.exists(self._config_dir):
            os.makedirs(self._config_dir)
    
    def _load_settings(self):
        """Load connection settings from config file."""
        if not os.path.exists(self._config_file):
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(self._config_file)
            
            if 'Connection' in config:
                self._baudrate = config['Connection'].getint('baudrate', 38400)
        except Exception as e:
            print(f"Warning: Failed to load connection settings: {e}")
    
    def _save_settings(self, port: Optional[str] = None):
        """
        Save connection settings to config file.
        
        Args:
            port: Port to save as preference (if None, saves current settings only)
        """
        try:
            config = configparser.ConfigParser()
            
            # Load existing config if it exists
            if os.path.exists(self._config_file):
                config.read(self._config_file)
            
            # Ensure Connection section exists
            if 'Connection' not in config:
                config['Connection'] = {}
            
            # Update settings
            if port is not None:
                config['Connection']['port'] = port
            config['Connection']['baudrate'] = str(self._baudrate)
            config['Connection']['last_updated'] = datetime.now().isoformat()
            
            # Write to file
            with open(self._config_file, 'w') as f:
                config.write(f)
                
        except Exception as e:
            print(f"Warning: Failed to save connection settings: {e}")
    
    def get_active_port(self) -> Optional[str]:
        """
        Get the currently active COM port.
        
        Returns:
            Port name (e.g., "COM3") or None if no port is active
        """
        return self._active_port
    
    def set_active_port(self, port_name: str, test: bool = True) -> bool:
        """
        Set the active COM port for this session.
        
        Args:
            port_name: COM port to activate (e.g., "COM3")
            test: Whether to test connection before activating (default: True)
            
        Returns:
            True if port was set successfully, False otherwise
        """
        if test:
            success, msg = com_scanner.test_port_connection(port_name)
            if not success:
                print(f"Cannot set active port: {msg}")
                return False
            self._connection_tested = True
        else:
            self._connection_tested = False
        
        self._active_port = port_name
        return True
    
    def clear_active_port(self):
        """Clear the active port (disconnect)."""
        self._active_port = None
        self._connection_tested = False
    
    def is_connected(self) -> bool:
        """
        Check if there is an active port connection.
        
        Returns:
            True if a port is active and has been tested, False otherwise
        """
        # Consider connected only if a port is active AND has been tested
        return self._active_port is not None and self._connection_tested
    
    class ConnectionInfo(TypedDict, total=False):
        connected: bool
        port: Optional[str]
        tested: bool
        status: str
        current_status: str
        accessible: bool

    def get_connection_info(self) -> ConnectionInfo:
        """
        Get detailed information about the current connection.
        
        Returns:
            Dictionary with connection details
        """
        if not self._active_port:
            return {
                "connected": False,
                "port": None,
                "tested": False,
                "status": "No active connection"
            }
        
        # Test current connection each time for accurate status
        success, msg = com_scanner.test_port_connection(self._active_port)

        return {
            "connected": bool(success),
            "port": self._active_port,
            "tested": self._connection_tested,
            "current_status": msg,
            "accessible": success
        }
    
    def load_saved_port(self, auto_activate: bool = False) -> Optional[str]:
        """
        Load the saved port preference from config.
        
        Args:
            auto_activate: If True, automatically set as active port
            
        Returns:
            Saved port name or None
        """
        saved = com_scanner.get_saved_port()
        
        if saved and auto_activate:
            if self.set_active_port(saved):
                print(f"Loaded saved port: {saved}")
            else:
                print(f"Saved port {saved} is not accessible")
        
        return saved
    
    # Task 2.0 required functions
    def save_port_preference(self, port: str):
        """
        Save a COM port as the preferred connection (Task 2.0 requirement).
        
        This method unifies port storage between connection_manager (INI file)
        and com_scanner (JSON file) to maintain compatibility with both Task 1.0 and Task 2.0.
        
        Args:
            port: COM port name (e.g., 'COM3')
        """
        # Save to connection.ini (Task 2.0)
        self._save_settings(port=port)
        # Also save to port_preferences.json (Task 1.0 compatibility)
        from . import com_scanner
        com_scanner.save_port_preference(port)
    
    def get_saved_port(self) -> Optional[str]:
        """
        Get the saved port preference (Task 2.0 requirement).
        
        This method checks both storage locations and returns the most recently saved port.
        Prioritizes connection.ini (Task 2.0) over port_preferences.json (Task 1.0).
        
        Returns:
            Saved port name or None
        """
        # First check connection.ini (Task 2.0 storage)
        if os.path.exists(self._config_file):
            try:
                config = configparser.ConfigParser()
                config.read(self._config_file)
                if 'Connection' in config and config['Connection'].get('port'):
                    return config['Connection']['port']
            except:
                pass
        
        # Fall back to port_preferences.json (Task 1.0 storage)
        from . import com_scanner
        return com_scanner.get_saved_port()
    
    def get_connection_settings(self) -> Dict[str, Any]:
        """
        Get current connection settings (Task 2.0 requirement).
        
        Returns:
            Dictionary containing connection settings
        """
        settings = {
            'port': self.get_saved_port(),
            'baudrate': self._baudrate,
            'status': 'Connected' if self._active_port else 'Not connected',
            'last_used': None
        }
        
        # Try to get last_used from config file
        if os.path.exists(self._config_file):
            try:
                config = configparser.ConfigParser()
                config.read(self._config_file)
                if 'Connection' in config:
                    settings['last_used'] = config['Connection'].get('last_updated', None)
            except:
                pass
        
        return settings
    
    def set_baudrate(self, baudrate: int):
        """
        Set the baudrate for serial communication (Task 2.0 requirement).
        
        Args:
            baudrate: Baudrate value (e.g., 38400, 115200)
        """
        self._baudrate = baudrate
        self._save_settings()
    
    def get_baudrate(self) -> int:
        """
        Get the configured baudrate (Task 2.0 requirement).
        
        Returns:
            Baudrate value
        """
        return self._baudrate
    
    def register_adapter(self, name: str, adapter: Any) -> None:
        """
        Register an active adapter for lifecycle management.
        
        Allows connection_manager to track and close all adapters during cleanup.
        Adapters should implement close(), disconnect(), or shutdown() method.
        
        Args:
            name: Unique identifier for this adapter (e.g., 'can_bus', 'obd_connection')
            adapter: Adapter instance with close/disconnect/shutdown method
            
        Example:
            >>> flasher = DirectCANFlasher()
            >>> flasher.connect()
            >>> conn_mgr.register_adapter('direct_can', flasher)
        """
        if name in self._adapters:
            logger.warning(f"Adapter '{name}' already registered, replacing")
        self._adapters[name] = adapter
        logger.debug(f"Registered adapter: {name} ({type(adapter).__name__})")
    
    def unregister_adapter(self, name: str) -> None:
        """
        Unregister an adapter from lifecycle management.
        
        Should be called when adapter is manually closed/disconnected.
        
        Args:
            name: Adapter identifier used during registration
        """
        if name in self._adapters:
            del self._adapters[name]
            logger.debug(f"Unregistered adapter: {name}")
    
    def get_active_adapters(self) -> List[str]:
        """
        Get list of currently registered adapter names.
        
        Returns:
            List of adapter names
        """
        return list(self._adapters.keys())
    
    def close_all(self) -> None:
        """
        Close all registered adapters and reset connection state.
        
        Safely shuts down all tracked adapters (CAN bus, OBD connections, etc.)
        by attempting multiple shutdown method names in order:
        1. close() - python-can convention
        2. disconnect() - custom convention
        3. shutdown() - alternative convention
        
        Logs failures but continues cleanup to ensure all adapters are processed.
        Clears adapter registry and resets connection state after cleanup.
        
        Example:
            >>> conn_mgr.register_adapter('can', flasher)
            >>> conn_mgr.register_adapter('obd', obd_conn)
            >>> conn_mgr.close_all()  # Closes both adapters
        """
        if not self._adapters:
            logger.debug("No adapters registered, nothing to close")
            return
        
        logger.info(f"Closing {len(self._adapters)} registered adapter(s)...")
        failures = []
        
        for name, adapter in list(self._adapters.items()):
            try:
                # Try multiple close method conventions
                if hasattr(adapter, 'close'):
                    adapter.close()
                    logger.debug(f"Closed adapter '{name}' via close()")
                elif hasattr(adapter, 'disconnect'):
                    adapter.disconnect()
                    logger.debug(f"Closed adapter '{name}' via disconnect()")
                elif hasattr(adapter, 'shutdown'):
                    adapter.shutdown()
                    logger.debug(f"Closed adapter '{name}' via shutdown()")
                else:
                    logger.warning(f"Adapter '{name}' has no close/disconnect/shutdown method")
            except Exception as e:
                logger.error(f"Failed to close adapter '{name}': {e}", exc_info=True)
                failures.append((name, str(e)))
        
        # Clear registry even if some closures failed
        self._adapters.clear()
        
        # Reset connection state
        self._active_port = None
        self._connection_tested = False
        
        if failures:
            logger.warning(f"Failed to close {len(failures)} adapter(s): {[name for name, _ in failures]}")
        else:
            logger.info("All adapters closed successfully")
    
    def __enter__(self):
        """Context manager entry - returns self."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup on scope exit."""
        self.close_all()
        return False  # Don't suppress exceptions
    
    @dataclass
    class ModulePingResult:
        module: bmw_modules.BMWModule
        responding: bool

    def scan_all_modules(self, protocol: str = "CAN") -> List["ConnectionManager.ModulePingResult"]:
        """
        Scan for active BMW modules on the vehicle bus (Task 1.1.3).
        
        This method attempts to communicate with all known BMW modules to determine
        which are present and responding on the vehicle.
        
        Args:
            protocol: Protocol to scan - "CAN" for UDS/CAN modules, "KLINE" for K-line modules, "ALL" for both
        
        Returns:
            List of tuples (module, is_responding) for each scanned module
        """
        results: List[ConnectionManager.ModulePingResult] = []
        
        if protocol.upper() in ["CAN", "ALL"]:
            # Scan CAN modules using UDS TesterPresent (0x3E)
            can_modules = bmw_modules.get_can_modules()
            print(f"\nScanning {len(can_modules)} CAN modules (Tester Present)...")

            uds = UDSClient()
            if uds.connect():
                try:
                    for module in can_modules:
                        try:
                            res = uds.send_raw(module, UDSService(0x3E), b"\x00")
                            responding = bool(res and res[0])
                        except Exception:
                            responding = False
                        results.append(ConnectionManager.ModulePingResult(module=module, responding=responding))
                finally:
                    try:
                        uds.disconnect()
                    except Exception:
                        pass
            else:
                # If we cannot connect, mark all as not responding
                for module in can_modules:
                    results.append(ConnectionManager.ModulePingResult(module=module, responding=False))
        
        if protocol.upper() in ["KLINE", "ALL"]:
            # Scan K-line modules
            kline_modules = bmw_modules.get_kline_modules()
            print(f"\nScanning {len(kline_modules)} K-line modules...")
            
            for module in kline_modules:
                # K-line scanning not implemented
                results.append(ConnectionManager.ModulePingResult(module=module, responding=False))
        
        return results
    
    def get_responding_modules(self) -> List[bmw_modules.BMWModule]:
        """
        Get list of modules that responded to last scan.
        
        Returns:
            List of BMWModule objects that are active
        """
        # This will be populated once we implement actual scanning
        # For now, return empty list
        return []


# Global connection manager instance
_manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """
    Get the global ConnectionManager instance.
    
    Returns:
        Singleton ConnectionManager instance
    """
    return _manager


# Task 2.0 module-level convenience functions
def save_port_preference(port: str):
    """Save a COM port preference (Task 2.0 requirement)."""
    get_manager().save_port_preference(port)


def get_saved_port() -> Optional[str]:
    """Get the saved COM port (Task 2.0 requirement)."""
    return get_manager().get_saved_port()


def get_connection_settings() -> Dict[str, Any]:
    """Get current connection settings (Task 2.0 requirement)."""
    return get_manager().get_connection_settings()


def clear_saved_port():
    """Clear the saved port preference (Task 2.0 requirement)."""
    # Clear from both storage locations
    manager = get_manager()
    
    # Clear connection.ini
    if os.path.exists(manager._config_file):
        try:
            config = configparser.ConfigParser()
            config.read(manager._config_file)
            if 'Connection' in config:
                config['Connection']['port'] = ''
                with open(manager._config_file, 'w') as f:
                    config.write(f)
        except:
            pass
    
    # Clear port_preferences.json (Task 1.0 compatibility)
    from . import com_scanner
    try:
        if os.path.exists(com_scanner.PORT_CONFIG_FILE):
            os.remove(com_scanner.PORT_CONFIG_FILE)
    except:
        pass

