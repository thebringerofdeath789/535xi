#!/usr/bin/env python3
"""
BMW N54 Settings Manager - Configuration and Preferences Management
====================================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Comprehensive settings and configuration management for Flash Tool.
    Handles user preferences, default values, validation, and persistent
    configuration storage using INI files.



Features:
    - Hierarchical configuration (paths, connection, timeouts, safety)
    - Default values with runtime override
    - Configuration validation
    - Persistent storage (flash_tool_config.ini)
    - Singleton pattern for global access

Classes:
    SettingsError(Exception) - Configuration errors
    SettingsManager - Main configuration manager (singleton)

Functions:
    get_settings_manager() -> SettingsManager
    load_settings() -> Dict[str, Dict[str, str]]
    save_settings(settings_dict: Dict) -> bool
    get_current_settings() -> Dict[str, Dict[str, str]]
    reset_to_defaults() -> bool

Variables (Module-level):
    DEFAULT_SETTINGS: Dict - Default configuration values
    logger: logging.Logger - Module logger
    _settings_manager: SettingsManager - Singleton instance
"""

import configparser
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger: logging.Logger = logging.getLogger(__name__)

# Default settings values
DEFAULT_SETTINGS: Dict[str, Dict[str, str]] = {
    'PATHS': {
        'maps_directory': 'maps',
        'backups_directory': 'backups',
        'logs_directory': 'logs'
    },
    'EXTRACTION': {
        # Calibration export window selection for 2MB full backups:
        #  - 'auto'  : Try 512KB at 0x100000 first (CRC32 check), then 256KB; fallback to 512KB
        #  - '512K'  : Force 512KB window at 0x100000
        #  - '256K'  : Force 256KB window at 0x100000
        'calibration_window': 'auto'
    },
    'CONNECTION': {
        'default_port': '',  # Empty = auto-detect
        'baudrate': '38400',
        'timeout': '5'
    },
    'TIMEOUTS': {
        'read_operation': '30',
        'write_operation': '120',
        'diagnostic_operation': '30',
        'flash_operation': '300'
    },
    'LOGGING': {
        'log_level': 'INFO',
        'log_retention_days': '30',
        'max_log_size_mb': '100',
        'enable_debug': 'false'
    },
    'SAFETY': {
        'auto_backup_before_flash': 'true',
        'require_vin_confirmation': 'true',
        'min_battery_voltage': '12.5'
    },
    'UI': {
        'confirm_clear_codes': 'true',
        'show_warnings': 'true',
        'enable_colors': 'true'
    }
    ,
    'FLASH': {
        # Controls automatic resetting of flash counter after write operations.
        # Values: 'true'|'false'|'ask' (ask will prompt the user during flash)
        'auto_reset_flash_counter': 'false'
    }
}


class SettingsError(Exception):
    """Raised when settings operation fails"""
    pass


