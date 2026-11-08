$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$repo = Split-Path (Split-Path $root -Parent) -Parent
$sourceFiles = @("$root/CMakeLists.txt", "$root/../kagura_fb/kagura_fb.c", "$root/../kagura_fb/kagura_fb.h", "$root/../midnight_terminal/vendor/kagura_host.pio", "$root/generated/assets.inc")
$sourceFiles += @(Get-ChildItem "$root/src" -File | Where-Object {$_.Extension -in '.c','.h'} | ForEach-Object {$_.FullName})
$sourceHashes = @{}
foreach ($file in $sourceFiles) {
 $absolute = (Resolve-Path -LiteralPath $file).Path
 $relative = [System.IO.Path]::GetRelativePath($repo, $absolute).Replace('\','/')
 $sourceHashes[$relative] = (Get-FileHash -LiteralPath $absolute -Algorithm SHA256).Hash.ToLower()
}
$variants = @(
 @{Name='A-off'; Profile=0},
 @{Name='A-summary'; Profile=1},
 @{Name='A-detailed'; Profile=2},
 @{Name='B-summary'; Profile=1; Transport=1},
 @{Name='C-test128'; Profile=1; Transport=2; DmaThreshold=128},
 @{Name='absolute30'; Profile=1; Scheduler=1},
 @{Name='cooperative'; Profile=1; Cooperative=$true},
 @{Name='work64'; Profile=1; WorkRounds=64}
)
$results = @()
foreach ($variant in $variants) {
 $name = $variant.Name
 $parameters = @{} + $variant
 $parameters.Remove('Name')
 $destination = "$root/out/headroom-firmware/$name"
 New-Item -ItemType Directory -Force $destination | Out-Null
 & "$PSScriptRoot/build_rp2040.ps1" @parameters *> "$destination/build.log"
 foreach ($file in @('beyond16.bin','beyond16.elf','beyond16.elf.map','CMakeCache.txt')) {
  Copy-Item -LiteralPath "$root/out/rp2040/$file" -Destination "$destination/$file"
 }
 $binary = Get-Item "$destination/beyond16.bin"
 $results += @{variant=$variant; bin_bytes=$binary.Length; bin_sha256=(Get-FileHash "$destination/beyond16.bin" -Algorithm SHA256).Hash.ToLower(); elf_sha256=(Get-FileHash "$destination/beyond16.elf" -Algorithm SHA256).Hash.ToLower(); filesystem_safe=($binary.Length -le 0xa0000); hardware='NOT RUN'; release_ready=$false}
 Write-Output "Built $name : $($binary.Length) bytes"
}
$results | ConvertTo-Json -Depth 6 | Set-Content "$root/evidence/headroom-firmware.json"
$sourceHashes | ConvertTo-Json | Set-Content "$root/evidence/headroom-source-sha256.json"
# Leave ordinary build configured for the conservative CPU baseline.
& "$PSScriptRoot/build_rp2040.ps1" *> "$root/out/headroom-firmware/default-build.log"
