"""Diagnostic only: cell locations that appear in archived STA path details (partial placement)."""
from pathlib import Path
import re, json
O = Path(__file__).resolve().parent
out = {}
for label in 'AB':
    toks = [t.strip() for t in (O/f'{label}-timing.txt').read_text(encoding='utf-8').replace('\n', ' | ').split('|') if t.strip()]
    locs = {}
    for i, t in enumerate(toks):
        if re.fullmatch(r'R\d+C\d+\[\d\]\[[AB]\]|R\d+C\d+|[A-Z]+SIDE\[\d\]|PLL_[LR]|IOT\d+\[[AB]\]|IOB\d+\[[AB]\]', t) and i+1 < len(toks):
            node = toks[i+1]
            if '/' in node or node:
                inst = node.rsplit('/', 1)[0] if '/' in node else node
                locs.setdefault(inst, set()).add(t)
    out[label] = {k: sorted(v) for k, v in sorted(locs.items())}
groups = {
 'tmds_ch0': 'tmds_gen[0]', 'tmds_ch1': 'tmds_gen[1]', 'tmds_ch2': 'tmds_gen[2]',
 'audio_packets': 'audio_packets', 'packet_assembler': 'packet_assembler', 'audio_fifo': 'audio_link/fifo',
 'palette': 'display/palette_', 'held_palette': 'held_palette', 'upload_ram': 'upload_words',
 'window_regs': 'host/registers/window', 'memory_tx': 'memory_ctrl/tx', 'hdmi_cx': 'protocol/cx_',
 'serializer': 'serial', 'prefetch': 'core/prefetch'}
def rc(loc):
    m = re.match(r'R(\d+)C(\d+)', loc); return (int(m[1]), int(m[2])) if m else None
summary = {}
for label in 'AB':
    s = {}
    for g, key in groups.items():
        pts = [rc(l) for k, v in out[label].items() if key in k for l in v if rc(l)]
        if pts:
            rows = [p[0] for p in pts]; cols = [p[1] for p in pts]
            s[g] = dict(n=len(pts), rows=[min(rows), max(rows)], cols=[min(cols), max(cols)],
                        centroid=[round(sum(rows)/len(rows), 1), round(sum(cols)/len(cols), 1)])
    summary[label] = s
(O/'placement-from-sta.json').write_text(json.dumps(dict(note='Only cells appearing in the 25+25+25 reported setup/hold/recovery path details; not a full placement.', summary=summary, cells=out), indent=1))
for label in 'AB':
    print(label)
    for g, v in summary[label].items(): print(' ', g, v)
