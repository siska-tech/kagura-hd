"""MIDNIGHT TERMINAL (FM edition) hardware run. FPGA: SRAM only (never Flash).
RP2040: RAM ELF, or with --flash the Flash image is written after a full 2 MiB
backup, and the backup is written back and verified byte-for-byte afterwards.

JTAG scan -> RP2040 flash read -> promoted FPGA image to SRAM -> RAM-only ELF
-> UGREEN HDMI video+audio capture of the 104 s show -> restore approved
Queue8 to FPGA SRAM -> RP2040 flash compare -> reboot to the resident host.
Then: 10 ms low-RMS scan and per-second correlation against the PC render.

usage: run_hardware.py OUT_DIR --elf ELF --elf-sha SHA --reference PC_WAV
"""
from pathlib import Path
import argparse, hashlib, json, os, re, struct, subprocess, sys, time, wave

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root/'build/showcase-hardware-deps'))
import serial
from serial.tools import list_ports

p = argparse.ArgumentParser()
p.add_argument('out', type=Path)
p.add_argument('--elf', type=Path, required=True)
p.add_argument('--elf-sha', required=True)
p.add_argument('--reference', type=Path, required=True)
p.add_argument('--analyze-only', action='store_true')
p.add_argument('--flash', action='store_true', help='RP2040 Flash image; restore the original Flash afterwards')
args = p.parse_args()
out = (args.out if args.out.is_absolute() else root/args.out).resolve()
assert out.is_relative_to(root/'build')
pico = root/'build/midnight-hardware/picotool/picotool/picotool.exe'
programmer = Path('C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe')
image = root/'artifacts/validated/kagura-hd-qspi-pcm-stream.fs'
IMAGE_SHA = 'fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db'
restore = root/'build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8/impl/pnr/kagura_fb.fs'
elf = (args.elf if args.elf.is_absolute() else root/args.elf).resolve()
reference = (args.reference if args.reference.is_absolute() else root/args.reference).resolve()
ff = Path((root/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip())
def sha(x): return hashlib.sha256(x.read_bytes()).hexdigest()
result = dict(image_sha256=IMAGE_SHA, elf_sha256=args.elf_sha.lower(), passed=False, fpga_flash_writes=0, rp2040_flash_writes=0)
def save(): (out/'result.json').write_text(json.dumps(result, indent=2))

def hardware():
    out.mkdir(parents=True, exist_ok=False)
    assert sha(image) == IMAGE_SHA and sha(restore) == '5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77'
    assert sha(elf) == args.elf_sha.lower()
    data = elf.read_bytes(); entry, offset = struct.unpack_from('<II', data, 24); size, count = struct.unpack_from('<HH', data, 42)
    loads = [s for s in (struct.unpack_from('<8I', data, offset+i*size) for i in range(count)) if s[0] == 1]
    if args.flash:
        assert 0x10000000 <= entry < 0x10200000 and loads
        assert all(0x10000000 <= s[3] and s[3]+s[4] <= 0x10200000 for s in loads if s[4]), 'Flash image must load into Flash'
    else:
        assert 0x20000000 <= entry < 0x20042000 and loads
        assert all(0x20000000 <= s[2] == s[3] and s[3]+s[5] <= 0x20042000 for s in loads), 'ELF must be RAM-only'
    def call(name, cmd, timeout=120):
        with (out/(name+'.log')).open('xb') as log:
            subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout, cwd=root)
        print(name, 'complete', flush=True)
        return (out/(name+'.log')).read_text(errors='replace')
    def sram(name, bit):
        code = re.search(r'^//UserCode: (0x[0-9A-Fa-f]+)', bit.read_text(), re.M)[1]
        log = call(name, [programmer, '--device', 'GW1NR-9C', '--cable-index', '1', '--run', '2', '--fsFile', bit])
        assert 'Finished.' in log and 'mismatch' not in log.lower() and 'User Code is: '+code in log and 'Status Code is: 0x0003F020' in log
        return code
    def flash_read(label, uid, force=False):
        path = out/(label+'.bin')
        call(label, [pico, 'save', '-r', '0x10000000', '0x10200000', '-v', path, '--ser', uid]+(['-F'] if force else []))
        assert path.stat().st_size == 2097152
        return sha(path)
    def rp_ports(): return [x for x in list_ports.comports() if x.vid == 0x2e8a and x.pid == 0x000a and x.serial_number]
    def wait_port(uid, seconds=20):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            m = [x for x in rp_ports() if x.serial_number.upper() == uid]
            if len(m) == 1: return m[0].device
            time.sleep(.2)
        raise RuntimeError('USB serial port did not appear')
    assert '0x1100481B' in call('jtag-scan', [programmer, '--cable-index', '1', '--scan'])
    ports = rp_ports(); assert len(ports) == 1, [x.device for x in ports]
    uid = ports[0].serial_number.upper(); assert uid != 'EEEEEEEEEEEEEEEE'
    before = None
    try:
        before = flash_read('host-flash-before', uid, True); result['host_flash_before'] = before
        result['fpga_user_code'] = sram('candidate-sram', image)
        if args.flash:
            result['rp2040_flash_writes'] = 1
            call('rp2040-flash', [pico, 'load', '-v', '-x', elf, '--ser', uid], timeout=300)
            port_name = wait_port(uid)
        else:
            call('rp2040-sram', [pico, 'load', '-v', '-x', elf, '--ser', uid])
            port_name = wait_port('EEEEEEEEEEEEEEEE')
        with serial.Serial(port_name, 115200, timeout=.2, write_timeout=2) as port, (out/'demo-usb.log').open('xb') as log:
            raw = bytearray()
            def pump():
                chunk = port.read(4096); raw.extend(chunk); log.write(chunk); log.flush()
            end = time.monotonic()+10
            while b'MIDNIGHT TERMINAL / FM EDITION' not in raw:
                assert time.monotonic() < end, 'No demo banner'; pump()
            with (out/'capture.log').open('xb') as caplog:
                cap = subprocess.Popen([str(ff), '-hide_banner', '-y', '-f', 'dshow', '-rtbufsize', '256M', '-video_size', '1280x720',
                    '-framerate', '60', '-sample_rate', '48000', '-channels', '2',
                    '-i', 'video=UGREEN 15390:audio=デジタル オーディオ インターフェイス (UGREEN 15390)',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(out/'demo-hdmi.mkv')],
                    stdin=subprocess.PIPE, stdout=caplog, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    time.sleep(3); assert cap.poll() is None, 'Capture exited before start'
                    port.write(b'g'); result['started'] = True; save(); print('demo started', flush=True)
                    end = time.monotonic()+200
                    while not re.search(rb'^STOP .*\r?\n', raw, re.M):
                        assert time.monotonic() < end, 'Demo timed out'; assert cap.poll() is None, 'Capture exited'
                        pump()
                    time.sleep(1.5); pump()
                    result['stop'] = re.search(rb'^STOP [^\r\n]+', raw, re.M)[0].decode()
                    m = re.search(rb'^PCM_STATUS [^\r\n]+', raw, re.M); result['pcm_status'] = m[0].decode() if m else None
                    m = re.search(rb'^SCENES [^\r\n]+', raw, re.M); result['scenes'] = m[0].decode() if m else None
                    print(result['stop'], flush=True)
                    result['passed'] = 'rc=0 ' in result['stop'] and 'timeouts=0 ' in result['stop']
                finally:
                    if cap.poll() is None:
                        try: cap.communicate(b'q', timeout=20)
                        except subprocess.TimeoutExpired: cap.kill(); cap.wait()
                    result['capture_exit'] = cap.returncode
    except BaseException as ex:
        result['error'] = repr(ex); print('stopped:', repr(ex), flush=True)
    finally:
        try:
            if (out/'candidate-sram.log').exists(): result['restore_fpga_user_code'] = sram('restore-sram', restore)
        except BaseException as ex: result['restore_fpga_error'] = repr(ex)
        try:
            if any(x.serial_number.upper() == 'EEEEEEEEEEEEEEEE' for x in rp_ports()):
                call('ram-to-bootsel', [pico, 'reboot', '-u', '-f', '--ser', 'EEEEEEEEEEEEEEEE']); time.sleep(1)
            if args.flash and before and result.get('rp2040_flash_writes'):
                if any(x.serial_number.upper() == uid for x in rp_ports()):
                    call('app-to-bootsel', [pico, 'reboot', '-u', '-f', '--ser', uid]); time.sleep(2)
                call('rp2040-flash-restore', [pico, 'load', '-v', out/'host-flash-before.bin', '-t', 'bin', '-o', '0x10000000', '--ser', uid], timeout=600)
                result['rp2040_flash_writes'] = 2
            if before:
                result['host_flash_equal'] = flash_read('host-flash-after', uid) == before
                call('restore-host-reboot', [pico, 'reboot', '--ser', uid]); result['restored_host_port'] = wait_port(uid)
        except BaseException as ex: result['restore_host_error'] = repr(ex)
        save()

def analyze():
    sys.path.insert(0, str(root/'build/uv-cache/archive-v0/rlh7ljqubiQHl4bs'))
    import numpy as np
    wav = out/'demo-audio.wav'
    subprocess.run([str(ff), '-nostdin', '-y', '-v', 'error', '-i', str(out/'demo-hdmi.mkv'), '-vn', '-c:a', 'pcm_s16le', str(wav)], check=True)
    def load(path):
        with wave.open(str(path)) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (48000, 2, 2)
            return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(float)
    cap, ref = load(wav), load(reference)
    rms = np.sqrt(np.mean(cap[:len(cap)//480*480].reshape(-1, 480, 2)**2, axis=1))
    loud = np.flatnonzero(rms.max(1) > 150); onset, end = loud[0]/100, (loud[-1]+1)/100
    # Reference blocks that are audible: a capture block is "low" only where the reference is not.
    rref = np.sqrt(np.mean(ref[:len(ref)//480*480].reshape(-1, 480, 2)**2, axis=1))
    # Global alignment on the first 20 s (mono, FFT cross-correlation).
    a = cap[:, 0]+cap[:, 1]; b = ref[:, 0]+ref[:, 1]
    n = 1 << 22; seg = b[:20*48000]
    corr = np.fft.irfft(np.fft.rfft(a[:n], n)*np.conj(np.fft.rfft(seg, n)), n)
    lag = int(np.argmax(corr[:n-len(seg)]))
    # Track the slow HDMI/capture clock drift (~16 ppm): re-align every second.
    per_second, lags, low = [], [], [0, 0]
    seconds = int(min(len(b), len(a)-lag-48000)/48000)
    for s in range(seconds):
        y = b[s*48000:(s+1)*48000]
        lo = max(0, lag+s*48000-400); seg = a[lo:lag+(s+1)*48000+400]
        if np.std(y) >= 50:
            c = np.fft.irfft(np.fft.rfft(seg, 1 << 17)*np.conj(np.fft.rfft(y, 1 << 17)), 1 << 17)[:len(seg)-len(y)+1]
            k = int(np.argmax(c)); lags.append(lo+k-lag-s*48000)
            per_second.append(float(np.corrcoef(seg[k:k+48000], y)[0, 1]))
        d = lags[-1] if lags else 0
        for ch in (0, 1):
            x = cap[lag+s*48000+d:lag+(s+1)*48000+d, ch]; r = ref[s*48000:(s+1)*48000, ch]
            xb = np.sqrt(np.mean(x[:len(x)//480*480].reshape(-1, 480)**2, axis=1)); rb = np.sqrt(np.mean(r.reshape(-1, 480)**2, axis=1))
            low[ch] += int(np.sum((rb[:len(xb)] > 40) & (xb < 20)))
    result['audio'] = dict(lag_frames=lag, lag_s=lag/48000, onset_s=float(onset), audible_span_s=float(end-onset),
        low_10ms_blocks_where_reference_audible=low, drift_frames_first_last=[lags[0], lags[-1]] if lags else None, per_second_corr_min=min(per_second), per_second_corr_median=float(np.median(per_second)),
        seconds_below_0_9=int(sum(c < 0.9 for c in per_second)), seconds_compared=len(per_second),
        scope='Correlation against the PC render of the same integer synthesizer; init-time libm differences can lower it slowly')
    stills = out/'stills'; stills.mkdir(exist_ok=True)
    for t in (6, 24, 35, 52, 61, 79, 92, 100):
        subprocess.run([str(ff), '-nostdin', '-y', '-v', 'error', '-ss', str(lag/48000+t), '-i', str(out/'demo-hdmi.mkv'),
                        '-frames:v', '1', '-vf', 'scale=640:360', str(stills/f's{t}.png')], check=True)
    inputs = sum((['-i', str(stills/f's{t}.png')] for t in (6, 24, 35, 52, 61, 79, 92, 100)), [])
    subprocess.run([str(ff), '-nostdin', '-y', '-v', 'error', *inputs, '-filter_complex',
                    '[0][1]hstack[a];[2][3]hstack[b];[4][5]hstack[c];[6][7]hstack[d];[a][b][c][d]vstack=inputs=4', str(out/'contact-sheet.png')], check=True)
    result['recording_sha256'] = sha(out/'demo-hdmi.mkv')

if args.analyze_only: result.update(json.loads((out/'result.json').read_text()))
else: hardware()
if (out/'demo-hdmi.mkv').exists():
    try: analyze()
    except BaseException as ex: result['analysis_error'] = repr(ex)
save()
print(json.dumps({k: v for k, v in result.items() if k not in ('host_flash_before',)}, indent=2), flush=True)
sys.exit(0 if result['passed'] and result.get('host_flash_equal') and result.get('restore_fpga_user_code') == '0x00004068' else 1)
