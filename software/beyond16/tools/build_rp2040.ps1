param(
 [ValidateRange(0,2)][int]$Profile = 0,
 [ValidateRange(0,2)][int]$Transport = 0,
 [ValidateRange(0,512)][int]$DmaThreshold = 0,
 [ValidateRange(0,1)][int]$Scheduler = 0,
 [ValidateRange(0,4096)][int]$WorkRounds = 0,
 [ValidateSet(0,8)][int]$GpuQueue = 0,
 [string]$BuildDirectory = '',
 [switch]$QueueMetrics,
 [switch]$MergeLettering,
 [switch]$CompletionBurst,
 [switch]$Cooperative
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$prior = Join-Path (Split-Path $root -Parent) 'midnight_terminal'
$env:PICO_SDK_PATH = "$prior/toolchain/pico-sdk"
$gcc = Get-ChildItem "$prior/toolchain/arm" -Recurse -Filter arm-none-eabi-gcc.exe | Select-Object -First 1
if (-not $gcc) {throw 'Existing Arm toolchain not found'}
$env:PICO_TOOLCHAIN_PATH = $gcc.Directory.FullName
$cmake = "$prior/.deps/cmake/data/bin/cmake.exe"
$ninja = "$prior/.deps/bin/ninja.exe"
$coop = if ($Cooperative) {'ON'} else {'OFF'}
$metrics = if ($QueueMetrics) {'ON'} else {'OFF'}
$lettering = if ($MergeLettering) {'ON'} else {'OFF'}
$burst = if ($CompletionBurst) {'ON'} else {'OFF'}
if (-not $BuildDirectory) { $BuildDirectory = "$root/out/rp2040" }
& $cmake -S $root -B $BuildDirectory -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" -DPICO_BOARD=pico -DPICO_PLATFORM=rp2040 -DCMAKE_BUILD_TYPE=Release -DPICO_NO_PICOTOOL=1 -DB16_HOST_FAST=ON "-DB16_PROFILE=$Profile" "-DB16_TRANSPORT=$Transport" "-DB16_DMA_THRESHOLD=$DmaThreshold" "-DB16_SCHEDULER=$Scheduler" "-DB16_WORK_ROUNDS=$WorkRounds" "-DB16_COOP=$coop" "-DB16_GPU_QUEUE=$GpuQueue" "-DB16_QUEUE_METRICS=$metrics" "-DB16_MERGE_LETTERING=$lettering" "-DB16_COMPLETION_BURST=$burst"
if ($LASTEXITCODE -ne 0) {throw 'Configure failed'}
& $cmake --build $BuildDirectory --parallel 4
if ($LASTEXITCODE -ne 0) {throw 'RP2040 C build failed'}
& "$($gcc.Directory.FullName)/arm-none-eabi-size.exe" "$BuildDirectory/beyond16.elf"
if ($LASTEXITCODE -ne 0) {throw 'Size check failed'}
if ((Get-Item "$BuildDirectory/beyond16.bin").Length -gt 0xa0000) {throw 'Filesystem boundary exceeded'}
