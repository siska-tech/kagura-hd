from preview import R,Engine
from PIL import Image
import json
files=sorted((R/'evidence').glob('0[0-7]-*.png'));assert len(files)==8
sheet=Image.new('RGB',(1280,1440))
for i,p in enumerate(files):sheet.paste(Image.open(p).convert('RGB'),((i%2)*640,(i//2)*360))
sheet.save(R/'evidence/contact-sheet.png')
e=Engine();e.tick(138888);e.image().save(R/'evidence/vector-tunnel.png')
# Update source analysis numbers from the final reproducible run.
p=R/'DRIVER_ANALYSIS.md';s=p.read_text(encoding='utf-8');s=s.replace('978,317 commands','1,029,051 commands').replace('9,878,431→8,805,653','10,428,231→9,262,259').replace('10.86%','11.18%').replace('48,317,777→46,961,616B','50,973,583→49,396,848B');p.write_text(s,encoding='utf-8')
