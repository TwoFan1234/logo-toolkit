# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).parent
app_name = "".join(chr(codepoint) for codepoint in (0x7D20, 0x6750, 0x5DE5, 0x5177, 0x7BB1))
hiddenimports = collect_submodules("PIL")
vendor_bin = project_root / "resources" / "vendor" / "bin"
icon_path = project_root / "resources" / "app_icon.ico"
binaries = []
datas = []

for binary_name in ("ffmpeg.exe", "ffprobe.exe"):
    binary_path = vendor_bin / binary_name
    if binary_path.exists():
        binaries.append((str(binary_path), "vendor/bin"))

if icon_path.exists():
    datas.append((str(icon_path), "."))


a = Analysis(
    [str(project_root / "src" / "logo_toolkit" / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
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
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    icon=str(icon_path) if icon_path.exists() else None,
    console=False,
)
