<<<<<<< HEAD
# 535xi N54 Flash Tool - Open Source ECU Tuning

**An open-source, cross-platform alternative to MHD Flasher for BMW N54 engines.**

A Python-based diagnostic and tuning tool for BMW N54 engines (2008+ 535xi, 335i, 135i, Z4) that provides direct CAN/UDS communication with the ECU, eliminating the need for proprietary software.

## Project Mission

**To build a free, open-source all-in-one BMW N54 tool with ECU flashing, diagnostics, service functions, and coding capabilities.**

Key advantages over Paid alternatives (MHD, BimmerCode, Carly):
- ✅ **Open source** - No license fees, community-driven development
- ✅ **Cross-platform** - Works on Windows, Linux, and macOS
- ✅ **Standalone** - No server dependency, no VIN locking
- ✅ **Transparent** - All algorithms and offsets documented
- ✅ **Safety-first** - 7-layer map validation, forbidden region protection
- ✅ **Complete tool** - Diagnostics + Service + Coding + Flashing in one package
- ⏳ **Feature parity** - Working towards complete functionality

## Current Status (November 3, 2025)

**🚧 Development Phase** - Software mostly complete.

### What Works (Software Only)
- ✅ **Code Complete:** 32 modules, 17,996 lines of Python
- ✅ **Direct CAN/UDS:** Complete protocol stack implementation (1,566 lines)
- ✅ **Interactive CLI:** Full menu system (4,895 lines)
- ✅ **Map Validation:** Safety framework with forbidden region checks
- ✅ **Documentation:** 60+ technical documents

### What's Untested
- ❌ **Map Modifications:** Offsets discovered but not applied/verified

## Features

### Core Capabilities (Planned)

**ECU Flashing** (Code Complete, Hardware Testing Required)
- Direct CAN/UDS ECU communication
- Read/write calibration maps
- RFTX-based seed/key security access
- 6 validated safe maps (ignition timing, WGDC)
- 7-layer safety validation system

**Diagnostics** (Planned - See Build Plan)
- Read/clear DTCs from all modules (DME, EGS, ABS, SRS, etc.)
- Live sensor data monitoring (20+ N54-specific PIDs)
- Freeze frame data reading
- Real-time boost, VANOS, fuel trim, knock monitoring

**Service Functions** (Planned - See Build Plan)
- CBS (Condition Based Service) reset - oil, brake, microfilter, etc.
- Battery registration (IBS module)
- Adaptation resets - throttle, transmission, fuel trims

**Data Logging** (Planned - See Build Plan)
- Multi-PID data logging to CSV/JSON
- Configurable sample rates
- Long-term logging for analysis

**Basic Coding** (Planned - See Build Plan)
- Backup/restore module coding
- Safe E60/N54 coding options (DRLs, seatbelt chime, auto-lock, etc.)
- Module coding for KOMBI, CAS, FRM, etc.

### Current Implementation Status

**What's Complete:**
- ✅ RFTX algorithm integration (Nov 3, 2025)
- ✅ Memory map updated (0x800000 base, RFTX-aligned)
- ✅ Sector erase function (UDS 0x31, routine 0xFF02)
- ✅ Absolute map addressing (all offsets corrected)
- ✅ Transfer size limits (512 bytes for MSD80/81)
- ✅ Basic OBD diagnostics (partial implementation)

**Next Steps:**
- ⏭️ Multi-module DTC reading (Phase 1.1 of build plan)
- ⏭️ N54-specific live data PIDs (Phase 1.3 of build plan)
- ⏭️ Hardware validation on bench ECU (CRITICAL before vehicle use)

## Architecture

The tool uses a modular architecture with two implementation paths:

### Path 1: Direct CAN/UDS (PRIMARY - Development Complete, Testing Required)
**Status:** ✅ Code complete, ❌ NOT tested on hardware

Standalone implementation using ISO-TP (ISO 15765-2) and UDS (ISO 14229) protocols:
- ✅ Complete CAN communication stack (1,566 lines)
- ✅ BMW seed/key algorithms (3 variants + RFTX) implemented (try-all)
- ✅ Memory read/write operations (implemented)
- ✅ CRC validation (BMW CRC32: 0x1EDC6F41; zone helpers integrated)
- ✅ Flash operations framework (CAL region: 0x100000-0x17FFFF)
- ✅ Cross-platform support code (Windows/Linux/Mac)

**Advantages:**
- No EDIABAS dependency
 - No dependency on vendor diagnostic tools
- Cross-platform compatible
- Full protocol control
- Open source algorithms

**Reality:**
 - CRC zones implemented; verify on hardware and optionally cross-check via vendor diagnostic tools
- Flashing always carries risk; follow safety docs

## Project Structure

```
535xi/
├── flash_tool/              # Main application package
│   ├── cli.py              # Interactive command-line interface
│   ├── com_scanner.py      # COM port detection
│   ├── obd_reader.py       # OBD-II diagnostics
│   ├── dme_handler.py      # BMW DME-specific functions
│   ├── map_flasher.py      # ECU flashing operations
│   └── 
├── docs/                    # Documentation
│   ├── agent_build_plan.md # Development roadmap
│   ├── architecture.md     # System design
│   └── research_log.md     # Reverse engineering notes
├── config/                  # Configuration files
└── requirements.txt         # Python dependencies
```

## Requirements

### Hardware
- K+DCAN cable (FTDI-based USB to OBD-II interface)
- 2008 BMW 535 with N54 engine (MSD80 or MSD81 DME)
- Windows PC with available USB port

### Software
- Python 3.10 or higher
- PCAN-USB driver (Windows) or SocketCAN (Linux) for CAN interface
- Optional (Legacy): vendor diagnostic tools installed locally for cross-checks

