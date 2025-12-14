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

```powershell
python -m flash_tool.cli
```

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
