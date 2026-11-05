#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run the unchanged client tests against the independent 32B-wrap model.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p build/analysis build/generated
python3 - <<'PY'
from pathlib import Path
s=Path('sim/support/kagura_psram_wrap_pair_model.sv').read_text()
s=s.replace('module kagura_psram_wrap_pair_model','module kagura_hyperram_pair_model')
s=s.replace('LAT=14, RDL=6, BYTES=4096, CS_HIGH_CYCLES=2,', 'LAT=14, RDL=6, BYTES=4096, CS_HIGH_CYCLES=2, MAX_WORDS=1,')
s=s.replace('ALLOW_UNDOCUMENTED_CA45=0','ALLOW_UNDOCUMENTED_CA45=1')
Path('build/generated/kagura_hyperram_pair_model_wrap32.sv').write_text(s)
s=Path('tools/test-fb-verilator.sh').read_text()
lines=s.splitlines()
lines[3]='root="${KAGURA_WRAP32_ROOT:?}"'
s='\n'.join(lines)+'\n'
s=s.replace('sim/support/kagura_hyperram_pair_model.sv','build/generated/kagura_hyperram_pair_model_wrap32.sv')
s=s.replace('build/fb-verilator','build/fb-wrap32-integration')
Path('build/analysis/run-wrap32-integration.sh').write_text(s)
PY
export KAGURA_WRAP32_ROOT="$root"
export KAGURA_STRICT_VERSION=1
export KAGURA_TEST_FILTER='tb_fb_blit tb_fb_fill_chain tb_fb_burst_ctrl tb_fb_contention tb_fb_line_fetch tb_fb_scanout tb_fb_scanout_faults tb_fb_fill_burst tb_fb_core tb_fb_host_spi tb_fb_host_qspi tb_fb_board'
exec bash build/analysis/run-wrap32-integration.sh
