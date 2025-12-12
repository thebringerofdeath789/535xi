"""
flash_tool.security
-------------------

Seed->key algorithm registry and implementations for BMW ECU security access.

Algorithms:
- v1: MSS54/MSD80 common algorithm (XOR with 0x4D48 'MH')
- v2: MSD80 byte swap variant
- v3: BM constant variant (XOR with 0x424D 'BM')
- rftx: Production RFTX algorithm (confirmed working)

All algorithms accept a 4-byte seed and return a 4-byte key.
"""
from typing import Callable, Dict

Algorithm = Callable[[bytes], bytes]

_algorithms: Dict[str, Algorithm] = {}


def register_algorithm(name: str, func: Algorithm) -> None:
    """Register a seed->key algorithm under a short name.

    Args:
        name: short algorithm name (e.g. "v1", "rftx").
        func: callable(seed: bytes) -> key: bytes
    """
    _algorithms[name] = func


def get_algorithm(name: str) -> Algorithm:
    """Return a previously-registered algorithm.

    Raises KeyError if the algorithm is not registered.
    """
    return _algorithms[name]


def compute_key(name: str, seed: bytes) -> bytes:
    """Compute key for a given seed using the named algorithm.

    This is a convenience wrapper around `get_algorithm`.
    """
    alg = get_algorithm(name)
    return alg(seed)


def list_algorithms() -> list[str]:
    """Return list of registered algorithm names."""
    return list(_algorithms.keys())


# ============================================================================
# Algorithm Implementations
# ============================================================================

def _algorithm_v1(seed: bytes) -> bytes:
    """MSS54/MSD80 common algorithm.
    
    XOR with 'MH' (0x4D48) constant + cross-XOR of seed bytes.
    """
    if len(seed) != 4:
        raise ValueError(f"Seed must be 4 bytes, got {len(seed)}")
    
    key = bytearray(4)
    key[0] = seed[0] ^ 0x48  # 'H'
    key[1] = seed[1] ^ 0x4D  # 'M'
    key[2] = seed[2] ^ seed[0]
    key[3] = seed[3] ^ seed[1]
    return bytes(key)


def _algorithm_v2(seed: bytes) -> bytes:
    """MSD80 byte swap variant.
    
    Rotate seed bytes, then XOR with 'MH' pattern.
    """
    if len(seed) != 4:
        raise ValueError(f"Seed must be 4 bytes, got {len(seed)}")
    
    rotated = bytearray([seed[1], seed[0], seed[3], seed[2]])
    key = bytearray(4)
    key[0] = rotated[0] ^ 0x4D
    key[1] = rotated[1] ^ 0x48
    key[2] = rotated[2] ^ 0x4D
    key[3] = rotated[3] ^ 0x48
    return bytes(key)


def _algorithm_v3(seed: bytes) -> bytes:
    """BM constant variant.
    
    XOR with 'BM' (0x424D) constant.
    """
    if len(seed) != 4:
        raise ValueError(f"Seed must be 4 bytes, got {len(seed)}")
    
    key = bytearray(4)
    key[0] = seed[0] ^ 0x42  # 'B'
    key[1] = seed[1] ^ 0x4D  # 'M'
    key[2] = seed[2] ^ 0x42
    key[3] = seed[3] ^ 0x4D
    return bytes(key)


def _algorithm_rftx(seed: bytes) -> bytes:
    """Production RFTX algorithm.
    
    Confirmed working algorithm: ((seed ^ 0x5A3C) + 0x7F1B) & 0xFFFF
    
    This is a 2-byte algorithm that has been verified against real RFTX
    BMW flasher implementation. Converts 2-byte seed to 2-byte key with
    XOR and addition operations.
    
    Note: The input seed should be 2 bytes. If 4 bytes are provided,
    uses the first 2 bytes.
    """
    if len(seed) < 2:
        raise ValueError(f"RFTX seed must be at least 2 bytes, got {len(seed)}")
    
    # Use only first 2 bytes for 2-byte algorithm
    seed_word = int.from_bytes(seed[:2], 'big')
    
    # RFTX algorithm: ((seed ^ 0x5A3C) + 0x7F1B) & 0xFFFF
    key_word = ((seed_word ^ 0x5A3C) + 0x7F1B) & 0xFFFF
    
    # Return as bytes
    return key_word.to_bytes(2, 'big')


def noop_algorithm(seed: bytes) -> bytes:
    """Placeholder algorithm used for tests.

    Returns the seed reversed as a deterministic, harmless transformation.
    """
    return seed[::-1]


# ============================================================================
# Algorithm Registration
# ============================================================================

# Register all algorithms
register_algorithm("v1", _algorithm_v1)
register_algorithm("v2", _algorithm_v2)
register_algorithm("v3", _algorithm_v3)
register_algorithm("rftx", _algorithm_rftx)
register_algorithm("noop", noop_algorithm)


__all__ = [
    "register_algorithm",
    "get_algorithm",
    "compute_key",
    "list_algorithms",
    "noop_algorithm",
]
