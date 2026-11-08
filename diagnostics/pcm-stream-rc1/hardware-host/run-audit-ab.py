"""SRAM-only A/B hardware run for design-audit-report.md section 11 (T1-T3).

Same sequence as build/pcm-stream-rc1/stream-traffic-x/run.py: JTAG scan,
RP2040 flash read, FPGA SRAM load (no Flash write), RAM-only Host ELF,
UGREEN audio capture, one 25 s mode, restore approved Queue8 to FPGA SRAM,
RP2040 flash compare and reboot to the resident Host.

usage: run-audit-ab.py MODE OUTPUT_DIR [--image A|B]
"""
from pathlib import Path
import argparse, hashlib, json, os, re, struct, subprocess, sys, time

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root/'build/showcase-hardware-deps'))
import serial
from serial.tools import list_ports

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=list('xz5fryeaioGSR1EIOTX'))
parser.add_argument('out', type=Path)
parser.add_argument('--image', choices=['A', 'B', 'T8', 'custom'], default='A')
parser.add_argument('--image-path', type=Path, help="with --image custom: bitstream under build/")
parser.add_argument('--image-sha', help='with --image custom: expected SHA-256 of --image-path')
args = parser.parse_args()
out = args.out if args.out.is_absolute() else root/args.out
out.mkdir(parents=True, exist_ok=False)

pico = root/'build/midnight-hardware/picotool/picotool/picotool.exe'
programmer = Path('C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe')
images = {
    'A': (root/'build/pcm-stream-rc1/sta-short-control/native/impl/pnr/kagura_fb.fs',
          'de71d3fb2f45f2f119413659ef199ad72569bd8a74c6c1b68ad5ae44f119cbcb'),
    'B': (root/'artifacts/experimental/queue8-qspi-deglitch-rc1/kagura-hd-qspi-queue8-cs-deglitch-rc1.fs',
          '1f4aeec6f87cc6a8e795f8712047c335fe355045b74639454398a7acfd3ce46f'),
    # T8 diagnostic image: A inputs + t8-di-local.patch, P&R place 3 / route 2 / maxfan 23, STA clean.
    'T8': (root/'build/pcm-stream-rc1/t8-di-local/sta-p3-r2-f23/impl/pnr/kagura_fb.fs',
           'fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db'),
}
if args.image == 'custom':
    if not (args.image_path and args.image_sha): parser.error('--image custom needs --image-path and --image-sha')
    custom = (args.image_path if args.image_path.is_absolute() else root/args.image_path).resolve()
    if not custom.is_relative_to((root/'build').resolve()): parser.error('custom image must be under build/')
    images['custom'] = (custom, args.image_sha.lower())
