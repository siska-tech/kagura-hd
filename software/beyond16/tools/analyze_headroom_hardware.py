"""Analyze completed matrix recordings. No device access or firmware changes."""
from pathlib import Path
import argparse,hashlib,json,re,statistics,subprocess,sys,wave

R=Path(__file__).resolve().parents[1];ROOT=R.parents[1]
p=argparse.ArgumentParser();p.add_argument('campaign',type=Path);p.add_argument('--media',action='store_true');args=p.parse_args()
base=args.campaign.resolve();E=R/'evidence/headroom-hardware';E.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'out/analysis-deps'));sys.path.insert(0,str(R.parent/'midnight_terminal/.deps'))
names=['IDLE','DRAW','NO_DRAW','USB','LOG','SCHEDULE','SLEEP','GEOMETRY','MASK','RECT','DESCRIPTOR','SUBMIT','DONE','PRESENT','BEGIN','DIRECTION','CS_SETUP','TX','RX','FIFO_WAIT','DEADLINE','WIRE','CS_HOLD','END','DMA_SETUP','DMA_WAIT','WORK','COOP_WORK']
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
def fields(line):return {k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)}
def delta(b,a):return (b-a)&0xffffffff
def stats(values):
    if not values:return None
    s=sorted(values)
    return dict(samples=len(s),mean=statistics.mean(s),median=statistics.median(s),p95=s[min(len(s)-1,(95*len(s)+99)//100-1)],worst=max(s),minimum=min(s))
campaign=json.loads((base/'campaign.json').read_text());reports=[]
for variant in campaign['variants']:
    name=variant['name'];folder=base/name
    complete=(folder/'demo-result.json').exists() and json.loads((folder/'demo-result.json').read_text())['success']
    if not complete:continue
    text=(folder/'demo-usb.log').read_text(errors='replace');frames=[];perfs=[];profiles=[];work=None
    for line in text.splitlines():
        if line.startswith('FRAME '):frames.append(fields(line))
        elif line.startswith('PERF '):perfs.append(fields(line))
        elif line.startswith('PROFILE '):profiles.append(fields(line))
        elif line.startswith('WORK '):work=fields(line)
    assert frames and 'STOP rc=0;' in text and work and work['valid']==1
    assert all(f['timeouts']==0 and f['audio_fault']==0 for f in perfs)
    assert all(f['overflow']==0 for f in profiles)
    assert len(frames)<4600
    present=json.loads((folder/'present.json').read_text())
    intervals=[delta(y['present_after_us'],x['present_after_us']) for x,y in zip(frames,frames[1:])]
    bench=[];phase=None
    for line in (folder/'bench-usb.log').read_text(errors='replace').splitlines():
        if line.startswith('BENCH_PHASE '):phase=line.split()[1]
        elif line.startswith('BENCH '):bench.append(dict(phase=phase,op=line.split()[1],**fields(line)))
    assert all(f.get('rc',0)==0 and f.get('gpu_error',0)==0 and f.get('timeouts',0)==0 for f in bench)
    grouped=[]
    for phase in ('PCM_STOPPED','PCM_PLAYING'):
        for op in ('raw_pointer_write','raw_csr_read','psram_write','psram_read','stages','fence','fill','blit','present'):
            lengths=sorted({b.get('n',0) for b in bench if b['phase']==phase and b['op']==op})
            for n in lengths:
                sample=[b for b in bench if b['phase']==phase and b['op']==op and b.get('n',0)==n]
                numeric=sorted(set.intersection(*(set(s) for s in sample))-{'phase','op','n','rc','transactions','pixels'})
                grouped.append(dict(phase=phase,op=op,n=n,**{key:stats([s[key] for s in sample]) for key in numeric}))
    total_us=sum(s['us'] for s in profiles)
    profile=[dict(region=names[s['region']],exclusive_us=s['us'],calls=s['calls'],wall_fraction=(s['us']/total_us if total_us else None)) for s in profiles]
    first,last=perfs[0],perfs[-1];tx=last['transactions']-first['transactions'];window=(last['ms']-first['ms'])/1000
    flash=json.loads((folder/'flash-write-verified.json').read_text())
    r=dict(name=name,firmware_sha256=flash['firmware_sha256'],release_ready=False,
           frames_logged=len(frames),scenes=present['scenes'],transitions=present['transitions'],
           actual_present_fps=len(intervals)*1e6/sum(intervals),present_intervals_us=stats(intervals),
           interval_over_33_333ms_rate=sum(v>100000/3 for v in intervals)/len(intervals),
           worst_call_us=max(f['us'] for f in frames),worst_call_frame=max(frames,key=lambda f:f['us']),call_budget_overruns=work['call_over_budget'],deadline_misses=work['deadline_misses'],
           timeout=0,pcm_status_fault=0,stop_rc=0,gpu_error='none observed (faults stop application)',
           busy_overwrite='no independent hardware counter; serialized SDK contract unchanged',
           transaction_mean_us=(last['transaction_us']-first['transaction_us'])/tx,
           host_measurement_window_s=window,bench=grouped,profile=profile,profile_total_wall_us=total_us,
           work={**work,'rounds_completed':work['batches']*work['rounds'],'arithmetic_operations':work['batches']*work['rounds']*8,
                 'operations_per_profile_window_second':work['batches']*work['rounds']*8*1e6/total_us if total_us else None},
           full_flash_after_tests_verified=variant.get('full_readback_unchanged',False),
           transport_data_validation='Frozen finite benchmark compares all-zero scratch data; changing-pattern physical DMA integrity is not independently established. PC fake tests use nonzero patterns.',
           physical_waveform_validation='NOT RUN; HDMI capture is not a PIO logic analyzer')
    out=E/name;out.mkdir(exist_ok=True)
    if args.media:
        import numpy as np
        from PIL import Image
        ff=Path((ROOT/'build/midnight-hardware/ffmpeg-path.txt').read_text(encoding='utf-8-sig').strip())
        wav=folder/'demo-audio.wav'
        if not wav.exists():
            subprocess.run([str(ff),'-nostdin','-v','error','-i',str(folder/'demo-hdmi.mkv'),'-vn','-c:a','pcm_s16le',str(wav)],check=True)
        with wave.open(str(wav)) as w:
            assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(48000,2,2)
            audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)
        left=audio[:,0].astype(np.float64);rms=np.sqrt(np.mean(left[:len(left)//480*480].reshape(-1,480)**2,axis=1))
        active=np.flatnonzero(rms>150);assert len(active)
        onset=float(active[0]/100);end=float((active[-1]+1)/100)
        selected=(np.arange(len(rms))*.01>=onset+.02)&(np.arange(len(rms))*.01<end-.02)
        low=np.flatnonzero(selected&(rms<20));runs=[]
        for i in low:
            if runs and i==runs[-1][1]:runs[-1][1]=int(i+1)
            else:runs.append([int(i),int(i+1)])
        r['audio']=dict(sample_rate=48000,channels=2,capture_seconds=len(audio)/48000,onset_s=onset,audible_span_s=end-onset,
                        low_rms_threshold=20,low_10ms_blocks=len(low),longest_low_rms_ms=max(((b-a)*10 for a,b in runs),default=0),
                        low_intervals_s=[[a/100,b/100] for a,b in runs],peak=int(np.max(np.abs(audio.astype(np.int32)))),
                        pcm_status_fault=0,independent_underrun_counter=False,scope='physical HDMI audio; silence scan does not prove every sample')
        reference=np.frombuffer((R/'generated/bgm.s8').read_bytes(),dtype=np.int8).astype(float)
        correlations=[];N=len(reference)
        for scene,(start_ms,gain) in enumerate(zip((0,10000,30000,50000,70000,95000,120000,140000),(150,165,175,160,180,195,170,185))):
            start=onset+start_ms/1000+3;segment=left[int(start*48000):int(start*48000)+96000]
            n=len(segment);assert n==96000
            ref=np.floor(reference*gain*180/256);ref-=ref.mean();y=segment-segment.mean()
            padded=np.zeros(N);padded[:n]=y
            corr=np.fft.irfft(np.fft.rfft(ref)*np.conj(np.fft.rfft(padded)),n=N)
            double=np.r_[ref,ref];s=np.r_[0,np.cumsum(double)];ss=np.r_[0,np.cumsum(double*double)];idx=np.arange(N)
            energy=ss[idx+n]-ss[idx]-(s[idx+n]-s[idx])**2/n
            normalized=corr/np.sqrt(np.maximum(energy,1)*np.dot(y,y));lag=int(np.argmax(normalized))
            correlations.append(dict(scene=scene,correlation=float(normalized[lag]),loop_offset_samples=lag))
        r['audio']['bgm_quiet_segment_correlations']=correlations
        probe=ff.with_name('ffprobe.exe')
        r['media']=json.loads(subprocess.check_output([str(probe),'-v','error','-show_entries','stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration','-of','json',str(folder/'demo-hdmi.mkv')]))
        capture_log=(folder/'demo-capture.log').read_text(errors='replace')
        progress=[line for line in re.split(r'[\r\n]+',capture_log) if line.startswith('frame=')]
        r['capture_health']=dict(final_progress=progress[-1] if progress else None,
            buffer_too_full_mentions=capture_log.lower().count('buffer too full'),
            caveat='Capture encoder statistics are not GPU PRESENT or source-frame drop counters')
        times=[5,20,40,60,82.5,107.5,130,145]
        for i,t in enumerate(times):
            image=out/f'{i:02}-hardware.png'
            if not image.exists():
                subprocess.run([str(ff),'-nostdin','-v','error','-ss',str(onset+t),'-i',str(folder/'demo-hdmi.mkv'),'-frames:v','1',str(image)],check=True)
        sheet=Image.new('RGB',(1280,1440))
        for i in range(8):sheet.paste(Image.open(out/f'{i:02}-hardware.png').resize((640,360)),((i%2)*640,(i//2)*360))
        sheet.save(out/'contact-sheet.png')
    elif (out/'result.json').exists():
        previous=json.loads((out/'result.json').read_text())
        for key in ('audio','media','capture_health'):
            if key in previous:r[key]=previous[key]
    (out/'result.json').write_text(json.dumps(r,indent=2))
    for filename in ('demo-usb.log','bench-usb.log','demo-result.json','bench-result.json','plan.json','flash-write-verified.json'):
        (out/filename).write_bytes((folder/filename).read_bytes())
    reports.append(r)
summary=dict(campaign_path=str(base.relative_to(ROOT)).replace('\\','/'),campaign_success=campaign.get('success',False),
             first_failure=campaign.get('failure'),variants=reports,release_ready=False,fpga_programming=0,fpga_flash_writes=0,
             replication='one finite run per variant; not randomized/repeated population statistics')
(E/'comparison.json').write_text(json.dumps(summary,indent=2))
lines=['# Eight-variant physical comparison','',f"Completed recordings: {len(reports)}/8. release_ready=false.",'',
       '|Variant|Actual PRESENT fps|p95 interval ms|Worst interval ms|Worst call ms|Deadline misses|',
       '|---|---:|---:|---:|---:|---:|']
for r in reports:
    s=r['present_intervals_us']
    lines.append(f"|{r['name']}|{r['actual_present_fps']:.3f}|{s['p95']/1000:.3f}|{s['worst']/1000:.3f}|{r['worst_call_us']/1000:.3f}|{r['deadline_misses']}|")
lines+=['','PRESENT completion is CPU-observed DONE/tag/error/ACK, not a scanout timestamp. Relative and absolute deadline definitions differ. No physical CPU-utilization percentage is inferred.',
        '', 'Firmware identity, PCM OFF/ON length benchmarks, exclusive elapsed regions, work checksum, scene and transition metrics: [comparison.json](evidence/headroom-hardware/comparison.json).',
        '', 'Full capture and new 2MiB backups stay in the campaign build directory. Existing backups and protected bitstream remain unchanged.']
(R/'HARDWARE_HEADROOM_RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps([dict(name=r['name'],fps=r['actual_present_fps'],worst_call_ms=r['worst_call_us']/1000,work=r['work']['rounds_completed']) for r in reports],indent=2))
