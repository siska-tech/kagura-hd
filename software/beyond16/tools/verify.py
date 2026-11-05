"""Final offline consistency audit. Never opens a device or programmer."""
from pathlib import Path
import hashlib,json,subprocess,shutil,wave
R=Path(__file__).resolve().parents[1];repo=R.parents[1];E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads((E/'source-sha256.json').read_text(encoding='utf-8'));assert all(sha(repo/p)==h for p,h in source.items()),'Frozen source changed'
build=json.loads((E/'rp2040-build.json').read_text(encoding='utf-8'));assert sha(R/'out/rp2040/beyond16.bin')==build['bin_sha256'];assert sha(R/'out/rp2040/beyond16.elf')==build['elf_sha256']
assert int(build['sector_end_exclusive'],16)<=0x100a0000
before=json.loads((E/'before-after.json').read_text());a=json.loads((E/'pc-baseline.json').read_text());b=json.loads((E/'pc-optimized.json').read_text());assert before['baseline']==a['runtime_counts'];assert before['optimized']==b['runtime_counts'];assert a['frame_crc32']==b['frame_crc32'];assert b['runtime_counts'][5:]==[0,0,0]
assert sum(s['logical_seconds'] for s in b['scenes'])==150
oracle=json.loads((E/'oracle.json').read_text());assert all(x['timestamps']==20 and x['pixel_oracle']=='PASS' for x in oracle)
trace=[bytes.fromhex(json.loads(s)['descriptor']) for s in (E/'oracle-command-trace.jsonl').read_text().splitlines()];assert len(trace)==oracle[-1]['commands'];assert all(len(c)==16 and c[0]<8 for c in trace)
with wave.open(str(R/'out/beyond16-pc.wav')) as w:assert (w.getnframes(),w.getframerate(),w.getnchannels(),w.getsampwidth())==(7200000,48000,2,2)
probe=shutil.which('ffprobe');assert probe
p=subprocess.run([probe,'-v','error','-show_entries','stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration','-of','json',str(R/'out/beyond16-pc.mp4')],capture_output=True,check=True);media=json.loads(p.stdout);video=next(s for s in media['streams'] if s['codec_type']=='video');audio=next(s for s in media['streams'] if s['codec_type']=='audio');assert (video['width'],video['height'],video['r_frame_rate'])==(640,360,'30/1');assert (audio['sample_rate'],audio['channels'])==('48000',2);assert abs(float(media['format']['duration'])-150)<.05
(E/'video-probe.json').write_text(json.dumps(media,indent=2))
artifacts=[R/'out/rp2040/beyond16.bin',R/'out/rp2040/beyond16.elf',R/'out/beyond16-pc.mp4',R/'out/beyond16-pc.wav',E/'contact-sheet.png']
report={'status':'PASS','scope':'offline artifact consistency; no physical hardware IO','frozen_source_files':len(source),'oracle_timestamps_per_variant':20,'oracle_variants':2,'traced_descriptors':len(trace),'PC_runtime_upload_bytes':0,'firmware_bytes':build['bin_bytes'],'filesystem_bounds':'PASS','video_seconds':float(media['format']['duration']),'hardware':'separate physical finite run recorded' if (E/'hardware/performance.json').exists() else 'NOT RUN','release_ready':False,'artifacts':{str(p.relative_to(R)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in artifacts}}
(E/'final-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
