#!/usr/bin/env python3
"""
BMW N54 Operation Logger - Comprehensive Logging System
========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Comprehensive logging system for all Flash Tool operations.
    Tracks operations, errors, warnings, and provides log management
    functions with automatic rotation and archival.

Features:
    - Structured operation logging (operation, status, details, timestamp)
    - Error tracking with traceback capture
    - Log file rotation and archival
    - Log browsing and search
    - Export capabilities
    - Singleton pattern for global access

Classes:
    OperationLogger - Main logging system (singleton)

Functions:
    get_operation_logger() -> OperationLogger
    log_operation(operation: str, status: str, details: Optional[str]) -> bool
    log_error(error_message: str, traceback: Optional[str]) -> bool

Variables (Module-level):
    logger: logging.Logger - Module logger
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import traceback as tb

logger = logging.getLogger(__name__)


class OperationLogger:
    """Manages operation logging and log file management."""
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize operation logger.
        
        Args:
            log_dir: Directory for log files. If None, uses default 'logs/' directory.
        """
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / 'logs'
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.operations_log = self.log_dir / 'operations.log'
        self.errors_log = self.log_dir / 'errors.log'
        
        # Ensure log files exist
        self.operations_log.touch(exist_ok=True)
        self.errors_log.touch(exist_ok=True)
    
    def log_operation(self, operation: str, status: str, details: Optional[str] = None) -> bool:
        """
        Log any operation with status and optional details.
        
        Args:
            operation: Name/description of operation
            status: Status ('success', 'failure', 'warning', 'info')
            details: Additional details or context
        
        Returns:
            True if logged successfully
        
        Example:
            >>> logger = OperationLogger()
            >>> logger.log_operation('Read DTCs', 'success', 'Found 3 codes')
            >>> logger.log_operation('Flash Map', 'failure', 'Communication timeout')
        """
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'operation': operation,
                'status': status.upper(),
                'details': details or ''
            }
            
            # Write to operations log
            with open(self.operations_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            # If failure or error, also log to errors log
            if status.upper() in ['FAILURE', 'ERROR']:
                with open(self.errors_log, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry) + '\n')
            
            return True
        
        except Exception as e:
            logger.error(f"Error logging operation: {e}")
            return False
    
    def log_error(self, error_message: str, traceback: Optional[str] = None) -> bool:
        """
        Log errors with full details and optional traceback.
        
        Args:
            error_message: Error message or description
            traceback: Full error traceback (optional)
        
        Returns:
            True if logged successfully
        
        Example:
            >>> logger = OperationLogger()
            >>> try:
            ...     raise ValueError("Invalid map file")
            ... except Exception as e:
            ...     logger.log_error(str(e), traceback.format_exc())
        """
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'operation': 'ERROR',
                'status': 'ERROR',
                'details': error_message,
                'traceback': traceback or ''
            }
            
            # Write to both logs
            with open(self.operations_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            with open(self.errors_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            return True
        
        except Exception as e:
            logger.error(f"Error logging error: {e}")
            return False
    
    def get_recent_logs(self, count: int = 50) -> List[Dict[str, str]]:
        """
        Retrieve recent log entries.
        
        Args:
            count: Number of recent entries to return
        
        Returns:
            List of log entry dictionaries (most recent first)
        
        Example:
            >>> logger = OperationLogger()
            >>> recent = logger.get_recent_logs(20)
            >>> for entry in recent:
            ...     print(f"{entry['timestamp']}: {entry['operation']} - {entry['status']}")
        """
        try:
            if not self.operations_log.exists():
                return []
            
            entries = []
            with open(self.operations_log, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Skip malformed entries
                            continue
            
            # Return most recent first
            return entries[-count:][::-1]
        
        except Exception as e:
            logger.error(f"Error reading operations log: {e}")
            return []
    
    def get_error_logs(self, count: int = 50) -> List[Dict[str, str]]:
        """
        Retrieve recent errors only.
        
        Args:
            count: Number of recent error entries to return
        
        Returns:
            List of error entry dictionaries (most recent first)
        
        Example:
            >>> logger = OperationLogger()
            >>> errors = logger.get_error_logs(10)
            >>> if errors:
            ...     print(f"Found {len(errors)} recent errors")
        """
        try:
            if not self.errors_log.exists():
                return []
            
            entries = []
            with open(self.errors_log, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Skip malformed entries
                            continue
            
            # Return most recent first
            return entries[-count:][::-1]
        
        except Exception as e:
            logger.error(f"Error reading errors log: {e}")
            return []
    
    def export_logs(self, output_file: Path, include_errors_only: bool = False) -> bool:
        """
        Export all logs to a file.
        
        Args:
            output_file: Path for exported log file
            include_errors_only: If True, only export errors
        
        Returns:
            True if export succeeded
        
        Example:
            >>> logger = OperationLogger()
            >>> logger.export_logs(Path('exported_logs.txt'))
            >>> logger.export_logs(Path('errors_only.txt'), include_errors_only=True)
        """
        try:
            source_log = self.errors_log if include_errors_only else self.operations_log
            
            if not source_log.exists():
                logger.warning(f"Source log not found: {source_log}")
                return False
            
            # Read all entries and format nicely
            entries = []
            with open(source_log, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            
            # Write formatted output
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"Flash Tool {'Error' if include_errors_only else 'Operations'} Log Export\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Entries: {len(entries)}\n")
                f.write("="*80 + "\n\n")
                
                for entry in entries:
                    f.write(f"[{entry.get('timestamp', 'Unknown')}]\n")
                    f.write(f"Operation: {entry.get('operation', 'Unknown')}\n")
                    f.write(f"Status: {entry.get('status', 'Unknown')}\n")
                    if entry.get('details'):
                        f.write(f"Details: {entry['details']}\n")
                    if entry.get('traceback'):
                        f.write(f"Traceback:\n{entry['traceback']}\n")
                    f.write("-"*80 + "\n\n")
            
            logger.info(f"Logs exported to: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            return False
    
    def clear_old_logs(self, days: int = 30) -> int:
        """
        Remove log entries older than N days.
        
        Args:
            days: Number of days to retain
        
        Returns:
            Number of entries removed
        
        Example:
            >>> logger = OperationLogger()
            >>> removed = logger.clear_old_logs(30)
            >>> print(f"Removed {removed} old log entries")
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            removed_count = 0
            
            for log_file in [self.operations_log, self.errors_log]:
                if not log_file.exists():
                    continue
                
                # Read all entries
                entries = []
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entry = json.loads(line)
                                # Parse timestamp and check if recent enough
                                entry_date = datetime.fromisoformat(entry.get('timestamp', ''))
                                if entry_date >= cutoff_date:
                                    entries.append(entry)
                                else:
                                    removed_count += 1
                            except (json.JSONDecodeError, ValueError):
                                # Keep malformed entries (don't know age)
                                entries.append({'raw': line})
                
                # Rewrite log file with remaining entries
                with open(log_file, 'w', encoding='utf-8') as f:
                    for entry in entries:
                        if 'raw' in entry:
                            f.write(entry['raw'] + '\n')
                        else:
                            f.write(json.dumps(entry) + '\n')
            
            logger.info(f"Removed {removed_count} log entries older than {days} days")
            return removed_count
        
        except Exception as e:
            logger.error(f"Error clearing old logs: {e}")
            return 0
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about log files.
        
        Returns:
            Dictionary with log statistics
        
        Example:
            >>> logger = OperationLogger()
            >>> stats = logger.get_log_statistics()
            >>> print(f"Total operations: {stats['total_operations']}")
            >>> print(f"Total errors: {stats['total_errors']}")
        """
        try:
            stats = {
                'total_operations': 0,
                'total_errors': 0,
                'operations_file_size_kb': 0,
                'errors_file_size_kb': 0,
                'oldest_entry': None,
                'newest_entry': None
            }
            
            # Count operations
            if self.operations_log.exists():
                with open(self.operations_log, 'r', encoding='utf-8') as f:
                    stats['total_operations'] = sum(1 for line in f if line.strip())
                stats['operations_file_size_kb'] = self.operations_log.stat().st_size / 1024
            
            # Count errors
            if self.errors_log.exists():
                with open(self.errors_log, 'r', encoding='utf-8') as f:
                    stats['total_errors'] = sum(1 for line in f if line.strip())
                stats['errors_file_size_kb'] = self.errors_log.stat().st_size / 1024
            
            # Get date range
            recent = self.get_recent_logs(count=999999)  # Get all
            if recent:
                stats['oldest_entry'] = recent[-1].get('timestamp')
                stats['newest_entry'] = recent[0].get('timestamp')
            
            return stats
        
        except Exception as e:
            logger.error(f"Error getting log statistics: {e}")
            return {}


# Global operation logger instance
_operation_logger: Optional[OperationLogger] = None


def get_operation_logger() -> OperationLogger:
    """
    Get the global operation logger instance (singleton pattern).
    
    Returns:
        Global OperationLogger instance
    
    Example:
        >>> logger = get_operation_logger()
        >>> logger.log_operation('Test', 'success')
    """
    global _operation_logger
    if _operation_logger is None:
        _operation_logger = OperationLogger()
    return _operation_logger


def log_operation(operation: str, status: str, details: Optional[str] = None) -> bool:
    """
    Convenience function to log operation using global logger.
    
    Args:
        operation: Operation name
        status: Status ('success', 'failure', 'warning', 'info')
        details: Additional details
    
    Returns:
        True if logged successfully
    """
    return get_operation_logger().log_operation(operation, status, details)


def log_error(error_message: str, traceback: Optional[str] = None) -> bool:
    """
    Convenience function to log error using global logger.
    
    Args:
        error_message: Error message
        traceback: Full traceback
    
    Returns:
        True if logged successfully
    """
    return get_operation_logger().log_error(error_message, traceback)
