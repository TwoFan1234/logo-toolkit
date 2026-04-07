param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pyproject = Join-Path $projectRoot "pyproject.toml"

if (-not $Version) {
    $versionLine = Get-Content $pyproject | Where-Object { $_ -match '^version\s*=\s*"([^"]+)"' } | Select-Object -First 1
    if ($versionLine -match '^version\s*=\s*"([^"]+)"') {
        $Version = $Matches[1]
    }
}

if (-not $Version) {
    throw "Could not read version from pyproject.toml. Pass -Version manually."
}

$dateStamp = Get-Date -Format "yyyyMMdd"
$displayName = [string]::Concat([char]0x7D20, [char]0x6750, [char]0x5DE5, [char]0x5177, [char]0x7BB1)
$exeName = "$displayName.exe"
$releaseName = "$displayName-v$Version-$dateStamp"
$releaseRoot = Join-Path $projectRoot "release"
$releaseDir = Join-Path $releaseRoot $releaseName
$zipPath = Join-Path $releaseRoot "$releaseName.zip"
$distExe = Join-Path $projectRoot "dist\$exeName"

& (Join-Path $PSScriptRoot "build_windows.ps1")

if (-not (Test-Path $distExe)) {
    throw "Build output not found: $distExe"
}

New-Item -ItemType Directory -Force $releaseRoot | Out-Null

if (Test-Path $releaseDir) {
    Remove-Item -Recurse -Force $releaseDir
}

New-Item -ItemType Directory -Force $releaseDir | Out-Null
Copy-Item -Path $distExe -Destination (Join-Path $releaseDir $exeName) -Force

$teamUsageSource = Join-Path $projectRoot "docs\TEAM_USAGE.md"
if (Test-Path $teamUsageSource) {
    Copy-Item $teamUsageSource (Join-Path $releaseDir "TEAM_USAGE.md") -Force

    $chineseUsageName = [string]::Concat(
        [char]0x4F7F,
        [char]0x7528,
        [char]0x8BF4,
        [char]0x660E,
        ".txt"
    )
    Get-Content $teamUsageSource -Encoding UTF8 | Set-Content (Join-Path $releaseDir $chineseUsageName) -Encoding UTF8
}

$quickStart = @"
Asset Toolkit Team Build
Version: v$Version
Date: $dateStamp

1. Extract this zip file.
2. Double-click the exe file in this folder.
3. If Windows shows a safety prompt, click More info, then Run anyway.
4. This is a single-file build. You can copy the exe file to another folder if needed.
5. Test with a few files first, then process the full batch.

For Chinese usage instructions, open TEAM_USAGE.md or the Chinese txt file.
"@

Set-Content -Path (Join-Path $releaseDir "START_HERE.txt") -Value $quickStart -Encoding UTF8

if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath -Force

Write-Host "Release zip created: $zipPath"
