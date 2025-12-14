"""
Test/Validation Script for Tuning Editor Workflow

Covers:
- Preset loading and parameter mapping
- Value display and editing logic
- Validation and safety checks
- Bin file read/write round-trip
- Edge cases (invalid/missing values)

Run: python -m flash_tool.test_tuning_editor_workflow
"""
import sys
from pathlib import Path
from flash_tool import tuning_parameters

PRESETS = tuning_parameters.ALL_PRESETS

TEST_BIN_PATH = Path("test_data/stock_i8a0s.bin")  # Update to a valid test bin path
TEMP_OUT_PATH = Path("test_data/temp_out.bin")

def test_preset_loading():
    print("\n=== Preset Loading and Mapping ===")
    for name, preset in PRESETS.items():
        print(f"Testing preset: {name}")
        for key, value in preset.values.items():
            assert key in tuning_parameters.ALL_PARAMETERS, f"Parameter {key} missing in ALL_PARAMETERS"
            param = tuning_parameters.ALL_PARAMETERS[key]
            valid, msg = param.validate(value)
            assert valid, f"Preset {name} invalid for {key}: {msg}"
    print("All presets loaded and validated successfully.")

def test_bin_read_write_roundtrip():
    print("\n=== Bin File Read/Write Round-Trip ===")
    if not TEST_BIN_PATH.exists():
        print(f"Test bin not found: {TEST_BIN_PATH}")
        return
    orig_values = tuning_parameters.read_all_parameters(TEST_BIN_PATH)
    # Write values to temp file
    TEMP_OUT_PATH.write_bytes(TEST_BIN_PATH.read_bytes())
    changes = tuning_parameters.write_all_parameters(TEMP_OUT_PATH, orig_values)
    assert TEMP_OUT_PATH.exists(), "Output bin not written"
    roundtrip_values = tuning_parameters.read_all_parameters(TEMP_OUT_PATH)
    for k, v in orig_values.items():
        assert roundtrip_values.get(k) == v, f"Mismatch after round-trip for {k}"
    print("Bin file round-trip read/write passed.")

def test_edit_and_validation():
    print("\n=== Edit and Validation Logic ===")
    preset = PRESETS['stage1']
    test_key = next(iter(preset.values.keys()))
    param = tuning_parameters.ALL_PARAMETERS[test_key]
    # Test valid edit
    valid, msg = param.validate(preset.values[test_key])
    assert valid, f"Valid value rejected: {msg}"
    # Test invalid edit (simulate out-of-range)
    if hasattr(param, 'max_value'):
        invalid_val = getattr(param, 'max_value', 1000000) + 1
        valid, msg = param.validate(invalid_val)
        assert not valid, "Invalid value accepted"
    print("Edit and validation logic passed.")

def test_edge_cases():
    print("\n=== Edge Cases ===")
    # Missing parameter
    try:
        tuning_parameters.ALL_PARAMETERS['nonexistent']
        assert False, "Nonexistent parameter did not raise error"
    except KeyError:
        pass
    # Invalid preset name
    assert tuning_parameters.get_preset('notapreset') is None, "Invalid preset name not handled"
    print("Edge case handling passed.")

def main():
    test_preset_loading()
    test_bin_read_write_roundtrip()
 def test_write_all_parameters(tmp_path):
     """Test writing all parameters to a binary using the correct per-parameter API."""
     from flash_tool import tuning_parameters
     import shutil

     # Load a reference bin (stock)
     stock_bin_path = tuning_parameters.DEFAULT_STOCK_BIN
     bin_data = bytearray(stock_bin_path.read_bytes())

     # Get all parameters for the bin
     params = tuning_parameters.load_parameters_for_bin("I8A0S_Corbanistan")

     # Set all parameters to their tuned values (if available)
     for key, param in params.items():
         if hasattr(param, "tuned_value") and param.tuned_value is not None:
             value = param.tuned_value
         elif hasattr(param, "stock_value") and param.stock_value is not None:
             value = param.stock_value
         else:
             continue
         # Validate value before writing
         valid, msg = param.validate(value)
         assert valid, f"Validation failed for {param.name}: {msg}"
         # Write to binary using the correct API
         param.write_to_binary(bin_data, value)

     # Save to temp file
     out_path = tmp_path / "tuned.bin"
     out_path.write_bytes(bin_data)

     # Reload and verify values
     reloaded = out_path.read_bytes()
     for key, param in params.items():
         if hasattr(param, "tuned_value") and param.tuned_value is not None:
             expected = param.tuned_value
         elif hasattr(param, "stock_value") and param.stock_value is not None:
             expected = param.stock_value
         else:
             continue
         actual = param.read_from_binary(reloaded)
         # Allow for float/int conversion
         if isinstance(expected, list):
             assert all(abs(float(a) - float(b)) < 1e-3 for a, b in zip(actual, expected)), f"Mismatch for {param.name}: {actual} != {expected}"
         else:
             assert abs(float(actual) - float(expected)) < 1e-3, f"Mismatch for {param.name}: {actual} != {expected}"
     print("All parameters written and verified successfully.")
