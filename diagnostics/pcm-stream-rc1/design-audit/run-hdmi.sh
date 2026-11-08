#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
out=diagnostics/pcm-stream-rc1/design-audit
python3 "$out/prepare-fixture.py"
for variant in A B; do
 if [ "$variant" = A ]; then src=build/pcm-stream-rc1/sta-short-control/inputs; else src=releases/queue8-qspi-deglitch-rc1/build-inputs; fi
 verilator --binary --timing --assert -Wno-fatal --top-module tb_hdmi_activity --Mdir "$out/obj-hdmi-$variant" -j 4 "$out/tb_hdmi_activity.sv" "$src/build/generated/kagura_hdmi_stream.sv" "$src/rtl/hdmi/kagura_audio_packets.sv" "$src/rtl/hdmi/kagura_packet_assembler.sv" "$src/rtl/hdmi/kagura_tmds_channel.sv" "$src"/third_party/hdl-util-hdmi/src/*.sv > "$out/hdmi-$variant-build.log" 2>&1
 "$out/obj-hdmi-$variant/Vtb_hdmi_activity" "+TRANSCRIPT=$out/packets-$variant.txt" > "$out/hdmi-$variant.log" 2>&1
done
cmp "$out/packets-A.txt" "$out/packets-B.txt"
