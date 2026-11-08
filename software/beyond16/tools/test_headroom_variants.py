"""Offline build + full byte comparison for profiling, cooperative, scheduler variants."""
import ctypes as C
import json
import subprocess
from pathlib import Path
from preview import Engine, R

ROOT=R.parents[1]
OUT=R/'out/headroom-variants'; OUT.mkdir(exist_ok=True)
VC=r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'

def build(name, flags, sources, includes=''):
    cmd=f'call "{VC}" >nul && cl /nologo /LD /O2 /std:c11 /DKFB_PACK_DESCRIPTOR=1 {flags} {includes} '
    cmd+=' '.join(f'"{p}"' for p in sources)
    cmd+=f' /Fo"{OUT}/" /link /IMPLIB:"{OUT}/{name}.lib" /OUT:"{OUT}/{name}.dll"'
    subprocess.run('cmd.exe /d /c '+cmd,check=True,capture_output=True)

# Reconstruct the committed baseline in out, without changing the working tree.
snapshot=OUT/'snapshot'
files=['software/beyond16/src/'+f for f in ('b16.c','b16.h','pc.c')]
files+=['software/beyond16/generated/assets.inc','software/kagura_fb/kagura_fb.c',
        'software/kagura_fb/kagura_fb.h','software/midnight_terminal/src/mt_lz.c',
        'software/midnight_terminal/src/mt_lz.h']
for path in files:
    target=snapshot/path;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT))
build('before','',[snapshot/p for p in files if p.endswith('.c')])
sources=[R/'src/b16.c',R/'src/pc.c',R/'src/b16_profile.c',R.parent/'kagura_fb/kagura_fb.c',R.parent/'midnight_terminal/src/mt_lz.c']
def load(path):
    e=Engine.__new__(Engine);e.lib=C.CDLL(str(path))
    e.lib.pc_memory.restype=C.POINTER(C.c_uint8);e.lib.pc_palette.restype=C.POINTER(C.c_uint16)
    e.lib.pc_counts.restype=C.POINTER(C.c_uint64)
    assert e.lib.pc_init(0xb1616,1)==0
    return e

rows=[]
for name,flags,step in [('off','',33),('summary','/DB16_PROFILE=1',33),
                        ('detailed','/DB16_PROFILE=2',33),('coop','/DB16_COOP=1',33),
                        ('absolute','/DB16_SCHEDULER=1',34)]:
    build(name,flags,sources)
    old=load(OUT/'before.dll');new=load(OUT/f'{name}.dll')
    for t in range(0,150000,step):
        old.tick(t);new.tick(t)
        assert old.memory()==new.memory(),(name,t)
        assert list(old.lib.pc_palette()[:16])==list(new.lib.pc_palette()[:16]),(name,t,'palette')
    assert list(new.lib.pc_counts()[6:8])==[0,0]
    rows.append(dict(variant=name,logical_step_ms=step,frames=len(range(0,150000,step)),
                     full_byte_palette_compare='PASS',gpu_errors=0,busy_overwrite=0))
# Save reproducible baseline for the separate 4546-frame replay test.
import shutil
(R/'out/headroom-before').mkdir(exist_ok=True)
shutil.copyfile(OUT/'before.dll',R/'out/headroom-before/optimized.dll')
(R/'evidence/headroom-variants.json').write_text(json.dumps(dict(
    baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    variants=rows,hardware='NOT RUN'),indent=2))
print(rows)
