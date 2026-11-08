"""PC pixel equivalence of baseline/merged glyphs through the actual C engine.
Uses separate shared libraries and does not overwrite prior evidence/previews.
"""
from pathlib import Path
import ctypes as C,json,hashlib,sys,zlib
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/queue-wait-tests'
times=[0,1000,10000,30000,50000,70000,95000,120000,140000,142999,143000,143034,143068,145555,149999]
libs=[]
for flag in (0,1):
 l=C.CDLL(str(OUT/f'lettering-{flag}.so'))
 l.pc_init.argtypes=[C.c_uint32,C.c_int];l.pc_tick.argtypes=[C.c_uint32]
 l.pc_memory.restype=C.POINTER(C.c_uint8);l.pc_palette.restype=C.POINTER(C.c_uint16)
 l.pc_counts.restype=C.POINTER(C.c_uint64)
 libs.append(l)
rows=[]
for seed in (0xb1616,19,73):
 for l in libs:assert l.pc_init(seed,1)==0
 for ms in times:
  for l in libs:assert l.pc_tick(ms)==0
  memory=[C.string_at(l.pc_memory(),230400) for l in libs]
  assert memory[0]==memory[1],(seed,ms,'pixels')
  assert [*libs[0].pc_palette()[:16]]==[*libs[1].pc_palette()[:16]]
  assert libs[0].pc_page()==libs[1].pc_page()
  rows.append(dict(seed=seed,ms=ms,framebuffers_crc32=zlib.crc32(memory[0]),
   baseline_commands=libs[0].pc_counts()[2],merged_commands=libs[1].pc_counts()[2]))
 # Both pages receive their first scheduled lettering after 143000; comparison
 # covers page alternation and subsequent static reuse.
 assert rows[-1]['merged_commands']<rows[-1]['baseline_commands']
report=dict(passed=True,comparisons=len(rows),scope='Both 115200-byte framebuffers, active palette and displayed page; functional model, not physical timing',rows=rows)
(OUT/'lettering-equivalence.json').write_text(json.dumps(report,indent=2))
print('PASS lettering: 45 full two-page comparisons, palette/page equality, three seeds, reduced command count')
print(json.dumps(rows[-6:],indent=2))
