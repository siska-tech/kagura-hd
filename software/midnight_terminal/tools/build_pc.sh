#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; root="$(cd "$here/../.." && pwd)"
out="${1:-$root/build/midnight-terminal}"; mkdir -p "$out"
gcc -O2 -Wall -Wextra -std=c11 -DKFB_PACK_DESCRIPTOR=1 -I"$here/src" -I"$here/generated" \
    "$here"/src/{mt_fm,mt_show,mt_inflate,pc_main}.c "$here/generated/assets.c" "$root/software/fm_megademo/src/font.c" \
    "$root/software/kagura_fb/kagura_fb.c" -lm -o "$out/mt_pc"
echo "$out/mt_pc"
