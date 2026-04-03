"""Path resolution for frozen (PyInstaller) and dev environments."""
from __future__ import annotations

import json
import os
import shutil
import sys

# Default content for writable data files (created if missing)
_WRITABLE_DEFAULTS: dict[str, str] = {
    "sl_teams_zamen.json": "{}",
    "sl_teams_rejected.json": "[]",
}


def get_base_dir() -> str:
    """Return base directory: _MEIPASS for frozen exe, project root for dev."""
    if getattr(sys, "frozen", False):
        # PyInstaller bundles data into sys._MEIPASS
        return sys._MEIPASS  # type: ignore[attr-defined]
    # Dev: project root is two levels up from src/paths.py -> src/ -> project_root/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_exe_dir() -> str:
    """Return directory where the exe (or project root in dev) lives.

    Use for writable files that must persist between runs.
    In frozen mode: directory containing the .exe file.
    In dev mode: project root (same as get_base_dir).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_path(filename: str) -> str:
    """Resolve a read-only file from assets/data/ (bundled inside exe)."""
    return os.path.join(get_base_dir(), "assets", "data", filename)


def writable_data_path(filename: str) -> str:
    """Resolve a writable file from assets/data/ next to exe.

    If the file already exists next to exe — uses it as-is.
    If not — copies from bundled assets (inside exe) if available,
    otherwise creates a new empty file with default content.
    """
    dir_path = os.path.join(get_exe_dir(), "assets", "data")
    os.makedirs(dir_path, exist_ok=True)
    target = os.path.join(dir_path, filename)

    if os.path.isfile(target):
        return target

    # Try copying from bundled assets (inside _MEIPASS)
    bundled = os.path.join(get_base_dir(), "assets", "data", filename)
    if bundled != target and os.path.isfile(bundled):
        shutil.copy2(bundled, target)
        return target

    # Create with default content
    default_content = _WRITABLE_DEFAULTS.get(filename, "{}")
    with open(target, "w", encoding="utf-8") as f:
        f.write(default_content)
    return target
