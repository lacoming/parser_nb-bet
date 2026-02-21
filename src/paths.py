"""Path resolution for frozen (PyInstaller) and dev environments."""
from __future__ import annotations

import os
import sys


def get_base_dir() -> str:
    """Return base directory: _MEIPASS for frozen exe, project root for dev."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundles data into sys._MEIPASS
        return sys._MEIPASS  # type: ignore[attr-defined]
    # Dev: project root is two levels up from src/paths.py -> src/ -> project_root/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_path(filename: str) -> str:
    """Resolve a file from assets/data/."""
    return os.path.join(get_base_dir(), "assets", "data", filename)
