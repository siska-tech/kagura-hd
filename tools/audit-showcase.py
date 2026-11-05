"""Freeze Host-only showcase evidence. No device access or source mutations."""
from pathlib import Path
import hashlib,json,re,subprocess,zipfile
r=Path(__file__).resolve().parents[1];p=r/'software/kagura_fb/showcase';b=r/'build/showcase'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
checks={}
for key,name,marker in [
 ('showcase16','tests.log','Ran 16 tests'),('existing15','existing-drivers.log','Ran 15 tests'),
 ('existing_qspi4','existing-drivers.log','Ran 4 tests'),
 ('micropython192','micropython-192k.log','PASS: MicroPython Unix bounded heap'),
 ('micropython128','micropython-128k.log','PASS: MicroPython Unix bounded heap'),
 ('ram_loader','ram-loader.log','PASS: RAM export load')]:
 f=b/name;s=f.read_text(errors='replace')
 ok=marker in s and 'Traceback' not in s and 'FAILED' not in s
 if key.startswith('showcase') or key.startswith('existing'):ok=ok and 'OK' in s
 checks[key]={'pass':ok,'log':str(f.relative_to(r)),'sha256':sha(f)}
assert all(x['pass'] for x in checks.values()),checks
diff=subprocess.check_output(['git','diff','--name-only','--','rtl','boards'],cwd=r,text=True).strip()
assert not diff,'Existing root RTL/board files changed'
candidate=r/'build/pcm2-timing-04';manifest=json.loads((candidate/'build/standard-timing-04/source-input-manifest.json').read_text())
assert all(sha(candidate/x)==h==sha(candidate/'build/standard-timing-04/inputs'/x) for x,h in manifest.items())
protected={
 'pcm2_sta04':('build/pcm2-timing-04/build/standard-timing-04/impl/pnr/kagura_fb.fs','642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7'),
 'rmw':('build/upload-rmw-worktree/build/standard-latched-rmw/impl/pnr/kagura_fb.fs','90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e'),
 'rx32':('build/rx32-scanout-worktree/build/kagura-fb-qspi/impl/pnr/kagura_fb.fs','a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf')}
assert all(sha(r/f)==h for f,h in protected.values())
assert not list(b.rglob('*.fs'))
assert 'release_ready=false' in (candidate/'DO_NOT_PROGRAM.txt').read_text()
assert 'release_ready=false' in (candidate/'build/standard-timing-04/DO_NOT_PROGRAM.txt').read_text()
for marker in ['build/rx32-scanout-worktree/DO_NOT_PROGRAM.txt','build/rx32-scanout-worktree/build/kagura-fb-qspi/DO_NOT_PROGRAM.txt']:
 assert sha(r/marker)=='d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546'
