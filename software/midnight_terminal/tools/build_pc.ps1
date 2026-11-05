$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force "$root/out" | Out-Null
foreach ($file in @('midnight_sdk.lib','midnight_sdk.exp')) {
  if (Test-Path "$root/out/$file") { Remove-Item -LiteralPath "$root/out/$file" }
}
$vc = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
$command = 'call "' + $vc + '" >nul && cl /nologo /LD /O2 /W4 /utf-8 /std:c11 /I"' + "$root/src" + '" "' + "$root/src/mt.c" + '" "' + "$root/src/mt_device.c" + '" "' + "$root/../kagura_fb/kagura_fb.c" + '" /Fo"' + "$root/out/" + '" /link /EXPORT:mt_device_poll /EXPORT:mt_device_start /EXPORT:mt_device_emit /EXPORT:kfb_init /EXPORT:kfb_probe /EXPORT:kfb_copy_rect /EXPORT:kfb_fill_rect /EXPORT:kfb_write_bytes /EXPORT:kfb_palette /EXPORT:kfb_present /EXPORT:kfb_read_bytes /IMPLIB:"' + "$root/out/midnight_sdk.lib" + '" /OUT:"' + "$root/out/midnight.dll" + '"'
$command = $command.Replace(' /Fo"', ' "' + "$root/src/mt_preflight.c" + '" "' + "$root/src/mt_lz.c" + '" /Fo"').Replace('/EXPORT:mt_device_poll', '/EXPORT:mt_lz_decode /EXPORT:mt_preflight /EXPORT:mt_device_poll')
& cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) { throw 'C build failed' }



