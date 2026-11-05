"""Single fixed-bitstream campaign. First failure stops stimuli; finally recovers."""
from pathlib import Path
import array,hashlib,importlib.util,json,subprocess,sys,time,traceback,wave

out=Path(__file__).resolve().parent
root=out.parents[1]
plan=json.loads((out/'plan.json').read_text())
manifest=json.loads((out/'frozen-inputs.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(out/p)==h for p,h in manifest.items()),'frozen stimulus changed'
candidate=root/'build/upload-rmw-worktree/build/standard-latched-rmw/impl/pnr/kagura_fb.fs'
assert sha(candidate)==plan['bitstream_sha256']
recovery=root/'build/hardware-eval-097/recovery'
assert sha(recovery/'current-flash-2MiB.bin')=='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6'
assert sha(recovery/'current-flash-recovery.uf2')=='4edd3bdcf17411049fe8ce58322c5bd0de2cbb5c41f1933ace1c440b7afaa44b'
assert not (out/'campaign-start.marker').exists(),'refuse replay'
(out/'campaign-start.marker').write_text(time.strftime('%Y-%m-%dT%H:%M:%S'))
spec=importlib.util.spec_from_file_location('measurement',out/'measurement.py')
measurement=importlib.util.module_from_spec(spec);spec.loader.exec_module(measurement)
programmer='C:/Gowin/Gowin_V1.9.12.04_x64/Programmer/bin/programmer_cli.exe'
audio_name='デジタル オーディオ インターフェイス (UGREEN 15390)'
state=dict(campaign=plan['campaign'],bitstream_sha256=sha(candidate),release_ready=False,
    cases=[],measurements=[],failure=None,recovery={},sram_program_attempts=0,
    preflight_fpga_recovery_file_hash_waived_by_user=True)
start=time.monotonic();worker=None;worker_log=None;connected=False;preflight=False

def save():
 (out/'result.json').write_text(json.dumps(state,indent=2)+'\n')
def command(args,name,timeout=60):
 with (out/(name+'.log')).open('wb') as f:
  p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 assert p.returncode==0,(name,p.returncode)
 return (out/(name+'.log')).read_text(errors='replace')
def job(key,path):
 assert key.startswith(('080-','090-')) or time.monotonic()-start<plan['campaign_timeout_seconds'],'campaign time limit'
 command([sys.executable,str(out/'dispatch.py'),key,str(path)],key+'-dispatch',65)
 log=(out/'control'/f'{key}.log').read_text()
 events=[json.loads(line[4:]) for line in log.splitlines() if line.startswith('CMP ')]
 for e in events:
  if e['event']=='compare':assert e['actual']==e['expected'] and not int(e['xor'] or '0',16),e
  if e['event']=='health':assert not e['error'] and not e['status']&0x8c,e
 return events
def image_capture(tid,rois=None):
 rgb=out/(tid+'.rgb')
 command(['ffmpeg','-hide_banner','-f','dshow','-video_size','1280x720','-framerate','60','-i','video=UGREEN 15390','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo',str(rgb)],tid+'-capture',15)
 command(['ffmpeg','-hide_banner','-f','rawvideo','-pixel_format','rgb24','-video_size','1280x720','-i',str(rgb),'-frames:v','1',str(out/(tid+'.png'))],tid+'-png',15)
 if rois is not None:
  measured=measurement.video(rgb,rois)
  state['measurements'].append(dict(id=tid,kind='HDMI_ROI',results=measured));save()
 else:assert any(rgb.read_bytes()),'blank recovery/preflight image'
def av_capture(tid,seconds):
 path=out/(tid+'.mkv')
 command(['ffmpeg','-hide_banner','-f','dshow','-video_size','1280x720','-framerate','60','-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio='+audio_name,
   '-t',str(seconds),'-c:v','ffv1','-c:a','pcm_s16le',str(path)],tid+'-av',seconds+20)
 wav=out/(tid+'.wav')
 command(['ffmpeg','-hide_banner','-i',str(path),'-vn','-acodec','pcm_s16le',str(wav)],tid+'-wav',15)
 return wav
def verify_memory_case(c,events):
 assert any(e.get('event')=='pass' and e.get('test_id')==c['id'] for e in events),'missing pass'
 count=0
 for e in events:
  if e['event']!='compare':continue
  count+=1
  if c['kind']=='upload':expected=c['data'];assert e['address']==c['offset']
  elif 'guard' in e['role'] or e['role']=='other-address':
   expected=next(g['expected'] for g in c['guards'] if g['address']==e['address'])
  else:
   off=e['address']-c['address'];expected=c['expected'][off*2:(off+e['length'])*2]
  assert e['expected']==expected and e['actual']==expected,('PC oracle mismatch',c['id'],e)
 assert count>0

try:
 from serial.tools import list_ports
 ports=[dict(device=p.device,vid=p.vid,pid=p.pid) for p in list_ports.comports()]
 assert any(p['device']=='COM7' and p['vid']==0x2e8a and p['pid']==5 for p in ports)
 assert any(p['device']=='COM8' and p['vid']==0x403 and p['pid']==0x6010 for p in ports)
 state['ports']=ports
 scan=command([programmer,'--scan','--cable-index','1'],'jtag-scan')
 assert '0x1100481B' in scan and '1 device(s)' in scan
 image_capture('kagura9-before')
 # Prove the capture chain can deliver native stereo audio and video BEFORE SRAM load.
 wav=av_capture('measurement-preflight',1)
 with wave.open(str(wav),'rb') as f:assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(2,2,48000) and f.getnframes()>40000
 worker_log=(out/'serial-worker.log').open('wb')
 worker=subprocess.Popen([sys.executable,'-u',str(out/'serial_worker.py')],stdout=worker_log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+8
 while not (out/'control/worker.ready').exists():
  assert worker.poll() is None and time.monotonic()<deadline,'raw connection failed'
  time.sleep(.1)
 connected=True
 job('001-preflight',out/'preflight.py');preflight=True
 for i,p in enumerate(sorted((out/'method-jobs').glob('*.py'))):job(f'010-load-{i:03}',p)
 job('015-engine',out/'engine.py');job('016-gpu-helper',out/'gpu-helper.py')
 # One attempt only; no alternative fs and no retry on uncertain programming.
 assert sha(candidate)==plan['bitstream_sha256']
 state['sram_program_attempts']=1;save()
 log=command([programmer,'--device','GW1NR-9C','--cable-index','1','--run','2','--fsFile',str(candidate)],'sram-program')
 assert 'SRAM Program' in log and 'Finished.' in log and 'Error' not in log
 job('020-identity',out/'identity.py')
 for c in plan['cases']:
  state['active_case']=c['id'];save()
  events=job('case-'+c['id'],out/'jobs'/(c['id']+'.py'))
  verify_memory_case(c,events)
  state['cases'].append(dict(id=c['id'],stage=c['stage'],status='PASS',comparisons=sum(e['event']=='compare' for e in events)))
  save();print('PASS',c['id'],flush=True)
 for c in plan['gpu_cases']:
  state['active_case']=c['id'];save()
  events=job('case-'+c['id'],out/'jobs'/(c['id']+'.py'))
  assert any(e.get('event')=='pass' for e in events)
  for address,expected in c['checks']:
   assert any(e.get('event')=='compare' and e['address']==address and e['actual']==expected for e in events)
  image_capture(c['id'],c['rois'])
  state['cases'].append(dict(id=c['id'],stage=5,status='PASS_FRAMEBUFFER_AND_HDMI'));save()
 for c in plan['audio_cases']:
  state['active_case']=c['id'];save()
  job('case-'+c['id'],out/'jobs'/(c['id']+'.py'))
  wav=av_capture(c['id'],3)
  result=measurement.audio(wav,c)
  # Status check after capture as well as before it.
  job('status-'+c['id'],out/'post-capture-health.py')
  state['measurements'].append(dict(id=c['id'],kind='HDMI_audio',result=result))
  state['cases'].append(dict(id=c['id'],stage=6,status='PASS_LIMITED_MIXED_AUDIO'));save()
 state['stage7']='NOT_RUN: fixed-top individual six-voice and detailed FIFO observability incomplete, as predeclared'
 state['outcome']='LIMITED_CAMPAIGN_PASS_WITH_MEASUREMENT_LIMITATIONS'
except Exception:
 state['failure']=dict(case=state.get('active_case','PREFLIGHT'),traceback=traceback.format_exc())
 state['outcome']='STOPPED_FIRST_ERROR';save();print(state['failure']['traceback'],flush=True)
finally:
 # Recovery never executes diagnostic WRITE or resends the failed case.
 try:
  if connected:
   try:job('080-release',out/'release_pins.py')
   except Exception:state['recovery']['gpio_error']=traceback.format_exc()
  if state['sram_program_attempts']:
   log=command([programmer,'--device','GW1NR-9C','--cable-index','1','--run','1'],'restore-fpga')
   assert 'Reprogram' in log and 'Finished.' in log
   state['recovery']['fpga_reprogram']=True
  if connected:
   job('090-flash-verify',out/'verify_flash.py')
   state['recovery']['rp2040_flash_unchanged']=True
   (out/'control/worker.stop').write_text('stop; no diagnostic replay')
   worker.wait(timeout=8);connected=False
  if worker_log:worker_log.close()
  if preflight or state['sram_program_attempts']:
   command([sys.executable,str(out/'restore_soft_reset.py')],'restore-soft-reset-host',20)
   command([sys.executable,str(out/'recovery_resume.py')],'recovery-resume-host',20)
   command([sys.executable,str(out/'recovery_state.py')],'recovery-state-host',10)
   image_capture('kagura9-restored')
   state['recovery']['soft_reset_banner']=True
   state['recovery']['console_resume']=True
   state['recovery']['hdmi_capture']=True
 except Exception:
  state['recovery']['error']=traceback.format_exc()
  print('RECOVERY_INCOMPLETE',state['recovery']['error'],flush=True)
 state['elapsed_seconds']=round(time.monotonic()-start,3)
 state['release_ready']=False;save()
 hashes={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'}
 (out/'evidence-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
 print(json.dumps(state,indent=2),flush=True)
