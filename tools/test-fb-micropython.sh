#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
: "${MICROPYTHON:=micropython}"
MICROPYPATH="$root/software/kagura_fb:$root/software/kagura_fb/tests"     "$MICROPYTHON" -X heapsize=16M software/kagura_fb/tests/test_micropython.py
