"""Analyze recorded physical evidence; no live hardware access."""
from pathlib import Path
import sys,json,re,statistics,subprocess,shutil,wave,hashlib
R=Path(__file__).resolve().parents[1];repo=R.parents[1];out=repo/'build/beyond16-hardware-2026-11-06';ev=R/'evidence/hardware';sys.path.insert(0,str(R/'out/analysis-deps'));sys.path.insert(0,str(R.parent/'midnight_terminal/.deps'))
import numpy as np
from PIL import Image
from preview import SCENES
state=json.loads((out/'demo-result.json').read_text());assert state['success'] and not state['failure'];text=(out/'demo-usb.log').read_text();frames=[]
for line in text.splitlines():
 if line.startswith('FRAME '):frames.append({k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)})
perfs=state['perf'];first,last=perfs[0],perfs[-1];dt=(last['ms']-first['ms'])/1000;delta={k:last[k]-first[k] for k in ('transactions','wire_bytes','transaction_us','frames','skipped')};frame_by_time={f['ms']:f for f in frames}
epoch=statistics.median(p['capture_elapsed_s']-p['ms']/1000-frame_by_time[p['ms']]['us']/1e6 for p in perfs if p['ms'] in frame_by_time)
scenes=[]
for scene,(name,a,b) in enumerate(SCENES):
 fs=[f for f in frames if f['scene']==scene];assert fs,name;ts=[f['us']/1000 for f in fs];sp=[p for p in perfs if p['scene']==scene];rates=None
 if len(sp)>=2:
  t=(sp[-1]['ms']-sp[0]['ms'])/1000;rates={'measured_seconds':t,'transactions_per_s':(sp[-1]['transactions']-sp[0]['transactions'])/t,'wire_bytes_per_s':(sp[-1]['wire_bytes']-sp[0]['wire_bytes'])/t}
 # command deltas at frame boundaries (previous counter includes earlier frame)
 lo=frames.index(fs[0]);previous=frames[lo-1] if lo else {'commands':0,'blit_pixels':0}
 scenes.append({'scene':scene,'name':name,'nominal_seconds':(b-a)/1000,'logged_frames':len(fs),'effective_fps':len(fs)/((b-a)/1000),'mean_frame_ms':statistics.mean(ts),'worst_frame_ms':max(ts),'drawing_commands':fs[-1]['commands']-previous['commands'],'blit_pixels':fs[-1]['blit_pixels']-previous['blit_pixels'],'first_host_ms':fs[0]['ms'],'last_host_ms':fs[-1]['ms'],'rates':rates})
bench=[];phase=None
for line in (out/'bench-usb.log').read_text().splitlines():
 if line.startswith('BENCH_PHASE '):phase=line.split()[1]
 elif line.startswith('BENCH '):
  row={k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)};row.update({'phase':phase,'op':line.split()[1]});assert row['rc']==0;bench.append(row)
summary=[]
for phase in ('PCM_STOPPED','PCM_PLAYING'):
 for op in ('fence','fill','blit','present'):
  rows=[r for r in bench if r['phase']==phase and r['op']==op];fields=('issue_us','completion_us') if op=='fence' else ('us',)
  summary.append({'phase':phase,'op':op,'samples':len(rows),**{f:{'mean':statistics.mean(r[f] for r in rows),'min':min(r[f] for r in rows),'max':max(r[f] for r in rows)} for f in fields}})
ff=shutil.which('ffmpeg');probe=shutil.which('ffprobe')
def run(args):subprocess.run([str(x) for x in args],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
run([ff,'-y','-i',out/'demo-hdmi.mkv','-vn','-acodec','pcm_s16le',out/'demo-audio.wav'])
with wave.open(str(out/'demo-audio.wav')) as w:
 assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(48000,2,2);audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).astype(np.float64)
