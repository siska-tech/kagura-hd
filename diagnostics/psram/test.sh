#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
mkdir -p build/psram-probe-sim
for test in '1 0 0' '16 0 0' '16 1 0' '1 0 1' '1 0 2'; do
    read -r words wrap fault <<< "$test"
    dir="build/psram-probe-sim/w${words}-r${wrap}-f${fault}"
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_psram_probe \
        -GWORDS="$words" -GWRAP="$wrap" -GFAULT="$fault" --Mdir "$root/$dir" -j 4 \
        diagnostics/psram/psram_probe_engine.sv diagnostics/psram/psram_probe_uart.sv \
        diagnostics/psram/tb_psram_probe.sv rtl/fb/kagura_fb_burst_ctrl.sv \
        sim/support/kagura_hyperram_pair_model.sv sim/support/kagura_psram_wrap_pair_model.sv \
        > "$dir.build.log" 2>&1
    timeout 60 "$dir/Vtb_psram_probe" > "$dir.run.log" 2>&1
    grep 'PASS: probe' "$dir.run.log"
done
