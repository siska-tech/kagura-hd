#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
base="${KAGURA_AUDIO_CREDIT_DIR:-build/audio-credit-predicate}"
mkdir -p "$base"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_audio_credit_predicate \
 --Mdir "$PWD/$base" -j 4 rtl/audio/kagura_audio_transport.sv rtl/memory/kagura_async_fifo.sv \
 sim/tests/tb_audio_credit_predicate.sv >"$base/build.log" 2>&1
timeout 90 "$base/Vtb_audio_credit_predicate" | tee "$base/run.log"
grep -q PASS "$base/run.log"
