#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/build/host-window-observe/sim-ff"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_window_observe_ff \
 --Mdir "$out/qspi" -j 4 \
 rtl/bus/kagura_spi_adapter.sv rtl/fb/{kagura_fb_registers,kagura_fb_commands,kagura_fb_fill_burst}.sv \
 diagnostics/psram/psram_probe_uart.sv diagnostics/host-window-observe/{kagura_fb_upload_word_ff,kagura_fb_host_observe,window_snapshot,window_observe_core}.sv \
 "$out/tb_window_observe_ff.sv" > "$out/build.log" 2>&1
"$out/qspi/Vtb_window_observe_ff" > "$out/run.log" 2>&1
cmp "$out/uart-l4-n0.bin" build/host-window-observe/sim/uart-l4-n0.bin
cat "$out/run.log"