class SettingsManager:
    """Manages application settings and configuration."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize settings manager.
        
        Args:
            config_file: Path to settings.ini file. If None, uses default location.
        """
        if config_file is None:
            config_file = Path(__file__).parent.parent / 'config' / 'settings.ini'
        
        self.config_file = Path(config_file)
        self.config: configparser.ConfigParser = configparser.ConfigParser()
        
        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or create config
        if self.config_file.exists():
            self.load_settings()
        else:
            self.reset_to_defaults()
            logger.info(f"Created new settings file: {self.config_file}")
    
    def load_settings(self) -> Dict[str, Dict[str, str]]:
        """
        Load settings from config file.
        
        Returns:
            Dictionary with all settings organized by section
        
        Raises:
            SettingsError: If config file cannot be read
        
        Example:
            >>> mgr = SettingsManager()
            >>> settings = mgr.load_settings()
            >>> # Access maps directory
            >>> settings['PATHS'].get('maps_directory')
        """
        try:
            self.config.read(self.config_file)
            
            # Verify all required sections exist, add missing ones
            for section, defaults in DEFAULT_SETTINGS.items():
                if section not in self.config:
                    self.config[section] = defaults
                    logger.warning(f"Added missing section: {section}")
                else:
                    # Add missing keys within existing sections
                    for key, value in defaults.items():
                        if key not in self.config[section]:
                            self.config[section][key] = value
                            logger.warning(f"Added missing setting: {section}.{key}")
            
            # Save if any defaults were added
            if self._has_missing_settings():
                self.save_settings(self.get_current_settings())
            
            logger.info(f"Settings loaded from {self.config_file}")
            return self.get_current_settings()
        
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            raise SettingsError(f"Failed to load settings: {e}")
    
    def save_settings(self, settings_dict: Optional[Dict[str, Dict[str, str]]] = None) -> bool:
        """
        Save settings to config file.
        
        Args:
            settings_dict: Settings to save. If None, saves current config state.
        
        Returns:
            True if save succeeded
        
        Raises:
            SettingsError: If config file cannot be written
        
        Example:
            >>> mgr = SettingsManager()
            >>> settings = mgr.get_current_settings()
            >>> settings['PATHS']['maps_directory'] = 'custom_maps'
            >>> mgr.save_settings(settings)
        """
        try:
            if settings_dict is not None:
                # Update config from provided dictionary
                for section, values in settings_dict.items():
                    if section not in self.config:
                        self.config[section] = {}
                    for key, value in values.items():
                        self.config[section][key] = str(value)
            
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            
            logger.info(f"Settings saved to {self.config_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            raise SettingsError(f"Failed to save settings: {e}")
    
    def get_current_settings(self) -> Dict[str, Dict[str, str]]:
        """
        Return all current settings as dictionary.
        
        Returns:
            Dictionary with all settings organized by section
        
        Example:
            >>> mgr = SettingsManager()
            >>> settings = mgr.get_current_settings()
            >>> for section, values in settings.items():
            ...     print(f"{section}: {values}")
        """
        settings = {}
        for section in self.config.sections():
            settings[section] = dict(self.config[section])
        return settings
    
    def reset_to_defaults(self) -> bool:
        """
        Reset all settings to default values.
        
        Returns:
            True if reset succeeded
        
        Example:
            >>> mgr = SettingsManager()
            >>> mgr.reset_to_defaults()
            True
        """
        try:
            self.config.clear()
            for section, values in DEFAULT_SETTINGS.items():
                self.config[section] = values
            
            self.save_settings()
            logger.info("Settings reset to defaults")
            return True
        
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            raise SettingsError(f"Failed to reset settings: {e}")
    

    
    def set_default_port(self, port: str) -> bool:
        """
        Set default COM port.
        
        Args:
            port: COM port name (e.g., "COM3") or empty for auto-detect
        
        Returns:
            True if saved successfully
        
        Example:
            >>> mgr = SettingsManager()
            >>> mgr.set_default_port("COM5")
        """
        self.config['CONNECTION']['default_port'] = port
        self.save_settings()
        logger.info(f"Default port set to: {port if port else 'auto-detect'}")
        return True
    
    def set_maps_directory(self, path: str) -> bool:
        """
        Configure maps folder location.
        
        Args:
            path: Path to maps directory (relative or absolute)
        
        Returns:
            True if saved successfully
        
        Example:
            >>> mgr = SettingsManager()
            >>> mgr.set_maps_directory("D:/BMW_Maps")
        """
        # Create directory if it doesn't exist
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        
        self.config['PATHS']['maps_directory'] = str(path)
        self.save_settings()
        logger.info(f"Maps directory set to: {path}")
        return True
    
    def set_backups_directory(self, path: str) -> bool:
        """
        Configure backups folder location.
        
        Args:
            path: Path to backups directory (relative or absolute)
        
        Returns:
            True if saved successfully
        
        Example:
            >>> mgr = SettingsManager()
            >>> mgr.set_backups_directory("D:/BMW_Backups")
        """
        # Create directory if it doesn't exist
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        
        self.config['PATHS']['backups_directory'] = str(path)
        self.save_settings()
        logger.info(f"Backups directory set to: {path}")
        return True
    
    def set_logs_directory(self, path: str) -> bool:
        """
        Configure logs folder location.

        Args:
            path: Path to logs directory (relative or absolute)

        Returns:
            True if saved successfully

        Example:
            >>> mgr = SettingsManager()
            >>> mgr.set_logs_directory("D:/BMW_Logs")
        """
        # Create directory if it doesn't exist
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)

        self.config['PATHS']['logs_directory'] = str(path)
        self.save_settings()
        logger.info(f"Logs directory set to: {path}")
        return True
    
    def set_timeout(self, operation: str, seconds: int) -> bool:
        """
        Configure operation timeout.
        
        Args:
            operation: Operation type ('read', 'write', 'diagnostic', 'flash')
            seconds: Timeout in seconds
        
        Returns:
            True if saved successfully
        
        Raises:
            SettingsError: If operation type is invalid
        
        Example:
            >>> mgr = SettingsManager()
            >>> mgr.set_timeout('flash', 600)  # 10 minutes
        """
        timeout_map = {
            'read': 'read_operation',
            'write': 'write_operation',
            'diagnostic': 'diagnostic_operation',
            'flash': 'flash_operation'
        }
        
        if operation not in timeout_map:
            raise SettingsError(f"Invalid operation type: {operation}. Must be one of: {list(timeout_map.keys())}")
        
        key = timeout_map[operation]
        self.config['TIMEOUTS'][key] = str(seconds)
        self.save_settings()
        logger.info(f"{operation} timeout set to: {seconds}s")
        return True
    
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a specific setting value.
        
        Args:
            section: Configuration section name
            key: Setting key name
            default: Default value if setting doesn't exist
        
        Returns:
            Setting value or default
        
        Example:
            >>> mgr = SettingsManager()

            >>> timeout = int(mgr.get_setting('TIMEOUTS', 'read_operation', 30))
        """
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def get_bool_setting(self, section: str, key: str, default: bool = False) -> bool:
        """
        Get a boolean setting value.
        
        Args:
            section: Configuration section name
            key: Setting key name
            default: Default value if setting doesn't exist
        
        Returns:
            Boolean setting value
        
        Example:
            >>> mgr = SettingsManager()
            >>> auto_backup = mgr.get_bool_setting('SAFETY', 'auto_backup_before_flash')
        """
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def get_int_setting(self, section: str, key: str, default: int = 0) -> int:
        """
        Get an integer setting value.
        
        Args:
            section: Configuration section name
            key: Setting key name
            default: Default value if setting doesn't exist
        
        Returns:
            Integer setting value
        
        Example:
            >>> mgr = SettingsManager()
            >>> timeout = mgr.get_int_setting('TIMEOUTS', 'read_operation', 30)
        """
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def get_float_setting(self, section: str, key: str, default: float = 0.0) -> float:
        """
        Get a float setting value.
        
        Args:
            section: Configuration section name
            key: Setting key name
            default: Default value if setting doesn't exist
        
        Returns:
            Float setting value
        
        Example:
            >>> mgr = SettingsManager()
            >>> min_voltage = mgr.get_float_setting('SAFETY', 'min_battery_voltage', 12.5)
        """
        try:
            return self.config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def set_setting(self, section: str, key: str, value: str) -> bool:
        """
        Set a configuration value directly.
        
        Args:
            section: Configuration section name
            key: Setting key
            value: Setting value (will be stored as string)
        
        Returns:
            True if saved successfully
        
        Example:
            >>> mgr = SettingsManager()
            >>> mgr.set_setting('UI', 'enable_colors', 'true')
        """
        if section not in self.config:
            self.config.add_section(section)
        self.config[section][key] = str(value)
        return self.save_settings()
    
    def _has_missing_settings(self) -> bool:
        """Check if any default settings are missing from current config."""
        for section, defaults in DEFAULT_SETTINGS.items():
            if section not in self.config:
                return True
            for key in defaults.keys():
                if key not in self.config[section]:
                    return True
        return False
    
    # Typed property accessors for common settings
    @property
    def maps_directory(self) -> Path:
        """Get maps directory path."""
        return Path(self.get_setting('PATHS', 'maps_directory', 'maps'))
    
    @property
    def backups_directory(self) -> Path:
        """Get backups directory path."""
        return Path(self.get_setting('PATHS', 'backups_directory', 'backups'))
    
    @property
    def logs_directory(self) -> Path:
        """Get logs directory path."""
        return Path(self.get_setting('PATHS', 'logs_directory', 'logs'))
    
    @property
    def default_port(self) -> str:
        """Get default COM port (empty string for auto-detect)."""
        return self.get_setting('CONNECTION', 'default_port', '')
    
    @property
    def baudrate(self) -> int:
        """Get serial baudrate."""
        return self.get_int_setting('CONNECTION', 'baudrate', 38400)
    
    @property
    def min_battery_voltage(self) -> float:
        """Get minimum battery voltage for flash operations."""
        return self.get_float_setting('SAFETY', 'min_battery_voltage', 12.5)
    
    @property
    def auto_backup_before_flash(self) -> bool:
        """Check if auto-backup is enabled before flash operations."""
        return self.get_bool_setting('SAFETY', 'auto_backup_before_flash', True)
    
    @property
    def require_vin_confirmation(self) -> bool:
        """Check if VIN confirmation is required."""
        return self.get_bool_setting('SAFETY', 'require_vin_confirmation', True)
    
    @property
    def calibration_window(self) -> str:
        """Get calibration window selection ('auto', '512K', or '256K')."""
        return self.get_setting('EXTRACTION', 'calibration_window', 'auto')
    
    @property
    def auto_reset_flash_counter(self) -> str:
        """Get flash counter auto-reset behavior ('true', 'false', or 'ask')."""
        return self.get_setting('FLASH', 'auto_reset_flash_counter', 'false')


# Global settings manager instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """
    Get the global settings manager instance (singleton pattern).
    
    Returns:
        Global SettingsManager instance
    
    Example:
        >>> mgr = get_settings_manager()
        >>> settings = mgr.get_current_settings()
    """
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


def load_settings() -> Dict[str, Dict[str, str]]:
    """
    Convenience function to load settings using global manager.
    
    Returns:
        Dictionary with all settings
    """
    return get_settings_manager().load_settings()


def save_settings(settings_dict: Dict[str, Dict[str, str]]) -> bool:
    """
    Convenience function to save settings using global manager.
    
    Args:
        settings_dict: Settings to save
    
    Returns:
        True if save succeeded
    """
    return get_settings_manager().save_settings(settings_dict)


def get_current_settings() -> Dict[str, Dict[str, str]]:
    """
    Convenience function to get current settings using global manager.
    
    Returns:
        Dictionary with all settings
    """
    return get_settings_manager().get_current_settings()


def reset_to_defaults() -> bool:
    """
    Convenience function to reset settings using global manager.
    
    Returns:
        True if reset succeeded
    """
    return get_settings_manager().reset_to_defaults()
