"""Every scheduled frame: both framebuffer bytes + palette, old vs candidate."""
import ctypes as C
import hashlib
import json
from preview import Engine, R

def old_engine():
    e = Engine.__new__(Engine)
    e.lib = C.CDLL(str(R/'out/headroom-before/optimized.dll'))
    e.lib.pc_memory.restype=C.POINTER(C.c_uint8)
    e.lib.pc_palette.restype=C.POINTER(C.c_uint16)
    e.lib.pc_counts.restype=C.POINTER(C.c_uint64)
    assert e.lib.pc_init(0xb1616,1)==0
    return e

old=old_engine(); new=Engine(); a=old.counts(); b=new.counts(); digest=hashlib.sha256()
for t in range(0,150000,33):
    old.tick(t); new.tick(t)
    pixels=new.memory(); palette=list(new.lib.pc_palette()[:16])
    assert old.memory()==pixels, ('both framebuffer bytes',t)
    assert list(old.lib.pc_palette()[:16])==palette, ('palette',t)
    assert old.lib.pc_page()==new.lib.pc_page(), ('display page',t)
    digest.update(pixels); digest.update(bytes(v for color in palette for v in (color&255,color>>8)))
before=[x-y for x,y in zip(old.counts(),a)]; after=[x-y for x,y in zip(new.counts(),b)]
assert before[5:]==after[5:]==[0,0,0]
repeat=Engine(); replay=hashlib.sha256()
for t in range(0,150000,33):
    repeat.tick(t); replay.update(repeat.memory())
    replay.update(bytes(v for color in repeat.lib.pc_palette()[:16] for v in (color&255,color>>8)))
assert digest.digest()==replay.digest()
result=dict(seed='0xb1616',frames=len(range(0,150000,33)),both_pages_every_byte='PASS',
            palette_every_frame='PASS',seed_replay='PASS',sha256=digest.hexdigest(),
            before=before,after=after,gpu_errors=0,busy_overwrite=0,hardware='NOT RUN')
(R/'evidence/headroom-render.json').write_text(json.dumps(result,indent=2));print(result)
