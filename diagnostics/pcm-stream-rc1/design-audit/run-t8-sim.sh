#!/usr/bin/env bash
# T8: functional and activity check of the diagnostic DI-select RTL.
set -euo pipefail
cd "$(dirname "$0")/../../.."
out=diagnostics/pcm-stream-rc1/design-audit
src=build/pcm-stream-rc1/t8-di-local/inputs
for tb in tb_window_activity tb_mode_activity; do
 verilator --binary --timing --assert -Wno-fatal --top-module $tb --Mdir "$out/obj-t8-$tb" -j 4 "$out/$tb.sv" "$src/rtl/fb/kagura_fb_registers.sv" "$src/rtl/fb/kagura_fb_upload_word.sv" "$src/rtl/fb/kagura_fb_burst_ctrl.sv" > "$out/t8-$tb-build.log" 2>&1
 "$out/obj-t8-$tb/V$tb" > "$out/t8-$tb-local.log" 2>&1
 "$out/obj-t8-$tb/V$tb" +BROADCAST > "$out/t8-$tb-broadcast.log" 2>&1
done
