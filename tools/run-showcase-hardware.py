"""One fixed SRAM campaign. Stop on first fault; recover without stimulus retry."""
from pathlib import Path
import sys,json,time,hashlib,subprocess,traceback,importlib.util,threading
out=Path(__file__).resolve().parent;r=out.parents[1]
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
plan=json.loads((out/'plan.json').read_text());frozen=json.loads((out/'frozen-inputs.json').read_text())
assert all(sha(out/f)==h for f,h in frozen.items())
assert not (out/'started.marker').exists(),'No replay'
candidate=r/'artifacts/validated/kagura-hd-qspi-pcm2.fs'
assert sha(candidate)==plan['bitstream_sha256']
recovery=r/'build/hardware-eval-097/recovery'
assert sha(recovery/'current-flash-2MiB.bin')=='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'
assert sha(recovery/'current-flash-recovery.uf2')=='4edd3bdcf17411049fe8ce58322c5bd0de2cbb5c41f1933ace1c440b7afaa44b'
spec=importlib.util.spec_from_file_location('measure',out/'measurement.py');measure=importlib.util.module_from_spec(spec);spec.loader.exec_module(measure)
programmer='C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe'
ffmpeg='ffmpeg';state={'id':plan['id'],'release_ready':False,'cases':[],'failure':None,'recovery':{},'sram_program_attempts':0,'bitstream_sha256':sha(candidate)}
started=time.monotonic();worker=None;worker_log=None;connected=False;paused=False;capture=None
def save():(out/'result.json').write_text(json.dumps(state,indent=2)+'\n')
def command(args,key,timeout=60):
 with (out/(key+'.log')).open('wb') as log:p=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
 assert p.returncode==0,(key,p.returncode)
 return (out/(key+'.log')).read_text(errors='replace')
def events(key):
 text=(out/'control'/(key+'.log')).read_text(encoding='utf-8')
 return [json.loads(line.split(' ',1)[1]) for line in text.splitlines() if line.startswith(('CMP ','SC '))]
def job(key,path,timeout=120,recover=False):
 if not recover:assert time.monotonic()-started<plan['campaign_max_seconds'],'campaign deadline'
 control=out/'control'
 assert not any((control/(key+s)).exists() for s in ('.request.json','.sent','.result.json')),'No replay '+key
 (control/(key+'.request.json')).write_text(json.dumps({'path':str(path),'timeout':timeout}))
 deadline=time.monotonic()+timeout+15
 while not (control/(key+'.result.json')).exists():
  assert worker.poll() is None and time.monotonic()<deadline,'uncertain raw job; STOP'
  time.sleep(.1)
 result=json.loads((control/(key+'.result.json')).read_text())
 assert result['ok'],(key,result)
 data=events(key)
 for e in data:
  if e.get('event')=='compare':assert e['expected']==e['actual'],e
 print('PASS_JOB',key,flush=True)
 return data
def capture_image(tid,expected=None):
 rgb=out/(tid+'.rgb')
 command([ffmpeg,'-hide_banner','-f','dshow','-video_size','1280x720','-framerate','60','-i','video=UGREEN 15390','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo',str(rgb)],tid+'-capture',20)
 command([ffmpeg,'-hide_banner','-f','rawvideo','-pixel_format','rgb24','-video_size','1280x720','-i',str(rgb),'-frames:v','1',str(out/(tid+'.png'))],tid+'-png',20)
 if expected:return measure.video(rgb,expected,plan)
 assert len(rgb.read_bytes())==1280*720*3 and any(rgb.read_bytes())
def capture_av(tid,seconds):
 path=out/(tid+'.mkv')
 command([ffmpeg,'-hide_banner','-f','dshow','-video_size','1280x720','-framerate','60','-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio=デジタル オーディオ インターフェイス (UGREEN 15390)','-t',str(seconds),'-c:v','ffv1','-c:a','pcm_s16le',str(path)],tid+'-av',seconds+30)
 wav=out/(tid+'.wav')
 command([ffmpeg,'-hide_banner','-i',str(path),'-vn','-c:a','pcm_s16le',str(wav)],tid+'-wav',20)
 return wav
