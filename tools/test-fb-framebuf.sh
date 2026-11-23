#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p build/framebuf
: "${MICROPYTHON:=micropython}"
MICROPYPATH="$root/software/kagura_fb:$root/software/kagura_fb/tests" \
    "$MICROPYTHON" -X heapsize=16M software/kagura_fb/tests/test_framebuf.py
MICROPYPATH="$root/software/kagura_fb" \
    "$MICROPYTHON" -X heapsize=192K software/kagura_fb/tests/memory_framebuf.py
MICROPYPATH="$root/software/kagura_fb" \
    "$MICROPYTHON" software/kagura_fb/tests/test_terminal.py
MICROPYPATH="$root/software/kagura_fb:$root/software/kagura_fb/tests" \
    "$MICROPYTHON" -X heapsize=16M software/kagura_fb/tests/test_glyph_atlas.py
