#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Optional local test using the installed vendor model; no vendor bytes are
# added to the repository. Override GOWIN_PRIM_SIM for another installation.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
primitive="${GOWIN_PRIM_SIM:-/mnt/c/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw1n/prim_sim.v}"
mkdir -p build/generated build/fb-verilator
# The other primitives contain constructs unsupported by Verilator, so select
# only the unmodified SP module from the user's installed simulation library.
python3 - "$primitive" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_bytes()
start = source.index(b"module SP (")
end = source.index(b"endmodule", start) + len(b"endmodule")
Path("build/generated/gowin_SP_sim.v").write_bytes(source[start:end] + b"\n")
PY
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal -DKAGURA_GOWIN_SIM \
    --top-module tb_fb_register_window --Mdir build/fb-verilator/tb_fb_register_window_gowin -j 4 \
    rtl/fb/kagura_fb_registers.sv rtl/fb/kagura_fb_upload_word.sv \
    build/generated/gowin_SP_sim.v sim/tests/tb_fb_register_window.sv \
    > build/fb-blit-vendor-ram.build.log 2>&1
timeout 60 build/fb-verilator/tb_fb_register_window_gowin/Vtb_fb_register_window \
    | tee build/fb-blit-vendor-ram.run.log
grep -q PASS build/fb-blit-vendor-ram.run.log
