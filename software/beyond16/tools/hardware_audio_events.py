from pathlib import Path
import sys,json,wave
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'out/analysis-deps'));import numpy as np
out=R.parents[1]/'build/beyond16-hardware-2026-11-06';ev=R/'evidence/hardware';report=json.loads((ev/'audio.json').read_text())
with wave.open(str(out/'demo-audio.wav')) as w:y=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)[:,0].astype(float)
events=[];times=[0,10,30,50,70,95,120,140]
for scene,t in enumerate(times):
 fx=np.frombuffer((R/'generated'/f'fx{scene%4}.s8').read_bytes(),dtype=np.int8).astype(float);fx=np.floor(fx*90*180/256);fx-=fx.mean();start=max(0,int((report['audio_onset_s']+t-.1)*48000));seg=y[start:start+int(1.2*48000)];seg-=seg.mean();n=len(seg);m=len(fx);N=1<<(n+m-1).bit_length();corr=np.fft.irfft(np.fft.rfft(seg,N)*np.conj(np.fft.rfft(fx,N)),N)[:n-m+1];s=np.r_[0,np.cumsum(seg)];power=np.r_[0,np.cumsum(seg**2)];energy=power[m:]-power[:-m]-(s[m:]-s[:-m])**2/m;normalized=corr/np.sqrt(np.maximum(energy,1)*np.dot(fx,fx));best=int(np.argmax(normalized));events.append({'scene':scene,'fx':scene%4,'capture_time_s':(start+best)/48000,'correlation_without_BGM_subtraction':float(normalized[best]),'scope':'matched waveform in 1.2s around scene boundary; mixed with continuing BGM'})
report['pcm1_scene_stingers']=events
base=report['bgm_segment_correlations'][0]['loop_offset_samples'];drift=[]
for scene,r in enumerate(report['bgm_segment_correlations']):
 delta=(r['loop_offset_samples']-base-times[scene]*48000+192000)%384000-192000;drift.append({'scene':scene,'relative_phase_error_ms':delta/48})
report['relative_BGM_phase']=drift;report['phase_caveat']='single integer-lag correlation per scene, no physical clock/scope measurement'
(ev/'audio.json').write_text(json.dumps(report,indent=2));print(json.dumps({'stingers':events,'relative_phase':drift},indent=2))
