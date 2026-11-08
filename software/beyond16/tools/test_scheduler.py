"""Logical scheduler tests and wrap-safe log parser checks; no timing claims."""
import ctypes as C
import json
import subprocess
import sys
from preview import R

rows=[]
for name,expected in [('off',list(range(0,150000,33))),
                       ('absolute',[(i*1000+29)//30 for i in range(4500)])]:
    l=C.CDLL(str(R/f'out/headroom-variants/{name}.dll'))
    l.pc_counts.restype=C.POINTER(C.c_uint64)
    assert l.pc_init(0xb1616,1)==0
    previous=l.pc_counts()[3];accepted=[]
    for t in range(150000):
        assert l.pc_tick(t)==0
        count=l.pc_counts()[3]
        if count!=previous:
            assert count==previous+1;accepted.append(t);previous=count
    assert accepted==expected,(name,len(accepted),len(expected))
    assert l.pc_init(0xb1616,1)==0
    assert l.pc_tick(0)==0
    assert l.pc_tick(50000)==0
    before=l.pc_counts()[3]
    for t in range(50001,50010):assert l.pc_tick(t)==0
    assert l.pc_counts()[3]==before
    rows.append(dict(variant=name,frames=len(accepted),logical_1ms_tick='PASS',late_no_catchup='PASS'))

out=R/'out/headroom-tests';out.mkdir(exist_ok=True)
base=0xffff0000
def low(n):return n&0xffffffff
data=[]
for i,elapsed in enumerate((0,33333,83333,150000)):
    done=base+elapsed
    data.append(f'FRAME ms={i*33} scene={0 if i<3 else 1} us=1000 present_before_us={low(done-1000)} present_after_us={low(done)} draw_start_us={low(done-2000)} deadline_us={low(done+(100 if i!=2 else -100))}')
(out/'parser-fixture.log').write_text('\n'.join(data))
subprocess.run([sys.executable,str(R/'tools/analyze_headroom_log.py'),str(out/'parser-fixture.log'),'--output',str(out/'parser-fixture.json')],check=True)
parsed=json.loads((out/'parser-fixture.json').read_text())
assert parsed['scenes'][0]['present_intervals']['worst_us']==50000
assert parsed['scenes'][0]['deadline_miss_rate']==1/3
assert parsed['transitions'][0]['present_gap_us']==66667
(R/'evidence/headroom-scheduler-tests.json').write_text(json.dumps(dict(
    variants=rows,parser_wrap_percentiles_deadline='PASS',physical_timing='NOT RUN'),indent=2))
print(rows)
