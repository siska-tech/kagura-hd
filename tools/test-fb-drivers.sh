#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p build/fb-driver
cc -std=c11 -Wall -Wextra -Werror -O2 -fPIC -shared software/kagura_fb/kagura_fb.c -o build/fb-driver/libkagura_fb.so
python3 software/kagura_fb/tests/test_drivers.py
python3 software/kagura_fb/tests/test_rp2040_qspi.py
python3 software/kagura_fb/tests/test_audio_csr.py
