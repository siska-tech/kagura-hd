#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
mkdir -p build/psram-wrap-target
for test in '0 0 0' '1 0 0' '0 1 0' '0 0 1' '0 0 2' '0 0 3' '0 0 4' '1 0 5' '0 0 6'; do
    read -r wrap alias fault <<< "$test"
    dir="build/psram-wrap-target/sim-r${wrap}-a${alias}-f${fault}"
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_wrap_target \
        -GWRAP="$wrap" -GALIAS="$alias" -GFAULT="$fault" --Mdir "$root/$dir" -j 4 \
        diagnostics/psram-wrap-target/wrap_target_engine.sv diagnostics/psram/psram_probe_uart.sv \
        diagnostics/psram-wrap-target/tb_wrap_target.sv rtl/fb/kagura_fb_burst_ctrl.sv \
        sim/support/kagura_hyperram_pair_model.sv sim/support/kagura_psram_wrap_pair_model.sv \
        > "$dir.build.log" 2>&1
    timeout 60 "$dir/Vtb_wrap_target" > "$dir.run.log" 2>&1
    grep 'PASS: wrap-target' "$dir.run.log"
done
