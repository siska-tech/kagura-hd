"""Fixed functional capture checks; no assertion of bit-transparent UGREEN I/O."""
import array,math,wave
from pathlib import Path

def video(path,expected,plan):
 raw=Path(path).read_bytes();assert len(raw)==1280*720*3
 measured=[]
 for x,y,rgb in expected['rois']:
  means=[sum(raw[(yy*1280+xx)*3+c] for yy in range(y*2-3,y*2+5) for xx in range(x*2-3,x*2+5))/64 for c in range(3)]
  delta=max(abs(means[c]-rgb[c]) for c in range(3))
  measured.append({'point':[x,y],'expected':rgb,'mean':means,'max_error':delta})
  assert delta<=plan['rgb_component_tolerance'],measured[-1]
 def match(points,tolerance):
  hits=0
  for x,y,rgb in points:
   best=min(max(abs(raw[(yy*1280+xx)*3+c]-rgb[c]) for c in range(3))
    for yy in range(max(0,y*2-1),min(720,y*2+4)) for xx in range(max(0,x*2-1),min(1280,x*2+4)))
   hits+=best<=tolerance
  return hits/max(1,len(points))
 points=expected.get('foreground_points',[]);fraction=match(points,60)
 if points:assert fraction>=0.95,('foreground pixel probe mismatch',fraction)
 cursor=expected['cursor_points'];cursor_fraction=match(cursor,plan['cursor_color_tolerance'])
 if cursor:assert cursor_fraction>=plan['cursor_match_minimum'],('cursor mismatch',cursor_fraction)
 return {'rois':measured,'foreground_points':len(points),'foreground_match':fraction,'cursor_points':len(cursor),
         'cursor_match':cursor_fraction if cursor else None,'scope':'fixed RGB ROI/sparse pixel checks, not full HDMI bit equality'}

def audio(path,mode,plan,tone_hex):
 with wave.open(str(path),'rb') as w:
  assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(2,2,48000)
  count=w.getnframes();raw=array.array('h',w.readframes(count))
 assert count>=120000,('too few capture samples',count)
 # Analyze one central second to avoid source/capture startup and shutdown.
 start=(count-48000)//2
 channels=[raw[(start*2+c):((start+48000)*2+c):2] for c in (0,1)]
 rms=[math.sqrt(sum(v*v for v in a)/len(a)) for a in channels]
 result={'frames':count,'central_frames':48000,'rms':rms,'mode':mode}
 if mode==0:
  assert max(rms)<=plan['audio']['silence_rms_max'],result
  return result
 def amplitude(samples,freq):
  step=complex(math.cos(2*math.pi*freq/48000),-math.sin(2*math.pi*freq/48000));z=1+0j;total=0j
  for v in samples:total+=v*z;z*=step
  return 2*abs(total)/len(samples)
 def search(samples,frequency):
  span=plan['audio']['frequency_search_hz'];step=plan['audio']['search_step_hz']
  candidates=[frequency-span+i*step for i in range(int(2*span/step)+1)]
  return max(((amplitude(samples,f),f) for f in candidates))
 target=mode-1 if mode in (1,2) else None
 if target is not None:
  signal,quiet=rms[target],rms[1-target]
  tone=bytes.fromhex(tone_hex[target]);signed=[v if v<128 else v-256 for v in tone]
  expected=math.sqrt(sum((v*100)**2 for v in signed)/len(signed))
  amp,f=search(channels[target],(1000,1500)[target])
  result.update(expected_rms=expected,amplitude=amp,frequency_hz=f,quiet_rms=quiet)
  assert abs(signal/expected-1)<=plan['audio']['amplitude_relative_tolerance'],result
  assert quiet<=max(plan['audio']['muted_rms_max_floor'],signal*plan['audio']['muted_rms_relative_max']),result
  assert abs(f-(1000,1500)[target])<=plan['audio']['frequency_search_hz'],result
  assert amp*amp/2/(signal*signal)>=plan['audio']['explained_energy_minimum'],result
 else:
  a0,f0=search(channels[0],1000);a1,f1=search(channels[1],1500)
  b0=amplitude(channels[1],f0);b1=amplitude(channels[0],f1)
  result.update(frequencies=[f0,f1],amplitudes=[[a0,b1],[b0,a1]],pan_ratios=[a0/max(b0,1e-9),a1/max(b1,1e-9)])
  assert all(abs(v/5-1)<=plan['audio']['pan_ratio_relative_tolerance'] for v in result['pan_ratios']),result
  assert all(x>1000 for x in rms),result
  explained=[(a0*a0+b1*b1)/2/(rms[0]*rms[0]),(a1*a1+b0*b0)/2/(rms[1]*rms[1])]
  result['explained_energy']=explained
  assert min(explained)>=plan['audio']['explained_energy_minimum'],result
 return result

def bgm(path,reference,plan):
 import numpy as np
 def read(p):
  with wave.open(str(p),'rb') as w:
   assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(2,2,48000)
   return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).astype(float)
 captured=read(path);ref=read(reference)
 assert len(captured)>=48000
 start=(len(captured)-48000)//2;window=captured[start:start+48000]
 c=window.mean(axis=1).reshape(-1,4).mean(axis=1);c-=c.mean()
 source=ref.mean(axis=1).reshape(-1,4).mean(axis=1)
 source=np.tile(source,2);source-=source.mean()
 n=len(c);size=1
 while size<len(source)+n:size*=2
 cf=np.fft.rfft(c[::-1],size);energy=float(c@c);rows=[];best=None
 for ppm in range(-1000,1001,100):
  rate=1+ppm/1000000
  z=np.interp(np.arange(96000+n)*rate,np.arange(len(source)),source)
  corr=np.fft.irfft(np.fft.rfft(z,size)*cf,size)[n-1:n-1+96000]
  squares=np.concatenate(([0.],np.cumsum(z*z)))
  denom=np.sqrt(np.maximum(1e-30,(squares[n:n+96000]-squares[:96000])*energy))
  normalized=corr/denom;offset=int(np.argmax(normalized));score=float(normalized[offset])
  rows.append({'ppm':ppm,'offset_ds':offset,'correlation':score})
  if best is None or score>best[0]:best=(score,offset,rate,ppm)
 score,offset,rate,ppm=best
 indices=(offset*4+np.arange(48000)*rate)%(len(ref))
 aligned=np.column_stack([np.interp(indices,np.arange(len(ref)),ref[:,side]) for side in (0,1)])
 metrics=[]
 for side in (0,1):
  a=window[:,side]-window[:,side].mean();b=aligned[:,side]-aligned[:,side].mean()
  metrics.append({'correlation':float(a@b/np.sqrt((a@a)*(b@b))),
    'gain':float((a@b)/(b@b)),'rms':float(np.sqrt(np.mean(a*a)))})
 result={'scope':'functional reference correlation, not bit equality or physical clock measurement',
   'best_mono_correlation':score,'estimated_alignment_ppm':ppm,'reference_offset_samples':offset*4,
   'channels':metrics,'search_results':rows}
 assert score>=plan['audio']['bgm_mono_correlation_minimum'],result
 assert all(m['correlation']>=plan['audio']['bgm_channel_correlation_minimum'] and abs(m['gain']-1)<=.25 for m in metrics),result
 return result
