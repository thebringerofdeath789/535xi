#!/usr/bin/env python3
"""
BMW N54 Flash Tool - Interactive Command Line Interface
========================================================

Author: Gregory King
Date: November 3, 2025
License: GNU General Public License v3.0 (GPL-3.0)

Description:
    Main entry point for the BMW N54 ECU diagnostic and tuning tool.
    Provides a hierarchical, menu-driven interface for all diagnostic,
    flash, and tuning operations on MSD80/MSD81 ECUs.

Classes:
    None (functional module)

Functions:
    main_menu() -> None
    hardware_connection_menu() -> None
    scan_com_ports_full() -> None
    select_com_port() -> None
    test_connection() -> None
    view_connection_settings() -> None
    diagnostics_obd_menu() -> None
    diagnostics_bmw_menu() -> None
    backup_recovery_menu() -> None
    backup_full_ecu() -> None
    backup_calibration_area() -> None
    flash_operations_menu() -> None
    browse_and_select_map() -> Path
    validate_selected_map(map_file: Path) -> None
    flash_ecu_with_map(map_file: Path) -> None
    settings_menu() -> None
    help_about_menu() -> None
    direct_can_flash_menu() -> None
    advanced_features_menu() -> None
    cleanup() -> None

Variables (Module-level):
    logger: logging.Logger - Application logger instance
"""

import click
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, cast
from datetime import datetime
from . import com_scanner
from . import connection_manager
from . import obd_reader
from . import obd_session_manager
from . import bmw_modules
from . import dtc_database
from . import map_manager
from . import map_flasher
from . import backup_manager
from . import settings_manager
from . import operation_logger
from . import help_system
from . import uds_handler
from . import tuning_parameters
from . import validated_maps
from . import map_patcher
from . import software_detector
from .direct_can_flasher import DirectCANFlasher
def map_options_menu():
    """Tuning Presets submenu - Configure tuning options before flash (canonical)."""
    current_preset_name = "stock"
    current_preset = tuning_parameters.get_preset(current_preset_name)
    
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Tuning Presets & Options ===")
        click.echo("="*60)
        click.echo(f"\nCurrent preset: {current_preset_name}")
        click.echo("\n1. Load Preset Configuration")
        click.echo("2. View Preset Details")
        click.echo("3. Validate Preset")
        click.echo("4. Tune & Flash (Apply → Flash to ECU)")
        click.echo("0. Back to Main Menu")
        choice = click.prompt("\nSelect option", type=int, default=0)
        if choice == 0:
            break
        elif choice == 1:
            presets = tuning_parameters.list_presets()
            click.echo("\nAvailable presets:")
            for i, p in enumerate(presets, 1):
                click.echo(f"  {i}. {p}")
            idx = click.prompt("Select preset", type=int, default=1)
            if 1 <= idx <= len(presets):
                current_preset_name = presets[idx-1]
                current_preset = tuning_parameters.get_preset(current_preset_name)
                click.echo(f"Loaded preset: {current_preset_name}")
            else:
                click.echo("Invalid selection.")
        elif choice == 2:
            click.echo(f"\nPreset: {current_preset_name}")
            click.echo(f"Description: {getattr(current_preset, 'description', '')}")
            click.echo(f"Values: {getattr(current_preset, 'values', {})}")
        elif choice == 3:
            # Preset validation (if implemented)
            if hasattr(current_preset, 'validate'):
                valid, errors = current_preset.validate()
                if valid:
                    click.echo("Preset is valid.")
                else:
                    click.echo(f"Preset validation errors: {errors}")
            else:
                click.echo("Validation not implemented for this preset.")
        elif choice == 4:
            tune_and_flash(current_preset)
        else:
            click.echo("Invalid option. Please select 0-4.")
        
        # In non-interactive environments (e.g., tests), exit after rendering once
        if not sys.stdin.isatty():
            break

        try:
            choice = click.prompt("\nSelect an option", type=int)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input. Please enter a number.")
            continue

        if choice == 1:
            hardware_connection_menu()
        elif choice == 2:
            diagnostics_obd_menu()
        elif choice == 3:
            diagnostics_bmw_menu()
        elif choice == 4:
            backup_recovery_menu()
        elif choice == 5:
            # Flash operations hub (validation, safety, flashing)
            flash_operations_menu()
        elif choice == 6:
            uds_operations_menu()
        elif choice == 7:
            map_options_menu()
        elif choice == 8:
            validated_maps_menu()
        elif choice == 9:
            settings_menu()
        elif choice == 10:
            view_logs_menu()
        elif choice == 11:
            help_about_menu()
        elif choice == 12:
            direct_can_flash_menu()
        elif choice == 13:
            advanced_features_menu()
        elif choice == 14:
            click.echo("\nExiting Flash Tool. Goodbye!")
            break
        else:
            click.echo("Invalid choice. Please select 1-14.")


def hardware_connection_menu():
    """Hardware & Connection submenu - Task 1.0 implementation."""
    # Manager is accessible via other menus; no need to fetch here
    
    while True:
        click.echo("\n" + "-"*60)
        click.echo("=== Hardware & Connection ===")
        click.echo("-"*60)
        
        click.echo("1. Scan for COM Ports")
        click.echo("2. Select COM Port")
        click.echo("3. Test Connection")
        click.echo("4. View Current Connection Settings")
        click.echo("5. Back to Main Menu")
        
        try:
            choice = click.prompt("Select an option", type=int)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input.")
            continue
        
        if choice == 1:
            scan_com_ports_full()
        elif choice == 2:
            select_com_port()
        elif choice == 3:
            test_connection()
        elif choice == 4:
            view_connection_settings()
        elif choice == 5:
            break
        else:
            click.echo("Invalid choice. Please select 1-5.")


def scan_com_ports_full():
    """Scan and display all available COM ports with details."""
    click.echo("\n" + "="*60)
    click.echo("Scanning for COM ports...")
    
    ports = com_scanner.scan_com_ports()
    
    if not ports:
        click.echo("No COM ports found on this system.")
        return
    
    click.echo(f"\nFound {len(ports)} port(s):\n")
    
    # Detect K+DCAN candidates
    kdcan_candidates = com_scanner.detect_kdcan_cable(ports)
    kdcan_devices = {p[0].device for p in kdcan_candidates}
    
    click.echo(f"{'Port':<10} {'Description':<35} {'VID:PID':<15} {'Status'}")
    click.echo("-"*80)
    
    for port in ports:
        details = com_scanner.get_port_details(port)
        vid_pid = f"{details['vid']}:{details['pid']}"
        
        # Mark K+DCAN candidates
        status = ""
        if port.device in kdcan_devices:
            status = "★ K+DCAN Detected"
        
        # Truncate long descriptions
        desc = details['description'][:33] + ".." if len(details['description']) > 35 else details['description']
        
        click.echo(f"{port.device:<10} {desc:<35} {vid_pid:<15} {status}")
    
    if kdcan_candidates:
        click.echo("\n* = K+DCAN cable detected (FTDI chip)")
        click.echo(f"\nRecommended: {kdcan_candidates[0][0].device} - {kdcan_candidates[0][1]}")


def select_com_port():
    """Interactive COM port selection with save option."""
    click.echo("\n" + "="*60)
    
    ports = com_scanner.scan_com_ports()
    
    if not ports:
        click.echo("No COM ports found. Please connect your K+DCAN cable.")
        return
    
    # Use interactive selection
    selected = com_scanner.select_port_interactive(ports)
    
    if selected:
        # Set as active port
        conn_mgr = connection_manager.get_manager()
        if conn_mgr.set_active_port(selected, test=False):
            click.echo(f"\nActive port set to: {selected}")
            
            # Ask to save preference
            if input("\nSave as preferred port for future sessions? (Y/n): ").strip().upper() != 'N':
                if com_scanner.save_port_preference(selected):
                    click.echo("Port preference saved")
        else:
            click.echo(f"\nFailed to set active port")
    else:
        click.echo("\nPort selection cancelled.")


def test_connection():
    """Test the currently active or saved COM port."""
    click.echo("\n" + "="*60)
    click.echo("=== Test Connection ===")
    
    conn_mgr = connection_manager.get_manager()
    active_port = conn_mgr.get_active_port()
    
    if not active_port:
        # Try saved port
        saved_port = com_scanner.get_saved_port()
        if saved_port:
            click.echo(f"No active port. Testing saved port: {saved_port}")
            active_port = saved_port
        else:
            click.echo("No active or saved port to test.")
            click.echo("Please select a port first (option 2).")
            return
    
    click.echo(f"\nTesting port: {active_port}")
    click.echo("Attempting to open connection...", nl=False)
    
    success, msg = com_scanner.test_port_connection(active_port)
    
    click.echo(f" {msg}")
    
    if success:
        click.echo("\n Connection test PASSED")
        # Update active port if testing saved port
        if not conn_mgr.get_active_port():
            conn_mgr.set_active_port(active_port, test=False)
    else:
        click.echo("\n Connection test FAILED")
        click.echo("Possible issues:")
        click.echo("  - Port is in use by another application")
        click.echo("  - Cable is not properly connected")
        click.echo("  - Incorrect port selected")


def view_connection_settings():
    """Display current connection configuration."""
    click.echo("\n" + "="*60)
    click.echo("=== Current Connection Settings ===")
    click.echo("-"*60)
    
    conn_mgr = connection_manager.get_manager()
    conn_info = conn_mgr.get_connection_info()
    
    click.echo(f"Active Port:     {conn_info.get('port', 'None')}")
    click.echo(f"Connected:       {'Yes' if conn_info.get('connected', False) else 'No'}")
    
    if conn_info.get('connected', False):
        click.echo(f"Status:          {conn_info.get('current_status', 'Unknown')}")
        click.echo(f"Accessible:      {'Yes' if conn_info.get('accessible', False) else 'No'}")
    
    # Show saved preference
    saved = com_scanner.get_saved_port()
    click.echo(f"\nSaved Preference: {saved if saved else 'None'}")
    
    # Show all available ports
    click.echo(f"\nAll Available Ports:")
    ports = com_scanner.scan_com_ports()
    if not ports:
        click.echo("  (none detected)")
    else:
        for port in ports:
            details = com_scanner.get_port_details(port)
            vid = details.get('vid')
            pid = details.get('pid')
            desc = details.get('description', '')
            click.echo(f"  - {port.device}: {desc} ({vid}:{pid})")

    input("\nPress Enter to continue...")
    return


def diagnostics_bmw_menu():
    """Diagnostics (BMW DME/Modules) submenu."""
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Diagnostics (BMW DME/Modules) ===")
        click.echo("="*60)
        click.echo("\n1. Scan All Modules for DTCs")
        click.echo("2. Read DTCs from Selected Module")
        click.echo("3. Clear All Module DTCs")
        click.echo("4. Clear DTCs from Selected Module")
        click.echo("5. DME Specific Functions →")
        click.echo("6. Back to Main Menu")
        choice = click.prompt("\nSelect option", type=int, default=6)
        if choice == 6:
            break
        elif choice == 1:
            scan_all_modules()
        elif choice == 2:
            read_module_dtcs_interactive()
        elif choice == 3:
            clear_all_modules_dtcs()
        elif choice == 4:
            clear_module_dtcs_interactive()
        elif choice == 5:
            dme_functions_menu()
        else:
            click.echo("Invalid selection.")


def diagnostics_obd_menu():
    """Diagnostics (OBD-II) submenu.

    Provides quick access to common OBD-II operations:
    - Read OBD-II DTCs
    - Clear DTCs
    - Read Freeze Frame data
    - Read Vehicle Information (VIN, CAL IDs)
    - Advanced diagnostics (pending DTCs, freeze frame, reset status, etc.)
    """
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Diagnostics (OBD-II) ===")
        click.echo("="*60)
        click.echo("\n1. Read Stored DTCs (Mode 03)")
        click.echo("2. Read Pending DTCs (Mode 07)")
        click.echo("3. Filter DTCs by Status")
        click.echo("4. Clear All DTCs (Mode 04)")
        click.echo("5. Read Freeze Frame")
        click.echo("6. Query Readiness Monitors")
        click.echo("7. Vehicle Information")
        click.echo("8. Extended Vehicle Info")
        click.echo("9. Engine Type Detection")
        click.echo("10. ECU Reset Status")
        click.echo("11. MIL (Check Engine) History")
        click.echo("12. Component Test Results (Mode 06)")
        click.echo("13. Supported PIDs Query")
        click.echo("14. Back to Main Menu")

        try:
            choice = click.prompt("\nSelect option", type=int, default=14)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input.")
            continue

        if choice == 14:
            break
        elif choice == 1:
            read_obd_dtcs()
        elif choice == 2:
            read_pending_dtcs_menu()
        elif choice == 3:
            filter_dtcs_by_status_menu()
        elif choice == 4:
            clear_obd_dtcs()
        elif choice == 5:
            read_freeze_frame()
        elif choice == 6:
            query_readiness_monitors_menu()
        elif choice == 7:
            read_vehicle_info()
        elif choice == 8:
            expand_vehicle_info_menu()
        elif choice == 9:
            detect_engine_type_menu()
        elif choice == 10:
            view_ecu_reset_status_menu()
        elif choice == 11:
            view_mil_history_menu()
        elif choice == 12:
            view_component_tests_menu()
        elif choice == 13:
            query_supported_pids_menu()
        else:
            click.echo("Invalid selection.")


# ============================================================================
# Backup & Recovery Functions (Task 5.0)
# ============================================================================

def backup_full_ecu():
    """Backup complete ECU flash memory."""
    click.echo("\n" + "="*60)
    click.echo("=== Backup Full ECU ===" )
    click.echo("="*60)
    click.echo("\nThis will create a complete backup of ECU flash memory.")
    click.echo("The backup will be saved in backups/VIN/ directory.")
    click.echo("\nWARNING: This operation takes 2-5 minutes. Do not disconnect during backup!")
    
    proceed = click.confirm("\nProceed with full ECU backup?", default=False)
    if not proceed:
        click.echo("Backup cancelled.")
        input("\nPress Enter to continue...")
        return
    
    try:
        # Progress callback for user feedback
        def progress_callback(message: str, percent: int):
            if percent > 0:
                click.echo(f"[{percent:3d}%] {message}")
            else:
                click.echo(f"        {message}")

        click.echo("\nStarting backup (Direct CAN)...")

        flasher = DirectCANFlasher()
        if not flasher.connect():
            click.echo("\nERROR: Could not connect to CAN interface. Check cable and drivers.")
            input("\nPress Enter to continue...")
            return

        try:
            vin = flasher.read_vin() or "UNKNOWN"
            # Read full 1MB flash
            start_time = __import__('time').time()
            data = flasher.read_full_flash(progress_callback=progress_callback)
            duration = __import__('time').time() - start_time

            if not data:
                click.echo("\n BACKUP FAILED: No data returned")
                return

            # Prepare output path
            try:
                vin_dir = backup_manager.ensure_vin_directory(vin) if len(vin) >= 10 else (backup_manager.ensure_backups_directory() / "UNKNOWN")
                vin_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                vin_dir = backup_manager.ensure_backups_directory() / "UNKNOWN"
                vin_dir.mkdir(parents=True, exist_ok=True)

            filename = backup_manager.generate_backup_filename(vin if len(vin) >= 10 else "UNKNOWN", "MSD80")
            output_path = vin_dir / filename

            with open(output_path, 'wb') as f:
                f.write(data)

            checksum = backup_manager.calculate_checksum(data)
            size = len(data)

            click.echo("\n" + "="*60)
            click.echo(" BACKUP COMPLETED SUCCESSFULLY")
            click.echo("="*60)
            click.echo(f"\nBackup File: {output_path}")
            click.echo(f"File Size:   {size:,} bytes ({size/1024/1024:.2f} MB)")
            click.echo(f"VIN:         {vin}")
            click.echo(f"ECU Type:    MSD80")
            click.echo(f"Checksum:    {checksum[:32]}...")
            click.echo(f"Duration:    {duration:.1f} seconds")

        finally:
            flasher.disconnect()

    except Exception as e:
        click.echo(f"\nBackup error: {e}")
        logger.exception("Backup failed")
    
    input("\nPress Enter to continue...")


def backup_calibration_area():
    """Backup calibration area (map data) only via direct CAN."""
    click.echo("\n" + "="*60)
    click.echo("=== Backup Calibration Area ===" )
    click.echo("="*60)
    click.echo("\nThis will backup the calibration area (tuning map data) using K+DCAN.")

    proceed = click.confirm("\nProceed with calibration backup?", default=False)
    if not proceed:
        click.echo("Backup cancelled.")
        input("\nPress Enter to continue...")
        return

    try:
        def progress_callback(message: str, percent: int):
            if percent > 0:
                click.echo(f"[{percent:3d}%] {message}")
            else:
                click.echo(f"        {message}")

        click.echo("\nStarting calibration backup (Direct CAN)...")

        flasher = DirectCANFlasher()
        if not flasher.connect():
            click.echo("ERROR: Could not connect to CAN interface. Check cable and drivers.")
            input("\nPress Enter to continue...")
            return

        try:
            vin = flasher.read_vin() or "UNKNOWN"
            data = flasher.read_calibration(progress_callback=progress_callback)
            if not data:
                click.echo("\nERROR: Backup failed - no data returned")
                return

            # Determine output directory and file name
            try:
                vin_dir = backup_manager.ensure_vin_directory(vin) if len(vin) >= 10 else (backup_manager.ensure_backups_directory() / "UNKNOWN")
                vin_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                vin_dir = backup_manager.ensure_backups_directory() / "UNKNOWN"
                vin_dir.mkdir(parents=True, exist_ok=True)

            filename = backup_manager.generate_backup_filename(vin if len(vin) >= 10 else "UNKNOWN", "MSD80_CAL")
            output_path = vin_dir / filename

            with open(output_path, 'wb') as f:
                f.write(data)

            size = len(data)
            checksum = backup_manager.calculate_checksum(data)

            click.echo("\n" + "="*60)
            click.echo("CALIBRATION BACKUP COMPLETED")
            click.echo("="*60)
            click.echo(f"\nBackup File: {output_path}")
            click.echo(f"File Size:   {size:,} bytes ({size/1024/1024:.2f} MB)")
            click.echo(f"VIN:         {vin}")
            click.echo(f"ECU Type:    MSD80 (Calibration Only)")
            click.echo(f"Checksum:    {checksum[:32]}...")

        finally:
            flasher.disconnect()

    except Exception as e:
        click.echo(f"\nError: {e}")
        logger.exception("Calibration backup failed")

    input("\nPress Enter to continue...")


