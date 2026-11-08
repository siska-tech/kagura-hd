#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
out=diagnostics/pcm-stream-rc1/design-audit
for variant in A B; do
 if [ "$variant" = A ]; then src=build/pcm-stream-rc1/sta-short-control/inputs; else src=releases/queue8-qspi-deglitch-rc1/build-inputs; fi
 verilator --binary --timing --assert -Wno-fatal --top-module tb_mode_activity --Mdir "$out/obj-mode-$variant" -j 4 "$out/tb_mode_activity.sv" "$src/rtl/fb/kagura_fb_registers.sv" "$src/rtl/fb/kagura_fb_upload_word.sv" "$src/rtl/fb/kagura_fb_burst_ctrl.sv" > "$out/mode-$variant-build.log" 2>&1
 "$out/obj-mode-$variant/Vtb_mode_activity" > "$out/mode-$variant.log" 2>&1
done
