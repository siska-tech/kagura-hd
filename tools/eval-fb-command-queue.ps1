# SPDX-License-Identifier: Apache-2.0
[CmdletBinding()]
param(
    [string]$GowinExe='C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',
    [ValidateSet('spi','qspi')][string]$Transport='qspi',
    [ValidateSet(1,2,4,8)][int[]]$Depths=@(1,2,4,8),
    [ValidateRange(0,4)][int]$PlaceOption=1,
    [ValidateRange(0,2)][int]$RouteOption=2,
    [switch]$RegisterAudioCredits,
    [switch]$ReplicatePacketFirst,
    [ValidateSet('auto','area','timing')][string]$OptimizationGoal='auto',
    [string]$OutputBase='build/fb-queue-eval'
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if(!(Test-Path (Join-Path $root 'build/generated/kagura_hdmi_stream.sv'))) {
    throw 'Run python3 tools/prepare-hdmi-stream.py first'
}
$results=@()
$evidence=Join-Path $root $OutputBase
New-Item -ItemType Directory -Force $evidence | Out-Null
$inputs=@(Get-Content (Join-Path $root 'rtl/fb/sources.f') | Where-Object { $_.Trim() })
$inputs += @('rtl/fb/sources.f','rtl/platform/kagura_gowin_serializer.sv',
    'rtl/platform/kagura_nano9k_clocks.sv','rtl/memory/kagura_hyperram_phy_gowin.sv',
    'boards/tang-nano-9k/kagura_fb_top.sv','boards/tang-nano-9k/phase1.cst',
    'boards/tang-nano-9k/host.cst','boards/tang-nano-9k/kagura-fb.sdc','tools/build-fb.tcl')
$inputs | ForEach-Object {
    [pscustomobject]@{path=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $root $_) -Algorithm SHA256).Hash}
} | ConvertTo-Json | Set-Content (Join-Path $evidence 'source-sha256.json') -Encoding utf8
foreach($inputPath in $inputs) {
    $snapshot=Join-Path (Join-Path $evidence 'source-snapshot') $inputPath
    New-Item -ItemType Directory -Force (Split-Path -Parent $snapshot) | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $inputPath) -Destination $snapshot
}
foreach($depth in $Depths) {
    $relative="$OutputBase/$Transport-depth-$depth"
    $build=Join-Path $root $relative
    New-Item -ItemType Directory -Force $build | Out-Null
    $started=Get-Date
    Push-Location $build
    try {
        & $GowinExe (Join-Path $root 'tools/build-fb.tcl') $Transport $PlaceOption $RouteOption $depth ([int]$RegisterAudioCredits.IsPresent) ([int]$ReplicatePacketFirst.IsPresent) $OptimizationGoal 2>&1 | Tee-Object -FilePath build.log
        $buildExit=$LASTEXITCODE
        $failed=$buildExit -ne 0 -or (Select-String -LiteralPath build.log -Pattern '^ERROR\s*\(' -Quiet)
        $bitstream=Get-Item -LiteralPath 'impl/pnr/kagura_fb.fs' -ErrorAction SilentlyContinue
        $fresh=$null -ne $bitstream -and $bitstream.LastWriteTime -ge $started
        $timing=$null
        if(!$failed -and $fresh) {
            & (Join-Path $PSScriptRoot 'check-fb-timing.ps1') -BuildDir $relative -ReportOnly
            $timing=Get-Content timing-status.json -Raw | ConvertFrom-Json
        }
        $entry=[ordered]@{depth=$depth;transport=$Transport;place=$PlaceOption;route=$RouteOption;exit_code=$buildExit;
            register_audio_credits=$RegisterAudioCredits.IsPresent;
            replicate_packet_first=$ReplicatePacketFirst.IsPresent;
            optimization_goal=$OptimizationGoal;
            build_failed=$failed;fresh_bitstream=$fresh;timing=$timing;
            elapsed_seconds=[math]::Round(((Get-Date)-$started).TotalSeconds,1)}
        if($fresh) { $entry.bitstream_sha256=(Get-FileHash $bitstream.FullName -Algorithm SHA256).Hash }
        $results += [pscustomobject]$entry
        $entry | ConvertTo-Json -Depth 12 | Set-Content result.json -Encoding utf8
    } finally { Pop-Location }
    $results | ConvertTo-Json -Depth 12 | Set-Content (Join-Path $evidence "$Transport-results.json") -Encoding utf8
}
if(@($results | Where-Object { $_.build_failed -or !$_.fresh_bitstream }).Count) {
    throw "Some queue candidates failed to build; inspect $OutputBase/*-results.json"
}
