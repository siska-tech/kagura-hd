# SPDX-License-Identifier: Apache-2.0
param(
    [ValidateRange(0,4)][int]$Place = 4,
    [ValidateRange(0,2)][int]$Route = 2,
    [ValidateRange(1,100)][int]$MaxFan = 23,
    [string]$SourceTrial = 'build/pcm-stream-rc1',
    [string]$PalettePlacement,
    [string]$Gowin = 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$trial = [IO.Path]::GetFullPath((Join-Path $root $SourceTrial))
$buildRoot = (Join-Path $root 'build') + [IO.Path]::DirectorySeparatorChar
if (!$trial.StartsWith($buildRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Use a trial under build/' }
$suffix = ''
if ($PalettePlacement) {
    $placementPath = (Resolve-Path -LiteralPath $PalettePlacement).Path
    $placementLines = @(Get-Content -LiteralPath $placementPath | Where-Object { $_.Trim() })
    $pointPattern = '^INS_LOC "core/display/(held_)?palette_(11|77|89|125|181|184)_s0" R\d+C\d+\[[0-3]\]\[[AB]\];$'
    $regionPattern = '^INS_LOC "core/display/(held_)?palette_(81|18[0-9]|19[01])_s0" R\[\d+:\d+\]C\[\d+:\d+\];$'
    if (!$placementLines -or @($placementLines | Where-Object { $_ -cnotmatch $pointPattern -and $_ -cnotmatch $regionPattern }).Count) {
        throw 'Placement must constrain measured critical palette bits or the color containing bit 181'
    }
    $suffix = '-' + [IO.Path]::GetFileNameWithoutExtension($placementPath)
}
$relative = [IO.Path]::GetRelativePath($root, (Join-Path $trial "sta-p$Place-r$Route-f$MaxFan$suffix"))
$output = Join-Path $root $relative
if (Test-Path -LiteralPath $output) { throw "Output already exists: $output" }
$inputs = [ordered]@{
    'kagura_fb.vg' = "$trial/native/impl/gwsynthesis/kagura_fb.vg"
    'kagura_fb.cst' = "$trial/native/kagura_fb.cst"
    'kagura-fb.sdc' = "$trial/inputs/boards/tang-nano-9k/kagura-fb.sdc"
}
$frozenSdc = Join-Path $root 'releases/queue8-qspi-deglitch-rc1/build-inputs/boards/tang-nano-9k/kagura-fb.sdc'
if ((Get-FileHash $frozenSdc).Hash -ne (Get-FileHash $inputs['kagura-fb.sdc']).Hash) { throw 'RC1 SDC mismatch' }
$gowinPath = (Resolve-Path -LiteralPath $Gowin).Path
New-Item -ItemType Directory $output | Out-Null
$hashes = [ordered]@{}
foreach ($file in $inputs.Keys) {
    $hashes[$file] = (Get-FileHash -LiteralPath $inputs[$file]).Hash
    Copy-Item -LiteralPath $inputs[$file] -Destination "$output/$file"
}
$hashes | ConvertTo-Json | Set-Content "$output/input-sha256.json"
$routedCstHash = $hashes['kagura_fb.cst']
if ($PalettePlacement) {
    Copy-Item -LiteralPath $placementPath -Destination "$output/palette-placement.cst"
    [IO.File]::AppendAllText("$output/kagura_fb.cst", "`n" + ($placementLines -join "`n") + "`n", [Text.Encoding]::ASCII)
    $routedCstHash = (Get-FileHash -LiteralPath "$output/kagura_fb.cst").Hash
    [ordered]@{ placement_sha256 = (Get-FileHash -LiteralPath "$output/palette-placement.cst").Hash; combined_cst_sha256 = $routedCstHash } |
        ConvertTo-Json | Set-Content "$output/placement-sha256.json"
}
@"
set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
add_file -type netlist [file join [pwd] kagura_fb.vg]
add_file -type cst [file join [pwd] kagura_fb.cst]
add_file -type sdc [file join [pwd] kagura-fb.sdc]
set_option -top_module kagura_fb_top
set_option -output_base_name kagura_fb
set_option -timing_driven 1
set_option -place_option $Place
set_option -route_option $Route
set_option -route_maxfan $MaxFan
set_option -replicate_resources 0
set_option -retiming_resource none
foreach feature {sspi mspi ready done cpu} { set_option -use_`${feature}_as_gpio 1 }
run pnr
"@ | Set-Content "$output/reroute.tcl" -Encoding ascii
Push-Location $output
try {
    & $gowinPath reroute.tcl *> build.log
    if ($LASTEXITCODE -ne 0 -or !(Test-Path 'impl/pnr/kagura_fb.tr')) { throw "P&R failed. See $output/build.log" }
    foreach ($file in $inputs.Keys) {
        $expected = if ($file -eq 'kagura_fb.cst') { $routedCstHash } else { $hashes[$file] }
        if ((Get-FileHash -LiteralPath $file).Hash -ne $expected -or (Get-FileHash -LiteralPath $inputs[$file]).Hash -ne $hashes[$file]) {
            throw "P&R input changed: $file"
        }
    }
    & "$root/tools/check-fb-timing.ps1" -BuildDir $relative -ReportOnly
} finally { Pop-Location }
