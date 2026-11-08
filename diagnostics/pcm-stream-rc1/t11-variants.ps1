# SPDX-License-Identifier: Apache-2.0
# T11 (design-audit-report.md section 16.5): placement variants of the
# unchanged A RTL. (a) P&R-only options on A's netlist; (b) re-synthesis of the
# identical A inputs with another opt_goal. Product RTL/SDC/CST untouched.
param([string]$Gowin = 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$A = Join-Path $root 'build/pcm-stream-rc1/sta-short-control'
$out = Join-Path $root 'build/pcm-stream-rc1/t11-a'
New-Item -ItemType Directory -Force $out | Out-Null
$baseSums = Get-Content (Join-Path $PSScriptRoot 'design-audit/t8-base-inputs.sha256')
function Check-Timing($dir) {
    & "$root/tools/check-fb-timing.ps1" -BuildDir ([IO.Path]::GetRelativePath($root, $dir)) -ReportOnly | Out-Null
    $j = Get-Content (Join-Path $dir 'timing-status.json') -Raw | ConvertFrom-Json
    "{0} setupViol={1} holdViol={2} wns={3} whs={4} worst={5}" -f ([IO.Path]::GetFileName($dir)), $j.setup_violated_endpoints, $j.hold_violated_endpoints, $j.worst.Setup.slack_ns, $j.worst.Hold.slack_ns, $j.worst.Setup.to
}
function Run-Pnr($dir, $netlist, $place, $route, $maxfan, $extra) {
    New-Item -ItemType Directory $dir | Out-Null
    Copy-Item $netlist "$dir/kagura_fb.vg"
    Copy-Item "$A/native/kagura_fb.cst" "$dir/kagura_fb.cst"
    Copy-Item "$A/inputs/boards/tang-nano-9k/kagura-fb.sdc" "$dir/kagura-fb.sdc"
    [ordered]@{ 'kagura_fb.vg' = (Get-FileHash "$dir/kagura_fb.vg").Hash; 'kagura_fb.cst' = (Get-FileHash "$dir/kagura_fb.cst").Hash; 'kagura-fb.sdc' = (Get-FileHash "$dir/kagura-fb.sdc").Hash } |
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
    if (!(Test-Path "$dir/impl/pnr/kagura_fb.tr")) { return "$([IO.Path]::GetFileName($dir)) P&R failed" }
    Check-Timing $dir
}
# (a) P&R-only on A's netlist.
$aNet = "$A/native/impl/gwsynthesis/kagura_fb.vg"
if (!(Test-Path "$out/pnr-replicate1")) { Run-Pnr "$out/pnr-replicate1" $aNet 4 2 23 'set_option -replicate_resources 1' }
if (!(Test-Path "$out/pnr-clockorder1")) { Run-Pnr "$out/pnr-clockorder1" $aNet 4 2 23 'set_option -clock_route_order 1' }
# (b) Re-synthesis of identical A inputs.
foreach ($goal in 'timing', 'area') {
    # syn-timing/ holds an aborted first attempt (input check format); left in place.
    $dir = "$out/syn2-$goal"
    New-Item -ItemType Directory -Force "$dir/native" | Out-Null
    if (!(Test-Path "$dir/inputs")) { Copy-Item "$A/inputs" "$dir/inputs" -Recurse }
    # Compare every copied file with design-audit/t8-base-inputs.sha256 (A inputs).
    $expected = @{}
    foreach ($line in $baseSums) { $h, $f = $line -split ' \*', 2; $expected[$f] = $h.ToLower() }
    $actual = @{}
    Get-ChildItem "$dir/inputs" -Recurse -File | ForEach-Object {
        $rel = './' + [IO.Path]::GetRelativePath("$dir/inputs", $_.FullName).Replace([char]92, [char]47)
        $actual[$rel] = (Get-FileHash $_.FullName).Hash.ToLower()
    }
    if ($actual.Count -ne $expected.Count -or @($expected.Keys | Where-Object { $actual[$_] -ne $expected[$_] }).Count) {
        throw "Copied inputs differ from A: $goal"
    }
    Push-Location "$dir/native"
    try { & $Gowin "$dir/inputs/tools/build-fb.tcl" qspi 4 2 8 0 1 $goal *> build.log } finally { Pop-Location }
    if (!(Test-Path "$dir/native/impl/pnr/kagura_fb.fs")) { "syn2-$goal build failed"; continue }
    Check-Timing "$dir/native"
    Run-Pnr "$dir/p3-r2-f23" "$dir/native/impl/gwsynthesis/kagura_fb.vg" 3 2 23 ''
}
