#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
out="$PWD/build/host-window-observe/rmw-pc"
mkdir -p "$out"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_fb_register_window \
 --Mdir "$out/model" -j 4 rtl/fb/kagura_fb_registers.sv \
 diagnostics/host-window-observe/fix-candidates/kagura_fb_upload_word_rmw.sv \
 build/psram-isolation/board-sim/gowin_SP_sim.v sim/tests/tb_fb_register_window.sv > "$out/build.log" 2>&1
"$out/model/Vtb_fb_register_window" > "$out/run.log" 2>&1
cat "$out/run.log"
