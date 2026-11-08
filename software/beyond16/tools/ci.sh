#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/out"
for variant in baseline optimized; do
 flag=0; if [ "$variant" = optimized ]; then flag=1; fi
 cc -std=c11 -O2 -Wall -Wextra -DKFB_PACK_DESCRIPTOR=$flag -shared -fPIC "$root/src/b16_profile.c" "$root/src/b16.c" "$root/src/pc.c" "$root/../midnight_terminal/src/mt_lz.c" "$root/../kagura_fb/kagura_fb.c" -o "$root/out/lib$variant.so"
done
python3 "$root/tools/test.py"
