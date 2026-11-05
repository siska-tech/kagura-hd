"""Reuse the prior pin/constant/STA/hash gate; allow an omitted zero-DSP row."""
from pathlib import Path
source=(Path(__file__).resolve().parents[1]/'psram-isolation/audit_build.py').read_text()
source=source.replace('    assert match,label', '''    if match is None and label in ('DSP','BSRAM'):
        if label=='DSP':assert not re.search(r'\\b(?:MULTADDALU|MULTALU|ALU54D|MULT18X18)',vg)
        else:assert not re.search(r'^\\s*(?:SP|DP|SDP|SPB|DPB|SDPB)\\s+\\w+\\s*\\(',vg,re.M)
        resources[label]=[0,None]
        continue
    assert match,label''')
source=source.replace('ISO1 Host/CSR isolation; internal STA; PSRAM held inactive',
                      'ISO2 Host/CSR six-boundary observation; PSRAM held inactive')
exec(compile(source,str(Path(__file__)), 'exec'))
