#!/usr/bin/env python3
"""
BMW N54 Help System - Contextual Documentation and Guidance
============================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Provides contextual help, documentation, and user guidance for
    all Flash Tool features. Organized by category with searchable
    help topics and interactive documentation browser.

Features:
    - Category-based help organization
    - Quick reference guides
    - Safety warnings and best practices
    - Troubleshooting guides
    - Command examples

Classes:
    HelpSystem - Main help content provider

Functions:
    None (class-based module)

Variables (Module-level):
    None
"""

from typing import Dict, List, Optional
from pathlib import Path


class HelpSystem:
    """Provides help content and documentation for Flash Tool."""
    
    # Help topics organized by category
    HELP_TOPICS = {
        'hardware': {
            'title': 'Hardware & Connection',
            'content': """
=== Hardware & Connection Help ===

The Flash Tool connects to your BMW N54 ECU using a K+DCAN cable.

Supported Cables:
- FTDI-based K+DCAN cables (recommended)
- Generic OBD-II adapters with K-line support

Setup Steps:
1. Connect K+DCAN cable to vehicle OBD-II port (under steering wheel)
2. Connect cable to computer USB port
3. Turn ignition to position 2 (ON, engine off)
4. Use 'Scan for COM Ports' to detect the cable
5. Select the correct COM port (usually highlighted as K+DCAN)
6. Test connection before proceeding with operations

Troubleshooting:
- Cable not detected: Check Windows Device Manager for FTDI devices
- Connection fails: Ensure ignition is ON and cable is fully connected
- Multiple COM ports: Look for FTDI chip (VID:0403 PID:6001)
            """
        },
        'diagnostics': {
            'title': 'Diagnostics',
            'content': """
=== Diagnostics Help ===

The Flash Tool provides two levels of diagnostics:

1. OBD-II Diagnostics (Standard):
   - Read engine fault codes (P0xxx, P2xxx)
   - Clear fault codes after repairs
   - Read freeze frame data
   - Check readiness monitors

2. BMW DME/Module Diagnostics (Advanced):
   - Scan all vehicle modules for faults
   - Read DME-specific codes
   - Access N54-specific data (injectors, VANOS, boost)
   - Clear module-specific codes

Best Practices:
- Always document codes before clearing
- Address underlying issues before clearing codes
- Active codes may reappear immediately if problem persists
- Use DME diagnostics for detailed N54 engine data

Safety Notes:
- Never clear codes without understanding the problem
- Some codes indicate serious mechanical issues
- Clearing codes does not fix the underlying problem
            """
        },
        'dme_functions': {
            'title': 'DME-Specific Functions',
            'content': """
=== DME-Specific Functions Help ===

N54-specific diagnostic functions via Direct CAN/UDS:

1. ECU Identification:
   - Read VIN, part numbers, software versions
   - Verify ECU type before flashing

2. Injector Codes:
   - Read injector correction values for all 6 cylinders
   - Values stored in DME for each injector
   - Important for aftermarket injector installations

3. VANOS Data:
   - Intake and exhaust camshaft positions
   - Target vs actual positions
   - Adaptation values

4. Boost/Wastegate Data:
   - Actual vs target boost pressure
   - Wastegate positions (left and right)
   - Overboost/underboost event counters

5. DME Fault Codes:
   - DME-specific codes beyond standard OBD-II
   - Active and stored codes
   - More detailed than generic scanner

Requirements:
- K+DCAN cable or PCAN adapter connected to vehicle
- python-can library installed
            """
        },
        'flash': {
            'title': 'Flash Operations',
            'content': """
=== Flash Operations Help ===

WARNING: Flashing ECU is HIGH RISK!

Flash operations modify your ECU's firmware. Improper flashing can:
- Cause engine damage
- Brick your ECU (expensive to repair)
- Void warranties

Safety Requirements:
1. Create full ECU backup BEFORE any flash
2. Verify battery voltage >12.5V
3. Ensure stable power (use battery maintainer)
4. Never disconnect power during flash
5. Validate map file before flashing

Flash Workflow:
1. Backup current ECU (Task 5.0)
2. Browse and select map file (Task 5.1)
3. Validate map file checksums
4. Confirm VIN matches vehicle
5. Type THREE confirmations to proceed
6. Monitor progress (do NOT interrupt)
7. Verify ECU after flash

Map File Management:
- Store maps in organized VIN-based folders
- Keep original backups separate from tuned maps
- Validate checksums before flashing
- Document all map changes

Recovery Plan:
- Always have backup available
- Know how to restore from backup
- Have emergency recovery tools ready
- Consider professional help if uncertain
            """
        },
        'settings': {
            'title': 'Settings & Configuration',
            'content': """
=== Settings & Configuration Help ===

Configurable Settings:

Paths:
- Maps directory (default: maps/)
- Backups directory (default: backups/)
- Logs directory (default: logs/)

Connection:
- Default COM port (auto-detect if empty)
- Baudrate (default: 38400)
- Connection timeout (default: 5 seconds)

Timeouts:
- Read operation: 30 seconds
- Write operation: 120 seconds
- Diagnostic operation: 30 seconds
- Flash operation: 300 seconds (5 minutes)

Safety:
- Auto-backup before flash (default: enabled)
- Require VIN confirmation (default: enabled)
- Minimum battery voltage: 12.5V

UI Preferences:
- Confirm before clearing codes (default: enabled)
- Show warnings (default: enabled)
- Enable colors (default: enabled)

Logging:
- Log level (INFO, DEBUG, WARNING, ERROR)
- Log retention period (default: 30 days)
- Maximum log file size: 100MB

All settings are stored in config/settings.ini
            """
        },
        'safety': {
            'title': 'Safety Guidelines',
            'content': """
=== Safety Guidelines ===

CRITICAL SAFETY RULES:

Before ANY Operation:
- Read and understand what the operation does
- Create backups before making changes
- Verify correct vehicle (check VIN)
- Ensure stable power supply
- Have recovery plan ready

During Operations:
- Never disconnect power mid-operation
- Do not start engine during flash
- Monitor battery voltage
- Watch for error messages
- Do not interrupt diagnostic operations

After Operations:
- Verify operation completed successfully
- Test basic functionality
- Clear codes only after addressing root cause
- Document all changes made
- Keep logs of operations

Flash-Specific Safety:
- NEVER flash on a running engine
- NEVER flash with low battery
- NEVER flash without backup
- NEVER flash unvalidated maps
- NEVER interrupt a flash operation

Legal & Warranty:
- Flashing may void warranty
- Emissions compliance is user's responsibility
- Tool is for off-road/track use only
- User assumes all liability

If Something Goes Wrong:
1. Do NOT panic
2. Do NOT disconnect power
3. Check error messages
4. Refer to troubleshooting guide
5. Restore from backup if available
6. Seek professional help if needed
            """
        }
    }
    
    @staticmethod
    def get_help(topic: str) -> Optional[str]:
        """
        Get help content for a specific topic.
        
        Args:
            topic: Help topic name
        
        Returns:
            Help content string or None if topic not found
        
        Example:
            >>> help_text = HelpSystem.get_help('diagnostics')
            >>> print(help_text)
        """
        if topic in HelpSystem.HELP_TOPICS:
            return HelpSystem.HELP_TOPICS[topic]['content'].strip()
        return None
    
    @staticmethod
    def get_available_topics() -> List[Dict[str, str]]:
        """
        Get list of available help topics.
        
        Returns:
            List of topic dictionaries with 'name' and 'title'
        
        Example:
            >>> topics = HelpSystem.get_available_topics()
            >>> for topic in topics:
            ...     print(f"{topic['name']}: {topic['title']}")
        """
        topics = []
        for name, info in HelpSystem.HELP_TOPICS.items():
            topics.append({
                'name': name,
                'title': info['title']
            })
        return topics
    
    @staticmethod
    def get_quick_start_guide() -> str:
        """
        Get quick start guide for new users.
        
        Returns:
            Quick start guide text
        """
        return """
=== Flash Tool - Quick Start Guide ===

Welcome to the BMW N54 Flash Tool!

First Time Setup:
1. Install python-can (pip install python-can)
2. Connect K+DCAN cable or PCAN adapter to vehicle
3. Run: python -m flash_tool.cli
4. Navigate to 'Hardware & Connection'
5. Scan and select COM port or CAN interface
6. Test connection

Basic Diagnostic Workflow:
1. Read fault codes (Main Menu → Diagnostics → Read DTCs)
2. Document any codes found
3. Repair underlying issues
4. Clear codes after repairs
5. Verify codes do not return

Advanced Diagnostics:
1. Use DME-specific functions for N54 data
2. Read injector codes, VANOS data, boost data
3. Access detailed ECU information

Before Flashing (CRITICAL):
1. Create FULL ECU backup
2. Validate map file
3. Check battery voltage >12.5V
4. Read safety guidelines
5. Have recovery plan ready

Need Help?
- Main Menu → Help & About → View Documentation
- Read docs/user_guide.md for detailed instructions
- Check logs/ directory for operation history
- Consult safety guidelines before flash operations

Support:
- Documentation: docs/ directory
- Logs: logs/ directory
- Configuration: config/ directory
- Issues: See README.md
        """.strip()
    
    @staticmethod
    def get_troubleshooting_guide() -> str:
        """
        Get common troubleshooting tips.
        
        Returns:
            Troubleshooting guide text
        """
        return """
=== Troubleshooting Guide ===

Connection Issues:
Problem: Cable not detected
- Check USB connection
- Verify FTDI drivers installed
- Check Windows Device Manager
- Try different USB port

Problem: Cannot connect to ECU
- Ensure ignition is ON (position 2)
- Verify cable is K-line compatible
- Check vehicle OBD-II port
- Try different COM port

Diagnostic Issues:
Problem: No fault codes found (but check engine light is on)
- Use DME-specific diagnostics
- Try multi-module scan
- Verify communication is working
- Check with another scanner

Problem: Codes reappear after clearing
- This is normal for active faults
- Repair underlying problem first
- Some codes require drive cycle to clear

Flash Operation Issues:
Problem: CAN adapter not detected
- Check USB connection and driver installation
- Verify PCAN or K+DCAN cable is connected
- Install python-can library if missing

Problem: Communication timeout during flash
- Check battery voltage
- Ensure stable power supply
- Do NOT interrupt - wait for timeout
- May need to restore from backup

Problem: ECU not responding after flash
- Do NOT panic
- Cycle ignition (off, wait 30s, on)
- Attempt to reconnect
- Restore from backup if available
- Seek professional help if needed

Log Issues:
Problem: Log files too large
- Use 'Clear Old Logs' function
- Set lower retention period in settings
- Export and archive old logs

Settings Issues:
Problem: Settings not saving
- Check config/ directory permissions
- Verify config/settings.ini exists
- Try 'Reset to Defaults'

Still Having Issues?
1. Check logs/errors.log for details
2. Enable debug mode in settings
3. Export logs for analysis
4. Consult documentation
5. Seek professional assistance
        """.strip()
    
    @staticmethod
    def get_version_info() -> Dict[str, str]:
        """
        Get version and build information.
        
        Returns:
            Dictionary with version details
        """
        return {
            'version': '0.1.0',
            'status': 'Development',
            'build_date': '2025-11-01',
            'python_required': '3.8+',
            'vehicle': '2008 BMW 535xi (N54)',
            'ecu': 'MSD80/MSD81',
            'author': 'AgentTask7.0'
        }
    
    @staticmethod
    def get_implemented_features() -> List[Dict[str, str]]:
        """
        Get list of implemented features.
        
        Returns:
            List of feature dictionaries with task and status
        """
        return [
            {'task': 'Task 1.0', 'feature': 'Core Project Structure and Interactive CLI', 'status': 'Complete'},
            {'task': 'Task 2.0', 'feature': 'COM Port Scanner with K+DCAN Detection', 'status': 'Complete'},
            {'task': 'Task 3.0', 'feature': 'OBD-II and Multi-Module Diagnostics', 'status': 'Complete'},
            {'task': 'Task 3.1', 'feature': 'Map File Management and Validation', 'status': 'Complete'},
            {'task': 'Task 4.0', 'feature': 'Direct CAN/UDS Communication', 'status': 'Complete'},
            {'task': 'Task 4.1', 'feature': 'N54 DME Diagnostics', 'status': 'Complete'},
            {'task': 'Task 5.0', 'feature': 'Backup, Recovery & Map Export', 'status': 'Complete'},
            {'task': 'Task 5.1', 'feature': 'ECU Flash Operations', 'status': 'Not Started'},
            {'task': 'Task 7.0', 'feature': 'Settings, Configuration & Logging', 'status': 'Complete'},
        ]
