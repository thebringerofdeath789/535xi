<<<<<<< HEAD
# BMW N54 CAN/UDS Flash & Tuning Tool

**Description:**
Standalone Python tool for CAN/UDS-based flashing, diagnostics, and map editing for BMW N54 MSD80 I8A0S (7614480/7614481). Features  map validation, backup/restore, GUI and CLI. All offsets are for a single, validated bin file only.

**Author:**
Gregory King

**License:**
MIT License

---
=======
>>>>>>> 938335846dcad22b12a954a2d28f714dd6030c14
## Requirements

- Python 3.10+
- PySide6
- python-can
- anyio
- numpy
- (Optional for advanced features: matplotlib, pandas)

Install all dependencies with:

```powershell
pip install -r requirements.txt
```

## Map Offset Policy

All map offsets, validation, and safety logic in this tool are based on a single, specific N54 bin file (MSD80 I8A0S, 7614480/7614481). These offsets are not valid for other N54 software versions or DME variants.

**Warning:** Attempting to use this tool with other N54 bin files (e.g., 7603537, 7614482, 7614483, etc.) without proper offset migration will result in incorrect map locations and may cause ECU damage. Offset migration for other bins is not supported in this release.
## Usage: Starting the CLI and GUI

### Start the CLI

From the project root:

```powershell
python -m flash_tool.cli
```

This launches the interactive command-line interface.

#### Main CLI Options:
- Flash ECU (direct CAN/UDS)
- Read/Write Maps
- Backup/Restore
- Diagnostics (OBD-II, DME)
- Safety Validation
- Hardware/Adapter Scan
- Logging and Audit
- Advanced Tools (bench, CRC, etc.)

### Start the GUI

From the project root:

```powershell
python -m flash_tool.gui.app
```

This launches the full graphical interface (PySide6 required).

#### Main GUI Features:
- Visual Map Editor
- Flash/Backup/Restore Wizards
- Live Data Dashboards
- Tuning Parameter Editors
- Logging and Diagnostics
- Connection/Adapter Management
- Safety and Validation Tools

Both interfaces use the same backend and safety systems. All map/flash operations are validated and logged.
# BMW N54 Flash Tool


ECU diagnostics, tuning, and map flashing for BMW MSD80/MSD81 (N54) engines. Standalone Direct CAN/UDS implementation with interactive CLI and PySide6 GUI.

---

## Features

| Feature | Description |
|---------|-------------|
| **Direct CAN/UDS** | Complete ISO-TP (ISO 15765-2) + UDS (ISO 14229) protocol stack |
| **Security Access** | Three BMW seed/key algorithm variants with auto-detection |
| **Map Flashing** | 7-layer safety validation, CRC32 recalculation (BMW polynomial 0x1EDC6F41) |
| **OBD-II Diagnostics** | DTCs, live data, 96 N54-specific PIDs |
| **Tuning Options** | Burbles, VMAX delete, DTC disable, boost limits, rev limiter, launch control |
| **GUI Application** | PySide6 widgets: flash wizard, OBD dashboard, map editor, tuning options |
| **Tune & Flash** | End-to-end workflow: configure → patch → CRC recalc → flash → verify |

**Supported ECUs:** MSD80 & I8A0S only!

---

## Quick Start

```powershell
# Install
cd C:\Users\admin\Documents\535xi
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run CLI
python -m flash_tool.cli

# Run GUI
python -m flash_tool.gui.app
```

---

## Hardware Requirements

| Adapter | Purpose | Notes |
|---------|---------|-------|
| PCAN-USB | Flash operations | Required for ECU write |
| K+DCAN USB | OBD-II diagnostics | DTCs, live data, adaptations |
| 12V supply | Flash safety | Battery charger recommended |



## Package Overview

**70 modules | 31,000+ lines**

