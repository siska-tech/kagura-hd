# SPDX-License-Identifier: Apache-2.0
param(
    [string]$Output = 'build/pcm-stream-rc1-repro',
    [string]$Gowin = 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe',
    [switch]$RegisterTxControl,
    [switch]$LocalWindowSelect,
    [switch]$ShortControlPaths,
    [switch]$PresentRxStage,
    [switch]$FillEndAdder,
    [switch]$GenerationCarry,
    [switch]$WindowCommitMerge,
    [switch]$PaletteRam,
    [switch]$WindowWordSelect
)
$ErrorActionPreference = 'Stop'
if ($ShortControlPaths -and !$RegisterTxControl) { throw 'ShortControlPaths requires RegisterTxControl' }
if ($WindowCommitMerge -and !$LocalWindowSelect) { throw 'WindowCommitMerge requires LocalWindowSelect' }
if ($WindowWordSelect -and !$LocalWindowSelect) { throw 'WindowWordSelect requires LocalWindowSelect' }
$root = (Resolve-Path "$PSScriptRoot/../..").Path
$release = Join-Path $root 'releases/queue8-qspi-deglitch-rc1'
$baseline = Join-Path $release 'build-inputs'
$outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
if (Test-Path -LiteralPath $outputPath) { throw "Output already exists: $outputPath" }
$manifest = Get-Content -Raw "$release/source-input-manifest.json" | ConvertFrom-Json -AsHashtable
foreach ($file in $manifest.Keys) {
    if ((Get-FileHash -LiteralPath (Join-Path $baseline $file)).Hash -ne $manifest[$file]) {
        throw "RC1 input hash mismatch: $file"
    }
}
$gowinPath = (Resolve-Path -LiteralPath $Gowin).Path
New-Item -ItemType Directory -Path $outputPath | Out-Null
$inputs = Join-Path $outputPath 'inputs'
$native = Join-Path $outputPath 'native'
Copy-Item -LiteralPath $baseline -Destination $inputs -Recurse
New-Item -ItemType Directory -Path $native | Out-Null
Push-Location $inputs
try {
    git apply --check "$PSScriptRoot/stream.patch"
    if ($LASTEXITCODE -ne 0) { throw 'Patch check failed' }
    git apply "$PSScriptRoot/stream.patch"
    if ($LASTEXITCODE -ne 0) { throw 'Patch application failed' }
    if (-not (Select-String -Quiet -SimpleMatch 'g_stream' 'rtl/audio/kagura_pcm_prefetch.sv')) {
        throw 'Patch was skipped by git apply'
    }
    if ($RegisterTxControl) {
        git apply "$PSScriptRoot/tx-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch 'reg tx_load,tx_shift' 'rtl/fb/kagura_fb_burst_ctrl.sv')) {
            throw 'TX control patch application failed'
        }
    }
    if ($LocalWindowSelect) {
        git apply "$PSScriptRoot/window-sta.patch"
        if ($LASTEXITCODE -ne 0) { throw 'Window select patch application failed' }
    }
    if ($ShortControlPaths) {
        git apply "$PSScriptRoot/control-sta.patch"
        if ($LASTEXITCODE -ne 0) { throw 'Short control paths patch application failed' }
    }
    if ($PresentRxStage) {
        git apply --ignore-space-change --recount "$PSScriptRoot/present-rx-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch 'reg [192:0] present_rx' 'rtl/fb/kagura_fb_scanout.sv')) {
            throw 'PRESENT receive stage patch application failed'
        }
    }
    if ($FillEndAdder) {
        git apply --ignore-space-change "$PSScriptRoot/fill-end-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch 'wire [9:0] rounded_end' 'rtl/fb/kagura_fb_fill_burst.sv')) {
            throw 'FILL end adder patch application failed'
        }
    }
    if ($GenerationCarry) {
        git apply --ignore-space-change "$PSScriptRoot/generation-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch 'reg generation_carry' 'rtl/fb/kagura_fb_scanout.sv')) {
            throw 'Generation carry patch application failed'
        }
    }
    if ($WindowCommitMerge) {
        git apply --ignore-space-change "$PSScriptRoot/window-merge-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch 'reg [7:0] window_write_byte' 'rtl/fb/kagura_fb_registers.sv')) {
            throw 'Window commit merge patch application failed'
        }
    }
    if ($PaletteRam) {
        git apply --ignore-space-change "$PSScriptRoot/palette-ram-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch 'palette_write_addr' 'rtl/fb/kagura_fb_scanout.sv')) {
            throw 'Palette RAM patch application failed'
        }
    }
    if ($WindowWordSelect) {
        git apply --ignore-space-change "$PSScriptRoot/window-word-sta.patch"
        if ($LASTEXITCODE -ne 0 -or -not (Select-String -Quiet -SimpleMatch "data_addr[5:2]==4'(word)" 'rtl/fb/kagura_fb_registers.sv')) {
            throw 'Window word select patch application failed'
        }
    }
} finally { Pop-Location }
Push-Location $native
try {
    & $gowinPath "$inputs/tools/build-fb.tcl" qspi 4 2 8 0 1 auto *> build.log
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path 'impl/pnr/kagura_fb.fs')) {
        throw "Gowin build failed. See $native/build.log"
    }
} finally { Pop-Location }
$timingDir = [IO.Path]::GetRelativePath($root, $native)
& "$root/tools/check-fb-timing.ps1" -BuildDir $timingDir
