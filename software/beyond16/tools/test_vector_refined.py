import sys,ctypes as C,json
sys.path.insert(0,'software/beyond16/tools')
from preview import Engine,R
old=Engine();old.lib=C.CDLL(str(R/'out/vector-lowres-before/optimized.dll'));old.lib.pc_memory.restype=C.POINTER(C.c_uint8);old.lib.pc_counts.restype=C.POINTER(C.c_uint64);old.lib.pc_palette.restype=C.POINTER(C.c_uint16);assert old.lib.pc_init(0xb1616,1)==0
new=Engine();a=old.counts();b=new.counts()
for t in range(120000,140000,33):
 old.tick(t);new.tick(t);assert old.memory()==new.memory(),t
r={'frames':607,'before':[x-y for x,y in zip(old.counts(),a)],'after':[x-y for x,y in zip(new.counts(),b)],'both_pages_equal':True,'hardware':'NOT RUN'}
(R/'evidence/vector-refined.json').write_text(json.dumps(r,indent=2));print(r)
