#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for delay in 0 100; do
dir="build/fb-ack-observe/delay-$delay"
mkdir -p "$dir"
verilator --binary --timing --timescale 1ns/1ps -Wno-fatal \
    --top-module tb_fb_ack_observe -GACK_DELAY="$delay" --Mdir "$PWD/$dir" -j 4 \
    rtl/fb/kagura_fb_command_head.sv rtl/fb/kagura_fb_registers.sv \
    rtl/fb/kagura_fb_upload_word.sv rtl/fb/kagura_fb_commands.sv \
    rtl/fb/kagura_fb_fill_burst.sv sim/tests/tb_fb_command_queue.sv \
    sim/tests/tb_fb_ack_observe.sv >"$dir/build.log" 2>&1
timeout 60 "$dir/Vtb_fb_ack_observe" | tee "$dir/run.log"
grep -q 'PASS: passive ACK dispatch observer' "$dir/run.log"
done
python3 - <<'PY'
from pathlib import Path
import json,re
rows=[]
for delay in (0,100):
    line=next(s for s in Path(f'build/fb-ack-observe/delay-{delay}/run.log').read_text().splitlines() if s.startswith('ACK_OBSERVE '))
    rows.append(dict(delay=delay,**{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}))
a,b=rows
assert b['completion_hold']-a['completion_hold']==4*8*100
assert b['blocked_dispatch']-a['blocked_dispatch']==4*7*100
assert b['no_younger']-a['no_younger']==4*100
Path('build/fb-ack-observe/comparison.json').write_text(json.dumps(dict(simulation_only=True,variants=rows,blocked_cycles_delta=2800,hold_cycles_delta=3200),indent=2))
print('PASS: removing 100 ACK-delay cycles saves 2800 blocked-dispatch cycles across 28 queued completions; no physical timing inference')
PY
