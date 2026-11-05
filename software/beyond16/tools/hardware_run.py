"""Explicitly authorized finite board test. First fault stops; no command replay."""
from pathlib import Path
import os
import sys,json,time,subprocess,re,datetime
repo=Path(__file__).resolve().parents[3];out=repo/'build/beyond16-hardware-2026-11-06';sys.path.insert(0,str(repo/'build/showcase-hardware-deps'))
import serial
from serial.tools import list_ports
mode=sys.argv[1];assert mode in ('bench','demo');assert(out/'flash-write-verified.json').exists();assert not(out/(mode+'.started')).exists()
ports=[p for p in list_ports.comports() if p.vid==0x2e8a and p.serial_number.upper()==os.environ['KAGURA_RP2040_UID'].upper()];assert len(ports)==1
state={'mode':mode,'release_ready':False,'port':ports[0].device,'started':False,'success':False,'failure':None,'start_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'perf':[]}
def save():(out/(mode+'-result.json')).write_text(json.dumps(state,indent=2))
p=serial.Serial(ports[0].device,115200,timeout=.1,write_timeout=5);capture=None;caplog=None;rawlog=(out/(mode+'-usb.log')).open('wb');raw=bytearray();(out/(mode+'.started')).write_text(state['start_utc']);begin=time.monotonic()
try:
 deadline=time.monotonic()+15
 while b'BEYOND 16 COLORS /' not in raw:
  assert time.monotonic()<deadline,'USB banner deadline';data=p.read(4096);raw.extend(data);rawlog.write(data);rawlog.flush()
 print(raw.decode(errors='replace'),flush=True)
 ff=(repo/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip();caplog=(out/(mode+'-capture.log')).open('wb')
 capture=subprocess.Popen([ff,'-hide_banner','-y','-f','dshow','-rtbufsize','256M','-video_size','1280x720','-framerate','60','-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio=デジタル オーディオ インターフェイス (UGREEN 15390)','-c:v','libx264','-preset','ultrafast','-crf','16','-pix_fmt','yuv420p','-c:a','pcm_s16le',str(out/(mode+'-hdmi.mkv'))],stdin=subprocess.PIPE,stdout=caplog,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 time.sleep(2);assert capture.poll() is None,'capture failed before stimulus';p.write(b'b' if mode=='bench' else b'g');begin=time.monotonic();state['started']=True;save();pending=bytearray();deadline=begin+(120 if mode=='bench' else 240);lastprint=0
 while time.monotonic()<deadline:
  data=p.read(8192)
  if data:rawlog.write(data);rawlog.flush();pending.extend(data)
  while b'\n' in pending:
   line,_,pending=pending.partition(b'\n');line=line.decode(errors='replace').strip()
   if line.startswith('PERF '):
    sample={k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)};sample['capture_elapsed_s']=time.monotonic()-begin;state['perf'].append(sample);save()
    if sample.get('audio_fault',0) or sample.get('timeouts',0):raise RuntimeError(line)
    if time.monotonic()-lastprint>8:print(line,flush=True);lastprint=time.monotonic()
   if line.startswith('BENCH') and ('PHASE' in line or 'n=' in line):print(line,flush=True)
   if line.startswith('BENCH') and re.search(r'rc=-?[1-9]',line):raise RuntimeError(line)
   if line.startswith('STOP '):
    print(line,flush=True);assert 'rc=0;' in line,line;state['success']=True;state['stop_elapsed_s']=time.monotonic()-begin;save();break
  assert capture.poll() is None,'capture exited during test'
  if state['success']:break
 assert state['success'],'campaign deadline without successful STOP'
 time.sleep(2)
except BaseException as ex:
 state['failure']=repr(ex);state['stop_elapsed_s']=time.monotonic()-begin;save();print('FIRST FAULT; NO RETRY:',repr(ex),flush=True)
 if state['started']:
  try:p.write(b'q');time.sleep(.3);rawlog.write(p.read(p.in_waiting));rawlog.flush()
  except Exception:pass
finally:
 p.close();rawlog.close()
 if capture and capture.poll() is None:
  try:capture.communicate(b'q',timeout=15)
  except Exception:capture.kill();capture.wait()
 if capture:state['capture_exit']=capture.returncode
 if caplog:caplog.close()
 save()
if state['failure']:sys.exit(1)
