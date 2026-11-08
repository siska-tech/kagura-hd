"""Analyze captured logs only. Does not connect to hardware."""
import argparse,json,re,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('log',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();frames=[]
for line in a.log.read_text(errors='replace').splitlines():
    if line.startswith('FRAME '):
        row={k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)}
        if 'present_after_us' in row and 'draw_start_us' in row:frames.append(row)
def delta(b,a):return (b-a)&0xffffffff
def metrics(intervals):
    if not intervals:return None
    s=sorted(intervals)
    return dict(median_us=statistics.median(s),p95_us=s[min(len(s)-1,(len(s)*95+99)//100-1)],
                worst_us=max(s),over_33_333ms_rate=sum(v>100000/3 for v in s)/len(s))
scenes=[]
for scene in range(8):
    f=[r for r in frames if r['scene']==scene]
    intervals=[delta(y['present_after_us'],x['present_after_us']) for x,y in zip(f,f[1:])]
    elapsed=sum(intervals)
    scenes.append(dict(scene=scene,frames=len(f),actual_update_fps=(len(intervals)*1e6/elapsed if elapsed else None),
                       present_intervals=metrics(intervals),
                       deadline_miss_rate=(sum(0<delta(r['present_after_us'],r['deadline_us'])<0x80000000 for r in f)/len(f) if f and all('deadline_us' in r for r in f) else None),
                       relative_call_budget_miss_rate=(sum(delta(r['present_after_us'],r['draw_start_us'])>100000/3 for r in f)/len(f) if f else None)))
transitions=[dict(from_scene=x['scene'],to_scene=y['scene'],present_gap_us=delta(y['present_after_us'],x['present_after_us']),
                  next_draw_gap_us=delta(y['draw_start_us'],x['present_after_us'])) for x,y in zip(frames,frames[1:]) if x['scene']!=y['scene']]
a.output.write_text(json.dumps(dict(scenes=scenes,transitions=transitions,
    timing='CPU-observed SDK PRESENT completion after DONE/tag/error/ack, not HDMI scanout timestamp',
    absolute_deadline_miss='requires selected scheduler deadline; call-budget miss is reported separately',
    cpu_headroom='NOT MEASURED',release_ready=False),indent=2))
