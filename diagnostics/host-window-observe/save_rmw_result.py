"""Retain this single RMW hardware case without modifying prior SP/FF evidence."""
from pathlib import Path
import hashlib,json,re
from decode import decode
root=Path(__file__).resolve().parents[2];base=root/'build/host-window-observe'
out=base/'hardware-rmw';build=base/'standard-rmw';pc=base/'sim-rmw'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
gate=json.loads((build/'diagnostic-gate.json').read_text())
extra=json.loads((build/'rmw-extra-audit.json').read_text())
assert gate['numeric_sta_pass'] and gate['pin_constraints_match'] and gate['psram_inactive_netlist_verified']
assert extra['sp_instances']==16 and extra['all_word_write_constant_ad'] and extra['shared_source_hashes_match']
fs=build/'impl/pnr/host_isolation.fs'
assert sha(fs)==gate['bitstream_sha256']=='487c81c0ce99d4a795e3edea48b46d19e0aeccbf932359469c00d3888edab38a'
raw=(out/'uart-full.bin').read_bytes();decoded=decode(raw)
assert decoded['all_six_match'] and decoded['flags']==0 and not decoded['header_fault']
for key in ('rx_count','write_count','read_count','csr_count','tx_count'):assert decoded[key]==4
for name in ('001-preflight','010-load-adapter','015-ram-check','020-identity','030-trial','090-release','095-flash'):
 assert json.loads((out/f'control/{name}.result.json').read_text())['ok'],name
host=(out/'control/030-trial.log').read_text()
assert 'EXPECTED ed0f2143 ACTUAL ed0f2143' in host
flash='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'
assert flash in (out/'control/001-preflight.log').read_text() and flash in (out/'control/095-flash.log').read_text()
assert 'Finished.' in (out/'sram-program.log').read_text() and 'SRAM Program' in (out/'sram-program.log').read_text()
assert 'Finished.' in (out/'restore-fpga.log').read_text() and 'Reprogram' in (out/'restore-fpga.log').read_text()
assert 'KAGURA-9 HDMI console (QSPI 5MHz)' in (out/'restore-soft-reset.log').read_text()
assert 'RECOVERY_STATE None False' in (out/'recovery-state.log').read_text()
seq=sorted(out.glob('recovery-seq-*.png'))
assert len(seq)==5 and len({sha(p) for p in seq})==1
assert seq[-1].read_bytes()==(base/'hardware-ff/recovery-seq-05.png').read_bytes()
assert json.loads((out/'uart-capture.json').read_text())==dict(bytes=136,armed=True,serial_writes=0)
for relative in ('tb_upload_rmw.run.log','tb_fb_register_window.run.log','qspi.run.log'):
 text=(pc/relative).read_text();assert 'PASS' in text and '%Fatal' not in text
assert 'native byte-enable dependence rejected' in (pc/'original-rejected.run.log').read_text()
assert (pc/'uart-l4-n0.bin').read_bytes()==(base/'sim/uart-l4-n0.bin').read_bytes()
protected={
 'build/rx32-scanout-worktree/build/kagura-fb-qspi/impl/pnr/kagura_fb.fs':'a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf',
 'build/psram-probe-standard/candidate-v3/impl/pnr/psram_probe.fs':'f6619b747171c92ea9fdb0aa562acfadfdf7af37940d2d6286b9535eebca62ac',
 'build/rx32-scanout-worktree/DO_NOT_PROGRAM.txt':'d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546',
 'rtl/fb/kagura_fb_upload_word.sv':'0c6724da635664801fcc8ae8ae8bc1512629e5e05f17fb1162affe7c44adf147',
 'rtl/memory/kagura_hyperram_phy_gowin.sv':'e20611d49ed5ebebb84db01cbee732f9198db57ec4e4ff8ef43b1a84b69d72c0'}
for relative,expected in protected.items():assert sha(root/relative)==expected,relative
result=dict(date='2026-11-05',mode='rmw',test_id='ISO2-1',candidate_sha256=sha(fs),
 hardware_tested=True,authorization_scope='one RMW SRAM-only 4B observation, followed by recovery; completed',
 outcome='PASS_LIMITED_4B_HOST_WINDOW_ONLY',uart=decoded,host_expected='ed0f2143',host_actual='ed0f2143',
 internal_sta=gate,build_gate_is_pre_program_snapshot=True,netlist_extra_audit=extra,
 pc_tests=dict(mask_cases=128,csr_window='PASS: 6 READ completions, 18 COPY captures, warm reset',
 qspi_uart='PASS',original_leaf_gate='expected rejection of native partial write; not silicon fault prediction'),
 sram_program_count=1,restore_reprogram_count=1,retries=0,configured_qspi_sck_hz=1000000,pad_clock_measured=False,
 psram_transfers=0,psram_validated=False,product_integrated=False,fpga_flash_writes=0,rp2040_flash_writes=0,
 fw_or_device_file_changes=False,rp2040_flash_before_after_sha256=flash,
 restore_banner_confirmed=True,console_error=None,console_paused=False,
 hdmi_recovery='5 captured PNGs identical to the previously verified KAGURA-9 FF recovery reference',
 hdmi_recovery_sha256=sha(seq[-1]),protected_artifacts=protected,release_ready=False)
(out/'decoded.json').write_text(json.dumps(decoded,indent=2)+'\n')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
(build/'hardware-evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'evidence-sha256.json').write_text(json.dumps({p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'},indent=2)+'\n')
(root/'docs/evidence/host-window-rmw-2026-11-05.json').write_text(json.dumps(result,indent=2)+'\n')
(root/'docs/evidence/host-window-rmw-uart-2026-11-05.hex').write_text(raw.hex()+'\n')
print(json.dumps({k:result[k] for k in ('outcome','candidate_sha256','psram_transfers','product_integrated','sram_program_count','restore_reprogram_count','release_ready')},indent=2))
