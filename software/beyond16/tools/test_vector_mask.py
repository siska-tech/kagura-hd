import sys,ctypes as C,json,time
sys.path.insert(0,'software/beyond16/tools')
from preview import Engine,R
old=Engine();old.lib=C.CDLL(str(R/'out/vector-before/optimized.dll'));old.lib.pc_memory.restype=C.POINTER(C.c_uint8);old.lib.pc_counts.restype=C.POINTER(C.c_uint64);old.lib.pc_palette.restype=C.POINTER(C.c_uint16);assert old.lib.pc_init(0xb1616,1)==0
new=Engine();a=old.counts();b=new.counts();cpu=[0,0]
for t in range(120000,140000,33):
 for i,e in enumerate((old,new)):
  start=time.perf_counter_ns();e.tick(t);cpu[i]+=time.perf_counter_ns()-start
 assert old.memory()==new.memory(),t
rows={'frames':607,'before':[x-y for x,y in zip(old.counts(),a)],'mask':[x-y for x,y in zip(new.counts(),b)],'pc_cpu_total_ms':[x/1e6 for x in cpu],'both_pages_equal':True,'hardware_fps':None}
(R/'evidence/vector-mask.json').write_text(json.dumps(rows,indent=2));print(rows)
