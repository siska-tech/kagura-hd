"""Verify both local firmware images and bundle the generic runtime files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


def verify(directory,nm):
    raw=(directory/'firmware.bin').read_bytes()
    uf2=(directory/'kagura-micropython.uf2').read_bytes()
    assert len(raw)<=655360 and len(uf2)%512==0
    import struct
    rebuilt=bytearray(b'\xff'*((len(raw)+255)//256*256))
    seen=set()
    for offset in range(0,len(uf2),512):
        block=uf2[offset:offset+512]
        a,b,flags,address,n,index,count,family=struct.unpack_from('<8I',block)
        assert (a,b)==(0x0a324655,0x9e5d5157)
        assert struct.unpack_from('<I',block,508)[0]==0x0ab16f30
        assert flags&0x2000 and family==0xe48bff56 and n==256
        assert count==len(uf2)//512 and index not in seen
        seen.add(index)
        start=address-0x10000000
        assert 0<=start<len(raw) and start+n<=655360
        rebuilt[start:start+n]=block[32:32+n]
    assert rebuilt[:len(raw)]==raw and len(seen)==(len(raw)+255)//256
    assert b'MIDNIGHT TERMINAL' not in raw
    frozen=(directory/'frozen_content.c').read_text()
    for name in ('kagura_gpu','kagura_fm','kagura_repl','kagura_keyboard','kagura_terminal','kagura_framebuf'):
        assert '// frozen module '+name+'\n' in frozen
    assert '// frozen module midnight_' not in frozen
    assert 'MODULE_DEF__KAGURA' in (directory/'genhdr/moduledefs.h').read_text()
    symbols=subprocess.check_output([str(nm),str(directory/'firmware.elf')],text=True)
    assert not re.search(r'\b(show_init|show_frame|img_title|img_bar|P_EP|build_script_events|midnight_module)$',symbols,re.M)
    assert re.search(r'\bfm_render$',symbols,re.M)
    return dict(firmware_bytes=len(raw),uf2_sha256=hashlib.sha256(uf2).hexdigest(),
                uf2_matches_binary=True,application_code_and_assets_embedded=False,
                framebuffer_repl_and_keyboard_modules=True)


if __name__=='__main__':
    root=Path(__file__).resolve().parents[3]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=root/'build/kagura-runtime')
    parser.add_argument('--nm',type=Path,default=root/'software/midnight_terminal/toolchain/arm/bin/arm-none-eabi-nm.exe')
    args=parser.parse_args()
    result=dict(builds={name:verify(args.directory/name,args.nm) for name in ('qspi','spi')},hardware_tested=False)
    (args.directory/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    with zipfile.ZipFile(args.directory/'kagura-runtime.zip','w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(root/'software/kagura_runtime/README.md','README.md')
        archive.write(args.directory/'verification.json','verification.json')
        for name in ('qspi','spi'):
            archive.write(args.directory/name/'kagura-micropython.uf2',name+'/kagura-micropython.uf2')
        for path in (args.directory/'files').rglob('*'):
            if path.is_file(): archive.write(path,str(path.relative_to(args.directory)))
    print(json.dumps(result,indent=2))
