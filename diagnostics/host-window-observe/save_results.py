"""Verify and retain both hardware cases, compile provenance and protected images."""
from pathlib import Path
import hashlib,json,re
from decode import decode
root=Path(__file__).resolve().parents[2];base=root/'build/host-window-observe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
flash='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'
cases={}
for mode in ('sp','ff'):
 out=base/f'hardware-{mode}';build=base/f'standard-{mode}'
 gate=json.loads((build/'diagnostic-gate.json').read_text())
 assert gate['numeric_sta_pass'] and gate['pin_constraints_match'] and gate['psram_inactive_netlist_verified']
 assert sha(build/'impl/pnr/host_isolation.fs')==gate['bitstream_sha256']
 raw=(out/'uart-full.bin').read_bytes();decoded=decode(raw)
 assert decoded['flags']==0 and not decoded['header_fault']
 for key in ('rx_count','write_count','read_count','csr_count','tx_count'):assert decoded[key]==4
 for key in ('001-preflight','020-identity','090-release','095-flash'):
  assert json.loads((out/f'control/{key}.result.json').read_text())['ok'],key
 assert flash in (out/'control/001-preflight.log').read_text() and flash in (out/'control/095-flash.log').read_text()
 assert 'SRAM Program' in (out/'sram-program.log').read_text() and 'Finished.' in (out/'sram-program.log').read_text()
 assert 'Reprogram' in (out/'restore-fpga.log').read_text() and 'Finished.' in (out/'restore-fpga.log').read_text()
 assert 'KAGURA-9 HDMI console (QSPI 5MHz)' in (out/'restore-soft-reset.log').read_text()
 image=out/'kagura9-restored-confirmed.png'
 assert image.exists()
 if mode=='ff':
  sequence=sorted(out.glob('recovery-seq-*.png'))
  assert len(sequence)==5 and len({sha(p) for p in sequence})==1
 host=(out/'control/030-trial.log').read_text()
 echo=re.search(r'ISO2_ECHO EXPECTED ([0-9a-f]+) ACTUAL ([0-9a-f]+)',host)
 expected,actual=echo.groups()
 assert actual==decoded['boundaries']['transport_response']
 assert decoded['boundaries']['transport_rx']==decoded['boundaries']['csr_accept']=='ed0f2143'
 assert decoded['all_six_match']==(mode=='ff')
 result=dict(mode=mode,test_id='ISO2-1',candidate_sha256=gate['bitstream_sha256'],
  internal_sta=gate,uart=decoded,expected=expected,host_actual=actual,
  xor=bytes(a^b for a,b in zip(bytes.fromhex(expected),bytes.fromhex(actual))).hex(),
  outcome='PASS_LIMITED_4B' if mode=='ff' else 'FAIL_FIRST_AT_UPLOAD_OUTPUT',
  sram_program_count=1,restore_reprogram_count=1,retries=0,
  configured_qspi_sck_hz=1000000,pad_clock_measured=False,
  psram_transfers=0,fpga_flash_writes=0,rp2040_flash_writes=0,fw_files_changed=False,
  flash_hash_before_after=flash,restore_banner_confirmed=True,hdmi_restored_visually_confirmed=True,
  hdmi_restore_image_sha256=sha(image),
  release_ready=False)
 (out/'decoded.json').write_text(json.dumps(decoded,indent=2)+'\n')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 (out/'evidence-sha256.json').write_text(json.dumps({p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'},indent=2)+'\n')
 (root/f'docs/evidence/host-window-{mode}-2026-11-05.json').write_text(json.dumps(result,indent=2)+'\n')
 (root/f'docs/evidence/host-window-{mode}-uart-2026-11-05.hex').write_text(raw.hex()+'\n')
 cases[mode]=result
manifests={mode:{v['path']:v['sha256'] for v in json.loads((base/f'standard-{mode}/source-manifest.json').read_text())} for mode in ('sp','ff')}
shared=manifests['sp'].keys()&manifests['ff'].keys()
assert all(manifests['sp'][k]==manifests['ff'][k] for k in shared)
differences={mode:sorted(manifests[mode].keys()-shared) for mode in ('sp','ff')}
assert differences['sp']==['diagnostics/host-window-observe/build.tcl','rtl/fb/kagura_fb_upload_word.sv']
assert differences['ff']==['diagnostics/host-window-observe/build-ff.tcl','diagnostics/host-window-observe/kagura_fb_upload_word_ff.sv']
protected={
 'build/rx32-scanout-worktree/build/kagura-fb-qspi/impl/pnr/kagura_fb.fs':'a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf',
 'build/psram-probe-standard/candidate-v3/impl/pnr/psram_probe.fs':'f6619b747171c92ea9fdb0aa562acfadfdf7af37940d2d6286b9535eebca62ac',
 'build/rx32-scanout-worktree/DO_NOT_PROGRAM.txt':'d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546'}
for name,value in protected.items():assert sha(root/name)==value
summary=dict(date='2026-11-05',observed_first_bad_boundary='CSR accepted bytes -> upload SP output',
 ff_counterfactual_all_six_match=True,source_differences=differences,shared_input_hashes_match=True,
 exact_cause='UNRESOLVED: SP configuration/byte-enable support or port timing/implementation',
 original_psram_failure_same_cause='UNPROVEN',additional_sram_programs=2,restores=2,
 flash_writes=0,release_ready=False,protected_artifacts=protected,
 hardware_cases={m:r['candidate_sha256'] for m,r in cases.items()})
(base/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
(root/'docs/evidence/host-window-comparison-2026-11-05.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
