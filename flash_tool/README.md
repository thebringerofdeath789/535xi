# BMW N54 Flash Tool

ECU diagnostics, tuning, and map flashing for BMW MSD80/MSD81 (N54) engines. Standalone Direct CAN/UDS implementation with interactive CLI and PySide6 GUI.

**Status:** Code Complete — Hardware Validation Pending  
**Updated:** December 2025

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

**Supported ECUs:** MSD80, MSD81 (N54 twin-turbo)

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

⚠️ **Bench ECU testing required before vehicle use**

---

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

| Module | Purpose |
|--------|---------|
| `validated_maps.py` | Safe map registry + forbidden regions |
| `boost_patcher.py` | Boost table modifications |
| `backup_manager.py` | Backup lifecycle management |
| `crc_validator.py` | Pre-flash CRC validation |
| `crc_zones.py` | BMW CRC zone definitions |
| `bmw_checksum.py` | CRC16/CRC32 algorithms |
| `dtc_database.py` | DTC code definitions |
| `security.py` | Seed/key algorithms |
| `settings_manager.py` | Persistent configuration |
| `operation_logger.py` | JSON operation logging |

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

### Validated Maps (6)
| Type | Offsets |
|------|---------|
| Ignition Timing | `0x057B58`, `0x05D288`, `0x060EC0` |
| WGDC | `0x051580`, `0x051DA0`, `0x0546D0` |

### Forbidden Regions
| Range | Risk |
|-------|------|
| `0x054A90–0x054B50` | WGDC checksum — **BRICK** |
| `0x05AD20–0x05AD80` | WGDC checksum — **BRICK** |
| `0x000000–0x007FFF` | Boot code |
| `0x1F0000–0x200000` | Flash counter |

---

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

---

## Testing Status

| Phase | Status | Notes |
|-------|--------|-------|
| Syntax validation | ✅ | All 70 modules compile |
| Import testing | ✅ | All dependencies resolve |
| Mock mode | ✅ | Simulated flash verified |
| Seed/key algorithms | ✅ | Test vectors pass |
| Hardware testing | ⏳ | Requires PCAN + bench ECU |
| Vehicle testing | ⏳ | After bench validation |

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/DOCUMENTATION_INDEX.md](../docs/DOCUMENTATION_INDEX.md) | Master index |
| [docs/architecture.md](../docs/architecture.md) | System design |
| [docs/FINAL_VALIDATED_DISCOVERIES.md](../docs/FINAL_VALIDATED_DISCOVERIES.md) | Safe maps & forbidden regions |
| [docs/flash_safety_checklist.md](../docs/flash_safety_checklist.md) | Pre-flash safety |
| [docs/direct_can_flash_guide.md](../docs/direct_can_flash_guide.md) | Flash procedure |
| [docs/user_guide.md](../docs/user_guide.md) | End-user manual |

---

## Project Structure

```
flash_tool/
├── cli.py                    # Main CLI entry point
├── direct_can_flasher.py     # CAN/UDS protocol stack
├── map_flasher.py            # Flash orchestration
├── map_patcher.py            # Binary patching
├── validated_maps.py         # Safe map registry
├── n54_pids.py               # N54 parameters
├── obd_reader.py             # OBD-II handler
├── dme_handler.py            # BMW DME functions
├── gui/
│   ├── app.py                # GUI application
│   ├── gui_api.py            # Backend bridge
│   └── widgets/              # 17 UI widgets
└── adapters/
    └── pcan_adapter.py       # PCAN interface
```

---

## Requirements

- Python 3.10+
- python-can
- PySide6 (GUI)
- PCAN-USB adapter (flash operations)
- K+DCAN cable (OBD diagnostics)

---

## License

Research and educational use only. Use at your own risk.

⚠️ **Do not flash vehicle ECU without bench validation.**
