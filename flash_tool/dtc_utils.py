#!/usr/bin/env python3
"""
Diagnostic Trouble Code (DTC) parsing utilities
===============================================

Provides shared DTC parsing functions used by both UDS and KWP clients.

Functions:
    - parse_dtc_response(response_data: bytes, positive_header: int) -> List[Dict[str, Any]]

The parsing follows UDS/KWP-style triplet format:
    [Header] [Subfunction] [DTC1_HI] [DTC1_LO] [STATUS1] [DTC2_HI] [DTC2_LO] [STATUS2] ...

This is intentionally conservative and focuses on robust parsing for unit
testing and basic diagnostic retrieval across both transport layers.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import logging
from . import dtc_database

logger = logging.getLogger(__name__)


def parse_dtc_response(response_data: bytes, positive_header: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Parse a DTC response from UDS/KWP into structured dictionaries.

    Args:
        response_data: Raw bytes returned by the ECU
        positive_header: Optional expected positive response header value (e.g., 0x59 for UDS 0x19)

    Returns:
        List of DTC dicts with 'code', 'status', 'pending', 'confirmed', 'active', 'description', 'severity'
    """
    dtcs: List[Dict[str, Any]] = []
    if not response_data or len(response_data) < 3:
        return dtcs

    # If a positive header is provided, validate it
    if positive_header is not None and response_data[0] != positive_header:
        logger.warning(f"Invalid DTC response header: 0x{response_data[0]:02X}")
        return dtcs

    # If header exists, skip the first two bytes (header + subfunction)
    offset = 2 if (len(response_data) > 2) else 0

    while offset + 2 < len(response_data):
        dtc_high = response_data[offset]
        dtc_low = response_data[offset + 1]
        status = response_data[offset + 2]

        # Decode DTC code type from first two bits
        dtc_type_bits = (dtc_high >> 6) & 0x03
        dtc_types = {0: 'P', 1: 'C', 2: 'B', 3: 'U'}
        dtc_type = dtc_types.get(dtc_type_bits, 'P')

        dtc_number = ((dtc_high & 0x3F) << 8) | dtc_low

        # Compatibility tweak for specific U-codes
        if dtc_type == 'U' and 0x1000 <= dtc_number < 0x2000:
            dtc_number -= 0x1000

        dtc_code = f"{dtc_type}{dtc_number:04X}"

        dtc_info = dtc_database.lookup_dtc(dtc_code)

        dtc_dict = {
            'code': dtc_code,
            'status': status,
            'pending': bool(status & 0x01),
            'confirmed': bool(status & 0x08),
            'active': bool(status & 0x80) or bool(status & 0x08),
            'status_pending': bool(status & 0x01),
            'status_confirmed': bool(status & 0x08),
            'status_active': bool(status & 0x80) or bool(status & 0x08),
            'description': dtc_info.description if dtc_info else 'Unknown DTC',
            'severity': dtc_info.severity.value if dtc_info else 'Unknown'
        }

        dtcs.append(dtc_dict)
        offset += 3

    return dtcs
