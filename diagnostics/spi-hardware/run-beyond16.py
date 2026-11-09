"""BEYOND 16 COLORS hardware run on a given FPGA SRAM image and RP2040 firmware.

Same procedure as diagnostics/pcm-stream-rc1/promotion/run-megademo.py, except
that the firmware is not the resident one: the full 2 MiB RP2040 Flash is read
twice (must match), the firmware ELF is written, and afterwards the backup is
written back and read again (must match the first read). FPGA: SRAM only, the
approved Queue8 image is restored in all cases. No FPGA Flash writes.

usage: run-beyond16.py OUT_DIR --image FS --image-sha SHA --firmware ELF --firmware-sha SHA [--modes bench,demo]
Modes run in order on the same firmware; the RP2040 is rebooted between them.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess, sys, time, wave

root = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser()
ap.add_argument('out', type=Path)
ap.add_argument('--image', type=Path, required=True)
ap.add_argument('--image-sha', required=True)
ap.add_argument('--firmware', type=Path, required=True)
ap.add_argument('--firmware-sha', required=True)
ap.add_argument('--analyze-only', action='store_true')
ap.add_argument('--modes', default='demo', help='comma-separated hardware_run.py modes: bench, demo')
args = ap.parse_args()
modes = args.modes.split(',')
assert modes and all(m in ('bench', 'demo') for m in modes) and len(set(modes)) == len(modes)
def resolve(p): return (p if p.is_absolute() else root/p).resolve()
out, image, firmware = resolve(args.out), resolve(args.image), resolve(args.firmware)
assert out.is_relative_to(root/'build')
if not args.analyze_only: out.mkdir(parents=True)
pico = root/'build/midnight-hardware/picotool/picotool/picotool.exe'
program = 'C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe'
uid = 'E663A837CB73512D'
restore = root/'build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8/impl/pnr/kagura_fb.fs'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def call(name, cmd, timeout=120, env=None):
    with (out/(name+'.log')).open('xb') as log:
        subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout, cwd=root, env=env)
def flash(name, force=False):
    path = out/(name+'.bin')
    call(name, [pico, 'save', '-r', '0x10000000', '0x10200000', '-v', path, '--ser', uid]+(['-F'] if force else []))
    assert path.stat().st_size == 2097152
    return sha(path)
def sram(bit, label):
    code = re.search(r'^//UserCode: (0x[0-9A-Fa-f]+)', bit.read_text(), re.M)[1]
    for i in range(1, 4):
        name = f'{label}-{i}'
        call(name, [program, '--device', 'GW1NR-9C', '--cable-index', '1', '--run', '2', '--fsFile', bit])
        log = (out/(name+'.log')).read_text(errors='replace')
        if f'User Code is: {code}' in log and 'Status Code is: 0x0003F020' in log and 'Finished.' in log and 'mismatch' not in log.lower():
            return code
        time.sleep(2)
    raise RuntimeError('SRAM readback mismatch')
sys.path.insert(0, str(root/'build/showcase-hardware-deps'))
from serial.tools import list_ports
def wait_stable_port(seconds=30):
    end, stable = time.monotonic()+seconds, None
    while time.monotonic() < end:
        if [p for p in list_ports.comports() if p.vid == 0x2e8a and (p.serial_number or '').upper() == uid]:
            stable = stable or time.monotonic()
            if time.monotonic()-stable > 3: return
        else: stable = None
        time.sleep(.25)
    raise RuntimeError('USB enumeration')

def hardware():
    global state
    state = dict(image_sha256=sha(image), firmware_sha256=sha(firmware), restore_sha256=sha(restore),
                 fpga_flash_writes=0, rp2040_flash_writes=0)
    assert state['image_sha256'] == args.image_sha.lower() and state['firmware_sha256'] == args.firmware_sha.lower()
    assert state['restore_sha256'] == '5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77'
    before = flash('before', True)
    assert before == flash('confirm')
    state['flash_before'] = before
    (out/'flash-write-verified.json').write_text(json.dumps(dict(sha256=before, method='two full reads before writing the test firmware')))
    try:
        state['candidate_user_code'] = sram(image, 'candidate-sram')
        state['rp2040_flash_writes'] = 1
        call('firmware-flash', [pico, 'load', '-v', '-x', firmware, '--ser', uid], timeout=300)
        time.sleep(2); wait_stable_port()
        env = dict(os.environ, KAGURA_CAMPAIGN_DIR=str(out), KAGURA_RP2040_UID=uid)
        env.pop('PYTHONIOENCODING', None)
        for i, mode in enumerate(modes):
            if i:
                call(f'reboot-before-{mode}', [pico, 'reboot', '-f', '--ser', uid]); time.sleep(2); wait_stable_port()
            try:
                call(f'runner-{mode}', [sys.executable, root/'software/beyond16/tools/hardware_run.py', mode], timeout=320, env=env)
            finally:
                path = out/f'{mode}-result.json'
                state[f'{mode}_result'] = json.loads(path.read_text()) if path.exists() else None
        if 'demo' in modes:
            call('analysis', [sys.executable, root/'software/beyond16/tools/analyze_headroom_log.py', out/'demo-usb.log', '--output', out/'present.json'])
    finally:
        try:
            if state['rp2040_flash_writes']:
                call('to-bootsel', [pico, 'reboot', '-u', '-f', '--ser', uid]); time.sleep(2)
                call('flash-restore', [pico, 'load', '-v', out/'before.bin', '-t', 'bin', '-o', '0x10000000', '--ser', uid], timeout=600)
                state['rp2040_flash_writes'] = 2
            state['flash_after'] = flash('after', True)
            state['full_flash_equal'] = state['flash_after'] == before
        finally:
            state['restore_user_code'] = sram(restore, 'restore-sram')
            call('restore-reboot', [pico, 'reboot', '--ser', uid])
            (out/'state.json').write_text(json.dumps({k: v for k, v in state.items() if not k.endswith('_result')}, indent=2))

if args.analyze_only:
    state = json.loads((out/'state.json').read_text())
    for mode in modes: state[f'{mode}_result'] = json.loads((out/f'{mode}-result.json').read_text())
else:
    hardware()

bench = [l for l in (out/'bench-usb.log').read_text(errors='replace').splitlines() if l.startswith('BENCH')] if 'bench' in modes else []
(out/'bench.txt').write_text(''.join(line+'\n' for line in bench))
if 'demo' not in modes:
    print(json.dumps(dict(bench_success=bool(state.get('bench_result') and state['bench_result']['success']),
                          full_flash_equal=state.get('full_flash_equal'), restore_user_code=state.get('restore_user_code')), indent=2))
    sys.exit(0)

# Audio: same 10 ms low-RMS scan as run-megademo.py.
sys.path[:0] = [str(root/'build/uv-cache/archive-v0/rlh7ljqubiQHl4bs')]
import numpy as np
ff = Path((root/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip())
wav = out/'demo-audio.wav'
subprocess.run([str(ff), '-nostdin', '-y', '-v', 'error', '-i', str(out/'demo-hdmi.mkv'), '-vn', '-c:a', 'pcm_s16le', str(wav)], check=True)
with wave.open(str(wav)) as w:
    assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (48000, 2, 2)
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2)
left = audio[:, 0].astype(float); rms = np.sqrt(np.mean(left[:len(left)//480*480].reshape(-1, 480)**2, axis=1))
active = np.flatnonzero(rms > 150); onset = active[0]/100; end = (active[-1]+1)/100
t = np.arange(len(rms))*.01; selected = (t >= onset+.02) & (t < end-.02)
stereo = np.sqrt(np.mean(audio[:len(audio)//480*480].astype(float).reshape(-1, 480, 2)**2, axis=1))
log = (out/'demo-usb.log').read_text(errors='replace').splitlines()
perfs = [dict(re.findall(r'(\w+)=(-?\d+)', s)) for s in log if s.startswith('PERF ')]
frames = [s for s in log if s.startswith('FRAME ')]
summary = dict(state, demo_success=bool(state['demo_result'] and state['demo_result']['success']),
               frames=len(frames), scenes=sorted({int(re.search(r'scene=(\d+)', f)[1]) for f in frames}),
               last_perf={k: int(v) for k, v in perfs[-1].items()} if perfs else None,
               audio=dict(onset_s=float(onset), audible_span_s=float(end-onset),
                          low_10ms_blocks_by_channel=[int(np.sum(selected & (stereo[:, c] < 20))) for c in (0, 1)]),
               recording_sha256=sha(out/'demo-hdmi.mkv'))
(out/'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps({k: summary[k] for k in ('demo_success', 'frames', 'scenes', 'last_perf', 'audio', 'full_flash_equal', 'restore_user_code')}, indent=2))
