"""Read-only collection of archived inputs and reports; outputs stay here."""
from pathlib import Path
import hashlib, json, difflib, re, bisect, xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
A = ROOT/'build/pcm-stream-rc1/sta-short-control'
B = ROOT/'build/queue8-deglitch-release'
R = ROOT/'releases/queue8-qspi-deglitch-rc1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return p.relative_to(ROOT).as_posix()
manifest = json.loads((R/'source-input-manifest.json').read_text())
rows=[]; diff=[]
for name, expected in sorted(manifest.items()):
    p=R/'build-inputs'/name; a=A/'inputs'/name; b=B/'inputs'/name
    rows.append(dict(file=name, release_sha256=sha(p), release_match=sha(p).lower()==expected.lower(),
        A_sha256=sha(a) if a.exists() else None, B_original_sha256=sha(b) if b.exists() else None,
        B_original_matches_release=b.exists() and sha(b)==sha(p)))
    if a.exists() and a.read_bytes()!=p.read_bytes():
        diff.extend(difflib.unified_diff(p.read_text().splitlines(True),a.read_text().splitlines(True),fromfile=rel(p),tofile=rel(a)))
(OUT/'inputs-diff.patch').write_text(''.join(diff),encoding='utf-8')
artifacts={}
resources={}
for label, base in [('A',A),('B',B)]:
    native=base/'native'
    paths=[native/'impl/pnr/kagura_fb.fs',native/'impl/gwsynthesis/kagura_fb.vg',native/'impl/gwsynthesis/kagura_fb.prj',native/'impl/gwsynthesis/kagura_fb_syn_rsc.xml',native/'impl/pnr/kagura_fb.tr',native/'impl/pnr/kagura_fb_tr_content.html',native/'impl/pnr/kagura_fb.rpt.txt',native/'impl/pnr/cmd.do',native/'impl/pnr/device.cfg',native/'kagura_fb.cst',native/'kagura_fb_config.sv',native/'build.log']
    artifacts[label]=[{"path":rel(p),"sha256":sha(p),"bytes":p.stat().st_size} for p in paths if p.exists()]
    xml=ET.parse(native/'impl/gwsynthesis/kagura_fb_syn_rsc.xml').getroot()
    def walk(e,prefix=''):
        name=prefix+e.attrib['name']; resources.setdefault(name,{})[label]=e.attrib
        for c in e: walk(c,name+'/')
    walk(xml)
    # Flatten report HTML to searchable lines, retaining source report separately.
    import html
    s=(native/'impl/pnr/kagura_fb_tr_content.html').read_text(errors='replace')
    s=re.sub(r'</(?:tr|p|div|h[1-6])>', '\n', s, flags=re.I)
    s=re.sub(r'</t[dh]>', ' | ', s, flags=re.I)
    s=html.unescape(re.sub('<[^>]+>','',s))
    (OUT/f'{label}-timing.txt').write_text('\n'.join(x.strip() for x in s.splitlines() if x.strip()),encoding='utf-8')
    vg=(native/'impl/gwsynthesis/kagura_fb.vg').read_text()
    # Primitive connection counts: exact named net token occurrences at input ports.
    instances=[]
    line_offsets=[m.start() for m in re.finditer('\n',vg)]
    for m in re.finditer(r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\((.*?)\);',vg,re.M|re.S):
        typ,name,body=m.groups()
        ports=dict(re.findall(r'\.(\w+)\s*\(([^()]*)\)',body))
        instances.append((typ,name,ports,bisect.bisect_left(line_offsets,m.start())+1))
    selected=[]
    for typ,name,ports,line in instances:
        if any(t in name for t in ['window_select','window_write_word','tx_load','tx_shift','first_local','cursor_upper_carry','upload_words']):
            selected.append(dict(type=typ,name=name,line=line,ports=ports))
    sinks={}
    for typ,name,ports,line in instances:
        for port, expr in ports.items():
            if port in ['Q','Q0','Q1','F','O','DO','CLKOUT','CLKOUTP','LOCK']: continue
            for net in re.findall(r'\\[^\s,{}]+|\b[A-Za-z_]\w*(?:\[\d+\])?',expr):
                sinks.setdefault(net,[]).append(f'{name}.{port}')
    for cell in selected:
        cell['output_sink_counts']={p:len(sinks.get(n.strip(),[])) for p,n in cell['ports'].items() if p in ['Q','O','DO']}
    (OUT/f'{label}-netlist-selected.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
(OUT/'identity.json').write_text(json.dumps(dict(inputs=rows,artifacts=artifacts,resources=resources),indent=2),encoding='utf-8')
print(json.dumps({'release_files':len(rows),'release_hash_failures':[x['file'] for x in rows if not x['release_match']], 'original_B_mismatch':[x['file'] for x in rows if not x['B_original_matches_release']], 'changed_files':[x['file'] for x in rows if x['A_sha256']!=x['release_sha256']]},indent=2))
