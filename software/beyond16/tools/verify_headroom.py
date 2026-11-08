"""Offline protection, firmware identity and ELF memory bounds. No device tools."""
import hashlib,json,struct
from pathlib import Path

R=Path(__file__).resolve().parents[1]; ROOT=R.parents[1]; E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=json.loads((E/'headroom-protected-before.json').read_text())
assert all(sha(ROOT/r['path'])==r['sha256'] for r in protected),'Protected file changed'
prior=json.loads((E/'protection.json').read_text())
assert sha(ROOT/prior['bitstream'])==prior['bitstream_sha256']
for name in ('original_backup','last_native_flash_snapshot'):
    assert sha(ROOT/prior[name]['path'])==prior[name]['sha256']

def elf_map(path):
    b=path.read_bytes();assert b[:6]==b'\x7fELF\x01\x01'
    off=struct.unpack_from('<I',b,32)[0];entry,n,string=struct.unpack_from('<HHH',b,46)
    sections=[struct.unpack_from('<10I',b,off+i*entry) for i in range(n)]
    def contents(s):return b[s[4]:s[4]+s[5]]
    names=contents(sections[string])
    cstr=lambda data,start:data[start:data.index(0,start)].decode()
    symbols={};allocated=[]
    for s in sections:
        name=cstr(names,s[0])
        if s[2]&2 and s[5]:allocated.append(dict(name=name,address=hex(s[3]),bytes=s[5],type=s[1],flags=s[2]))
        if s[1]==2:
            strings=contents(sections[s[6]])
            for j in range(0,s[5],s[9]):
                no,value,size,info,other,ndx=struct.unpack_from('<IIIBBH',b,s[4]+j)
                if no:
                    key=cstr(strings,no)
                    if key in ('__bss_end__','__StackBottom','__StackTop','__StackLimit','__flash_binary_end','engine','frame_log','history','dma_words','dma_sink','star_seed_cache','profile_snapshot'):
                        symbols[key]=dict(address=hex(value),bytes=size)
    assert int(symbols['__bss_end__']['address'],16)<=int(symbols['__StackBottom']['address'],16)
    return dict(sections=allocated,symbols=symbols)

firmware=json.loads((E/'headroom-firmware.json').read_text(encoding='utf-8-sig'))
maps=[]
for f in firmware:
    name=f['variant']['Name'];folder=R/'out/headroom-firmware'/name
    assert sha(folder/'beyond16.bin')==f['bin_sha256']
    assert sha(folder/'beyond16.elf')==f['elf_sha256']
    size=(folder/'beyond16.bin').stat().st_size;erase=(size+4095)&~4095
    assert erase<=0xa0000
    mapping=elf_map(folder/'beyond16.elf')
    maps.append(dict(variant=name,bin_bytes=size,erase_end=hex(0x10000000+erase),
                     filesystem_start='0x100a0000',**mapping))
(E/'headroom-memory.json').write_text(json.dumps(maps,indent=2))
lines=['# RAM / Flash memory map','', 'ELF section/symbol analysis. Offline bounds only; no device readback.', '',
       '|Variant|Binary B|BSS B (allocated NOBITS)|Firmware erase end|', '|---|---:|---:|---|']
for m in maps:
    bss=sum(s['bytes'] for s in m['sections'] if s['type']==8 and s['name'] in ('.bss','.ram_vector_table','.tbss'))
    lines.append(f"|{m['variant']}|{m['bin_bytes']}|{bss}|{m['erase_end']}|")
lines+=['','Filesystem starts at 0x100a0000; every firmware erase extent stays below it. Stack is reserved at __StackBottom..__StackTop (8192B). bss_end <= StackBottom verified; this is not a runtime stack watermark.',
        '', 'Frame log: 4600 × 24 = 110400B, down from 147200B. VECTOR previous masks: 2 × 7296B. Current mask: 7296B. LZ history: 32768B. DMA staging only in B/C: 2048+4B. Cooperative seed cache only in separate cooperative candidate: 1024B. PSRAM layout remains memory.json.',
        '', 'Exact allocated sections and symbols: [headroom-memory.json](evidence/headroom-memory.json). Per-variant full linker maps: out/headroom-firmware/<variant>/beyond16.elf.map. Existing memory.json and rp2040-build.json are historical and have not been relabeled as current.']
(R/'MEMORY_MAP.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
sources=[R/'CMakeLists.txt',*R.glob('src/*.[ch]'),R.parent/'kagura_fb/kagura_fb.c',R.parent/'kagura_fb/kagura_fb.h',R.parent/'midnight_terminal/vendor/kagura_host.pio',R/'generated/assets.inc']
source_hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sources}
source_manifest=E/'headroom-source-sha256.json'
if source_manifest.exists():
    assert json.loads(source_manifest.read_text(encoding='utf-8-sig'))==source_hashes,'Source changed after firmware freeze; rebuild matrix'
else:
    source_manifest.write_text(json.dumps(source_hashes,indent=2))
(E/'headroom-protection.json').write_text(json.dumps(dict(status='PASS',protected_files=len(protected),
    bitstream_sha256=prior['bitstream_sha256'],backups_unchanged=True,rtl_changes=0,hardware_operations=0,
    firmware_variants=len(firmware),filesystem_bounds='PASS (offline only)',release_ready=False),indent=2))
print('PASS: protection, firmware hashes, RAM and Flash bounds',len(protected),'protected files')
