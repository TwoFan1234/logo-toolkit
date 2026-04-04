# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).parent
hiddenimports = collect_submodules("PIL")
vendor_bin = project_root / "resources" / "vendor" / "bin"
binaries = []

for binary_name in ("ffmpeg.exe", "ffprobe.exe"):
    binary_path = vendor_bin / binary_name
    if binary_path.exists():
        binaries.append((str(binary_path), "vendor/bin"))


a = Analysis(
    [str(project_root / "src" / "logo_toolkit" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LogoToolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LogoToolkit",
)
