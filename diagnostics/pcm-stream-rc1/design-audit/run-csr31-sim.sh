#!/usr/bin/env bash
# CSR 31 safety simulation of the T8 register RTL (section 20).
set -euo pipefail
cd "$(dirname "$0")/../../.."
out=diagnostics/pcm-stream-rc1/design-audit
src=build/pcm-stream-rc1/t8-di-local/inputs
verilator --binary --timing --assert -Wno-fatal --top-module tb_csr31_safety --Mdir "$out/obj-csr31" -j 4 "$out/tb_csr31_safety.sv" "$src/rtl/fb/kagura_fb_registers.sv" "$src/rtl/fb/kagura_fb_upload_word.sv" > "$out/csr31-build.log" 2>&1
"$out/obj-csr31/Vtb_csr31_safety" | tee "$out/csr31-safety.log"
