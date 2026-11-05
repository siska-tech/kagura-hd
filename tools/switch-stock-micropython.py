"""User-authorized RP2040 stock FW + empty FS. One write, no retry.
Only the uniquely identified RP2040 ROM UF2 volume is a write target.
"""
from pathlib import Path
import serial,time,json,hashlib,ctypes,os,struct
from serial.tools import list_ports
r=Path(__file__).resolve().parents[1];out=r/'build/showcase-stock-fw-2026-11-05-v1'
plan=json.loads((out/'plan.json').read_text());uf2=out/'RPI_PICO-20250809-v1.26.0.uf2'
assert hashlib.sha256(uf2.read_bytes()).hexdigest()==plan['stock_uf2_sha256']
assert not (out/'stock-write.started').exists(),'No replay of firmware write'
log=(out/'switch.log').open('w',encoding='utf-8')
state={'user_authorized_fw_and_filesystem_initialization':True,'stock_write_attempts':0,'filesystem_format_attempts':0,'release_ready':False}
def save():(out/'switch-result.json').write_text(json.dumps(state,indent=2)+'\n')
def note(text):print(text,flush=True);log.write(text+'\n');log.flush()
def port():
 p=[p for p in list_ports.comports() if p.vid==0x2e8a and p.pid==5]
 assert len(p)==1,p
 return p[0].device
def until(p,marker,seconds=12):
 data=bytearray();deadline=time.monotonic()+seconds
 while not data.endswith(marker):
  if time.monotonic()>deadline:raise TimeoutError('serial deadline; no retry')
  data.extend(p.read(1))
 return bytes(data)
def enter(p):
 p.write(b'\r\x03\x03');time.sleep(.2);p.read(p.in_waiting);p.write(b'\x01')
 banner=until(p,b'>');assert b'raw REPL' in banner
def raw(p,source,key,timeout=30,disconnect=False):
 for i in range(0,len(source),128):p.write(source[i:i+128].encode());time.sleep(.01)
 p.write(b'\x04');ack=p.read(2);assert ack==b'OK',ack
 if disconnect:return
 stdout=until(p,b'\x04',timeout);stderr=until(p,b'\x04',timeout);until(p,b'>',timeout)
 (out/(key+'.log')).write_bytes(stdout+stderr)
 text=stdout[:-1].decode(errors='replace');note(text)
 assert stderr==b'\x04',stderr.decode(errors='replace')
 return text
def volume():
 matches=[];mask=ctypes.windll.kernel32.GetLogicalDrives()
 for i in range(2,26):
  if not mask&(1<<i):continue
  root=Path(chr(65+i)+':/');info=root/'INFO_UF2.TXT'
  try:
   if info.exists() and 'Board-ID: RPI-RP2' in info.read_text():matches.append(root)
  except OSError:pass
 assert len(matches)<=1,matches
 return matches[0] if matches else None
