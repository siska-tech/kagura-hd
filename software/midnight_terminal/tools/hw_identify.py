"""Read existing RP flash digest and release old pin owners. No flash/FPGA write."""
from pathlib import Path
import sys,json,time
repo=Path(__file__).resolve().parents[3];sys.path.insert(0,str(repo/'build/showcase-hardware-deps'));sys.path.insert(0,str(repo/'tools'))
import serial
from serial.tools import list_ports
from showcase_raw_session import RawSession
out=repo/'build/midnight-hardware';out.mkdir(exist_ok=True)
assert not (out/'identify.started').exists(),'Do not replay device jobs'
ports=[p for p in list_ports.comports() if p.vid==0x2e8a and p.pid==5];assert len(ports)==1,ports
(out/'identify.started').write_text('read identity + hash, release GPIO owners')
p=serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=5)
try:
 p.write(b'\r\x03\x03');time.sleep(.3);p.read(p.in_waiting);p.write(b'\x01');banner=bytearray();deadline=time.monotonic()+8
 while not banner.endswith(b'>'):
  assert time.monotonic()<deadline,'No raw REPL';banner.extend(p.read(1))
 assert b'raw REPL' in banner
 s=RawSession(p)
 code=b'''import sys,os,machine,hashlib,binascii,uctypes,json
assert 'RP2040' in sys.implementation._machine
h=hashlib.sha256()
for o in range(0,2097152,1024):h.update(uctypes.bytearray_at(0x10000000+o,1024))
state={'machine':sys.implementation._machine,'flash_sha256':binascii.hexlify(h.digest()).decode(),'frequency':machine.freq(),'uid':binascii.hexlify(machine.unique_id()).decode()}
if 'boot.py' in os.listdir('/'):
 state['boot_py_sha256']=binascii.hexlify(hashlib.sha256(open('/boot.py','rb').read()).digest()).decode()
if 'kagura_console' in globals():
 kagura_console.pause()
 kagura_console.close()
from machine import Pin
Pin(7,Pin.OUT,value=1);Pin(6,Pin.OUT,value=0)
for i in range(2,6):Pin(i,Pin.IN)
state['gpio_safe']=Pin(7).value()==1 and Pin(6).value()==0
print('STATE '+json.dumps(state))
'''
 result=s.transfer('identity-before-native',code,30);(out/'identify.log').write_bytes(result);print(result.decode())
 state=json.loads(next(l[6:] for l in result.decode().splitlines() if l.startswith('STATE ')));assert state['gpio_safe'];(out/'before.json').write_text(json.dumps(state,indent=2))
finally:p.close()
