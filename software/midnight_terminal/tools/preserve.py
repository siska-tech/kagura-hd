"""Hash protected inputs only; never synthesize or write hardware."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
out=ROOT/'software/midnight_terminal/evidence/protected-inputs.json'
files=[]
for folder in ['rtl','boards','software/kagura_fb','build/pcm2-timing-04/rtl','build/pcm2-timing-04/boards']:
 files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend((ROOT/'build/pcm2-timing-04').rglob('*.fs'))
current={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
if '--check' in sys.argv:
 old=json.loads(out.read_text());assert current==old,'protected inputs changed';print(f'Protected {len(current)} source/constraint/bitstream hashes unchanged')
else:out.write_text(json.dumps(current,indent=2));print(f'Captured {len(current)} protected input hashes')
