#!/usr/bin/env python3
"""Collect queue evaluation evidence; missing/failed runs stay explicit."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def collect(root, eval_dir, host_dir, baseline_dir=None):
    rows = []
    for depth in (1, 2, 4, 8):
        base = root / eval_dir / f'qspi-depth-{depth}'
        if depth == 1 and baseline_dir and not (base / 'result.json').exists():
            base = root / baseline_dir / 'qspi-depth-1'
        row = {'depth': depth, 'evidence_dir': base.relative_to(root).as_posix()}
        result = base / 'result.json'
        row['build'] = json.loads(result.read_text(encoding='utf-8-sig')) if result.exists() else None
        timing = (row['build'] or {}).get('timing')
        if timing:
            setup = (timing.get('worst', {}).get('Setup') or {}).get('slack_ns')
            row['numeric_timing_gate_passed'] = (
                timing['setup_violated_endpoints'] == 0 and timing['hold_violated_endpoints'] == 0
                and not timing['negative_analyses'] and setup is not None and setup >= 0.10)
        build_log = base / 'build.log'
        if build_log.exists():
            row['errors'] = re.findall(r'^ERROR.*$', build_log.read_text(errors='replace'), re.M)
        resource = base / 'impl/gwsynthesis/kagura_fb_syn_rsc.xml'
        if resource.exists():
            module = ET.parse(resource).getroot()
            row['synthesis'] = {name: int(module.get('T_' + name, '0').split('(')[0])
                                for name in ('Register', 'Lut', 'Alu', 'Bsram', 'Ssram')}
        pnr = base / 'impl/pnr/kagura_fb.rpt.txt'
        if pnr.exists():
            plain = pnr.read_text(errors='replace')
            row['pnr'] = {}
            for name in ('Logic', 'Register', 'CLS'):
                match = re.search(r'^\s*' + name + r'\s*\|\s*(\d+)/(\d+)', plain, re.M)
                if match:
                    row['pnr'][name] = {'used': int(match[1]), 'available': int(match[2])}
        row['host_tests'] = []
        for lanes in (1, 4):
            log = root / host_dir / f'lanes-{lanes}-depth-{depth}' / 'run.log'
            if not log.exists():
                continue
            plain = log.read_text(errors='replace')
            measurements = [dict(round=int(m[1]), accept_cycles=int(m[2]), drain_cycles=int(m[3]))
                            for m in re.finditer(r'round=(\d+) accept=(\d+) drain=(\d+) cycles', plain)]
            row['host_tests'].append({'lanes': lanes, 'passed': 'PASS: queued fb_host' in plain,
                                      'measurements': measurements})
        rows.append(row)
    manifests = {}
    for directory in dict.fromkeys(p for p in (eval_dir, baseline_dir) if p):
        manifest = root / directory / 'source-sha256.json'
        if manifest.exists():
            manifests[directory] = json.loads(manifest.read_text(encoding='utf-8-sig'))
    return {'system_clock_hz': 54000000, 'hardware_tested': False,
            'eval_dir': eval_dir, 'host_dir': host_dir, 'baseline_dir': baseline_dir,
            'source_manifests': manifests, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--eval-dir', default='build/fb-queue-eval')
    parser.add_argument('--host-dir', default='build/fb-queue-host')
    parser.add_argument('--baseline-dir', help='Use an existing depth-one reference when absent in eval-dir')
    args = parser.parse_args()
    report = json.dumps(collect(args.root, args.eval_dir, args.host_dir, args.baseline_dir),
                        ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding='utf-8')
    else:
        print(report, end='')
