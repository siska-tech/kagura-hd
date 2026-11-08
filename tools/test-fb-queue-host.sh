#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare-hdmi-stream.py
base="${KAGURA_QUEUE_HOST_DIR:-build/fb-queue-host}"
mkdir -p "$base"
exec 9>"$base/.lock"
flock -n 9 || { echo "Queue host regression already running" >&2; exit 1; }
for lanes in ${KAGURA_QUEUE_LANES:-1 4}; do
    for depth in ${KAGURA_QUEUE_DEPTHS:-2 4 8}; do
        dir="$base/lanes-$lanes-depth-$depth"
        mkdir -p "$dir"
        verilator --binary --timing --timescale 1ns/1ps -Wno-fatal \
            --top-module tb_fb_host -GLANES="$lanes" -GQUEUE_DEPTH="$depth" -GREGISTER_AUDIO_CREDITS="${KAGURA_AUDIO_CREDITS:-0}" \
            -GREPLICATE_PACKET_FIRST="${KAGURA_PACKET_FIRST:-0}" \
            --Mdir "$PWD/$dir" -j 4 -f rtl/fb/sources.f \
            sim/support/kagura_fb_serializer_stub.sv sim/support/kagura_hyperram_pair_model.sv \
            sim/tests/tb_fb_host.sv >"$dir/build.log" 2>&1
        timeout 180 "$dir/Vtb_fb_host" | tee "$dir/run.log"
        grep -q 'PASS: queued fb_host' "$dir/run.log"
    done
done
