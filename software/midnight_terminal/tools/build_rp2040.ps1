# SPDX-License-Identifier: Apache-2.0
param(
    [string]$Output = 'build/midnight-terminal/rp2040'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot/../../..").Path
$src = (Resolve-Path "$PSScriptRoot/..").Path
$mt = Join-Path $root 'software/midnight_terminal'
$env:PICO_SDK_PATH = "$mt/toolchain/pico-sdk"
$gcc = Get-ChildItem "$mt/toolchain/arm" -Recurse -Filter arm-none-eabi-gcc.exe | Select-Object -First 1
if (!$gcc) { throw 'RP2040 Arm toolchain missing' }
$env:PICO_TOOLCHAIN_PATH = $gcc.DirectoryName
$cmake = "$mt/.deps/cmake/data/bin/cmake.exe"
$ninja = "$mt/.deps/bin/ninja.exe"
& $cmake -S $src -B $Output -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" -DPICO_BOARD=pico -DPICO_NO_PICOTOOL=1 -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE -ne 0) { throw 'Configure failed' }
& $cmake --build $Output --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
& "$($gcc.DirectoryName)/arm-none-eabi-size.exe" "$Output/midnight_terminal.elf"
if ($LASTEXITCODE -ne 0) { throw 'ELF size check failed' }
$elf = Join-Path $Output 'midnight_terminal.elf'
Get-FileHash $elf | Format-List Algorithm,Hash,Path
