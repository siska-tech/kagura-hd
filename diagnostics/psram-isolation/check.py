"""Verify offline evidence, provenance and independent oracle invariants."""
from pathlib import Path
import hashlib
import json
from oracle import FIXED, pattern, chunks, guards

root = Path(__file__).resolve().parents[2]
out = root / 'build/psram-isolation'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
past = json.loads((root/'build/psram-probe-standard/candidate-v3/source-manifest.json').read_text())
current = json.loads((root/'build/rx32-scanout-worktree/build/analysis/standard-input-manifest.json').read_text())
for item in json.loads((out/'baseline-manifest.json').read_text()):
    relative = item['source'].replace('\\', '/')
    if item['label'] == 'fail':
        relative = relative.split('build/rx32-scanout-worktree/')[1]
        expected = current[relative]
    else:
        expected = next(x['sha256'] for x in past if x['path']==relative)
    assert item['sha256'].lower() == expected.lower()
    assert sha(out/'baseline'/item['label']/relative) == expected.lower()
for relative in ('rtl/fb/kagura_fb_host.sv', 'rtl/fb/kagura_fb_registers.sv',
                 'rtl/fb/kagura_fb_commands.sv', 'rtl/fb/kagura_fb_upload_word.sv'):
    assert sha(root/relative) == current[relative].lower(), relative
logs = {}
for name in ('p0', 'p1', 'capture', 'host1', 'host4'):
    path = out/(name+'.run.log')
    content = path.read_text()
    assert 'PASS:' in content and '%Fatal' not in content, name
    logs[name] = sha(path)
for address in (300032,300060,300064,1048576,4194240):
    for length in (4,8,16,32,64):
        plan = chunks(address,length)
        assert sum(x['length'] for x in plan)==length
        assert all(x['address']//32==(x['address']+x['length']-1)//32 for x in plan)
        assert all(g//32 < address//32 or g//32 > (address+length-1)//32 for g in guards(address,length))
        for name in (*FIXED,'walking1','walking0','address','random'):
            assert len(pattern(name,address,length))==length
assert pattern('ed0f2143',300032,4)==bytes.fromhex('ed0f2143')
assert [x['length'] for x in chunks(300060,64)]==[4,32,28]
assert chunks(300032,4)[0]['ca_write']=='200049400000'
evidence = dict(scope='initial independent PC functional suite',pc_functional_pass=True, hardware_tested=False, release_ready=False,
                new_bitstream_generated=any((root/'build/host-isolation-standard').glob('*/impl/pnr/host_isolation.fs')), log_sha256=logs,
                oracle_checks='range/chunk/guard/pattern/CA invariants PASS')
(out/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps(evidence,indent=2))