### Core Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `cli.py` | 6,011 | Interactive menu system |
| `direct_can_flasher.py` | 2,264 | ISO-TP + UDS stack, seed/key |
| `n54_pids.py` | 1,430 | 96 N54-specific parameters |
| `map_flasher.py` | 1,334 | Flash orchestration + validation |
| `obd_reader.py` | 1,041 | OBD-II protocol handler |
| `map_patcher.py` | 837 | Binary patching engine |
| `dme_handler.py` | 598 | BMW DME-specific functions |
| `map_options.py` | 550 | Tuning option data model |

### GUI Widgets

| Widget | Lines | Purpose |
|--------|-------|---------|
| `flasher_wizard.py` | 983 | Step-by-step flash workflow |
| `tuning_options.py` | 785 | Tuning configuration UI |
| `obd_logger.py` | 756 | Data logging interface |
| `obd_dashboard.py` | 410 | Live data display |
| `coding_widget.py` | 424 | Module coding interface |
| `map_editor_widget.py` | 246 | Table/grid map editing |


### Supporting Modules

| Module                | Purpose                                      |
|-----------------------|----------------------------------------------|
| `validated_maps.py`   | XDF-validated map registry, forbidden regions|
| `boost_patcher.py`    | Boost table patching and map logic           |
| `backup_manager.py`   | Backup/restore orchestration, file mgmt      |
| `crc_validator.py`    | CRC32/CRC16 validation, pre-flash checks     |
| `crc_zones.py`        | BMW CRC zone definitions, region helpers     |
| `bmw_checksum.py`     | BMW CRC16/CRC32 algorithms                   |
| `dtc_database.py`     | DTC code definitions, lookup                 |
| `security.py`         | Seed/key algorithms, security access         |
| `settings_manager.py` | Persistent config, user settings             |
| `operation_logger.py` | JSON/text operation logging                  |
| `map_validator.py`    | Map data validation, structure checks        |
| `offset_database.py`  | Offset registry, address helpers             |
| `software_detector.py`| Platform/adapter detection                   |
| `connection_manager.py`| Port selection, connection state            |
| `com_scanner.py`      | Serial port and CAN adapter scanning         |
| `bmw_modules.py`      | BMW module registry, addressing              |
| `obd_session_manager.py`| OBD session state, protocol helpers        |
| `map_manager.py`      | Map file management, patching, metadata      |
| `flash_safety.py`     | Flash safety logic, error classes            |
| `operation_logger.py` | Operation logging, audit trail               |

---

## Safety System

### 7-Layer Validation
1. Forbidden region check
2. Rejected map detection (checksum blocks)
3. Map registry lookup
4. Size validation
5. All-zero detection
6. All-0xFF detection
7. Warning accumulation

## Tuning Options

| Category | Status | Details |
|----------|--------|---------|
| Burbles/Pops | ✅ | 8 timing parameters |
| VMAX Delete | ✅ | 2 offsets (0x93A0, 0xB240) |
| DTC Disable | ✅ | 551 codewords |
| Boost Limits | ✅ | Target boost, WGDC tables |
| Rev Limiter | ✅ | Hard/soft limits |
| Launch Control | ✅ | RPM, timing retard, boost |

### Presets
- **Stage 1** — ~1.0 bar boost
- **Stage 2** — ~1.2 bar boost  
- **Stage 2+** — ~1.4 bar boost

---

## Usage Examples

### Direct CAN Flash

```python
from flash_tool.direct_can_flasher import DirectCANFlasher

flasher = DirectCANFlasher(can_interface="pcan", can_channel="PCAN_USBBUS1")
flasher.connect()

if flasher.unlock_ecu(try_all_algorithms=True):
    backup = flasher.read_calibration_region()
    flasher.flash_calibration_region(modified_data, verify=True)
```

### CLI Workflow

```
Main Menu → 7. Map Options & Tuning
  → 7. Load Preset → Stage 2
  → 1. Configure Burbles → Sport mode
  → 10. Apply to Map File
  → 11. Tune & Flash
```



