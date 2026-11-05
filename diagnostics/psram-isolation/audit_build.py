"""Audit saved Standard outputs and immutable compile inputs. No hardware IO."""
from pathlib import Path
import hashlib
import html
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
build=ROOT/sys.argv[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
status=json.loads((build/'timing-status.json').read_text(encoding='utf-8-sig'))
log=(build/'build.log').read_text()
assert 'Placement and routing completed' in log and 'Bitstream generation completed' in log
assert not re.search(r'ERROR|[Uu]nrouted|[Rr]outing failed',log)
assert status['setup_violated_endpoints']==status['hold_violated_endpoints']==0
assert status['worst']['Setup']['slack_ns']>=.100 and status['worst']['Hold']['slack_ns']>=0
assert not status['negative_analyses']
compiled=[]
for item in json.loads((build/'source-manifest.json').read_text()):
    # The initial broad manifest also lists PC-only helper scripts. They are
    # not synthesis inputs; their final hashes are recorded separately below.
    relative=Path(item['path'])
    if relative.suffix not in ('.sv','.tcl','.cst','.sdc'):continue
    source=ROOT/relative
    assert sha(source)==item['sha256'], str(relative)
    compiled.append(item)
    target=build/'inputs'/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert sha(target)==item['sha256']
    else:target.write_bytes(source.read_bytes())
vg=(build/'impl/gwsynthesis/host_isolation.vg').read_text()
for stem,constant in [('O_psram_cs_n','VCC'),('O_psram_ck','GND'),('O_psram_ck_n','VCC'),('O_psram_reset_n','GND')]:
    for i in range(2):
        assert re.search(r'OBUF\s+\S+\s*\(\s*\.O\('+re.escape(f'{stem}[{i}]')+r'\),\s*\.I\('+constant+r'\)',vg)
for stem,width in [('IO_psram_dq',16),('IO_psram_rwds',2),('sd_hiz',4)]:
    for i in range(width):
        assert re.search(r'TBUF\s+\S+\s*\(\s*\.O\('+re.escape(f'{stem}[{i}]')+r'\),\s*\.I\(GND\),\s*\.OEN\(VCC\)',vg)
assert not re.search(r'module kagura_(?:fb_core|fb_burst_ctrl|hyperram_phy_gowin)\b',vg)
pin=(build/'impl/pnr/host_isolation.pin.html').read_text()
rows={}
for row in re.findall(r'<tr>(.*?)</tr>',pin,re.S):
    fields=[html.unescape(re.sub('<[^>]*>','',v)).strip() for v in re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)]
    if len(fields)==17 and fields[0] not in rows:rows[fields[0]]=fields
cst=(ROOT/'diagnostics/psram-isolation/host-isolation.cst').read_text()
for port,location in re.findall(r'IO_LOC "([^"]+)" (\d+);',cst):
    assert rows[port][2].split('/')[0]==location,(port,rows.get(port))
for port,kind in re.findall(r'IO_PORT "([^"]+)" IO_TYPE=(\w+)',cst):
    assert rows[port][7]==kind,(port,rows[port])
for stem,width in [('O_psram_cs_n',2),('O_psram_ck',2),('O_psram_ck_n',2),('O_psram_reset_n',2),('IO_psram_dq',16),('IO_psram_rwds',2)]:
    for i in range(width):
        row=rows[f'{stem}[{i}]']
        assert row[7]=='LVCMOS18' and row[2].startswith(('p1-','p2-')),row
timing=(build/'impl/pnr/host_isolation_tr_content.html').read_text()
for name in ['sck_sync_0_s0/D','cs_sync_0_s0/D',*(f'io_sync0_{i}_s0/D' for i in range(4))]:
    assert name in timing and name.split('/')[0] in vg
assert 'create_generated_clock -name sys54' in timing
rpt=(build/'impl/pnr/host_isolation.rpt.txt').read_text()
assert '<Part Number>: GW1NR-LV9QN88PC6/I5' in rpt and '<Tool Version>: V1.9.12.04 (64-bit)' in rpt
resources={}
for label in ['Logic','Register','CLS','BSRAM','DSP']:
    match=re.search(r'^  '+label+r'\s+\|\s+(\d+)/(\d+)',rpt,re.M)
    assert match,label
    resources[label]=[int(x) for x in match.groups()]
fs=build/'impl/pnr/host_isolation.fs'
result=dict(scope='ISO1 Host/CSR isolation; internal STA; PSRAM held inactive',
    numeric_sta_pass=True,setup_slack_ns=status['worst']['Setup']['slack_ns'],
    hold_slack_ns=status['worst']['Hold']['slack_ns'],setup_violations=0,hold_violations=0,
    routing_completed=True,resources=resources,bitstream_sha256=sha(fs),
    pin_constraints_match=True,psram_inactive_netlist_verified=True,
    psram_external_timing='not exercised: static CS high, reset low, DQ/RWDS Hi-Z',
    host_external_timing='asynchronous oversampled; board min/max unverified; initial SCK 1MHz only',
    hardware_tested=False,release_ready=False,sram_programming_authorized=False,
    compile_inputs=compiled)
(build/'diagnostic-gate.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='compile_inputs'},indent=2))
