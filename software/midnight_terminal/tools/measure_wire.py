"""Full C SDK + independent register-model run; bytes are PC protocol accounting."""
import ctypes as C,json,time,statistics
from test_device import Harness
from preview import ROOT,CALL
h=Harness();buf=C.create_string_buffer(h.lib.mt_size());cb=CALL(lambda _,op,a,p,n:h.lib.mt_device_emit(h.adapter,op,a,p,n));h.lib.mt_init(buf,cb,None,1)
times=[];per_second={};last_commands=0;last_bytes=0
for ms in range(0,88000,33):
 before=time.perf_counter();rc=h.lib.mt_tick(buf,ms,0);assert rc==0,(rc,h.errors);times.append((time.perf_counter()-before)*1000)
 key=ms//1000
 if key not in per_second:per_second[key]={'commands':0,'register_bytes':0}
 per_second[key]['commands']+=len(h.model.commands)-last_commands;last_commands=len(h.model.commands)
 total=h.traffic['read_bytes']+h.traffic['write_bytes'];per_second[key]['register_bytes']+=total-last_bytes;last_bytes=total
report={'scope':'88s logical autoplay through actual existing C SDK and independent PC register model; no hardware','release_ready':False,'pcm_startup_included':True,'commands':len(h.model.commands),'traffic':h.traffic,'pc_tick_ms_mean':statistics.mean(times),'pc_tick_ms_p95':sorted(times)[int(len(times)*.95)],'pc_tick_ms_max':max(times),'logical_seconds':per_second,'real_hardware_fps':None,'real_fence_ms':None}
(ROOT/'out/wire-report.json').write_text(json.dumps(report,indent=2));(ROOT/'out/wire-descriptors.jsonl').write_text('\n'.join(json.dumps({'index':i,'hex':c.hex()}) for i,c in enumerate(h.model.commands)))
print(json.dumps({k:v for k,v in report.items() if k!='logical_seconds'},indent=2))