## Project Structure

```
flash_tool/
├── accel_logger.py
├── adapters/
│   ├── __init__.py
│   └── pcan_adapter.py
├── backup_manager.py
├── bench_tools.py
├── bin_analyzer.py
├── bmw_checksum.py
├── bmw_modules.py
├── bmw_protocol.py
├── boost_patcher.py
├── can_adapter.py
├── cli.py
├── com_scanner.py
├── connection_manager.py
├── crc_validator.py
├── crc_zones.py
├── data_logger.py
├── direct_can_flasher.py
├── dme_handler.py
├── dtc_database.py
├── dtc_utils.py
├── flash_safety.py
├── gui/
│   ├── __init__.py
│   ├── app.py
│   ├── gui_api.py
│   ├── gui_api_stub.py
│   ├── map_model.py
│   ├── patch_manifest.py
│   ├── theme.qss
│   ├── utils.py
│   ├── worker.py
│   └── widgets/
│       ├── backup_recovery.py
│       ├── bin_compare.py
│       ├── bin_inspector.py
│       ├── coding_widget.py
│       ├── connection_widget.py
│       ├── direct_can_widget.py
│       ├── flasher_wizard.py
│       ├── gauges_dashboard.py
│       ├── help_about_dialog.py
│       ├── live_control_widget.py
│       ├── live_plot_widget.py
│       ├── log_viewer.py
│       ├── map_editor.py
│       ├── map_editor_widget.py
│       ├── map_preview.py
│       ├── obd_dashboard.py
│       ├── obd_logger.py
│       ├── settings_dialog.py
│       ├── tuning_editor.py
│       ├── tuning_options.py
│       └── validated_maps_viewer.py
├── help_system.py
├── img/
│   ├── About.png
│   ├── AppIcon.png
│   ├── Backup.png
│   ├── CheckboxOff.png
│   ├── CheckboxOn.png
│   ├── Chip.png
│   ├── Connect.png
│   ├── Connection.png
│   ├── Diagnostics.png
│   ├── Differences.png
│   ├── Disconnect.png
│   ├── DTCClear.png
│   ├── DTCRead.png
│   ├── ECUInfo.png
│   ├── Flash.png
│   ├── FlashTab.png
│   ├── Folder.png
│   ├── InfoSmall.png
│   ├── LiveData.png
│   ├── LiveStart.png
│   ├── LiveStop.png
│   ├── LoadBin.png
│   ├── Log.png
│   ├── Logo.png
│   ├── Logs.png
│   ├── MapsTuning.png
│   ├── Patch.png
│   ├── RadioOff.png
│   ├── RadioOn.png
│   ├── Redo.png
│   ├── Restore.png
│   ├── Save.png
│   ├── Scan.png
│   ├── Settings.png
│   ├── Splash.png
│   ├── TableEditor.png
│   ├── Undo.png
│   ├── ValidateBin.png
│   ├── Verify.png
│   └── Warning.png
├── kwp_client.py
├── logger_integration.py
├── map_flasher.py
├── map_manager.py
├── map_offsets.py
├── map_options.py
├── map_patcher.py
├── map_validator.py
├── module_scanner.py
├── n54_pids.py
├── obd_reader.py
├── obd_session_manager.py
├── offset_database.py
├── operation_logger.py
├── README.md
├── security.py
├── settings_manager.py
├── software_detector.py
├── stock_values.py
├── tuning_parameters.py
├── udsoncan_adapter.py
├── uds_client.py
├── uds_handler.py
├── uds_isotp_client.py
├── validated_maps.py
├── __init__.py
```

---

<<<<<<< HEAD
=======
## Requirements

- Python 3.10+
- python-can
- PySide6 (GUI)
- PCAN-USB adapter (flash operations)
- K+DCAN cable (OBD diagnostics)
>>>>>>> 938335846dcad22b12a954a2d28f714dd6030c14
