#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Independent opt-in diagnostics; does not replace either existing regression.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p build/psram-investigation
for mode in hypothesis strict-reject strict-legal; do
    strict=1; adapter=0
    [[ "$mode" != hypothesis ]] || strict=0
    [[ "$mode" != strict-legal ]] || adapter=1
    dir="build/psram-investigation/wrap-$mode"
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal \
        --top-module tb_psram_wrap_repro -GSTRICT_CA="$strict" -GLEGAL_CA_ADAPTER="$adapter" --Mdir "$root/$dir" -j 4 \
        rtl/fb/kagura_fb_burst_ctrl.sv sim/support/kagura_psram_wrap_pair_model.sv \
        sim/diagnostics/tb_psram_wrap_repro.sv > "$dir.build.log" 2>&1
    if [[ "$mode" != strict-reject ]]; then
        timeout 60 "$dir/Vtb_psram_wrap_repro" > "$dir.run.log" 2>&1
        grep -q 'PASS: 32B wrap hypothesis' "$dir.run.log"
        grep 'PASS: 32B wrap hypothesis' "$dir.run.log"
    else
        # Strict reference protocol MUST reject production memory CA45=1.
        ulimit -c 0
        set +e
        timeout 60 "$dir/Vtb_psram_wrap_repro" > "$dir.run.log" 2>&1
        result=$?
        set -e
        [[ "$result" != 0 && "$result" != 124 ]]
        grep -q 'memory CA45=1 undocumented by reference die' "$dir.run.log"
        echo 'PASS: strict reference CA rejection (expected negative test)'
    fi
done
