# SPDX-License-Identifier: Apache-2.0
param(
    [string]$Output = 'build/fm-megademo/rp2040'
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
& "$($gcc.DirectoryName)/arm-none-eabi-size.exe" "$Output/four_operators.elf"
if ($LASTEXITCODE -ne 0) { throw 'ELF size check failed' }
$elf = Join-Path $Output 'four_operators.elf'
$headers = & "$($gcc.DirectoryName)/arm-none-eabi-readelf.exe" -lW $elf
if ($LASTEXITCODE -ne 0) { throw 'ELF header check failed' }
$segments = @($headers | Where-Object { $_ -match '^\s+LOAD\s' })
if ($segments.Count -eq 0) { throw 'No ELF load segments' }
foreach ($segment in $segments) {
    $fields = $segment.Trim() -split '\s+'
    $virtual = [Convert]::ToUInt64($fields[2],16)
    $physical = [Convert]::ToUInt64($fields[3],16)
    $size = [Convert]::ToUInt64($fields[5],16)
    if ($virtual -ne $physical -or $physical -lt 0x20000000 -or
        $physical + $size -gt 0x20042000) {
        throw "ELF load segment outside RP2040 SRAM: $segment"
    }
}
$headers | Set-Content "$Output/elf-program-headers.txt"
Get-FileHash $elf | Format-List Algorithm,Hash,Path
