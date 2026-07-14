# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MovToMp4.

Builds a single-file, windowed executable and bundles the local ``bin/`` folder
(containing ffmpeg/ffprobe) so the app is fully self-contained.

Build with:
    pyinstaller MovToMp4.spec
or simply:
    python build.py
"""
from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH)
bin_dir = project_root / "bin"

# Bundle every file inside bin/ under a "bin/" folder in the package so that
# resources.resource_path("bin") resolves correctly at runtime.
datas = []
if bin_dir.is_dir():
    for f in bin_dir.iterdir():
        if f.is_file():
            datas.append((str(f), "bin"))

a = Analysis(
    ["run.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MovToMp4",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed GUI app (no console window)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # add an icon here if you have one
)
