#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/showcase
python3 software/kagura_fb/showcase/tests/test_showcase.py > build/showcase/tests.log 2>&1
bash tools/test-fb-drivers.sh > build/showcase/existing-drivers.log 2>&1
if [[ -n "${MICROPYTHON:-}" ]]; then
    for heap in 192 128; do
        MICROPYPATH="$PWD/software/kagura_fb" "$MICROPYTHON" -X heapsize="${heap}K" \
            software/kagura_fb/showcase/tests/memory_micropython.py > "build/showcase/micropython-${heap}k.log" 2>&1
    done
fi
echo 'PASS: showcase wire-Mock/oracle + existing drivers; inspect logs for optional MicroPython heap runs'
