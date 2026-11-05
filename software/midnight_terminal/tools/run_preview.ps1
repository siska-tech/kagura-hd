$root = Split-Path $PSScriptRoot -Parent
$python = Get-Command python3.12.exe -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python }
if (-not (Test-Path "$root/out/midnight.dll")) { & "$PSScriptRoot/build_pc.ps1" }
& $python.Source "$PSScriptRoot/preview.py"
