#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/build/psram-isolation"
mkdir -p "$out" build/psram-probe-sim
ctrl="$out/baseline/fail/rtl/fb/kagura_fb_burst_ctrl.sv"
for pattern in 0 1; do
  dir="$out/p$pattern"
  verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_psram_probe \
    -GEXACT_FAIL_PATTERN="$pattern" --Mdir "$dir" -j 4 \
    "$out/psram_probe_engine.sv" diagnostics/psram/psram_probe_uart.sv "$out/tb_psram_probe.sv" \
    "$ctrl" sim/support/kagura_hyperram_pair_model.sv sim/support/kagura_psram_wrap_pair_model.sv > "$dir.build.log" 2>&1
  "$dir/Vtb_psram_probe" > "$dir.run.log" 2>&1
  cat "$dir.run.log"
done
verilator --binary --timing -Wno-fatal --top-module tb_capture --Mdir "$out/capture" -j 4 \
 diagnostics/psram-isolation/{psram_boundary_capture,tb_capture}.sv > "$out/capture.build.log" 2>&1
"$out/capture/Vtb_capture" > "$out/capture.run.log" 2>&1
cat "$out/capture.run.log"
for lanes in 1 4; do
 dir="$out/host$lanes"
 verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_host_isolation \
  -GLANES="$lanes" --Mdir "$dir" -j 4 -f rtl/fb/sources.f \
  sim/support/kagura_fb_serializer_stub.sv diagnostics/psram-isolation/psram_host_stub.sv \
  "$out/tb_host_isolation.sv" > "$dir.build.log" 2>&1
 "$dir/Vtb_host_isolation" > "$dir.run.log" 2>&1
 cat "$dir.run.log"
done
