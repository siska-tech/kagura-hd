"""Collect memory bounds, frozen inputs and comparison tables; read-only toward devices."""
from pathlib import Path
import json,hashlib,struct,re,subprocess,sys,platform
R=Path(__file__).resolve().parents[1];repo=R.parents[1];E=R/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
bit=repo/'artifacts/validated/kagura-hd-qspi-pcm2.fs';expected='642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7';assert sha(bit)==expected
original=repo/'build/midnight-hardware/recovery/current-flash-2MiB.bin';last=repo/'build/midnight-hardware/recovery/after-native-flash.bin';assert sha(original)=='7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6';assert sha(last)=='7ea52cb9898e6dbd3b44eb1b80861b28a3fd8026d858973162e05f5df32ee596'
old=json.loads((R.parent/'midnight_terminal/evidence/protected-inputs.json').read_text());frozen={k:v for k,v in old.items() if k.startswith(('rtl/','boards/','build/pcm2-timing-04/'))};changes=[k for k,v in frozen.items() if not (repo/k).exists() or sha(repo/k)!=v];assert not changes,changes
write(E/'protection.json',{'release_ready':False,'bitstream':str(bit.relative_to(repo)),'bitstream_sha256':expected,'previous_freeze_files_verified':len(frozen),'freeze_mismatches':changes,'original_backup':{'path':str(original.relative_to(repo)),'sha256':sha(original),'bytes':original.stat().st_size},'last_native_flash_snapshot':{'path':str(last.relative_to(repo)),'sha256':sha(last),'bytes':last.stat().st_size},'current_device_flash_read':False,'hardware_opened':False,'rtl_changes_this_task':0})
data=(R/'out/rp2040/beyond16.elf').read_bytes();assert data[:6]==b'\x7fELF\x01\x01';shoff=struct.unpack_from('<I',data,32)[0];entry,count,strings=struct.unpack_from('<HHH',data,46);secs=[struct.unpack_from('<10I',data,shoff+i*entry) for i in range(count)];s=secs[strings];names=data[s[4]:s[4]+s[5]]
def string(tab,offset):return tab[offset:tab.index(0,offset)].decode()
alloc=[];symbols={}
for sec in secs:
 if sec[2]&2:alloc.append({'name':string(names,sec[0]),'address':hex(sec[3]),'bytes':sec[5],'type':sec[1]})
 if sec[1]==2:
  st=secs[sec[6]];tab=data[st[4]:st[4]+st[5]]
  for pos in range(sec[4],sec[4]+sec[5],sec[9]):
   n,val,size,info,other,index=struct.unpack_from('<IIIBBH',data,pos);name=string(tab,n)
   if name in ['__StackTop','__StackBottom','__flash_binary_end','frame_lz','song_lz','history','engine','gpu']:symbols[name]={'address':hex(val),'bytes':size}
binary=R/'out/rp2040/beyond16.bin';n=binary.stat().st_size;sector_end=(n+4095)//4096*4096;assert sector_end<=0xa0000;assert int(symbols['__flash_binary_end']['address'],16)<=0x100a0000;assert int(symbols['__StackTop']['address'],16)-int(symbols['__StackBottom']['address'],16)==8192
sizes=re.findall(r'(?m)^\s*(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+[0-9a-f]+\s+',(E/'rp2040-build.log').read_text())[-1]
write(E/'rp2040-build.json',{'target':'RP2040/Pico Cortex-M0+','compiler':'Arm GNU GCC 14.2.1','sdk_commit':'bddd20f928ce76142793bef434d4f75f4af6e433','text':int(sizes[0]),'data':int(sizes[1]),'bss':int(sizes[2]),'stack_reserved':8192,'sections':alloc,'symbols':symbols,'bin_bytes':n,'sector_end_exclusive':hex(0x10000000+sector_end),'filesystem_start':hex(0x100a0000),'filesystem_capacity_check':'PASS (offline bounds only)','bin_sha256':sha(binary),'elf_sha256':sha(R/'out/rp2040/beyond16.elf'),'programmed':False,'release_ready':False})
mem=[]
for name,start,size,role in [('page0',0,115200,'display/back buffer + immutable source strip'),('page1',115200,115200,'display/back buffer + immutable source strip'),('PCM0 BGM',0x80000,384000,'8 second looping FM composition'),('PCM1 FX0',0xe0000,4096,'scene stinger'),('PCM1 FX1',0xe4000,2048,'scene stinger'),('PCM1 FX2',0xe8000,8192,'scene stinger'),('PCM1 FX3',0xec000,8192,'scene stinger'),('scratch',0x100000,4096,'bench only, before autoplay')]:
 mem.append({'name':name,'start':hex(start),'end_exclusive':hex(start+size),'bytes':size,'alignment':4,'role':role,'lifetime':'preload through end; scratch reusable after benchmark','discardable':'after playback stopped','start_integer':start})
