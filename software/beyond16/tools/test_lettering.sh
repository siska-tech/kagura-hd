#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p build/queue-wait-tests
for flag in 0 1; do
 gcc -std=c11 -O2 -shared -fPIC -DKFB_PACK_DESCRIPTOR=1 -DB16_MERGE_LETTERING="$flag" \
  -Isoftware/beyond16/src software/beyond16/src/b16.c software/beyond16/src/b16_profile.c \
  software/beyond16/src/pc.c software/midnight_terminal/src/mt_lz.c software/kagura_fb/kagura_fb.c \
  -o "build/queue-wait-tests/lettering-$flag.so"
done
python3 software/beyond16/tools/test_lettering.py | tee build/queue-wait-tests/lettering.log