assert sha(r/'software/kagura_fb/kagura_fb.py')==sha(candidate/'software/kagura_fb/kagura_fb.py')
assert sha(r/'software/kagura_fb/kagura_fb_audio.py')==sha(candidate/'software/kagura_fb/kagura_fb_audio.py')
provenance=json.loads((p/'provenance.json').read_text())
for name in ['fonts.py','font-license.txt']:assert sha(p/'vendor'/name)==provenance[name]['sha256']
assert sha(r/'software/kagura_fb/kagura_fb_audio.py')==provenance['kagura_fb_audio.py']['sha256']
loader=json.loads((b/'ram-loader/manifest.json').read_text())
assert all(sha(r/x['source'])==x['sha256'] for x in loader)
preview=json.loads((b/'preview/result.json').read_text())
assert preview['frames']==288 and preview['wav']['clipped_samples']==0
video=json.loads((b/'video-probe.json').read_text(encoding='utf-8-sig'))
v=next(s for s in video['streams'] if s['codec_type']=='video');a=next(s for s in video['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['r_frame_rate'])==(1280,720,'60/1')
assert (a['sample_rate'],a['channels'])==('48000',2) and float(video['format']['duration'])==36
sources={str(f.relative_to(r)):sha(f) for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
artifacts={str(f.relative_to(r)):sha(f) for f in (b/'preview').iterdir() if f.is_file()}
heap={}
for name in ['micropython-128k.log','micropython-192k.log','ram-loader.log']:
 text=(b/name).read_text();m=re.search(r'heap_before=(\d+) heap_after=(\d+) sampled_max_alloc=(\d+) sampled_min_free=(\d+)',text)
 heap[name]=dict(zip(['before','after_gc','sampled_max_alloc','sampled_min_free'],map(int,m.groups())))
evidence={'release_ready':False,'all_pc_checks_pass':True,'checks':checks,'source_sha256':sources,
 'artifacts_sha256':artifacts,'heap_unix_only':heap,'preview':preview,
 'protected_bitstreams':{k:h for k,(f,h) in protected.items()},'fixed_fpga_inputs_unchanged':len(manifest),
 'root_rtl_boards_diff_empty':True,'existing_driver_unchanged':True,'audio_sdk_reused_verbatim':True,
 'new_demo_verilator_replay_performed':False,'hardware_test_performed':False,'new_bitstream_generated':False,
 'rp2040_heap_measured':False,'external_psram_io_verified_by_demo':False,
 'micropython_version':(b/'micropython-version.log').read_text().strip(),
 'prior_do_not_program_markers_preserved':True,
 'limitations':['behavioral Mock is not RTL/IO/PVT proof','Unix heap fixture is not native RP2040','Host timing is virtual in preview','FIFO level/sample position unavailable in ABI']}
ep=r/'docs/evidence/kagura-hd-showcase-pc-2026-11-05.json';ep.write_text(json.dumps(evidence,indent=2)+'\n')
report=r/'docs/kagura-hd-showcase-result-2026-11-05.md'
report.write_text('''# KAGURA-HD 統合ショーケース PC評価

**6シーンのHost実装、独立oracle検証、PCプレビュー生成を完了。実機未実施、release_ready=false。**

## 成果物

- [ソース・動作手順・ABI監査・録画構成](../software/kagura_fb/showcase/README.md)
- [対話プレビュー](../build/showcase/preview/index.html)、[720p MP4](../build/showcase/preview/kagura-hd-pc-preview.mp4)
- [6画面一覧](../build/showcase/preview/contact-sheet.png)、[元の非圧縮音源](../build/showcase/preview/tiny-horizon.wav)
- [検証JSON・ソース/成果物hash](evidence/kagura-hd-showcase-pc-2026-11-05.json)
- 配布用ZIP：`build/showcase/kagura-hd-showcase.zip`（PCでのみ生成、実機への自動senderなし）

## 既存コードの監査

root既存Device/6bit protocolをそのまま使用。音声facadeはPCM2 STA合格候補から同一hashで再利用し、ABI1.4/CAPS FFを厳密照合する。旧KAGURA-9の別ABIや1.3の6ch prototypeと同一視しない。文字opcodeを仮定せず、既存KAGURA Hostフォントを小さなscanlineへ展開してWRITEする。

BLITは偶数x/幅・同一x modulo8・範囲内を検証。PRESENTはFENCEと既存同期waitでVBlank ACKまで待つ。Cursorはinactive bankへの全shape転送とACKを守る。PCMはSTOP確認、384000B×2の初回供給、PREPARE/READY、単一COMMITの順に開始する。

## PC結果

|確認|結果・実行範囲|
|---|---|
|新デモ16試験|PASS。6章×2周、計576更新、開始/終了/ループ|
|FILL|clip、odd nibble、末尾画素、複数領域を独立unpacked pixel oracleで比較|
|BLIT|上下左右・斜めの重なり、guard、無効phaseの送信前拒否|
|窓の意味的再合成|全48位置でCOPYを使わない新規合成画像と一致。影の範囲と透明cornerの残像を検出・修正|
|PALETTE/PRESENT|Mock上でACK前は旧page/palette、ACK後は対で反映。前半24更新のFB無変更、後半の交互pageと色循環を検査|
|Cursor|両pageの前後CRC一致、移動中FILL/WRITE/COPYなし、bank lock、形状/色変更、edge clip|
|PCM|全byte upload readback、独立mix式、RMS/peak、READY/ACTIVE/STOP、faultによる停止|
|異常処理|BUSY前投入ゼロ、completion timeout、device error、不確かなsubmit、PCM underrun。再送/自動reset/cleanupなし、復旧後fresh instanceのみ|
|既存ドライバ|C/Python 15件＋QSPI 4件 PASS|
|MicroPython Unix|128KiBと192KiBの各ヒープで全12シーン/2周 PASS（storage-free sink）|
|RAM loader|13 packet読込み後、192KiBで全12シーン/2周 PASS。GPIO/serial/filesystem書込みなし|

新デモの検証は実Device/Audioドライバを通した**behavioral wire Mock**。新しいpacket列のVerilator replay、HDMI実機取得、外部PSRAMの物理検証は行っていない。既存RTL回帰を今回新規実行したとは扱わない。

## メモリ・性能の意味

Hostは320B scanline、256B PCM生成、必要時256B検証、256B cursorを使い、全FBを持たない。PC oracleの460800B/4MiB MockをRPへ持ち込まない。Unix heapのGC後保持/観測最大は下表の通り。GC前の最大値はgarbageを含み、native RP2040のheap/stack保証ではない。

|Unix fixture|GC後保持 B|観測最大 B|観測最小free B|
|---|---:|---:|---:|
'''+''.join('|%s|%d|%d|%d|\n'%(name,x['after_gc'],x['sampled_max_alloc'],x['sampled_min_free']) for name,x in heap.items())+'''

動画は36秒、1280×720、60fps container、48kHz stereo。Hostは仮想8Hz更新を繰り返したもので、実機GPU/Host処理時間の測定ではない。シーン構築の黒待機や初回768000Bロード時間も動画へ含めていない。実機ではwork時間が125msを超えれば更新を遅くし、sleep・実更新Hz・PRESENT待機・errorを別記録する。

PCM源「Tiny Horizon」はオリジナル生成の120BPM/8秒2track。WAV stereo peakは'''+str(preview['wav']['peak'])+'、clip sample '+str(preview['wav']['clipped_samples'])+'''。メーターは生成PCMとGAIN/MASTERのRMS/peakで、位置はHost時刻推定。HDMI音声の解析結果やFFT、FIFO水位の実測と称しない。

## 保護・安全・未確認

FPGA固定40入力、元のSTA Bitstream群、root RTL/boardsと既存Deviceを保護しhash照合。新しいBitstream、Flash/FW/filesystem変更、実機操作、Git Push/Merge/Releaseを行っていない。既存DO_NOT_PROGRAM/release_ready=falseを維持。

次はPSRAM統合試験PASS後、別承認済みの有限実機計画で、静止画→BLIT/PRESENT/cursor→PCM/連続動作。SRAMのみ一時投入し、正常/異常どちらも既存KAGURA-9復旧とFlash hash/banner/HDMI確認を完了条件とする。復旧image hashの過去の保留を今回解決済みとは扱わない。

未確認：native RP2040のheap/stackとloader、実帯域/描画更新の滑らかさ、HDMI AV capture、真のsample位置/FIFO水位、長時間AV drift、PSRAM外部I/O/PVT、実機復旧。詳細と具体的な起動・停止手順はREADMEを参照。
''')
bundle=b/'kagura-hd-showcase.zip'
files=set()
for f in p.rglob('*'):
 if f.is_file() and '__pycache__' not in f.parts:files.add(f)
for name in ['kagura_fb.py','kagura_fb_audio.py','rp2040_qspi.py','kagura_fb.c','kagura_fb.h','tests/model.py','tests/test_drivers.py','tests/test_rp2040_qspi.py']:
 files.add(r/'software/kagura_fb'/name)
for name in ['test-showcase.sh','test-fb-drivers.sh','preview-showcase.py','bundle-showcase-ram.py','encode-showcase-video.ps1','audit-showcase.py']:
 files.add(r/'tools'/name)
files.update([ep,report,r/'LICENSE'])
files.update(f for f in (b/'preview').iterdir() if f.is_file())
files.update(f for f in (b/'ram-loader').iterdir() if f.is_file())
files.update(b/name for name in ['tests.log','test-suite.log','existing-drivers.log','micropython-128k.log','micropython-192k.log','ram-loader.log','micropython-version.log','video-probe.json','video-encode.log'])
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted(files):z.write(f,str(f.relative_to(r)))
(b/'bundle-sha256.txt').write_text(sha(bundle)+'  '+bundle.name+'\n')
print(json.dumps({'all_pc_checks_pass':True,'root_rtl_unchanged':True,'protected_bitstreams':{k:h for k,(f,h) in protected.items()},
 'heap_unix_only':heap,'bundle_bytes':bundle.stat().st_size,'bundle_sha256':sha(bundle),'release_ready':False},indent=2))