for i,a in enumerate(mem):
 assert int(a['end_exclusive'],16)<=0x3fffff
 for b in mem[i+1:]:assert int(a['end_exclusive'],16)<=b['start_integer'] or int(b['end_exclusive'],16)<=a['start_integer']
write(R/'memory.json',{'die_relative_limit':4194304,'pcm_exclusive_end_max':'0x3fffff','psram':mem,'atlas':{'per_page_byte_offset':102400,'y':320,'width':640,'height':32,'bytes':10240,'logo':'header, y16..79, already in both pages','plasma':'tiles 8..15, sx=40*id,sy=320,size=32x32','storm_roto_wave':'sphere/icon tiles0..7; waves generated as FILL bands','mapping':'BLIT sources are framebuffer rectangles; no arbitrary PSRAM-address BLIT','visible':True,'lifetime':'entire demo; never erased by dynamic region'},'dirty_map_ram_bytes':4160,'lz_history_ram_bytes':32768,'framebuffer_in_rp2040_ram':False,'flash_bin_bytes':n,'firmware_sector_end_exclusive':hex(0x10000000+sector_end),'filesystem_start':'0x100a0000'})
stack=[]
for p in (R/'out/rp2040').rglob('*.su'):
 for line in p.read_text().splitlines():
  if '/beyond16/src/' in line or '/midnight_terminal/src/' in line:stack.append(line)
