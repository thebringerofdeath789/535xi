from pathlib import Path
from typing import Dict, Optional

# Mapping from OS family (prefix) to authoritative XDF path
OS_AUTHORITATIVE_XDF: Dict[str, Path] = {
    'I8A0S': Path('maps/xdf_definitions/github/I8A0S_Custom_Corbanistan.xdf'),
    'IJE0S': Path('maps/xdf_definitions/github/IJE0S_zarboz.xdf'),
    'IKM0S': Path('maps/xdf_definitions/github/IKM0S_zarboz.xdf'),
    'INA0S': Path('maps/xdf_definitions/github/INA0S_zarboz.xdf'),
    # fallback Zarboz variant
    'ZARBOZ_IJE0S': Path('maps/xdf_definitions/github/zarboz-IJE0S-Standard-Units.xdf'),
}

DEFAULT_XDF = OS_AUTHORITATIVE_XDF['I8A0S']


def _infer_os_from_bin(bin_name: str) -> Optional[str]:
    """Infer OS family from a bin name like 'I8A0S_Corbanistan' or 'IJE0S_zarboz'.
    Returns the OS family prefix (e.g., 'I8A0S') or None if it cannot be inferred.
    """
    if not bin_name:
        return None
    # Bin name may contain underscores; take first token
    token = bin_name.split('_')[0]
    token = token.strip()
    if token.upper() in OS_AUTHORITATIVE_XDF:
        return token.upper()
    # Some names might not include underscore; check if the token matches any key
    upper_token = bin_name.upper()
    for k in OS_AUTHORITATIVE_XDF.keys():
        if k in upper_token:
            return k
    return None


def get_authoritative_xdf_for_os_family(os_family: str) -> Path:
    """Return the authoritative XDF path for the given OS family. If the OS family
    is not recognized, return the default I8A0S Corbanistan XDF path.
    """
    if not os_family:
        return DEFAULT_XDF
    return OS_AUTHORITATIVE_XDF.get(os_family.upper(), DEFAULT_XDF)


def get_authoritative_xdf_for_bin(bin_name: str) -> Path:
    """Return the authoritative XDF path for the provided bin/XDF name.
    If the bin name can be inferred to an OS family (via prefix), return that OS family's
authoritative XDF. Otherwise, return the default.
    """
    os_family = _infer_os_from_bin(bin_name)
    return get_authoritative_xdf_for_os_family(os_family) if os_family else DEFAULT_XDF
