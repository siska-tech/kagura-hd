#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for depth in 2 4 8; do
    head="${KAGURA_QUEUE_REGISTER_HEAD:-1}"
    dir="build/fb-command-queue/depth-$depth"
    if [[ "$head" == 1 ]]; then dir+="-registered"; fi
    mkdir -p "$dir"
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal \
        --top-module tb_fb_command_queue -GDEPTH="$depth" -GREGISTER_HEAD="$head" --Mdir "$PWD/$dir" -j 4 \
        rtl/fb/kagura_fb_command_head.sv \
        rtl/fb/kagura_fb_registers.sv rtl/fb/kagura_fb_upload_word.sv \
        rtl/fb/kagura_fb_commands.sv rtl/fb/kagura_fb_fill_burst.sv \
        sim/tests/tb_fb_command_queue.sv >"$dir/build.log" 2>&1
    timeout 60 "$dir/Vtb_fb_command_queue" | tee "$dir/run.log"
    grep -q PASS "$dir/run.log"
done
# Depth one is compared cycle-by-cycle against the preserved reference.
KAGURA_TEST_FILTER=tb_fb_register_window bash tools/test-fb-verilator.sh
