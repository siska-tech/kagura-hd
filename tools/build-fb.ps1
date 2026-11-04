# SPDX-License-Identifier: Apache-2.0
[CmdletBinding()]
param(
    [string]$GowinExe='C:/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',
    [ValidateSet("spi","qspi")][string]$Transport="spi",
    [switch]$ReportOnly
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & python tools/prepare-hdmi-stream.py
    if($LASTEXITCODE -ne 0) { throw 'HDMI generation failed' }
    $relativeBuild=if($Transport -eq 'spi') { 'build/kagura-fb' } else { 'build/kagura-fb-qspi' }
    $build=Join-Path $root $relativeBuild
    New-Item -ItemType Directory -Force $build | Out-Null
    $started=Get-Date
    Push-Location $build
    try {
        & $GowinExe (Join-Path $root 'tools/build-fb.tcl') $Transport 2>&1 | Tee-Object -FilePath build.log
        if($LASTEXITCODE -ne 0) { throw 'Gowin build failed' }
        if(Select-String -LiteralPath build.log -Pattern '^ERROR\s*\(' -Quiet) { throw 'Gowin reported synthesis/P&R errors' }
        $bitstream=Get-Item -LiteralPath 'impl/pnr/kagura_fb.fs'
        if($bitstream.LastWriteTime -lt $started) { throw 'Bitstream was not regenerated' }
    } finally { Pop-Location }
    & (Join-Path $PSScriptRoot 'check-fb-timing.ps1') -BuildDir $relativeBuild -ReportOnly:$ReportOnly
} finally { Pop-Location }
