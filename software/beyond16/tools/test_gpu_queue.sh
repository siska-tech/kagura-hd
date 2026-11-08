#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/../../.."
dir="${KAGURA_QUEUE_TEST_DIR:-build/queue-demo-tests}";mkdir -p "$dir"
for pack in 0 1; do
 for metrics in 0 1; do
 for burst in 0 1; do
 gcc -std=c11 -O2 -Wall -Wextra -DB16_GPU_QUEUE=8 -DB16_QUEUE_METRICS="$metrics" -DB16_COMPLETION_BURST="$burst" -DKFB_PACK_DESCRIPTOR="$pack" \
  -Isoftware/kagura_fb -Isoftware/beyond16/src software/kagura_fb/kagura_fb.c \
  software/beyond16/tests/queue_test.c -o "$dir/queue-$pack-$metrics-$burst"
 for mode in normal error tag delay race timeout transport io sticky; do
  "$dir/queue-$pack-$metrics-$burst" $([[ "$mode" != normal ]] && echo "$mode" || true) | tee "$dir/pack-$pack-metrics-$metrics-burst-$burst-$mode.log"
 done
 done
 done
done
