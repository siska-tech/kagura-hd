$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force "$root/out/qspi-tests" | Out-Null
if (-not (Test-Path "$root/out/rp2040/kagura_host.pio.h")) { throw 'Run build_rp2040.ps1 first to assemble the real PIO header.' }
foreach ($file in @('qspi_test.lib','qspi_test.exp')) {
  if (Test-Path "$root/out/qspi-tests/$file") { Remove-Item -LiteralPath "$root/out/qspi-tests/$file" }
}
$vc = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
$command = 'call "' + $vc + '" >nul && cl /nologo /LD /O2 /W4 /utf-8 /std:c11 /I"' + "$root/tests/fake_sdk" + '" /I"' + "$root/tests" + '" /I"' + "$root/out/rp2040" + '" "' + "$root/src/mt_qspi.c" + '" "' + "$root/tests/qspi_fake.c" + '" /Fo"' + "$root/out/qspi-tests/" + '" /link /EXPORT:mt_qspi_init /EXPORT:mt_qspi_deinit /EXPORT:mt_qspi_io /EXPORT:mt_qspi_statistics /IMPLIB:"' + "$root/out/qspi-tests/qspi_test.lib" + '" /OUT:"' + "$root/out/qspi-tests/qspi_test.dll" + '"'
& cmd.exe /d /c $command
if ($LASTEXITCODE -ne 0) { throw 'Native QSPI test build failed' }
