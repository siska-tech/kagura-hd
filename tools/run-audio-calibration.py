"""Play only explicit HDMI output; capture each calibration condition once."""
from pathlib import Path
import hashlib,json,subprocess,time,traceback,wave
import numpy as np
import sounddevice as sd

out=Path(__file__).resolve().parent
plan=json.loads((out/'plan.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((out/'frozen-inputs.json').read_text());assert all(sha(out/p)==h for p,h in frozen.items())
assert not (out/'started.marker').exists(),'no replay'
(out/'started.marker').write_text(time.strftime('%Y-%m-%dT%H:%M:%S'))
devices=list(sd.query_devices());apis=list(sd.query_hostapis())
pick=lambda part,kind:[d for d in devices if apis[d['hostapi']]['name']=='Windows WASAPI' and part in d['name'] and d[f'max_{kind}_channels']>=2]
outputs=pick(plan['playback_device_name_contains'],'output');inputs=pick(plan['capture_device_name_contains'],'input')
assert len(outputs)==len(inputs)==1,(outputs,inputs)
output=outputs[0];input_=inputs[0]
settings=sd.WasapiSettings(exclusive=True,explicit_sample_format=True)
sd.check_output_settings(device=output['index'],channels=2,dtype='int16',samplerate=48000,extra_settings=settings)
sd.check_input_settings(device=input_['index'],channels=2,dtype='int16',samplerate=48000,extra_settings=settings)
state=dict(id=plan['id'],output=output,input=input_,devices=devices,apis=apis,
    sounddevice_version=sd.__version__,portaudio=sd.get_portaudio_version(),cases=[],failure=None,FPGA_access=False)
started=time.monotonic()
try:
 for case in plan['cases']:
  assert time.monotonic()-started<plan['maximum_seconds']
  reference=out/plan['references'][case['reference']]['path']
  assert sha(reference)==plan['references'][case['reference']]['sha256']
  with wave.open(str(reference),'rb') as f:source=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2)
  assert np.array_equal(source[:,0],source[:,1])
  played=[0];flags=[]
  def callback(buffer,frames,time_info,status):
   if status:flags.append(str(status))
   begin=played[0];end=begin+frames;count=max(0,min(frames,len(source)-begin))
   buffer.fill(0)
   if count:buffer[:count]=source[begin:begin+count]
   played[0]=end
  target=out/(case['id']+'.wav');overflow_count=0
  with sd.OutputStream(samplerate=48000,device=output['index'],channels=2,dtype='int16',blocksize=960,
      latency=.1,extra_settings=settings,callback=callback,clip_off=True,dither_off=True):
   time.sleep(.6)
   if case['path']=='DirectShow_AV_original':
    with (out/(case['id']+'-capture.log')).open('wb') as log:
     p=subprocess.run(['ffmpeg','-hide_banner','-f','dshow','-video_size','1280x720','-framerate','60',
      '-sample_rate','48000','-channels','2','-i','video=UGREEN 15390:audio='+input_['name'],
      '-t','3','-c:v','ffv1','-c:a','pcm_s16le',str(out/(case['id']+'.mkv'))],stdout=log,stderr=subprocess.STDOUT,timeout=20)
    assert p.returncode==0,'DirectShow acquisition failed'
   else:
    blocks=[]
    with sd.RawInputStream(samplerate=48000,device=input_['index'],channels=2,dtype='int16',blocksize=960,
       latency=.1,extra_settings=settings) as stream:
     for _ in range(150):
      data,overflow=stream.read(960);blocks.append(bytes(data));overflow_count+=int(overflow)
    with wave.open(str(target),'wb') as f:f.setparams((2,2,48000,0,'NONE','NONE'));f.writeframes(b''.join(blocks))
  assert not flags and not overflow_count,dict(render_status=flags,capture_overflow=overflow_count)
  assert played[0]<len(source),'reference exhausted'
  if case['path']=='DirectShow_AV_original':
   with (out/(case['id']+'-extract.log')).open('wb') as log:
    p=subprocess.run(['ffmpeg','-hide_banner','-i',str(out/(case['id']+'.mkv')),'-vn','-acodec','pcm_s16le',str(target)],stdout=log,stderr=subprocess.STDOUT,timeout=15)
   assert p.returncode==0
  with wave.open(str(target),'rb') as f:
   assert (f.getframerate(),f.getsampwidth(),f.getnchannels())==(48000,2,2)
   frames=f.getnframes();assert 140000<=frames<=148000
  record=dict(**case,status='ACQUIRED_ONCE',capture=target.name,capture_sha256=sha(target),frames=frames,
    output_frames_submitted=played[0],render_status=flags,input_overflows=overflow_count)
  state['cases'].append(record)
  (out/'acquisition.json').write_text(json.dumps(state,indent=2)+'\n')
  print('ACQUIRED',case['id'],case['reference'],frames,flush=True)
except Exception:
 state['failure']=dict(case=case['id'] if 'case' in globals() else 'preflight',traceback=traceback.format_exc())
 print(state['failure']['traceback'],flush=True)
finally:
 sd.stop();state['elapsed_seconds']=time.monotonic()-started
 (out/'acquisition.json').write_text(json.dumps(state,indent=2)+'\n')
 print('CALIBRATION_ACQUISITION_FINISHED',len(state['cases']),'failure',bool(state['failure']),flush=True)
