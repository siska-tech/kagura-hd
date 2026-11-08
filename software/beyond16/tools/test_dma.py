"""Compile the actual transport against a finite FIFO/DMA seam; no device access."""
import ctypes as C
import json
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parents[1]
VC = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
OUT = R/'out/headroom-tests'
OUT.mkdir(exist_ok=True)
rows = []
for variant, threshold in ((0, 0), (1, 0), (2, 0), (2, 128)):
    name = f'v{variant}t{threshold}'
    cmd = (f'call "{VC}" >nul && cl /nologo /LD /O2 /std:c11 '
           f'/DB16_TRANSPORT={variant} /DB16_DMA_THRESHOLD={threshold} /DB16_PROFILE=2 '
           f'/I"{R}/tests" /I"{R}/tests/fake_sdk" /I"{R}/src" /I"{R}/out/rp2040" '
           f'"{R}/tests/transport_fake.c" "{R}/src/b16_qspi.c" "{R}/src/b16_profile.c" '
           f'/Fo"{OUT}/" /link /IMPLIB:"{OUT}/{name}.lib" /OUT:"{OUT}/{name}.dll" /EXPORT:mt_qspi_init /EXPORT:mt_qspi_deinit')
    subprocess.run('cmd.exe /d /c '+cmd, check=True)
    l = C.CDLL(str(OUT/f'{name}.dll'))
    l.fake_write.argtypes = [C.c_uint,C.c_bool,C.c_void_p,C.c_size_t]
    l.fake_read.argtypes = l.fake_write.argtypes
    l.fake_dma_count.restype = C.c_uint64
    l.fake_profile_us.restype = C.c_uint64
    l.fake_work.restype = C.c_uint32
    l.fake_reset(); l.fake_profile_init(); assert l.mt_qspi_init() == 0
    for n in (1,2,4,8,16,32,64,128,256,512):
        a = (C.c_uint8*n)(*[i&255 for i in range(n)])
        before = l.fake_get(0,0); dma = l.fake_dma_count()
        assert l.fake_write(25,False,a,n) == 0
        assert [l.fake_get(1,before+i+1)>>22 for i in range(n)] == list(a)
        expected = variant == 1 and n >= 64 or variant == 2 and threshold and n >= threshold
        assert l.fake_dma_count()-dma == bool(expected)
        assert l.fake_get(6,0) == 1 and l.fake_get(21,0) == 0
    a = (C.c_uint8*512)(*[i&255 for i in range(512)])
    for n in (1,2,4,8,16,32,64,128,256):
        b = (C.c_uint8*n)(); before=l.fake_get(0,0); dma=l.fake_dma_count()
        assert l.fake_read(25,False,b,n) == 0 and bytes(b)==bytes([255])*n
        words=[l.fake_get(1,before+i) for i in range(n+3)]
        assert words[1] & (1<<30) and not any(w & (1<<30) for w in words[2:])
        assert l.fake_get(7,0)&60 == 0 and l.fake_dma_count()==dma
    # TX blocked, RX lost, and wire terminal PC stuck after DMA completion.
    modes = (1,2,3,6,7,11) if variant and (variant==1 or threshold) else (1,2,3)
    for mode in modes:
        l.fake_reset(); assert l.mt_qspi_init()==0; l.fake_mode(mode)
        assert l.fake_write(25,False,a,512)==(-2 if mode==11 else -3)
        assert l.fake_get(6,0)==1 and l.fake_get(7,0)&60==0 and l.fake_get(21,0)==0
        before=l.fake_get(0,0)
        assert l.fake_write(26,False,a,1)==-2 and before==l.fake_get(0,0)
    l.fake_reset(); l.fake_clock(125000000); assert l.mt_qspi_init()==-1
    if variant:
        for mode in (9,10):
            l.fake_reset(); l.fake_mode(mode); assert l.mt_qspi_init()==-2
            l.fake_mode(0); assert l.mt_qspi_init()==0; l.mt_qspi_deinit()
    l.fake_reset(); l.fake_profile_init()
    l.fake_push(1); l.fake_time(); l.fake_push(2); l.fake_time(); l.fake_pop(); l.fake_pop()
    assert l.fake_profile_us(1)==3 and l.fake_profile_us(2)==2
    x=0xb1616
    for i in range(64):
        x=(x^(x<<13))&0xffffffff; x^=x>>17; x=(x^(x<<5))&0xffffffff
        x=(x+0x9e3779b9+i)&0xffffffff
    assert l.fake_work(0xb1616,64)==x
    rows.append(dict(variant=variant,threshold=threshold,lengths='PASS',read_release='PASS',
                     fault_latch_no_retry='PASS',dma_stop_cs_release='PASS',profile_work='PASS'))
(R/'evidence/dma-fake.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))

