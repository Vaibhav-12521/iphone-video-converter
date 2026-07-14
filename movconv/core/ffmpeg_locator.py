"""Locate the ``ffmpeg`` and ``ffprobe`` executables.

Search order (first hit wins):

1. Explicit override via the ``MOVCONV_FFMPEG_DIR`` environment variable.
2. A ``bin/`` folder bundled next to the app (or inside the PyInstaller bundle).
3. The system ``PATH``.

If neither binary can be found a :class:`FFmpegNotFound` error is raised with a
human-friendly message explaining how to fix it.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from movconv.utils.resources import resource_path

log = logging.getLogger(__name__)

# Flags to prevent a console window flashing when we spawn ffmpeg on Windows.
if sys.platform == "win32":
    _CREATE_NO_WINDOW = 0x08000000
    SUBPROCESS_FLAGS = _CREATE_NO_WINDOW
else:
    SUBPROCESS_FLAGS = 0

_EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""


class FFmpegNotFound(RuntimeError):
    """Raised when ffmpeg/ffprobe cannot be located."""


@dataclass(frozen=True)
class FFmpegTools:
    """Resolved paths to the FFmpeg tools plus the detected version banner."""

    ffmpeg: str
    ffprobe: str
    version: str


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    env_dir = os.environ.get("MOVCONV_FFMPEG_DIR")
    if env_dir:
        dirs.append(Path(env_dir))
    dirs.append(resource_path("bin"))
    return dirs


def _find_in_dirs(name: str) -> str | None:
    filename = name + _EXE_SUFFIX
    for d in _candidate_dirs():
        candidate = d / filename
        if candidate.is_file():
            return str(candidate)
    # Fall back to PATH.
    return shutil.which(name)


def _read_version(ffmpeg: str) -> str:
    try:
        out = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True,
            text=True,
            creationflags=SUBPROCESS_FLAGS,
            timeout=15,
        )
        first_line = (out.stdout or out.stderr).splitlines()[0]
        return first_line.strip()
    except Exception:  # pragma: no cover
        return "unknown version"


def locate_ffmpeg() -> FFmpegTools:
    """Find ffmpeg + ffprobe or raise :class:`FFmpegNotFound`."""
    ffmpeg = _find_in_dirs("ffmpeg")
    ffprobe = _find_in_dirs("ffprobe")

    missing = [n for n, p in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if not p]
    if missing:
        raise FFmpegNotFound(
            "Could not find: " + ", ".join(missing) + ".\n\n"
            "Fix it in any of these ways:\n"
            "  1. Run  python scripts/download_ffmpeg.py  to fetch a local copy "
            "into the app's bin/ folder.\n"
            "  2. Install FFmpeg and make sure it is on your PATH "
            "(https://ffmpeg.org/download.html).\n"
            "  3. Set the MOVCONV_FFMPEG_DIR environment variable to the folder "
            "that contains ffmpeg/ffprobe."
        )

    version = _read_version(ffmpeg)
    log.info("Using FFmpeg: %s", version)
    log.info("  ffmpeg:  %s", ffmpeg)
    log.info("  ffprobe: %s", ffprobe)
    return FFmpegTools(ffmpeg=ffmpeg, ffprobe=ffprobe, version=version)
