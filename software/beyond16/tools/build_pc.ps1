$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$vc = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
foreach ($variant in @('baseline','optimized')) {
 $define = if ($variant -eq 'optimized') {'/DKFB_PACK_DESCRIPTOR=1'} else {'/DKFB_PACK_DESCRIPTOR=0'}
 $command = 'call "' + $vc + '" >nul && cl /nologo /LD /O2 /W4 /utf-8 /std:c11 ' + $define + ' "' + "$root/src/b16.c" + '" "' + "$root/src/b16_profile.c" + '" "' + "$root/src/pc.c" + '" "' + "$root/../midnight_terminal/src/mt_lz.c" + '" "' + "$root/../kagura_fb/kagura_fb.c" + '" /Fo"' + "$root/out/" + '" /link /IMPLIB:"' + "$root/out/$variant.lib" + '" /EXPORT:b16_init /EXPORT:b16_tick /EXPORT:kfb_init /EXPORT:kfb_probe /EXPORT:kfb_fill_rect /EXPORT:kfb_copy_rect /EXPORT:kfb_fence /EXPORT:kfb_write_bytes /EXPORT:kfb_read_bytes /EXPORT:kfb_wait /EXPORT:kfb_submit /OUT:"' + "$root/out/$variant.dll" + '"'
 & cmd.exe /d /c $command
 if ($LASTEXITCODE -ne 0) {throw 'PC C build failed'}
}


