"""Recovery only. No diagnostic replay and no FPGA/PSRAM stimulus."""
from pathlib import Path
import serial,time,subprocess,sys,json,hashlib
r=Path(__file__).resolve().parents[1];out=r/'build/showcase-hardware-2026-11-05-v2'
assert not (out/'manual-recovery.started').exists(),'No repeated recovery operation'
(out/'manual-recovery.started').write_text('one recovery after raw REPL timeout; no diagnostic replay')
result={'diagnostic_replayed':False,'fpga_sram_programs_additional':0,'rp_restore_attempts':0}
def until(p,end,seconds=10):
 data=bytearray();deadline=time.monotonic()+seconds
 while not data.endswith(end):
  if time.monotonic()>deadline:raise TimeoutError('recovery serial synchronization failed')
  data.extend(p.read(1))
 return bytes(data)
try:
 with serial.Serial('COM7',115200,timeout=.1,write_timeout=5) as p:
  p.read(p.in_waiting);p.write(b'\r\x03\x03\x02')
  normal=until(p,b'>>> ',12);(out/'manual-recovery-friendly.bin').write_bytes(normal)
  p.write(b'\x01');raw=until(p,b'>');assert b'raw REPL' in raw
  source="""from machine import Pin
if '_q' in globals():_q.deinit()
Pin(7,Pin.OUT,value=1);Pin(6,Pin.OUT,value=0)
for pin in range(2,6):Pin(pin,Pin.IN)
print('RECOVERY_GPIO_SAFE',Pin(7).value(),Pin(6).value())
import hashlib,binascii,uctypes
h=hashlib.sha256()
for o in range(0,2097152,1024):h.update(uctypes.bytearray_at(0x10000000+o,1024))
print('STOCK_FLASH_BEFORE_RESTORE',binascii.hexlify(h.digest()).decode())
"""
  for i in range(0,len(source),128):p.write(source[i:i+128].encode());time.sleep(.01)
  p.write(b'\x04');assert p.read(2)==b'OK'
  stdout=until(p,b'\x04',20);stderr=until(p,b'\x04',20);until(p,b'>')
  (out/'manual-recovery-gpio.log').write_bytes(stdout+stderr)
  assert stderr==b'\x04';assert b'RECOVERY_GPIO_SAFE 1 0' in stdout
  p.write(b'\x02');until(p,b'>>> ')
 result['gpio_safe']=True
 def run(name,timeout):
  with (out/('manual-'+name+'.log')).open('wb') as log:
   p=subprocess.run([sys.executable,str(out/(name+'.py'))],cwd=r,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  assert p.returncode==0,(name,p.returncode)
 result['rp_restore_attempts']=1
 run('restore-original-rp',90);result['original_rp_full_flash_restored']=True
 run('restore_soft_reset',20);run('recovery_resume',20);run('recovery_state',10)
 result['banner_console_recovered']=True
 ffmpeg='ffmpeg';rgb=out/'kagura9-final-recovered.rgb';png=out/'kagura9-final-recovered.png'
 for name,args in [('capture',['-f','dshow','-video_size','1280x720','-framerate','60','-i','video=UGREEN 15390','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo',str(rgb)]),('png',['-f','rawvideo','-pixel_format','rgb24','-video_size','1280x720','-i',str(rgb),'-frames:v','1',str(png)])]:
  with (out/('manual-recovery-'+name+'.log')).open('wb') as log:
   p=subprocess.run([ffmpeg,'-hide_banner']+args,stdout=log,stderr=subprocess.STDOUT,timeout=25)
  assert p.returncode==0
 assert len(rgb.read_bytes())==1280*720*3 and any(rgb.read_bytes())
 result['hdmi_captured']=True;result['complete']=True
except BaseException as error:result['error']=repr(error);result['complete']=False;raise
finally:
 (out/'recovery-supplement.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
