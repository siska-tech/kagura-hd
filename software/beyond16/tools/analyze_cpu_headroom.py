"""Offline CPU headroom bounds. These are wall-time buckets, not CPU utilization."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
s=json.loads((R/'evidence/host-ab-ON/demo-result.json').read_text())
def bucket(ps):
 a,b=ps[0],ps[-1];wall=(b['ms']-a['ms'])/1000;frame=(b['frame_sum_us']-a['frame_sum_us'])/1e6;host=(b['transaction_us']-a['transaction_us'])/1e6
 return {'window_s':wall,'frame_call_s':frame,'outside_frame_s':wall-frame,'outside_frame_fraction':(wall-frame)/wall,'host_callback_s':host,'host_callback_fraction':host/wall,'frame_nonhost_s':frame-host,'current_spare_cpu_s':None,'async_recoverable_cpu_s':None}
r={'scope':'recorded core0 wall-time bounds, not utilization; callbacks include active CPU work and waits','whole':bucket(s['perf']),'scenes':{str(i):bucket([p for p in s['perf'] if p['scene']==i]) for i in range(8)},'caveat':'PERF timestamps precede frame call but counters follow it; endpoints are not perfectly aligned. Interrupt CPU time not separated.'}
(R/'evidence/cpu-headroom-bounds.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r['whole'],indent=2))
