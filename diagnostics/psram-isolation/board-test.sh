#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/build/psram-isolation/board-sim"
for spec in '1 0' '4 0' '4 1'; do
 read -r lanes bad <<< "$spec"
 dir="$out/l$lanes-b$bad"
 verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_host_isolation_board \
  -GLANES="$lanes" -GBAD_REQUEST="$bad" --Mdir "$dir" -j 4 \
  rtl/bus/kagura_spi_adapter.sv rtl/fb/{kagura_fb_host,kagura_fb_registers,kagura_fb_commands,kagura_fb_fill_burst,kagura_fb_upload_word}.sv \
  diagnostics/psram/psram_probe_uart.sv diagnostics/psram-isolation/{psram_host_stub,pdt_snapshot,host_isolation_core}.sv \
  "$out/tb_host_isolation_board.sv" > "$dir.build.log" 2>&1
 "$dir/Vtb_host_isolation_board" > "$dir.run.log" 2>&1
 cat "$dir.run.log"
done
