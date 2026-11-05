#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/build/host-window-observe/sim"
for spec in '1 0' '4 0' '4 1'; do
 read -r lanes neg <<< "$spec";dir="$out/l$lanes-n$neg"
 verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_window_observe \
 -GLANES="$lanes" -GNEGATIVE="$neg" --Mdir "$dir" -j 4 \
 rtl/bus/kagura_spi_adapter.sv rtl/fb/{kagura_fb_registers,kagura_fb_upload_word,kagura_fb_commands,kagura_fb_fill_burst}.sv \
 diagnostics/psram/psram_probe_uart.sv diagnostics/host-window-observe/{kagura_fb_host_observe,window_snapshot,window_observe_core}.sv \
 "$out/tb_window_observe.sv" > "$dir.build.log" 2>&1
 "$dir/Vtb_window_observe" > "$dir.run.log" 2>&1;cat "$dir.run.log"
done
