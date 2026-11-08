# SPDX-License-Identifier: Apache-2.0
# Re-run P&R of the provisionally approved mapped design. No programming.
[CmdletBinding()]
param(
    [string]$GowinExe='C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',
    [string]$SourceBuild='build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8',
    [Parameter(Mandatory)][string]$OutputBuild,
    [ValidateRange(0,4)][int]$PlaceOption=4,
    [ValidateRange(0,2)][int]$RouteOption=2,
    [ValidateRange(1,100)][int]$RouteMaxFan=23,
    [string]$ExtraCst='',
    [switch]$ReplicateResources
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$source=[IO.Path]::GetFullPath((Join-Path $root $SourceBuild))
$output=[IO.Path]::GetFullPath((Join-Path $root $OutputBuild))
$buildRoot=[IO.Path]::GetFullPath((Join-Path $root 'build'))+[IO.Path]::DirectorySeparatorChar
if(!$source.StartsWith($buildRoot,[StringComparison]::OrdinalIgnoreCase) -or !$output.StartsWith($buildRoot,[StringComparison]::OrdinalIgnoreCase)) {throw 'Use build directories inside the workspace'}
if(Test-Path -LiteralPath $output) {throw 'Refuse to overwrite an existing P&R experiment'}
$frozen=Get-Content -LiteralPath (Join-Path $root 'diagnostics/queue8-sta/frozen-inputs.json') -Raw | ConvertFrom-Json
$bit=Join-Path $source 'impl/pnr/kagura_fb.fs'
$expected=(Get-FileHash -LiteralPath $bit).Hash.ToLowerInvariant()
$sdc=Join-Path $root 'boards/tang-nano-9k/kagura-fb.sdc'
$netlist=Join-Path $source 'impl/gwsynthesis/kagura_fb.vg'
$logicLines=[Collections.Generic.List[string]]::new()
foreach($line in [IO.File]::ReadAllLines($netlist)) {if(!$line.StartsWith('//')) {$logicLines.Add($line)}}
$logicBytes=[Text.Encoding]::UTF8.GetBytes([string]::Join("`n",$logicLines))
$hasher=[Security.Cryptography.SHA256]::Create()
try {$logicHash=[BitConverter]::ToString($hasher.ComputeHash($logicBytes)).Replace('-','').ToLowerInvariant()} finally {$hasher.Dispose()}
if($logicHash -ne $frozen.mapped_noncomment_verilog_sha256) {throw 'Mapped logic differs from the approved Queue8 design'}
if((Get-FileHash -LiteralPath (Join-Path $source 'kagura_fb.cst')).Hash.ToLowerInvariant() -ne $frozen.cst_sha256) {throw 'Base pin constraints changed'}
if((Get-FileHash -LiteralPath $sdc).Hash.ToLowerInvariant() -ne $frozen.sdc_sha256) {throw 'Clock/timing constraints changed'}
$files=[ordered]@{
    'impl/gwsynthesis/kagura_fb.vg'=(Join-Path $source 'impl/gwsynthesis/kagura_fb.vg')
    'kagura_fb.cst'=(Join-Path $source 'kagura_fb.cst')
    'kagura-fb.sdc'=$sdc
}
$inputHashes=[ordered]@{}
$sourceInputHashes=[ordered]@{}
New-Item -ItemType Directory -Force $output | Out-Null
foreach($entry in $files.GetEnumerator()) {
    $dest=Join-Path $output $entry.Key
    New-Item -ItemType Directory -Force (Split-Path -Parent $dest) | Out-Null
    $inputHashes[$entry.Key]=(Get-FileHash -LiteralPath $entry.Value).Hash.ToLowerInvariant()
    $sourceInputHashes[$entry.Key]=$inputHashes[$entry.Key]
    Copy-Item -LiteralPath $entry.Value -Destination $dest
    if((Get-FileHash -LiteralPath $dest).Hash.ToLowerInvariant() -ne $inputHashes[$entry.Key]) {throw 'Input copy mismatch'}
}
$extraCstHash=$null
if($ExtraCst) {
    $extraPath=[IO.Path]::GetFullPath((Join-Path $root $ExtraCst))
    if(!$extraPath.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {throw 'Use workspace-local extra CST'}
    $extraText=Get-Content -LiteralPath $extraPath -Raw
    foreach($line in ($extraText -split "`r?`n")) {
        $constraint=$line.Trim()
        if(!$constraint -or $constraint.StartsWith('//') -or $constraint.StartsWith('#')) {continue}
        if($constraint -notmatch '^INS_LOC\s+"core/(memory_ctrl|display|cursor)/[^"]+"\s+R\d+C\d+\[[0-3]\]\[[AB]\];$') {throw 'Extra CST is limited to internal memory/display/cursor cell placement'}
    }
    $extraCstHash=(Get-FileHash -LiteralPath $extraPath).Hash.ToLowerInvariant()
    Copy-Item -LiteralPath $extraPath -Destination (Join-Path $output 'extra-placement.cst')
    [IO.File]::AppendAllText((Join-Path $output 'kagura_fb.cst'),"`r`n"+$extraText,[Text.Encoding]::ASCII)
    $inputHashes['kagura_fb.cst']=(Get-FileHash -LiteralPath (Join-Path $output 'kagura_fb.cst')).Hash.ToLowerInvariant()
}
$replicate=[int]$ReplicateResources.IsPresent
$script=@"
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
add_file -type netlist [file join [pwd] impl gwsynthesis kagura_fb.vg]
add_file -type cst [file join [pwd] kagura_fb.cst]
add_file -type sdc [file join [pwd] kagura-fb.sdc]
set_option -top_module kagura_fb_top
set_option -output_base_name kagura_fb
set_option -timing_driven 1
set_option -place_option $PlaceOption
set_option -route_option $RouteOption
set_option -route_maxfan $RouteMaxFan
set_option -replicate_resources $replicate
set_option -retiming_resource none
foreach feature {sspi mspi ready done cpu} { set_option -use_`${feature}_as_gpio 1 }
run pnr
"@
$scriptPath=Join-Path $output 'reroute.tcl'
$script | Set-Content -LiteralPath $scriptPath -Encoding ascii
$record=[ordered]@{depth=8;transport='qspi';place=$PlaceOption;route=$RouteOption;route_maxfan=$RouteMaxFan;reused_mapped_netlist=$true;input_sha256=$inputHashes;source_input_sha256=$sourceInputHashes;extra_cst=$ExtraCst;extra_cst_sha256=$extraCstHash;source_build=$SourceBuild;source_bitstream_sha256=$expected;replicate_resources=$ReplicateResources.IsPresent;fpga_flash_writes=0;fpga_sram_programs=0;release_ready=$false}
$record.mapped_logic_sha256=$logicHash
$record.reference_bitstream_sha256=$frozen.reference_bitstream_sha256
$record | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $output 'plan.json') -Encoding utf8
$started=Get-Date
Push-Location $output
try {
    & $GowinExe $scriptPath 2>&1 | Tee-Object -FilePath build.log
    $record.exit_code=$LASTEXITCODE
    $record.build_failed=$LASTEXITCODE -ne 0 -or (Select-String -LiteralPath build.log -Pattern '^ERROR\s*\(' -Quiet)
    $fresh=Get-Item -LiteralPath 'impl/pnr/kagura_fb.fs' -ErrorAction SilentlyContinue
    $record.fresh_bitstream=$null -ne $fresh -and $fresh.LastWriteTime -ge $started
    $record.timing=$null
    $record.numeric_gate_passed=$false
    if(!$record.build_failed -and $record.fresh_bitstream) {
        & (Join-Path $PSScriptRoot 'check-fb-timing.ps1') -BuildDir $OutputBuild -ReportOnly
        $record.timing=Get-Content timing-status.json -Raw | ConvertFrom-Json
        $record.bitstream_sha256=(Get-FileHash -LiteralPath $fresh.FullName).Hash.ToLowerInvariant()
        $record.numeric_gate_passed=$record.timing.setup_violated_endpoints -eq 0 -and $record.timing.hold_violated_endpoints -eq 0 -and $record.timing.negative_analyses.Count -eq 0 -and $record.timing.worst.Setup.slack_ns -ge 0.10
    }
    foreach($entry in $files.GetEnumerator()) {
        if((Get-FileHash -LiteralPath $entry.Value).Hash.ToLowerInvariant() -ne $sourceInputHashes[$entry.Key]) {throw 'Source input changed during P&R'}
        if((Get-FileHash -LiteralPath (Join-Path $output $entry.Key)).Hash.ToLowerInvariant() -ne $inputHashes[$entry.Key]) {throw 'Mapped input changed during P&R'}
    }
    if($ExtraCst -and (Get-FileHash -LiteralPath $extraPath).Hash.ToLowerInvariant() -ne $extraCstHash) {throw 'Extra placement input changed during P&R'}
    if((Get-FileHash -LiteralPath $bit).Hash.ToLowerInvariant() -ne $expected) {throw 'Approved bitstream changed'}
    $record.elapsed_seconds=[math]::Round(((Get-Date)-$started).TotalSeconds,1)
    $record | ConvertTo-Json -Depth 10 | Set-Content result.json -Encoding utf8
    if($record.build_failed -or !$record.fresh_bitstream) {throw 'Mapped P&R failed; inspect build.log'}
} finally {Pop-Location}
