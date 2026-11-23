# SPDX-License-Identifier: Apache-2.0
param(
    [string]$MicroPython = 'build/midnight-micropython-src',
    [string]$Output = 'build/kagura-runtime/qspi',
    [string]$MpyCross = 'build/midnight-mpy-cross/mpy_cross/mpy-cross.exe',
    [string]$Python = 'python3.12',
    [ValidateSet(1,4)][int]$HostLanes = 4,
    [string]$Picotool = 'build/midnight-hardware/picotool/picotool/picotool.exe',
    [string]$PicoSDK = '',
    [string]$ArmBin = '',
    [string]$CMake = '',
    [string]$Ninja = '',
    [string]$Pioasm = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../../..").Path
$toolRoot = Join-Path $root 'software/midnight_terminal'
$module = Join-Path $root 'software/kagura_runtime'
$source = (Resolve-Path $MicroPython).Path
$cross = (Resolve-Path $MpyCross).Path
$pythonExe = (Get-Command $Python).Source
$cmakeExe = Join-Path $toolRoot '.deps/cmake/data/bin/cmake.exe'
$ninjaExe = Join-Path $toolRoot '.deps/bin/ninja.exe'
if ($CMake) { $cmakeExe = (Resolve-Path $CMake).Path }
if ($Ninja) { $ninjaExe = (Resolve-Path $Ninja).Path }
if (!$PicoSDK) { $PicoSDK = Join-Path $toolRoot 'toolchain/pico-sdk' }
if (!$ArmBin) { $ArmBin = Join-Path $toolRoot 'toolchain/arm/bin' }
if (!$Pioasm) { $Pioasm = Join-Path $toolRoot 'out/pioasm/pioasm.exe' }
$oldToolchain = $env:PICO_TOOLCHAIN_PATH
$oldCross = $env:MICROPY_MPYCROSS
$oldPath = $env:PATH
$oldUtf8 = $env:PYTHONUTF8
try {
    $env:PYTHONUTF8 = '1'
    $env:PICO_TOOLCHAIN_PATH = (Resolve-Path $ArmBin).Path
    $env:MICROPY_MPYCROSS = $cross
    $gitExe = (Get-Command git).Source
    $gitUsr = Join-Path (Split-Path (Split-Path $gitExe)) 'usr/bin'
    if (!(Test-Path (Join-Path $gitUsr 'touch.exe'))) { throw 'Git for Windows usr/bin tools required' }
    $env:PATH = "$gitUsr;$oldPath"
    & $cmakeExe -S "$source/ports/rp2" -B $Output -G Ninja `
        "-DCMAKE_MAKE_PROGRAM=$ninjaExe" '-DCMAKE_BUILD_TYPE=MinSizeRel' `
        '-DCMAKE_C_FLAGS_MINSIZEREL=-Os -DNDEBUG' '-DCMAKE_CXX_FLAGS_MINSIZEREL=-Os -DNDEBUG' `
        "-DPython3_EXECUTABLE=$pythonExe" "-DPICO_SDK_PATH_OVERRIDE=$((Resolve-Path $PicoSDK).Path)" `
        "-DMICROPY_BOARD_DIR=$module/board" "-DUSER_C_MODULES=$module/micropython.cmake" `
        "-DMICROPY_FROZEN_MANIFEST=$module/manifest.py" "-DKAGURA_HOST_LANES=$HostLanes" `
        "-DKAGURA_PIOASM_EXECUTABLE=$((Resolve-Path $Pioasm).Path)" '-DPICO_NO_PICOTOOL=1'
    if ($LASTEXITCODE -ne 0) { throw 'MicroPython configure failed' }
    & $pythonExe "$module/windows_batch.py" $Output
    if ($LASTEXITCODE -ne 0) { throw 'Windows command preparation failed' }
    & $cmakeExe --build $Output --parallel 4
    if ($LASTEXITCODE -ne 0) { throw 'MicroPython build failed' }
    if ((Get-Item "$Output/firmware.bin").Length -gt 655360) { throw 'Firmware overlaps standard Pico filesystem' }
    & $Picotool uf2 convert "$Output/firmware.elf" "$Output/kagura-micropython.uf2" --family rp2040
    if ($LASTEXITCODE -ne 0) { throw 'UF2 conversion failed' }
    Get-FileHash "$Output/kagura-micropython.uf2"
} finally {
    $env:PICO_TOOLCHAIN_PATH = $oldToolchain
    $env:MICROPY_MPYCROSS = $oldCross
    $env:PATH = $oldPath
    $env:PYTHONUTF8 = $oldUtf8
}
