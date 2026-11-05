"""New campaign after explicit stock-FW/FS authorization; preserve failed v1."""
from pathlib import Path
import json,hashlib,shutil
r=Path(__file__).resolve().parents[1];old=r/'build/showcase-hardware-2026-11-05-v1';out=r/'build/showcase-hardware-2026-11-05-v2'
assert not out.exists();out.mkdir();(out/'control').mkdir()
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
frozen=json.loads((old/'frozen-inputs.json').read_text());assert all(sha(old/x)==h for x,h in frozen.items())
for name in frozen:
 f=out/name;f.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old/name,f)
stock=json.loads((r/'build/showcase-stock-fw-2026-11-05-v1/switch-result.json').read_text())
assert stock['outcome']=='STOCK_FW_AND_EMPTY_FILESYSTEM_READY'
baseline=stock['full_flash_sha256']
source='''import sys,os,machine,gc,hashlib,binascii,uctypes
assert 'KAGURA' not in sys.implementation._machine and 'RP2040' in sys.implementation._machine
assert os.listdir('/')==[]
h=hashlib.sha256()
for o in range(0,2097152,1024):h.update(uctypes.bytearray_at(0x10000000+o,1024))
s=binascii.hexlify(h.digest()).decode();print('BEFORE_STOCK_FLASH_SHA256',s)
assert s==BASELINE
from machine import Pin
Pin(7,Pin.OUT,value=1);Pin(6,Pin.OUT,value=0)
for pin in range(2,6):Pin(pin,Pin.IN)
print('GPIO_SAFE',Pin(7).value(),Pin(6).value())
assert Pin(7).value()==1 and Pin(6).value()==0
gc.collect();print('STOCK_FREE_HEAP',gc.mem_free(),'RP_FREQUENCY',machine.freq())
assert gc.mem_free()>=150000
assert hasattr(binascii,'crc32')
'''.replace('BASELINE',repr(baseline))
(out/'preflight.py').write_text(source)
verify=(old/'verify_flash.py').read_text().replace('7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6',baseline).replace('RP2040_FLASH_UNCHANGED','RP2040_STOCK_FLASH_UNCHANGED_DURING_GPU_TESTS')
(out/'verify_flash.py').write_text(verify)
for name in ['restore_soft_reset.py']:
 (out/name).write_text((old/name).read_text().replace(old.relative_to(r).as_posix(),out.relative_to(r).as_posix()))
restore='''from pathlib import Path
import serial,time,ctypes,os,hashlib,json
from serial.tools import list_ports
root=Path(__file__).resolve().parent;repo=root.parents[1]
image=repo/'build/hardware-eval-097/recovery/current-flash-recovery.uf2'
assert hashlib.sha256(image.read_bytes()).hexdigest()=='4edd3bdcf17411049fe8ce58322c5bd0de2cbb5c41f1933ace1c440b7afaa44b'
assert not (root/'restore-rp.started').exists(),'No automatic restore replay'
def until(p,end,timeout=12):
 data=bytearray();deadline=time.monotonic()+timeout
 while not data.endswith(end):
  assert time.monotonic()<deadline,'restore REPL timeout'
  data.extend(p.read(1))
 return bytes(data)
def enter(p):
 p.write(b'\\r\\x03\\x03');time.sleep(.2);p.read(p.in_waiting);p.write(b'\\x01');assert b'raw REPL' in until(p,b'>')
def send(p,source,disconnect=False):
 for i in range(0,len(source),128):p.write(source[i:i+128].encode());time.sleep(.01)
 p.write(b'\\x04');assert p.read(2)==b'OK'
 if disconnect:return
 stdout=until(p,b'\\x04',30);err=until(p,b'\\x04',30);until(p,b'>')
 print(stdout[:-1].decode(),flush=True);assert err==b'\\x04',err
with serial.Serial('COM7',115200,timeout=.1,write_timeout=5) as p:
 enter(p);send(p,"import machine\\nmachine.bootloader()\\n",True)
deadline=time.monotonic()+25;target=None
while time.monotonic()<deadline and target is None:
 matches=[];mask=ctypes.windll.kernel32.GetLogicalDrives()
 for i in range(2,26):
  if mask&(1<<i):
   drive=Path(chr(65+i)+':/');info=drive/'INFO_UF2.TXT'
   try:
    if info.exists() and 'Board-ID: RPI-RP2' in info.read_text():matches.append(drive)
   except OSError:pass
 assert len(matches)<=1
 if matches:target=matches[0]
 time.sleep(.2)
assert target is not None
(root/'restore-rp.started').write_text('one full saved RP2040 restore, user authorized firmware/filesystem writes')
try:
 with (target/'KAGURA_ORIGINAL.uf2').open('wb') as f:f.write(image.read_bytes());f.flush();os.fsync(f.fileno())
except OSError as e:print('RESTORE_COPY_UNCERTAIN',repr(e),flush=True)
deadline=time.monotonic()+30
while time.monotonic()<deadline:
 if any(p.device=='COM7' and p.vid==0x2e8a and p.pid==5 for p in list_ports.comports()):break
 time.sleep(.3)
else:raise TimeoutError('restored serial absent')
time.sleep(2)
with serial.Serial('COM7',115200,timeout=.1,write_timeout=5) as p:
 enter(p)
 source="import hashlib,binascii,uctypes\\nh=hashlib.sha256()\\nfor o in range(0,2097152,1024):h.update(uctypes.bytearray_at(0x10000000+o,1024))\\ns=binascii.hexlify(h.digest()).decode();print('RESTORED_ORIGINAL_FLASH_SHA256',s)\\nassert s=='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'\\n"
 send(p,source);p.write(b'\\x02')
print('RP2040_ORIGINAL_FW_FILESYSTEM_RESTORED_EXACT',flush=True)
'''
(out/'restore-original-rp.py').write_text(restore)
runner=(old/'run.py').read_text()
runner=runner.replace("  if paused or state['sram_program_attempts']:","  if paused or state['sram_program_attempts'] or plan.get('user_authorized_rp2040_firmware_and_filesystem_initialization'):")
runner=runner.replace("   command([sys.executable,str(out/'restore_soft_reset.py')],'restore-soft-reset-host',20)","   command([sys.executable,str(out/'restore-original-rp.py')],'restore-original-rp-host',90)\n   state['recovery']['original_rp_fw_filesystem_restored_exact']=True\n   command([sys.executable,str(out/'restore_soft_reset.py')],'restore-soft-reset-host',20)")
(out/'run.py').write_text(runner)
plan=json.loads((out/'plan.json').read_text());plan['id']='SHOWCASE-HW-02-STOCK'
plan.update(rp2040_firmware='official RPI_PICO v1.26.0',rp2040_stock_flash_sha256=baseline,
 user_authorized_rp2040_firmware_and_filesystem_initialization=True,
 rp2040_fw_restore_at_end='original full backup, 1 attempt, exact old full SHA',previous_campaign='v1 stopped before SRAM, no replay')
plan['flash_fw_filesystem_writes']='RP2040 stock initialization and original restore authorized; none during GPU stimuli; FPGA Flash prohibited'
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
for f in out.rglob('*.py'):compile(f.read_text(),str(f),'exec')
manifest={str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()}
(out/'frozen-inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Frozen',len(manifest),'stock-FW campaign inputs; no device access')
