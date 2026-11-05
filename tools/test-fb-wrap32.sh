#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p build/analysis
dir=build/wrap32-verilator
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_fb_wrap32 \
    --Mdir "$root/$dir" -j 4 rtl/fb/kagura_fb_burst_ctrl.sv \
    sim/support/kagura_psram_wrap_pair_model.sv sim/tests/tb_fb_wrap32.sv > build/analysis/wrap32.build.log 2>&1
timeout 180 "$dir/Vtb_fb_wrap32" +verilator+seed+1 | tee build/analysis/wrap32.run.log
grep -q PASS build/analysis/wrap32.run.log
