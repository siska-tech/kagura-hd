"""Offline analysis of the provisionally approved queue-eight physical campaign."""
from pathlib import Path
import argparse,hashlib,json,re,statistics,subprocess,sys,wave
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'software/beyond16'
p=argparse.ArgumentParser();p.add_argument('--campaign-dir',type=Path,default=ROOT/'build/queue-demo-20261107/hardware')
p.add_argument('--evidence-dir',type=Path,default=ROOT/'docs/evidence/gpu-queue-demo');args=p.parse_args()
BASE=args.campaign_dir.resolve();OUT=args.evidence_dir.resolve()
assert BASE.is_relative_to(ROOT/'build') and OUT.is_relative_to(ROOT/'docs/evidence')
OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(R/'out/analysis-deps'),str(R.parent/'midnight_terminal/.deps')]
import numpy as np
from PIL import Image
campaign=json.loads((BASE/'campaign.json').read_text());assert campaign['success'],campaign.get('failure')
ff=Path((ROOT/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
fields=lambda s:{k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',s)}
def stats(v):
 s=sorted(v);return dict(samples=len(s),mean=statistics.mean(s),median=statistics.median(s),p95=s[min(len(s)-1,(len(s)*95+99)//100-1)],worst=max(s))
def delta(b,a):return (b-a)&0xffffffff
reports=[]
for item in campaign['variants']:
 name=item['name'];folder=BASE/name;ev=OUT/name;ev.mkdir(exist_ok=True)
 text=(folder/'demo-usb.log').read_text(errors='replace')
 result=json.loads((folder/'demo-result.json').read_text());assert result['success'] and not result['failure'] and result['capture_exit']==0
 frames=[fields(s) for s in text.splitlines() if s.startswith('FRAME ')]
 perfs=[fields(s) for s in text.splitlines() if s.startswith('PERF ')]
 assert len(frames)<4600 and all(p['timeouts']==p['audio_fault']==0 for p in perfs)
 assert set(f['scene'] for f in frames)==set(range(8))
 intervals=[delta(b['present_after_us'],a['present_after_us']) for a,b in zip(frames,frames[1:])]
 present=json.loads((folder/'present.json').read_text())
 first,last=perfs[0],perfs[-1];window=(last['ms']-first['ms'])/1000
 rep=dict(name=name,firmware_sha256=item['firmware_sha256'],frames=len(frames),actual_present_fps=len(intervals)*1e6/sum(intervals),
  present_intervals_us=stats(intervals),worst_call_us=max(f['us'] for f in frames),worst_call_frame=max(frames,key=lambda f:f['us']),scenes=present['scenes'],transitions=present['transitions'],
  timeouts=0,pcm_status_fault=0,stop_rc=0,selftest_readback_bytes=32,queue=item.get('queue'),
  transaction_window_s=window,transactions_per_second=(last['transactions']-first['transactions'])/window,
  wire_bytes_per_second=(last['wire_bytes']-first['wire_bytes'])/window,
  frame_deadline_misses=fields(next(s for s in text.splitlines() if s.startswith('WORK ')))['deadline_misses'],
  full_flash_after_tests_verified=item['full_flash_after_tests_verified'])
 if 'QRET' in item:
  rep['queue_retirement']=[dict(row,mean_poll_us=row['poll_us']/row['samples'] if row['samples'] else None,
   mean_metadata_us=row['metadata_us']/row['samples'] if row['samples'] else None,
   mean_ack_us=row['ack_us']/row['samples'] if row['samples'] else None) for row in item['QRET']]
  rep['sync_commands']=[dict(row,mean_drain_us=row['drain_us']/row['samples'] if row['samples'] else None,
   mean_command_us=row['command_us']/row['samples'] if row['samples'] else None) for row in item['QSYNC']]
  rep['finale_lettering_frames']=[f for f in frames if 143000<=f['ms']<143500]
  full=next(row for row in item['QRET'] if row['reason']==0)
  rep['ack_wait_observation']=dict(samples=full['samples'],
   known_completed_before_ack_issue_us_sample_sum=full['metadata_us'],
   mean_known_completed_before_ack_issue_us=full['metadata_us']/full['samples'] if full['samples'] else None,
   scope='reason=0 only: eight software tags outstanding, DONE confirmed, no other owner/ACK. At least one younger descriptor remains; current RTL inhibits dispatch until ACK. q_done to q_ack is a known held interval, not total DONE-to-ACK or measured FPGA cycles. Do not extrapolate periodic samples to full-run totals or interpret differences as exact hardware cycle savings.')
 if 'completion_burst' in item:
  rep['completion_burst']=item['completion_burst']
 wav=folder/'demo-audio.wav'
 if not wav.exists():subprocess.run([str(ff),'-nostdin','-v','error','-i',str(folder/'demo-hdmi.mkv'),'-vn','-c:a','pcm_s16le',str(wav)],check=True)
 with wave.open(str(wav)) as w:
  assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(48000,2,2)
  audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)
 left=audio[:,0].astype(float);rms=np.sqrt(np.mean(left[:len(left)//480*480].reshape(-1,480)**2,axis=1))
 active=np.flatnonzero(rms>150);assert len(active);onset=active[0]/100;end=(active[-1]+1)/100
 selected=(np.arange(len(rms))*.01>=onset+.02)&(np.arange(len(rms))*.01<end-.02)
 stereo_rms=np.sqrt(np.mean(audio[:len(audio)//480*480].astype(float).reshape(-1,480,2)**2,axis=1))
 low_by_channel=[int(np.sum(selected&(stereo_rms[:,ch]<20))) for ch in (0,1)]
 low=np.flatnonzero(selected&np.any(stereo_rms<20,axis=1));runs=[]
 for i in low:
  if runs and i==runs[-1][1]:runs[-1][1]=int(i+1)
  else:runs.append([int(i),int(i+1)])
 reference=np.frombuffer((R/'generated/bgm.s8').read_bytes(),dtype=np.int8).astype(float);N=len(reference);correlations=[]
 for scene,(t,gain) in enumerate(zip((0,10,30,50,70,95,120,140),(150,165,175,160,180,195,170,185))):
  y=left[int((onset+t+3)*48000):int((onset+t+3)*48000)+96000];assert len(y)==96000;y=y-y.mean();n=len(y)
  ref=np.floor(reference*gain*180/256);ref-=ref.mean();padded=np.zeros(N);padded[:n]=y
  corr=np.fft.irfft(np.fft.rfft(ref)*np.conj(np.fft.rfft(padded)),n=N)
  double=np.r_[ref,ref];s=np.r_[0,np.cumsum(double)];ss=np.r_[0,np.cumsum(double*double)];idx=np.arange(N)
  energy=ss[idx+n]-ss[idx]-(s[idx+n]-s[idx])**2/n
  normalized=corr/np.sqrt(np.maximum(energy,1)*np.dot(y,y));correlations.append(float(np.max(normalized)))
 rep['audio']=dict(sample_rate=48000,channels=2,onset_s=float(onset),audible_span_s=float(end-onset),
  low_10ms_blocks=len(low),low_10ms_blocks_by_channel=low_by_channel,longest_low_rms_ms=max(((b-a)*10 for a,b in runs),default=0),bgm_correlations=correlations,
  scope='Physical HDMI capture; RMS scan and eight quiet segments, not an independent underrun counter')
 rep['media']=json.loads(subprocess.check_output([str(ff.with_name('ffprobe.exe')),'-v','error','-show_entries','stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration','-of','json',folder/'demo-hdmi.mkv']))
 sheet=Image.new('RGB',(1280,1440))
 for i,t in enumerate((5,20,40,60,82.5,107.5,130,145)):
  image=ev/f'{i:02}.png'
  if not image.exists():subprocess.run([str(ff),'-nostdin','-v','error','-ss',str(onset+t),'-i',str(folder/'demo-hdmi.mkv'),'-frames:v','1',str(image)],check=True)
  sheet.paste(Image.open(image).resize((640,360)),((i%2)*640,(i//2)*360))
 sheet.save(ev/'contact-sheet.png')
 capture_log=(folder/'demo-capture.log').read_text(errors='replace')
 rep['capture_buffer_full_mentions']=capture_log.lower().count('buffer too full')
 for filename in ('demo-usb.log','demo-result.json','plan.json','flash-write-verified.json','present.json'):
  (ev/filename).write_bytes((folder/filename).read_bytes())
 rep['recording_sha256']=sha(folder/'demo-hdmi.mkv');reports.append(rep)
summary=dict(hardware_tested=True,release_ready=False,user_provisionally_approved=True,numeric_timing_gate_passed=False,
 bitstream_sha256=campaign['bitstream_sha256'],fpga_queue_depth=8,fpga_sram_programs=campaign['fpga_sram_programs'],fpga_flash_writes=0,
 conditions='Same depth-eight FPGA, 120 MHz RP2040, CPU+PIO, profile OFF, relative33 scheduler, seed 0xb1616, one 150s run each',
 host_queue_scope='Only FILL/PALETTE async; COPY/PRESENT/transfers/audio drain FIFO in order',variants=reports,
 limits=['Single fixed-order run per host; no randomized repeated/PVT qualification','Software pending peak is not a hardware occupancy counter',
 'No concurrent depth-one FPGA reference in this campaign','CPU-observed PRESENT completion; not scanout timestamp',
 '32-byte selftest readback is not full framebuffer verification','Physical PIO waveforms and all-sample audio integrity not measured'],
 original_backup=campaign['original_backup'],final_state=campaign['final_state'])
if campaign.get('experiment','').startswith('sampled'):
 summary['conditions']='Same approved depth-eight FPGA, queue host, 120 MHz RP2040, profile OFF, relative33, seed 0xb1616, 1/64 sampling; baseline glyphs versus merged glyphs, 150s each'
 summary['limits']+=['DONE polling duration includes host IO; hardware DONE-to-ACK hold time and GPU idle cycles are not measured',
  'Periodic sampling is not randomized; sampled means must not be interpreted as exact full-run totals']
if campaign.get('experiment')=='queue completion burst':
 summary['conditions']='Same approved depth-eight FPGA, queue host, merged lettering, 120 MHz RP2040, profile OFF, relative33, seed 0xb1616, 1/64 sampling; separate completion reads versus first queue-retirement snapshot, 150s each'
 summary['limits']+=['DONE-to-ACK hardware idle/hold cycles are not measured; all measured intervals include host IO',
  'Snapshot moves tag/error IO into the poll interval; compare poll plus metadata plus ACK, not metadata alone',
  'Periodic sampling is not randomized; sampled means are not exact full-run totals']
if campaign.get('run_order')==['baseline-1','burst-1','baseline-2','burst-2']:
 assert [r['name'] for r in reports]==campaign['run_order']
 summary['conditions']='Same frozen baseline/burst firmware and approved FPGA; A/B/A/B, four 150s runs; other conditions unchanged'
 summary['limits'][0]='Two runs per variant in fixed A/B/A/B order; no randomized order, confidence interval or PVT qualification'
 def metric(r,scene=None):
  return r['actual_present_fps'] if scene is None else next(s['actual_update_fps'] for s in r['scenes'] if s['scene']==scene)
 repeated={}
 for label,scene in (('overall',None),('vector_world',6)):
  av=[metric(reports[i],scene) for i in (0,2)];bv=[metric(reports[i],scene) for i in (1,3)]
  repeated[label]=dict(baseline_fps=av,burst_fps=bv,baseline_mean_fps=statistics.mean(av),burst_mean_fps=statistics.mean(bv),
   mean_gain_percent=(statistics.mean(bv)/statistics.mean(av)-1)*100,
   adjacent_pair_gain_percent=[(b/a-1)*100 for a,b in zip(av,bv)],
   improved_in_both_adjacent_pairs=all(b>a for a,b in zip(av,bv)),burst_min_above_baseline_max=min(bv)>max(av))
 summary['repeated_comparison']=repeated
 summary['run_order']=campaign['run_order']
(OUT/'comparison.json').write_text(json.dumps(summary,indent=2))
(OUT/'campaign.json').write_bytes((BASE/'campaign.json').read_bytes());(OUT/'source-sha256.json').write_bytes((BASE/'source-sha256.json').read_bytes())
print(json.dumps([dict(name=r['name'],fps=r['actual_present_fps'],p95_ms=r['present_intervals_us']['p95']/1000,
 worst_call_ms=r['worst_call_us']/1000,queue=r['queue'],audio=r['audio']) for r in reports],indent=2))
