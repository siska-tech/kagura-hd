# SPDX-License-Identifier: Apache-2.0
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    New-Item -ItemType Directory -Force build | Out-Null
    & iverilog -g2012 -Wall -s tb_fb_fill -o build/tb_fb_fill.vvp rtl/fb/kagura_fb_fill.sv sim/tests/tb_fb_fill.sv
    if ($LASTEXITCODE -ne 0) { throw 'fb_fill compilation failed' }
    & vvp build/tb_fb_fill.vvp
    if ($LASTEXITCODE -ne 0) { throw 'fb_fill simulation failed' }
    & iverilog -g2012 -Wall -s tb_fb_byte_port -o build/tb_fb_byte_port.vvp rtl/fb/kagura_fb_byte_port.sv sim/tests/tb_fb_byte_port.sv
    if ($LASTEXITCODE -ne 0) { throw 'fb_byte_port compilation failed' }
    & vvp build/tb_fb_byte_port.vvp
    if ($LASTEXITCODE -ne 0) { throw 'fb_byte_port simulation failed' }
} finally {
    Pop-Location
}

