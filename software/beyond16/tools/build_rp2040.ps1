$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$prior = Join-Path (Split-Path $root -Parent) 'midnight_terminal'
$env:PICO_SDK_PATH = "$prior/toolchain/pico-sdk"
$gcc = Get-ChildItem "$prior/toolchain/arm" -Recurse -Filter arm-none-eabi-gcc.exe | Select-Object -First 1
if (-not $gcc) {throw 'Existing Arm toolchain not found'}
$env:PICO_TOOLCHAIN_PATH = $gcc.Directory.FullName
$cmake = "$prior/.deps/cmake/data/bin/cmake.exe"
$ninja = "$prior/.deps/bin/ninja.exe"
& $cmake -S $root -B "$root/out/rp2040" -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" -DPICO_BOARD=pico -DPICO_PLATFORM=rp2040 -DCMAKE_BUILD_TYPE=Release -DPICO_NO_PICOTOOL=1
if ($LASTEXITCODE -ne 0) {throw 'Configure failed'}
& $cmake --build "$root/out/rp2040" --parallel 4
if ($LASTEXITCODE -ne 0) {throw 'RP2040 C build failed'}
& "$($gcc.Directory.FullName)/arm-none-eabi-size.exe" "$root/out/rp2040/beyond16.elf"
if ($LASTEXITCODE -ne 0) {throw 'Size check failed'}
if ((Get-Item "$root/out/rp2040/beyond16.bin").Length -gt 0xa0000) {throw 'Filesystem boundary exceeded'}
