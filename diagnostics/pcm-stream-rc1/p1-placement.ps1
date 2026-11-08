# SPDX-License-Identifier: Apache-2.0
# P1 (design-audit-report.md section 19): place the product-equivalent netlist
# (build/pcm-stream-rc1/word-select) with the hard-block positions taken from
# the STA-clean T8 implementation (t8-di-local/sta-p3-r2-f23), reproduced with
# -gen_posp in p1-placement/t8-posp. RTL and SDC are unchanged; only INS_LOC
# lines are appended to a copy of the trial CST. Diagnostic output only.
param(
    [string]$Gowin = 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$base = Join-Path $root 'build/pcm-stream-rc1'
$out = Join-Path $base 'p1-placement'
$posp = Join-Path $out 't8-posp/impl/pnr/kagura_fb.posp'
$net = Join-Path $base 'word-select/native/impl/gwsynthesis/kagura_fb.vg'
$cst = Join-Path $base 'word-select/native/kagura_fb.cst'
$sdc = Join-Path $base 'word-select/inputs/boards/tang-nano-9k/kagura-fb.sdc'
$frozenSdc = Join-Path $root 'releases/queue8-qspi-deglitch-rc1/build-inputs/boards/tang-nano-9k/kagura-fb.sdc'
if ((Get-FileHash $frozenSdc).Hash -ne (Get-FileHash $sdc).Hash) { throw 'RC1 SDC mismatch' }

# Hard-block INS_LOC lines from the T8 post-place file.
$locs = foreach ($line in Get-Content $posp) {
    if ($line -match '^(\S+)\s+PLACE_(\S+)') { 'INS_LOC "{0}" {1};' -f $Matches[1], $Matches[2] }
}
if ($locs.Count -ne 25) { throw "Expected 25 hard blocks, got $($locs.Count)" }
$locs | Set-Content (Join-Path $out 'hard-block-loc.cst') -Encoding ascii

function Check-Timing($dir, $name) {
    & "$root/tools/check-fb-timing.ps1" -BuildDir ([IO.Path]::GetRelativePath($root, $dir)) -ReportOnly | Out-Null
    $j = Get-Content (Join-Path $dir 'timing-status.json') -Raw | ConvertFrom-Json
    "{0} setupViol={1} holdViol={2} wns={3} whs={4} worst={5}" -f $name, $j.setup_violated_endpoints, $j.hold_violated_endpoints, $j.worst.Setup.slack_ns, $j.worst.Hold.slack_ns, $j.worst.Setup.to
}
function Run-Pnr($name, $place, $route, $maxfan, $extraCst) {
    $dir = Join-Path $out $name
    if (Test-Path $dir) { return "$name exists, skipped" }
    New-Item -ItemType Directory $dir | Out-Null
    Copy-Item $net "$dir/kagura_fb.vg"
    Copy-Item $sdc "$dir/kagura-fb.sdc"
    (Get-Content $cst) + '' + '// P1 diagnostic placement (hard blocks from T8 sta-p3-r2-f23)' + $extraCst |
        Set-Content "$dir/kagura_fb.cst" -Encoding ascii
    [ordered]@{ 'kagura_fb.vg' = (Get-FileHash "$dir/kagura_fb.vg").Hash; 'base_cst' = (Get-FileHash $cst).Hash
        'kagura_fb.cst' = (Get-FileHash "$dir/kagura_fb.cst").Hash; 'kagura-fb.sdc' = (Get-FileHash "$dir/kagura-fb.sdc").Hash
        't8_posp' = (Get-FileHash $posp).Hash; options = "p$place r$route f$maxfan" } |
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
set_option -gen_posp 1
foreach feature {sspi mspi ready done cpu} { set_option -use_`${feature}_as_gpio 1 }
run pnr
"@ | Set-Content "$dir/reroute.tcl" -Encoding ascii
    Push-Location $dir
    try { & $Gowin reroute.tcl *> build.log } finally { Pop-Location }
    if (!(Test-Path "$dir/impl/pnr/kagura_fb.tr")) { return "$name P&R failed" }
    Check-Timing $dir $name
}
# All 25 hard blocks: every variant left unrouted nets (218 / 408).
foreach ($c in @(@(3,2,23),@(4,2,23),@(3,2,26),@(4,2,26),@(3,2,30))) {
    Run-Pnr ("hb-p{0}-r{1}-f{2}" -f $c) $c[0] $c[1] $c[2] $locs
}
# Subsets: the 16 upload-window BSRAMs alone, then with the 4 descriptor BSRAMs.
$win = @($locs | Where-Object { $_ -match 'upload_words' })
$winDesc = @($locs | Where-Object { $_ -match 'upload_words|descriptors' })
foreach ($c in @(@(3,2,23),@(4,2,23))) {
    Run-Pnr ("win-p{0}-r{1}-f{2}" -f $c) $c[0] $c[1] $c[2] $win
    Run-Pnr ("windesc-p{0}-r{1}-f{2}" -f $c) $c[0] $c[1] $c[2] $winDesc
}
