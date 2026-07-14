#!/usr/bin/env python3
"""Download a static FFmpeg build into the project's ``bin/`` folder.

This lets the app run (and be packaged) without requiring the user to install
FFmpeg system-wide.  Static builds are fetched from well-known providers:

* Windows : gyan.dev "essentials" build
* Linux   : John Van Sickle static build
* macOS   : evermeet.cx (ffmpeg + ffprobe fetched separately)

Usage:
    python scripts/download_ffmpeg.py

Network access is required.  If it is unavailable, install FFmpeg manually and
put ``ffmpeg``/``ffprobe`` on your PATH (or in this ``bin/`` folder).
"""
from __future__ import annotations

import io
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parents[1] / "bin"

WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
LINUX_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
MAC_FFMPEG_URL = "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
MAC_FFPROBE_URL = "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"

EXE = ".exe" if sys.platform == "win32" else ""


def _download(url: str) -> bytes:
    print(f"  Downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "movconv-setup"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read()


def _place(src: Path, name: str) -> None:
    """Copy *src* into bin/ as *name* and mark it executable."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = BIN_DIR / (name + EXE)
    shutil.copy2(src, dest)
    if sys.platform != "win32":
        dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  Installed {dest}")


def _install_windows() -> None:
    data = _download(WIN_URL)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = {Path(m).name: m for m in zf.namelist()}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for tool in ("ffmpeg.exe", "ffprobe.exe"):
                member = members.get(tool)
                if not member:
                    raise RuntimeError(f"{tool} not found in archive")
                extracted = Path(zf.extract(member, tmp_path))
                _place(extracted, tool[:-4])


def _install_linux() -> None:
    data = _download(LINUX_URL)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for member in tf.getmembers():
                base = Path(member.name).name
                if base in ("ffmpeg", "ffprobe") and member.isfile():
                    member.name = base
                    tf.extract(member, tmp_path)
                    _place(tmp_path / base, base)


def _install_mac() -> None:
    for url, name in ((MAC_FFMPEG_URL, "ffmpeg"), (MAC_FFPROBE_URL, "ffprobe")):
        data = _download(url)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                zf.extractall(tmp_path)
                found = next(tmp_path.rglob(name), None)
                if not found:
                    raise RuntimeError(f"{name} not found in archive")
                _place(found, name)


def main() -> int:
    system = platform.system()
    print(f"Installing FFmpeg for {system} into {BIN_DIR}")
    try:
        if system == "Windows":
            _install_windows()
        elif system == "Linux":
            _install_linux()
        elif system == "Darwin":
            _install_mac()
        else:
            print(f"Unsupported platform: {system}", file=sys.stderr)
            return 2
    except Exception as exc:  # pragma: no cover
        print(f"\nERROR: {exc}", file=sys.stderr)
        print(
            "Download failed. Install FFmpeg manually from "
            "https://ffmpeg.org/download.html and put ffmpeg/ffprobe on your PATH.",
            file=sys.stderr,
        )
        return 1
    print("\nFFmpeg installed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
