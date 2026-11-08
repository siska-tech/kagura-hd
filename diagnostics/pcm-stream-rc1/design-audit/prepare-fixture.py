from pathlib import Path
import re,hashlib,json
out=Path(__file__).resolve().parent
root=out.parents[2]
p=root/'software/beyond16/generated/assets.inc'
s=p.read_text()
src=list(map(int,re.search(r'frame_lz\[\]\s*=\s*\{([^}]+)',s).group(1).split(',')))
data=[]; i=0
while i<len(src):
    ctrl=src[i];i+=1
    if ctrl<128:
        n=ctrl+1;data.extend(src[i:i+n]);i+=n
    else:
        n=(ctrl&127)+3;back=1+src[i]+256*src[i+1];i+=2
        for _ in range(n): data.append(data[-back])
assert len(data)==640*360//2
(out/'frame.hex').write_text(''.join(f'{x:02x}\n' for x in data))
pal=list(map(int,re.search(r'b16_pal\[16\]\s*=\s*\{([^}]+)',s).group(1).split(',')))
(out/'palette.hex').write_text(''.join(f'{x:03x}\n' for x in pal))
(out/'fixture.json').write_text(json.dumps({'source':str(p.relative_to(root)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frame_bytes':len(data),'frame_sha256':hashlib.sha256(bytes(data)).hexdigest(),'note':'Current saved assets; historical ELF input hash not attested.'},indent=2))
