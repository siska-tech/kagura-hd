"""Vendor existing Host font and PCM2 facade verbatim; record provenance."""
from pathlib import Path
import re,hashlib,json,shutil
r=Path(__file__).resolve().parents[1];p=r/'software/kagura_fb/showcase';v=p/'vendor';v.mkdir(parents=True,exist_ok=True)
sources={'fonts.py':r.parent/'kagura/software/micropython/kagura/ui/fonts.py',
 'font-license.txt':r.parent/'kagura/software/micropython/fonts/README.md',
 'kagura_fb_audio.py':r/'software/kagura_fb/kagura_fb_audio.py'}
proof={}
for dest,src in sources.items():
 out=(p.parent/dest) if dest=='kagura_fb_audio.py' else v/dest
 assert not out.exists(),out
 shutil.copy2(src,out);proof[dest]={'source':str(src.relative_to(r.parent)),'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
f=r.parent/'kagura/software/desktop/core/kd_font_data.c';s=f.read_text();table=s.split('static const uint8_t system_rows[95 * 8] = {',1)[1].split('};',1)[0]
rows=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',table));assert len(rows)==760
(v/'ascii_rows.py').write_text('# SPDX-License-Identifier: LicenseRef-Misaki\n# Existing KAGURA-9 Host system_rows, unchanged glyphs. See font-license.txt.\nROWS = '+repr(rows)+'\n')
proof['ascii_rows.py']={'source':str(f.relative_to(r.parent)),'source_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'rows_sha256':hashlib.sha256(rows).hexdigest()}
(p/'provenance.json').write_text(json.dumps(proof,indent=2)+'\n')
(p/'__init__.py').write_text('# SPDX-License-Identifier: Apache-2.0\n')
(v/'__init__.py').write_text('# SPDX-License-Identifier: Apache-2.0\n')
print('Vendored existing Host font and ABI1.4 PCM2 facade; no RTL or existing driver edits')