try:
 with serial.Serial(port(),115200,timeout=.1,write_timeout=5) as p:
  enter(p)
  text=raw(p,"""import sys,os,machine,gc,hashlib,binascii,uctypes
print('OLD_MACHINE',sys.implementation._machine)
assert 'RP2040' in sys.implementation._machine
h=hashlib.sha256()
for o in range(0,2097152,1024):h.update(uctypes.bytearray_at(0x10000000+o,1024))
s=binascii.hexlify(h.digest()).decode();print('OLD_FLASH_SHA256',s)
assert s=='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'
if 'kagura_console' in globals():kagura_console.pause();kagura_console.close()
from machine import Pin
Pin(7,Pin.OUT,value=1);Pin(6,Pin.OUT,value=0)
for pin in range(2,6):Pin(pin,Pin.IN)
print('OLD_GPIO_SAFE',Pin(7).value(),Pin(6).value())
""",'old-preflight')
  state['old_backup_verified']=True;save()
  raw(p,"import machine\nprint('ENTER_RP2040_ROM_BOOTLOADER')\nmachine.bootloader()\n",'enter-bootloader',disconnect=True)
 deadline=time.monotonic()+25;target=None
 while time.monotonic()<deadline and target is None:target=volume();time.sleep(.2)
 assert target is not None,'RP2040 UF2 volume absent'
 note('UF2_TARGET '+str(target))
 (out/'stock-write.started').write_text('one authorized stock FW write; no replay')
 state['stock_write_attempts']=1;save()
 try:
  with (target/'KAGURA_STANDARD.uf2').open('wb') as f:f.write(uf2.read_bytes());f.flush();os.fsync(f.fileno())
 except OSError as e:note('COPY_RETURN_UNCERTAIN '+repr(e))
 deadline=time.monotonic()+25
 while time.monotonic()<deadline:
  found=[p for p in list_ports.comports() if p.vid==0x2e8a and p.pid==5]
  if len(found)==1:break
  time.sleep(.3)
 else:raise TimeoutError('stock USB serial did not return')
 time.sleep(1)
 payload=b''.join(uf2.read_bytes()[i+32:i+288] for i in range(0,uf2.stat().st_size,512))
 payload_sha=hashlib.sha256(payload).hexdigest()
 with serial.Serial(port(),115200,timeout=.1,write_timeout=5) as p:
  enter(p)
  source="""import sys,hashlib,binascii,uctypes,machine
print('STOCK_MACHINE',sys.implementation._machine,'VERSION',sys.version)
assert 'KAGURA' not in sys.implementation._machine and 'RP2040' in sys.implementation._machine
h=hashlib.sha256()
for o in range(0,SIZE,1024):h.update(uctypes.bytearray_at(0x10000000+o,min(1024,SIZE-o)))
s=binascii.hexlify(h.digest()).decode();print('STOCK_FIRMWARE_PAYLOAD_SHA256',s);assert s==EXPECTED
""".replace('SIZE',str(len(payload))).replace('EXPECTED',repr(payload_sha))
  raw(p,source,'stock-verify');state['official_payload_verified']=True
  state['filesystem_format_attempts']=1;save()
  raw(p,"""import os,vfs,rp2,machine
if 'kagura_console' in globals():kagura_console.close()
try:vfs.umount('/')
except OSError:pass
bdev=rp2.Flash();vfs.VfsLfs2.mkfs(bdev,progsize=256)
fs=vfs.VfsLfs2(bdev,progsize=256);vfs.mount(fs,'/')
assert os.listdir('/')==[]
print('FILESYSTEM_INITIALIZED_EMPTY')
""",'filesystem-init')
  raw(p,"import machine\nmachine.soft_reset()\n",'clean-soft-reset',disconnect=True)
 time.sleep(2)
 with serial.Serial(port(),115200,timeout=.1,write_timeout=5) as p:
  enter(p)
  text=raw(p,"""import sys,os,machine,gc,hashlib,binascii,uctypes,json
gc.collect();assert os.listdir('/')==[]
from machine import Pin
Pin(7,Pin.OUT,value=1);Pin(6,Pin.OUT,value=0)
for pin in range(2,6):Pin(pin,Pin.IN)
h=hashlib.sha256()
for o in range(0,2097152,1024):h.update(uctypes.bytearray_at(0x10000000+o,1024))
print('STOCK_STATE '+json.dumps({'machine':sys.implementation._machine,'version':sys.version,'free_heap':gc.mem_free(),'full_flash_sha256':binascii.hexlify(h.digest()).decode(),'filesystem_empty':True,'frequency':machine.freq()}))
""",'bare-stock-state')
  p.write(b'\x02')
  state.update(json.loads(next(s[12:] for s in text.splitlines() if s.startswith('STOCK_STATE '))))
 state['outcome']='STOCK_FW_AND_EMPTY_FILESYSTEM_READY';save()
except BaseException as error:
 state['failure']=repr(error);state['outcome']='STOPPED_NO_RETRY';save();raise
finally:log.close()