# Locate the first BGM attack in 10ms RMS windows; capture before playback is silent.
blocks=audio[:len(audio)//480*480,0].reshape(-1,480);rms=np.sqrt(np.mean(blocks**2,axis=1));active=np.flatnonzero(rms>150);onset=float(active[0]*.01);endpoint=float(active[-1]*.01+.01)
reference=np.frombuffer((R/'generated/bgm.s8').read_bytes(),dtype=np.int8).astype(float);N=len(reference)
# Matched phase/gain on a quiet 2s BGM segment in every scene, excluding stinger.
gains=[150,165,175,160,180,195,170,185];correlations=[]
for scene,(_,a,b) in enumerate(SCENES):
 start=onset+a/1000+3;segment=audio[int(start*48000):int((start+2)*48000),0];n=len(segment);ref=np.floor(reference*gains[scene]*180/256);ref-=ref.mean();y=segment-segment.mean();pad=np.zeros(N);pad[:n]=y
 corr=np.fft.irfft(np.fft.rfft(ref)*np.conj(np.fft.rfft(pad)),n=N);double=np.r_[ref,ref];s=np.r_[0,np.cumsum(double)];ss=np.r_[0,np.cumsum(double*double)];idx=np.arange(N);power=ss[idx+n]-ss[idx]-(s[idx+n]-s[idx])**2/n;norm=corr/np.sqrt(np.maximum(power,1)*np.dot(y,y));lag=int(np.argmax(norm));matched=double[lag:lag+n];gain=float(np.dot(matched,y)/np.dot(matched,matched));correlations.append({'scene':scene,'capture_start_s':start,'samples':n,'correlation':float(norm[lag]),'loop_offset_samples':lag,'gain_relative_to_reference':gain,'capture_rms':float(np.sqrt(np.mean(segment**2)))})
# Silence/dropout scan after detected onset and before clean STOP. Low RMS intervals
# are observations, not a FIFO underrun counter. PCM STATUS is the separate evidence.
mask=(np.arange(len(rms))*.01>=onset+.02)&(np.arange(len(rms))*.01<endpoint-.02);low=np.flatnonzero(mask&(rms<20));runs=[]
for i in low:
 if runs and i==runs[-1][1]:runs[-1][1]=int(i+1)
 else:runs.append([int(i),int(i+1)])
audio_report={'scope':'physical UGREEN HDMI PCM16 stereo capture, not PC mix','sample_rate':48000,'channels':2,'capture_seconds':len(audio)/48000,'audio_onset_s':onset,'audio_end_s':endpoint,'audible_span_s':endpoint-onset,'whole_capture_rms':np.sqrt(np.mean(audio**2,axis=0)).tolist(),'peak':np.max(np.abs(audio),axis=0).tolist(),'left_right_max_abs_difference':float(np.max(np.abs(audio[:,0]-audio[:,1]))),'longest_observed_low_rms_ms':max(((b-a)*10 for a,b in runs),default=0),'low_rms_scan_threshold':20,'low_rms_intervals':[[a/100,b/100] for a,b in runs],'bgm_segment_correlations':correlations,'pcm_status_faults':sorted(set(p['audio_fault'] for p in perfs)),'underrun_counter_available':False,'caveat':'STATUS fault observed at 1s cadence; no isolated underrun counter. Capture silence scan does not prove every sample.'}
# Capture offset uses measured audio onset. Each PNG is actual 1280x720 HDMI input.
for i,(name,a,b) in enumerate(SCENES):
 t=onset+(a+b)/2000
 run([ff,'-y','-ss',t,'-i',out/'demo-hdmi.mkv','-frames:v','1',ev/f'{i:02}-hardware.png'])
contact=Image.new('RGB',(1280,1440))
for i in range(8):contact.paste(Image.open(ev/f'{i:02}-hardware.png').resize((640,360)),((i%2)*640,(i//2)*360))
contact.save(ev/'contact-sheet.png')
media=json.loads(subprocess.check_output([probe,'-v','error','-show_entries','stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration','-of','json',str(out/'demo-hdmi.mkv')]))
report={'release_ready':False,'scope':'one finite optimized firmware physical run; logging on; seed0xb1616; stars64 objects32; nominal QSPI5MHz','success':True,'scenes_complete':len(scenes)==8,'stop_rc':0,'g_to_stop_s':state['stop_elapsed_s'],'estimated_audio_epoch_from_g_s':epoch,'runtime_rate_window':{'first_ms':first['ms'],'last_ms':last['ms'],'seconds':dt,'transactions_per_s':delta['transactions']/dt,'wire_bytes_per_s':delta['wire_bytes']/dt,'transaction_us_per_second':delta['transaction_us']/dt,'cumulative_transaction_us':delta['transaction_us'],'transaction_average_us':delta['transaction_us']/delta['transactions'],'actual_fps':delta['frames']/dt},'frames_logged_excluding_initial_frame':len(frames),'mean_frame_ms':statistics.mean(f['us']/1000 for f in frames),'worst_frame_ms':max(f['us']/1000 for f in frames),'drawing_commands_final_counter':frames[-1]['commands'],'blit_pixels_final_counter':frames[-1]['blit_pixels'],'timeouts':last['timeouts'],'maximum_transaction_us':last['max_transaction_us'],'pcm_status_faults':sorted(set(p['audio_fault'] for p in perfs)),'scenes':scenes,'bench':summary,'physical_before_after':'NOT RUN: only optimized firmware deployed','PIO_GPIO_GPU_PSRAM_internal_split':'not separately measured','media':media}
(ev/'performance.json').write_text(json.dumps(report,indent=2));(ev/'audio.json').write_text(json.dumps(audio_report,indent=2));(ev/'bench-raw.json').write_text(json.dumps(bench,indent=2))
for name in ['backup-verified.json','deployment-plan.json','flash-write-verified.json','bench-result.json','demo-result.json','stop-previous.log','demo-usb.log','bench-usb.log']:(ev/name).write_bytes((out/name).read_bytes())
print(json.dumps({'success':True,'rates':report['runtime_rate_window'],'scenes':[(s['name'],s['effective_fps'],s['mean_frame_ms'],s['worst_frame_ms']) for s in scenes],'audio':{'onset_s':onset,'span_s':endpoint-onset,'longest_low_ms':audio_report['longest_observed_low_rms_ms'],'correlations':[r['correlation'] for r in correlations]}},indent=2))
