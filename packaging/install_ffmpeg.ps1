$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$vendorBin = Join-Path $projectRoot "resources\vendor\bin"
New-Item -ItemType Directory -Force $vendorBin | Out-Null

$tempRoot = Join-Path $env:TEMP "logo-toolkit-ffmpeg"
if (Test-Path $tempRoot) {
    Remove-Item -Recurse -Force $tempRoot
}
New-Item -ItemType Directory -Force $tempRoot | Out-Null

$ffmpegZip = Join-Path $tempRoot "ffmpeg-release-essentials.zip"
$extractRoot = Join-Path $tempRoot "ffmpeg"

Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ffmpegZip
Expand-Archive -Path $ffmpegZip -DestinationPath $extractRoot -Force

$ffmpegExe = Get-ChildItem $extractRoot -Recurse -Filter ffmpeg.exe | Select-Object -First 1
$ffprobeExe = Get-ChildItem $extractRoot -Recurse -Filter ffprobe.exe | Select-Object -First 1

if (-not $ffmpegExe -or -not $ffprobeExe) {
    throw "未能从下载包中找到 ffmpeg.exe 或 ffprobe.exe"
}

Copy-Item $ffmpegExe.FullName (Join-Path $vendorBin "ffmpeg.exe") -Force
Copy-Item $ffprobeExe.FullName (Join-Path $vendorBin "ffprobe.exe") -Force

Remove-Item -Recurse -Force $tempRoot