def success(tid,**values):
 state['cases'].append({'id':tid,'status':'PASS',**values});save();print('PASS_CASE',tid,flush=True)
try:
 (out/'started.marker').write_text(time.strftime('%Y-%m-%dT%H:%M:%S'))
 from serial.tools import list_ports
 ports=[{'device':p.device,'vid':p.vid,'pid':p.pid} for p in list_ports.comports()]
 assert any(p['device']=='COM7' and p['vid']==0x2e8a and p['pid']==5 for p in ports)
 assert any(p['device']=='COM8' and p['vid']==0x403 and p['pid']==0x6010 for p in ports)
 state['ports']=ports
 scan=command([programmer,'--scan','--cable-index','1'],'jtag-scan')
 assert '0x1100481B' in scan and '1 device(s)' in scan
 capture_image('kagura9-before')
 capture_av('capture-preflight',1)
 worker_log=(out/'serial-worker.log').open('wb')
 worker=subprocess.Popen([sys.executable,'-u',str(out/'serial_worker.py')],stdout=worker_log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+8
 while not (out/'control/worker.ready').exists():
  assert worker.poll() is None and time.monotonic()<deadline,'COM raw connect failed'
  time.sleep(.1)
 connected=True;paused=True
 job('001-preflight',out/'preflight.py')
 loader=json.loads((out/'ram-loader/manifest.json').read_text())
 for i,item in enumerate(loader):job('010-ram-%02d'%i,out/'ram-loader'/item['packet'])
 job('015-aliases',out/'aliases.py');job('016-engine',out/'engine.py')
 assert sha(candidate)==plan['bitstream_sha256']
 state['sram_program_attempts']=1;save()
 text=command([programmer,'--device','GW1NR-9C','--cable-index','1','--run','2','--fsFile',str(candidate)],'sram-program',180)
 assert 'SRAM Program' in text and 'Finished.' in text and 'Error' not in text
 job('020-identity',out/'identity.py')
 for c in plan['memory_cases']:
  tid=c['id'];state['active_case']=tid;save();data=job('mem-'+tid,out/'jobs'/(tid+'.py'))
  assert any(e.get('event')=='pass' and e.get('test_id')==tid for e in data)
  for e in data:
   if e.get('event')!='compare':continue
   if c['kind']=='upload':expect=c['data']
   elif 'guard' in e['role'] or e['role']=='other-address':expect=next(g['expected'] for g in c['guards'] if g['address']==e['address'])
   else:
    offset=e['address']-c['address'];expect=c['expected'][offset*2:(offset+e['length'])*2]
   assert expect==e['expected']==e['actual'],e
  success(tid,kind='memory',comparisons=sum(e.get('event')=='compare' for e in data))
 state['psram_cases_passed']=True;save()
 job('030-runtime',out/'runtime.py')
 for i,c in enumerate(plan['graphics']):
  tid=c['id'];state['active_case']=tid;save();job('gfx-'+tid,out/'jobs'/c['job'])
  if c['crc_check']:
   for page,expected in enumerate(c['expected']['crc']):
    path=out/'jobs'/(tid+'-crc%d.py'%page)
    job('crc-'+tid+'-%d'%page,path)
  measured=capture_image(tid,c['expected']);success(tid,kind='graphics',capture=measured)
  last=i+1==len(plan['graphics']) or plan['graphics'][i+1]['id'][1]!=tid[1]
  if last:job(tid[:2]+'-leave',out/'jobs'/(tid[:2]+'-leave.py'))
 for mode in range(4):
  tid='A%d'%mode;state['active_case']=tid;save();job('audio-'+tid,out/'jobs'/(tid+'.py'))
  wav=capture_av(tid,3);result=measure.audio(wav,mode,plan,plan['tone_hex'])
  job('health-'+tid,out/'jobs'/'health.py');success(tid,kind='functional_PCM',measurement=result)
 job('audio-stop',out/'jobs'/'A0.py')
 job('bgm-init',out/'jobs'/'BGM-init.py')
 for c in plan['bgm_chunks']:
  state['active_case']=c['id'];save();data=job(c['id'],out/'jobs'/c['job'])
  assert any(e.get('event')=='pcm_crc' and e['actual']==c['crc32']==e['expected'] for e in data)
  success(c['id'],kind='PCM_buffer',crc32=c['crc32'],length=c['length'])
 state['active_case']='BGM-play';save();job('bgm-play',out/'jobs'/'BGM-play.py')
 capture_image('G6-BGM');capture_av('BGM',3);job('health-BGM',out/'jobs'/'health.py')
 job('bgm-stop',out/'jobs'/'BGM-stop.py');success('BGM',kind='captured_original_music',note='no bit-exact UGREEN sample qualification')
 state['active_case']='FULL';save()
 caplog=(out/'full-capture.log').open('wb')
 capture=subprocess.Popen([ffmpeg,'-hide_banner','-f','dshow','-video_size','1280x720','-framerate','60','-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio=デジタル オーディオ インターフェイス (UGREEN 15390)','-t',str(plan['full_loop_max_seconds']),'-c:v','libx264','-preset','fast','-crf','18','-c:a','pcm_s16le',str(out/'full-showcase.mkv')],stdin=subprocess.PIPE,stdout=caplog,stderr=subprocess.STDOUT)
 time.sleep(1);assert capture.poll() is None,'full capture failed to start'
 data=job('full-loop',out/'jobs'/'FULL.py',plan['full_loop_max_seconds'])
 if capture.poll() is None:capture.stdin.write(b'q\n');capture.stdin.flush()
 capture.wait(timeout=20);capture=None;caplog.close()
 assert len([e for e in data if e.get('event')=='scene_end'])==6
 assert len([e for e in data if e.get('event')=='frame'])==288
 assert any(e.get('event')=='complete' for e in data)
 assert any(e.get('event')=='cursor_crc' and e.get('pass_crc') for e in data)
 success('FULL',kind='one_finite_loop',updates=288)
 state['outcome']='FUNCTIONAL_SHOWCASE_PASS_WITH_CAPTURE_LIMITATIONS'
except Exception:
 state['failure']={'case':state.get('active_case','PREFLIGHT'),'traceback':traceback.format_exc()};state['outcome']='STOPPED_FIRST_ERROR';save();print(state['failure']['traceback'],flush=True)
finally:
 if capture is not None:
  try:
   if capture.poll() is None:capture.stdin.write(b'q\n');capture.stdin.flush()
   capture.wait(timeout=20)
  except Exception:state['capture_stop_error']=traceback.format_exc()
 try:
  if connected:
   try:job('080-release',out/'release_pins.py',recover=True)
   except Exception:state['recovery']['gpio_error']=traceback.format_exc()
  if state['sram_program_attempts']:
   text=command([programmer,'--device','GW1NR-9C','--cable-index','1','--run','1'],'restore-fpga')
   assert 'Reprogram' in text and 'Finished.' in text;state['recovery']['fpga_reprogram']=True
  if connected:
   job('090-flash',out/'verify_flash.py',recover=True);state['recovery']['rp2040_flash_unchanged']=True
   (out/'control/worker.stop').write_text('stop, no replay');worker.wait(timeout=8);connected=False
  if worker_log:worker_log.close()
  if paused or state['sram_program_attempts']:
   command([sys.executable,str(out/'restore_soft_reset.py')],'restore-soft-reset-host',20)
   command([sys.executable,str(out/'recovery_resume.py')],'recovery-resume-host',20)
   command([sys.executable,str(out/'recovery_state.py')],'recovery-state-host',10)
   capture_image('kagura9-restored');state['recovery']['banner_console_hdmi']=True
 except Exception:state['recovery']['error']=traceback.format_exc();print('RECOVERY_INCOMPLETE',state['recovery']['error'],flush=True)
 state['elapsed_seconds']=time.monotonic()-started;state['release_ready']=False
 state['frozen_inputs_unchanged']=all(sha(out/f)==h for f,h in frozen.items());state['bitstream_hash_unchanged']=sha(candidate)==plan['bitstream_sha256'];save()
 (out/'evidence-sha256.json').write_text(json.dumps({str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file() and f.name!='evidence-sha256.json'},indent=2)+'\n')
 print(json.dumps(state,indent=2),flush=True)
