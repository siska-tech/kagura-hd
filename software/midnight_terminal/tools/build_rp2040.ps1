$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
& python3.12.exe "$root/tools/pack_bgm.py"
if ($LASTEXITCODE -ne 0) { throw 'Lossless BGM packing failed' }
if (-not $env:PICO_SDK_PATH) { $env:PICO_SDK_PATH = "$root/toolchain/pico-sdk" }
$gcc = Get-ChildItem "$root/toolchain/arm" -Recurse -Filter arm-none-eabi-gcc.exe | Select-Object -First 1
if (-not $gcc) { throw 'Set up Arm GNU toolchain under toolchain/arm first; see README.' }
$env:PICO_TOOLCHAIN_PATH = $gcc.Directory.FullName
$cmake = "$root/.deps/cmake/data/bin/cmake.exe"
$ninja = "$root/.deps/bin/ninja.exe"
if (-not (Test-Path $cmake)) { throw 'Install requirements into .deps first.' }
$pioasm = "$root/out/pioasm/pioasm.exe"
if (-not (Test-Path $pioasm)) {
  $vc = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
  $hostBuild = 'call "' + $vc + '" >nul && "' + $cmake + '" -S "' + "$env:PICO_SDK_PATH/tools/pioasm" + '" -B "' + "$root/out/pioasm" + '" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM="' + $ninja + '" && "' + $cmake + '" --build "' + "$root/out/pioasm" + '" --parallel 4'
  & cmd.exe /d /c $hostBuild
  if ($LASTEXITCODE -ne 0) { throw 'Host pioasm build failed' }
}
& $cmake -S $root -B "$root/out/rp2040" -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" -DPICO_BOARD=pico -DPICO_PLATFORM=rp2040 -DCMAKE_BUILD_TYPE=Release -DPICO_NO_PICOTOOL=1
if ($LASTEXITCODE -ne 0) { throw 'RP2040 CMake configure failed' }
& $cmake --build "$root/out/rp2040" --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'RP2040 C build failed' }
& "$($gcc.Directory.FullName)/arm-none-eabi-size.exe" "$root/out/rp2040/midnight_terminal.elf"
# Deliberately no programming or deployment commands.

