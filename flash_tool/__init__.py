"""
Flash Tool - BMW N54 ECU Diagnostic and Tuning Tool

A Python-based command-line tool for interacting with the ECU (DME) 
of a 2008 BMW 535xi (N54 engine) via K+DCAN cable.

Author: AgentTask1.0
Date: 2025-11-01
"""

__version__ = "0.1.0"
__author__ = "Flash Tool Development Team"

# Expose convenient package-level modules expected by older imports/tests
# Import the validated_maps module (should be lightweight and available).
from . import validated_maps  # type: ignore
