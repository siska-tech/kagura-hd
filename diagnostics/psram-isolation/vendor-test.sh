#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/build/psram-isolation/board-sim"
python3 - <<'PY'
from pathlib import Path
source=Path('/mnt/c/Gowin/Gowin_V1.9.12.04_x64/IDE/simlib/gw1n/prim_sim.v').read_bytes()
start=source.index(b'module SP (');end=source.index(b'endmodule',start)+len(b'endmodule')
Path('build/psram-isolation/board-sim/gowin_SP_sim.v').write_bytes(source[start:end]+b'\n')
PY
dir="$out/vendor-qspi"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal -DKAGURA_GOWIN_SIM \
 --top-module tb_host_isolation_board --Mdir "$dir" -j 4 \
 rtl/bus/kagura_spi_adapter.sv rtl/fb/{kagura_fb_host,kagura_fb_registers,kagura_fb_commands,kagura_fb_fill_burst,kagura_fb_upload_word}.sv \
 diagnostics/psram/psram_probe_uart.sv diagnostics/psram-isolation/{psram_host_stub,pdt_snapshot,host_isolation_core}.sv \
 "$out/gowin_SP_sim.v" "$out/tb_host_isolation_board.sv" > "$dir.build.log" 2>&1
# Preserve behavioral model's UART capture; vendor bench writes the same name.
cp "$out/uart-l4-b0.bin" "$out/uart-l4-b0-behavioral.bin"
"$dir/Vtb_host_isolation_board" > "$dir.run.log" 2>&1
mv "$out/uart-l4-b0.bin" "$out/uart-l4-b0-vendor.bin"
cp "$out/uart-l4-b0-behavioral.bin" "$out/uart-l4-b0.bin"
cmp "$out/uart-l4-b0.bin" "$out/uart-l4-b0-vendor.bin"
cat "$dir.run.log"
