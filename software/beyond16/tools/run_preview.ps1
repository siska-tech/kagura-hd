$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$root/out/optimized.dll")) {& "$PSScriptRoot/build_pc.ps1"}
& python3.12.exe "$PSScriptRoot/preview.py" @args
if ($LASTEXITCODE -ne 0) {throw 'Preview failed'}
