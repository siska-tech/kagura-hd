#!/usr/bin/env bash
# Read protected PCM2 snapshot, write simulation products ONLY under showcase/out.
set -euo pipefail
app="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
repo="$(cd -- "$app/../.." && pwd)"
python3 "$app/tools/prepare_qspi_rtl.py"
cd "$repo"
verilator --version | tee "$app/evidence/qspi-rtl-version.log"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_fb_board_qspi \
 --Mdir "$app/out/qspi-rtl/obj" -j 4 -f rtl/fb/sources.f \
 sim/support/kagura_fb_serializer_stub.sv sim/support/kagura_hyperram_pair_model.sv \
 "$app/out/qspi-rtl/tb_fb_board_qspi_5mhz.sv" boards/tang-nano-9k/kagura_fb_top.sv \
 > "$app/evidence/qspi-rtl-build.log" 2>&1
timeout 180 "$app/out/qspi-rtl/obj/Vtb_fb_board_qspi" +verilator+seed+1 | tee "$app/evidence/qspi-rtl-run.log"
grep -q 'PASS: 5MHz QSPI PCM2 board' "$app/evidence/qspi-rtl-run.log"
