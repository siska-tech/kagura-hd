# SPDX-License-Identifier: Apache-2.0
# Search for an STA-clean implementation of an existing trial without changing
# its RTL, SDC or CST: (a) P&R options on the trial's netlist, (b) re-synthesis
# of the trial's own inputs (hash-checked copy) with another opt_goal.
# Generalises t11-variants.ps1. Prints one line per variant.
param(
    [Parameter(Mandatory)][string]$Trial,           # e.g. build/pcm-stream-rc1/word-select
    [string]$Gowin = 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$T = (Resolve-Path (Join-Path $root $Trial)).Path
if (!$T.StartsWith((Join-Path $root 'build'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Use a trial under build/' }
$out = Join-Path $T 'sweep'
New-Item -ItemType Directory -Force $out | Out-Null
$frozenSdc = Join-Path $root 'releases/queue8-qspi-deglitch-rc1/build-inputs/boards/tang-nano-9k/kagura-fb.sdc'
if ((Get-FileHash $frozenSdc).Hash -ne (Get-FileHash "$T/inputs/boards/tang-nano-9k/kagura-fb.sdc").Hash) { throw 'RC1 SDC mismatch' }
function Tree-Hashes($dir) {
    $h = @{}
    Get-ChildItem $dir -Recurse -File | ForEach-Object {
        $h[[IO.Path]::GetRelativePath($dir, $_.FullName).Replace([char]92, [char]47)] = (Get-FileHash $_.FullName).Hash
    }
    $h
}
function Check-Timing($dir, $name) {
    & "$root/tools/check-fb-timing.ps1" -BuildDir ([IO.Path]::GetRelativePath($root, $dir)) -ReportOnly | Out-Null
    $j = Get-Content (Join-Path $dir 'timing-status.json') -Raw | ConvertFrom-Json
    "{0} setupViol={1} holdViol={2} wns={3} whs={4} worst={5}" -f $name, $j.setup_violated_endpoints, $j.hold_violated_endpoints, $j.worst.Setup.slack_ns, $j.worst.Hold.slack_ns, $j.worst.Setup.to
}
function Run-Pnr($name, $netlist, $place, $route, $maxfan, $extra) {
    $dir = Join-Path $out $name
    if (Test-Path $dir) { return "$name exists, skipped" }
    New-Item -ItemType Directory $dir | Out-Null
    Copy-Item $netlist "$dir/kagura_fb.vg"
    Copy-Item "$T/native/kagura_fb.cst" "$dir/kagura_fb.cst"
    Copy-Item "$T/inputs/boards/tang-nano-9k/kagura-fb.sdc" "$dir/kagura-fb.sdc"
    [ordered]@{ 'kagura_fb.vg' = (Get-FileHash "$dir/kagura_fb.vg").Hash; 'kagura_fb.cst' = (Get-FileHash "$dir/kagura_fb.cst").Hash; 'kagura-fb.sdc' = (Get-FileHash "$dir/kagura-fb.sdc").Hash; options = "p$place r$route f$maxfan $extra" } |
        ConvertTo-Json | Set-Content "$dir/input-sha256.json"
    @"
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
add_file -type netlist [file join [pwd] kagura_fb.vg]
add_file -type cst [file join [pwd] kagura_fb.cst]
add_file -type sdc [file join [pwd] kagura-fb.sdc]
set_option -top_module kagura_fb_top
set_option -output_base_name kagura_fb
set_option -timing_driven 1
set_option -place_option $place
set_option -route_option $route
set_option -route_maxfan $maxfan
set_option -replicate_resources 0
set_option -retiming_resource none
$extra
foreach feature {sspi mspi ready done cpu} { set_option -use_`${feature}_as_gpio 1 }
run pnr
"@ | Set-Content "$dir/reroute.tcl" -Encoding ascii
    Push-Location $dir
    try { & $Gowin reroute.tcl *> build.log } finally { Pop-Location }
    if (!(Test-Path "$dir/impl/pnr/kagura_fb.tr")) { return "$name P&R failed" }
    Check-Timing $dir $name
}
$net = "$T/native/impl/gwsynthesis/kagura_fb.vg"
foreach ($c in @(@(4,2,18),@(4,2,20),@(4,2,22),@(4,2,28),@(4,2,30),@(3,2,18),@(3,2,20),@(3,2,30))) {
    Run-Pnr ("p{0}-r{1}-f{2}" -f $c) $net $c[0] $c[1] $c[2] ''
}
Run-Pnr 'p4-r2-f23-replicate1' $net 4 2 23 'set_option -replicate_resources 1'
Run-Pnr 'p4-r2-f23-clockorder1' $net 4 2 23 'set_option -clock_route_order 1'
Run-Pnr 'p3-r2-f23-replicate1' $net 3 2 23 'set_option -replicate_resources 1'
$reference = Tree-Hashes "$T/inputs"
foreach ($goal in 'area', 'timing') {
    $dir = Join-Path $out "syn-$goal"
    if (Test-Path $dir) { "syn-$goal exists, skipped"; continue }
    New-Item -ItemType Directory "$dir/native" | Out-Null
    Copy-Item "$T/inputs" "$dir/inputs" -Recurse
    $copy = Tree-Hashes "$dir/inputs"
    if ($copy.Count -ne $reference.Count -or @($reference.Keys | Where-Object { $copy[$_] -ne $reference[$_] }).Count) { throw "Copied inputs differ: $goal" }
    Push-Location "$dir/native"
    try { & $Gowin "$dir/inputs/tools/build-fb.tcl" qspi 4 2 8 0 1 $goal *> build.log } finally { Pop-Location }
    if (!(Test-Path "$dir/native/impl/pnr/kagura_fb.tr")) { "syn-$goal p4-r2 P&R failed" } else { Check-Timing "$dir/native" "syn-$goal-p4-r2" }
    if (Test-Path "$dir/native/impl/gwsynthesis/kagura_fb.vg") {
        Run-Pnr "syn-$goal-p3-r2-f23" "$dir/native/impl/gwsynthesis/kagura_fb.vg" 3 2 23 ''
    }
}
