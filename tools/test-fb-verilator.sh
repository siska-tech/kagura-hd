#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
expected="$(tr -d '[:space:]' < tools/verilator.version)"
actual="$(verilator --version | awk '{print $2}')"
if [[ "${KAGURA_STRICT_VERSION:-0}" == 1 && "$actual" != "$expected" ]]; then
    echo "Expected Verilator $expected, got $actual" >&2; exit 1
fi
echo "$(verilator --version), seed ${KAGURA_SEED:-1}"
mkdir -p build/fb-verilator build/verilator
exec 9>build/fb-verilator/.lock
flock -n 9 || { echo "FB regression already running" >&2; exit 1; }
run_count=0
run() {
    local top="$1"; shift
    if [[ -n "${KAGURA_TEST_FILTER:-}" && " $KAGURA_TEST_FILTER " != *" $top "* ]]; then return 0; fi
    run_count=$((run_count+1))
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module "$top" \
        --Mdir "$root/build/fb-verilator/$top" -j 4 "$@" > "build/fb-verilator/$top.build.log" 2>&1
    timeout 180 "$root/build/fb-verilator/$top/V$top" +verilator+seed+"${KAGURA_SEED:-1}" | tee "build/fb-verilator/$top.run.log"
    grep -q 'PASS' "build/fb-verilator/$top.run.log"
}
run tb_tmds_pipeline rtl/hdmi/kagura_tmds_channel.sv third_party/hdl-util-hdmi/src/tmds_channel.sv sim/tests/tb_tmds_pipeline.sv
run tb_audio_synth rtl/audio/kagura_audio_synth.sv sim/tests/tb_audio_synth.sv
run tb_fb_command_bounds rtl/fb/kagura_fb_commands.sv rtl/fb/kagura_fb_fill_burst.sv sim/tests/tb_fb_command_bounds.sv
run tb_fb_blit rtl/fb/kagura_fb_commands.sv rtl/fb/kagura_fb_fill_burst.sv rtl/fb/kagura_fb_arbiter.sv \
    rtl/fb/kagura_fb_burst_ctrl.sv sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_blit.sv
run tb_fb_register_window sim/support/kagura_fb_registers_reference.sv rtl/fb/kagura_fb_registers.sv rtl/fb/kagura_fb_upload_word.sv sim/tests/tb_fb_register_window.sv
run tb_fb_audio_clock rtl/audio/kagura_audio_transport.sv rtl/memory/kagura_async_fifo.sv sim/tests/tb_fb_audio_clock.sv
run tb_async_fifo rtl/memory/kagura_async_fifo.sv sim/tests/tb_async_fifo.sv
run tb_fb_cursor sim/support/kagura_fb_cursor_reference.sv rtl/fb/kagura_fb_cursor.sv rtl/memory/kagura_ram_tdp.sv sim/tests/tb_fb_cursor.sv
run tb_fb_fill rtl/fb/kagura_fb_fill.sv sim/tests/tb_fb_fill.sv
run tb_fb_byte_port rtl/fb/kagura_fb_byte_port.sv sim/tests/tb_fb_byte_port.sv
run tb_fb_fill_chain rtl/fb/kagura_fb_fill.sv rtl/fb/kagura_fb_byte_port.sv \
    rtl/memory/kagura_hyperram_ctrl.sv sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_fill_chain.sv
run tb_fb_burst_ctrl rtl/fb/kagura_fb_burst_ctrl.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_burst_ctrl.sv

run tb_fb_burst_bounds rtl/fb/kagura_fb_burst_ctrl.sv sim/tests/tb_fb_burst_bounds.sv
run tb_fb_burst_service rtl/fb/kagura_fb_burst_ctrl.sv rtl/fb/kagura_fb_arbiter.sv sim/tests/tb_fb_burst_service.sv

run tb_fb_contention rtl/fb/kagura_fb_arbiter.sv rtl/fb/kagura_fb_burst_ctrl.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_contention.sv

run tb_fb_line_fetch rtl/fb/kagura_fb_line_fetch.sv rtl/fb/kagura_fb_arbiter.sv rtl/fb/kagura_fb_burst_ctrl.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_line_fetch.sv

run tb_fb_line_fetch_control rtl/fb/kagura_fb_line_fetch.sv sim/tests/tb_fb_line_fetch_control.sv

run tb_fb_line_banks rtl/memory/kagura_ram_tdp.sv rtl/fb/kagura_fb_line_banks.sv sim/tests/tb_fb_line_banks.sv

run tb_fb_scanout rtl/fb/kagura_fb_scanout.sv rtl/fb/kagura_fb_line_banks.sv rtl/fb/kagura_fb_line_fetch.sv \
    rtl/fb/kagura_fb_arbiter.sv rtl/fb/kagura_fb_burst_ctrl.sv rtl/memory/kagura_ram_tdp.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_scanout.sv

run tb_fb_scanout_faults rtl/fb/kagura_fb_scanout.sv rtl/fb/kagura_fb_line_banks.sv rtl/fb/kagura_fb_line_fetch.sv \
    rtl/fb/kagura_fb_arbiter.sv rtl/fb/kagura_fb_burst_ctrl.sv rtl/memory/kagura_ram_tdp.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_scanout.sv

run tb_fb_pcm_port rtl/fb/kagura_fb_pcm_port.sv sim/tests/tb_fb_pcm_port.sv

python3 tools/prepare-hdmi-stream.py
run tb_fb_fill_burst rtl/fb/kagura_fb_fill_burst.sv rtl/fb/kagura_fb_burst_ctrl.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_fill_burst.sv
run tb_fb_core sim/support/kagura_fb_serializer_stub.sv -f rtl/fb/sources.f sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_core.sv

for lanes in spi qspi; do
    run "tb_fb_host_$lanes" -f rtl/fb/sources.f \
        sim/support/kagura_fb_serializer_stub.sv sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_host.sv
done

run tb_fb_board -f rtl/fb/sources.f sim/support/kagura_fb_serializer_stub.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_board.sv boards/tang-nano-9k/kagura_fb_top.sv

if [[ "$run_count" == 0 ]]; then echo "No matching tests" >&2; exit 1; fi
echo "PASS: all $run_count Kagura-FB tests"
