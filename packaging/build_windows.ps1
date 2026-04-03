$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$vendorBin = Join-Path $projectRoot "resources\vendor\bin"
$ffmpegExe = Join-Path $vendorBin "ffmpeg.exe"
$ffprobeExe = Join-Path $vendorBin "ffprobe.exe"

if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffprobeExe)) {
    & (Join-Path $PSScriptRoot "install_ffmpeg.ps1")
}

pip install -e .[dev]
pyinstaller packaging/logo_toolkit.spec
