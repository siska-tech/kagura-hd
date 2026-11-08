# SPDX-License-Identifier: Apache-2.0
[CmdletBinding()]
param(
    [string]$GowinExe='C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',
    [ValidateSet("spi","qspi")][string]$Transport="qspi",
    [ValidateRange(0,4)][int]$PlaceOption=1,
    [ValidateRange(0,2)][int]$RouteOption=2,
    [ValidateSet(1,2,4,8)][int]$QueueDepth=1,
    [switch]$RegisterAudioCredits,
    [switch]$ReplicatePacketFirst,
    [ValidateSet('auto','area','timing')][string]$OptimizationGoal='auto',
    [switch]$ReportOnly
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & python tools/prepare-hdmi-stream.py
    if($LASTEXITCODE -ne 0) { throw 'HDMI generation failed' }
    $relativeBuild=if($Transport -eq 'spi') { 'build/kagura-fb' } else { 'build/kagura-fb-qspi' }
    if($PlaceOption -ne 1 -or $RouteOption -ne 2) {
        $relativeBuild += "-p$PlaceOption-r$RouteOption"
    }
    if($QueueDepth -ne 1) { $relativeBuild += "-queue$QueueDepth" }
    if($RegisterAudioCredits) { $relativeBuild += '-credits' }
    if($ReplicatePacketFirst) { $relativeBuild += '-packet-first' }
    if($OptimizationGoal -ne 'auto') { $relativeBuild += "-opt-$OptimizationGoal" }
    $build=Join-Path $root $relativeBuild
    New-Item -ItemType Directory -Force $build | Out-Null
    $started=Get-Date
    Push-Location $build
    try {
        & $GowinExe (Join-Path $root 'tools/build-fb.tcl') $Transport $PlaceOption $RouteOption $QueueDepth ([int]$RegisterAudioCredits.IsPresent) ([int]$ReplicatePacketFirst.IsPresent) $OptimizationGoal 2>&1 | Tee-Object -FilePath build.log
        if($LASTEXITCODE -ne 0) { throw 'Gowin build failed' }
        if(Select-String -LiteralPath build.log -Pattern '^ERROR\s*\(' -Quiet) { throw 'Gowin reported synthesis/P&R errors' }
        $bitstream=Get-Item -LiteralPath 'impl/pnr/kagura_fb.fs'
        if($bitstream.LastWriteTime -lt $started) { throw 'Bitstream was not regenerated' }
    } finally { Pop-Location }
    & (Join-Path $PSScriptRoot 'check-fb-timing.ps1') -BuildDir $relativeBuild -ReportOnly:$ReportOnly
} finally { Pop-Location }
