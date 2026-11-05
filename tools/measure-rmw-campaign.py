"""Independent RGB/PCM acceptance; no third-party packages or hardware writes."""
from pathlib import Path
import array,json,math,sys,wave

def video(path,rois):
 data=Path(path).read_bytes();assert len(data)==1280*720*3,'wrong RGB24 dimensions'
 results=[]
 for x,y,color in rois:
  sums=[0,0,0];count=0
  for yy in range(y*2-3,y*2+5):
   for xx in range(x*2-3,x*2+5):
    i=(yy*1280+xx)*3
    for c in range(3):sums[c]+=data[i+c]
    count+=1
  mean=[v/count for v in sums];delta=[abs(mean[c]-color[c]) for c in range(3)]
  results.append(dict(point=[x,y],expected=color,actual_mean=mean,max_error=max(delta)))
  assert max(delta)<=50,results[-1]
 return results

def audio(path,case):
 with wave.open(str(path),'rb') as f:
  assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(2,2,48000)
  frames=f.getnframes();assert 140000<=frames<=148000,frames
  a=array.array('h',f.readframes(frames))
 left=a[0::2];right=a[1::2];longest=run=0;energies=[]
 for l,r in zip(left,right):
  run=run+1 if l==0 and r==0 else 0;longest=max(longest,run)
 for off in range(4800,frames-4800,4800):
  rms=math.sqrt(sum(x*x+y*y for x,y in zip(left[off:off+4800],right[off:off+4800]))/9600)
  energies.append(rms)
 assert longest<480 and energies and min(energies)>1,(longest,energies)
 result=dict(frames=frames,longest_zero_frames=longest,min_rms=min(energies))
 if case['id']!='A0':
  difference=[l-r for l,r in zip(left,right)][4800:-4800];period=case['period'];sign=case['sign']
  best=max(sum(abs(value-sign*(16 if (i+phase)%period<period//2 else -16))<=2 for i,value in enumerate(difference))/len(difference) for phase in range(period))
  result['pcm_independent_sample_match_fraction']=best
  assert best>=.99,result
 else:
  result['stereo_equal_fraction']=sum(abs(l-r)<=2 for l,r in zip(left,right))/frames
  assert result['stereo_equal_fraction']>=.99,result
 return result

def selftest():
 from contextlib import nullcontext
 d=Path(__file__).resolve().parents[1]/'build/rmw-campaign-2026-11-05-v1/measurement-selfcheck'
 d.mkdir(exist_ok=True)
 with nullcontext(d):
  p=Path(d)/'rgb';p.write_bytes(bytes((255,0,0))*(1280*720))
  video(p,[(100,100,(255,0,0))])
  try:video(p,[(100,100,(0,255,0))])
  except AssertionError:pass
  else:raise AssertionError('negative video oracle did not reject')
  for mode in ('A0','A1','A2'):
   case=dict(id=mode,period=16 if mode=='A1' else 32,sign=1 if mode=='A1' else -1)
   samples=array.array('h')
   for i in range(144000):
    expected=case['sign']*(16 if i%case['period']<case['period']//2 else -16) if mode!='A0' else 0
    samples.extend((100+expected,100))
   w=Path(d)/(mode+'.wav')
   with wave.open(str(w),'wb') as f:f.setparams((2,2,48000,0,'NONE','NONE'));f.writeframes(samples.tobytes())
   audio(w,case)
  w=Path(d)/'silent.wav'
  with wave.open(str(w),'wb') as f:f.setparams((2,2,48000,0,'NONE','NONE'));f.writeframes(bytes(144000*4))
  try:audio(w,dict(id='A0'))
  except AssertionError:pass
  else:raise AssertionError('negative silent audio did not reject')
 print('PASS: independent RGB and PCM positive/negative measurement self-check')

if __name__=='__main__':selftest()
