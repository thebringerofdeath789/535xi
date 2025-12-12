#!/usr/bin/env python3
"""
XDF-Independent Bin File Analyzer for BMW N54 ECUs

Instead of relying on potentially incorrect XDF files, this tool:
1. Compares stock vs tuned bins to find modifications
2. Identifies table patterns through statistical analysis
3. Detects common tuning modifications (boost, timing, fuel)
4. Provides validation through pattern recognition

This is MORE RELIABLE than blindly trusting XDF offsets.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import struct

class BinAnalyzer:
    """Analyze bin files without XDF dependency."""
    
    def __init__(self, bin_path: Path):
        self.bin_path = bin_path
        self.bin_data = bin_path.read_bytes()
        self.file_size = len(self.bin_data)
        
    def find_modified_regions(self, reference_bin: Path, min_region_size=4) -> List[Dict]:
        """
        Compare this bin with a reference to find modifications.
        
        Args:
            reference_bin: Path to stock/reference bin file
            min_region_size: Minimum consecutive bytes changed to count as region
            
        Returns:
            List of modified regions with metadata
        """
        ref_data = reference_bin.read_bytes()
        
        if len(ref_data) != len(self.bin_data):
            raise ValueError(f"File size mismatch: {len(ref_data)} vs {len(self.bin_data)}")
        
        # Find all differences
        diffs = []
        for i in range(len(self.bin_data)):
            if self.bin_data[i] != ref_data[i]:
                diffs.append((i, ref_data[i], self.bin_data[i]))
        
        if not diffs:
            return []
        
        # Group consecutive changes into regions
        regions = []
        current_region = {
            'start': diffs[0][0],
            'changes': [diffs[0]]
        }
        
        for i in range(1, len(diffs)):
            offset, old_val, new_val = diffs[i]
            
            # If consecutive or very close, add to current region
            if offset <= current_region['changes'][-1][0] + 10:
                current_region['changes'].append((offset, old_val, new_val))
            else:
                # Finalize current region
                if len(current_region['changes']) >= min_region_size:
                    current_region['end'] = current_region['changes'][-1][0]
                    current_region['size'] = len(current_region['changes'])
                    regions.append(current_region)
                
                # Start new region
                current_region = {
                    'start': offset,
                    'changes': [(offset, old_val, new_val)]
                }
        
        # Add last region
        if len(current_region['changes']) >= min_region_size:
            current_region['end'] = current_region['changes'][-1][0]
            current_region['size'] = len(current_region['changes'])
            regions.append(current_region)
        
        return regions
    
    def detect_table_structure(self, offset: int, max_size=2048) -> Optional[Dict]:
        """
        Detect if data at offset looks like a calibration table.
        
        Tables typically have:
        - 16-bit values (big-endian on MSD81)
        - Regular patterns (sorted or stepped values)
        - Reasonable value ranges
        
        Returns:
            Table metadata if detected, None otherwise
        """
        if offset + 32 > len(self.bin_data):
            return None
        
        # Try to detect table dimensions
        # Common sizes: 8x8, 10x12, 12x12, 14x14, 16x16, 16x20, 20x16
        common_dimensions = [
            (8, 8), (10, 10), (12, 12), (14, 14), (16, 16),
            (10, 12), (12, 10), (16, 20), (20, 16), (16, 12), (12, 16)
        ]
        
        best_match = None
        best_score = 0
        
        for rows, cols in common_dimensions:
            table_size = rows * cols * 2  # 16-bit values
            
            if offset + table_size > len(self.bin_data):
                continue
            
            # Extract potential table data
            values = []
            for i in range(rows * cols):
                byte_offset = offset + i * 2
                value = struct.unpack('>H', self.bin_data[byte_offset:byte_offset+2])[0]
                values.append(value)
            
            # Score this as a table
            score = self._score_as_table(values, rows, cols)
            
            if score > best_score:
                best_score = score
                best_match = {
                    'rows': rows,
                    'cols': cols,
                    'size_bytes': table_size,
                    'confidence': score,
                    'values': values
                }
        
        return best_match if best_score > 0.5 else None
    
    def _score_as_table(self, values: List[int], rows: int, cols: int) -> float:
        """
        Score how likely a set of values represents a calibration table.
        
        Returns:
            Confidence score 0.0-1.0
        """
        if not values:
            return 0.0
        
        score = 0.0
        
        # 1. Values should not be all the same
        if len(set(values)) > 1:
            score += 0.2
        
        # 2. Values should be in reasonable ranges (not all 0 or 0xFFFF)
        if not all(v == 0 for v in values) and not all(v == 0xFFFF for v in values):
            score += 0.2
        
        # 3. Check for monotonic or stepped patterns (common in tables)
        # Check rows
        row_patterns = 0
        for r in range(rows):
            row_vals = values[r*cols:(r+1)*cols]
            if self._is_monotonic(row_vals) or self._has_pattern(row_vals):
                row_patterns += 1
        
        if row_patterns > rows / 2:
            score += 0.3
        
        # 4. Values should be distributed (not all extremes)
        value_range = max(values) - min(values)
        if value_range > 0:
            avg_val = sum(values) / len(values)
            if min(values) < avg_val < max(values):
                score += 0.3
        
        return min(score, 1.0)
    
    def _is_monotonic(self, values: List[int]) -> bool:
        """Check if values are monotonically increasing or decreasing."""
        if len(values) < 3:
            return False
        
        increasing = all(values[i] <= values[i+1] for i in range(len(values)-1))
        decreasing = all(values[i] >= values[i+1] for i in range(len(values)-1))
        
        return increasing or decreasing
    
    def _has_pattern(self, values: List[int]) -> bool:
        """Check if values have a regular pattern (stepped)."""
        if len(values) < 3:
            return False
        
        # Check if differences are constant
        diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
        unique_diffs = set(diffs)
        
        # Pattern exists if only 1-3 unique step sizes
        return len(unique_diffs) <= 3
    
    def categorize_region(self, region: Dict) -> str:
        """
        Categorize what a modified region likely represents.
        
        Based on:
        - Location in file
        - Modification pattern
        - Statistical analysis
        """
        offset = region['start']
        size = region['size']
        
        # MSD81 common regions (approximate):
        # 0x40000-0x80000: Main calibration data
        # 0x60000-0x65000: Boost/WGDC tables
        # 0x70000-0x78000: Timing tables
        # 0x78000-0x7F000: Fuel tables
        
        if 0x5F000 <= offset <= 0x65000:
            return "Boost Control (WGDC)"
        elif 0x70000 <= offset <= 0x78000:
            return "Ignition Timing"
        elif 0x78000 <= offset <= 0x7F000:
            return "Fuel Tables"
        elif 0x40000 <= offset <= 0x5F000:
            return "Load/Torque Management"
        elif 0x7F000 <= offset <= 0x85000:
            return "Map Switch / Configuration"
        else:
            # Try to detect based on modification pattern
            changes = region['changes']
            
            # If many small increases, likely boost
            increases = sum(1 for _, old, new in changes if new > old)
            if increases > len(changes) * 0.7:
                return "Likely Boost/Performance (increases)"
            
            # If many decreases, could be timing advance (lower = more advanced)
            decreases = sum(1 for _, old, new in changes if new < old)
            if decreases > len(changes) * 0.7:
                return "Likely Timing Advance (decreases)"
            
            return "Unknown Calibration"


def analyze_tuned_vs_stock(stock_bin: Path, tuned_bin: Path):
    """
    Comprehensive analysis of tuned bin vs stock.
    Shows what was modified WITHOUT relying on XDF.
    """
    print("="*80)
    print("XDF-INDEPENDENT BIN ANALYSIS")
    print("="*80)
    print(f"\nStock: {stock_bin.name}")
    print(f"Tuned: {tuned_bin.name}")
    print()
    
    analyzer = BinAnalyzer(tuned_bin)
    
    # Find modifications
    print("Comparing files...")
    regions = analyzer.find_modified_regions(stock_bin)
    
    print(f"\nFound {len(regions)} modified regions:")
    print()
    
    # Analyze each region
    for i, region in enumerate(regions[:50], 1):  # Show first 50
        start = region['start']
        end = region['end']
        size = region['size']
        category = analyzer.categorize_region(region)
        
        print(f"Region {i}: 0x{start:08X} - 0x{end:08X} ({size} bytes)")
        print(f"  Category: {category}")
        
        # Try to detect table structure
        table = analyzer.detect_table_structure(start)
        if table and table['confidence'] > 0.6:
            print(f"  Table detected: {table['rows']}x{table['cols']} (confidence: {table['confidence']:.1%})")
            
            # Show value range
            vals = table['values']
            print(f"  Value range: {min(vals)} - {max(vals)} (avg: {sum(vals)//len(vals)})")
        else:
            # Show first few changes
            changes = region['changes'][:5]
            print(f"  First changes:")
            for offset, old_val, new_val in changes:
                print(f"    0x{offset:08X}: 0x{old_val:02X} -> 0x{new_val:02X}")
        
        print()
    
    if len(regions) > 50:
        print(f"... and {len(regions) - 50} more regions")
    
    print("="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
This analysis shows modifications made to the bin file.


NEXT STEPS:
1. Review detected boost/timing/fuel regions
2. Use this data to create custom table definitions
3. Cross-reference with live ECU logging
4. Build your own reliable offset database

For boost tuning:
- Focus on regions categorized as "Boost Control (WGDC)"
- Look for 0x5F000-0x65000 range modifications
- Tables are typically 16x16 or 20x16 dimensions
""")


if __name__ == '__main__':
    workspace = Path(__file__).parent.parent  # Go up to 535xi/
    
    # Example: Compare your stock vs MHD mapswitch
    stock = workspace / 'backups/WBANV93588CZ62508/WBANV93588CZ62508_I8A0S.bin'
    tuned = workspace / 'backups/WBANV93588CZ62508/WBANV93588CZ62508_I8A0S_mapswitch.bin'
    
    if stock.exists() and tuned.exists():
        analyze_tuned_vs_stock(stock, tuned)
    else:
        print(f"Test files not found:")
        print(f"  Stock: {stock}")
        print(f"  Tuned: {tuned}")
