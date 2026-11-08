# SPDX-License-Identifier: Apache-2.0
# Rebuild the frozen T8 candidate from build-inputs and compare with the
# frozen artifacts (../../diagnostics/pcm-stream-rc1/design-audit-report.md section 20.3). Read-only for this
# package; writes only under -Output (must be under build/ and must not exist).
#   stage 1  synthesis + P&R p4/r2 (tools/build-fb.tcl qspi 4 2 8 0 1 auto)
#            -> netlist body SHA-256 must equal the frozen value (header comments excluded)
#   stage 2  P&R of the stage-1 netlist with pnr/reroute.tcl (p3 r2 f23)
#            -> .bin must equal the frozen .bin; .fs equal except the
#               "//Created Time" comment line; numeric STA gate rechecked
param(
    [string]$Output = 'build/pcm-stream-qspi-repro',
    [string]$Gowin = 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe'
)
$ErrorActionPreference = 'Stop'
$pkg = $PSScriptRoot
$root = (Resolve-Path "$pkg/../..").Path
$out = Join-Path $root $Output
if (!$out.StartsWith((Join-Path $root 'build'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must be under build/' }
if (Test-Path $out) { throw "Output already exists: $out" }
function Check-Sums($file, $base) {
    foreach ($line in Get-Content $file) {
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { throw "Bad line: $line" }
        if ((Get-FileHash (Join-Path $base $Matches[2])).Hash -ne $Matches[1].ToUpper()) { throw "Hash mismatch: $($Matches[2])" }
    }
}
Check-Sums "$pkg/SHA256SUMS" $pkg
$manifest = Get-Content -Raw "$pkg/source-input-manifest.json" | ConvertFrom-Json -AsHashtable
$files = @(Get-ChildItem "$pkg/build-inputs" -Recurse -File)
if ($files.Count -ne $manifest.Count) { throw 'build-inputs file count differs from manifest' }
New-Item -ItemType Directory "$out/native", "$out/pnr" | Out-Null
Copy-Item "$pkg/build-inputs" "$out/inputs" -Recurse
foreach ($k in $manifest.Keys) { if ((Get-FileHash "$out/inputs/$k").Hash -ne $manifest[$k].ToUpper()) { throw "Copied input mismatch: $k" } }
$gw = (Resolve-Path $Gowin).Path
Push-Location "$out/native"
try { & $gw "$out/inputs/tools/build-fb.tcl" qspi 4 2 8 0 1 auto *> build.log } finally { Pop-Location }
$net = "$out/native/impl/gwsynthesis/kagura_fb.vg"
if (!(Test-Path $net)) { throw 'Synthesis failed' }
$result = [ordered]@{}
# The netlist header comments carry the synthesis time and absolute source
# paths; compare everything else.
# The 2.6 MB netlist is not shipped; compare the SHA-256 of its body (lines not
# starting with "//", LF-joined, trailing LF) with the frozen value.
$body = (@(Get-Content $net | Where-Object { $_ -notmatch '^//' }) -join "`n") + "`n"
$sha = [Security.Cryptography.SHA256]::Create()
$result.netlist_body_sha256 = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($body))) -replace '-','').ToLower()
$result.netlist_equal = $result.netlist_body_sha256 -eq '79434504365e9baf1b6b76e24c53b2c900e9a68121d854d6ce1f6cecf3ce7a33'
$result.native_cst_equal = (Get-FileHash "$out/native/kagura_fb.cst").Hash -eq (Get-FileHash "$pkg/pnr/kagura_fb.cst").Hash
Copy-Item $net "$out/pnr/kagura_fb.vg"
Copy-Item "$out/native/kagura_fb.cst" "$out/pnr/kagura_fb.cst"
Copy-Item "$out/inputs/boards/tang-nano-9k/kagura-fb.sdc" "$out/pnr/kagura-fb.sdc"
Copy-Item "$pkg/pnr/reroute.tcl" "$out/pnr/reroute.tcl"
Push-Location "$out/pnr"
try { & $gw reroute.tcl *> build.log } finally { Pop-Location }
$fs = "$out/pnr/impl/pnr/kagura_fb.fs"
if (!(Test-Path $fs)) { throw 'P&R failed' }
$result.bin_equal = (Get-FileHash "$out/pnr/impl/pnr/kagura_fb.bin").Hash -eq '40E37294D47265DD2AED708F9099B2DB001A83C4578279892311DE0E7A0D91AE'
$a = @(Get-Content $fs | Where-Object { $_ -notmatch '^//Created Time' })
$b = @(Get-Content "$root/artifacts/validated/kagura-hd-qspi-pcm-stream.fs" | Where-Object { $_ -notmatch '^//Created Time' })
$result.fs_equal_except_created_time = ($a.Count -eq $b.Count) -and !(Compare-Object $a $b -SyncWindow 0)
$result.fs_sha256 = (Get-FileHash $fs).Hash.ToLower()
& "$root/tools/check-fb-timing.ps1" -BuildDir ([IO.Path]::GetRelativePath($root, "$out/pnr")) -ReportOnly | Out-Null
$t = Get-Content "$out/pnr/timing-status.json" -Raw | ConvertFrom-Json
$result.setup_wns_ns = $t.worst.Setup.slack_ns
$result.hold_wns_ns = $t.worst.Hold.slack_ns
$result.violations = @($t.setup_violated_endpoints, $t.hold_violated_endpoints)
$result.reproduced = $result.netlist_equal -and $result.bin_equal -and $result.fs_equal_except_created_time -and
    $t.setup_violated_endpoints -eq 0 -and $t.hold_violated_endpoints -eq 0
$result | ConvertTo-Json | Tee-Object "$out/reproduce-result.json"
if (!$result.reproduced) { exit 1 }
