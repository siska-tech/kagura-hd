"""G1 adoption gate for a candidate bitstream (design-audit-report.md section 17.4).

Hardware reproduction set from the audit, SRAM-only, through run-audit-ab.py:
  positive control  A  (DE71...) mode i    must reproduce (bench sensitive)
  negative control  RC1 (1F4A...) mode 5   must be clean
  candidate         modes x 5 i o S        must all be clean
Clean = rc=0, timeouts=0, low-RMS 10 ms blocks 0/0 and marker mismatches 0/0.
Every run also restores approved Queue8 and checks the RP2040 flash.
The gate refuses candidates without a passing numeric STA status.

A pass means only: no reproduction with this bench, these conditions and
25 s per condition. It does not prove the physical root cause is absent.

usage: adoption-gate.py LABEL CANDIDATE_FS [--out DIR] [--modes x5ioS]
       [--rounds N] [--closing-controls] [--fault-modes IOTX]
Formal certification (section 20): --modes xz5fryeaioGSR1E --rounds 3
--closing-controls --fault-modes IOTX. Fault modes write CSR 31 = 0x02
(T8 diag_broadcast) first and must also be clean.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, subprocess, sys

root = Path(__file__).resolve().parents[3]
driver = Path(__file__).with_name('run-audit-ab.py')
parser = argparse.ArgumentParser()
parser.add_argument('label')
parser.add_argument('candidate', type=Path)
parser.add_argument('--out', type=Path)
parser.add_argument('--modes', default='x5ioS')
parser.add_argument('--rounds', type=int, default=1)
parser.add_argument('--closing-controls', action='store_true')
parser.add_argument('--fault-modes', default='')
args = parser.parse_args()
candidate = (args.candidate if args.candidate.is_absolute() else root/args.candidate).resolve()
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out = args.out or root/'build/pcm-stream-rc1/gate'/f'{args.label}-{stamp}'
out = out if out.is_absolute() else root/out
out.mkdir(parents=True, exist_ok=False)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
candidate_sha = sha(candidate)
status_path = candidate.parents[2]/'timing-status.json'
status = json.loads(status_path.read_text())
sta_ok = (status['setup_violated_endpoints'] == 0 and status['hold_violated_endpoints'] == 0
          and not status['negative_analyses'] and status['worst']['Setup']['slack_ns'] >= 0.10)
gate = dict(label=args.label, candidate=str(candidate.relative_to(root)), candidate_sha256=candidate_sha,
            timing_status=str(status_path.relative_to(root)), timing_status_sha256=sha(status_path),
            sta_setup_wns_ns=status['worst']['Setup']['slack_ns'], sta_hold_wns_ns=status['worst']['Hold']['slack_ns'],
            sta_ok=sta_ok, modes=args.modes, rounds=args.rounds, closing_controls=args.closing_controls,
            fault_modes=args.fault_modes, runs=[])
def save(): (out/'gate.json').write_text(json.dumps(gate, indent=2))
save()
if not sta_ok:
    gate['verdict'] = 'REFUSED: numeric STA gate not met'; save(); print(gate['verdict']); sys.exit(2)

def run(role, mode, image_args):
    name = f'{len(gate["runs"])+1:02d}-{role}-{mode}'
    proc = subprocess.run([sys.executable, '-I', str(driver), mode, str(out/name), *image_args],
                          capture_output=True, text=True, cwd=root, timeout=900)
    (out/(name+'.out')).write_text(proc.stdout+proc.stderr, encoding='utf-8')
    result = json.loads((out/name/'result.json').read_text())
    phase = json.loads((out/name/'phase-analysis.json').read_text()) if (out/name/'phase-analysis.json').exists() else None
    low = result.get('low_rms_10ms')
    markers = [c['marker_mismatches'] for c in phase['channels']] if phase else None
    infra_ok = bool(result.get('passed') and result.get('host_flash_equal') and
                    result.get('restore_fpga_user_code') == '0x00004068' and low is not None)
    row = dict(role=role, mode=mode, run=name, driver_exit=proc.returncode, infra_ok=infra_ok,
               stop=result.get('stop'), low_rms_10ms=low, marker_mismatches=markers,
               candidate_sha256=result.get('candidate_sha256'),
               clean=infra_ok and low == [0, 0] and markers == [0, 0])
    gate['runs'].append(row); save()
    print(name, 'infra_ok' if infra_ok else 'INFRA_FAIL', low, markers, flush=True)
    if not infra_ok: raise SystemExit(f'Infrastructure failure in {name}; gate aborted')
    return row

positive = run('positive', 'i', ['--image', 'A'])
negative = run('negative', '5', ['--image', 'B'])
gate['bench_valid'] = sum(positive['low_rms_10ms']) >= 10 and negative['clean']
if not gate['bench_valid']:
    gate['verdict'] = 'INVALID: controls did not behave (bench insensitive or RC1 not clean)'; save()
    print(gate['verdict']); sys.exit(3)
image = ['--image', 'custom', '--image-path', str(candidate), '--image-sha', candidate_sha]
cand = [run('candidate', m, image) for _ in range(args.rounds) for m in args.modes]
cand += [run('fault', m, image) for m in args.fault_modes]
if args.closing_controls:
    closing_positive = run('positive', 'i', ['--image', 'A'])
    closing_negative = run('negative', '5', ['--image', 'B'])
    gate['closing_bench_valid'] = sum(closing_positive['low_rms_10ms']) >= 10 and closing_negative['clean']
    if not gate['closing_bench_valid']:
        gate['verdict'] = 'INVALID: closing controls did not behave'; save(); print(gate['verdict']); sys.exit(3)
gate['candidate_runs'] = len(cand)
gate['verdict'] = 'PASS (no reproduction under the audit set)' if all(r['clean'] for r in cand) else 'FAIL (reproduced)'
save()
print(json.dumps({k: gate.get(k) for k in ('label', 'candidate_sha256', 'sta_setup_wns_ns', 'bench_valid', 'closing_bench_valid', 'candidate_runs', 'verdict')}, indent=2))
sys.exit(0 if gate['verdict'].startswith('PASS') else 1)
