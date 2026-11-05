"""Repeatable PC workload sweep. Durations are CPU/model times, not bus timings."""
import json,time,statistics
from preview import Engine,R
rows=[]
for variant in ('baseline','optimized'):
 e=Engine(variant)
 for op,name in enumerate(['FENCE','FILL32x16','BLIT32x32','PRESENT','PSRAM_WRITE','PSRAM_READ','PCM_command','PALETTE']):
  for n in ([1,2,4,8,16,64,512] if op in (4,5) else [32]):
   before=e.counts();ts=[]
   for _ in range(64):
    start=time.perf_counter_ns();assert e.lib.pc_bench(op,n)==0;ts.append((time.perf_counter_ns()-start)/1000)
   after=e.counts();rows.append({'variant':variant,'op':name,'length':n,'iterations':64,'cpu_model_mean_us':statistics.mean(ts),'cpu_model_worst_us':max(ts),'transactions':after[0]-before[0],'wire_bytes':after[1]-before[1],'hardware_us':None})
loads=[]
for kind,values,epoch in [('stars',[64,128,256],10000),('objects',[8,16,32,64,128],95000)]:
 for n in values:
  e=Engine();e.lib.pc_load(n if kind=='stars' else 64,n if kind=='objects' else 32);before=e.counts();ts=[]
  for t in range(epoch,epoch+2000,33):
   start=time.perf_counter_ns();e.tick(t);ts.append((time.perf_counter_ns()-start)/1000)
  after=e.counts();delta=[a-b for a,b in zip(after,before)];loads.append({'kind':kind,'count':n,'frames':len(ts),'logical_seconds':2,'transactions':delta[0],'wire_bytes':delta[1],'gpu_commands':delta[2],'blit_pixels':delta[4],'gpu_errors':delta[6],'busy_overwrites':delta[7],'cpu_model_mean_us':statistics.mean(ts),'cpu_model_worst_us':max(ts),'actual_fps_hardware':None,'fence_wait_hardware_us':None})
(R/'evidence/benchmarks.json').write_text(json.dumps({'scope':'PC C SDK/native model, 3 status polls/command; not physical measurements','operations':rows,'load_sweep':loads},indent=2));print('benchmarks',len(rows),'loads',len(loads))
