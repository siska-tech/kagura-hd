"""Promotion regression: the RC1 hardware megademo procedure on the T8 candidate.

Same as build/queue8-deglitch-release/run-hardware.py (RC1 validation), with the
frozen T8 image. FPGA SRAM only; RP2040 runs its resident megademo firmware
(flash c7052a32...). Two full flash reads before, one after (must be equal);
approved Queue8 SRAM restore in all cases. No Flash writes.

usage: run-megademo.py OUT_DIR   (under build/)
"""
from pathlib import Path
import hashlib, json, os, re, subprocess, sys, time, wave

root = Path(__file__).resolve().parents[3]
out = Path(sys.argv[1]); out = (out if out.is_absolute() else root/out).resolve()
assert out.is_relative_to(root/'build')
analyze_only = sys.argv[2:] == ['--analyze-only']  # re-run only the offline analysis
if not analyze_only: out.mkdir(parents=True)
pico = root/'build/midnight-hardware/picotool/picotool/picotool.exe'
program = 'C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe'
uid = 'E663A837CB73512D'
old = root/'build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8/impl/pnr/kagura_fb.fs'
new = root/'diagnostics/pcm-stream-rc1/candidate-t8/bitstream/kagura-hd-pcm-stream-t8-candidate.fs'
FLASH = 'c7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def call(name, args, timeout=120, env=None):
    with (out/(name+'.log')).open('xb') as log:
        subprocess.run(list(map(str, args)), stdout=log, stderr=subprocess.STDOUT, check=True,
                       timeout=timeout, cwd=root, env=env)
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

def hardware():
    global state
    state = dict(candidate_sha256=sha(new), restore_sha256=sha(old), fpga_flash_writes=0, rp2040_flash_writes=0)
    assert state['candidate_sha256'] == 'fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db'
    assert state['restore_sha256'] == '5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77'
    before = flash('before', True)
    assert before == flash('confirm') == FLASH
    (out/'flash-write-verified.json').write_text(json.dumps(dict(sha256=before, method='two full reads; no flash programming')))
    try:
        state['candidate_user_code'] = sram(new, 'candidate-sram')
        call('reboot', [pico, 'reboot', '--ser', uid]); time.sleep(5)
        # First attempt (promotion-megademo) missed the banner right after reboot:
        # wait until the resident CDC port has been present for 3 s.
        sys.path.insert(0, str(root/'build/showcase-hardware-deps'))
        from serial.tools import list_ports
        end, stable = time.monotonic()+30, None
        while time.monotonic() < end:
            if [p for p in list_ports.comports() if p.vid == 0x2e8a and (p.serial_number or '').upper() == uid]:
                stable = stable or time.monotonic()
                if time.monotonic()-stable > 3: break
            else: stable = None
            time.sleep(.25)
        else: raise RuntimeError('USB enumeration')
        env = dict(os.environ, KAGURA_CAMPAIGN_DIR=str(out), KAGURA_RP2040_UID=uid)
        env.pop('PYTHONIOENCODING', None)
        try:
            call('runner', [sys.executable, root/'software/beyond16/tools/hardware_run.py', 'demo'], timeout=320, env=env)
        finally:
            state['demo_result'] = json.loads((out/'demo-result.json').read_text()) if (out/'demo-result.json').exists() else None
        call('analysis', [sys.executable, root/'software/beyond16/tools/analyze_headroom_log.py', out/'demo-usb.log', '--output', out/'present.json'])
    finally:
        try:
            state['flash_after'] = flash('after', True)
            state['full_flash_equal'] = state['flash_after'] == before
        finally:
            state['restore_user_code'] = sram(old, 'restore-sram')
            call('restore-reboot', [pico, 'reboot', '--ser', uid])
            (out/'state.json').write_text(json.dumps({k: v for k, v in state.items() if k != 'demo_result'}, indent=2))

if analyze_only:
    state = json.loads((out/'state.json').read_text()); state['demo_result'] = json.loads((out/'demo-result.json').read_text())
else:
    hardware()

# Audio: same 10 ms low-RMS scan as the RC1 analysis (analyze-capture.py).
sys.path[:0] = [str(root/'build/uv-cache/archive-v0/rlh7ljqubiQHl4bs')]  # NumPy for Python 3.14
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
perfs = [dict(re.findall(r'(\w+)=(-?\d+)', s)) for s in (out/'demo-usb.log').read_text(errors='replace').splitlines() if s.startswith('PERF ')]
frames = [s for s in (out/'demo-usb.log').read_text(errors='replace').splitlines() if s.startswith('FRAME ')]
summary = dict(state, demo_success=bool(state['demo_result'] and state['demo_result']['success']),
               frames=len(frames), scenes=sorted({int(re.search(r'scene=(\d+)', f)[1]) for f in frames}),
               last_perf={k: int(v) for k, v in perfs[-1].items()} if perfs else None,
               audio=dict(onset_s=float(onset), audible_span_s=float(end-onset),
                          low_10ms_blocks_by_channel=[int(np.sum(selected & (stereo[:, c] < 20))) for c in (0, 1)]),
               recording_sha256=sha(out/'demo-hdmi.mkv'))
(out/'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps({k: summary[k] for k in ('demo_success', 'frames', 'scenes', 'last_perf', 'audio', 'full_flash_equal', 'restore_user_code')}, indent=2))
