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
mkdir -p build/common-verilator build/verilator
exec 9>build/common-verilator/.lock
flock -n 9 || { echo "Common regression already running" >&2; exit 1; }
run_count=0
run() {
    local top="$1"; shift
    run_count=$((run_count+1))
    verilator --binary --timing --timescale 1ns/1ps -Wno-fatal --top-module "$top" \
        --Mdir "$root/build/common-verilator/$top" -j 4 "$@" > "build/common-verilator/$top.build.log" 2>&1
    timeout 180 "$root/build/common-verilator/$top/V$top" +verilator+seed+"${KAGURA_SEED:-1}" | tee "build/common-verilator/$top.run.log"
    grep -q 'PASS' "build/common-verilator/$top.run.log"
}
run tb_phase1_sources rtl/vdp/kagura_bar_pattern.sv rtl/vdp/kagura_test_pattern.sv \
    rtl/audio/kagura_test_tone.sv sim/tests/tb_phase1_sources.sv
# Compile unchanged upstream SystemVerilog; no Icarus compatibility rewriting.
run tb_tmds_channel third_party/hdl-util-hdmi/src/tmds_channel.sv \
    sim/tests/tb_tmds_channel.sv
run tb_tmds_pipeline third_party/hdl-util-hdmi/src/tmds_channel.sv rtl/hdmi/kagura_tmds_channel.sv \
    sim/tests/tb_tmds_pipeline.sv
run tb_packet_assembler third_party/hdl-util-hdmi/src/packet_assembler.sv rtl/hdmi/kagura_packet_assembler.sv \
    sim/tests/tb_packet_assembler.sv
run tb_serializer_reset rtl/platform/kagura_gowin_serializer.sv sim/tests/tb_serializer_reset.sv
run tb_async_fifo rtl/memory/kagura_async_fifo.sv sim/tests/tb_async_fifo.sv
run tb_audio_packets rtl/memory/kagura_async_fifo.sv \
    rtl/audio/kagura_audio_transport.sv rtl/hdmi/kagura_audio_packets.sv \
    third_party/hdl-util-hdmi/src/audio_sample_packet.sv \
    third_party/hdl-util-hdmi/src/audio_info_frame.sv \
    third_party/hdl-util-hdmi/src/auxiliary_video_information_info_frame.sv \
    third_party/hdl-util-hdmi/src/source_product_description_info_frame.sv \
    third_party/hdl-util-hdmi/src/packet_assembler.sv sim/tests/tb_audio_packets.sv
python3 tools/prepare-hdmi-stream.py
# The same stream at VIC1 (640x480) and VIC4 (1280x720, docs/video.md).
for stream_test in tb_hdmi_stream tb_hdmi_stream720; do
    run "$stream_test" build/generated/kagura_hdmi_stream.sv rtl/hdmi/kagura_tmds_channel.sv rtl/hdmi/kagura_packet_assembler.sv \
        rtl/memory/kagura_async_fifo.sv rtl/audio/kagura_audio_transport.sv \
        rtl/hdmi/kagura_audio_packets.sv rtl/vdp/kagura_bar_pattern.sv rtl/vdp/kagura_video_source_bars.sv rtl/hdmi/kagura_hdmi_stream_eval.sv \
        third_party/hdl-util-hdmi/src/audio_sample_packet.sv \
        third_party/hdl-util-hdmi/src/audio_info_frame.sv \
        third_party/hdl-util-hdmi/src/auxiliary_video_information_info_frame.sv \
        third_party/hdl-util-hdmi/src/source_product_description_info_frame.sv \
        third_party/hdl-util-hdmi/src/packet_assembler.sv \
        third_party/hdl-util-hdmi/src/tmds_channel.sv sim/tests/tb_hdmi_stream.sv
done
run tb_bsram_wrappers rtl/memory/kagura_ram_sp.sv rtl/memory/kagura_ram_sdp.sv \
    rtl/memory/kagura_ram_tdp.sv rtl/memory/kagura_ram_rmw16.sv rtl/vdp/kagura_line_banks.sv \
    sim/tests/tb_bsram_wrappers.sv
run tb_audio_synth rtl/audio/kagura_audio_synth.sv sim/tests/tb_audio_synth.sv
run tb_audio_pcm_mix rtl/audio/kagura_audio_synth.sv sim/tests/tb_audio_pcm_mix.sv
run tb_pcm_prefetch rtl/audio/kagura_pcm_prefetch.sv sim/tests/tb_pcm_prefetch.sv
run tb_pcm_timeout rtl/audio/kagura_pcm_prefetch.sv sim/tests/tb_pcm_timeout.sv
run tb_pcm_audio_path rtl/audio/kagura_audio_synth.sv rtl/audio/kagura_pcm_prefetch.sv sim/tests/tb_pcm_audio_path.sv
run tb_psram_byte_bridge rtl/memory/kagura_psram_byte_bridge.sv sim/tests/tb_psram_byte_bridge.sv
run tb_psram_read_cdc rtl/memory/kagura_psram_read_cdc.sv sim/tests/tb_psram_read_cdc.sv
run tb_hyperram_ctrl rtl/memory/kagura_hyperram_ctrl.sv sim/tests/tb_hyperram_ctrl.sv
run tb_psram_arbiter rtl/memory/kagura_psram_arbiter.sv sim/tests/tb_psram_arbiter.sv
run tb_hyperram_pcm_source rtl/audio/kagura_audio_synth.sv rtl/audio/kagura_pcm_prefetch.sv \
    rtl/memory/kagura_psram_read_cdc.sv rtl/memory/kagura_psram_byte_bridge.sv \
    rtl/memory/kagura_psram_read_path.sv rtl/memory/kagura_hyperram_ctrl.sv \
    rtl/memory/kagura_psram_arbiter.sv boards/tang-nano-9k/kagura_hyperram_pcm_source.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_hyperram_pcm_source.sv
run tb_hyperram_pcm_chain rtl/audio/kagura_audio_synth.sv rtl/audio/kagura_pcm_prefetch.sv \
    rtl/memory/kagura_psram_read_cdc.sv rtl/memory/kagura_psram_byte_bridge.sv \
    rtl/memory/kagura_psram_read_path.sv rtl/memory/kagura_hyperram_ctrl.sv \
    sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_hyperram_pcm_chain.sv
run tb_psram_pcm_chain rtl/audio/kagura_audio_synth.sv rtl/audio/kagura_pcm_prefetch.sv \
    rtl/memory/kagura_psram_read_cdc.sv rtl/memory/kagura_psram_byte_bridge.sv \
    rtl/memory/kagura_psram_read_path.sv sim/tests/tb_psram_pcm_chain.sv

echo "PASS: all $run_count shared component tests"