candidate, candidate_sha = images[args.image]
restore = root/'build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8/impl/pnr/kagura_fb.fs'
elf = root/'build/pcm-stream-rc1/hardware-host-audit-t8/pcm_stream_hw.elf'
ELF_SHA = '5e08a679a69d601240ab87e6a36539f2ac34bb542580f94f5717d462076acad1'  # audit-t8; earlier: 82e73846 (T1-T3), d7e013d0 (T6/T7), b4e61dd4 (sweep)
ff = Path((root/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip())
numpy_path = root/'build/uv-cache/archive-v0/rlh7ljqubiQHl4bs'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(candidate) == candidate_sha
assert sha(restore) == '5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77'
assert sha(elf) == ELF_SHA
data = elf.read_bytes()
assert data[:6] == b'\x7fELF\x01\x01'
entry, offset = struct.unpack_from('<II', data, 24)
size, count = struct.unpack_from('<HH', data, 42)
loads = [s for s in (struct.unpack_from('<8I', data, offset+i*size) for i in range(count)) if s[0] == 1]
assert 0x20000000 <= entry < 0x20042000 and loads
assert all(0x20000000 <= s[2] == s[3] and s[3]+s[5] <= 0x20042000 and s[4] <= s[5] for s in loads)

result = dict(image=args.image, candidate_sha256=candidate_sha, elf_sha256=ELF_SHA, mode=args.mode, passed=False)
def save(): (out/'result.json').write_text(json.dumps(result, indent=2))
def call(name, cmd, timeout=120):
    with (out/(name+'.log')).open('xb') as log:
        subprocess.run(list(map(str, cmd)), stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout, cwd=root)
    print(name+' complete', flush=True)
    return (out/(name+'.log')).read_text(errors='replace')
def sram(name, image):
    code = re.search(r'^//UserCode: (0x[0-9A-Fa-f]+)', image.read_text(), re.M)[1]
    log = call(name, [programmer, '--device', 'GW1NR-9C', '--cable-index', '1', '--run', '2', '--fsFile', image])
    assert 'SRAM Program' in log and 'Finished.' in log and 'mismatch' not in log.lower()
    assert 'User Code is: '+code in log and 'Status Code is: 0x0003F020' in log
    return code
def flash_read(label, uid, force=False):
    path = out/(label+'.bin')
    call(label, [pico, 'save', '-r', '0x10000000', '0x10200000', '-v', path, '--ser', uid]+(['-F'] if force else []))
    assert path.stat().st_size == 2097152
    return sha(path)
def rp_ports():
    return [p for p in list_ports.comports() if p.vid == 0x2e8a and p.pid == 0x000a and p.serial_number]
def wait_port(uid, seconds=20):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        matches = [p for p in rp_ports() if p.serial_number.upper() == uid]
        if len(matches) == 1: return matches[0].device
        time.sleep(.2)
    raise RuntimeError('Expected USB serial port did not appear')

assert '0x1100481B' in call('jtag-scan', [programmer, '--cable-index', '1', '--scan'])
ports = rp_ports()
assert len(ports) == 1 and ports[0].device == 'COM5', [p.device for p in ports]
uid = ports[0].serial_number.upper()
assert uid != 'EEEEEEEEEEEEEEEE'
before = None
try:
    before = flash_read('host-flash-before', uid, True)
    result['host_flash_before'] = before
    result['fpga_user_code'] = sram('candidate-sram', candidate)
    call('rp2040-sram', [pico, 'load', '-v', '-x', elf, '--ser', uid])
    ram_port = wait_port('EEEEEEEEEEEEEEEE')
    result['ram_port'] = ram_port
    with serial.Serial(ram_port, 115200, timeout=.2, write_timeout=2) as port, (out/'stream-usb.log').open('xb') as log:
        raw = bytearray()
        def pump():
            chunk = port.read(4096)
            raw.extend(chunk); log.write(chunk); log.flush()
        deadline = time.monotonic()+10
        while b'PCM STREAM RC1 RAM HOST' not in raw:
            assert time.monotonic() < deadline, 'No dedicated-host banner'
            pump()
        assert b'I/O/T/X=i/o/S/x' in raw, 'Unexpected Host build'
        print('RAM Host banner confirmed', flush=True)
        with (out/'capture.log').open('xb') as capture_log:
            capture = subprocess.Popen([str(ff), '-hide_banner', '-f', 'dshow', '-rtbufsize', '256M',
                '-sample_rate', '48000', '-channels', '2',
                '-i', 'audio=デジタル オーディオ インターフェイス (UGREEN 15390)',
                '-c:a', 'flac', str(out/'stream-audio.mka')],
                stdin=subprocess.PIPE, stdout=capture_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                time.sleep(2)
                assert capture.poll() is None, 'Capture exited before test'
                port.write(args.mode.encode())
                result['started'] = True; save()
                print('mode', args.mode, 'started', flush=True)
                deadline = time.monotonic()+210
                while not re.search(rb'^STOP .*\r?\n', raw, re.M):
                    assert time.monotonic() < deadline, 'Test timed out'
                    assert capture.poll() is None, 'Capture exited during test'
                    pump()
                stop = re.search(rb'^STOP [^\r\n]+', raw, re.M)[0].decode()
                result['stop'] = stop
                print(stop, flush=True)
                assert 'rc=0 ' in stop and 'timeouts=0 ' in stop
                result['dummy_halves'] = int(re.search(rb'dummy_halves=(\d+)', raw)[1])
                assert result['dummy_halves'] >= 290
                result['passed'] = True
            finally:
                if capture.poll() is None:
                    try: capture.communicate(b'q', timeout=15)
                    except subprocess.TimeoutExpired: capture.kill(); capture.wait()
                result['capture_exit'] = capture.returncode
except BaseException as ex:
    result['error'] = repr(ex)
    print('Test stopped:', repr(ex), flush=True)
finally:
    try:
        if (out/'candidate-sram.log').exists():
            result['restore_fpga_user_code'] = sram('restore-sram', restore)
    except BaseException as ex:
        result['restore_fpga_error'] = repr(ex)
    try:
        if any(p.serial_number.upper() == 'EEEEEEEEEEEEEEEE' for p in rp_ports()):
            call('ram-to-bootsel', [pico, 'reboot', '-u', '-f', '--ser', 'EEEEEEEEEEEEEEEE'])
            time.sleep(1)
        if before:
            result['host_flash_equal'] = flash_read('host-flash-after', uid) == before
            call('restore-host-reboot', [pico, 'reboot', '--ser', uid])
            result['restored_host_port'] = wait_port(uid)
    except BaseException as ex:
        result['restore_host_error'] = repr(ex)
    save()

# Offline analysis of the capture; same method as the earlier x/z runs.
if (out/'stream-audio.mka').exists():
    try:
        call('wav-convert', [ff, '-hide_banner', '-i', out/'stream-audio.mka', '-c:a', 'pcm_s16le', out/'stream-audio.wav'])
        env = dict(os.environ, PYTHONPATH=str(numpy_path))
        analysis = subprocess.run([sys.executable, str(Path(__file__).with_name('analyze-phase.py')),
                                   str(out/'stream-audio.wav'), '291', '--marker-cycle', '2'],
                                  capture_output=True, text=True, env=env, cwd=root, timeout=300)
        (out/'phase-analysis.json').write_text(analysis.stdout + analysis.stderr)
        result['low_rms_10ms'] = json.loads(analysis.stdout)['low_rms_10ms_by_channel']
    except BaseException as ex:
        result['analysis_error'] = repr(ex)
    save()
print(json.dumps(result, indent=2), flush=True)
sys.exit(0 if result['passed'] and result.get('host_flash_equal') and result.get('restore_fpga_user_code') else 1)
