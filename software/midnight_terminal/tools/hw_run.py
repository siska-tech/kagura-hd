"""One bounded native C campaign with physical HDMI/PCM capture. No retries."""
from pathlib import Path
import sys,json,time,subprocess,re
repo=Path(__file__).resolve().parents[3];out=repo/'build/midnight-hardware';sys.path.insert(0,str(repo/'build/showcase-hardware-deps'))
import serial
from serial.tools import list_ports
assert (out/'flash-write-verified.json').exists();assert not(out/'run.started').exists(),'No replay'
ports=[p for p in list_ports.comports() if p.vid==0x2e8a];assert len(ports)==1,[(p.device,p.pid) for p in ports]
ff=(out/'ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip()
state={'release_ready':False,'native_c':True,'nominal_qspi_hz':5000000,'started':False,'complete_loop':False,'failure':None,'scenes':[],'port':ports[0].device}
def save():(out/'run-result.json').write_text(json.dumps(state,indent=2))
(out/'run.started').write_text('one C firmware / one autoplay / first fault stops')
p=serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=5);capture=None;log=(out/'native-usb.log').open('wb');raw=bytearray();begin=time.monotonic()
try:
 deadline=time.monotonic()+20
 while b'USB CONTROL' not in raw:
  assert time.monotonic()<deadline,'native USB ready timeout';b=p.read(2048);raw.extend(b);log.write(b);log.flush()
 print(raw.decode(errors='replace'),flush=True)
 caplog=(out/'capture.log').open('wb')
 capture=subprocess.Popen([ff,'-hide_banner','-y','-f','dshow','-rtbufsize','256M','-video_size','1280x720','-framerate','60','-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio=デジタル オーディオ インターフェイス (UGREEN 15390)','-c:v','libx264','-preset','ultrafast','-crf','16','-pix_fmt','yuv420p','-c:a','pcm_s16le',str(out/'midnight-terminal-hardware.mkv')],stdin=subprocess.PIPE,stdout=caplog,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 time.sleep(3);assert capture.poll() is None,'capture failed before stimulus'
 p.write(b'g');state['started']=True;state['capture_started_seconds_before_g']=3;save();begin=time.monotonic();pending=bytearray();deadline=begin+240
 while time.monotonic()<deadline:
  b=p.read(4096)
  if b:log.write(b);log.flush();pending.extend(b)
  while b'\n' in pending:
   line,_,pending=pending.partition(b'\n');line=line.decode(errors='replace').strip();print(line,flush=True)
   if line.startswith('SCENE '):
    m=re.search(r'id=(\d+) host_ms=(\d+)',line)
    if m:
     scene={'id':int(m[1]),'host_ms':int(m[2]),'pc_elapsed_seconds':time.monotonic()-begin};state['scenes'].append(scene);save()
     if scene['id']==0 and scene['host_ms']>=88000:state['complete_loop']=True
   if 'PREFLIGHT PSRAM PASS' in line:state['psram_preflight_pass']=True;save()
   if 'PREFLIGHT GPU PASS' in line:state['gpu_preflight_pass']=True;save()
   if 'PREFLIGHT FAIL' in line or 'PREFLIGHT FILL FAIL' in line or 'PREFLIGHT BLIT FAIL' in line:raise RuntimeError(line)
   if 'STOP error=' in line:raise RuntimeError(line)
   if 'audio_fault=' in line and 'audio_fault=0' not in line:raise RuntimeError(line)
   if line.startswith('qspi_') and re.search(r'timeouts=[1-9]',line):raise RuntimeError(line)
  assert capture.poll() is None,'capture stopped unexpectedly'
  if state['complete_loop']:break
 assert state['complete_loop'],'full-loop deadline'
 state['wall_seconds_after_g']=time.monotonic()-begin;state['left_running']=True;save();print('NATIVE C FULL LOOP RECORDED',flush=True)
except BaseException as e:
 state['failure']=repr(e);state['wall_seconds_after_g']=time.monotonic()-begin;save()
 if state['started']:
  try:p.write(b'q');time.sleep(.4);log.write(p.read(p.in_waiting));log.flush()
  except Exception:pass
 print('STOPPED FIRST FAULT',repr(e),flush=True)
finally:
 p.close();log.close()
 if capture and capture.poll() is None:
  try:capture.communicate(b'q',timeout=15)
  except Exception:capture.kill();capture.wait()
 if capture:state['capture_exit']=capture.returncode
 save()
if state['failure']:sys.exit(1)
