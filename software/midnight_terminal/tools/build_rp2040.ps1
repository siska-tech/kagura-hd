# SPDX-License-Identifier: Apache-2.0
# -Release: the UF2 for GitHub Releases (starts on power-up without a host; needs picotool 2.x)
# -HostLanes 1: SPI host for the SPI FPGA build (default 4: QSPI). -SpiPioDiv: SPI PIO divider
# (SCK = 120 MHz / (12 * div); empty keeps the 5 MHz default).
param(
    [string]$Output = '',
    [switch]$Release,
    [ValidateSet(1,4)][int]$HostLanes = 4,
    [string]$SpiPioDiv = '',
    [string]$Picotool = 'build/midnight-hardware/picotool/picotool/picotool.exe'
)
if (!$Output) { $Output = if ($Release) { 'build/midnight-terminal/rp2040-release' } else { 'build/midnight-terminal/rp2040' } }
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
& $cmake -S $src -B $Output -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" -DPICO_BOARD=pico -DPICO_NO_PICOTOOL=1 -DCMAKE_BUILD_TYPE=Release "-DKAGURA_RELEASE_UF2=$(if ($Release) {'ON'} else {'OFF'})" "-DKAGURA_HOST_LANES=$HostLanes" "-DKAGURA_SPI_PIO_DIV=$SpiPioDiv"
if ($LASTEXITCODE -ne 0) { throw 'Configure failed' }
& $cmake --build $Output --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
& "$($gcc.DirectoryName)/arm-none-eabi-size.exe" "$Output/midnight_terminal.elf"
if ($LASTEXITCODE -ne 0) { throw 'ELF size check failed' }
$elf = Join-Path $Output 'midnight_terminal.elf'
Get-FileHash $elf | Format-List Algorithm,Hash,Path
if ($Release) {
    $uf2 = Join-Path $Output 'midnight_terminal.uf2'
    & (Join-Path $root $Picotool) uf2 convert $elf $uf2 --family rp2040
    if ($LASTEXITCODE -ne 0) { throw 'UF2 conversion failed' }
    Get-FileHash $uf2 | Format-List Algorithm,Hash,Path
}
