"""Deterministic lossless LZ for streaming BGM; 32KiB history, no runtime heap."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def compress(src):
 out=bytearray();pending=bytearray();table={};pos=0
 def flush():
  if pending:out.append(len(pending)-1);out.extend(pending);pending.clear()
 while pos<len(src):
  key=src[pos:pos+3];best=0;distance=0
  for old in reversed(table.get(key,[])[-8:]):
   if pos-old>32768:continue
   n=0
   while n<130 and pos+n<len(src) and src[old+n]==src[pos+n]:n+=1
   if n>best:best=n;distance=pos-old
  if best>=4:
   flush();out.append(128|(best-3));out.extend((distance-1).to_bytes(2,'little'));step=best
  else:
   pending.append(src[pos]);step=1
   if len(pending)==128:flush()
  for at in range(pos,pos+step):
   k=src[at:at+3];lst=table.setdefault(k,[]);lst.append(at)
   if len(lst)>8:del lst[0]
  pos+=step
 flush();return bytes(out)
if __name__=='__main__':
 src=(ROOT/'generated/bgm.s8').read_bytes();packed=compress(src);(ROOT/'generated/bgm.lz').write_bytes(packed)
 (ROOT/'generated/bgm-lz.inc').write_text('static const uint8_t bgm_lz[]={\n'+',\n'.join(','.join(map(str,packed[i:i+64])) for i in range(0,len(packed),64))+'\n};\n')
 report={'original_bytes':len(src),'packed_bytes':len(packed),'sha256_original':hashlib.sha256(src).hexdigest(),'sha256_packed':hashlib.sha256(packed).hexdigest(),'codec':'literal1..128 or 3..130 byte LZ match / uint16 distance-1 / 32KiB history'}
 (ROOT/'generated/bgm-pack.json').write_text(json.dumps(report,indent=2));print(report)
