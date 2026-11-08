#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# PC build of FOUR OPERATORS (behavioural KFB model + real SDK, demo and synth).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; root="$(cd "$here/../.." && pwd)"
out="${1:-$root/build/fm-megademo}"; mkdir -p "$out"
gcc -O2 -Wall -Wextra -std=c11 -DKFB_PACK_DESCRIPTOR=1 -I"$here/src" \
    "$here"/src/{fm,font,demo,pc_main}.c "$root/software/kagura_fb/kagura_fb.c" -lm -o "$out/fm_pc"
echo "$out/fm_pc"
