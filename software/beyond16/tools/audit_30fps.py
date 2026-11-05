"""Read-only device audit: recorded hardware timing + existing PC DLL traces.

Does not build firmware, access devices, or alter original evidence.
"""
import collections, hashlib, json, re, statistics
from preview import Engine, R, SCENES

out = R / 'evidence/audit-30fps'
out.mkdir(exist_ok=True)
hardware = json.loads((R/'evidence/hardware/performance.json').read_text())
frames = []
for line in (R/'evidence/hardware/demo-usb.log').read_text().splitlines():
    m = re.match(r'FRAME ms=(\d+) scene=(\d+) us=(\d+) commands=(\d+) blit_pixels=(\d+)', line)
    if m:
        frames.append(tuple(map(int, m.groups())))
rows = []
for scene, (name, start, end) in enumerate(SCENES):
    e = Engine()
    # Initialize both pages at this scene; exclude captions from steady traces.
    e.tick(start + 1000)
    e.tick(start + 1033)
    trace = out / f'{scene:02}-trace.jsonl'
    e.lib.pc_trace(str(trace).encode())
    for i in range(59):
        e.tick(start + 1066 + 33*i)
    e.lib.pc_trace(None)
    counts = collections.Counter()
    for line in trace.read_text().splitlines():
        d = bytes.fromhex(json.loads(line)['descriptor'])
        op = d[0]
        key = {0:'fence', 1:'fill', 2:'palette', 3:'present', 6:'blit', 7:'pcm_commit'}.get(op, str(op))
        if op == 1 and d[12] == 0:
            key = 'black_fill'
        counts[key] += 1
    e.lib.pc_finish()
    gaps = [b[0]-a[0]-a[2]/1000 for a,b in zip(frames,frames[1:])
            if a[1] == b[1] == scene and start+1000 <= a[0] < end-1000]
    h = hardware['scenes'][scene]
    rows.append({'scene':scene,'name':name,'hardware_fps':h['effective_fps'],
                 'required_throughput_factor':30/h['effective_fps'],
                 'hardware_commands_per_logged_frame':h['drawing_commands']/h['logged_frames'],
                 'hardware_mean_call_ms':h['mean_frame_ms'],
                 'observed_between_calls_median_ms':statistics.median(gaps),
                 'pc_59_frame_trace_commands_per_frame':{k:v/59 for k,v in counts.items()},
                 'pc_scope':'33ms input times, scene t=1066..2980ms; not hardware command distribution'})
sources = ['src/b16.c','src/rp2040_main.c','out/optimized.dll',
           'evidence/hardware/demo-usb.log','evidence/hardware/performance.json']
result = {'scope':'offline audit; hardware untouched; estimates are not measured improvements',
          'sources_sha256':{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in sources},
          'scenes':rows}
(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(rows,indent=2))
