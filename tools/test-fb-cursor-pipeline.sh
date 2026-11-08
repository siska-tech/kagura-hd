#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
base="${KAGURA_CURSOR_TEST_DIR:-build/fb-cursor-pipeline}"
for top in tb_fb_cursor tb_fb_cursor_mailbox_pipeline; do
    dir="$base/$top"
    mkdir -p "$dir"
    options=()
    if [[ "$top" == tb_fb_cursor ]]; then options+=(-GPIPELINE_MAILBOX=1); fi
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module "$top" \
        "${options[@]}" --Mdir "$PWD/$dir" -j 4 sim/support/kagura_fb_cursor_reference.sv \
        rtl/fb/kagura_fb_cursor.sv rtl/memory/kagura_ram_tdp.sv "sim/tests/$top.sv" >"$dir/build.log" 2>&1
    timeout 180 "$dir/V$top" | tee "$dir/run.log"
    grep -q PASS "$dir/run.log"
done
