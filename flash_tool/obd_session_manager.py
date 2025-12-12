#!/usr/bin/env python3
"""
BMW N54 OBD Session Manager - Persistent Connection Management
===============================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Manages OBD-II connection lifecycle with persistent connection
    across multiple menu operations. Avoids unnecessary reconnections
    and provides automatic connection recovery.

Features:
    - Single persistent OBD connection
    - Automatic reconnection on failure
    - Connection state tracking
    - Resource cleanup on exit
    - Singleton pattern for global access

Classes:
    OBDSessionManager - Persistent OBD connection manager (singleton)

Functions:
    get_session() -> OBDSessionManager

Variables (Module-level):
    logger: logging.Logger - Module logger
    _obd_session: OBDSessionManager - Singleton instance
"""

import logging
from typing import Optional
from . import obd_reader

logger = logging.getLogger(__name__)


class OBDSessionManager:
    """
    Manages persistent OBD-II connection throughout application lifecycle.
    
    This class maintains a single OBD connection object that can be reused
    across multiple diagnostic operations, avoiding the overhead of
    reconnecting on every operation.
    
    The connection is only re-established when:
    - The COM port changes
    - The connection is explicitly closed
    - A connection error occurs
    """
    
    def __init__(self, connection_manager=None):
        """Initialize session manager with no active connection.
        
        Args:
            connection_manager: Optional ConnectionManager instance for auto-registration
        """
        self._connection = None
        self._connected_port: Optional[str] = None
        self._baudrate = 38400
        self._connection_manager = connection_manager
    
    def get_connection(self, port: str, baudrate: int = 38400):
        """
        Get an active OBD connection, reusing existing if possible.
        
        Args:
            port: COM port name (e.g., "COM3")
            baudrate: Baud rate for serial communication (default: 38400)
            
        Returns:
            OBD connection object or None if connection failed
            
        Raises:
            OBDConnectionError: If connection cannot be established
        """
        # Check if we can reuse the existing connection
        if self._connection is not None:
            # Same port and baudrate - reuse connection
            if self._connected_port == port and self._baudrate == baudrate:
                # Verify connection is still alive
                if hasattr(self._connection, 'is_connected') and self._connection.is_connected():
                    logger.debug(f"Reusing existing OBD connection on {port}")
                    return self._connection
                else:
                    logger.info(f"Existing connection on {port} is dead, reconnecting...")
                    self.disconnect()
            else:
                # Different port/baudrate - close old connection
                logger.info(f"Port changed from {self._connected_port} to {port}, reconnecting...")
                self.disconnect()
        
        # Establish new connection
        logger.info(f"Establishing new OBD connection on {port} @ {baudrate} baud")
        try:
            self._connection = obd_reader.connect_obd(port, baudrate)
            self._connected_port = port
            self._baudrate = baudrate
            
            # Auto-register with connection_manager if provided
            if self._connection_manager:
                self._connection_manager.register_adapter('obd_session', self)
            
            return self._connection
        except obd_reader.OBDConnectionError as e:
            logger.error(f"Failed to connect to OBD on {port}: {e}")
            self._connection = None
            self._connected_port = None
            raise
    
    def disconnect(self):
        """Close the current OBD connection if one exists."""
        if self._connection is not None:
            logger.info(f"Closing OBD connection on {self._connected_port}")
            try:
                obd_reader.disconnect_obd(self._connection)
            except Exception as e:
                logger.warning(f"Error disconnecting OBD: {e}")
            finally:
                self._connection = None
                self._connected_port = None
                
                # Auto-unregister from connection_manager if registered
                if self._connection_manager:
                    self._connection_manager.unregister_adapter('obd_session')
    
    def close(self):
        """Alias for disconnect() to support Adapter protocol."""
        self.disconnect()
    
    def __enter__(self):
        """Context manager entry - returns self."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures disconnect on scope exit."""
        self.disconnect()
        return False  # Don't suppress exceptions
    
    def is_connected(self) -> bool:
        """
        Check if there's an active OBD connection.
        
        Returns:
            True if connected, False otherwise
        """
        if self._connection is None:
            return False
        
        # Verify connection is still alive
        try:
            if hasattr(self._connection, 'is_connected'):
                return self._connection.is_connected()
            return True
        except:
            return False
    
    def get_current_port(self) -> Optional[str]:
        """
        Get the port currently connected to.
        
        Returns:
            Port name or None if not connected
        """
        return self._connected_port if self.is_connected() else None
    
    def force_reconnect(self, port: Optional[str] = None, baudrate: Optional[int] = None):
        """
        Force a reconnection, even if already connected.
        
        Useful for recovering from connection errors or changing parameters.
        
        Args:
            port: New port to connect to (uses current port if None)
            baudrate: New baudrate (uses current if None)
            
        Returns:
            OBD connection object or None if connection failed
        """
        # Use current values if not specified
        if port is None:
            port = self._connected_port
        if baudrate is None:
            baudrate = self._baudrate
        
        # Disconnect and reconnect
        self.disconnect()
        
        if port is not None:
            return self.get_connection(port, baudrate)
        else:
            logger.warning("Cannot reconnect: no port specified and no previous connection")
            return None


# Global OBD session manager instance
_obd_session = OBDSessionManager()


def get_session() -> OBDSessionManager:
    """
    Get the global OBDSessionManager instance.
    
    Returns:
        Singleton OBDSessionManager instance
    """
    return _obd_session


# Convenience helper: return an active connection if available
def get_active_connection():
    """
    Return the currently active OBD connection object if connected, else None.

    This is a convenience wrapper used by higher-level components that want
    to read live data without forcing a reconnect. It does NOT attempt to
    auto-detect ports or establish new connections.
    """
    if _obd_session.is_connected():
        return _obd_session._connection
    return None
