"""Decompose CPU-observed PRESENT gaps without changing measured firmware."""
import argparse, hashlib, json, re
from pathlib import Path

def analyze(path):
    text = path.read_text(errors='replace')
    frames = [dict((k, int(v)) for k, v in re.findall(r'(\w+)=(-?\d+)', s))
              for s in text.splitlines() if s.startswith('FRAME ')]
    delta = lambda a, b: (a-b) & 0xffffffff
    lettering = [i for i, f in enumerate(frames) if f['scene'] == 7 and f['ms'] >= 143000][:2]
    gaps = []
    for i in range(1, len(frames)):
        prev, f = frames[i-1], frames[i]
        gap = delta(f['present_after_us'], prev['present_after_us'])
        parts = dict(before_draw_us=delta(f['draw_start_us'], prev['present_after_us']),
                     draw_to_present_us=delta(f['present_before_us'], f['draw_start_us']),
                     present_call_us=delta(f['present_after_us'], f['present_before_us']))
        assert sum(parts.values()) == gap, (path, i, parts, gap)
        assert parts['draw_to_present_us'] + parts['present_call_us'] <= f['us'] + 2
        gaps.append(dict(frame_index=i, timeline_ms=f['ms'], scene=f['scene'], interval_us=gap,
                         **parts, call_us=f['us'],
                         finale_page_initial_lettering=i in lettering,
                         context=frames[max(0,i-2):i+3]))
    return dict(log=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                frames=len(frames), worst=max(gaps,key=lambda f:f['interval_us']),
                over_80ms=[f for f in gaps if f['interval_us'] >= 80000],
                finale_initial_lettering=[f for f in gaps if f['frame_index'] in lettering],
                interpretation='CPU-observed intervals; PRESENT call includes Queue drain, submit, GPU/vblank wait and ACK. before_draw includes scheduling and any work after previous PRESENT. No direct GPU timing.')

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('logs', nargs='+',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    result=[analyze(path) for path in a.logs]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2))
    print(json.dumps([dict(log=r['log'],worst=r['worst']) for r in result],indent=2))
