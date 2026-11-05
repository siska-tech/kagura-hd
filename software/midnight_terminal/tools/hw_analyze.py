"""Analyze recorded native USB counters and physical HDMI PCM, no hardware IO."""
from pathlib import Path
import numpy as np,json,re,wave
repo=Path(__file__).resolve().parents[3];app=repo/'software/midnight_terminal';out=repo/'build/midnight-hardware';evidence=app/'evidence/hardware'
run=json.loads((out/'run-result.json').read_text());text=(out/'native-usb.log').read_text();samples=[]
for line in text.splitlines():
 if line.startswith('host_ms='):samples.append({k:int(v) for k,v in re.findall(r'(host_ms|frames|bytes|commands|waits_ms|audio_fault)=(-?\d+)',line)})
rates=[]
for a,b in zip(samples,samples[1:]):
 dt=b['host_ms']-a['host_ms'];rates.append({'from_ms':a['host_ms'],'to_ms':b['host_ms'],'scheduler_hz':(b['frames']-a['frames'])*1000/dt,'adapter_command_rate':(b['commands']-a['commands'])*1000/dt})
with wave.open(str(out/'hdmi-audio.wav')) as w:
 assert (w.getframerate(),w.getsampwidth(),w.getnchannels())==(48000,2,2)
 audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).astype(np.float64)
reference=np.frombuffer((app/'generated/bgm.s8').read_bytes(),dtype=np.int8).astype(np.float64);reference=np.floor(reference*155*180/256)
# A two-second dialogue interval after the typewriter effects have finished.
segment=audio[44*48000:46*48000];correlations=[]
for ch in range(2):
 best=None
 for ppm in range(-1000,1001,100):
  positions=np.arange(int(len(segment)/(1+ppm/1e6)))*(1+ppm/1e6)
  actual=np.interp(positions,np.arange(len(segment)),segment[:,ch]);n=len(actual);N=len(reference)
  ac=actual-actual.mean();pad=np.zeros(N);pad[:n]=ac
  corr=np.fft.irfft(np.fft.rfft(reference)*np.conj(np.fft.rfft(pad)),n=N)
  double=np.r_[reference,reference];s=np.r_[0,np.cumsum(double)];ss=np.r_[0,np.cumsum(double*double)];idx=np.arange(N);sums=s[idx+n]-s[idx];power=ss[idx+n]-ss[idx]-sums*sums/n
  normalized=corr/np.sqrt(np.maximum(power,1)*np.sum(ac*ac));lag=int(np.argmax(normalized));score=float(normalized[lag])
  if best is None or score>best['correlation']:
   ref=double[lag:lag+n];ref=ref-ref.mean();gain=float(np.dot(ref,ac)/np.dot(ref,ref));best={'correlation':score,'ppm_grid':ppm,'reference_offset_sample':lag,'gain_relative_to_digital_reference':gain}
 correlations.append(best)
def stats(a):return {'rms':[float(x) for x in np.sqrt(np.mean(a*a,axis=0))],'peak':[float(x) for x in np.max(np.abs(a),axis=0)]}
report={'scope':'physical UGREEN HDMI capture + native C USB log','release_ready':False,'full_loop':run['complete_loop'],'g_to_first_frame_seconds':run['scenes'][0]['pc_elapsed_seconds'],'g_to_second_boot_seconds':run['wall_seconds_after_g'],'scenes':run['scenes'],'pcm_format':'48000Hz signed16 stereo','whole_capture_audio':stats(audio),'dialogue_44_46s':stats(segment),'bgm_reference_match':correlations,'scheduler_intervals':rates,'scheduler_caveat':'frames counts eligible C engine ticks; not a direct PRESENT or HDMI refresh counter','last_scheduler_sample':samples[-1],'pcm_faults_observed':sorted(set(s['audio_fault'] for s in samples)),'raw_transport_last':next(l for l in reversed(text.splitlines()) if l.startswith('qspi_')),'all_branches_on_hardware':'not tested; autoplay selected terminal only','physical_sck_scope_measurement':'not performed; nominal 5MHz config'}
# Check the one-shot select sound while PCM0 continues, with fitted BGM removed.
y=audio[60*48000:63*48000,0];N=len(reference);n=len(y);pad=np.zeros(N);pad[:n]=y-y.mean()
corr=np.fft.irfft(np.fft.rfft(reference)*np.conj(np.fft.rfft(pad)),n=N)
double=np.r_[reference,reference];s=np.r_[0,np.cumsum(double)];ss=np.r_[0,np.cumsum(double*double)];idx=np.arange(N);power=ss[idx+n]-ss[idx]-(s[idx+n]-s[idx])**2/n
lag=int(np.argmax(corr/np.sqrt(np.maximum(power,1))));ref=double[lag:lag+n];ref=ref-ref.mean();residual=y-y.mean()-ref*np.dot(ref,y-y.mean())/np.dot(ref,ref)
effect=np.floor(np.frombuffer((app/'generated/select.s8').read_bytes(),dtype=np.int8).astype(float)*170*180/256);effect-=effect.mean();m=len(effect);size=1<<(n+m-1).bit_length()
c=np.fft.irfft(np.fft.rfft(residual,size)*np.conj(np.fft.rfft(effect,size)),size)[:n-m+1];ener=np.r_[0,np.cumsum(residual*residual)];den=np.sqrt(np.maximum(ener[m:]-ener[:-m],1)*np.dot(effect,effect));normalized=c/den;k=int(np.argmax(normalized))
report['pcm1_select_while_bgm']={'capture_start_seconds':60+k/48000,'correlation_after_bgm_removal':float(normalized[k]),'gain_relative_to_digital_reference':float(c[k]/np.dot(effect,effect)),'scope':'one short selection effect only, not every PCM1 effect'}
(evidence/'analysis.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('scheduler_intervals','scenes')},indent=2))
