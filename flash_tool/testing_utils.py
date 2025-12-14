from pathlib import Path
import re
from typing import Dict, List


def parse_tunerpro_export(path: Path) -> Dict[str, List[int]]:
    """Parse a simple TunerPro 'TABLE:' export into a dict of title -> list of ints.

    This parser is intentionally small and expects TABLE: <title> followed by
    whitespace-separated integer values possibly across multiple lines. It will
    ignore non-table content. Returns raw integer arrays as found in the file.
    """
    text = Path(path).read_text(encoding='utf-8', errors='ignore')
    tables: Dict[str, List[int]] = {}

    # Find TABLE blocks
    # Example header: TABLE: Ignition Timing Main (20x16)
    pattern = re.compile(r"^TABLE:\s*(.+)$", re.MULTILINE)
    headers = list(pattern.finditer(text))
    if not headers:
        return tables

    # For each header, capture until next header or EOF
    for i, m in enumerate(headers):
        title = m.group(1).strip()
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]

        # Extract integers (allow hex with 0x prefix and signed/unsigned decimal)
        nums: List[int] = []
        for token in re.findall(r"0x[0-9A-Fa-f]+|[-+]?[0-9]+", block):
            try:
                if token.lower().startswith('0x'):
                    nums.append(int(token, 16))
                else:
                    nums.append(int(token, 10))
            except Exception:
                continue

        tables[title] = nums

    return tables


def normalize_title(t: str) -> str:
    """Normalize a TunerPro title for fuzzy matching: lower, remove non-alnum."""
    return re.sub(r'[^a-z0-9]', '', t.lower())