### Python Dependencies
- `pyserial` - Serial port communication
- `python-obd` - OBD-II protocol implementation
- `click` - CLI framework

## Installation

1. **Clone the repository:**
   ```powershell
   cd C:\Users\admin\Documents\535xi
   ```

2. **Create virtual environment:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

## Usage

### Starting the Tool
=======
# BMW N54 CAN/UDS Flash & Tuning Tool

**Description:**
Standalone Python tool for CAN/UDS-based flashing, diagnostics, and map editing for BMW N54 MSD80 I8A0S (7614480/7614481). Features  map validation, backup/restore, GUI and CLI. All offsets are for a single, validated bin file only.

**Author:**
Gregory King

**License:**
MIT License

---
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
>>>>>>> 938335846dcad22b12a954a2d28f714dd6030c14

```powershell
python -m flash_tool.cli
```

<<<<<<< HEAD
This launches the interactive menu with the following options:

**Current Menu:**
1. Scan for COM ports
2. Read DTCs (Diagnostic Trouble Codes)
3. Clear DTCs
4. Flash ECU with new map
5. Exit

**Planned Menu (See `docs/FEATURE_EXPANSION_BUILD_PLAN.md`):**
1. **Diagnostics**
   - Read DTCs (All Modules)
   - Clear DTCs
   - Freeze Frame Data
2. **Live Data**
   - View Sensors (20+ N54 PIDs)
   - Start/Stop Logging
   - Export Log
3. **Service Functions**
   - Reset Service Interval (CBS)
   - Register New Battery
   - Reset Adaptations
4. **Coding**
   - Backup/Restore Coding
   - Change Coding Options (DRLs, etc.)
5. **ECU Flashing** (existing)
6. Exit

### Typical Workflow

1. **Connect Hardware:** Plug K+DCAN cable into car's OBD-II port and USB to PC
2. **Scan Ports:** Use option 1 to identify the cable's COM port
3. **Read DTCs:** Check for any existing fault codes
4. **Backup ECU:** **(CRITICAL)** Always create a full backup before flashing
5. **Flash Map:** Upload custom tune (only after successful backup)

## Safety Features

- **Multiple Confirmations:** User must explicitly confirm dangerous operations
- **Mandatory Backups:** Cannot flash without creating a backup first
- **Pre-Flight Checks:** Validates battery voltage, file integrity, etc.
- **Read-Only Mode:** Diagnostic operations are safe and non-invasive
- **Progress Monitoring:** Real-time feedback during long operations

## Development

### Build Plan

**ECU Flashing Development** (outlined in `docs/agent_build_plan.md`):
- **Phase 1:** ✅ Core infrastructure and diagnostics (Tasks 1.0-3.0)  
- **Phase 2:** ✅ Advanced DME interaction (Tasks 4.0-4.1)  
- **Phase 3:** ✅ Direct CAN/UDS implementation (100% code complete)

**Feature Expansion** (outlined in `docs/FEATURE_EXPANSION_BUILD_PLAN.md`):
- **Phase 1:** ⏳ Diagnostics - Multi-module DTC reading, live data, freeze frames
- **Phase 2:** ⏳ Service Functions - CBS reset, battery registration, adaptations
- **Phase 3:** ⏳ Data Logging - CSV/JSON export, multi-PID recording
- **Phase 4:** ⏳ Basic Coding - E60/N54 coding options (DRLs, comfort features)
- **Phase 5:** ⏳ Connection & Hardware Support - ELM327, OBDLink, PCAN
- **Phase 6:** ⏳ UI/CLI Enhancement - Menu restructure, color coding
- **Phase 7:** ⏳ Documentation - Feature guides, quick starts
- **Phase 8:** ⏳ Testing & Validation - Unit tests, bench testing
- **Phase 9:** ⏳ Polish & Release - Packaging, v2.0.0 release

**Estimated Timeline:** 12-17 weeks for full feature expansion (see build plan for details)

### Current Status

- ✅ Phase 1-3: All code complete (7000+ lines)
- ⏳ Hardware testing: Requires PCAN adapter + bench ECU
- ⏳ Reverse engineering: CRC zones, complete map offsets

### Feature Comparison vs Commercial Tools

| Feature | MHD | BimmerCode | Carly | Our Tool | Status |
|---------|-----|------------|-------|----------|--------|
| **ECU Flashing** | ✅ | ❌ | ❌ | ⚠️ | Code complete, NOT tested |
| **Diagnostics (DTCs)** | ✅ | ✅ | ✅ | ⏳ | Planned (Phase 1) |
| **Live Data** | ✅ | ✅ | ✅ | ⏳ | Planned (Phase 1.3) |
| **Service Reset (CBS)** | ❌ | ✅ | ✅ | ⏳ | Planned (Phase 2.1) |
| **Battery Registration** | ❌ | ✅ | ✅ | ⏳ | Planned (Phase 2.2) |
| **Coding** | ❌ | ✅ | ✅ | ⏳ | Planned (Phase 4) |
| **Data Logging** | ✅ | ❌ | ❌ | ⏳ | Planned (Phase 3) |

**See:** 
- `docs/FEATURE_EXPANSION_BUILD_PLAN.md` for diagnostic/service/coding roadmap

### Contributing

Refer to `docs/development_guide.md` for:
- Coding conventions
- Testing procedures  
- Task execution workflow

## Warnings

**This tool is for research and education only. The developers assume NO liability for ECU damage, vehicle damage, or any other consequences of use.**

## License

1. This tool is for educational and research purposes. Use at your own risk.
2. This software, in whole or in part, may be freely used, distributed and
   modified as long as attribution is given to the original author.

## Acknowledgments

- N54Tech community for technical documentation
- RTFX Flasher
=======
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

>>>>>>> 938335846dcad22b12a954a2d28f714dd6030c14
