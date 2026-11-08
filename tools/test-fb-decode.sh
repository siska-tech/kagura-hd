#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
base="${KAGURA_DECODE_DIR:-build/fb-decode}"
mkdir -p "$base"
for audio in 0 1; do
    dir="$base/equivalence-audio-$audio"
    mkdir -p "$dir"
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_fb_decode_equivalence \
        -GAUDIO_CSR="$audio" --Mdir "$PWD/$dir" -j 4 rtl/fb/kagura_fb_commands.sv \
        rtl/fb/kagura_fb_fill_burst.sv sim/tests/tb_fb_decode_equivalence.sv >"$dir/build.log" 2>&1
    timeout 60 "$dir/Vtb_fb_decode_equivalence" | tee "$dir/run.log"
    grep -q PASS "$dir/run.log"
done
dir="$base/bounds"
mkdir -p "$dir"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_fb_command_bounds \
    -GREGISTER_DECODE=1 --Mdir "$PWD/$dir" -j 4 rtl/fb/kagura_fb_commands.sv \
    rtl/fb/kagura_fb_fill_burst.sv sim/tests/tb_fb_command_bounds.sv >"$dir/build.log" 2>&1
timeout 60 "$dir/Vtb_fb_command_bounds" | tee "$dir/run.log"
grep -q PASS "$dir/run.log"
