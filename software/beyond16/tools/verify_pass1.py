import sys,json,ctypes as C
sys.path.insert(0,'software/beyond16/tools')
from preview import Engine,R
old=Engine();old.lib=C.CDLL(str(R/'out/optimization-before/optimized.dll'));l=old.lib
l.pc_memory.restype=C.POINTER(C.c_uint8);l.pc_counts.restype=C.POINTER(C.c_uint64);l.pc_palette.restype=C.POINTER(C.c_uint16)
assert l.pc_init(0xb1616,1)==0
new=Engine();n=0
for t in range(0,150000,33):
 old.tick(t);new.tick(t);n+=1
 assert old.memory()==new.memory(),t
 assert old.lib.pc_palette()[:16]==new.lib.pc_palette()[:16],t
rows={'frames':n,'old_counts':old.counts(),'new_counts':new.counts(),'both_pages_and_palette_equal':True}
(R/'evidence/optimization-pass1.json').write_text(json.dumps(rows,indent=2));print(rows)
