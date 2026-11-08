#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
base="${KAGURA_PACKET_TEST_DIR:-build/packet-first}"
for replica in 0 1; do
 dir="$base/replica-$replica";mkdir -p "$dir"
 verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_packet_assembler \
  -GREPLICATE_FIRST="$replica" --Mdir "$PWD/$dir" -j 4 \
  third_party/hdl-util-hdmi/src/packet_assembler.sv rtl/hdmi/kagura_packet_assembler.sv \
  sim/tests/tb_packet_assembler.sv >"$dir/build.log" 2>&1
 for seed in 1 19 73; do
  timeout 60 "$dir/Vtb_packet_assembler" +verilator+seed+"$seed" | tee "$dir/seed-$seed.log"
  grep -q PASS "$dir/seed-$seed.log"
 done
done
