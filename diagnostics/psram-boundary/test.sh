#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"
mkdir -p build/psram-boundary
for test in '0 0 0' '1 0 0' '0 1 0' '0 0 1' '0 0 2' '0 0 3' '0 0 4'; do
    read -r wrap alias fault <<< "$test"
    dir="build/psram-boundary/sim-r${wrap}-a${alias}-f${fault}"
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_boundary \
        -GWRAP="$wrap" -GALIAS="$alias" -GFAULT="$fault" --Mdir "$root/$dir" -j 4 \
        diagnostics/psram-boundary/boundary_engine.sv diagnostics/psram/psram_probe_uart.sv \
        diagnostics/psram-boundary/tb_boundary.sv rtl/fb/kagura_fb_burst_ctrl.sv \
        sim/support/kagura_hyperram_pair_model.sv sim/support/kagura_psram_wrap_pair_model.sv \
        > "$dir.build.log" 2>&1
    timeout 60 "$dir/Vtb_boundary" > "$dir.run.log" 2>&1
    grep 'PASS: boundary' "$dir.run.log"
done
