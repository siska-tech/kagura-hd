from pathlib import Path
import json,re,hashlib
O=Path(__file__).resolve().parent; R=O.parents[2]
d=json.loads((O/'identity.json').read_text())
out=[]
for name,ab in d['resources'].items():
    if 'A' in ab and 'B' in ab and ab['A']!=ab['B']:
        out.append(f"{name}: B={ab['B']} A={ab['A']}")
(O/'resource-delta.txt').write_text('\n'.join(out))
summary={}
for label,base in [('A','build/pcm-stream-rc1/sta-short-control'),('B','build/queue8-deglitch-release')]:
    p=R/base/'native/impl/gwsynthesis/kagura_fb.vg';txt=p.read_text()
    result={}
    for mod in ['kagura_fb_registers','kagura_fb_burst_ctrl','kagura_packet_assembler']:
        m=re.search(r'^module '+mod+r'\b(.*?)^endmodule',txt,re.M|re.S)
        if not m: continue
        s=m.group(); rows=[]
        for im in re.finditer(r'^\s*(\w+)\s+(\\[^\s]+|\w+)\s*\((.*?)\);',s,re.M|re.S):
            typ,name,body=im.groups()
            ports=dict(re.findall(r'\.(\w+)\s*\(([^()]*)\)',body))
            rows.append((typ,name,ports))
        targets=['tx_load','tx_shift','tx_495_7','tx_495_9','window_write_word[0]','window_write_word[31]']
        targets += [f'\\window_select[{i}].select_cpu' for i in range(8)]
        counts={}
        for net in targets:
            sinks=[];drivers=[]
            for typ,name,ports in rows:
                for port,expr in ports.items():
                    # Scalar nets selected here: no bus concatenation needed.
                    if expr.strip()==net:
                        (drivers if port in ['Q','F','O','DO'] else sinks).append(f'{typ} {name}.{port}')
            if sinks or drivers: counts[net]={'sink_pins':len(sinks),'drivers':drivers,'sinks':sinks}
        result[mod]=counts
    summary[label]=result
(O/'fanout.json').write_text(json.dumps(summary,indent=2))
extra=[R/'artifacts/experimental/queue8-qspi-deglitch-rc1/kagura-hd-qspi-queue8-cs-deglitch-rc1.fs',R/'build/pcm-stream-rc1/hardware-host-traffic-control/pcm_stream_hw.elf',R/'software/midnight_terminal/vendor/kagura_host.pio',R/'build/pcm-stream-rc1/hardware-host-traffic-control/kagura_host.pio.h']
for folder in ['stream-traffic-x','stream-traffic-x-repeat','stream-traffic-z','stream-traffic-x-rc1','stream-traffic-v','stream-traffic-w','stream-match-w']:
    for filename in ['result.json','phase-analysis.json','stream-usb.log']:
        p=R/'build/pcm-stream-rc1'/folder/filename
        if p.exists():extra.append(p)
(O/'evidence-hashes.json').write_text(json.dumps({p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in extra},indent=2))
for label,mods in summary.items():
    print(label,{m:{n:x['sink_pins'] for n,x in ns.items()} for m,ns in mods.items()})
for label,files in d['artifacts'].items():
    print(label,[(x['path'],x['sha256']) for x in files if x['path'].endswith(('.fs','.vg','.cst','.sv'))])
