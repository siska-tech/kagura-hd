# SPDX-License-Identifier: Apache-2.0
# Rebuild the SPI release bitstream from build-inputs and compare it with the
# frozen artifact. Read-only for this package; writes only under -Output (must
# be under build/ and must not exist). One stage:
#   tools/build-fb.tcl spi 4 2 8 0 1 auto (synthesis + P&R place 4 / route 2,
#   Queue8, PACKET_FIRST; the rtl/spi/ overlay replaces the same-named files)
#   -> netlist body SHA-256 (header comments excluded) must equal the frozen value
#   -> .bin must equal the frozen .bin; .fs equal except the "//Created Time" line
#   -> numeric STA gate rechecked (setup >= +0.100 ns, 0/0 violations)
param(
    [string]$Output = 'build/pcm-stream-spi-repro',
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
New-Item -ItemType Directory "$out/native" | Out-Null
Copy-Item "$pkg/build-inputs" "$out/inputs" -Recurse
foreach ($k in $manifest.Keys) { if ((Get-FileHash "$out/inputs/$k").Hash -ne $manifest[$k].ToUpper()) { throw "Copied input mismatch: $k" } }
$gw = (Resolve-Path $Gowin).Path
Push-Location "$out/native"
try { & $gw "$out/inputs/tools/build-fb.tcl" spi 4 2 8 0 1 auto *> build.log } finally { Pop-Location }
$net = "$out/native/impl/gwsynthesis/kagura_fb.vg"
$fs = "$out/native/impl/pnr/kagura_fb.fs"
if (!(Test-Path $net) -or !(Test-Path $fs)) { throw 'Synthesis or P&R failed' }
if ((Select-String -Path "$out/native/build.log" -Pattern 'KAGURA_SPI_OVERLAY').Count -ne 4) { throw 'Expected four rtl/spi overlay substitutions' }
$frozen = Get-Content -Raw "$pkg/manifest.json" | ConvertFrom-Json
$result = [ordered]@{}
$body = (@(Get-Content $net | Where-Object { $_ -notmatch '^//' }) -join "`n") + "`n"
$sha = [Security.Cryptography.SHA256]::Create()
$result.netlist_body_sha256 = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($body))) -replace '-','').ToLower()
$result.netlist_equal = $result.netlist_body_sha256 -eq $frozen.netlist_body_sha256
$result.bin_equal = (Get-FileHash "$out/native/impl/pnr/kagura_fb.bin").Hash.ToLower() -eq $frozen.bin_sha256
$a = @(Get-Content $fs | Where-Object { $_ -notmatch '^//Created Time' })
$b = @(Get-Content (Join-Path $pkg $frozen.artifact) | Where-Object { $_ -notmatch '^//Created Time' })
$result.fs_equal_except_created_time = ($a.Count -eq $b.Count) -and !(Compare-Object $a $b -SyncWindow 0)
$result.fs_sha256 = (Get-FileHash $fs).Hash.ToLower()
& "$root/tools/check-fb-timing.ps1" -BuildDir ([IO.Path]::GetRelativePath($root, "$out/native")) -ReportOnly | Out-Null
$t = Get-Content "$out/native/timing-status.json" -Raw | ConvertFrom-Json
$result.setup_wns_ns = $t.worst.Setup.slack_ns
$result.hold_wns_ns = $t.worst.Hold.slack_ns
$result.violations = @($t.setup_violated_endpoints, $t.hold_violated_endpoints)
$result.reproduced = $result.netlist_equal -and $result.bin_equal -and $result.fs_equal_except_created_time -and
    $t.setup_violated_endpoints -eq 0 -and $t.hold_violated_endpoints -eq 0 -and $t.worst.Setup.slack_ns -ge 0.10
$result | ConvertTo-Json | Tee-Object "$out/reproduce-result.json"
if (!$result.reproduced) { exit 1 }
