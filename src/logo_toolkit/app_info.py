from __future__ import annotations

import sys
from pathlib import Path

APP_DISPLAY_NAME = "".join(chr(codepoint) for codepoint in (0x7D20, 0x6750, 0x5DE5, 0x5177, 0x7BB1))


def bundled_resource_path(file_name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / file_name
    return Path(__file__).resolve().parents[2] / "resources" / file_name
