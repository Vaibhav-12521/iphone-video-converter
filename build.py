#!/usr/bin/env python3
"""One-command build script: produce a standalone executable with PyInstaller.

Steps:
1. Ensure PyInstaller is installed.
2. Warn (but continue) if bin/ has no ffmpeg - the user may rely on PATH.
3. Invoke PyInstaller with MovToMp4.spec.

Usage:
    python build.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXE = ".exe" if sys.platform == "win32" else ""


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found - installing it now…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=6.3.0"])


def _check_bin() -> None:
    bin_dir = ROOT / "bin"
    ffmpeg = bin_dir / f"ffmpeg{EXE}"
    if not ffmpeg.is_file():
        print(
            "WARNING: bin/ffmpeg not found. The build will NOT bundle FFmpeg,\n"
            "         so the packaged app will rely on FFmpeg being on the\n"
            "         user's PATH. To bundle it, run:\n"
            "             python scripts/download_ffmpeg.py\n"
        )
    else:
        print(f"Bundling FFmpeg from {bin_dir}")


def main() -> int:
    _ensure_pyinstaller()
    _check_bin()
    print("Running PyInstaller…")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "MovToMp4.spec"],
        cwd=ROOT,
    )
    if result.returncode == 0:
        out = ROOT / "dist" / f"MovToMp4{EXE}"
        print(f"\nBuild complete: {out}")
    else:
        print("\nBuild failed.", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
