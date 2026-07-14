"""Filesystem helpers that work both from source and from a PyInstaller bundle.

When packaged with PyInstaller (``--onefile``), bundled data files are unpacked
at runtime into a temporary directory exposed as ``sys._MEIPASS``.  These
helpers resolve paths correctly in both situations.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from movconv import __app_name__


def is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """Root directory for bundled resources.

    * Frozen:  the PyInstaller extraction dir (``sys._MEIPASS``).
    * Source:  the project root (the folder containing the ``movconv`` package).
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    """Absolute path to a bundled resource (e.g. ``resource_path("bin")``)."""
    return bundle_root().joinpath(*parts)


def app_data_dir() -> Path:
    """Per-user writable directory for logs and settings.

    Uses the conventional per-platform location and creates it on demand.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / __app_name__
    path.mkdir(parents=True, exist_ok=True)
    return path
