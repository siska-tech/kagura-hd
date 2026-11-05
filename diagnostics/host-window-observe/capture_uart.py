import serial,time,json,sys,os
from pathlib import Path
from serial.tools import list_ports
out=Path(sys.argv[1]);data=bytearray();last=None;armed=False
assert not (out/'uart-full.bin').exists(),'Refusing capture replay'
assert any(p.device=='COM8' and p.vid==0x0403 and p.pid==0x6010 for p in list_ports.comports())
p=serial.Serial();p.port='COM8';p.baudrate=115200;p.timeout=.05;p.dtr=False;p.rts=False
deadline=time.monotonic()+300
try:
 p.open();(out/'uart-open.ready').write_text('115200 8N1 RX only')
 while time.monotonic()<deadline:
  if not armed and (out/'trial.marker').exists():armed=True;deadline=time.monotonic()+8
  chunk=p.read(max(1,min(p.in_waiting,4096)))
  if chunk:
   data.extend(chunk);last=time.monotonic()
   with (out/'uart-full.bin').open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
   if not armed:raise RuntimeError('UART before arm')
   if len(data)>136:raise RuntimeError('extra UART bytes')
  if len(data)==136 and last and time.monotonic()-last>=1:
   (out/'uart-complete.ready').write_text('136B + 1s quiet');break
  if (out/'uart-stop.marker').exists():break
 else:raise TimeoutError('capture timeout')
except Exception as exc:
 (out/'uart-error.txt').write_text(repr(exc));raise
finally:
 p.close();(out/'uart-full.bin').write_bytes(data)
 (out/'uart-capture.json').write_text(json.dumps(dict(bytes=len(data),armed=armed,serial_writes=0),indent=2))
 print('UART_CAPTURE',len(data),flush=True)
