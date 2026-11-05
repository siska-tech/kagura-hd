#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/build/host-window-observe/sim-rmw"
leaf=diagnostics/host-window-observe/fix-candidates/kagura_fb_upload_word_rmw.sv
model="$out/gowin_SP_fullword_guard.v"
for top in tb_upload_rmw tb_fb_register_window; do
 dir="$out/$top"
 if [[ "$top" == tb_upload_rmw ]]; then
  inputs=(diagnostics/host-window-observe/fix-candidates/tb_upload_rmw.sv)
 else
  inputs=(rtl/fb/kagura_fb_registers.sv sim/tests/tb_fb_register_window.sv)
 fi
 verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module "$top" \
 --Mdir "$dir" -j 4 "$leaf" "$model" "${inputs[@]}" > "$dir.build.log" 2>&1
 "$dir/V$top" > "$dir.run.log" 2>&1;cat "$dir.run.log"
done
dir="$out/qspi"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_window_observe_rmw \
 --Mdir "$dir" -j 4 rtl/bus/kagura_spi_adapter.sv \
 rtl/fb/{kagura_fb_registers,kagura_fb_commands,kagura_fb_fill_burst}.sv "$leaf" "$model" \
 diagnostics/psram/psram_probe_uart.sv diagnostics/host-window-observe/{kagura_fb_host_observe,window_snapshot,window_observe_core}.sv \
 "$out/tb_window_observe_rmw.sv" > "$dir.build.log" 2>&1
"$dir/Vtb_window_observe_rmw" > "$dir.run.log" 2>&1;cat "$dir.run.log"
cmp "$out/uart-l4-n0.bin" build/host-window-observe/sim/uart-l4-n0.bin
# Prove the gate catches the original dynamic-AD implementation.
dir="$out/original-rejected"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal -DKAGURA_GOWIN_SIM \
 --top-module tb_fb_register_window --Mdir "$dir" -j 4 rtl/fb/kagura_fb_registers.sv \
 rtl/fb/kagura_fb_upload_word.sv "$model" sim/tests/tb_fb_register_window.sv > "$dir.build.log" 2>&1
ulimit -c 0
set +e
"$dir/Vtb_fb_register_window" > "$dir.run.log" 2>&1
result=$?
set -e
[[ "$result" != 0 ]]
grep -q 'native byte-enable dependence rejected' "$dir.run.log"
echo 'PASS: original leaf rejected by conservative full-word-only gate (expected negative test)'
