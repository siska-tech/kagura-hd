"""Explicit recovery action only. Restores PRIVATE saved RP flash + FPGA Flash image.
Does not write FPGA Flash. Do not run while intending to keep the showcase playing.
"""
from pathlib import Path
import sys,subprocess,time,json,hashlib
repo=Path(__file__).resolve().parents[3];out=repo/'build/midnight-hardware';sys.path.insert(0,str(repo/'build/showcase-hardware-deps'))
import serial
from serial.tools import list_ports
assert '--restore-original' in sys.argv,'Explicit --restore-original required'
assert not(out/'restore.started').exists(),'No automatic replay of restore'
backup=out/'recovery/current-flash-2MiB.bin';before=json.loads((out/'before.json').read_text());assert hashlib.sha256(backup.read_bytes()).hexdigest()==before['flash_sha256']
tool=out/'picotool/picotool/picotool.exe';programmer='C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe'
(out/'restore.started').write_text('restore original saved firmware; FPGA existing Flash Reprogram only')
ports=[p for p in list_ports.comports() if p.vid==0x2e8a];assert len(ports)==1
with serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=5) as p:
 p.write(b'q');deadline=time.monotonic()+12;data=bytearray()
 while b'STOP error=' not in data and b'CANCELLED' not in data:
  assert time.monotonic()<deadline,'safe-stop not confirmed';data.extend(p.read(2048))
 (out/'restore-stop.log').write_bytes(data)
def run(name,args):
 r=subprocess.run([str(a) for a in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120);(out/(name+'.log')).write_bytes(r.stdout);assert r.returncode==0,name
run('restore-flash',[tool,'load','-F','-v',backup]);run('restore-verify',[tool,'save','-r','0x10000000','0x10200000',out/'recovery/restored-check.bin'])
assert hashlib.sha256((out/'recovery/restored-check.bin').read_bytes()).hexdigest()==before['flash_sha256']
run('restore-fpga-existing-flash',[programmer,'--device','GW1NR-9C','--cable-index','1','--run','1'])
run('restore-rp-reboot',[tool,'reboot']);(out/'restore-result.json').write_text(json.dumps({'original_full_flash_sha256_verified':before['flash_sha256'],'fpga_flash_written':False,'fpga_existing_flash_reprogrammed':True,'release_ready':False},indent=2));print('Original Flash restored; normal KAGURA-9 boot requested')