(E/'stack-usage.txt').write_text('\n'.join(stack),encoding='utf-8')
a=json.loads((E/'pc-baseline.json').read_text());b=json.loads((E/'pc-optimized.json').read_text());bench=json.loads((E/'benchmarks.json').read_text());before=json.loads((E/'before-after.json').read_text());frames=sum(s['frames'] for s in b['scenes']);mean=sum(s['frames']*s['cpu_frame_mean_ms'] for s in b['scenes'])/frames;worst=max(s['cpu_frame_worst_ms'] for s in b['scenes']);fence=next(r for r in bench['operations'] if r['variant']=='optimized' and r['op']=='FENCE')
text='''# 性能報告 — BEYOND 16 COLORS

実機は一切操作していない。PCのregister modelは3回のstatus pollingで完了させる機能モデルであり、PIO・GPIO固定費・PSRAM仲裁・HDMI vblank・PCM prefetchの時間を再現しない。以下のPC時間はネイティブC/SDK/modelのCPU実行時間。論理時間で割った通信量は「この描画を指定頻度で更新するための要求量」であり、実機がその量を処理できる証拠ではない。

## 指定比較表

|指標|MIDNIGHT TERMINAL実測|MEGADEMO PC|MEGADEMO実機|
|---|---:|---:|---|
'''
text+=f'|Host transactions/s|{839060/95:.2f}（約95秒で除算）|{b["runtime_counts"][0]/150:.2f}（論理150秒で除算）|未実行|\n|wire bytes/s|{6753735/95:.2f}|{b["runtime_counts"][1]/150:.2f}（要求量）|未実行|\n|平均frame time|未計測|{mean:.4f}ms CPU/model|未実行|\n|FENCE待機|未計測|{fence["cpu_model_mean_us"]:.3f}µs CPU/model呼出し全体。物理待機は未モデル化|未実行|\n|実更新fps|通常scheduler約30Hz、増殖0.65–3Hz、scroll19–20Hz|{frames/150:.3f}論理更新/s。実機fpsではない|未実行|\n|PCM underrun|0（前作観測）|未モデル化。PCM制御fault=0、オフラインPCM生成欠落=0|未実行|\n'
text+='\n前作の57.60秒はtransaction累積時間でありGPU内部描画時間ではない。元ログの測定区間・startup包含と95秒の周回区間は厳密一致が保証されないため、上の前作rateは指定基準値からの参考算出。異なる作品間の高速化倍率は算出しない。\n\n## 同条件Before/After\n\n'
text+=f'同一Cシーン・seed 0xB1616・33ms論理schedule・同一model。通常SDK＋CAPS非cache → opt-in descriptor burst＋session CAPS cache。\n\n|指標|Before|After|\n|---|---:|---:|\n|GPU commands|{a["runtime_counts"][2]:,}|{b["runtime_counts"][2]:,}|\n|Host transactions|{a["runtime_counts"][0]:,}|{b["runtime_counts"][0]:,}|\n|Wire bytes|{a["runtime_counts"][1]:,}|{b["runtime_counts"][1]:,}|\n|本編WRITE upload bytes|0|0|\n\ntransactionは{before["transaction_reduction_percent"]:.2f}%削減。全シーン代表画素CRC一致。これは通信回数の削減で、実機速度の改善宣言ではない。GPU command数は変わらない。\n'
text+='\n## Scene別PC結果\n\n|Scene|更新数|command/s要求|transaction/s要求|wire B/s要求|平均CPU ms|最悪CPU ms|\n|---|---:|---:|---:|---:|---:|---:|\n'
for s in b['scenes']:text+=f'|{s["name"]}|{s["frames"]}|{s["gpu_commands"]/s["logical_seconds"]:.1f}|{s["transactions_per_logical_second"]:.1f}|{s["wire_bytes_per_logical_second"]:.1f}|{s["cpu_frame_mean_ms"]:.4f}|{s["cpu_frame_worst_ms"]:.4f}|\n'
text+='\n描画負荷は依然大きい。30/60fps、無停止遷移、実機音声の安定性はいずれも未証明。選んだ標準64 stars／32 objectsはPCでの保守的設定であり、実機安定上限として選定した値ではない。\n\n## 負荷段階試験\n\n|対象|個数|2秒の更新数|commands|transactions|wire bytes|BLIT pixels|CPU平均µs|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
for s in bench['load_sweep']:text+=f'|{s["kind"]}|{s["count"]}|{s["frames"]}|{s["gpu_commands"]}|{s["transactions"]}|{s["wire_bytes"]}|{s["blit_pixels"]}|{s["cpu_model_mean_us"]:.2f}|\n'
text+='\n全組合せでmodel command error=0／BUSY上書き=0。FENCE物理待機と実機fpsは未実行。個数が増えるとHost要求量が増える事実をそのまま記録した。\n\n40件の転送／GPU／PCMベンチは[benchmarks.json](evidence/benchmarks.json)。RAW/CSR等の実機測定は[計画書](HARDWARE_PLAN.md)を参照。\n'
(R/'PERFORMANCE.md').write_text(text,encoding='utf-8')
status={'C_build':'PASS','PC_preview':'PASS','GPU_command_compatibility':'PASS (existing SDK + independent behavioral model; new burst hardware NOT RUN)','pixel_oracle':'PASS (20 timestamps x 2 variants; full timeline before/after CRC and existing SDK regressions)','PCM_data_generation':'PASS','flash_capacity_filesystem_protection':'PASS (offline bin/ELF/sector bounds; no write performed)','PC_performance_measurement':'PASS (CPU/model and wire counts; no physical timing simulation)','hardware_performance':'NOT RUN','hardware_audio':'NOT RUN','hardware_full_demo':'NOT RUN','RTL_changes':0,'release':'NOT READY','release_ready':False}
write(R/'STATUS.json',status)
# Snapshot inputs; outputs and old evidence do not participate in source hashes.
inputs=list((R/'src').glob('*'))+list((R/'tools').glob('*.py'))+list((R/'tools').glob('*.ps1'))+list((R/'tools').glob('*.sh'))+[R/'CMakeLists.txt',repo/'software/kagura_fb/kagura_fb.c',repo/'software/kagura_fb/kagura_fb.h',repo/'software/midnight_terminal/src/mt_qspi.c',repo/'software/midnight_terminal/src/mt_qspi.h',repo/'software/midnight_terminal/src/mt_lz.c',repo/'software/midnight_terminal/src/mt_lz.h',repo/'software/midnight_terminal/vendor/kagura_host.pio',R/'generated/assets.inc']
write(E/'source-sha256.json',{str(p.relative_to(repo)).replace('\\','/'):sha(p) for p in inputs if p.is_file()})
write(E/'counter-schema.json',{'pc_counts_array':['host_transactions','wire_bytes_including_headers_dummy','completed_GPU_commands','completed_PRESENTs','BLIT_pixels','PSRAM_WRITE_bytes_aligned','GPU_errors','BUSY_window_write_violations'],'timing':'CPU/model only. pc clock_ms increments on callback and is for timeout tests, never used as a physical duration.'})
write(E/'asset-sha256.json',{str(p.relative_to(R)).replace('\\','/'):sha(p) for p in (R/'generated').glob('*') if p.is_file()})
patch=subprocess.run(['git','diff','--','software/kagura_fb/kagura_fb.c'],cwd=repo,capture_output=True,check=True).stdout;(E/'sdk-opt-in.patch').write_bytes(patch)
# Preserve PC measurements while incorporating the separately recorded physical run.
hwpath=E/'hardware/performance.json'
if hwpath.exists():
 hw=json.loads(hwpath.read_text());rate=hw['runtime_rate_window'];audio=json.loads((E/'hardware/audio.json').read_text());flash=json.loads((E/'hardware/flash-write-verified.json').read_text())
 status.update({'GPU_command_compatibility':'PASS (existing SDK + independent model + finite physical optimized run)','flash_capacity_filesystem_protection':'PASS (full physical readback, firmware matches, tail and filesystem unchanged)','hardware_performance':'MEASURED / FAIL 30fps target (scene range 3.9..21fps)','hardware_audio':'PASS observed finite 150s capture; PCM status fault0; no >=10ms low-RMS gap; independent underrun counter unavailable','hardware_full_demo':'PASS (8 scenes, STOP rc=0)','physical_before_after':'NOT RUN (optimized firmware only)','hardware_framebuffer_crc':'NOT RUN','current_hardware_state':'BEYOND firmware, finale held, audio stopped, QSPI deinitialized'})
 write(R/'STATUS.json',status)
 build=json.loads((E/'rp2040-build.json').read_text());build.update({'programmed':True,'flash_deployment':flash,'hardware_result':'HARDWARE_RESULT.md'});write(E/'rp2040-build.json',build)
 protection=json.loads((E/'protection.json').read_text());protection.update({'hardware_opened':True,'current_device_flash_read':True,'new_backup':json.loads((E/'hardware/backup-verified.json').read_text()),'fpga_sram_programs_this_campaign':1,'fpga_flash_written':False});write(E/'protection.json',protection)
 fence=next(x for x in hw['bench'] if x['phase']=='PCM_PLAYING' and x['op']=='fence')
 cells={'Host transactions/s':f"{rate['transactions_per_s']:.2f}（startup除外）",'wire bytes/s':f"{rate['wire_bytes_per_s']:.2f}",'平均frame time':f"{hw['mean_frame_ms']:.3f}ms（描画呼出し）",'FENCE待機':f"{fence['completion_us']['mean']:.2f}µs（Host completion確認）",'実更新fps':f"{rate['actual_fps']:.3f}全体、scene3.9–21.0",'PCM underrun':'STATUS fault0、capture低RMS欠落0。独立counterなし'}
 path=R/'PERFORMANCE.md';txt=path.read_text(encoding='utf-8').replace('実機は一切操作していない。','実機の有限1周測定を追記した。')
 lines=[]
 for line in txt.splitlines():
  for key,value in cells.items():
   if line.startswith('|'+key+'|'):
    parts=line.split('|');parts[-2]=value;line='|'.join(parts);break
  lines.append(line)
 txt='\n'.join(lines)+'\n\n## 実機の判定\n\n全8sceneを150秒で正常STOP。30fps目標はFAIL、Release NOT READY。実機Before/Afterは未実行で、PCの11.18%を実機速度改善としない。[実機結果とScene別実測](HARDWARE_RESULT.md)。\n'
 # Earlier sections describe the frozen PC campaign; label their unmeasured scope.
 txt=txt.replace('実機の30fps／軽量60fps、連続描画のPSRAM負荷、音声underrun、initial preload時間、AV driftは未測定。','')
 txt=txt.replace('実機は未実行。','PC凍結時点では実機未実行。')
 path.write_text(txt,encoding='utf-8')
print('PASS: protected bitstream/backups, freeze, ELF/sector bounds; bin',n,'sector',hex(sector_end),'commands',b['runtime_counts'][2])
