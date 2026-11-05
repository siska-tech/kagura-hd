"""Finalize bounded local/public evidence. No device connections or programming."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[2]
build=root/'build/host-isolation-standard/candidate-v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
gate=json.loads((build/'diagnostic-gate.json').read_text())
assert gate['numeric_sta_pass'] and not gate['hardware_tested']
protected={
 'build/rx32-scanout-worktree/build/kagura-fb-qspi/impl/pnr/kagura_fb.fs':'a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf',
 'build/psram-probe-standard/candidate-v3/impl/pnr/psram_probe.fs':'f6619b747171c92ea9fdb0aa562acfadfdf7af37940d2d6286b9535eebca62ac',
 'build/rx32-scanout-worktree/DO_NOT_PROGRAM.txt':'d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546'}
for relative,expected in protected.items():assert sha(root/relative)==expected,relative
files=list((root/'diagnostics/psram-isolation').glob('*'))
files=[p for p in files if p.is_file()]
files += [root/'build/psram-isolation/board-sim'/p for p in (
 'l1-b0.run.log','l4-b0.run.log','l4-b1.run.log','vendor-qspi.run.log',
 'uart-l1-b0.bin','uart-l4-b0.bin','uart-l4-b1.bin','uart-l4-b0-vendor.bin',
 'tb_host_isolation_board.sv','gowin_SP_sim.v')]
files += [build/p for p in ('build.log','diagnostic-gate.json','timing-status.json','impl/pnr/host_isolation.fs','impl/pnr/host_isolation.pin.html')]
evidence=dict(scope='ISO1 candidate-v2 creation and PC verification; NOT hardware test',
 gate=gate,protected_artifacts_sha256=protected,
 tests=dict(board_core_spi='PASS',board_core_qspi='PASS',board_core_qspi_bad_request='PASS',
            standard_vendor_sp_qspi='PASS',pdt_decoder='4 PASS',ram_host_case_real_device_driver='4 PASS'),
 fpga_sram_program_count=0,fpga_flash_writes=0,rp2040_flash_writes=0,
 live_flash_hash_checked=False,release_ready=False,
 file_sha256={p.relative_to(root).as_posix():sha(p) for p in files})
(build/'final-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
# No vendor model bytes or private recovery images are copied to public evidence.
public=root/'docs/evidence/host-isolation-standard-result.json'
public.write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps(dict(bitstream_sha256=gate['bitstream_sha256'],files=len(files),
                     protected_artifacts='unchanged',hardware_tested=False,release_ready=False),indent=2))