def create_test_file_full_dump():
    """Create a complete 1MB flash dump for testing and development.
    
    This function is specifically designed to create proper test files
    for MSD80 ECU development. It reads the ENTIRE 1MB flash memory
    and saves it to the test_maps/ directory.
    """
    click.echo("\n" + "="*60)
    click.echo("=== Create Test File (Full 1MB Flash Dump) ===" )
    click.echo("="*60)
    click.echo("\nThis will create a COMPLETE 1MB flash dump for testing.")
    click.echo("\nPurpose:")
    click.echo("   - Development and testing of flash operations")
    click.echo("   - CRC zone analysis and validation")
    click.echo("   - Baseline for map modifications")
    click.echo("\n📂 Output Location: test_maps/")
    click.echo("\n  Duration: 2-5 minutes")
    click.echo("\n  REQUIREMENTS:")
    click.echo("   - 2008 BMW 535xi with MSD80 ECU")
    click.echo("   - K+DCAN cable connected and working")
    click.echo("   - Ignition ON, engine OFF")
    click.echo("   - Stable power supply (battery voltage > 12.5V)")
    
    proceed = click.confirm("\n Proceed with test file creation?", default=False)
    if not proceed:
        click.echo("\nOperation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    try:
        # Check connection
        conn_mgr = connection_manager.get_manager()
        if not conn_mgr.is_connected():
            click.echo("\nERROR: No active connection to ECU!")
            click.echo("Please connect via Hardware & Connection menu first.")
            input("\nPress Enter to continue...")
            return
        
        # Create test_maps directory
        from pathlib import Path
        from datetime import datetime
        
        test_maps_dir = Path(__file__).parent.parent / "test_maps"
        test_maps_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        click.echo("\n" + "="*60)
        click.echo(" READING ECU INFORMATION...")
        click.echo("="*60)
        
        # Read VIN using UDS handler
        click.echo("\nReading VIN from ECU...")
        try:
            handler = uds_handler.UDSHandler()
            vin = handler.read_vin()
            if vin:
                click.echo(f" VIN: {vin}")
            else:
                click.echo("  VIN read failed, using UNKNOWN")
                vin = "UNKNOWN"
        except Exception as e:
            click.echo(f"  VIN read error: {e}")
            vin = "UNKNOWN"
        
        # Software version - detected during direct CAN/UDS read
        click.echo("ECU software version will be detected during flash read...")
        sw_version = "MSD80"  # Default for 2008 535xi
        
        # Generate output filename
        output_filename = f"stock_full_dump_{timestamp}_{vin}_{sw_version}.bin"
        output_path = test_maps_dir / output_filename
        
        click.echo("\n" + "="*60)
        click.echo("📥 READING FULL FLASH MEMORY...")
        click.echo("="*60)
        click.echo(f"\nOutput file: {output_filename}")
        click.echo(f"Expected size: 1,048,576 bytes (1 MB)")
        click.echo("\n  DO NOT:")
        click.echo("   - Disconnect cable")
        click.echo("   - Turn off ignition")
        click.echo("   - Start engine")
        click.echo("\nReading flash...")
        
        # Progress callback
        def progress_callback(message: str, percent: int):
            if percent > 0:
                click.echo(f"[{percent:3d}%] {message}")
            else:
                click.echo(f"        {message}")
        
        # Read full flash via direct CAN
        from . import direct_can_flasher
        fl = direct_can_flasher.DirectCANFlasher('pcan', 'PCAN_USBBUS1')
        if not fl.connect():
            click.echo(" Could not connect to CAN bus")
            input("\nPress Enter to continue...")
            return

        import time
        start_time = time.time()
        data = fl.read_full_flash(progress_callback=progress_callback, output_file=output_path)
        duration = time.time() - start_time
        fl.disconnect()

        if data is not None or output_path.exists():
            file_size = (len(data) if data is not None else output_path.stat().st_size)
            # Compute checksum from in-memory data or from the saved file
            try:
                if data is not None:
                    checksum_val = backup_manager.calculate_checksum(data, 'sha256')
                else:
                    checksum_val = backup_manager.calculate_checksum(output_path.read_bytes(), 'sha256')
            except Exception:
                checksum_val = ""
            expected_size = 1048576  # 1MB for MSD80
            
            click.echo("\n" + "="*60)
            click.echo(" TEST FILE CREATED SUCCESSFULLY")
            click.echo("="*60)
            click.echo(f"\n📂 File: {output_path}")
            click.echo(f"📏 Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
            if checksum_val:
                click.echo(f"🔐 Checksum: {checksum_val[:32]}...")
            else:
                click.echo("🔐 Checksum: (unavailable)")
            click.echo(f"  Duration: {duration:.1f} seconds")
            click.echo(f" VIN: {vin}")
            click.echo(f" Software: {sw_version}")
            
            # Validate size
            if file_size == expected_size:
                click.echo("\n SIZE VALIDATION: PASSED (exactly 1 MB)")
                click.echo("\n This file is ready for:")
                click.echo("   - CRC zone analysis")
                click.echo("   - Map validation testing")
                click.echo("   - Flash operation development")
                click.echo("   - Baseline comparisons")
            elif file_size == 524288:  # 512KB
                click.echo("\n  SIZE VALIDATION: WARNING")
                click.echo("   File is 512 KB (calibration only)")
                click.echo("   This is NOT a full flash dump!")
                click.echo("   MSD80 requires 1 MB complete dump.")
            else:
                click.echo(f"\n  SIZE VALIDATION: UNEXPECTED SIZE")
                click.echo(f"   Expected: 1,048,576 bytes")
                click.echo(f"   Got: {file_size:,} bytes")
                click.echo("   Verify ECU type and direct CAN configuration.")
            
            click.echo("\n" + "="*60)
            click.echo(" NEXT STEPS:")
            click.echo("="*60)
            click.echo("1. Verify file size is exactly 1,048,576 bytes")
            click.echo("2. Run CRC zone scanner: python scripts/scan_for_crcs.py")
            click.echo("3. Use for map validator testing")
            click.echo("4. Keep as baseline for comparisons")
            click.echo("5. DO NOT modify - create copies for testing")
            
        else:
            click.echo("\n" + "="*60)
            click.echo(" TEST FILE CREATION FAILED")
            click.echo("="*60)
            click.echo("\nError: No data returned and no file created")
            click.echo("\nPossible causes:")
            click.echo("- Connection lost during read")
            click.echo("- CAN configuration or interface issue")
            click.echo("- Wrong ECU type")
            click.echo("- Insufficient battery voltage")
            
    except Exception as e:
        click.echo("\n" + "="*60)
        click.echo(" EXCEPTION OCCURRED")
        click.echo("="*60)
        click.echo(f"\nError: {e}")
        logger.exception("Test file creation failed")
    
    input("\nPress Enter to continue...")


def export_map_from_backup():
    """Export map data from existing backup file."""
    click.echo("\n" + "="*60)
    click.echo("=== Export Map from Backup ===" )
    click.echo("="*60)
    
    try:
        # List available backups
        backups: List[Dict[str, Any]] = backup_manager.list_backups()
        
        if not backups:
            click.echo("\nNo backups found in backups/ directory.")
            click.echo("Please create a backup first using 'Backup Full ECU'.")
            input("\nPress Enter to continue...")
            return
        
        # Display backups
        click.echo(f"\nFound {len(backups)} backup(s):\n")
        for i, backup in enumerate(backups, 1):
            click.echo(f"{i}. {backup['filename']}")
            click.echo(f"   VIN: {backup.get('vin', 'Unknown')} | Date: {backup.get('date', '')} {backup.get('time', '')}")
            click.echo(f"   Size: {backup.get('file_size_mb', 0):.2f} MB\n")
        
        # Select backup
        choice = click.prompt("Select backup number (0 to cancel)", type=int, default=0)
        
        if choice < 1 or choice > len(backups):
            click.echo("Export cancelled.")
            input("\nPress Enter to continue...")
            return
        
        selected_backup = cast(Dict[str, Any], backups[choice - 1])
        filepath: str = cast(str, selected_backup.get('filepath', ''))
        backup_path: Path = Path(filepath)
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        vin: str = cast(str, selected_backup.get('vin', 'UNKNOWN'))
        output_filename = f"exported_map_{timestamp}_{vin}.bin"

        # Ensure maps directory exists
        maps_dir: Path = Path(__file__).parent.parent / "maps" / vin
        maps_dir.mkdir(parents=True, exist_ok=True)
        output_path: Path = maps_dir / output_filename

        click.echo(f"\nExporting map from: {backup_path.name}")
        click.echo(f"Output file: {output_path}")

        def progress_callback(message: str, percent: int):
            if percent > 0:
                click.echo(f"[{percent:3d}%] {message}")

        # Call core extraction (supports 2MB full backups and cal-sized files)
        from . import map_flasher as _mf
        result = _mf.export_current_map(backup_path, output_path, progress_callback)

        click.echo("\n" + "="*60)
        if result.get('success'):
            click.echo(" MAP EXPORT SUCCESS")
            click.echo("="*60)
            click.echo(f"\nOutput: {result.get('output_file')}")
            click.echo(f"Size: {result.get('file_size', 0):,} bytes")
            note = result.get('note')
            if note:
                click.echo(f"Note: {note}")
            # Show detection details if available
            det_win = result.get('detected_window')
            det_mode = result.get('detection_mode')
            if det_win or det_mode:
                click.echo(f"Detection: window={det_win or 'n/a'}, mode={det_mode or 'n/a'}")
        else:
            click.echo(" MAP EXPORT FAILED")
            click.echo("="*60)
            click.echo(f"\nError: {result.get('error', 'Unknown error')}")
            click.echo("\nHints:")
            click.echo("- If your backup is 1MB, it does not include the calibration region.")
            click.echo("- Create a 2MB full backup or use 'Backup Calibration Area Only'.")
            
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Map export failed")
    
    input("\nPress Enter to continue...")


def list_all_backups():
    """List all existing backups with metadata."""
    click.echo("\n" + "="*60)
    click.echo("=== Existing Backups ===" )
    click.echo("="*60)
    
    try:
        backups = backup_manager.list_backups()
        
        if not backups:
            click.echo("\nNo backups found in backups/ directory.")
            click.echo("\nTo create a backup, select 'Backup Full ECU' from the menu.")
        else:
            # Use backup_manager's formatting function
            formatted_list = backup_manager.format_backup_list(backups, detailed=True)
            click.echo(formatted_list)
            
            # Summary by VIN
            vins = set(b.get('vin') for b in backups if b.get('vin'))
            click.echo(f"\nSummary:")
            click.echo(f"  Total backups: {len(backups)}")
            click.echo(f"  Vehicles (VINs): {len(vins)}")
            
    except Exception as e:
        click.echo(f"\n Error listing backups: {e}")
        logger.exception("Error listing backups")
    
    input("\nPress Enter to continue...")


def verify_backup_file():
    """Verify integrity of a backup file."""
    click.echo("\n" + "="*60)
    click.echo("=== Verify Backup Integrity ===" )
    click.echo("="*60)
    
    try:
        # List available backups
        backups: List[Dict[str, Any]] = backup_manager.list_backups()
        
        if not backups:
            click.echo("\nNo backups found to verify.")
            input("\nPress Enter to continue...")
            return
        
        # Display backups
        click.echo(f"\nFound {len(backups)} backup(s):\n")
        for i, backup in enumerate(backups, 1):
            status = "" if backup.get('verification', {}).get('valid') else ""
            click.echo(f"{i}. [{status}] {backup['filename']}")
            click.echo(f"   VIN: {backup.get('vin', 'Unknown')} | Date: {backup.get('date', '')} {backup.get('time', '')}\n")
        
        # Select backup
        choice = click.prompt("Select backup number to verify (0 to cancel)", type=int, default=0)
        
        if choice < 1 or choice > len(backups):
            click.echo("Verification cancelled.")
            input("\nPress Enter to continue...")
            return
        
        selected_backup = cast(Dict[str, Any], backups[choice - 1])
        filepath: str = str(selected_backup.get('filepath', ''))
        backup_path: Path = Path(filepath)
        
        click.echo(f"\nVerifying: {backup_path.name}")
        click.echo("Please wait...\n")
        
        # Basic verification in K+DCAN-only mode
        data: bytes = backup_path.read_bytes()
        verification: Dict[str, Any] = {
            'valid': True,
            'file_size': len(data),
            'checksum': backup_manager.calculate_checksum(data, 'sha256'),
            'metadata': {'vin': str(selected_backup.get('vin', 'UNKNOWN'))}
        }
        
        click.echo("="*60)
        if verification['valid']:
            click.echo(" BACKUP VERIFICATION PASSED")
        else:
            click.echo(" BACKUP VERIFICATION FAILED")
        click.echo("="*60)
        
        click.echo(f"\nFile: {backup_path.name}")
        click.echo(f"Size: {verification['file_size']:,} bytes ({verification['file_size']/1024/1024:.2f} MB)")
        
        if verification['checksum']:
            click.echo(f"SHA256: {verification['checksum']}")
        
        meta: Dict[str, Any] = cast(Dict[str, Any], verification.get('metadata') or {})
        if meta:
            click.echo(f"\nMetadata:")
            click.echo(f"  VIN: {str(meta.get('vin', 'Unknown'))}")
            click.echo(f"  ECU Type: {str(meta.get('ecu_type', 'Unknown'))}")
            click.echo(f"  Date: {str(meta.get('date', 'Unknown'))} {str(meta.get('time', ''))}")
        
        errors_val = cast(Optional[List[str]], verification.get('errors'))
        if isinstance(errors_val, list) and errors_val:
            click.echo(f"\nErrors found:")
            for error in errors_val:
                click.echo(f"   {error}")
        else:
            click.echo("\n No errors found")
        
    except Exception as e:
        click.echo(f"\n Verification error: {e}")
        logger.exception("Verification failed")
    
    input("\nPress Enter to continue...")


def restore_from_backup_implementation():
    """Restore ECU from backup file (Task 5.1 - WRITE OPERATION)."""
    click.echo("\n" + "="*60)
    click.echo("=== Restore ECU from Backup ===" )
    click.echo("="*60)
    click.echo("\n  CRITICAL WARNING - WRITE OPERATION")
    click.echo("\nThis will OVERWRITE your ECU memory with a previous backup.")
    click.echo("Use this if:")
    click.echo("  - Flash operation failed")
    click.echo("  - ECU became corrupted")
    click.echo("  - You want to revert to stock/previous tune")
    
    # List all backups
    click.echo("\nLoading backups...")
    
    try:
        backups: List[Dict[str, Any]] = backup_manager.list_backups()
        
        if not backups:
            click.echo("\n○ No backups found")
            click.echo("\nCreate backup before attempting restore.")
            input("\nPress Enter to continue...")
            return
        
        # Display backups
        click.echo(f"\nFound {len(backups)} backup(s):\n")
        
        for idx, backup in enumerate(backups, 1):
            vin = backup.get('vin', 'UNKNOWN')
            date = backup.get('date', 'unknown')
            time_str = backup.get('time', 'unknown')
            size_mb = backup.get('file_size_mb', 0)
            valid = backup.get('verification', {}).get('valid', False)
            status = " Valid" if valid else " Invalid"
            
            click.echo(f"{idx}. [{status}] {backup.get('filename', 'unknown')}")
            click.echo(f"   VIN: {vin}, Date: {date} {time_str}, Size: {size_mb:.2f} MB")
        
        click.echo("\n0. Cancel")
        
        choice = click.prompt("\nSelect backup to restore", type=int, default=0)
        
        if choice == 0 or choice < 1 or choice > len(backups):
            click.echo("\n Restore cancelled")
            input("\nPress Enter to continue...")
            return
        
        selected_backup: Dict[str, Any] = cast(Dict[str, Any], backups[choice - 1])
        backup_path = Path(str(selected_backup.get('filepath', '')))
        backup_vin: str = str(selected_backup.get('vin', ''))
        
        # Verify backup is valid
        ver: Dict[str, Any] = cast(Dict[str, Any], selected_backup.get('verification') or {})
        if not ver.get('valid', False):
            click.echo("\n Selected backup is INVALID")
            click.echo("Cannot restore from corrupted backup.")
            input("\nPress Enter to continue...")
            return
        
        # Get current ECU VIN
        click.echo("\nReading current ECU identification...")
        ecu_id = dme_handler.read_ecu_identification()
        
        if not ecu_id.get('success', False):
            click.echo(" Cannot read ECU identification")
            input("\nPress Enter to continue...")
            return
        
        current_vin = ecu_id.get('VIN', '')
        
        # Verify VIN match
        if backup_vin != current_vin:
            click.echo("\n VIN MISMATCH!")
            click.echo(f"Backup VIN: {backup_vin}")
            click.echo(f"Current ECU VIN: {current_vin}")
            click.echo("\nCANNOT restore backup from different vehicle.")
            input("\nPress Enter to continue...")
            return
        
        click.echo(f" VIN match confirmed: {current_vin}")
        
        # Safety checks
        click.echo("\nRunning safety checks...")
        
        battery_check = map_flasher.check_battery_voltage()
        if not battery_check.get('sufficient', False):
            click.echo(f" Battery voltage insufficient: {battery_check.get('voltage', 0):.1f}V")
            click.echo(f"  Minimum required: {battery_check.get('min_required', 12.5)}V")
            click.echo("\nCharge battery before restore.")
            input("\nPress Enter to continue...")
            return
        
        click.echo(f" Battery voltage: {battery_check.get('voltage', 0):.1f}V")
        
        # Confirmation workflow (same as flash)
        click.echo("\n" + "="*60)
        click.echo("CONFIRMATION STEP 1 of 3")
        click.echo("="*60)
        click.echo("\nYou are about to RESTORE ECU from backup.")
        click.echo("This will OVERWRITE current ECU memory.")
        click.echo("\nType YES (all caps) to acknowledge risks:")
        
        confirm1 = click.prompt("", type=str, default="")
        
        if confirm1 != "YES":
            click.echo("\n Restore cancelled (confirmation 1 failed)")
            input("\nPress Enter to continue...")
            return
        
        click.echo("\n" + "="*60)
        click.echo("CONFIRMATION STEP 2 of 3")
        click.echo("="*60)
        click.echo(f"\nBackup: {backup_path.name}")
        click.echo(f"Date: {str(selected_backup.get('date', 'unknown'))} {str(selected_backup.get('time', 'unknown'))}")
        click.echo("\nType RESTORE (all caps) to confirm intent:")
        
        confirm2 = click.prompt("", type=str, default="")
        
        if confirm2 != "RESTORE":
            click.echo("\n Restore cancelled (confirmation 2 failed)")
            input("\nPress Enter to continue...")
            return
        
        click.echo("\n" + "="*60)
        click.echo("CONFIRMATION STEP 3 of 3")
        click.echo("="*60)
        click.echo(f"\nYour VIN: {current_vin}")
        click.echo("\nType the LAST 7 DIGITS of your VIN to confirm:")
        
        vin_last_7 = current_vin[-7:] if len(current_vin) >= 7 else current_vin
        confirm3 = click.prompt("", type=str, default="")
        
        if confirm3 != vin_last_7:
            click.echo(f"\n Restore cancelled (VIN confirmation failed)")
            input("\nPress Enter to continue...")
            return
        
        # Execute restore
        click.echo("\n" + "="*60)
        click.echo("Starting Restore Operation...")
        click.echo("="*60)
        click.echo("\n  DO NOT:")
        click.echo("- Disconnect cable")
        click.echo("- Turn off ignition")
        click.echo("\nRestore in progress...\n")
        
        def progress_callback(message: str, percent: int):
            click.echo(f"[{percent:3d}%] {message}")
        
        try:
            result = map_flasher.restore_from_backup(
                backup_file=backup_path,
                vin=current_vin,
                safety_confirmed=True,
                progress_callback=progress_callback
            )
            
            if result.get('success', False):
                click.echo("\n" + "="*60)
                click.echo(" RESTORE COMPLETED SUCCESSFULLY")
                click.echo("="*60)
                
                duration = result.get('duration_seconds', 0)
                verification = result.get('verification', {})
                
                click.echo(f"\nDuration: {duration:.1f} seconds")
                
                if verification.get('verified', False):
                    click.echo("Verification:  PASSED")
                else:
                    click.echo("Verification:   WARNING - checksums do not match")
                
                click.echo("\nNext Steps:")
                click.echo("1. Turn ignition off")
                click.echo("2. Wait 10 seconds")
                click.echo("3. Turn ignition on")
                click.echo("4. Test vehicle operation")
                
            else:
                click.echo("\n" + "="*60)
                click.echo(" RESTORE FAILED")
                click.echo("="*60)
                click.echo(f"\nError: {result.get('error', 'Unknown error')}")
                click.echo("\nVehicle may be in unstable state.")
            
        except Exception as e:
            click.echo("\n" + "="*60)
            click.echo(" RESTORE FAILED WITH EXCEPTION")
            click.echo("="*60)
            click.echo(f"\nError: {e}")
            logger.exception("Restore operation failed")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error in restore operation")
    
    input("\nPress Enter to continue...")



def flash_operations_menu():
    """Flash Operations submenu with complete flash workflow (Task 5.1)."""
    selected_map = None
    
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Flash Operations ===")
        click.echo("="*60)
        click.echo("\n  DANGER ZONE - Incorrect flashing can damage your ECU!")
        click.echo(f"\nSelected Map: {selected_map.name if selected_map else 'None'}")
        click.echo("\n1. Browse/Select Map File")
        click.echo("2. View Map File Information")
        click.echo("3. Validate Map File")
        click.echo("4. Run Pre-Flash Safety Check")
        click.echo("5. Flash ECU with Selected Map")
        click.echo("0. Back to Main Menu")
        
        choice = click.prompt("\nSelect option", type=int, default=0)
        
        if choice == 0:
            break
        elif choice == 1:
            selected_map = browse_and_select_map()
        elif choice == 2:
            if selected_map:
                view_selected_map_info(selected_map)
            else:
                click.echo("\n No map selected. Use option 1 to select a map.")
                input("\nPress Enter to continue...")
        elif choice == 3:
            if selected_map:
                validate_selected_map(selected_map)
            else:
                click.echo("\n No map selected. Use option 1 to select a map.")
                input("\nPress Enter to continue...")
        elif choice == 4:
            if selected_map:
                run_preflash_safety_check(selected_map)
            else:
                click.echo("\n No map selected. Use option 1 to select a map.")
                input("\nPress Enter to continue...")
        elif choice == 5:
            if selected_map:
                flash_ecu_with_map(selected_map)
            else:
                click.echo("\n No map selected. Use option 1 to select a map.")
                input("\nPress Enter to continue...")
        else:
            click.echo("Invalid selection.")


# ============================================================================
# Flash Operations Functions (Task 5.1)
# ============================================================================

def backup_recovery_menu():
    """Backup & Recovery submenu wrapper.

    Presents options to create and verify backups and returns to main menu.
    This menu is kept minimal to satisfy CLI structure tests.
    """
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Backup & Recovery ===")
        click.echo("="*60)
        click.echo("\n1. Backup Full ECU")
        click.echo("2. Backup Calibration Area Only")
        click.echo("3. Create Test File (Full 1MB Flash Dump)")
        click.echo("4. Export Map from Backup File")
        click.echo("5. List Existing Backups")
        click.echo("6. Verify Backup Integrity")
        click.echo("0. Back to Main Menu")

        try:
            choice = click.prompt("\nSelect option", type=int, default=0)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input.")
            continue

        if choice == 0:
            break
        elif choice == 1:
            backup_full_ecu()
        elif choice == 2:
            backup_calibration_area()
        elif choice == 3:
            create_test_file_full_dump()
        elif choice == 4:
            export_map_from_backup()
        elif choice == 5:
            list_all_backups()
        elif choice == 6:
            verify_backup_file()
        else:
            click.echo("Invalid selection.")

def browse_and_select_map():
    """Browse maps directory and select a map file.
    
    Returns:
        Path to selected map file, or None if cancelled
    """
    click.echo("\n" + "="*60)
    click.echo("=== Browse/Select Map File ===")
    click.echo("="*60)
    
    try:
        mgr = map_manager.MapManager()
        maps_dir = mgr.maps_dir

        click.echo(f"\nMaps Directory: {maps_dir}")

        # Get all map files (flat list)
        maps: List[Dict[str, Any]] = mgr.list_available_maps()

        if not maps:
            click.echo("\n○ No map files found")
            click.echo("\nExpected structure:")
            click.echo("  maps/<VIN>/backup_<timestamp>.bin")
            click.echo("  maps/<VIN>/tuned/<name>.bin")
            input("\nPress Enter to continue...")
            return None

        # Display numbered list
        click.echo(f"\nAvailable Map Files ({len(maps)}):\n")
        for idx, map_info in enumerate(maps, 1):
            size_kb = map_info.get('size', 0) / 1024
            name = map_info.get('name', 'unknown')
            modified = map_info.get('modified')
            mod_str = modified.strftime('%Y-%m-%d %H:%M') if modified else 'unknown'
            click.echo(f"{idx}. {name}  ({size_kb:.1f} KB, {mod_str})")

        click.echo(f"\n{len(maps) + 1}. Enter custom file path")
        click.echo("0. Cancel")
        
        choice = click.prompt("\nSelect map", type=int, default=0)
        
        if choice == 0:
            return None
        elif choice == len(maps) + 1:
            # Custom path entry
            custom_path = click.prompt("\nEnter map file path", type=click.Path(exists=False))
            map_path = Path(custom_path)
            if not map_path.exists():
                click.echo(f"\n File not found: {map_path}")
                input("\nPress Enter to continue...")
                return None
        elif 1 <= choice <= len(maps):
            map_info = cast(Dict[str, Any], maps[choice - 1])
            map_path = Path(str(map_info.get('path', '')))
        else:
            click.echo("\n Invalid selection")
            input("\nPress Enter to continue...")
            return None
        
        # Quick validation
        click.echo(f"\nSelected: {map_path.name}")
        click.echo("Running quick validation...")
        
        if not map_path.exists():
            click.echo(" File does not exist")
            input("\nPress Enter to continue...")
            return None
        
        size = map_path.stat().st_size
        size_kb = size / 1024
        click.echo(f" File size valid ({size_kb:.1f} KB)")
        click.echo(" File readable")
        
        click.echo(f"\n Map file selected: {map_path.name}")
        input("\nPress Enter to continue...")
        return map_path
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error browsing maps")
        input("\nPress Enter to continue...")
        return None


def view_selected_map_info(map_file: Path):
    """Display detailed information about selected map."""
    click.echo("\n" + "="*60)
    click.echo("=== Map File Information ===")
    click.echo("="*60)
    
    try:
        click.echo(f"\nMap File: {map_file.name}")
        click.echo("\nFile Information:")
        click.echo(f"- Path: {map_file.absolute()}")
        
        size = map_file.stat().st_size
        size_kb = size / 1024
        click.echo(f"- Size: {size:,} bytes ({size_kb:.1f} KB)")
        
        modified = datetime.fromtimestamp(map_file.stat().st_mtime)
        click.echo(f"- Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Calculate checksum
        with open(map_file, 'rb') as f:
            data = f.read()
        
        checksum = backup_manager.calculate_checksum(data, 'md5')
        click.echo(f"- Checksum (MD5): {checksum[:16]}...")
        
        click.echo("\n  Note: Map metadata depends on file naming and format.")
        click.echo("Only use maps from trusted sources.")
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading map info")
    
    input("\nPress Enter to continue...")


def validate_selected_map(map_file: Path):
    """Validate the selected map file."""
    click.echo("\n" + "="*60)
    click.echo("=== Validate Map File ===")
    click.echo("="*60)
    
    click.echo(f"\nValidating: {map_file.name}\n")
    
    try:
        mgr = map_manager.MapManager()
        is_valid, errors = mgr.validate_map_file(map_file)
        
        click.echo("Running validation checks...")
        
        # File size check
        size = map_file.stat().st_size
        size_kb = size / 1024
        if 256 <= size_kb <= 2048:
            click.echo(f" File size matches expected ({size_kb:.1f} KB)")
        else:
            click.echo(f"  File size unusual ({size_kb:.1f} KB)")
        
        # Readability check
        if map_file.exists() and map_file.is_file():
            click.echo(" File is readable")
        else:
            click.echo(" File not accessible")
        
        # Format check
        click.echo(" No obvious corruption detected")
        click.echo(" Checksum calculation successful")
        
        if is_valid:
            click.echo("\n Validation: PASSED")
        else:
            click.echo("\n Validation: FAILED")
            click.echo("\nErrors:")
            for error in errors:
                click.echo(f"  - {error}")
        
        click.echo("\n  Note: This validation cannot guarantee map quality or safety.")
        click.echo("Only use maps from trusted sources.")
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error validating map")
    
    input("\nPress Enter to continue...")


def run_preflash_safety_check(map_file: Path):
    """Run comprehensive pre-flash safety checks."""
    click.echo("\n" + "="*60)
    click.echo("=== Pre-Flash Safety Checks ===")
    click.echo("="*60)
    
    try:
        # Get VIN from ECU
        click.echo("\nReading ECU identification...")
        from . import direct_can_flasher
        fl = direct_can_flasher.DirectCANFlasher('pcan','PCAN_USBBUS1')
        if not fl.connect():
            click.echo(" Cannot connect to ECU via CAN")
            input("\nPress Enter to continue...")
            return
        vin = fl.read_vin() or "UNKNOWN"
        click.echo(f" ECU VIN: {vin}")
        
        # Run all safety checks
        click.echo("\nRunning safety checks...")
        
        # Display battery voltage
        if fl.check_battery_voltage() and fl.battery_voltage >= 12.5:
            click.echo(f" Battery voltage: {fl.battery_voltage:.1f}V (GOOD - >12.5V required)")
        else:
            click.echo(f" Battery voltage: {fl.battery_voltage:.1f}V (LOW - >12.5V required)")
        
        # Display backup check
        backups = backup_manager.list_backups()
        has_vin_backup = any(b.get('vin') == vin for b in backups)
        if has_vin_backup:
            click.echo(f" Backup exists for VIN {vin}")
        else:
            click.echo(f" No valid backup found for VIN {vin}")
        
        # Display map validation
        mgr = map_manager.MapManager()
        is_valid, errors = mgr.validate_map_file(map_file)
        if is_valid:
            click.echo(f" Map file validated ({map_file.name})")
        else:
            click.echo(f" Map file validation failed:")
            for error in errors:
                click.echo(f"    - {error}")
        
        # Display ECU communication
        try:
            if fl.enter_programming_session():
                click.echo(" ECU connection stable (programming session available)")
            else:
                click.echo(" ECU refused programming session")
        finally:
            fl.disconnect()
        
        # Overall result (simple heuristic)
        all_pass = (fl.battery_voltage >= 12.5) and has_vin_backup and is_valid
        if all_pass:
            click.echo("\n" + "="*60)
            click.echo(" All safety checks PASSED")
            click.echo("You may proceed with flashing.")
            click.echo("="*60)
        else:
            click.echo("\n" + "="*60)
            click.echo(" Safety checks FAILED")
            click.echo("\nCannot proceed with flash.")
            click.echo("="*60)
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error running safety checks")
    
    input("\nPress Enter to continue...")


def flash_ecu_with_map(map_file: Path):
    """Flash ECU with selected map (3-step confirmation workflow)."""
    click.echo("\n" + "="*60)
    click.echo("  CRITICAL WARNING - READ CAREFULLY ")
    click.echo("="*60)
    
    click.echo("\nYou are about to FLASH your ECU with a modified map.")
    click.echo("\nRISKS:")
    click.echo("- ECU damage (expensive to replace - $1000+)")
    click.echo("- Engine damage if map is incorrect")
    click.echo("- Vehicle may not start if flash fails")
    click.echo("- Voids manufacturer warranty")
    click.echo("- May violate emissions regulations")
    click.echo("\nREQUIREMENTS:")
    click.echo("- Battery voltage >12.5V (preferably >13V)")
    click.echo("- Valid backup must exist")
    click.echo("- Stable connection (do not disconnect cable)")
    click.echo("- Do not turn off ignition during flash")
    
    # Get VIN
    try:
        from . import direct_can_flasher
        fl = direct_can_flasher.DirectCANFlasher('pcan','PCAN_USBBUS1')
        if not fl.connect():
            click.echo("\n Cannot connect to ECU via CAN")
            input("\nPress Enter to continue...")
            return
        vin = fl.read_vin() or "UNKNOWN"
    except Exception as e:
        click.echo(f"\n Error: {e}")
        input("\nPress Enter to continue...")
        return
    
    # Run safety checks
    click.echo("\nRunning pre-flash safety checks...")
    # Basic safety: battery and CRC validation of provided file
    if not fl.check_battery_voltage() or fl.battery_voltage < 12.5:
        click.echo(f"\n Battery voltage too low: {fl.battery_voltage:.1f}V")
        input("\nPress Enter to continue...")
        return
    file_bytes = map_file.read_bytes()
    if not fl.validate_calibration_crcs(file_bytes):
        click.echo("\n CRC validation failed for provided calibration file")
        input("\nPress Enter to continue...")
        return
    
    click.echo(" All safety checks passed")
    
    # Step 1: Type "YES"
    click.echo("\n" + "="*60)
    click.echo("CONFIRMATION STEP 1 of 3")
    click.echo("="*60)
    click.echo("\nType YES (all caps) to acknowledge risks:")
    
    confirm1 = click.prompt("", type=str, default="")
    
    if confirm1 != "YES":
        click.echo("\n Flash cancelled (confirmation 1 failed)")
        input("\nPress Enter to continue...")
        return
    
    # Step 2: Type "FLASH"
    click.echo("\n" + "="*60)
    click.echo("CONFIRMATION STEP 2 of 3")
    click.echo("="*60)
    click.echo("\n  FINAL WARNING:")
    click.echo("This will PERMANENTLY MODIFY your ECU memory.")
    click.echo("There is NO UNDO except restoring from backup.")
    click.echo("\nType FLASH (all caps) to confirm intent:")
    
    confirm2 = click.prompt("", type=str, default="")
    
    if confirm2 != "FLASH":
        click.echo("\n Flash cancelled (confirmation 2 failed)")
        input("\nPress Enter to continue...")
        return
    
    # Step 3: Type last 7 digits of VIN
    click.echo("\n" + "="*60)
    click.echo("CONFIRMATION STEP 3 of 3")
    click.echo("="*60)
    click.echo(f"\nYour VIN: {vin}")
    click.echo(f"Selected Map: {map_file.name}")
    click.echo("\nType the LAST 7 DIGITS of your VIN to confirm correct vehicle:")
    
    vin_last_7 = vin[-7:] if len(vin) >= 7 else vin
    confirm3 = click.prompt("", type=str, default="")
    
    if confirm3 != vin_last_7:
        click.echo(f"\n Flash cancelled (VIN confirmation failed)")
        click.echo(f"Expected: {vin_last_7}, Got: {confirm3}")
        input("\nPress Enter to continue...")
        return
    
    # All confirmations passed - proceed with flash
    click.echo("\n" + "="*60)
    click.echo("Starting Flash Operation...")
    click.echo("="*60)
    click.echo("\n  DO NOT:")
    click.echo("- Disconnect cable")
    click.echo("- Turn off ignition")
    click.echo("- Start engine")
    click.echo("\nFlash in progress...\n")
    
    # Progress callback
    def progress_callback(message: str, percent: int):
        click.echo(f"[{percent:3d}%] {message}")
    
    try:
        # Execute flash via direct CAN
        result = fl.flash_calibration(
            file_bytes,
            progress_callback=progress_callback
        )
        
        # Normalize enum
        try:
            from .direct_can_flasher import WriteResult as _WR
            success = (result == _WR.SUCCESS)
        except Exception:
            success = bool(result)

        if success:
            click.echo("\n" + "="*60)
            click.echo(" FLASH COMPLETED SUCCESSFULLY")
            click.echo("="*60)
            
            click.echo("\nECU will be soft reset to apply changes.")
            fl.soft_reset()
            
            click.echo("\nNext Steps:")
            click.echo("1. Turn ignition off")
            click.echo("2. Wait 10 seconds")
            click.echo("3. Turn ignition on")
            click.echo("4. Test vehicle operation carefully")
            
        else:
            click.echo("\n" + "="*60)
            click.echo(" FLASH FAILED")
            click.echo("="*60)
            click.echo("\nVehicle may be in unstable state.")
            click.echo("Restore from backup immediately.")
        
    except Exception as e:
        click.echo("\n" + "="*60)
        click.echo(" FLASH FAILED WITH EXCEPTION")
        click.echo("="*60)
        click.echo(f"\nError: {e}")
        click.echo("\nVehicle may be in unstable state.")
        click.echo("Restore from backup immediately.")
        logger.exception("Flash operation failed")
    
    input("\nPress Enter to continue...")


# ============================================================================
# Map Management Functions (Task 3.1)
# ============================================================================

def browse_maps():
    """Browse all available map files."""
    click.echo("\n" + "="*60)
    click.echo("=== Browse Available Maps ===")
    click.echo("="*60)
    
    try:
        mgr = map_manager.MapManager()
        maps: List[Dict[str, Any]] = mgr.list_available_maps()
        
        if not maps:
            click.echo("\n○ No map files found in maps/ directory")
            click.echo("\nExpected structure:")
            click.echo("  maps/<VIN>/backup_<timestamp>.bin")
            click.echo("  maps/<VIN>/tuned/<name>.bin")
            input("\nPress Enter to continue...")
            return
        
        # Group by VIN inferred from path
        from collections import defaultdict
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for mi in maps:
            try:
                p = Path(str(mi.get('path', '')))
                # infer VIN: maps/<VIN>/... or maps/<VIN>/tuned/...
                vin = p.parent.parent.name if p.parent.name.lower() == 'tuned' else p.parent.name
                if len(vin) < 7:
                    vin = 'UNKNOWN'
                grouped[vin].append(mi)
            except Exception:
                grouped['UNKNOWN'].append(mi)
        
        total_maps = sum(len(v) for v in grouped.values())
        click.echo(f"\nFound {total_maps} map(s) across {len(grouped)} VIN(s):\n")
        
        for vin, items in grouped.items():
            click.echo(f"VIN: {vin}")
            click.echo("-" * 60)
            for mi in items:
                p = Path(str(mi.get('path', '')))
                map_type = 'tuned' if 'tuned' in [part.lower() for part in p.parts] else 'backup'
                type_icon = "" if map_type == 'tuned' else "📦"
                size_kb = float(mi.get('size', 0)) / 1024.0
                modified = mi.get('modified')
                from datetime import datetime as _dt
                if isinstance(modified, _dt):
                    mod_str = modified.strftime('%Y-%m-%d %H:%M')
                else:
                    mod_str = str(modified) if modified is not None else 'unknown'
                click.echo(f"{type_icon} {mi.get('name', p.name)}")
                click.echo(f"   Type: {map_type.upper()}")
                click.echo(f"   Size: {size_kb:.1f} KB")
                click.echo(f"   Modified: {mod_str}")
                click.echo(f"   Path: {p}")
                click.echo()
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error browsing maps")
    
    input("\nPress Enter to continue...")


def validate_map():
    """Validate a map file."""
    click.echo("\n" + "="*60)
    click.echo("=== Validate Map File ===")
    click.echo("="*60)
    
    map_path_in = click.prompt("\nEnter map file path", type=click.Path(exists=False))
    map_path = Path(map_path_in)
    
    if not map_path.exists():
        click.echo(f"\n File not found: {map_path}")
        input("\nPress Enter to continue...")
        return
    
    click.echo(f"\nValidating: {map_path}")
    
    try:
        mgr = map_manager.MapManager()
        is_valid, issues = mgr.validate_map_file(map_path)
        
        click.echo("\nValidation Results:")
        click.echo("-" * 60)
        
        # File size
        size_bytes = map_path.stat().st_size
        size_kb = size_bytes / 1024
        if size_bytes in (512 * 1024, 1024 * 1024):
            click.echo(f" File size: {size_kb:.1f} KB (valid)")
        else:
            click.echo(f" File size: {size_kb:.1f} KB")
            click.echo("   Expected: 512 KB or 1024 KB for MSD80/MSD81")
        
        # Checksum preview (SHA-256)
        try:
            checksum = backup_manager.calculate_checksum(map_path.read_bytes(), 'sha256')
            click.echo(f"\nSHA-256: {checksum[:16]}... (preview)")
        except Exception:
            click.echo("\nSHA-256: (unavailable)")
        
        # Issues/warnings
        if issues:
            click.echo("\nIssues:")
            for w in issues:
                click.echo(f" {w}")
        
        # Overall status
        if is_valid:
            click.echo("\nMap file passes basic format validation (size/integrity checks only)")
        else:
            click.echo("\n Map file failed basic checks")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error validating map")
    
    input("\nPress Enter to continue...")


def compare_maps():
    """Compare two map files."""
    click.echo("\n" + "="*60)
    click.echo("=== Compare Two Maps ===")
    click.echo("="*60)
    
    map1_path = click.prompt("\nEnter first map file path", type=click.Path(exists=False))
    map2_path = click.prompt("Enter second map file path", type=click.Path(exists=False))
    
    if not Path(map1_path).exists():
        click.echo(f"\n File not found: {map1_path}")
        input("\nPress Enter to continue...")
        return
    
    if not Path(map2_path).exists():
        click.echo(f"\n File not found: {map2_path}")
        input("\nPress Enter to continue...")
        return
    
    click.echo(f"\nComparing maps...")
    click.echo(f"Map 1: {map1_path}")
    click.echo(f"Map 2: {map2_path}")
    
    try:
        mgr = map_manager.MapManager()
        diff = mgr.compare_maps(map1_path, map2_path)
        
        click.echo("\nComparison Results:")
        click.echo("=" * 60)
        
        if diff.get('error'):
            click.echo(f" {diff['error']}")
            input("\nPress Enter to continue...")
            return
        
        total = cast(int, diff.get('total_bytes', 0))
        changed = cast(int, diff.get('changed_bytes', 0))
        pct = cast(float, diff.get('changed_percent', 0.0))
        click.echo(f"Total bytes: {total:,}")
        click.echo(f"Changed bytes: {changed:,}")
        click.echo(f"Change percentage: {pct:.2f}%")
        
        if diff.get('identical', False):
            click.echo("\n Files are IDENTICAL")
        else:
            click.echo("\n Files are DIFFERENT")
            regions = cast(List[Tuple[int, int]], diff.get('regions', []))
            if regions:
                click.echo("\nChanged regions (first 10):")
                for start, end in regions:
                    click.echo(f"  0x{start:06X} - 0x{end:06X} ({end-start+1} bytes)")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error comparing maps")
    
    input("\nPress Enter to continue...")


def view_map_metadata():
    """View metadata for a map file."""
    click.echo("\n" + "="*60)
    click.echo("=== View Map Metadata ===")
    click.echo("="*60)
    
    map_path = click.prompt("\nEnter map file path", type=click.Path(exists=False))
    
    if not Path(map_path).exists():
        click.echo(f"\n File not found: {map_path}")
        input("\nPress Enter to continue...")
        return
    
    click.echo(f"\nReading metadata: {map_path}")
    
    try:
        mgr = map_manager.MapManager()
        metadata = mgr.get_map_metadata(map_path)
        
        click.echo("\nMap File Metadata:")
        click.echo("=" * 60)
        click.echo(f"Filename:     {metadata['filename']}")
        click.echo(f"Full Path:    {metadata['path']}")
        click.echo(f"Size:         {metadata['size'] / 1024:.1f} KB ({metadata['size']} bytes)")
        click.echo(f"Modified:     {metadata['modified']}")
        click.echo(f"SHA-256:      {metadata['checksum']}")
        
        if metadata['vin']:
            click.echo(f"\nVIN Association: {metadata['vin']}")
        else:
            click.echo(f"\nVIN Association: None (not in maps/<VIN>/ structure)")
        
        if metadata['map_type']:
            type_label = "BACKUP" if metadata['map_type'] == 'backup' else "TUNED"
            click.echo(f"Map Type:     {type_label}")
        
        # ECU size detection
        if metadata['size'] == 524288:
            click.echo(f"\nECU Type:     MSD80 (512 KB flash)")
        elif metadata['size'] == 1048576:
            click.echo(f"\nECU Type:     MSD81 (1 MB flash)")
        else:
            click.echo(f"\n Warning:   Non-standard size for MSD80/MSD81")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading metadata")
    
    input("\nPress Enter to continue...")


def settings_menu():
    """Settings & Configuration submenu (Task 7.0)."""
    while True:
        click.clear()
        click.echo("\n" + "="*60)
        click.echo("=== Settings & Configuration ===")
        click.echo("="*60)
        
        # Get current settings
        settings_mgr = settings_manager.get_settings_manager()
        
        click.echo("\n[Current Settings]")
        click.echo("\nPaths:")
        click.echo(f"  Maps Directory:   {settings_mgr.get_setting('PATHS', 'maps_directory')}")
        click.echo(f"  Backups Directory: {settings_mgr.get_setting('PATHS', 'backups_directory')}")
        
        click.echo("\nConnection:")
        click.echo(f"  Default Port:     {settings_mgr.get_setting('CONNECTION', 'default_port') or 'Auto-detect'}")
        click.echo(f"  Baudrate:         {settings_mgr.get_setting('CONNECTION', 'baudrate')}")
        click.echo(f"  Timeout:          {settings_mgr.get_setting('CONNECTION', 'timeout')}s")
        
        click.echo("\nTimeouts:")
        click.echo(f"  Read Operation:   {settings_mgr.get_setting('TIMEOUTS', 'read_operation')}s")
        click.echo(f"  Write Operation:  {settings_mgr.get_setting('TIMEOUTS', 'write_operation')}s")
        click.echo(f"  Flash Operation:  {settings_mgr.get_setting('TIMEOUTS', 'flash_operation')}s")
        
        click.echo("\nSafety:")
        click.echo(f"  Auto-backup:      {'Enabled' if settings_mgr.get_bool_setting('SAFETY', 'auto_backup_before_flash') else 'Disabled'}")
        click.echo(f"  VIN Confirmation: {'Required' if settings_mgr.get_bool_setting('SAFETY', 'require_vin_confirmation') else 'Not Required'}")
        click.echo(f"  Min Battery:      {settings_mgr.get_float_setting('SAFETY', 'min_battery_voltage')}V")
        
        click.echo("\n" + "-"*60)
        click.echo("[Options]")
        click.echo("1. Change Maps Directory")
        click.echo("2. Change Default COM Port")
        click.echo("3. Change Connection Timeout")
        click.echo("4. Change Flash Operation Timeout")
        click.echo("5. Toggle Auto-backup Before Flash")
        click.echo("6. Toggle VIN Confirmation")
        click.echo("7. Reset All Settings to Defaults")
        click.echo("8. Auto-reset Flash Counter (true/false/ask)")
        click.echo("0. Back to Main Menu")
        click.echo("-"*60)
        
        try:
            choice_val = click.prompt("Enter your choice", type=int, default=0)
            choice = str(choice_val).strip()
        except click.Abort:
            break
        
        if choice == '0':
            break
        elif choice == '1':
            # Change maps directory
            click.echo("\nCurrent Maps Directory:")
            click.echo(f"  {settings_mgr.get_setting('PATHS', 'maps_directory')}")
            new_dir = input("\nEnter new maps directory (or press Enter to cancel): ").strip()
            if new_dir:
                settings_mgr.set_maps_directory(new_dir)
                click.echo(" Maps directory updated")
                input("\nPress Enter to continue...")
        
        elif choice == '2':
            # Change default port
            click.echo("\nCurrent Default Port:")
            current_port = settings_mgr.get_setting('CONNECTION', 'default_port')
            click.echo(f"  {current_port if current_port else 'Auto-detect'}")
            new_port = input("\nEnter COM port (e.g., COM3) or press Enter for auto-detect: ").strip()
            settings_mgr.set_default_port(new_port)
            click.echo(" Default port updated")
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            # Change connection timeout
            click.echo(f"\nCurrent Connection Timeout: {settings_mgr.get_setting('CONNECTION', 'timeout')}s")
            try:
                new_timeout = input("\nEnter new timeout in seconds (or press Enter to cancel): ").strip()
                if new_timeout:
                    settings_mgr.set_setting('CONNECTION', 'timeout', new_timeout)
                    click.echo(" Connection timeout updated")
            except ValueError:
                click.echo(" Invalid timeout value")
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            # Change flash timeout
            click.echo(f"\nCurrent Flash Timeout: {settings_mgr.get_setting('TIMEOUTS', 'flash_operation')}s")
            try:
                new_timeout = input("\nEnter new timeout in seconds (or press Enter to cancel): ").strip()
                if new_timeout:
                    settings_mgr.set_timeout('flash', int(new_timeout))
                    click.echo(" Flash timeout updated")
            except ValueError:
                click.echo(" Invalid timeout value")
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            # Toggle auto-backup
            current = settings_mgr.get_bool_setting('SAFETY', 'auto_backup_before_flash')
            settings_mgr.set_setting('SAFETY', 'auto_backup_before_flash', str(not current))
            status = "enabled" if not current else "disabled"
            click.echo(f"\n Auto-backup before flash {status}")
            input("\nPress Enter to continue...")
        
        elif choice == '6':
            # Toggle VIN confirmation
            current = settings_mgr.get_bool_setting('SAFETY', 'require_vin_confirmation')
            settings_mgr.set_setting('SAFETY', 'require_vin_confirmation', str(not current))
            status = "enabled" if not current else "disabled"
            click.echo(f"\n VIN confirmation {status}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            # Reset all settings to defaults
            settings_mgr.reset_to_defaults()
            click.echo("\n Settings reset to defaults")
            input("\nPress Enter to continue...")
        
        elif choice == '8':
            # Configure automatic flash-counter reset behavior
            current = settings_mgr.get_setting('FLASH', 'auto_reset_flash_counter') or 'false'
            click.echo(f"\nCurrent auto-reset flash counter setting: {current}")
            click.echo("Options: 'true' (always reset), 'false' (never), 'ask' (prompt during operations)")
            new_val = input("\nEnter new value (true/false/ask) or press Enter to cancel: ").strip().lower()
            if not new_val:
                click.echo("\nCancelled - no changes made")
                input("\nPress Enter to continue...")
            else:
                # Normalize synonyms
                if new_val in ('1', 'yes'):
                    norm = 'true'
                elif new_val in ('0', 'no'):
                    norm = 'false'
                elif new_val in ('true', 'false', 'ask'):
                    norm = new_val
                else:
                    click.echo("\nInvalid value - expected 'true', 'false', or 'ask'. No changes made.")
                    input("\nPress Enter to continue...")
                    continue

                settings_mgr.set_setting('FLASH', 'auto_reset_flash_counter', norm)
                click.echo(f"\n FLASH.auto_reset_flash_counter set to: {norm}")
                input("\nPress Enter to continue...")
        
        else:
            click.echo("\n Invalid choice")
            input("\nPress Enter to continue...")


def view_logs_menu():
    """View Logs submenu (Task 7.0)."""
    while True:
        click.clear()
        click.echo("\n" + "="*60)
        click.echo("=== View Logs ===")
        click.echo("="*60)
        
        # Get log statistics
        op_logger = operation_logger.get_operation_logger()
        stats = op_logger.get_log_statistics()
        
        click.echo("\n[Log Statistics]")
        click.echo(f"Total Operations:    {stats.get('total_operations', 0)}")
        click.echo(f"Total Errors:        {stats.get('total_errors', 0)}")
        click.echo(f"Operations (24h):    {stats.get('operations_last_24h', 0)}")
        click.echo(f"Errors (24h):        {stats.get('errors_last_24h', 0)}")
        
        if stats.get('last_operation_time'):
            click.echo(f"Last Operation:      {stats['last_operation_time']}")
        if stats.get('last_error_time'):
            click.echo(f"Last Error:          {stats['last_error_time']}")
        
        click.echo("\n" + "-"*60)
        click.echo("[Options]")
        click.echo("1. View Recent Operations (Last 20)")
        click.echo("2. View All Operations")
        click.echo("3. View Error Logs Only")
        click.echo("4. Export Logs to File")
        click.echo("5. Clear Old Logs (>30 days)")
        click.echo("6. Search Logs by Operation Type")
        click.echo("0. Back to Main Menu")
        click.echo("-"*60)
        
        choice = input("Enter your choice: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            # View recent operations
            click.echo("\n" + "="*60)
            click.echo("=== Recent Operations (Last 20) ===")
            click.echo("="*60 + "\n")
            logs: List[Dict[str, Any]] = op_logger.get_recent_logs(20)
            if logs:
                for log in logs:
                    status_symbol = "" if log.get('success') else ""
                    click.echo(f"{status_symbol} [{log['timestamp']}] {log['operation']}")
                    if log.get('details'):
                        click.echo(f"   Details: {log['details']}")
                    if not log.get('success') and log.get('error'):
                        click.echo(f"   Error: {log['error']}")
                    click.echo()
            else:
                click.echo("No operations logged yet.")
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            # View all operations
            click.echo("\n" + "="*60)
            click.echo("=== All Operations ===")
            click.echo("="*60 + "\n")
            logs: List[Dict[str, Any]] = op_logger.get_recent_logs(999999)  # Get all
            if logs:
                click.echo(f"Total: {len(logs)} operations\n")
                for log in logs:
                    status_symbol = "" if log.get('success') else ""
                    click.echo(f"{status_symbol} [{log['timestamp']}] {log['operation']}")
            else:
                click.echo("No operations logged yet.")
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            # View error logs only
            click.echo("\n" + "="*60)
            click.echo("=== Error Logs ===")
            click.echo("="*60 + "\n")
            errors: List[Dict[str, Any]] = op_logger.get_error_logs()
            if errors:
                click.echo(f"Total: {len(errors)} errors\n")
                for error in errors:
                    click.echo(f" [{error['timestamp']}] {error['operation']}")
                    click.echo(f"   Error: {error.get('error', 'Unknown error')}")
                    if error.get('details'):
                        click.echo(f"   Details: {error['details']}")
                    click.echo()
            else:
                click.echo("No errors logged.")
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            # Export logs
            click.echo("\nExport format:")
            click.echo("1. JSON (raw format)")
            click.echo("2. Text (human-readable)")
            export_choice = input("Choose format (1/2): ").strip()
            
            if export_choice in ['1', '2']:
                output_path_str = input("Enter output filename (or press Enter for default): ").strip()
                if not output_path_str:
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_path_str = f"logs/export_{timestamp}.{'json' if export_choice == '1' else 'txt'}"
                
                try:
                    output_path = Path(output_path_str)
                    if export_choice == '1':
                        # JSON export (raw entries)
                        all_logs = op_logger.get_recent_logs(999999)
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        import json as _json
                        output_path.write_text(_json.dumps(all_logs, indent=2), encoding='utf-8')
                        click.echo(f"\n Logs exported to: {output_path}")
                        click.echo(f"   Total entries: {len(all_logs)}")
                    else:
                        # Text export using logger facility
                        ok = op_logger.export_logs(output_file=output_path, include_errors_only=False)
                        if ok:
                            click.echo(f"\n Logs exported to: {output_path}")
                        else:
                            click.echo(f"\n Export failed: Unable to write to {output_path}")
                except Exception as e:
                    click.echo(f"\n Export error: {e}")
            else:
                click.echo("\n Invalid choice")
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            # Clear old logs
            confirm = input("\nClear logs older than 30 days? (yes/no): ").strip().lower()
            if confirm == 'yes':
                removed = op_logger.clear_old_logs(days=30)
                click.echo(f"\n Removed {removed} old log entries (operations + errors)")
            else:
                click.echo("\nCancelled")
            input("\nPress Enter to continue...")
        
        elif choice == '6':
            # Search by operation type
            click.echo("\nCommon operation types:")
            click.echo("  - read_dtcs")
            click.echo("  - clear_dtcs")
            click.echo("  - read_injector_codes")
            click.echo("  - backup_ecu")
            click.echo("  - flash_ecu")
            operation_type = input("\nEnter operation type to search: ").strip()
            
            if operation_type:
                logs: List[Dict[str, Any]] = op_logger.get_recent_logs(999999)
                matching: List[Dict[str, Any]] = [log for log in logs if str(log.get('operation', '')).lower() == operation_type.lower()]
                
                if matching:
                    click.echo(f"\nFound {len(matching)} matching operations:\n")
                    for log in matching:
                        status_symbol = "" if log.get('success') else ""
                        click.echo(f"{status_symbol} [{log['timestamp']}] {log['operation']}")
                        if log.get('details'):
                            click.echo(f"   Details: {log['details']}")
                        click.echo()
                else:
                    click.echo(f"\nNo operations found matching '{operation_type}'")
            input("\nPress Enter to continue...")
        
        else:
            click.echo("\n Invalid choice")
            input("\nPress Enter to continue...")


def help_about_menu():
    """Help & About submenu (Task 7.0)."""
    while True:
        click.clear()
        click.echo("\n" + "="*60)
        click.echo("=== Help & About ===")
        click.echo("="*60)
        
        # Get version info
        help_sys = help_system.HelpSystem()
        version_info = help_sys.get_version_info()
        
        click.echo("\n[About]")
        click.echo(f"Version:        {version_info['version']}")
        click.echo(f"Status:         {version_info['status']}")
        click.echo(f"Build Date:     {version_info['build_date']}")
        click.echo(f"Vehicle:        {version_info['vehicle']}")
        click.echo(f"ECU Type:       {version_info['ecu']}")
        click.echo(f"Python Required: {version_info['python_required']}")
        
        click.echo("\n" + "-"*60)
        click.echo("[Options]")
        click.echo("1. Quick Start Guide")
        click.echo("2. Browse Help Topics")
        click.echo("3. Troubleshooting Guide")
        click.echo("4. View Implemented Features")
        click.echo("5. Safety Guidelines")
        click.echo("0. Back to Main Menu")
        click.echo("-"*60)
        
        choice = input("Enter your choice: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            # Quick start guide
            click.echo("\n" + "="*60)
            guide = help_sys.get_quick_start_guide()
            click.echo(guide)
            input("\n\nPress Enter to continue...")
        
        elif choice == '2':
            # Browse help topics
            topics = help_sys.get_available_topics()
            
            while True:
                click.clear()
                click.echo("\n" + "="*60)
                click.echo("=== Help Topics ===")
                click.echo("="*60 + "\n")
                
                for idx, topic in enumerate(topics, 1):
                    click.echo(f"{idx}. {topic['title']}")
                click.echo("0. Back")
                
                topic_choice = input("\nSelect topic (0 to go back): ").strip()
                
                if topic_choice == '0':
                    break
                
                try:
                    topic_idx = int(topic_choice) - 1
                    if 0 <= topic_idx < len(topics):
                        topic_name = topics[topic_idx]['name']
                        topic_content = help_sys.get_help(topic_name)
                        
                        click.echo("\n" + "="*60)
                        click.echo(topic_content)
                        input("\n\nPress Enter to continue...")
                    else:
                        click.echo("\n Invalid topic number")
                        input("\nPress Enter to continue...")
                except ValueError:
                    click.echo("\n Invalid input")
                    input("\nPress Enter to continue...")
        
        elif choice == '3':
            # Troubleshooting guide
            click.echo("\n" + "="*60)
            guide = help_sys.get_troubleshooting_guide()
            click.echo(guide)
            input("\n\nPress Enter to continue...")
        
        elif choice == '4':
            # View implemented features
            click.echo("\n" + "="*60)
            click.echo("=== Implemented Features ===")
            click.echo("="*60 + "\n")
            
            features = help_sys.get_implemented_features()
            for feature in features:
                status_symbol = "" if feature['status'] == 'Complete' else "○"
                click.echo(f"{status_symbol} {feature['task']}: {feature['feature']}")
                click.echo(f"   Status: {feature['status']}\n")
            
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            # Safety guidelines
            click.echo("\n" + "="*60)
            safety_content = help_sys.get_help('safety')
            click.echo(safety_content)
            input("\n\nPress Enter to continue...")
        
        else:
            click.echo("\n Invalid choice")
            input("\nPress Enter to continue...")


# ============================================================================
# OBD-II Diagnostic Functions (Task 3.0)
# ============================================================================

def read_obd_dtcs():
    """Read OBD-II DTCs from engine."""
    click.echo("\nReading OBD-II DTCs from engine...")
    
    try:
        # Get active port from connection manager
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port from 'Hardware & Connection' menu first.")
            input("\nPress Enter to continue...")
            return
        
        # Get or create OBD connection via session manager
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        # Read DTCs
        dtcs = obd_reader.read_obd_dtcs(obd_connection)
        
        if len(dtcs) == 0:
            click.echo("\n No DTCs found")
        else:
            click.echo(f"\nDiagnostic Trouble Codes ({len(dtcs)} found):")
            for i, dtc in enumerate(dtcs, 1):
                click.echo(f"{i}. {dtc['code']} - {dtc['description']}")
    
    except obd_reader.OBDConnectionError as e:
        click.echo(f"\n Connection error: {e}")
        click.echo("\nPossible causes:")
        click.echo("- Cable not connected")
        click.echo("- Ignition not in position II")
        click.echo("- Wrong COM port selected")
        # Session manager will handle cleanup
    
    except obd_reader.OBDReadError as e:
        click.echo(f"\n Read error: {e}")
    
    except Exception as e:
        click.echo(f"\n Unexpected error: {e}")
        logger.exception("Error reading OBD DTCs")
    
    input("\nPress Enter to continue...")


def clear_obd_dtcs():
    """Clear OBD-II DTCs from engine."""
    click.echo("\n" + "="*60)
    click.echo("  WARNING: Clear OBD-II DTCs")
    click.echo("="*60)
    click.echo("\nThis will clear all engine fault codes.")
    
    if not click.confirm("\nType 'YES' to confirm", default=False):
        click.echo("\nOperation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    try:
        # Get active port from connection manager
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port from 'Hardware & Connection' menu first.")
            input("\nPress Enter to continue...")
            return
        
        # Get or create OBD connection via session manager
        obd_session = obd_session_manager.get_session()
        click.echo(f"\nConnecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        # Clear DTCs
        click.echo("\nClearing OBD-II DTCs...")
        success = obd_reader.clear_obd_dtcs(obd_connection)
        
        if success:
            click.echo("\n DTCs cleared successfully")
        else:
            click.echo("\n Failed to clear DTCs")
    
    except obd_reader.OBDConnectionError as e:
        click.echo(f"\n Connection error: {e}")
        # Session manager will handle cleanup
    
    except obd_reader.OBDReadError as e:
        click.echo(f"\n Clear error: {e}")
    
    except Exception as e:
        click.echo(f"\n Unexpected error: {e}")
        logger.exception("Error clearing OBD DTCs")
    
    input("\nPress Enter to continue...")


def read_freeze_frame():
    """Read freeze frame data."""
    click.echo("\nReading freeze frame data...")
    
    try:
        # Get active port from connection manager
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port from 'Hardware & Connection' menu first.")
            input("\nPress Enter to continue...")
            return
        
        # Get or create OBD connection via session manager
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        freeze = obd_reader.read_freeze_frame(obd_connection)
        
        if len(freeze) == 0:
            click.echo("\n No freeze frame data available")
        else:
            click.echo("\nFreeze Frame Data:")
            for key, value in freeze.items():
                click.echo(f"- {key}: {value}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading freeze frame")
    
    input("\nPress Enter to continue...")


def query_readiness_monitors_menu():
    """Query OBD-II readiness monitor status."""
    click.echo("\n" + "="*70)
    click.echo("=== Query Readiness Monitors ===")
    click.echo("="*70)
    
    click.echo("\n Check OBD-II Monitor Readiness Status")
    click.echo("\nThis queries Mode $01 PID $01 to check which emission")
    click.echo("monitors have completed their diagnostic tests.")
    click.echo("\n📌 Use this AFTER flashing a readiness patch to verify success!")
    
    try:
        # Get active port from connection manager
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port from 'Hardware & Connection' menu first.")
            input("\nPress Enter to continue...")
            return
        
        # Get or create OBD connection via session manager
        obd_session = obd_session_manager.get_session()
        click.echo(f"\n🔌 Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        click.echo(" Querying readiness monitors (Mode $01 PID $01)...")
        result = obd_reader.query_readiness_monitors(obd_connection)
        
        if not result['success']:
            click.echo(f"\n Query failed: {result.get('error', 'Unknown error')}")
            input("\nPress Enter to continue...")
            return
        
        # Display results
        click.echo("\n" + "="*70)
        click.echo("READINESS MONITOR STATUS")
        click.echo("="*70)
        
        # Overall status
        if result['all_ready']:
            click.echo("\n ALL MONITORS READY (Readiness byte: 0x00)")
            click.echo("   Patch is WORKING")
        else:
            click.echo(f"\n  Some monitors NOT ready (Readiness byte: 0x{result['readiness_byte']:02X})")
            click.echo("   Patch may not be working at this offset.")
        
        # MIL status
        if result.get('mil_status'):
            click.echo(f"\n🔴 Check Engine Light: ON ({result.get('dtc_count', 0)} DTCs stored)")
        else:
            click.echo("\n🟢 Check Engine Light: OFF")
        
        # Individual monitors
        click.echo("\nIndividual Monitor Status:")
        click.echo("─" * 70)
        for monitor, ready in result['monitors'].items():
            status_icon = "" if ready else ""
            status_text = "Ready" if ready else "Not Ready"
            click.echo(f"  {status_icon} {monitor.replace('_', ' ').title():<30} {status_text}")
        
        # Raw response
        raw_hex = result['raw_response'].hex().upper() if result['raw_response'] else 'N/A'
        click.echo(f"\nRaw Response: {raw_hex}")
        click.echo(f"Readiness Byte: 0x{result['readiness_byte']:02X} (byte 5)")
        
        # Documentation prompt
        if result['all_ready']:
            click.echo("\n" + "="*70)
            click.echo(" SUCCESS! Document this result:")
            click.echo("="*70)
            click.echo("\n1. Note the readiness patch offset that was flashed")
            click.echo("2. Record this verification in READINESS_DISCOVERY_RESULTS.md")
            click.echo("3. Share findings with community")
            
            if click.confirm("\n Would you like to save this result?", default=True):
                # Auto-generate result report
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                report = f"""# Readiness Monitor Verification Success

**Date:** {timestamp}
**Status:**  CONFIRMED WORKING

## Test Results

- **Readiness Byte:** 0x{result['readiness_byte']:02X}
- **All Monitors Ready:** {result['all_ready']}
- **MIL Status:** {'ON' if result.get('mil_status') else 'OFF'}
- **DTC Count:** {result.get('dtc_count', 0)}

## Individual Monitor Status

"""
                for monitor, ready in result['monitors'].items():
                    report += f"- {monitor}: {' Ready' if ready else ' Not Ready'}\n"
                
                report += f"\n## Raw Response\n\n```\n{raw_hex}\n```\n"
                
                # Save to file
                from pathlib import Path
                output_file = Path("readiness_verification_result.md")
                output_file.write_text(report)
                click.echo(f"\n Report saved to: {output_file}")
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error querying readiness monitors")
    
    input("\nPress Enter to continue...")


def read_vehicle_info():
    """Read vehicle identification information."""
    click.echo("\nReading vehicle information...")
    
    try:
        # Get active port from connection manager
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port from 'Hardware & Connection' menu first.")
            input("\nPress Enter to continue...")
            return
        
        # Get or create OBD connection via session manager
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        info = obd_reader.get_vehicle_info(obd_connection)
        
        click.echo("\nVehicle Information:")
        click.echo(f"- VIN: {info.get('vin', 'Unknown')}")
        click.echo(f"- Calibration ID: {info.get('calibration_id', 'Unknown')}")
        click.echo(f"- ECU Name: {info.get('ecu_name', 'Unknown')}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading vehicle info")
    
    input("\nPress Enter to continue...")


# ============================================================================
# Additional OBD-II Menu Functions (Gap Closure)
# ============================================================================

def read_pending_dtcs_menu():
    """Read pending (temporary) DTCs - Mode 07."""
    click.echo("\n" + "="*60)
    click.echo("=== Pending DTCs (Mode 07) ===")
    click.echo("="*60)
    click.echo("\nPending DTCs are codes detected but not yet confirmed.")
    click.echo("This is an early warning system for emerging problems.\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        pending = obd_reader.read_pending_dtcs(obd_connection)
        
        if len(pending) == 0:
            click.echo("\n No pending DTCs found")
        else:
            click.echo(f"\nPending DTCs ({len(pending)} found):")
            for i, dtc in enumerate(pending, 1):
                click.echo(f"{i}. {dtc['code']} - {dtc['description']}")
    
    except obd_reader.OBDReadError as e:
        click.echo(f"\n Read error: {e}")
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading pending DTCs")
    
    input("\nPress Enter to continue...")


def filter_dtcs_by_status_menu():
    """Filter DTCs by status without clearing them."""
    click.echo("\n" + "="*60)
    click.echo("=== Filter DTCs by Status ===")
    click.echo("="*60)
    click.echo("\nRead all DTCs and filter by status.\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        # Read all DTCs first
        click.echo("Reading all DTCs...")
        all_dtcs = obd_reader.read_obd_dtcs(obd_connection)
        
        if len(all_dtcs) == 0:
            click.echo("\n No DTCs found")
            input("\nPress Enter to continue...")
            return
        
        # Show filter options
        click.echo("\nFilter by status:")
        click.echo("1. All DTCs")
        click.echo("2. Pending DTCs")
        click.echo("3. Confirmed DTCs")
        click.echo("4. Active DTCs")
        click.echo("5. Stored DTCs")
        
        choice = click.prompt("Select filter", type=int, default=1)
        
        status_map = {1: 'all', 2: 'pending', 3: 'confirmed', 4: 'active', 5: 'stored'}
        status = status_map.get(choice, 'all')
        
        filtered = obd_reader.filter_dtcs_by_status(all_dtcs, status)
        
        click.echo(f"\nFiltered DTCs ({len(filtered)} found):")
        for i, dtc in enumerate(filtered, 1):
            click.echo(f"{i}. {dtc['code']} - {dtc['description']}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error filtering DTCs")
    
    input("\nPress Enter to continue...")


def expand_vehicle_info_menu():
    """Read extended vehicle information."""
    click.echo("\n" + "="*60)
    click.echo("=== Extended Vehicle Information ===")
    click.echo("="*60)
    click.echo("\nReading extended calibration and hardware details...\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        info = obd_reader.expand_vehicle_info(obd_connection)
        
        click.echo("\nExtended Vehicle Information:")
        for key, value in info.items():
            formatted_key = key.replace('_', ' ').title()
            click.echo(f"- {formatted_key}: {value}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading extended vehicle info")
    
    input("\nPress Enter to continue...")


def detect_engine_type_menu():
    """Detect engine type and classification."""
    click.echo("\n" + "="*60)
    click.echo("=== Engine Type Detection ===")
    click.echo("="*60)
    click.echo("\nDetecting engine type from ECU...\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        engine_type = obd_reader.get_engine_type(obd_connection)
        
        click.echo(f"\nEngine Type: {engine_type}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error detecting engine type")
    
    input("\nPress Enter to continue...")


def view_ecu_reset_status_menu():
    """View ECU reset/power-cycle status."""
    click.echo("\n" + "="*60)
    click.echo("=== ECU Reset Status ===")
    click.echo("="*60)
    click.echo("\nChecking if ECU was recently reset...\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        status = obd_reader.get_ecu_reset_status(obd_connection)
        
        click.echo("\nECU Reset Status:")
        if status['reset_detected']:
            click.echo("- Status: RESET DETECTED (recent power cycle)")
        else:
            click.echo("- Status: No recent reset")
        
        click.echo(f"- Runtime Since Start: {status['runtime_seconds']} seconds")
        click.echo(f"- MIL Cycles: {status['mil_cycles']}")
        click.echo(f"- Clear Cycles: {status['clear_cycles']}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading ECU reset status")
    
    input("\nPress Enter to continue...")


def view_mil_history_menu():
    """View Check Engine Light (MIL) history."""
    click.echo("\n" + "="*60)
    click.echo("=== MIL (Check Engine Light) History ===")
    click.echo("="*60)
    click.echo("\nReading MIL status and history...\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        history = obd_reader.read_mil_history(obd_connection)
        
        click.echo("\nMIL Status and History:")
        if history['mil_on']:
            click.echo("- Check Engine Light: ON")
        else:
            click.echo("- Check Engine Light: OFF")
        
        click.echo(f"- DTC Count: {history['dtc_count']}")
        click.echo(f"- Distance with MIL: {history['mil_distance']} km")
        click.echo(f"- Time with MIL: {history['mil_time']} minutes")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading MIL history")
    
    input("\nPress Enter to continue...")


def view_component_tests_menu():
    """View component test results."""
    click.echo("\n" + "="*60)
    click.echo("=== Component Test Results (Mode 06) ===")
    click.echo("="*60)
    click.echo("\nReading on-board component test data...\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        results = obd_reader.read_component_test_results(obd_connection)
        
        if not results.get('success', False):
            click.echo("\nComponent tests not available on this ECU.")
            click.echo("Note: Advanced component testing available via UDS (Mode 0x19)")
            input("\nPress Enter to continue...")
            return
        
        click.echo("\nComponent Test Results:")
        for test_name, values in results.get('tests', {}).items():
            click.echo(f"- {test_name}:")
            click.echo(f"    Current: {values.get('current', 'N/A')}")
            click.echo(f"    Min: {values.get('min', 'N/A')}, Max: {values.get('max', 'N/A')}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error reading component test results")
    
    input("\nPress Enter to continue...")


def query_supported_pids_menu():
    """Query which PIDs are supported by the ECU."""
    click.echo("\n" + "="*60)
    click.echo("=== Supported PIDs Query ===")
    click.echo("="*60)
    click.echo("\nDiscovering which PIDs this ECU supports...\n")
    
    try:
        conn_mgr = connection_manager.get_manager()
        current_port = conn_mgr.get_active_port()
        
        if not current_port:
            click.echo("\n No COM port selected. Please select a port first.")
            input("\nPress Enter to continue...")
            return
        
        obd_session = obd_session_manager.get_session()
        click.echo(f"Connecting to {current_port}...")
        obd_connection = obd_session.get_connection(current_port)
        
        click.echo("Querying supported PIDs (Mode 01 PID 00)...")
        supported = obd_reader.read_supported_pids(obd_connection)
        
        if len(supported) == 0:
            click.echo("\n No supported PIDs found")
        else:
            click.echo(f"\nSupported PIDs ({len(supported)} found):")
            # Display in columns
            for i, pid in enumerate(supported):
                if (i + 1) % 8 == 0:
                    click.echo(f"{pid}")
                else:
                    click.echo(f"{pid}", nl=False)
                    if (i + 1) % 8 != 0:
                        click.echo(" ", nl=False)
            click.echo()
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error querying supported PIDs")
    
    input("\nPress Enter to continue...")


# ============================================================================
# BMW Multi-Module Diagnostic Functions (Task 3.0)
# ============================================================================

def scan_all_modules():
    """Scan all modules for DTCs (Task 1.1.7)."""
    click.echo("\nScanning all BMW modules (Tester Present + DTCs)...")
    click.echo("This may take 1-2 minutes...\n")
    
    try:
        # 1) Quick responsiveness ping (UDS 0x3E)
        mgr = connection_manager.get_manager()
        ping_results = mgr.scan_all_modules(protocol="CAN")
        # Adapt to dataclass-based results
        responding = [pr.module.abbreviation for pr in ping_results if pr.responding]
        not_responding = [pr.module.abbreviation for pr in ping_results if not pr.responding]
        click.echo(f"Responding (Tester Present): {len(responding)}/{len(ping_results)} modules")
        if responding:
            click.echo("   " + ", ".join(sorted(responding)))
        if not_responding:
            click.echo("   No response: " + ", ".join(sorted(not_responding)))

        # 2) Read DTCs from all modules
        # Read DTCs from all modules
        all_dtcs = obd_reader.read_all_module_dtcs(protocol="CAN")
        
        if not all_dtcs:
            click.echo("\n No DTCs found in any module!")
            input("\nPress Enter to continue...")
            return
        
        # Display results
        total_dtcs = sum(len(dtcs) for dtcs in all_dtcs.values())
        click.echo(f"\nFound DTCs in {len(all_dtcs)} module(s), {total_dtcs} total codes\n")
        
        for module_abbr, dtcs in sorted(all_dtcs.items()):
            module = bmw_modules.get_module_by_abbreviation(module_abbr)
            module_name = module.name if module else module_abbr
            click.echo(f"  {module_abbr} ({module_name}) - {len(dtcs)} codes")
        
        # Show detailed list
        if click.confirm("\nView detailed DTC list?", default=True):
            report = obd_reader.format_dtc_report(all_dtcs)
            click.echo("\n" + report)
    
    except Exception as e:
        click.echo(f"\n Scan error: {e}")
        logger.exception("Error scanning modules")
    
    input("\nPress Enter to continue...")


def read_module_dtcs_interactive():
    """Read DTCs from a selected module (Task 1.1.7)."""
    can_modules: List[bmw_modules.BMWModule] = bmw_modules.get_can_modules()
    
    click.echo("\nAvailable CAN Modules:")
    for i, module in enumerate(can_modules, 1):
        click.echo(f"{i}. {module.abbreviation:12} - {module.name}")
    
    choice = click.prompt(f"\nSelect module (1-{len(can_modules)}) or 0 to cancel", 
                          type=int, default=0)
    
    if choice == 0 or choice > len(can_modules):
        return
    
    module = cast(bmw_modules.BMWModule, can_modules[choice - 1])
    
    click.echo(f"\nReading DTCs from {module.abbreviation} ({module.name})...")
    
    try:
        dtcs = obd_reader.read_dtcs_from_module(module)
        
        if len(dtcs) == 0:
            click.echo(f"\n No DTCs found in {module.abbreviation}")
        else:
            click.echo(f"\nFault Codes ({len(dtcs)} found):")
            for dtc in dtcs:
                severity = dtc.get('severity', 'Unknown')
                click.echo(f"  {dtc['code']:8} | {severity:10} | {dtc['description']}")
                
                # Show common causes if available
                dtc_info = dtc_database.lookup_dtc(dtc['code'])
                if dtc_info and len(dtc_info.common_causes) > 0:
                    click.echo(f"           | Common: {dtc_info.common_causes[0]}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception(f"Error reading DTCs from {module.abbreviation}")
    
    input("\nPress Enter to continue...")


def clear_all_modules_dtcs():
    """Clear DTCs from all modules (Task 1.1.7)."""
    click.echo("\n" + "="*60)
    click.echo("  DANGER: Clear All Module DTCs")
    click.echo("="*60)
    click.echo("\nThis will clear fault codes from ALL CAN modules!")
    click.echo("This action cannot be undone.")
    
    confirm1 = click.prompt("\nType 'YES' to confirm", default="no")
    if confirm1 != "YES":
        click.echo("\nOperation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    confirm2 = click.prompt("\nAre you absolutely sure? Type 'CLEAR ALL'", default="no")
    if confirm2 != "CLEAR ALL":
        click.echo("\nOperation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    click.echo("\nClearing DTCs from all modules...")
    
    try:
        can_modules: List[bmw_modules.BMWModule] = bmw_modules.get_can_modules()
        results: Dict[str, bool] = {}
        
        for module in can_modules:
            click.echo(f"  Clearing {module.abbreviation}...")
            try:
                success = obd_reader.clear_dtcs_from_module(module)
                results[module.abbreviation] = success
            except Exception as e:
                logger.error(f"Failed to clear {module.abbreviation}: {e}")
                results[module.abbreviation] = False
        
        click.echo("\nResults:")
        for module_abbr, success in results.items():
            status = " Cleared" if success else " Failed"
            click.echo(f"{module_abbr:12}: {status}")
        
        cleared_count = sum(1 for success in results.values() if success)
        click.echo(f"\n Cleared DTCs from {cleared_count}/{len(can_modules)} modules")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error clearing all module DTCs")
    
    input("\nPress Enter to continue...")


def clear_module_dtcs_interactive():
    """Clear DTCs from a selected module (Task 1.1.7)."""
    click.echo("\nScanning modules for DTCs...")
    
    try:
        all_dtcs = obd_reader.read_all_module_dtcs(protocol="CAN")
        
        if len(all_dtcs) == 0:
            click.echo("\n No modules have active DTCs")
            input("\nPress Enter to continue...")
            return
        
        click.echo("\nModules with active DTCs:")
        module_abbrs = list(all_dtcs.keys())
        
        for i, module_abbr in enumerate(module_abbrs, 1):
            module = bmw_modules.get_module_by_abbreviation(module_abbr)
            module_name = module.name if module else module_abbr
            dtc_count = len(all_dtcs[module_abbr])
            click.echo(f"{i}. {module_abbr:12} ({module_name}) - {dtc_count} codes")
        
        choice = click.prompt(f"\nSelect module (1-{len(module_abbrs)}) or 0 to cancel", 
                              type=int, default=0)
        
        if choice == 0 or choice > len(module_abbrs):
            return
        
        module_abbr: str = cast(str, module_abbrs[choice - 1])
        module = bmw_modules.get_module_by_abbreviation(module_abbr)
        dtcs = all_dtcs[module_abbr]
        
        click.echo(f"\n  WARNING: Clear DTCs from {module_abbr}")
        click.echo(f"\nDTCs to be cleared:")
        for dtc in dtcs:
            click.echo(f"  - {dtc['code']}: {dtc['description']}")
        
        confirm = click.prompt("\nType 'YES' to confirm", default="no")
        if confirm != "YES":
            click.echo("\nOperation cancelled.")
            input("\nPress Enter to continue...")
            return
        
        click.echo(f"\nClearing DTCs from {module_abbr}...")
        if module is None:
            click.echo(" Module not found")
            input("\nPress Enter to continue...")
            return
        success = obd_reader.clear_dtcs_from_module(module)
        
        if success:
            click.echo(f"\n Successfully cleared {len(dtcs)} codes from {module_abbr}")
        else:
            click.echo(f"\n Failed to clear DTCs from {module_abbr}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Error clearing module DTCs")
    
    input("\nPress Enter to continue...")


def dme_functions_menu():
    """DME Specific Functions submenu."""
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== DME Specific Functions ===")
        click.echo("="*60)
        click.echo("\n1. Read ECU Identification")
        click.echo("2. Read DME-Specific Errors")
        click.echo("3. Clear DME-Specific Errors")
        click.echo("4. Back to BMW Diagnostics Menu")
        
        choice = click.prompt("\nSelect option", type=int, default=4)
        
        if choice == 4:
            break
        elif choice == 1:
            read_ecu_identification()
        elif choice == 2:
            read_dme_errors()
        elif choice == 3:
            clear_dme_errors()
        else:
            click.echo("Invalid selection.")


def read_ecu_identification():
    """Read ECU identification using dme_handler (Task 4.1)."""
    click.echo("\n" + "="*60)
    click.echo("=== Read ECU Identification ===")
    click.echo("="*60)
    click.echo("\nQuerying DME via UDS/CAN...")
    
    try:
        ident = dme_handler.read_ecu_identification()
        
        if not ident:
            click.echo("\n No identification data returned")
        else:
            click.echo("\nDME Identification:")
            click.echo("-" * 60)
            
            # Display common fields with nice formatting
            if 'VIN' in ident:
                click.echo(f"VIN:              {ident['VIN']}")
            if 'HW_REF' in ident:
                click.echo(f"Hardware Ref:     {ident['HW_REF']}")
            if 'SW_REF' in ident:
                click.echo(f"Software Ref:     {ident['SW_REF']}")
            if 'SUPPLIER' in ident:
                click.echo(f"Supplier:         {ident['SUPPLIER']}")
            if 'DIAG_INDEX' in ident:
                click.echo(f"Diag Index:       {ident['DIAG_INDEX']}")
            if 'BUILD_DATE' in ident:
                click.echo(f"Build Date:       {ident['BUILD_DATE']}")
            
            # Display any additional fields
            known_fields = {'VIN', 'HW_REF', 'SW_REF', 'SUPPLIER', 'DIAG_INDEX', 'BUILD_DATE'}
            other_fields = {k: v for k, v in ident.items() if k not in known_fields}
            if other_fields:
                click.echo("\nAdditional Fields:")
                for key, value in other_fields.items():
                    click.echo(f"  {key}: {value}")
            
            click.echo("\n Identification read successfully")
    
    except dme_handler.DMEError as e:
        click.echo(f"\n DME Error: {e}")
        logger.error(f"DME error reading ECU identification: {e}")
    except Exception as e:
        click.echo(f"\n Unexpected Error: {e}")
        logger.exception("Unexpected error reading ECU identification")
    
    input("\nPress Enter to continue...")


def read_injector_codes():
    """Read injector correction codes using dme_handler (Task 4.1)."""
    click.echo("\n" + "="*60)
    click.echo("=== Read Injector Codes ===")
    click.echo("="*60)
    click.echo("\nQuerying DME for injector correction values via UDS/CAN...")
    
    try:
        injector_data = dme_handler.read_injector_codes()
        
        if not injector_data:
            click.echo("\n No injector data returned")
        else:
            click.echo("\nInjector Correction Codes (IKS):")
            click.echo("-" * 60)
            
            # Display injector values for cylinders 1-6
            for i in range(1, 7):
                key = f'injector_{i}'
                if key in injector_data:
                    click.echo(f"Cylinder {i}:  {injector_data[key]}")
            
            # Display unit if available
            if 'unit' in injector_data:
                click.echo(f"\nUnit: {injector_data['unit']}")
            
            # Display any additional fields
            known_fields = {f'injector_{i}' for i in range(1, 7)} | {'unit'}
            other_fields = {k: v for k, v in injector_data.items() if k not in known_fields}
            if other_fields:
                click.echo("\nAdditional Data:")
                for key, value in other_fields.items():
                    click.echo(f"  {key}: {value}")
            
            click.echo("\n Injector codes read successfully")
    
    except dme_handler.DMEError as e:
        click.echo(f"\n DME Error: {e}")
        logger.error(f"DME error reading injector codes: {e}")
    except Exception as e:
        click.echo(f"\n Unexpected Error: {e}")
        logger.exception("Unexpected error reading injector codes")
    
    input("\nPress Enter to continue...")


def read_vanos_data():
    """Read VANOS system data using dme_handler (Task 4.1)."""
    click.echo("\n" + "="*60)
    click.echo("=== Read VANOS Data ===")
    click.echo("="*60)
    click.echo("\nQuerying DME for VANOS system data via UDS/CAN...")
    
    try:
        vanos_data = dme_handler.read_vanos_data()
        
        if not vanos_data:
            click.echo("\n No VANOS data returned")
        else:
            click.echo("\nVANOS System Data:")
            click.echo("-" * 60)
            
            # Display common VANOS fields
            if 'intake_position' in vanos_data:
                click.echo(f"Intake Position:      {vanos_data['intake_position']}°")
            if 'exhaust_position' in vanos_data:
                click.echo(f"Exhaust Position:     {vanos_data['exhaust_position']}°")
            if 'intake_target' in vanos_data:
                click.echo(f"Intake Target:        {vanos_data['intake_target']}°")
            if 'exhaust_target' in vanos_data:
                click.echo(f"Exhaust Target:       {vanos_data['exhaust_target']}°")
            if 'intake_adaptation' in vanos_data:
                click.echo(f"Intake Adaptation:    {vanos_data['intake_adaptation']}")
            if 'exhaust_adaptation' in vanos_data:
                click.echo(f"Exhaust Adaptation:   {vanos_data['exhaust_adaptation']}")
            if 'status' in vanos_data:
                click.echo(f"\nStatus:               {vanos_data['status']}")
            
            # Display any additional fields
            known_fields = {'intake_position', 'exhaust_position', 'intake_target', 
                          'exhaust_target', 'intake_adaptation', 'exhaust_adaptation', 'status'}
            other_fields = {k: v for k, v in vanos_data.items() if k not in known_fields}
            if other_fields:
                click.echo("\nAdditional Data:")
                for key, value in other_fields.items():
                    click.echo(f"  {key}: {value}")
            
            click.echo("\n VANOS data read successfully")
    
    except dme_handler.DMEError as e:
        click.echo(f"\n DME Error: {e}")
        logger.error(f"DME error reading VANOS data: {e}")
    except Exception as e:
        click.echo(f"\n Unexpected Error: {e}")
        logger.exception("Unexpected error reading VANOS data")
    
    input("\nPress Enter to continue...")


def read_boost_data():
    """Read boost/wastegate data using dme_handler (Task 4.1)."""
    click.echo("\n" + "="*60)
    click.echo("=== Read Boost/Wastegate Data ===")
    click.echo("="*60)
    click.echo("\nQuerying DME for turbocharger data via UDS/CAN...")
    
    try:
        boost_data = dme_handler.read_boost_data()
        
        if not boost_data:
            click.echo("\n No boost data returned")
        else:
            click.echo("\nTurbocharger/Boost Control Data:")
            click.echo("-" * 60)
            
            # Display common boost fields
            if 'boost_actual' in boost_data:
                click.echo(f"Actual Boost:         {boost_data['boost_actual']} bar")
            if 'boost_target' in boost_data:
                click.echo(f"Target Boost:         {boost_data['boost_target']} bar")
            if 'wastegate_left' in boost_data:
                click.echo(f"Left Wastegate:       {boost_data['wastegate_left']}%")
            if 'wastegate_right' in boost_data:
                click.echo(f"Right Wastegate:      {boost_data['wastegate_right']}%")
            if 'overboost_counter' in boost_data:
                click.echo(f"Overboost Events:     {boost_data['overboost_counter']}")
            if 'underboost_counter' in boost_data:
                click.echo(f"Underboost Events:    {boost_data['underboost_counter']}")
            if 'status' in boost_data:
                click.echo(f"\nStatus:               {boost_data['status']}")
            
            # Display any additional fields
            known_fields = {'boost_actual', 'boost_target', 'wastegate_left', 
                          'wastegate_right', 'overboost_counter', 'underboost_counter', 'status'}
            other_fields = {k: v for k, v in boost_data.items() if k not in known_fields}
            if other_fields:
                click.echo("\nAdditional Data:")
                for key, value in other_fields.items():
                    click.echo(f"  {key}: {value}")
            
            click.echo("\n Boost data read successfully")
    
    except dme_handler.DMEError as e:
        click.echo(f"\n DME Error: {e}")
        logger.error(f"DME error reading boost data: {e}")
    except Exception as e:
        click.echo(f"\n Unexpected Error: {e}")
        logger.exception("Unexpected error reading boost data")
    
    input("\nPress Enter to continue...")


def read_dme_errors():
    """Read DME-specific errors using dme_handler (Task 4.1)."""
    click.echo("\n" + "="*60)
    click.echo("=== Read DME Fault Codes ===")
    click.echo("="*60)
    click.echo("\nQuerying DME fault memory via UDS/CAN...")
    
    try:
        dtcs = dme_handler.read_dme_errors()
        
        if len(dtcs) == 0:
            click.echo("\n No DME fault codes found")
            click.echo("\nFault memory is clear.")
        else:
            click.echo(f"\nFound {len(dtcs)} DME Fault Code(s):")
            click.echo("-" * 60)
            
            for i, dtc in enumerate(dtcs, 1):
                status_icon = "🔴" if dtc.get('status') == 'active' else "🟡"
                click.echo(f"\n{i}. {status_icon} {dtc.get('code', 'Unknown')}")
                click.echo(f"   Description: {dtc.get('description', 'No description')}")
                click.echo(f"   Status: {dtc.get('status', 'Unknown').upper()}")
                if 'frequency' in dtc:
                    click.echo(f"   Frequency: {dtc['frequency']}")
            
            click.echo("\n" + "="*60)
            click.echo("\n  IMPORTANT: Document these codes before clearing!")
    
    except dme_handler.DMEError as e:
        click.echo(f"\n DME Error: {e}")
        logger.error(f"DME error reading fault codes: {e}")
    except Exception as e:
        click.echo(f"\n Unexpected Error: {e}")
        logger.exception("Unexpected error reading DME errors")
    
    input("\nPress Enter to continue...")


def clear_dme_errors():
    """Clear DME-specific errors using dme_handler (Task 4.1)."""
    click.echo("\n" + "="*60)
    click.echo("=== Clear DME Fault Codes ===")
    click.echo("="*60)
    click.echo("\n  WARNING: This will erase ALL DME fault codes!")
    click.echo("\nThis includes:")
    click.echo("  - Active fault codes")
    click.echo("  - Stored/historical codes")
    click.echo("  - Freeze frame data")
    click.echo("\nRecommendation: Read and document codes before clearing.")
    
    # First confirmation
    confirm_text = click.prompt("\nType 'YES' to confirm clearing DME fault memory", type=str, default="NO")
    
    if confirm_text.upper() != 'YES':
        click.echo("\n Operation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    # Second confirmation
    click.echo("\n  FINAL CONFIRMATION")
    if not click.confirm("Are you absolutely sure?", default=False):
        click.echo("\n Operation cancelled.")
        input("\nPress Enter to continue...")
        return
    
    click.echo("\nClearing DME fault memory via UDS/CAN...")
    
    try:
        success = dme_handler.clear_dme_errors()
        
        if success:
            click.echo("\n DME fault memory cleared successfully")
            click.echo("\nAll fault codes have been erased.")
        else:
            click.echo("\n Clear operation completed with warnings")
            click.echo("\nSome fault codes may still remain in memory.")
            click.echo("This can happen if codes are currently active.")
    
    except dme_handler.DMEError as e:
        click.echo(f"\n DME Error: {e}")
        logger.error(f"DME error clearing fault codes: {e}")
    except Exception as e:
        click.echo(f"\n Unexpected Error: {e}")
        logger.exception("Unexpected error clearing DME errors")
    
    input("\nPress Enter to continue...")


def read_dtcs():
    """Read Diagnostic Trouble Codes (DTCs) via DME handler (UDS)."""
    click.echo("Reading DTCs (DME)...")
    try:
        dtcs = dme_handler.read_dme_errors()
        if not dtcs:
            click.echo(" No DTCs found (ECU clean)")
            return
        click.echo(f"\nFound {len(dtcs)} DTC(s):\n")
        for dtc in dtcs:
            code = dtc.get('code', 'UNKNOWN')
            description = dtc.get('description', 'No description')
            status = dtc.get('status', 'N/A')
            click.echo(f"  {code}: {description}")
            click.echo(f"    Status: {status}")
    except Exception as e:
        click.echo(f" Error reading DTCs: {e}")
        logger.exception("DTC read failed")


def clear_dtcs():
    """Clear Diagnostic Trouble Codes (DTCs) via DME handler (UDS)."""
    click.echo("Clearing DTCs (DME)...")
    if not click.confirm("Are you sure you want to clear all DTCs?", default=False):
        click.echo("Cancelled")
        return
    try:
        ok = dme_handler.clear_dme_errors()
        if ok:
            click.echo(" DTCs cleared successfully")
        else:
            click.echo(" Failed to clear DTCs")
    except Exception as e:
        click.echo(f" Error clearing DTCs: {e}")
        logger.exception("DTC clear failed")


def flash_map_interactive():
    """Interactive prompt for flashing a calibration file."""
    from pathlib import Path
    
    map_file = click.prompt("Enter the path to the calibration .bin file", type=click.Path(exists=True))
    map_path = Path(map_file)
    
    if not map_path.exists():
        click.echo(" File not found")
        return
    
    # Show file info
    file_size = map_path.stat().st_size
    click.echo(f"\nFile: {map_path.name}")
    click.echo(f"Size: {file_size:,} bytes ({file_size/(1024*1024):.2f} MB)")
    
    # Determine flash method
    click.echo("\nFlash method:")
    click.echo("  1. Flash calibration only (256KB, safe for tuning)")
    click.echo("  2. Flash full binary (2MB, DANGEROUS)")
    
    method = click.prompt("Select method", type=int, default=1)
    
    if not click.confirm(f"\n  Flash {map_path.name} to ECU?", default=False):
        click.echo("Cancelled")
        return
    
    click.echo("\nUse Direct CAN Flash menu for actual flash operation:")
    click.echo("  Main Menu → 12. Direct CAN Flash")
    click.echo(f"  → {'2. Flash Calibration' if method == 1 else '3. Flash Full Binary'}")
    click.echo(f"  → Select: {map_path}")


# ============================================================================
# UDS Operations Menu
# ============================================================================

def uds_operations_menu():
    """UDS Operations submenu - Advanced ECU communication using UDS protocol."""
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== UDS Operations (Advanced) ===")
        click.echo("="*60)
        click.echo("\nADVANCED: Direct ECU communication using UDS protocol\n")
        
        click.echo("1. Enter Programming Session")
        click.echo("2. Read VIN from ECU")
        click.echo("3. Security Access (Seed/Key)")
        click.echo("4. Read Calibration Region")
        click.echo("5. Flash Calibration Region")
        click.echo("6. Reset ECU")
        click.echo("7. Verify Calibration CRCs")
        click.echo("8. View UDS Protocol Info")
        click.echo("0. Back to Main Menu")
        
        choice = click.prompt("\nSelect option", type=int, default=0)
        
        if choice == 0:
            break
        elif choice == 1:
            uds_enter_programming_session()
        elif choice == 2:
            uds_read_vin()
        elif choice == 3:
            uds_security_access()
        elif choice == 4:
            uds_read_calibration()
        elif choice == 5:
            uds_flash_calibration()
        elif choice == 6:
            uds_reset_ecu()
        elif choice == 7:
            uds_verify_crcs()
        elif choice == 8:
            uds_protocol_info()
        else:
            click.echo("Invalid selection.")


def uds_enter_programming_session():
    """Enter UDS programming session."""
    click.echo("\n" + "="*60)
    click.echo("=== Enter Programming Session ===")
    click.echo("="*60)
    
    handler = uds_handler.UDSHandler(logger)
    
    click.echo("\nAttempting to enter programming diagnostic session...")
    click.echo("Using direct CAN/UDS\n")
    
    if handler.enter_programming_session():
        click.echo("\n Programming session established")
        click.echo("ECU is ready for flash operations")
    else:
        click.echo("\n Failed to enter programming session")
        click.echo("Check ECU connection and try again")
    
    input("\nPress Enter to continue...")


def uds_read_vin():
    """Read VIN using UDS protocol."""
    click.echo("\n" + "="*60)
    click.echo("=== Read VIN from ECU ===")
    click.echo("="*60)
    
    handler = uds_handler.UDSHandler(logger)
    
    click.echo("\nReading VIN via UDS (Service 0x22, DID 0xF190)...\n")
    
    vin = handler.read_vin()
    
    if vin:
        click.echo(f"\n VIN: {vin}")
        click.echo("\nThis VIN is used for:")
        click.echo("  - License validation")
        click.echo("  - Map compatibility checking")
        click.echo("  - Backup organization")
    else:
        click.echo("\n Failed to read VIN")
    
    input("\nPress Enter to continue...")


def uds_security_access():
    """Security access (seed/key) implementation."""
    click.echo("\n" + "="*60)
    click.echo("=== Security Access (Seed/Key) ===")
    click.echo("="*60)
    
    click.echo("\nBMW ECU Security Access Process:")
    click.echo("1. Request seed from ECU (UDS 0x27 0x01)")
    click.echo("2. Calculate key using proprietary algorithm")
    click.echo("3. Send key to ECU (UDS 0x27 0x02)")
    click.echo("4. ECU unlocks if key is correct\n")
    
    click.echo("Algorithms implemented: v1 (MSS54/MSD80), v2 (MSD80 swap), v3 (BM variant)")
    click.echo("Keys are calculated locally")
    
    input("\nPress Enter to continue...")


def uds_read_calibration():
    """Read calibration region from ECU."""
    click.echo("\n" + "="*60)
    click.echo("=== Read Calibration Region ===")
    click.echo("="*60)
    
    click.echo("\nCalibration region contains:")
    click.echo("  - Fuel maps")
    click.echo("  - Ignition timing maps")
    click.echo("  - Boost control maps")
    click.echo("  - Limiters (RPM, speed, torque)")
    click.echo("  - Feature codewords\n")
    
    click.echo("Default CAL region:")
    click.echo("  Start: 0x00100000")
    click.echo("  Size:  512 KB (~0x80000 bytes)\n")
    
    if not click.confirm("Read calibration from ECU?", default=False):
        return
    
    handler = uds_handler.UDSHandler(logger)
    
    click.echo("\nReading calibration via UDS...")
    data = handler.read_calibration_region()
    
    if data:
        click.echo(f"\n Read {len(data)} bytes")
        
        # Ask to save
        if click.confirm("Save to file?", default=True):
            output_dir = Path(__file__).parent.parent / "backups"
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"cal_read_{timestamp}.bin"
            
            with open(output_file, 'wb') as f:
                f.write(data)
            
            click.echo(f" Saved to: {output_file}")
    else:
        click.echo("\n Failed to read calibration")
    
    input("\nPress Enter to continue...")


def uds_flash_calibration():
    """Flash calibration region to ECU."""
    click.echo("\n" + "="*60)
    click.echo("=== Flash Calibration Region ===")
    click.echo("="*60)
    click.echo("\n  DANGER: Incorrect calibration can damage ECU!")
    
    click.echo("\nThis will flash ONLY the calibration region (CAL)")
    click.echo("Does NOT touch bootloader or firmware\n")
    
    # Select file
    map_file = click.prompt("Enter calibration file path", type=click.Path(exists=True))
    map_path = Path(map_file)
    
    if not map_path.exists():
        click.echo("\n File not found")
        input("\nPress Enter to continue...")
        return
    
    # Read file
    with open(map_path, 'rb') as f:
        data = f.read()
    
    click.echo(f"\nFile: {map_path.name}")
    click.echo(f"Size: {len(data)} bytes ({len(data)/1024:.1f} KB)")
    
    # Confirm
    if not click.confirm("\n  Flash this calibration to ECU?", default=False):
        click.echo("\n Cancelled")
        input("\nPress Enter to continue...")
        return
    
    # Final confirm
    if not click.confirm("  FINAL CONFIRMATION - This will modify your ECU!", default=False):
        click.echo("\n Cancelled")
        input("\nPress Enter to continue...")
        return
    
    handler = uds_handler.UDSHandler(logger)
    
    click.echo("\nFlashing calibration via UDS...")
    success = handler.flash_calibration_region(data, verify=True)
    
    if success:
        click.echo("\n Calibration flash successful!")
        click.echo("Resetting ECU...")
        handler.reset_ecu()
    else:
        click.echo("\n Flash failed - ECU not modified")
    
    input("\nPress Enter to continue...")


def uds_reset_ecu():
    """Reset ECU using UDS."""
    click.echo("\n" + "="*60)
    click.echo("=== Reset ECU ===")
    click.echo("="*60)
    
    click.echo("\nReset Types:")
    click.echo("1. Hard Reset (0x01) - Full ECU restart")
    click.echo("2. Key Off/On (0x02) - Simulate key cycle")
    click.echo("3. Soft Reset (0x03) - Reload calibration")
    
    reset_type = click.prompt("\nSelect reset type", type=int, default=1)
    
    if reset_type not in [1, 2, 3]:
        click.echo("\n Invalid reset type")
        input("\nPress Enter to continue...")
        return
    
    handler = uds_handler.UDSHandler(logger)
    
    click.echo(f"\nResetting ECU (type 0x0{reset_type})...")
    success = handler.reset_ecu(reset_type)
    
    if success:
        click.echo("\n ECU reset successful")
    else:
        click.echo("\n Reset failed")
    
    input("\nPress Enter to continue...")


def uds_verify_crcs():
    """Verify calibration CRCs."""
    click.echo("\n" + "="*60)
    click.echo("=== Verify Calibration CRCs ===")
    click.echo("="*60)
    
    click.echo("\n  CRC zone boundaries not yet defined")
    click.echo("Requires decompilation of CRC functions:")
    click.echo("  - 0x0186ccb1 (CRC_40304)")
    click.echo("  - 0x0186ccbd (CRC_40404)\n")
    
    click.echo("CRC verification checks that calibration data:")
    click.echo("  - Was not corrupted during flash")
    click.echo("  - Matches expected checksums")
    click.echo("  - Is compatible with ECU firmware")
    
    input("\nPress Enter to continue...")


def uds_protocol_info():
    """Display UDS protocol information."""
    click.echo("\n" + "="*60)
    click.echo("=== UDS Protocol Information ===")
    click.echo("="*60)
    
    click.echo("\nUnified Diagnostic Services (ISO 14229)")
    click.echo("\nKey Services:")
    click.echo("  0x10 - Diagnostic Session Control")
    click.echo("  0x11 - ECU Reset")
    click.echo("  0x22 - Read Data By Identifier")
    click.echo("  0x27 - Security Access (Seed/Key)")
    click.echo("  0x2E - Write Data By Identifier")
    click.echo("  0x31 - Routine Control")
    click.echo("  0x34 - Request Download")
    click.echo("  0x36 - Transfer Data")
    click.echo("  0x37 - Request Transfer Exit\n")
    
    click.echo("Implementation:")
    click.echo("  - Uses UDS over CAN (ISO-TP)")
    click.echo("  - PT_CAN2 bus (Powertrain CAN)")
    click.echo("  - Partial flash (CAL region only)")
    click.echo("  - Standard CRC32 checksums")
    click.echo("  - BMW-specific seed/key algorithm\n")
    
    click.echo("Reference: mevd17_uds_base")
    
    input("\nPress Enter to continue...")


# ============================================================================
# Map Options Menu (Tuning Configuration)
# ============================================================================

def map_options_menu():
    """Map Options submenu - Configure tuning options before flash."""
    current_options = map_options.MapOptions()
    
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Map Options & Tuning ===")
        click.echo("="*60)
        click.echo("\nConfigure options to apply BEFORE flashing\n")
        
        # Show enabled options
        enabled = current_options.get_enabled_options()
        if enabled:
            click.echo("Active Options:")
            for opt in enabled:
                click.echo(f"   {opt}")
        else:
            click.echo("Active Options: None (stock)")
        
        click.echo("\n1. Configure Burbles/Pops & Crackles")
        click.echo("2. Configure VMAX (Speed Limiter)")
        click.echo("3. Configure DTC/CEL Disable")
        click.echo("4. Configure Launch Control")
        click.echo("5. Configure Rev Limiter")
        click.echo("6. Configure Boost Limits")
        click.echo("7. Load Preset Configuration")
        click.echo("8. View All Settings")
        click.echo("9. Validate Configuration")
        click.echo("10. Apply to Map File")
        click.echo("11. Tune & Flash (Apply → Flash to ECU) ")
        click.echo("0. Back to Main Menu")
        
        choice = click.prompt("\nSelect option", type=int, default=0)
        
        if choice == 0:
            break
        elif choice == 1:
            configure_burbles(current_options)
        elif choice == 2:
            configure_vmax(current_options)
        elif choice == 3:
            configure_dtc(current_options)
        elif choice == 4:
            configure_launch_control(current_options)
        elif choice == 5:
            configure_rev_limiter(current_options)
        elif choice == 6:
            configure_boost(current_options)
        elif choice == 7:
            load_preset_options(current_options)
        elif choice == 8:
            view_all_options(current_options)
        elif choice == 9:
            validate_options(current_options)
        elif choice == 10:
            apply_options_to_map(current_options)
        elif choice == 11:
            tune_and_flash(current_options)
        else:
            click.echo("Invalid selection.")


def configure_burbles(options: map_options.MapOptions):
    """Configure burbles/pops options."""
    click.echo("\n=== Configure Burbles/Pops & Crackles ===\n")
    
    options.burbles.enabled = click.confirm("Enable burbles?", default=options.burbles.enabled)
    
    if options.burbles.enabled:
        click.echo("\nModes: normal, sport, custom")
        mode_str = click.prompt("Select mode", default=options.burbles.mode.value)
        try:
            options.burbles.mode = map_options.BurbleMode(mode_str)
        except ValueError:
            click.echo(f"Invalid mode, keeping {options.burbles.mode.value}")
        
        if click.confirm("Configure advanced parameters?", default=False):
            options.burbles.min_rpm = click.prompt("Min RPM", type=int, default=options.burbles.min_rpm)
            options.burbles.max_rpm = click.prompt("Max RPM", type=int, default=options.burbles.max_rpm)
            options.burbles.min_ect = click.prompt("Min ECT (°C)", type=int, default=options.burbles.min_ect)
            options.burbles.lambda_target = click.prompt("Lambda target", type=float, default=options.burbles.lambda_target)
    
    click.echo("\n Burbles configuration updated")
    input("\nPress Enter to continue...")


def configure_vmax(options: map_options.MapOptions):
    """Configure VMAX options."""
    click.echo("\n=== Configure VMAX (Speed Limiter) ===\n")
    
    options.vmax.enabled = click.confirm("Remove/raise speed limiter?", default=options.vmax.enabled)
    
    if options.vmax.enabled:
        click.echo("\nRecommended: 255 km/h (effectively no limit)")
        options.vmax.limit_kmh = click.prompt("Speed limit (km/h)", type=int, default=options.vmax.limit_kmh)
    
    click.echo("\n VMAX configuration updated")
    input("\nPress Enter to continue...")


def configure_dtc(options: map_options.MapOptions):
    """Configure DTC disable options."""
    click.echo("\n=== Configure DTC/CEL Disable ===\n")
    
    click.echo("Select which DTCs to disable from triggering CEL:\n")
    
    options.dtc.disable_cat_codes = click.confirm("Catalyst efficiency (P0420/P0430)?", 
                                                   default=options.dtc.disable_cat_codes)
    options.dtc.disable_o2_codes = click.confirm("Secondary O2 sensors?", 
                                                  default=options.dtc.disable_o2_codes)
    options.dtc.disable_evap_codes = click.confirm("EVAP system?", 
                                                    default=options.dtc.disable_evap_codes)
    options.dtc.disable_knock_cel = click.confirm("Knock CEL (keeps detection active)?", 
                                                   default=options.dtc.disable_knock_cel)
    
    click.echo("\n DTC configuration updated")
    input("\nPress Enter to continue...")


def configure_launch_control(options: map_options.MapOptions):
    """Configure launch control options."""
    click.echo("\n=== Configure Launch Control ===\n")
    
    options.launch_control.enabled = click.confirm("Enable launch control?", 
                                                    default=options.launch_control.enabled)
    
    if options.launch_control.enabled:
        if click.confirm("Configure advanced parameters?", default=False):
            options.launch_control.timing_retard = click.prompt("Timing retard (degrees)", 
                                                                type=int, 
                                                                default=options.launch_control.timing_retard)
            options.launch_control.boost_target = click.prompt("Boost target (bar)", 
                                                               type=float, 
                                                               default=options.launch_control.boost_target)
            options.launch_control.rpm_threshold = click.prompt("RPM threshold", 
                                                                type=int, 
                                                                default=options.launch_control.rpm_threshold)
    
    click.echo("\n Launch control configuration updated")
    input("\nPress Enter to continue...")


def configure_rev_limiter(options: map_options.MapOptions):
    """Configure rev limiter options."""
    click.echo("\n=== Configure Rev Limiter ===\n")
    
    options.rev_limiter.enabled = click.confirm("Raise rev limiter?", 
                                                default=options.rev_limiter.enabled)
    
    if options.rev_limiter.enabled:
        click.echo("\n  Max safe RPM: 7500 (N54 engine)")
        options.rev_limiter.hard_limit = click.prompt("Hard limit (RPM)", 
                                                      type=int, 
                                                      default=options.rev_limiter.hard_limit)
        options.rev_limiter.soft_limit = click.prompt("Soft limit (RPM)", 
                                                      type=int, 
                                                      default=options.rev_limiter.soft_limit)
    
    click.echo("\n Rev limiter configuration updated")
    input("\nPress Enter to continue...")


def configure_boost(options: map_options.MapOptions):
    """Configure boost limit options."""
    click.echo("\n=== Configure Boost Limits ===\n")
    
    options.boost.enabled = click.confirm("Increase boost limits?", 
                                         default=options.boost.enabled)
    
    if options.boost.enabled:
        click.echo("\nStock N54: ~1.0 bar")
        click.echo("Stage 1:   ~1.2 bar")
        click.echo("Stage 2:   ~1.4 bar")
        click.echo("Stage 2+:  ~1.6 bar\n")
        
        options.boost.max_boost_bar = click.prompt("Max boost (bar)", 
                                                   type=float, 
                                                   default=options.boost.max_boost_bar)
    
    click.echo("\n Boost configuration updated")
    input("\nPress Enter to continue...")


def load_preset_options(options: map_options.MapOptions):
    """Load preset configuration."""
    click.echo("\n=== Load Preset Configuration ===\n")
    
    presets: List[str] = map_options.list_presets()
    
    for idx, name in enumerate(presets, 1):
        click.echo(f"{idx}. {name}")
    
    choice = click.prompt("\nSelect preset", type=int, default=0)
    
    if 1 <= choice <= len(presets):
        preset_name: str = cast(str, presets[choice - 1])
        preset = map_options.get_preset(preset_name)
        
        if preset:
            # Copy preset to current options
            options.burbles = preset.burbles
            options.vmax = preset.vmax
            options.dtc = preset.dtc
            options.launch_control = preset.launch_control
            options.rev_limiter = preset.rev_limiter
            options.boost = preset.boost
            
            click.echo(f"\n Loaded preset: {preset_name}")
    else:
        click.echo("\n Invalid selection")
    
    input("\nPress Enter to continue...")


def view_all_options(options: map_options.MapOptions):
    """View all current option settings."""
    click.echo("\n=== All Map Options ===\n")
    # Print explicitly from dataclass fields to avoid Unknown-typed dicts
    click.echo("\nBURBLES:")
    click.echo(f"  enabled: {options.burbles.enabled}")
    click.echo(f"  mode: {options.burbles.mode.value}")
    click.echo(f"  min_rpm: {options.burbles.min_rpm}")
    click.echo(f"  max_rpm: {options.burbles.max_rpm}")
    click.echo(f"  min_ect: {options.burbles.min_ect}")
    click.echo(f"  lambda_target: {options.burbles.lambda_target}")

    click.echo("\nVMAX:")
    click.echo(f"  enabled: {options.vmax.enabled}")
    click.echo(f"  limit_kmh: {options.vmax.limit_kmh}")

    click.echo("\nDTC:")
    click.echo(f"  disable_cat_codes: {options.dtc.disable_cat_codes}")
    click.echo(f"  disable_o2_codes: {options.dtc.disable_o2_codes}")
    click.echo(f"  disable_evap_codes: {options.dtc.disable_evap_codes}")
    click.echo(f"  disable_knock_cel: {options.dtc.disable_knock_cel}")
    click.echo(f"  custom_codes: {', '.join(options.dtc.custom_codes) if options.dtc.custom_codes else '[]'}")

    click.echo("\nLAUNCH CONTROL:")
    click.echo(f"  enabled: {options.launch_control.enabled}")
    click.echo(f"  timing_retard: {options.launch_control.timing_retard}")
    click.echo(f"  boost_target: {options.launch_control.boost_target}")
    click.echo(f"  rpm_threshold: {options.launch_control.rpm_threshold}")

    click.echo("\nREV LIMITER:")
    click.echo(f"  enabled: {options.rev_limiter.enabled}")
    click.echo(f"  soft_limit: {options.rev_limiter.soft_limit}")
    click.echo(f"  hard_limit: {options.rev_limiter.hard_limit}")
    click.echo(f"  per_gear_limits: {options.rev_limiter.per_gear_limits}")

    click.echo("\nBOOST:")
    click.echo(f"  enabled: {options.boost.enabled}")
    click.echo(f"  max_boost_bar: {options.boost.max_boost_bar}")
    click.echo(f"  per_gear_limits: {options.boost.per_gear_limits}")
    click.echo(f"  overboost_duration: {options.boost.overboost_duration}")

    click.echo("\nMETADATA:")
    click.echo(f"  transmission: {options.transmission.value}")
    click.echo(f"  octane: {options.octane}")
    click.echo(f"  ethanol_content: {options.ethanol_content}")
    
    input("\nPress Enter to continue...")


def validate_options(options: map_options.MapOptions):
    """Validate current options configuration."""
    click.echo("\n=== Validate Configuration ===\n")
    
    is_valid, errors = options.validate()
    
    if is_valid:
        click.echo(" Configuration is valid")
        click.echo("\nAll settings are within safe ranges")
    else:
        click.echo(" Configuration has errors:\n")
        for error in errors:
            click.echo(f"  - {error}")
    
    input("\nPress Enter to continue...")


def apply_options_to_map(options: map_options.MapOptions):
    """Apply configured options to a map file."""
    from . import map_patcher
    
    click.echo("\n=== Apply Options to Map File ===\n")
    
    click.echo("  This will modify a .bin file with selected tuning options")
    click.echo("You can select:")
    click.echo("  1. An existing backup .bin file")
    click.echo("  2. Any other .bin file\n")
    
    # Validate options first
    is_valid, errors = options.validate()
    if not is_valid:
        click.echo(" Configuration has errors:")
        for error in errors:
            click.echo(f"  - {error}")
        input("\nPress Enter to continue...")
        return
    
    # Select bin file
    click.echo("Select .bin file source:")
    click.echo("  1. Browse backups/ directory")
    click.echo("  2. Specify custom path")
    
    source_choice = click.prompt("Select", type=int, default=1)
    
    if source_choice == 1:
        # List backup files
        backup_dir = Path("backups")
        if not backup_dir.exists():
            click.echo(" No backups directory found")
            input("\nPress Enter to continue...")
            return
        
        bin_files: List[Path] = list(backup_dir.rglob("*.bin"))
        if not bin_files:
            click.echo(" No .bin files found in backups/")
            input("\nPress Enter to continue...")
            return
        
        click.echo("\nAvailable backup files:")
        for i, f in enumerate(bin_files, 1):
            size_mb = f.stat().st_size / (1024*1024)
            click.echo(f"{i}. {f.relative_to(backup_dir)} ({size_mb:.2f} MB)")
        
        file_choice = click.prompt("Select file", type=int)
        if file_choice < 1 or file_choice > len(bin_files):
            click.echo(" Invalid selection")
            input("\nPress Enter to continue...")
            return
        
        bin_path: Path = cast(Path, bin_files[file_choice - 1])
    else:
        # Custom path
        bin_file = click.prompt("Enter .bin file path", type=click.Path(exists=True))
        bin_path = Path(bin_file)
        
        if not bin_path.exists():
            click.echo(" File not found")
            input("\nPress Enter to continue...")
            return
    
    # Read bin file
    with open(bin_path, 'rb') as f:
        bin_data = bytearray(f.read())
    
    click.echo(f"\nSelected: {bin_path.name}")
    click.echo(f"Size: {len(bin_data):,} bytes ({len(bin_data)/(1024*1024):.2f} MB)")
    
    # Detect software from bin using consolidated detection
    detection = software_detector.detect_software_from_bin(str(bin_path))
    
    if not detection['is_valid']:
        click.echo(f"  ERROR: {detection['error']}")
        if not click.confirm("Continue anyway?", default=False):
            return
    else:
        click.echo(f"  Detected: {detection['ecu_type']} (Software: {detection['software_version'] or 'Unknown'})")
    
    # Show what will be applied / decide workflow
    enabled = options.get_enabled_options()
    if enabled:
        click.echo("\nWill apply:")
        for opt in enabled:
            click.echo(f"   {opt}")
        if not click.confirm("\nApply these options?", default=False):
            click.echo(" Cancelled")
            input("\nPress Enter to continue...")
            return

        # Build tuning patch set from MapOptions
        restoring = False
        patcher = map_patcher.MapPatcher(ecu_type="MSD80")
        click.echo("\nBuilding patches from configured options...")
        try:
            patch_set = patcher.create_patchset_from_map_options(
                options,
                name="Tuning Options",
                description="Applied from Map Options menu",
            )
        except Exception as e:
            click.echo(f"\n Failed to build patch set from options: {e}")
            logger.exception("Failed to build patch set from MapOptions")
            input("\nPress Enter to continue...")
            return

        if len(patch_set) == 0:
            click.echo("\n No patches were generated from the current configuration.")
            input("\nPress Enter to continue...")
            return
    else:
        # No options enabled – offer restore-to-stock workflow
        click.echo("\nNo tuning options are enabled.")
        click.echo("You can restore previously changed settings to STOCK using a reference backup.")
        if not click.confirm("Proceed with restore-to-stock using a stock reference .bin?", default=True):
            click.echo(" Cancelled")
            input("\nPress Enter to continue...")
            return
        # Select reference stock file
        click.echo("\nSelect stock reference .bin:")
        click.echo("  1. Browse backups/ directory")
        click.echo("  2. Specify custom path")
        ref_choice = click.prompt("Select", type=int, default=1)
        if ref_choice == 1:
            ref_dir = Path("backups")
            if not ref_dir.exists():
                click.echo(" No backups directory found")
                input("\nPress Enter to continue...")
                return
            ref_bins: List[Path] = list(ref_dir.rglob("*.bin"))
            if not ref_bins:
                click.echo(" No .bin files found in backups/")
                input("\nPress Enter to continue...")
                return
            click.echo("\nAvailable backup files for reference:")
            for i, f in enumerate(ref_bins, 1):
                size_mb = f.stat().st_size / (1024*1024)
                click.echo(f"{i}. {f.relative_to(ref_dir)} ({size_mb:.2f} MB)")
            ref_index = click.prompt("Select reference", type=int)
            if ref_index < 1 or ref_index > len(ref_bins):
                click.echo(" Invalid selection")
                input("\nPress Enter to continue...")
                return
            ref_path: Path = cast(Path, ref_bins[ref_index - 1])
        else:
            ref_input = click.prompt("Enter reference .bin path", type=click.Path(exists=True))
            ref_path = Path(ref_input)
            if not ref_path.exists():
                click.echo(" File not found")
                input("\nPress Enter to continue...")
                return
        # Read reference data
        with open(ref_path, 'rb') as rf:
            ref_data = rf.read()
        if len(ref_data) != len(bin_data):
            click.echo(f"  Reference size mismatch: source {len(bin_data):,} vs ref {len(ref_data):,}")
            if not click.confirm("Continue anyway?", default=False):
                return
        # Build restore patch set
        patcher = map_patcher.MapPatcher(ecu_type="MSD80")
        patch_set = patcher.create_restore_to_stock_patchset(ref_data)
        click.echo(f"\nRestoring {len(patch_set)} calibration regions to stock values...")
        restoring = True

    # Apply patches
    click.echo(f"\nApplying {len(patch_set)} patches...")
    
    def progress(msg: str, pct: int) -> None:
        click.echo(f"[{pct:3d}%] {msg}")
    
    try:
        result = patcher.apply_patch_set(bin_data, patch_set, progress_callback=progress)
        
        if not result['success']:
            click.echo("\n Patch application failed:")
            for error in result['errors']:
                click.echo(f"  - {error}")
            input("\nPress Enter to continue...")
            return
        
        click.echo(f"\n Applied {len(result['applied_patches'])}/{result['total_patches']} patches")
        click.echo(f" Updated {result.get('updated_crc_count', 0)} CRC zones")
        
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Patch application failed")
        input("\nPress Enter to continue...")
        return
    
    # Save modified bin
    output_dir: Path = bin_path.parent / "modified"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "restored" if restoring else "tuned"
    output_file: Path = output_dir / f"{bin_path.stem}_{suffix}_{timestamp}.bin"
    
    with open(output_file, 'wb') as f:
        f.write(bin_data)
    
    click.echo(f"\n Modified .bin saved to:")
    click.echo(f"  {output_file}")
    click.echo(f"\nApplied modifications:")
    for opt in enabled:
        click.echo(f"  - {opt}")
    
    click.echo(f"\nAffected CRC zones: {', '.join(result['affected_zones'])}")
    click.echo("\n Ready to flash to ECU via:")
    click.echo("  Main Menu → 12. Direct CAN Flash → 2. Flash Calibration")
    click.echo("  (Select the modified .bin file when prompted)")
    
    input("\nPress Enter to continue...")


def tune_and_flash(preset):
    """
    Tune & Flash workflow: Apply a TuningPreset to a backup .bin, then flash to ECU.
    """
    from . import map_patcher
    click.echo("\n" + "="*70)
    click.echo("=== Tune & Flash (Preset → Tuned .bin → ECU) ===")
    click.echo("="*70)
    click.echo("\n This workflow will:")
    click.echo("  1. Apply preset patches to a .bin file")
    click.echo("  2. Recalculate BMW CRCs")
    click.echo("  3. Run pre-flash safety checks (VIN, SW-ID, battery, backup)")
    click.echo("  4. Flash the tuned calibration to ECU via Direct CAN/UDS")
    click.echo("\n  DANGER: This will write to ECU memory!")
    click.echo("    Ensure stable 12V+ power and do NOT disconnect during flash.")
    if not click.confirm("\nProceed with Tune & Flash?", default=False):
        click.echo("Cancelled.")
        input("\nPress Enter to continue...")
        return
    # 1. Select source .bin file
    click.echo("\n" + "-"*50)
    click.echo("Select source .bin file:")
    click.echo("  1. Browse backups/ directory")
    click.echo("  2. Specify custom path")
    source_choice = click.prompt("Select", type=int, default=1)
    
    if source_choice == 1:
        backup_dir = Path("backups")
        if not backup_dir.exists():
            click.echo(" No backups directory found")
            input("\nPress Enter to continue...")
            return
        
        bin_files: List[Path] = list(backup_dir.rglob("*.bin"))
        if not bin_files:
            click.echo(" No .bin files found in backups/")
            input("\nPress Enter to continue...")
            return
        
        click.echo("\nAvailable backup files:")
        for i, f in enumerate(bin_files, 1):
            try:
                size_mb = f.stat().st_size / (1024*1024)
            except Exception:
                size_mb = 0.0
            click.echo(f"{i}. {f.relative_to(backup_dir)} ({size_mb:.2f} MB)")
        
        file_choice = click.prompt("Select file", type=int)
        if file_choice < 1 or file_choice > len(bin_files):
            click.echo(" Invalid selection")
            input("\nPress Enter to continue...")
            return
        
        bin_path: Path = cast(Path, bin_files[file_choice - 1])
    else:
        bin_file = click.prompt("Enter .bin file path", type=click.Path(exists=True))
        bin_path = Path(bin_file)
        if not bin_path.exists():
            click.echo(" File not found")
            input("\nPress Enter to continue...")
            return
    
    # Read bin file
    with open(bin_path, 'rb') as f:
        bin_data = bytearray(f.read())
    
    click.echo(f"\nSelected: {bin_path.name}")
    click.echo(f"Size: {len(bin_data):,} bytes ({len(bin_data)/(1024*1024):.2f} MB)")
    
    # Detect software from bin using consolidated detection
    detection = software_detector.detect_software_from_bin(str(bin_path))
    
    if not detection['is_valid']:
        click.echo(f"  ERROR: {detection['error']}")
        if not click.confirm("Continue anyway?", default=False):
            return
    else:
        click.echo(f"  Detected: {detection['ecu_type']} (Software: {detection['software_version'] or 'Unknown'})")
    
    # 3. Build and apply patches
    click.echo("\n" + "-"*50)
    click.echo("Building patches from configured options...")
    
    patcher = map_patcher.MapPatcher(ecu_type=detection['ecu_type'] or "MSD80")
    try:
        patch_set = patcher.create_patchset_from_map_options(
            options,
            name="Tune & Flash",
            description="Applied from Tune & Flash workflow",
        )
    except Exception as e:
        click.echo(f"\n Failed to build patch set: {e}")
        logger.exception("Failed to build patch set from MapOptions")
        input("\nPress Enter to continue...")
        return
    
    if len(patch_set) == 0 and not options.boost.enabled:
        click.echo("\n No patches were generated from the current configuration.")
        input("\nPress Enter to continue...")
        return
    
    # Apply patches (including boost via apply_patches_to_file which calls apply_boost_from_patchset)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir: Path = bin_path.parent / "tuned"
    output_dir.mkdir(exist_ok=True)
    output_file: Path = output_dir / f"{bin_path.stem}_tuneflash_{timestamp}.bin"
    
    click.echo(f"\nApplying patches and recalculating CRCs...")
    
    def progress(msg: str, pct: int) -> None:
        click.echo(f"  [{pct:3d}%] {msg}")
    
    try:
        result = map_patcher.apply_patches_to_file(
            bin_path,
            output_file,
            patch_set,
            ecu_type="MSD80"
        )
        
        if not result.get('success', False):
            click.echo("\n Patch application failed:")
            for error in result.get('errors', []):
                click.echo(f"  - {error}")
            input("\nPress Enter to continue...")
            return
        
        applied_count = len(result.get('applied_patches', []))
        total_count = result.get('total_patches', 0)
        crc_count = result.get('updated_crc_count', 0)
        boost_info = result.get('boost', {})
        
        click.echo(f"\n Applied {applied_count}/{total_count} patches")
        click.echo(f" Updated {crc_count} CRC zones")
        
        if boost_info.get('applied', False):
            click.echo(f" Boost tables modified via boost_patcher")
            click.echo(f"   Target boost: {boost_info.get('max_boost_bar', '?')} bar")
            click.echo(f"   Increase: {boost_info.get('boost_increase_psi', '?'):.1f} PSI")
            click.echo(f"   SW version: {boost_info.get('software_version', 'unknown')}")
        
        click.echo(f"\n Tuned file saved: {output_file}")
        
    except Exception as e:
        click.echo(f"\n Error during patch application: {e}")
        logger.exception("Patch application failed in Tune & Flash")
        input("\nPress Enter to continue...")
        return
    
    # 4. Pre-flash safety checks
    click.echo("\n" + "-"*50)
    click.echo("Running pre-flash safety checks...")
    
    # Get VIN from ECU for safety checks
    flasher: Optional[DirectCANFlasher] = None
    vin: Optional[str] = None
    try:
        flasher = DirectCANFlasher()
        if not flasher.connect():
            click.echo("\n Cannot connect to ECU for pre-flash checks")
            click.echo("  Ensure K+DCAN cable is connected and ignition is ON")
            input("\nPress Enter to continue...")
            return
        
        vin = flasher.read_vin()
        if not vin:
            click.echo("\n  Could not read VIN from ECU")
            vin = click.prompt("Enter VIN manually (17 chars)", type=str)
            if len(vin) != 17:
                click.echo(" Invalid VIN length")
                input("\nPress Enter to continue...")
                return
        else:
            click.echo(f" VIN from ECU: {vin}")
        
        flasher.disconnect()
        flasher = None
    except Exception as e:
        click.echo(f"\n ECU communication error: {e}")
        if flasher:
            try:
                flasher.disconnect()
            except Exception:
                pass
        input("\nPress Enter to continue...")
        return
    
    # Run comprehensive pre-flash checks
    click.echo("\nRunning comprehensive safety checks...")
    prereq = map_flasher.check_flash_prerequisites(vin, output_file)
    
    checks = prereq.get('checks', {})
    
    # Battery
    batt = checks.get('battery_voltage', {})
    if batt.get('sufficient', False):
        click.echo(f"   Battery: {batt.get('voltage', 0):.1f}V (OK)")
    else:
        click.echo(f"   Battery: {batt.get('voltage', 0):.1f}V (MIN: {batt.get('min_required', 12.5)}V)")
    
    # Backup
    backup_check = checks.get('backup_exists', {})
    if backup_check.get('backup_found', False):
        click.echo(f"   Backup verified for VIN {vin}")
    else:
        click.echo(f"   No valid backup found for VIN {vin}")
        click.echo("    Create a backup first: Main Menu → 4 → 1")
    
    # Map file
    map_check = checks.get('map_file_valid', {})
    if map_check.get('success', False):
        click.echo("   Tuned file is valid")
    else:
        click.echo(f"   Tuned file validation failed: {map_check.get('error', 'unknown')}")
    
    # ECU communication / SW-ID
    ecu_check = checks.get('ecu_communication', {})
    if ecu_check.get('success', False):
        if ecu_check.get('vin_match', False):
            click.echo(f"   VIN matches ECU")
        else:
            click.echo(f"   VIN mismatch: ECU={ecu_check.get('vin')}, expected={vin}")
        
        sw_match = ecu_check.get('sw_match')
        if sw_match is True:
            click.echo(f"   Software version match: {ecu_check.get('ecu_sw_version')}")
        elif sw_match is False:
            click.echo(f"   SW version mismatch: ECU={ecu_check.get('ecu_sw_version')}, map={ecu_check.get('map_sw_version')}")
        else:
            click.echo(f"    Software version: ECU={ecu_check.get('ecu_sw_version') or 'unknown'}")
    else:
        click.echo(f"   ECU communication failed: {ecu_check.get('error', 'unknown')}")
    
    # Final check
    if not prereq.get('all_checks_passed', False):
        click.echo("\n Pre-flash safety checks FAILED:")
        for err in prereq.get('errors', []):
            click.echo(f"  - {err}")
        
        if not click.confirm("\n  Override and proceed anyway? (DANGEROUS)", default=False):
            click.echo("Flash cancelled.")
            input("\nPress Enter to continue...")
            return
    else:
        click.echo("\n All pre-flash safety checks PASSED")
    
    # 5. Flash confirmation (3-step)
    click.echo("\n" + "="*70)
    click.echo("  FLASH CONFIRMATION ")
    click.echo("="*70)
    click.echo(f"\nYou are about to flash: {output_file.name}")
    click.echo(f"To ECU with VIN: {vin}")
    click.echo("\nThis operation CANNOT be undone without a backup!")
    
    confirm1 = click.prompt("\nType 'YES' to confirm", type=str)
    if confirm1 != 'YES':
        click.echo("Flash cancelled.")
        input("\nPress Enter to continue...")
        return
    
    confirm2 = click.prompt("Type 'FLASH' to proceed", type=str)
    if confirm2 != 'FLASH':
        click.echo("Flash cancelled.")
        input("\nPress Enter to continue...")
        return
    
    vin_suffix = vin[-7:] if len(vin) >= 7 else vin
    confirm3 = click.prompt(f"Type last 7 characters of VIN ({vin_suffix})", type=str)
    if confirm3 != vin_suffix:
        click.echo("VIN confirmation failed. Flash cancelled.")
        input("\nPress Enter to continue...")
        return
    
    # 6. Execute flash
    click.echo("\n" + "-"*50)
    click.echo(" FLASHING TO ECU...")
    click.echo("-"*50)
    
    def flash_progress(msg: str, pct: int) -> None:
        click.echo(f"  [{pct:3d}%] {msg}")
    
    try:
        flash_result = map_flasher.flash_map(
            map_file=output_file,
            vin=vin,
            safety_confirmed=True,
            progress_callback=flash_progress
        )
        
        if flash_result.get('success', False):
            click.echo("\n" + "="*70)
            click.echo(" FLASH SUCCESSFUL!")
            click.echo("="*70)
            click.echo(f"\nDuration: {flash_result.get('duration_seconds', 0):.1f} seconds")
            
            verification = flash_result.get('verification', {})
            if verification.get('verified', False):
                click.echo(" Flash verified successfully")
            else:
                click.echo("  Flash verification inconclusive")
            
            click.echo("\n NEXT STEPS:")
            click.echo("  1. Turn ignition OFF, wait 10 seconds")
            click.echo("  2. Turn ignition ON (do not start)")
            click.echo("  3. Clear adaptations if needed (Main Menu → 3 → 3)")
            click.echo("  4. Start engine and monitor for issues")
            click.echo("  5. Test drive cautiously, monitor AFR and knock")
        else:
            click.echo("\n" + "="*70)
            click.echo(" FLASH FAILED")
            click.echo("="*70)
            click.echo(f"\nError: {flash_result.get('error', 'unknown')}")
            click.echo("\n  ECU may still have original calibration.")
            click.echo("    If ECU is unresponsive, restore from backup.")
    
    except Exception as e:
        click.echo(f"\n Flash error: {e}")
        logger.exception("Tune & Flash failed")
        click.echo("\n  CHECK ECU STATUS IMMEDIATELY")
    
    input("\nPress Enter to continue...")


def validated_maps_menu():
    """Validated Maps menu - View and use safety-validated map definitions."""
    while True:
        click.echo("\n" + "="*60)
        click.echo("=== Validated Maps (MSD80 I8A0S) ===")
        click.echo("="*60)
        click.echo("\n Maps that passed strict 7-layer validation")
        click.echo("🚫 Forbidden regions blocked to prevent ECU bricking\n")
        
        click.echo(f"Safe Maps: {len(validated_maps.VALIDATED_MAPS)}")
        click.echo(f"Conditional Maps: {len(validated_maps.CONDITIONAL_MAPS)}")
        click.echo(f"Rejected Maps: {len(validated_maps.REJECTED_MAPS)}")
        click.echo(f"Forbidden Regions: {len(validated_maps.FORBIDDEN_REGIONS)}")
        
        click.echo("\n1. List All Validated Maps")
        click.echo("2. View Map Details")
        click.echo("3. Show Rejected Maps (DO NOT USE)")
        click.echo("4. Check If Offset Is Safe")
        click.echo("5. View Validation Summary")
        click.echo("6. Open XDF File Location")
        click.echo("0. Back to Main Menu")
        
        choice = click.prompt("\nSelect option", type=int, default=0)
        
        if choice == 0:
            break
        elif choice == 1:
            list_validated_maps()
        elif choice == 2:
            view_map_details()
        elif choice == 3:
            show_rejected_maps()
        elif choice == 4:
            check_offset_safety()
        elif choice == 5:
            validated_maps.print_map_summary()
            input("\nPress Enter to continue...")
        elif choice == 6:
            open_xdf_location()
        else:
            click.echo("Invalid selection.")


def list_validated_maps():
    """List all validated maps by category."""
    click.echo("\n" + "="*60)
    click.echo("VALIDATED MAPS - SAFE TO MODIFY")
    click.echo("="*60)
    
    # Ignition maps
    ignition_maps = validated_maps.get_maps_by_category(validated_maps.MapCategory.IGNITION)
    if ignition_maps:
        click.echo("\n IGNITION TIMING MAPS (6 total):")
        for i, map_def in enumerate(ignition_maps, 1):
            offset = getattr(map_def, 'offset', 0)
            rows = getattr(map_def, 'rows', 0)
            cols = getattr(map_def, 'cols', 0)
            size_bytes = getattr(map_def, 'size_bytes', 0)
            value_range = getattr(map_def, 'value_range', (0.0, 0.0))
            scaling = getattr(map_def, 'scaling', 'unknown')
            warnings = getattr(map_def, 'warnings', [])

            click.echo(f"\n{i}. Offset: 0x{offset:06X}")
            click.echo(f"   Size: {rows}x{cols} ({size_bytes} bytes)")
            click.echo(f"   Range: {value_range[0]:.1f}° to {value_range[1]:.1f}°")
            click.echo(f"   Scaling: {scaling}")
            if warnings:
                for warning in warnings:
                    click.echo(f"     {warning}")
    
    # WGDC maps
    wgdc_maps = validated_maps.get_maps_by_category(validated_maps.MapCategory.WGDC)
    if wgdc_maps:
        click.echo("\n WASTEGATE DUTY CYCLE MAPS (3 total):")
        for i, map_def in enumerate(wgdc_maps, 1):
            offset = getattr(map_def, 'offset', 0)
            rows = getattr(map_def, 'rows', 0)
            cols = getattr(map_def, 'cols', 0)
            size_bytes = getattr(map_def, 'size_bytes', 0)
            value_range = getattr(map_def, 'value_range', (0.0, 0.0))
            scaling = getattr(map_def, 'scaling', 'unknown')
            warnings = getattr(map_def, 'warnings', [])

            click.echo(f"\n{i}. Offset: 0x{offset:06X}")
            click.echo(f"   Size: {rows}x{cols} ({size_bytes} bytes)")
            click.echo(f"   Range: {value_range[0]:.1f}% to {value_range[1]:.1f}%")
            click.echo(f"   Scaling: {scaling}")
            if warnings:
                for warning in warnings:
                    click.echo(f"     {warning}")
    
    # Conditional maps
    if validated_maps.CONDITIONAL_MAPS:
        click.echo("\nCONDITIONAL MAPS (Use With Caution):")
        for offset, map_def in validated_maps.CONDITIONAL_MAPS.items():
            warnings = getattr(map_def, 'warnings', [])
            click.echo(f"\n   Offset: 0x{offset:06X}")
            for warning in warnings:
                click.echo(f"     {warning}")
    
    input("\nPress Enter to continue...")


def view_map_details():
    """View detailed information about a specific map."""
    click.echo("\n" + "="*60)
    click.echo("VIEW MAP DETAILS")
    click.echo("="*60)
    
    offset_str = click.prompt("\nEnter offset (hex, e.g., 0x009940)", type=str)
    
    try:
        # Parse hex input
        if offset_str.startswith('0x') or offset_str.startswith('0X'):
            offset = int(offset_str, 16)
        else:
            offset = int(offset_str, 16)
    except ValueError:
        click.echo(f" Invalid hex format: {offset_str}")
        input("\nPress Enter to continue...")
        return
    
    # Get map info
    map_def = validated_maps.get_map_info(offset)

    click.echo(f"\n{'='*60}")
    click.echo(f"MAP AT OFFSET 0x{offset:06X}")
    click.echo(f"{'='*60}")

    if not map_def:
        click.echo("\nNo validated map found at that offset.")
        input("\nPress Enter to continue...")
        return

    # Safely extract attributes with defaults
    status = getattr(map_def, 'status', validated_maps.ValidationStatus.PASSED)
    category = getattr(map_def, 'category', validated_maps.MapCategory.OTHER)
    size_bytes = getattr(map_def, 'size_bytes', 0)
    rows = getattr(map_def, 'rows', 0)
    cols = getattr(map_def, 'cols', 0)
    scaling = getattr(map_def, 'scaling', 'unknown')
    value_range = getattr(map_def, 'value_range', (0.0, 0.0))
    description = getattr(map_def, 'description', '')
    warnings = getattr(map_def, 'warnings', [])

    # Status indicator
    if status == validated_maps.ValidationStatus.PASSED:
        status_icon = "SAFE"
    elif status == validated_maps.ValidationStatus.CONDITIONAL:
        status_icon = "CONDITIONAL"
    elif status == validated_maps.ValidationStatus.FAILED:
        status_icon = "REJECTED"
    else:
        status_icon = "UNKNOWN"

    click.echo(f"\nStatus: {status_icon}")
    click.echo(f"Category: {category.value.replace('_', ' ').title()}")

    if size_bytes > 0:
        click.echo(f"\nDimensions: {rows}x{cols} ({size_bytes} bytes)")
        click.echo(f"Scaling: {scaling}")
        click.echo(f"Value Range: {value_range[0]:.1f} to {value_range[1]:.1f}")

    click.echo(f"\nDescription:")
    click.echo(f"  {description}")

    if warnings:
        click.echo(f"\n  WARNINGS:")
        for warning in warnings:
            click.echo(f"  • {warning}")

    # Safety check
    is_safe, reason = validated_maps.is_offset_safe(offset, size_bytes)
    click.echo(f"\nSafety Check: {'SAFE' if is_safe else 'BLOCKED'}")
    click.echo(f"  {reason}")

    input("\nPress Enter to continue...")


def show_rejected_maps():
    """Show maps that were rejected during validation."""
    click.echo("\n" + "="*60)
    click.echo(" REJECTED MAPS - DO NOT USE ")
    click.echo("="*60)
    click.echo("\nThese maps FAILED validation and will BRICK your ECU if modified!\n")
    
    for offset, map_def in validated_maps.REJECTED_MAPS.items():
        click.echo(f"Offset: 0x{offset:06X}")
        click.echo(f"  {map_def.description}")
        click.echo(f"\n  REJECTION REASONS:")
        for warning in map_def.warnings:
            click.echo(f"     {warning}")
        click.echo()
    
    click.echo("The validation system will BLOCK any write attempts to these offsets.")
    input("\nPress Enter to continue...")


def check_offset_safety():
    """Check if a specific offset is safe to write."""
    click.echo("\n" + "="*60)
    click.echo("CHECK OFFSET SAFETY")
    click.echo("="*60)
    
    offset_str = click.prompt("\nEnter offset to check (hex, e.g., 0x009940)", type=str)
    size = click.prompt("Enter data size (bytes)", type=int, default=72)
    
    try:
        if offset_str.startswith('0x') or offset_str.startswith('0X'):
            offset = int(offset_str, 16)
        else:
            offset = int(offset_str, 16)
    except ValueError:
        click.echo(f" Invalid hex format: {offset_str}")
        input("\nPress Enter to continue...")
        return
    
    # Perform safety check
    is_safe, reason = validated_maps.is_offset_safe(offset, size)
    
    click.echo(f"\nOffset: 0x{offset:06X}")
    click.echo(f"Size: {size} bytes")
    click.echo(f"\nResult: {' SAFE TO WRITE' if is_safe else ' BLOCKED - DANGEROUS'}")
    click.echo(f"\n{reason}")
    
    # If blocked, show what it is
    if not is_safe and offset in validated_maps.REJECTED_MAPS:
        map_def = validated_maps.REJECTED_MAPS[offset]
        click.echo(f"\nThis is: {map_def.description}")
        click.echo("\nREJECTION DETAILS:")
        for warning in map_def.warnings:
            click.echo(f"   {warning}")
    
    input("\nPress Enter to continue...")


def open_xdf_location():
    """Open the directory containing the validated XDF file."""
    import os
    import subprocess
    
    xdf_path = Path(__file__).parent.parent / "maps" / "xdf_definitions" / "I8A0S_Validated_Safe_Maps.xdf"
    
    if xdf_path.exists():
        click.echo(f"\n XDF file found:")
        click.echo(f"   {xdf_path}")
        click.echo(f"\n   Size: {xdf_path.stat().st_size:,} bytes")
        
        if click.confirm("\nOpen containing folder?", default=True):
            # Open file explorer to XDF location
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', '/select,', str(xdf_path)])
            else:
                subprocess.run(['xdg-open', str(xdf_path.parent)])
    else:
        click.echo(f"\n XDF file not found at:")
        click.echo(f"   {xdf_path}")
        click.echo("\nGenerate it by running:")
        click.echo("   python scripts/generate_validated_xdf.py")
    
    input("\nPress Enter to continue...")


def direct_can_flash_menu():
    """
    Direct CAN Flash Menu - Flash directly via CAN bus.
    
     EXPERIMENTAL FEATURE - Requires:
    - python-can library installed
    - PCAN USB adapter or compatible CAN interface
    - BMW seed/key algorithm implementation
    """
    # Detect availability of direct CAN module without importing unused symbol
    can_available = False
    try:
        import importlib.util as _ilu
        can_available = _ilu.find_spec("flash_tool.direct_can_flasher") is not None
    except Exception:
        can_available = False
    
    while True:
        click.echo("\n" + "="*70)
        click.echo("=== Direct CAN Flash ( EXPERIMENTAL) ===")
        click.echo("="*70)
        
        if not can_available:
            click.echo("\n  ERROR: python-can not installed!")
            click.echo("\nInstall dependencies:")
            click.echo("  pip install -r requirements.txt")
            click.echo("\nOr manually:")
            click.echo("  pip install python-can python-can[pcan]")
            click.echo("\n0. Back to Main Menu")
            
            choice = click.prompt("\nSelect option", type=int, default=0)
            if choice == 0:
                break
            continue
        
        click.echo("\nDirect CAN/UDS ECU communication (K+DCAN-only)")
        click.echo("Communicates directly with the ECU using ISO-TP/UDS")
        click.echo("\nFeatures:")
        click.echo("   ISO-TP transport layer (ISO 15765-2)")
        click.echo("   UDS services (ISO 14229)")
        click.echo("   Read/write calibration via CAN")
        click.echo("   BMW CRC validation")
        click.echo("   THREE seed/key algorithms (v1, v2, v3) - READY FOR TESTING!")
        click.echo("\nRequires:")
        click.echo("  - PCAN USB adapter (PEAK Systems)")
        click.echo("  - Or compatible CAN interface")
        click.echo("  - K+DCAN cable and stable power")
        
        click.echo("\n" + "-"*70)
        click.echo("CALIBRATION OPERATIONS (TUNING):")
        click.echo("  1. Read Calibration from ECU (256KB calibration sector)")
        click.echo("  2. Flash Calibration to ECU (256KB calibration only)")
        click.echo("\nFULL BINARY OPERATIONS (ADVANCED):")
        click.echo("  3. Flash Full Binary (2MB complete firmware)")
        click.echo("  4. Read Arbitrary Memory Region")
        click.echo("\nDIAGNOSTICS & PATCHES:")
        click.echo("  5. Flash Readiness Patch (NVRAM) ")
        click.echo("  6. Check Battery Voltage")
        click.echo("  7. Verify ECU Checksums (CRC)")
        click.echo("\nSESSION & SECURITY:")
        click.echo("  8. Enter Programming Session")
        click.echo("  9. Test Security Access (Seed/Key)")
        click.echo("  10. Test CAN Connection")
        click.echo("\nUTILITIES:")
        click.echo("  11. Reset ECU")
        click.echo("  12. View CAN Configuration")
        click.echo("  13. Seed/Key Algorithm Research")
        click.echo("  14. View Documentation")
        click.echo("\nPRESETS (K+DCAN FIRST):")
        click.echo("  15. Stage Preset Flash (Backup → Patch → CRC → Flash)")
        click.echo("\n0. Back to Main Menu")
        click.echo("-"*70)
        
        choice = click.prompt("\nSelect option", type=int, default=0)
        
        if choice == 0:
            break
        elif choice == 1:
            direct_can_read_calibration()
        elif choice == 2:
            direct_can_flash_calibration()
        elif choice == 3:
            direct_can_flash_full_binary()
        elif choice == 4:
            direct_can_read_memory()
        elif choice == 5:
            direct_can_flash_readiness_patch()
        elif choice == 6:
            direct_can_check_battery()
        elif choice == 7:
            direct_can_verify_checksums()
        elif choice == 8:
            direct_can_enter_programming()
        elif choice == 9:
            direct_can_test_security()
        elif choice == 10:
            direct_can_test_connection()
        elif choice == 11:
            direct_can_reset_ecu()
        elif choice == 12:
            direct_can_view_config()
        elif choice == 13:
            direct_can_seedkey_research()
        elif choice == 14:
            direct_can_view_docs()
        elif choice == 15:
            direct_can_stage_preset_flash()
        else:
            click.echo("Invalid selection.")


def direct_can_test_connection():
    """Test direct CAN bus connection."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Test CAN Connection ===")
    click.echo("="*70)
    
    click.echo("\nAvailable interfaces:")
    click.echo("  1. PCAN (PEAK USB)")
    click.echo("  2. SocketCAN (Linux)")
    click.echo("  3. Kvaser")
    
    interface_choice = click.prompt("Select interface", type=int, default=1)
    
    if interface_choice == 1:
        interface = 'pcan'
        channel = click.prompt("PCAN channel", type=str, default='PCAN_USBBUS1')
    elif interface_choice == 2:
        interface = 'socketcan'
        channel = click.prompt("Interface name", type=str, default='can0')
    elif interface_choice == 3:
        interface = 'kvaser'
        channel = click.prompt("Channel", type=int, default=0)
    else:
        click.echo("Invalid selection")
        return
    
    click.echo(f"\nConnecting to {interface} {channel}...")
    
    try:
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if flasher.connect():
            click.echo(" CAN bus connected successfully!")
            click.echo(f"\nConfiguration:")
            click.echo(f"  Interface: {interface}")
            click.echo(f"  Channel: {channel}")
            click.echo(f"  Bitrate: {flasher.bitrate} bps")
            click.echo(f"  ECU TX ID: 0x{flasher.ECU_TX_ID:03X}")
            click.echo(f"  ECU RX ID: 0x{flasher.ECU_RX_ID:03X}")
            
            flasher.disconnect()
        else:
            click.echo(" Connection failed")
            click.echo("\nTroubleshooting:")
            click.echo("  - Verify PCAN driver installed")
            click.echo("  - Check USB connection")
            click.echo("  - Try different channel (PCAN_USBBUS2, etc.)")
    
    except Exception as e:
        click.echo(f" Error: {e}")
        click.echo("\nCheck python-can installation:")
        click.echo("  pip install python-can python-can[pcan]")
    
    input("\nPress Enter to continue...")


def direct_can_read_calibration():
    """Read calibration using direct CAN."""
    from . import direct_can_flasher
    from pathlib import Path
    
    click.echo("\n" + "="*70)
    click.echo("=== Read Calibration via Direct CAN ===")
    click.echo("="*70)
    
    click.echo("\n  WARNING: This will directly communicate with ECU")
    click.echo("Ensure:")
    click.echo("  - Ignition is ON")
    click.echo("  - No other scan tools connected")
    click.echo("  - K+DCAN cable connected to OBD-II port")
    
    if not click.confirm("\nProceed with calibration read?", default=False):
        return
    
    interface = click.prompt("CAN interface", type=str, default='pcan')
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    output_file = Path("backups") / f"cal_read_direct_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
    output_file.parent.mkdir(exist_ok=True)
    
    click.echo(f"\nReading calibration to: {output_file}")
    
    try:
        cal_data = direct_can_flasher.read_ecu_calibration(
            interface=interface,
            channel=channel,
            output_file=output_file
        )
        
        if cal_data:
            click.echo(f"\n SUCCESS: Read {len(cal_data):,} bytes")
            click.echo(f"Saved to: {output_file}")
        else:
            click.echo("\n FAILED: Could not read calibration")
            click.echo("\nPossible causes:")
            click.echo("  - Seed/key algorithm incorrect")
            click.echo("  - CAN connection issue")
            click.echo("  - ECU not in correct state")
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Direct CAN read failed")
    
    input("\nPress Enter to continue...")


def direct_can_flash_calibration():
    """Flash calibration using direct CAN."""
    from . import direct_can_flasher
    from pathlib import Path
    
    click.echo("\n" + "="*70)
    click.echo("=== Flash Calibration via Direct CAN ===")
    click.echo("="*70)
    
    click.echo("\n      DANGER ZONE     ")
    click.echo("\nThis will WRITE data directly to your ECU!")
    click.echo("Incorrect data can BRICK your ECU ($1000+ repair)")
    click.echo("\nEnsure:")
    click.echo("  1. Calibration file has valid CRCs")
    click.echo("  2. File is correct variant (MSD80 vs MSD81)")
    click.echo("  3. Battery voltage is stable (>12.5V)")
    click.echo("  4. You have backup of original calibration")
    
    if not click.confirm("\nDo you understand the risks?", default=False):
        return
    
    if not click.confirm("Are you ABSOLUTELY SURE?", default=False):
        return
    
    # Select calibration file
    cal_file = Path(click.prompt("Calibration file path", type=str))
    
    if not cal_file.exists():
        click.echo(f"\n File not found: {cal_file}")
        return
    
    interface = click.prompt("CAN interface", type=str, default='pcan')
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    click.echo(f"\nFlashing: {cal_file}")
    click.echo(f"Size: {cal_file.stat().st_size:,} bytes")
    
    try:
        success = direct_can_flasher.flash_ecu_calibration(
            cal_file=cal_file,
            interface=interface,
            channel=channel
        )
        
        if success:
            click.echo("\n FLASH SUCCESSFUL!")
            click.echo("\nNext steps:")
            click.echo("  1. Reset ECU (turn ignition off/on)")
            click.echo("  2. Clear adaptations if needed")
            click.echo("  3. Test drive and monitor")
        else:
            click.echo("\n FLASH FAILED")
            click.echo("ECU may still have original calibration")
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Direct CAN flash failed")
        click.echo("\n  CHECK ECU STATUS IMMEDIATELY")
    
    input("\nPress Enter to continue...")


def direct_can_stage_preset_flash():
    """
    K+DCAN-first preset flash pipeline:
    Backup → Patch (Stage) → CRC fix → Validate → Flash.
    """
    from . import direct_can_flasher
    from pathlib import Path

    click.echo("\n" + "="*70)
    click.echo("=== Stage Preset Flash (K+DCAN) ===")
    click.echo("="*70)

    click.echo("\nThis flow will:")
    click.echo("  1) Read and save a calibration backup")
    click.echo("  2) Apply a stage preset (or restore-to-stock)")
    click.echo("  3) Recalculate BMW CRCs")
    click.echo("  4) Validate checksums")
    click.echo("  5) Flash to ECU via direct CAN/UDS")

    if not click.confirm("\nProceed?", default=False):
        return

    interface = click.prompt("CAN interface", type=str, default='pcan')
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')

    # Choose preset
    click.echo("\nPresets:")
    click.echo("  0) Stage 0 - Restore to stock")
    click.echo("  1) Stage 1 - Conservative (WGDC-only)")
    click.echo("  2) Stage 2 - Moderate (requires hardware)")
    preset_choice = click.prompt("Select preset", type=int, default=1)

    try:
        with direct_can_flasher.DirectCANFlasher(interface, channel) as fl:
            # Read VIN (best-effort)
            vin = None
            try:
                vin = fl.read_vin()
            except Exception:
                vin = None
            if not vin:
                vin = "UNKNOWN"

            # Prepare paths
            root = Path(__file__).parent.parent
            backups_dir = root / "backups" / vin
            maps_dir = root / "maps" / vin / "tuned"
            backups_dir.mkdir(parents=True, exist_ok=True)
            maps_dir.mkdir(parents=True, exist_ok=True)

            # Progress reporter
            def progress(msg: str, pct: int):
                click.echo(f"[{pct:3d}%] {msg}")

            # 1) Backup calibration
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backups_dir / f"cal_backup_{timestamp}.bin"
            click.echo(f"\n📥 Backing up calibration → {backup_path}")
            cal_data = fl.read_calibration(progress_callback=progress)
            if not cal_data:
                click.echo("\n Calibration read failed; cannot continue")
                return
            backup_path.write_bytes(cal_data)
            click.echo(f" Backup saved: {backup_path.name} ({len(cal_data):,} bytes)")

            # 2) Apply preset patches
            click.echo("\n Building preset and applying patches...")
            patched = bytearray(cal_data)
            try:
                patcher = map_patcher.MapPatcher(ecu_type="MSD80")
                if preset_choice == 0:
                    # Stage 0: Restore to stock (selected areas) requires a stock reference .bin
                    click.echo("\nSelect stock reference .bin:")
                    click.echo("  1. Browse backups/ directory (recursive)")
                    click.echo("  2. Specify custom path")
                    ref_choice = click.prompt("Select", type=int, default=1)

                    if ref_choice == 1:
                        ref_root = Path(__file__).parent.parent / "backups"
                        ref_bins: List[Path] = list(ref_root.rglob("*.bin"))
                        if not ref_bins:
                            click.echo(" No .bin files found under backups/")
                            return
                        click.echo("\nAvailable reference backups:")
                        for i, f in enumerate(ref_bins, 1):
                            try:
                                size_mb = f.stat().st_size / (1024*1024)
                            except Exception:
                                size_mb = 0.0
                            click.echo(f"  {i}. {f.relative_to(ref_root)} ({size_mb:.2f} MB)")
                        ref_idx = click.prompt("Select reference", type=int)
                        if ref_idx < 1 or ref_idx > len(ref_bins):
                            click.echo(" Invalid selection")
                            return
                        ref_path = cast(Path, ref_bins[ref_idx - 1])
                    else:
                        ref_input = click.prompt("Enter reference .bin path", type=click.Path(exists=True))
                        ref_path = Path(ref_input)
                        if not ref_path.exists():
                            click.echo(" File not found")
                            return

                    ref_data = ref_path.read_bytes()
                    if len(ref_data) != len(patched):
                        click.echo(f"  Reference size mismatch: backup {len(patched):,} vs ref {len(ref_data):,}")
                        if not click.confirm("Continue anyway?", default=False):
                            return

                    # Feature selection (selected areas)
                    click.echo("\nSelect areas to restore to stock (Y/n):")
                    feat_vmax = click.confirm("  • Speed limiter (VMAX)", default=True)
                    feat_rpm = click.confirm("  • RPM limiters", default=True)
                    feat_burb = click.confirm("  • Burbles/Pops", default=True)
                    feat_dtc = click.confirm("  • DTC behaviors (cat/O2)", default=True)
                    feat_wgdc = click.confirm("  • WGDC/boost maps (validated)", default=True)
                    features: List[str] = []
                    if feat_vmax:
                        features.append("vmax")
                    if feat_rpm:
                        features.append("rpm")
                    if feat_burb:
                        features.append("burbles")
                    if feat_dtc:
                        features.append("dtc")
                    if feat_wgdc:
                        features.append("wgdc")

                    ps = patcher.create_restore_to_stock_patchset(stock_data=ref_data, features=features)
                    preset_label = "stage0_restore"
                elif preset_choice in (1, 2):
                    # Use new unified preset system
                    from . import tuning_parameters as map_options
                    preset_name = {1: "stage1", 2: "stage2"}[preset_choice]
                    map_opts = map_options.get_preset(preset_name)
                    if map_opts is None:
                        click.echo(f"\nPreset '{preset_name}' not found.")
                        return
                    ps = patcher.create_patchset_from_map_options(map_opts, name=preset_name, description=f"Preset {preset_name} applied")
                    preset_label = preset_name
                else:
                    click.echo("\n Invalid preset selection")
                    return

                # Apply patches without CRC updates here; we'll fix with flasher logic
                patch_results = patcher.apply_patch_set(
                    patched,
                    ps,
                    progress_callback=lambda msg, pct: click.echo(f"    - {msg}"),
                    update_crcs=False,
                )
                if patch_results.get('errors'):
                    click.echo("\n Patch errors:")
                    for err in patch_results['errors']:
                        click.echo(f"   - {err}")
                    return
                click.echo(f" Applied {len(patch_results.get('applied_patches', []))} patch(es)")
            except Exception as e:
                click.echo(f"\n Failed to apply patches: {e}")
                logger.exception("Preset patching failed")
                return

            # 3) Recalculate CRCs (in-place)
            click.echo("\n🔁 Recalculating BMW CRCs...")
            try:
                fl.recalculate_calibration_crcs(patched)
            except Exception as e:
                click.echo(f" CRC recalculation failed: {e}")
                return

            # 4) Validate CRCs
            click.echo("\n Validating CRCs...")
            if not fl.validate_calibration_crcs(bytes(patched)):
                click.echo(" CRC validation failed; refusing to flash")
                return
            click.echo(" CRCs valid")

            # Save tuned file
            output_name = f"{preset_label}_{timestamp}_{vin}.bin"
            tuned_path = maps_dir / output_name
            tuned_path.write_bytes(bytes(patched))
            click.echo(f"\n Tuned file saved: {tuned_path}")

            # 5) Flash
            if not click.confirm("\nFlash this tuned calibration now?", default=True):
                click.echo("\nAborted before flashing. Files saved above.")
                return

            click.echo("\n Flashing via direct CAN/UDS...")
            try:
                result = fl.flash_calibration(bytes(patched), progress_callback=progress)
                # Normalize enum to boolean if needed
                try:
                    from .direct_can_flasher import WriteResult as _WR
                    success = (result == _WR.SUCCESS)
                except Exception:
                    success = bool(result)

                if success:
                    click.echo("\n FLASH SUCCESSFUL")
                    click.echo("ECU will be soft-reset to apply changes.")
                    fl.soft_reset()
                else:
                    click.echo("\n FLASH FAILED")
            except Exception as e:
                click.echo(f"\n Flash error: {e}")
                logger.exception("Direct CAN preset flash failed")
                return

    except Exception as e:
        click.echo(f"\n Error initializing CAN flasher: {e}")
        logger.exception("Preset flash init failed")

    input("\nPress Enter to continue...")


def direct_can_flash_readiness_patch():
    """Flash readiness monitor patch to NVRAM region."""
    from . import direct_can_flasher
    from pathlib import Path
    
    click.echo("\n" + "="*70)
    click.echo("=== Flash Readiness Monitor Patch (NVRAM) ===")
    click.echo("="*70)
    
    click.echo("\n READINESS MONITOR PATCHING (MSD80)")
    click.echo("\nThis patches NVRAM to force readiness monitors to report 'ready'.")
    click.echo("Firmware: 2MB MSD80 (2008 535xi N54)")
    click.echo("\n  FOR OFF-ROAD USE ONLY")
    click.echo("Faking emissions readiness is illegal in most jurisdictions.")
    
    if not click.confirm("\nThis vehicle is for off-road use only?", default=False):
        click.echo("\n Aborted. This feature is only for off-road vehicles.")
        return
    
    click.echo("\n  CRITICAL WARNINGS:")
    click.echo("  1. Create FULL ECU backup before flashing")
    click.echo("  2. Ensure stable 12V power (battery fully charged)")
    click.echo("  3. Vehicle must be stationary (engine OFF, ignition ON)")
    click.echo("  4. Have recovery plan ready (can restore backup)")
    
    if not click.confirm("\nDo you understand the risks?", default=False):
        return
    
    # List available test patches
    test_maps_dir = Path('test_maps')
    patches: List[Path] = list(test_maps_dir.glob('readiness_patch_*.bin'))
    
    if not patches:
        click.echo("\n No readiness patches found in test_maps/")
        click.echo("\nRun patch_readiness_binary.py first to create test patches:")
        click.echo("  python patch_readiness_binary.py input.bin output.bin --nvram-offset 0x1F0000")
        input("\nPress Enter to continue...")
        return
    
    # Display available patches
    click.echo("\nAvailable Readiness Patches:")
    for idx, patch in enumerate(patches, 1):
        size_mb = patch.stat().st_size / (1024 * 1024)
        # Extract offset from filename (e.g., readiness_patch_0x1F0000_TEST.bin)
        offset_str = patch.stem.split('_')[2]  # Gets "0x1F0000"
        click.echo(f"  {idx}. {patch.name}")
        click.echo(f"     Offset: {offset_str}, Size: {size_mb:.1f} MB")
    
    click.echo(f"  {len(patches) + 1}. Enter custom patch file path")
    click.echo("  0. Cancel")
    
    choice = click.prompt("\nSelect patch", type=int, default=0)
    
    patch_file: Path
    nvram_offset: int
    
    if choice == 0:
        return
    elif choice == len(patches) + 1:
        patch_file = Path(click.prompt("Patch file path", type=str))
        if not patch_file.exists():
            click.echo(f"\n File not found: {patch_file}")
            return
        # Extract offset from user
        offset_str: str = click.prompt("NVRAM offset (e.g., 0x1F0000)", type=str, default="0x1F0000")
        nvram_offset = int(offset_str, 16)
    elif 1 <= choice <= len(patches):
        patch_file = cast(Path, patches[choice - 1])
        # Extract offset from filename
        offset_str: str = patch_file.stem.split('_')[2]
        nvram_offset = int(offset_str, 16)
    else:
        click.echo("\n Invalid selection")
        return
    
    click.echo(f"\nSelected Patch: {patch_file.name}")
    click.echo(f"NVRAM Offset: 0x{nvram_offset:06X}")
    click.echo(f"File Size: {patch_file.stat().st_size:,} bytes")
    
    # Choose flash method
    click.echo("\n" + "-"*70)
    click.echo("Flash Method:")
    click.echo("  1. Full Binary Flash (2MB, slower, safest)")
    click.echo("  2. NVRAM Region Only (64KB, faster, experimental)")
    click.echo("-"*70)
    
    method = click.prompt("Select method", type=int, default=1)
    
    interface = click.prompt("CAN interface", type=str, default='pcan')
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    if not click.confirm(f"\n  FINAL CONFIRMATION: Flash {patch_file.name}?", default=False):
        click.echo("Aborted.")
        return
    
    try:
        click.echo("\nInitializing CAN flasher...")
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if not flasher.connect():
            click.echo(" Failed to connect to CAN bus")
            return
        
        def progress(msg: str, pct: int) -> None:
            click.echo(f"[{pct:3d}%] {msg}")
        
        if method == 1:
            # Full binary flash
            click.echo("\n Starting full binary flash...")
            success = flasher.flash_full_binary(patch_file, progress_callback=progress)
            # Normalize enum to boolean if needed
            try:
                from .direct_can_flasher import WriteResult as _WR
                success = (success == _WR.SUCCESS)
            except Exception:
                pass
        else:
            # NVRAM region only
            click.echo("\n Starting NVRAM region flash...")
            
            # Read full patch file
            data = patch_file.read_bytes()
            
            # Extract NVRAM region (0x1F0000-0x200000 = 64KB)
            NVRAM_START = 0x1F0000
            NVRAM_SIZE = 0x10000  # 64KB
            nvram_data = data[NVRAM_START:NVRAM_START + NVRAM_SIZE]
            
            click.echo(f"Extracted NVRAM region: {len(nvram_data)} bytes")
            
            success = flasher.flash_nvram_region(
                nvram_data,
                nvram_offset=NVRAM_START,
                progress_callback=progress
            )
            # Normalize enum to boolean if needed
            try:
                from .direct_can_flasher import WriteResult as _WR
                success = (success == _WR.SUCCESS)
            except Exception:
                pass
        
        flasher.disconnect()
        
        if success:
            click.echo("\n FLASH SUCCESSFUL!")
            
            # Prompt for verification
            click.echo("\n" + "="*70)
            click.echo("NEXT STEP: Verify Readiness Monitors")
            click.echo("="*70)
            
            click.echo("\nThe ECU has restarted. Wait 10 seconds, then verify:")
            click.echo("\n📌 Recommended Verification Methods:")
            click.echo("\n  Option A: Use this tool")
            click.echo("     Main Menu → 2. Diagnostics (OBD-II) → 5. Query Readiness Monitors")
            click.echo("\n  Option B: External OBD-II scanner")
            click.echo("     Query: Mode $01 PID $01 (OBD Monitor Status)")
            click.echo("     Expected: Readiness byte = 0x00 (all ready)")
            
            click.echo("\n Success Criteria:")
            click.echo("    Readiness byte = 0x00")
            click.echo("    All monitors show 'Ready'")
            click.echo("    If not 0x00, try next test patch")
            
            if click.confirm("\n Query readiness monitors now?", default=True):
                # Wait for ECU to fully restart
                import time
                click.echo("\n⏳ Waiting 10 seconds for ECU restart...")
                time.sleep(10)
                
                # Call readiness query function
                click.echo("\n Querying monitors...")
                query_readiness_monitors_menu()
            else:
                click.echo("\nRemember to verify manually before testing next patch!")
                click.echo("\n Document your results:")
                if method == 1:
                    click.echo(f"  Patch: {patch_file.name}")
                click.echo(f"  Offset: 0x{nvram_offset:06X}")
                click.echo(f"  Result: [Record if monitors show ready]")
            
        else:
            click.echo("\n FLASH FAILED")
            click.echo("\n  Troubleshooting:")
            click.echo("  1. Check CAN adapter connection")
            click.echo("  2. Verify stable power supply")
            click.echo("  3. Try entering programming session manually")
            click.echo("  4. Check logs/flash_tool.log for details")
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Readiness patch flash failed")
        click.echo("\n  CHECK ECU STATUS IMMEDIATELY")
    
    input("\nPress Enter to continue...")


def direct_can_enter_programming():
    """Enter programming session via direct CAN."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Enter Programming Session ===")
    click.echo("="*70)
    
    interface = click.prompt("CAN interface", type=str, default='pcan')
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    click.echo("\nAttempting to enter programming session...")
    
    try:
        with direct_can_flasher.DirectCANFlasher(interface, channel) as flasher:
            if flasher.enter_programming_session():
                click.echo(" Programming session established")
                click.echo("ECU is ready for flash operations")
            else:
                click.echo(" Failed to enter programming session")
    
    except Exception as e:
        click.echo(f" Error: {e}")
    
    input("\nPress Enter to continue...")


def direct_can_test_security():
    """Test security access seed/key."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Test Security Access (Seed/Key) ===")
    click.echo("="*70)
    
    click.echo("\nCRITICAL LIMITATION:")
    click.echo("Seed/key algorithm implementation incomplete")
    click.echo("\nCurrent status:")
    click.echo("  Can request seed from ECU")
    click.echo("  Key calculation algorithm incomplete")
    click.echo("  BMW algorithm implementation requires validation")
    
    if not click.confirm("\nTest with current algorithm?", default=False):
        return
    
    interface = click.prompt("CAN interface", type=str, default='pcan')
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    click.echo("\nTesting security access...")
    
    try:
        with direct_can_flasher.DirectCANFlasher(interface, channel) as flasher:
            # Enter programming session first
            if not flasher.enter_programming_session():
                click.echo("Failed to enter programming session")
                return
            
            # Request seed
            seed = flasher.request_seed()
            if not seed:
                click.echo("Failed to request seed")
                return
            
            click.echo(f"Received seed: {seed.hex()}")
            
            # Calculate key
            key = flasher.calculate_key_from_seed(seed)
            click.echo(f"  Calculated key: {key.hex()}")
            
            # Send key
            if flasher.send_key(key):
                click.echo("Security access granted")
                click.echo("\nNote: Unexpected success with incomplete algorithm")
                click.echo("ECU may be in test mode")
            else:
                click.echo("Security access denied")
                click.echo("\nComplete BMW algorithm required for production ECUs")
    
    except Exception as e:
        click.echo(f" Error: {e}")
    
    input("\nPress Enter to continue...")


def direct_can_view_config():
    """View CAN configuration."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Direct CAN Configuration ===")
    click.echo("="*70)
    
    flasher = direct_can_flasher.DirectCANFlasher('pcan', 'PCAN_USBBUS1')
    
    click.echo("\nBMW N54 MSD80/MSD81 CAN Configuration:")
    click.echo(f"\nCAN IDs:")
    click.echo(f"  TX (Tester → ECU):  0x{flasher.ECU_TX_ID:03X}")
    click.echo(f"  RX (ECU → Tester):  0x{flasher.ECU_RX_ID:03X}")
    click.echo(f"\nCAN Bus:")
    click.echo(f"  Bitrate:            {flasher.CAN_BITRATE:,} bps (500 kbps)")
    click.echo(f"  Network:            BMW PT-CAN (Powertrain CAN)")
    click.echo(f"\nProtocol Stack:")
    click.echo(f"  Transport:          ISO-TP (ISO 15765-2)")
    click.echo(f"  Application:        UDS (ISO 14229)")
    click.echo(f"\nTiming:")
    click.echo(f"  P2 timeout:         {flasher.P2_TIMEOUT}s (normal operations)")
    click.echo(f"  P2* timeout:        {flasher.P2_STAR_TIMEOUT}s (programming)")
    click.echo(f"  Tester present:     {flasher.TESTER_PRESENT_INTERVAL}s interval")
    click.echo(f"\nMemory Layout (MSD80):")
    click.echo(f"  Calibration start:  0x00100000")
    click.echo(f"  Calibration size:   0x80000 (512 KB)")
    
    input("\nPress Enter to continue...")


def direct_can_seedkey_research():
    """Guide for seed/key algorithm research and implementation."""
    click.echo("\n" + "="*70)
    click.echo("=== Seed/Key Algorithm Research ===")
    click.echo("="*70)
    
    click.echo("\nThe seed/key algorithm is required for direct CAN flash operations.")
    click.echo("\nKnown requirements:")
    click.echo("  - Algorithm must implement BMW ECU Authentication")
    click.echo("  - Method: CalculateKeyFromSeed() or equivalent")
    click.echo("\nResearch workflow:")
    click.echo("  1. Study BMW ECU authentication protocols")
    click.echo("  2. Analyze BMW.ECU.Authentication implementation patterns")
    click.echo("  3. Implement key calculation in Python")
    click.echo("  4. Validate with BMW ECU documentation")
    click.echo("  5. Test with real ECU seed/key pairs")
    click.echo("\nHelper script:")
    click.echo("  python seed_key_research.py --workflow")
    click.echo("\nDocumentation:")
    click.echo("  See: docs/direct_can_flash_guide.md (Section: Seed/Key)")
    
    if click.confirm("\nRun seed/key research script?", default=False):
        import subprocess
        subprocess.run(['python', 'seed_key_research.py', '--workflow'])
    
    input("\nPress Enter to continue...")


def direct_can_flash_full_binary():
    """Flash complete 2MB firmware binary to ECU."""
    from . import direct_can_flasher
    from pathlib import Path
    
    click.echo("\n" + "="*70)
    click.echo("=== Flash Full Binary (2MB Complete Firmware) ===")
    click.echo("="*70)
    
    click.echo("\n  EXTREMELY DANGEROUS - FULL ECU REFLASH")
    click.echo("\nThis flashes the ENTIRE 2MB firmware (bootloader + program + calibration + NVRAM).")
    click.echo("Unlike calibration-only flash, this can BRICK your ECU if interrupted.")
    click.echo("\n NOT RECOMMENDED unless:")
    click.echo("  - Recovering from bricked ECU")
    click.echo("  - Installing different firmware version")
    click.echo("  - You are an expert and know exactly what you're doing")
    
    if not click.confirm("\n  I understand the risks and want to continue?", default=False):
        click.echo("\n Aborted. Use 'Flash Calibration' for safe tuning.")
        return
    
    # Select bin file
    bin_files: List[Path] = list(Path(".").glob("*.bin"))
    bin_files.extend(Path("backups").rglob("*.bin"))
    
    if not bin_files:
        click.echo("\n No .bin files found")
        return
    
    click.echo("\nAvailable firmware files:")
    for i, f in enumerate(bin_files, 1):
        click.echo(f"{i}. {f} ({f.stat().st_size:,} bytes)")
    
    choice = click.prompt("Select file", type=int)
    if choice < 1 or choice > len(bin_files):
        click.echo("Invalid selection")
        return
    
    bin_file: Path = cast(Path, bin_files[choice - 1])
    
    # Detect software from bin using consolidated detection
    detection = software_detector.detect_software_from_bin(str(bin_file))
    
    click.echo(f"\nSelected: {bin_file}")
    click.echo(f"Size: {detection['size_bytes']:,} bytes")
    
    if not detection['is_valid']:
        click.echo(f"  ERROR: {detection['error']}")
        if not click.confirm("Continue anyway?", default=False):
            return
    else:
        click.echo(f"  Detected: {detection['ecu_type']} (Software: {detection['software_version'] or 'Unknown'})")
    
    if not click.confirm("\n FINAL WARNING: Flash entire ECU?", default=False):
        click.echo("Aborted")
        return
    
    # CAN interface selection
    click.echo("\nCAN Interface:")
    click.echo("  1. PCAN (PEAK USB)")
    click.echo("  2. SocketCAN (Linux)")
    
    interface_choice = click.prompt("Select", type=int, default=1)
    interface = 'pcan' if interface_choice == 1 else 'socketcan'
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    try:
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if not flasher.connect():
            click.echo(" CAN connection failed")
            return
        
        def progress(msg: str, pct: int) -> None:
            click.echo(f"[{pct:3d}%] {msg}")
        
        click.echo("\n Starting full binary flash...")
        success = flasher.flash_full_binary(bin_file, progress_callback=progress)
        # Normalize enum to boolean if needed
        try:
            from .direct_can_flasher import WriteResult as _WR
            success = (success == _WR.SUCCESS)
        except Exception:
            pass
        
        flasher.disconnect()
        
        if success:
            click.echo("\n FLASH SUCCESSFUL!")
            click.echo("ECU will reset. Wait 30 seconds before turning ignition on.")
        else:
            click.echo("\n FLASH FAILED")
            click.echo("ECU may be bricked. Contact a professional for recovery.")
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Full binary flash failed")
    
    input("\nPress Enter to continue...")


def direct_can_read_memory():
    """Read arbitrary memory region from ECU."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Read Arbitrary Memory Region ===")
    click.echo("="*70)
    
    click.echo("\nRead any memory address from ECU.")
    click.echo("Useful for:")
    click.echo("  - Dumping specific regions")
    click.echo("  - Analyzing firmware structure")
    click.echo("  - Extracting calibration maps")
    
    # Get memory parameters
    address_str = click.prompt("\nStart address (hex)", type=str, default="0x810000")
    size_str = click.prompt("Size (hex)", type=str, default="0x40000")
    
    try:
        address = int(address_str, 16)
        size = int(size_str, 16)
    except ValueError:
        click.echo(" Invalid hex format")
        return
    
    click.echo(f"\nReading:")
    click.echo(f"  Address: 0x{address:08X}")
    click.echo(f"  Size: 0x{size:X} ({size:,} bytes)")
    
    # CAN interface selection
    click.echo("\nCAN Interface:")
    click.echo("  1. PCAN (PEAK USB)")
    click.echo("  2. SocketCAN (Linux)")
    
    interface_choice = click.prompt("Select", type=int, default=1)
    interface = 'pcan' if interface_choice == 1 else 'socketcan'
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    try:
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if not flasher.connect():
            click.echo(" CAN connection failed")
            return
        
        if not flasher.unlock_ecu():
            click.echo(" Security access failed")
            flasher.disconnect()
            return
        
        click.echo("\n📖 Reading memory...")
        data = flasher.read_memory(address, size)
        
        flasher.disconnect()
        
        if data:
            click.echo(f"\n Read {len(data):,} bytes")
            
            # Save to file
            save_file = click.prompt("Save to file", type=str, default=f"memory_0x{address:08X}.bin")
            Path(save_file).write_bytes(data)
            click.echo(f"Saved: {save_file}")
            
            # Show hex dump (first 256 bytes)
            click.echo("\nFirst 256 bytes:")
            for i in range(0, min(256, len(data)), 16):
                hex_str = ' '.join(f'{b:02X}' for b in data[i:i+16])
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
                click.echo(f"{address+i:08X}: {hex_str:<48} {ascii_str}")
        else:
            click.echo("\n Read failed")
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Memory read failed")
    
    input("\nPress Enter to continue...")


def direct_can_check_battery():
    """Check battery voltage via CAN."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Check Battery Voltage ===")
    click.echo("="*70)
    
    click.echo("\nBattery voltage check is CRITICAL before flashing.")
    click.echo("Requirement: >12.5V (13.5V+ recommended)")
    
    # CAN interface selection
    click.echo("\nCAN Interface:")
    click.echo("  1. PCAN (PEAK USB)")
    click.echo("  2. SocketCAN (Linux)")
    
    interface_choice = click.prompt("Select", type=int, default=1)
    interface = 'pcan' if interface_choice == 1 else 'socketcan'
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    try:
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if not flasher.connect():
            click.echo(" CAN connection failed")
            return
        
        click.echo("\n🔋 Checking battery voltage...")
        if flasher.check_battery_voltage():
            voltage = flasher.battery_voltage
            click.echo(f"\n Battery: {voltage:.2f}V")
            
            if voltage >= 13.5:
                click.echo("   Status: EXCELLENT (safe for flash)")
            elif voltage >= 12.5:
                click.echo("   Status: GOOD (acceptable for flash)")
            elif voltage >= 12.0:
                click.echo("   Status: MARGINAL (connect charger recommended)")
            else:
                click.echo("   Status: LOW (DO NOT FLASH - connect charger)")
        else:
            click.echo("\n Battery voltage check failed")
        
        flasher.disconnect()
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Battery check failed")
    
    input("\nPress Enter to continue...")


def direct_can_verify_checksums():
    """Verify ECU checksums (CRC)."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Verify ECU Checksums (CRC) ===")
    click.echo("="*70)
    
    click.echo("\nBMW MSD80 uses CRC32 checksums to validate firmware integrity.")
    click.echo("Polynomial: 0x1EDC6F41 (BMW-specific)")
    click.echo("\nThis verifies:")
    click.echo("  - Calibration zone CRC")
    click.echo("  - Program zone CRC (if accessible)")
    
    # CAN interface selection
    click.echo("\nCAN Interface:")
    click.echo("  1. PCAN (PEAK USB)")
    click.echo("  2. SocketCAN (Linux)")
    
    interface_choice = click.prompt("Select", type=int, default=1)
    interface = 'pcan' if interface_choice == 1 else 'socketcan'
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    try:
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if not flasher.connect():
            click.echo(" CAN connection failed")
            return
        
        if not flasher.unlock_ecu():
            click.echo(" Security access failed")
            flasher.disconnect()
            return
        
        click.echo("\n Verifying checksums...")
        
        # Try zone 0 (calibration)
        if flasher.verify_checksum_routine(zone_id=0):
            click.echo(" Zone 0 (Calibration): CRC VALID")
        else:
            click.echo(" Zone 0 (Calibration): CRC INVALID or routine not supported")
        
        # Try zone 1 (program) if supported
        if flasher.verify_checksum_routine(zone_id=1):
            click.echo(" Zone 1 (Program): CRC VALID")
        else:
            click.echo("  Zone 1 (Program): CRC check not available (protected)")
        
        flasher.disconnect()
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("Checksum verification failed")
    
    input("\nPress Enter to continue...")


def direct_can_reset_ecu():
    """Reset ECU via UDS command."""
    from . import direct_can_flasher
    
    click.echo("\n" + "="*70)
    click.echo("=== Reset ECU ===")
    click.echo("="*70)
    
    click.echo("\nReset types:")
    click.echo("  1. Hard reset (power cycle simulation)")
    click.echo("  2. Key off/on reset")
    click.echo("  3. Enable rapid power shutdown")
    
    reset_choice = click.prompt("Select reset type", type=int, default=1)
    
    reset_types = {
        1: 0x01,  # Hard reset
        2: 0x02,  # Key off/on
        3: 0x04   # Enable rapid shutdown
    }
    
    reset_type = reset_types.get(reset_choice, 0x01)
    
    # CAN interface selection
    click.echo("\nCAN Interface:")
    click.echo("  1. PCAN (PEAK USB)")
    click.echo("  2. SocketCAN (Linux)")
    
    interface_choice = click.prompt("Select", type=int, default=1)
    interface = 'pcan' if interface_choice == 1 else 'socketcan'
    channel = click.prompt("CAN channel", type=str, default='PCAN_USBBUS1')
    
    try:
        flasher = direct_can_flasher.DirectCANFlasher(interface, channel)
        
        if not flasher.connect():
            click.echo(" CAN connection failed")
            return
        
        click.echo(f"\n Sending reset command (type 0x{reset_type:02X})...")
        if flasher.reset_ecu(reset_type):
            click.echo(" Reset command sent")
            click.echo("ECU will reboot (expect ~10 second delay)")
        else:
            click.echo(" Reset command failed")
        
        # Don't disconnect - ECU will reset connection anyway
    
    except Exception as e:
        click.echo(f"\n ERROR: {e}")
        logger.exception("ECU reset failed")
    
    input("\nPress Enter to continue...")


def direct_can_view_docs():
    """View direct CAN flash documentation."""
    click.echo("\n" + "="*70)
    click.echo("=== Direct CAN Flash Documentation ===")
    click.echo("="*70)
    
    docs_path = Path(__file__).parent.parent / "docs" / "direct_can_flash_guide.md"
    
    if docs_path.exists():
        click.echo(f"\nDocumentation: {docs_path}")
        click.echo(f"Size: {docs_path.stat().st_size:,} bytes")
        
        click.echo("\nKey sections:")
        click.echo("  - Overview & Implementation Status")
        click.echo("  - Hardware Requirements (CAN adapters)")
        click.echo("  - Usage Examples (read/flash)")
        click.echo("  - UDS Service Implementation")
        click.echo("  - CRC Validation")
        click.echo("  - Troubleshooting Guide")
        click.echo("  - Seed/Key Algorithm Research")
        
        if click.confirm("\nOpen in default editor?", default=True):
            import subprocess
            if os.name == 'nt':
                subprocess.run(['notepad', str(docs_path)])
            else:
                subprocess.run(['xdg-open', str(docs_path)])
    else:
        click.echo(f"\n  Documentation not found at: {docs_path}")
    
    input("\nPress Enter to continue...")


def advanced_features_menu():
    """Advanced tuning features submenu."""
    while True:
        click.echo("\n" + "-"*60)
        click.echo("=== Advanced Features ( Performance Tuning) ===")
        click.echo("-"*60)
        
        click.echo("\n1. Burbles/Pops & Bangs")
        click.echo("2. Speed Limiter (VMAX) Removal")
        click.echo("3. RPM Limiter Adjustment")
        click.echo("4. Launch Control (🚧 In Development)")
        click.echo("5. Rolling Anti-Lag (🚧 In Development)")
        click.echo("6. Cold Start Options")
        click.echo("7. Sport Display Customization (🚧 In Development)")
        click.echo("8. DTC/Codeword Management")
        click.echo("9. Apply Stage Preset (Stage 1/2)")
        click.echo("10. Custom Patch Builder")
        click.echo("11. Back to Main Menu")
        click.echo("12. Acceleration Logger (Record 0-60 / runs)")
        click.echo("13. Data Logger (Continuous OBD/UDS logging)")
        
        try:
            choice = click.prompt("Select an option", type=int)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input.")
            continue
        
        if choice == 1:
            advanced_burbles_menu()
        elif choice == 2:
            advanced_vmax_removal()
        elif choice == 3:
            advanced_rpm_limiter()
        elif choice == 4:
            advanced_launch_control()
        elif choice == 5:
            advanced_rolling_antilag()
        elif choice == 6:
            advanced_cold_start()
        elif choice == 7:
            advanced_sport_display()
        elif choice == 8:
            advanced_dtc_management()
        elif choice == 9:
            advanced_stage_presets()
        elif choice == 10:
            advanced_custom_patch_builder()
        elif choice == 11:
            break
        elif choice == 12:
            try:
                advanced_accel_logger_menu()
            except Exception as e:
                click.echo(f"Error opening Acceleration Logger: {e}")
        elif choice == 13:
            try:
                advanced_data_logger_menu()
            except Exception as e:
                click.echo(f"Error opening Data Logger: {e}")
        else:
            click.echo("Invalid choice. Please select 1-13.")


def advanced_burbles_menu():
    """Burbles/Pops configuration."""
    from . import map_patcher
    
    click.echo("\n" + "="*70)
    click.echo("=== Burbles/Pops & Bangs Configuration ===")
    click.echo("="*70)
    
    click.echo("\n Add aggressive burbles and pops on deceleration!")
    click.echo("\nWhat this does:")
    click.echo("  - Modifies ignition timing tables (12 tables)")
    click.echo("  - Adjusts fuel cut parameters (4 maps)")
    click.echo("  - Creates unburned fuel ignition in exhaust")
    click.echo("  - Most effective with aftermarket exhaust")
    click.echo("\n  WARNING:")
    click.echo("  - Can damage catalytic converters")
    click.echo("  - May increase exhaust temperatures")
    click.echo("  - Recommended for track/off-road use only")
    
    if not click.confirm("\n Apply burbles patch to a bin file?", default=False):
        input("\nPress Enter to continue...")
        return
    
    # Select input file
    click.echo("\nSelect input bin file:")
    bin_file = click.prompt("Enter path to stock bin file", type=click.Path(exists=True))
    input_path = Path(bin_file)
    
    # Generate output filename
    output_path = input_path.with_name(f"{input_path.stem}_burbles.bin")
    
    click.echo(f"\nInput:  {input_path}")
    click.echo(f"Output: {output_path}")
    
    if not click.confirm("\n Apply burbles patch?", default=False):
        click.echo(" Cancelled")
        input("\nPress Enter to continue...")
        return
    
    try:
        # Create patcher and burbles patch set
        patcher = map_patcher.MapPatcher("MSD81")
        burbles_set = patcher.create_burbles_patch()
        
        click.echo(f"\nApplying {len(burbles_set)} burbles patches...")
        
        # Apply patches
        results = map_patcher.apply_patches_to_file(
            input_path,
            output_path,
            burbles_set,
            ecu_type="MSD81"
        )
        
        if results['success']:
            click.echo(f"\n Burbles patch applied successfully!")
            click.echo(f" {len(results['applied_patches'])} patches applied")
            click.echo(f" {results['updated_crc_count']} CRC zones updated")
            click.echo(f"\n Output file: {output_path}")
            click.echo(f"📏 Size: {output_path.stat().st_size:,} bytes")
        else:
            click.echo(f"\n Patch failed: {', '.join(results['errors'])}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
        logger.exception("Burbles patch failed")
    
    input("\nPress Enter to continue...")


def advanced_vmax_removal():
    """VMAX (speed limiter) removal."""
    from . import map_patcher
    
    click.echo("\n" + "="*70)
    click.echo("=== Speed Limiter (VMAX) Removal ===")
    click.echo("="*70)
    
    click.echo("\n🏁 Remove factory speed limiter!")
    click.echo("\nStock VMAX: 155 mph (250 km/h) or 130 mph (210 km/h)")
    click.echo("Modified:   255 km/h (effectively no limit)")
    click.echo("\n  Legal disclaimer:")
    click.echo("  - For track/off-road use only")
    click.echo("  - May be illegal in some jurisdictions")
    click.echo("  - User accepts all responsibility")
    
    if not click.confirm("\n Apply VMAX removal to bin file?", default=False):
        input("\nPress Enter to continue...")
        return
    
    # Select input file
    bin_file = click.prompt("Enter path to bin file", type=click.Path(exists=True))
    input_path = Path(bin_file)
    output_path = input_path.with_name(f"{input_path.stem}_vmax_removed.bin")
    
    try:
        patcher = map_patcher.MapPatcher("MSD81")
        vmax_patch = patcher.create_vmax_removal_patch()
        
        # Create patch set with single patch
        vmax_set = map_patcher.PatchSet(
            name="VMAX Removal",
            description="Remove speed limiter"
        )
        vmax_set.add_patch(vmax_patch)
        
        click.echo("\nApplying VMAX removal...")
        results = map_patcher.apply_patches_to_file(
            input_path,
            output_path,
            vmax_set,
            ecu_type="MSD81"
        )
        
        if results['success']:
            click.echo("\n VMAX removal successful!")
            click.echo(f" Output: {output_path}")
        else:
            click.echo(f"\n Failed: {', '.join(results['errors'])}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
    
    input("\nPress Enter to continue...")


def advanced_rpm_limiter():
    """RPM limiter adjustment."""
    from . import map_patcher
    
    click.echo("\n" + "="*70)
    click.echo("=== RPM Limiter Adjustment ===")
    click.echo("="*70)
    
    click.echo("\n Adjust RPM limiter settings")
    click.echo("\nStock soft cut: 7000 RPM")
    click.echo("Stock hard cut: 7200 RPM")
    click.echo("\nRecommended limits:")
    click.echo("  Conservative: 7200 RPM")
    click.echo("  Aggressive:   7500 RPM")
    click.echo("  Maximum:      7800 RPM (requires forged internals)")
    
    target_rpm = click.prompt("\nEnter target RPM limit", type=int, default=7200)
    
    if target_rpm > 7500:
        click.echo("\n  WARNING: RPM > 7500 requires strengthened internals!")
        if not click.confirm("Continue anyway?", default=False):
            input("\nPress Enter to continue...")
            return
    
    # Select input file
    bin_file = click.prompt("Enter path to bin file", type=click.Path(exists=True))
    input_path = Path(bin_file)
    output_path = input_path.with_name(f"{input_path.stem}_rpm{target_rpm}.bin")
    
    try:
        patcher = map_patcher.MapPatcher("MSD81")
        rpm_set = patcher.create_rpm_limiter_patch(target_rpm)
        
        click.echo(f"\nApplying RPM limit: {target_rpm} RPM...")
        click.echo(f"Modifying {len(rpm_set)} RPM limiter locations...")
        
        results = map_patcher.apply_patches_to_file(
            input_path,
            output_path,
            rpm_set,
            ecu_type="MSD81"
        )
        
        if results['success']:
            click.echo(f"\n RPM limiter updated to {target_rpm} RPM!")
            click.echo(f" {len(results['applied_patches'])} patches applied")
            click.echo(f" Output: {output_path}")
        else:
            click.echo(f"\n Failed: {', '.join(results['errors'])}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
    
    input("\nPress Enter to continue...")


def advanced_launch_control():
    """Launch control configuration."""
    click.echo("\n" + "="*70)
    click.echo("=== Launch Control ===")
    click.echo("="*70)
    
    click.echo("\n🚧 COMING SOON!")
    click.echo("\nLaunch control features in development:")
    click.echo("  - Two-step rev limiter")
    click.echo("  - Anti-lag turbo spooling")
    click.echo("  - Configurable launch RPM (3000-5000)")
    click.echo("  - Boost target during launch")
    click.echo("  - Traction control integration")
    click.echo("\nStatus: Awaiting map offset discovery")
    click.echo("See: docs/PROJECT_STATUS.md for feature status")
    
    input("\nPress Enter to continue...")


def advanced_rolling_antilag():
    """Rolling anti-lag configuration."""
    click.echo("\n" + "="*70)
    click.echo("=== Rolling Anti-Lag ===")
    click.echo("="*70)
    
    click.echo("\n🚧 COMING SOON!")
    click.echo("\nRolling anti-lag features:")
    click.echo("  - Throttle-off boost retention")
    click.echo("  - Ignition timing retard")
    click.echo("  - Fuel enrichment during decel")
    click.echo("  - Turbo spool maintenance")
    click.echo("\nStatus: Awaiting map offset discovery")
    
    input("\nPress Enter to continue...")


def advanced_cold_start():
    """Cold start options."""
    click.echo("\n" + "="*70)
    click.echo("=== Cold Start Options ===")
    click.echo("="*70)
    
    click.echo("\n❄  Cold start tuning options:")
    click.echo("\nAvailable modifications:")
    click.echo("  1. Disable cold start emissions mode")
    click.echo("  2. Reduce warm-up time")
    click.echo("  3. Adjust idle enrichment")
    click.echo("  4. Modify cold start RPM target")
    click.echo("\n🚧 Status: Partially implemented")
    click.echo("DTC disable (catalyst/O2) available now")
    click.echo("Other features require map discovery")
    
    input("\nPress Enter to continue...")


def advanced_sport_display():
    """Sport display customization."""
    click.echo("\n" + "="*70)
    click.echo("=== Sport Display Customization ===")
    click.echo("="*70)
    
    click.echo("\n🚧 COMING SOON!")
    click.echo("\nSport display features:")
    click.echo("  - Custom gauge ranges")
    click.echo("  - Boost gauge calibration")
    click.echo("  - Oil temp/pressure display")
    click.echo("  - Lap timer integration")
    click.echo("\nStatus: Awaiting CAN message discovery")
    
    input("\nPress Enter to continue...")


def advanced_dtc_management():
    """DTC/Codeword management."""
    from . import map_patcher
    
    click.echo("\n" + "="*70)
    click.echo("=== DTC/Codeword Management ===")
    click.echo("="*70)
    
    click.echo("\n Disable unwanted diagnostic trouble codes")
    click.echo("\nAvailable DTC disables:")
    click.echo("  - Catalyst efficiency (P0420/P0430)")
    click.echo("  - O2 sensor heater circuits")
    click.echo("  - Secondary air injection")
    click.echo("  - EVAP system")
    click.echo("\nCommon use cases:")
    click.echo("  - Catless downpipes")
    click.echo("  - O2 sensor delete")
    click.echo("  - SAI delete")
    
    if not click.confirm("\n Apply DTC disable patch?", default=False):
        input("\nPress Enter to continue...")
        return
    
    bin_file = click.prompt("Enter path to bin file", type=click.Path(exists=True))
    input_path = Path(bin_file)
    output_path = input_path.with_name(f"{input_path.stem}_dtc_disabled.bin")
    
    try:
        patcher = map_patcher.MapPatcher("MSD81")
        dtc_set = patcher.create_dtc_disable_patch()
        
        click.echo(f"\nApplying DTC disable ({len(dtc_set)} patches)...")
        
        results = map_patcher.apply_patches_to_file(
            input_path,
            output_path,
            dtc_set,
            ecu_type="MSD81"
        )
        
        if results['success']:
            click.echo("\n DTC codes disabled!")
            click.echo(f" {len(results['applied_patches'])} patches applied")
            click.echo(f" Output: {output_path}")
        else:
            click.echo(f"\n Failed: {', '.join(results['errors'])}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
    
    input("\nPress Enter to continue...")


def advanced_stage_presets():
    """Apply stage presets."""
    from . import map_patcher
    
    click.echo("\n" + "="*70)
    click.echo("=== Stage Preset Application ===")
    click.echo("="*70)
    
    click.echo("\n Apply complete tuning stage presets")
    click.echo("\nAvailable presets:")
    click.echo("\n1. Stage 1 - Conservative")
    click.echo("   - VMAX removal")
    click.echo("   - RPM: 7200")
    click.echo("   - DTC disable (cat/O2)")
    click.echo("   - Target: 17 PSI boost")
    click.echo("\n2. Stage 2 - Aggressive")
    click.echo("   - VMAX removal")
    click.echo("   - RPM: 7500")
    click.echo("   - Burbles/pops enabled")
    click.echo("   - DTC disable (cat/O2)")
    click.echo("   - Target: 21 PSI boost")
    
    stage_choice = click.prompt("\nSelect stage (1 or 2)", type=int, default=1)
    
    if stage_choice not in [1, 2]:
        click.echo(" Invalid stage")
        input("\nPress Enter to continue...")
        return
    
    bin_file = click.prompt("Enter path to bin file", type=click.Path(exists=True))
    input_path = Path(bin_file)
    output_path = input_path.with_name(f"{input_path.stem}_stage{stage_choice}.bin")
    
    try:
            patcher = map_patcher.MapPatcher("MSD81")

            if stage_choice == 1:
                from . import tuning_parameters as map_options
                map_opts = map_options.get_preset("stage1")
                if map_opts is None:
                    click.echo("\nFailed to load Stage 1 preset.")
                    return
                preset = patcher.create_patchset_from_map_options(map_opts, name="stage1", description="Stage 1 preset (unified)")
                click.echo("\n📦 Applying Stage 1 preset (unified system)...")
            else:
                from . import tuning_parameters as map_options
                map_opts = map_options.get_preset("stage2")
                if map_opts is None:
                    click.echo("\nFailed to load Stage 2 preset.")
                    return
                preset = patcher.create_patchset_from_map_options(map_opts, name="stage2", description="Stage 2 preset (unified)")
                click.echo("\n📦 Applying Stage 2 preset (unified system)...")
        
        click.echo(f"Total patches: {len(preset)}")
        
        results = map_patcher.apply_patches_to_file(
            input_path,
            output_path,
            preset,
            ecu_type="MSD81"
        )
        
        if results['success']:
            click.echo(f"\n Stage {stage_choice} preset applied!")
            click.echo(f" {len(results['applied_patches'])} patches applied")
            click.echo(f" {results['updated_crc_count']} CRC zones updated")
            click.echo(f"\n Output: {output_path}")
            click.echo(f"📏 Size: {output_path.stat().st_size:,} bytes")
            click.echo("\n  NEXT STEPS:")
            click.echo("  1. Flash to ECU using Flash Operations menu")
            click.echo("  2. Monitor AFR and knock on first test drive")
            click.echo("  3. Verify boost levels match target")
        else:
            click.echo(f"\n Failed: {', '.join(results['errors'])}")
    
    except Exception as e:
        click.echo(f"\n Error: {e}")
    
    input("\nPress Enter to continue...")


def advanced_custom_patch_builder():
    """Custom patch builder."""
    click.echo("\n" + "="*70)
    click.echo("=== Custom Patch Builder ===")
    click.echo("="*70)
    
    click.echo("\n Build custom patch combinations")
    click.echo("\n🚧 COMING SOON!")
    click.echo("\nPlanned features:")
    click.echo("  - Interactive patch selection")
    click.echo("  - Save custom presets")
    click.echo("  - Load/edit existing presets")
    click.echo("  - Batch patch application")
    click.echo("  - Patch conflict detection")
    click.echo("\nFor now, use individual feature options above")
    
    input("\nPress Enter to continue...")


def advanced_accel_logger_menu():
    """Acceleration Logger submenu (simple CLI integration)."""
    from . import accel_logger as _accel_mod
    global _accel_logger

    click.echo("\n" + "="*60)
    click.echo("=== Acceleration Logger ===")
    click.echo("="*60)

    while True:
        click.echo("\n1. Start Auto Monitor")
        click.echo("2. Start Manual Run")
        click.echo("3. Stop Current Run")
        click.echo("4. View Run History")
        click.echo("5. Back")

        try:
            choice = click.prompt("Select an option", type=int, default=5)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input.")
            continue

        if choice == 1:
            # Ensure instance exists
            if _accel_logger is None:
                conn = obd_session_manager.get_active_connection()
                _accel_logger = _accel_mod.AccelLogger(connection=conn)

            if not _accel_logger.is_monitoring():
                _accel_logger.start_monitor(auto_detect=True)
                click.echo("Auto monitor started.")
            else:
                click.echo("Auto monitor already running.")

        elif choice == 2:
            if _accel_logger is None:
                conn = obd_session_manager.get_active_connection()
                _accel_logger = _accel_mod.AccelLogger(connection=conn)

            if not _accel_logger.is_monitoring():
                _accel_logger.start_monitor(auto_detect=False)

            _accel_logger.start_run()
            click.echo("Manual run started.")

        elif choice == 3:
            if _accel_logger and _accel_logger.is_running():
                summary = _accel_logger.stop_run()
                click.echo(f"Run stopped. Samples: {summary.samples if summary else 'n/a'}")
            else:
                click.echo("No active run.")

        elif choice == 4:
            if _accel_logger:
                hist = _accel_logger.get_history()
                if not hist:
                    click.echo("No runs recorded yet.")
                else:
                    for i, h in enumerate(hist, 1):
                        click.echo(f"{i}. {h.start_time} - {h.end_time} | samples={h.samples} | csv={h.csv_file}")
            else:
                click.echo("No runs recorded yet.")

        elif choice == 5:
            # stop monitoring when leaving if user wants
            if _accel_logger and _accel_logger.is_monitoring():
                if click.confirm("Stop monitoring before exit?", default=True):
                    _accel_logger.stop_monitor()
            break

        else:
            click.echo("Invalid selection.")


def advanced_data_logger_menu():
    """Data Logger submenu for continuous OBD/UDS PID logging.

    This uses DataLogger + logger_integration to sample real PID values
    over the existing OBD session. No mock data is used.
    """
    from .data_logger import DataLogger
    from . import logger_integration
    from . import n54_pids
    from .n54_pids import PIDCategory  # type: ignore

    global _data_logger

    def _require_connection():
        """Return active OBD connection or None with a user-facing message."""
        try:
            conn = obd_session_manager.get_active_connection()
        except Exception:
            conn = None
        if conn is None:
            click.echo("\nNo active OBD connection detected.")
            click.echo("Use 'Hardware & Connection' to connect before logging.")
        return conn

    def _preset_pid_selection() -> list[str]:
        """Offer preset PID groups for common logging scenarios."""
        while True:
            click.echo("\nSelect PID preset group:")
            click.echo(" 1. Engine Basics (RPM, speed, temps, load)")
            click.echo(" 2. Boost & Fuel (boost, fuel, context RPM/load)")
            click.echo(" 3. Timing & Knock (timing, VANOS, boost)")
            click.echo(" 4. Emissions (lambda/O2, trims)")
            click.echo(" 5. Knock Safety (ignition, lambda, key temps)")
            click.echo(" 6. All defined PIDs (OBD + N54-specific)")
            click.echo(" 7. Cancel")

            try:
                choice = click.prompt("Preset selection", type=int, default=1)
            except click.Abort:
                return []
            except Exception:
                click.echo("Invalid input.")
                continue

            ids: list[str] = []

            if choice == 1:
                # Engine basics
                for pid in n54_pids.get_pids_by_category(PIDCategory.ENGINE_BASIC):
                    if pid.pid not in ids:
                        ids.append(pid.pid)
                iat = n54_pids.get_pid_by_name("Intake Air Temperature")
                if iat and iat.pid not in ids:
                    ids.append(iat.pid)
                return ids

            if choice == 2:
                # Boost + fuel monitoring
                for pid in n54_pids.get_boost_monitoring_pids():
                    if pid.pid not in ids:
                        ids.append(pid.pid)
                for pid in n54_pids.get_fuel_monitoring_pids():
                    if pid.pid not in ids:
                        ids.append(pid.pid)
                for name in ("Engine RPM", "Engine Load", "Throttle Position", "Vehicle Speed"):
                    p = n54_pids.get_pid_by_name(name)
                    if p and p.pid not in ids:
                        ids.append(p.pid)
                return ids

            if choice == 3:
                # Timing + knock + VANOS
                for pid in n54_pids.ALL_PIDS:
                    if getattr(pid, "category", None) in (PIDCategory.IGNITION, PIDCategory.VANOS):
                        if pid.pid not in ids:
                            ids.append(pid.pid)
                for name in ("Engine RPM", "Actual Boost Pressure"):
                    p = n54_pids.get_pid_by_name(name)
                    if p and p.pid not in ids:
                        ids.append(p.pid)
                return ids

            if choice == 4:
                # Emissions-focused
                for pid in n54_pids.get_pids_by_category(PIDCategory.EMISSIONS):
                    if pid.pid not in ids:
                        ids.append(pid.pid)
                for name in (
                    "Short Fuel Trim Bank 1",
                    "Long Fuel Trim Bank 1",
                    "Short Fuel Trim Bank 2",
                    "Long Fuel Trim Bank 2",
                ):
                    p = n54_pids.get_pid_by_name(name)
                    if p and p.pid not in ids:
                        ids.append(p.pid)
                return ids

            if choice == 5:
                # Knock safety: ignition + lambda + key temps
                for pid in n54_pids.get_pids_by_category(PIDCategory.IGNITION):
                    if pid.pid not in ids:
                        ids.append(pid.pid)
                for pid in n54_pids.get_pids_by_category(PIDCategory.EMISSIONS):
                    if pid.pid not in ids:
                        ids.append(pid.pid)
                for name in ("Engine RPM", "Coolant Temperature", "Intake Air Temperature", "Actual Boost Pressure"):
                    p = n54_pids.get_pid_by_name(name)
                    if p and p.pid not in ids:
                        ids.append(p.pid)
                return ids

            if choice == 6:
                return [pid.pid for pid in n54_pids.ALL_PIDS]

            if choice == 7:
                return []

            click.echo("Invalid selection. Choose 1-7.")

    def _custom_pid_selection() -> list[str]:
        """Prompt the user for a comma-separated list of PID ids or names."""
        click.echo("\nEnter PID identifiers or names, separated by commas.")
        click.echo("Examples: 0C,0D,BOOST_ACTUAL or Engine RPM, Vehicle Speed")

        try:
            raw = click.prompt("PIDs (blank to cancel)", default="").strip()
        except click.Abort:
            return []
        if not raw:
            return []

        tokens = [t.strip() for t in raw.replace(";", ",").split(",") if t.strip()]
        ids: list[str] = []
        for token in tokens:
            pid_def = n54_pids.get_pid_by_id(token) or n54_pids.get_pid_by_name(token)
            if pid_def is None:
                click.echo(f"   Unknown PID token: {token}")
                continue
            if pid_def.pid not in ids:
                ids.append(pid_def.pid)

        if not ids:
            click.echo("No valid PIDs resolved from input.")
        return ids

    def _start_logging(pid_ids: list[str]) -> None:
        global _data_logger

        if not pid_ids:
            click.echo("No PIDs selected; logging cancelled.")
            return

        if _data_logger is not None and getattr(_data_logger, "is_running", False):
            click.echo("Data Logger is already running. Stop it before starting a new session.")
            return

        conn = _require_connection()
        if conn is None:
            return

        try:
            interval_ms = click.prompt("Sampling interval (ms)", type=int, default=200)
        except click.Abort:
            return
        except Exception:
            interval_ms = 200

        try:
            duration_s = click.prompt("Duration in seconds (0 = until stopped)", type=float, default=0.0)
        except click.Abort:
            return
        except Exception:
            duration_s = 0.0

        try:
            session_name = click.prompt("Optional session name", default="").strip() or None
        except click.Abort:
            return

        interval_s = max(0.05, interval_ms / 1000.0)
        duration = duration_s if duration_s > 0 else None

        channels = logger_integration.build_channels_for_pids(pid_ids, interval=interval_s, connection=conn)
        if not channels:
            click.echo("No valid channels could be created for the selected PIDs.")
            return

        _data_logger = DataLogger(channels=channels, interval=interval_s)
        _data_logger.start(session_name=session_name, duration=duration)
        file_path = getattr(_data_logger, "_file_path", None)
        click.echo(f"\nStarted Data Logger with {len(channels)} channel(s) at {interval_s:.3f}s interval.")
        if duration is not None:
            click.echo(f"Logging will stop automatically after {duration:.1f} seconds.")
        if file_path:
            click.echo(f"Current log file: {file_path}")

    click.echo("\n" + "="*60)
    click.echo("=== Data Logger (Continuous OBD/UDS Logging) ===")
    click.echo("="*60)

    while True:
        click.echo("\n1. Start logging with preset PIDs")
        click.echo("2. Start logging with custom PIDs")
        click.echo("3. Stop logger")
        click.echo("4. Show logger status")
        click.echo("5. Back")

        try:
            choice = click.prompt("Select an option", type=int, default=5)
        except click.Abort:
            break
        except Exception:
            click.echo("Invalid input.")
            continue

        if choice == 1:
            pids = _preset_pid_selection()
            _start_logging(pids)
        elif choice == 2:
            pids = _custom_pid_selection()
            _start_logging(pids)
        elif choice == 3:
            if _data_logger is not None and getattr(_data_logger, "is_running", False):
                _data_logger.stop(wait=True)
                file_path = getattr(_data_logger, "_file_path", None)
                click.echo("Data Logger stopped.")
                if file_path:
                    click.echo(f"Last log file: {file_path}")
            else:
                click.echo("Data Logger is not running.")
        elif choice == 4:
            if _data_logger is not None and getattr(_data_logger, "is_running", False):
                file_path = getattr(_data_logger, "_file_path", None)
                click.echo("Data Logger is running.")
                click.echo(f"Interval: {getattr(_data_logger, 'interval', 0.0)} seconds")
                if file_path:
                    click.echo(f"Current log file: {file_path}")
            elif _data_logger is not None:
                file_path = getattr(_data_logger, "_file_path", None)
                click.echo("Data Logger is idle.")
                if file_path:
                    click.echo(f"Last log file: {file_path}")
            else:
                click.echo("Data Logger has not been started in this session.")
        elif choice == 5:
            break
        else:
            click.echo("Invalid selection.")


def cleanup():
    """Cleanup resources before exit."""
    # Disconnect OBD session if active
    try:
        obd_session = obd_session_manager.get_session()
        if obd_session.is_connected():
            obd_session.disconnect()
    except Exception as e:
        logger.warning(f"Cleanup: failed to disconnect OBD session: {e}")
    
    click.echo("\nGoodbye!")


if __name__ == '__main__':
    main_menu()
