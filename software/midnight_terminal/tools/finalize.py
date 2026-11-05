"""Collect local evidence, ELF section/symbol sizes and memory table. No hardware IO."""
from pathlib import Path
import json,hashlib,shutil,struct,sys,subprocess,re
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'out';evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
for pattern in ['0*.png','report.json','wire-report.json','frame-crc.json','gui-smoke.json','audio-events.json']:
 for p in out.glob(pattern):shutil.copy(p,evidence/p.name)
data=(out/'rp2040/midnight_terminal.elf').read_bytes();assert data[:6]==b'\x7fELF\x01\x01'
shoff=struct.unpack_from('<I',data,32)[0];entry,count,strings=struct.unpack_from('<HHH',data,46)
sections=[struct.unpack_from('<10I',data,shoff+i*entry) for i in range(count)];s=sections[strings];names=data[s[4]:s[4]+s[5]]
def string(tab,offset):return tab[offset:tab.index(0,offset)].decode()
alloc=[];symbols={}
for sec in sections:
 name=string(names,sec[0])
 if sec[2]&2:alloc.append({'section':name,'address':hex(sec[3]),'bytes':sec[5],'type':sec[1]})
 if sec[1]==2:
  st=sections[sec[6]];tab=data[st[4]:st[4]+st[5]]
  for pos in range(sec[4],sec[4]+sec[5],sec[9]):
   n,val,size,info,other,index=struct.unpack_from('<IIIBBH',data,pos)
   nm=string(tab,n)
   if nm in ['__StackTop','__StackBottom','__flash_binary_end','mt_bar','mt_warning','mt_mplus','mt_misaki','mt_pcm_bgm']:symbols[nm]={'address':hex(val),'bytes':size}
size_match=re.findall(r'(?m)^\s*(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+[0-9a-f]+\s+', (evidence/'rp2040-build.log').read_text())[-1]
build={'release_ready':False,'target':'RP2040 / pico / Cortex-M0+','compiler':'Arm GNU 14.2.Rel1 / GCC 14.2.1','sdk_commit':'bddd20f928ce76142793bef434d4f75f4af6e433','text_bytes':int(size_match[0]),'data_bytes':int(size_match[1]),'bss_bytes':int(size_match[2]),'sections':alloc,'symbols':symbols,'stack_reserved_bytes':4096,'elf_sha256':hashlib.sha256(data).hexdigest(),'bin_sha256':hashlib.sha256((out/'rp2040/midnight_terminal.bin').read_bytes()).hexdigest(),'compiler_archive_sha256':hashlib.sha256((ROOT/'toolchain/arm.zip').read_bytes()).hexdigest(),'compiler_url':'https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-mingw-w64-i686-arm-none-eabi.zip','programmed':False}
build['host_transport']={'type':'KAGURA-9 original PIO / HD six-bit protocol','rp2040_hz':120000000,'nominal_sck_hz':5000000,'pio_clkdiv':2,'hd_hardware_verified':False}
if (ROOT/'evidence/hardware/flash-write-verified.json').exists():
 build['programmed']=True;build['host_transport']['hd_hardware_verified']='finite native C campaign completed; physical SCK not scope-measured'
 build['flash_deployment']=json.loads((ROOT/'evidence/hardware/flash-write-verified.json').read_text())
assert int(symbols['__StackTop']['address'],16)-int(symbols['__StackBottom']['address'],16)==4096
(evidence/'rp2040-build.json').write_text(json.dumps(build,indent=2))
mem=[]
for name,start,size,role in [('Framebuffer page0',0,115200,'double buffer'),('Framebuffer page1',115200,115200,'double buffer'),('bar backup',0x40000,115200,'background + attendant + UI, opaque composite'),('warning backup',0x60000,115200,'pre-generated 80x44 cells + header'),('PCM0 BGM',0x80000,384000,'8s loop'),('PCM1 select',0xde000,6720,'one shot'),('PCM1 talk',0xe0000,1680,'one shot'),('PCM1 alarm',0xe1000,14400,'one shot'),('PCM1 restore',0xe5000,11520,'one shot')]:
 mem.append({'name':name,'start':start,'end_exclusive':start+size,'start_hex':hex(start),'end_hex':hex(start+size),'bytes':size,'role':role})
for i,a in enumerate(mem):
 assert 0<=a['start']<a['end_exclusive']<=0x3fffff
 assert all(a['end_exclusive']<=b['start'] or b['end_exclusive']<=a['start'] for b in mem[i+1:])
memory={'addressing':'die-relative bytes / 4MiB / exclusive PCM END <=0x3fffff','psram':mem,'flash':{'mplus_subset':9600,'misaki_subset':9600,'bar':115200,'warning':115200,'pcm_total':418320},'host_scratch':'No full framebuffer. Text positions/Unicode arrays 1024B stack, max glyph row 6B; existing SDK transfer scratch64B. Generated data const in Flash.','cursor':'256B shape transient stack, hardware separate cursor bank; not PSRAM','scratch_psram':'none allocated'}
(ROOT/'memory.json').write_text(json.dumps(memory,ensure_ascii=False,indent=2))
if (ROOT/'generated/bgm-pack.json').exists():
 pack=json.loads((ROOT/'generated/bgm-pack.json').read_text());memory['flash']['bgm_lossless_packed']=pack['packed_bytes'];memory['flash']['pcm_total']=pack['packed_bytes']+34320;memory['rp2040_history_ram_bytes']=32768;memory['expanded_psram_pcm_bytes']=418320
 (ROOT/'memory.json').write_text(json.dumps(memory,ensure_ascii=False,indent=2))
pc=json.loads((out/'report.json').read_text());wire=json.loads((out/'wire-report.json').read_text())
stack=[]
for p in (out/'rp2040').rglob('*.su'):
 for line in p.read_text().splitlines():
  if '/midnight_terminal/src/' in line:stack.append(line)
(evidence/'stack-usage.txt').write_text('\n'.join(stack))
hashes={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['src','tools','tests','generated','vendor'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not any(s in p.parts for s in ['misaki','mplus'])}
(evidence/'artifact-sha256.json').write_text(json.dumps(hashes,indent=2))
report=f'''# 検証・性能レポート

最終状態：PCプレビュー、日本語フォント、GPUコマンド、PCMデータ、RP2040 Cビルドと独立画素検証を完了。後続のユーザー承認によりC firmware Flash書換えと既存FPGA SRAM投入を実施し、実機autoplayを1周録画した。既存filesystemはbyte一致を確認して保持。BGM stereo相関0.999692、BGM中のPCM1決定音相関0.999914。性能・全分岐・全画面CRC等は残る。[実機結果](HARDWARE_RESULT.md)。Release NOT READY、`release_ready=false`。

## 実施結果

`evidence/pc-tests.log`：8テストPASS。UTF-8正常・不正列、半角／全角、未知文字代替、独立した原BDF baseline照合、折返し／改行／基本禁則、nibble・重なり・palette/PRESENT、警告行順序・漸増・スクロール・黒画面・復旧、3分岐／ループ、PCMフォーマット・範囲を含む。

`evidence/sdk-tests.log`：6テストPASS。既存C SDKの実descriptorを、リポジトリの独立register/pixel Modelへ送った。160件のランダムFILL、128件のBLITと画素比較、不正4件の送信前拒否、非整列mask WRITE、15時点での全Framebuffer＋palette一致、PCM COMMIT snapshotのBGM保持、STOP／再開、faultによる映像fallback、実機用事前診断と最初のerrorで停止することを検査した。これはFPGAサイクル／prefetch／HDMI音声を模擬する試験ではない。BGMの可逆LZについて、別のC試験4件が元384,000byteとの完全一致・history wrap・不正stream・sink失敗での停止を検証した。

追加の`evidence/qspi-tests.log`：8テストPASS。KAGURA-9の原PIOを再利用した5MHz転送路のC実装、6bitレジスタ、dummy／ターンアラウンド、256byte、timeout停止・再送禁止と、実際にアセンブルしたPIOの周期・setup・IO競合を検査した。さらに候補04の無変更RTLを使う5MHz board-top機能シミュレーションがPASSし、Host upload/readback/FENCE、PCM2 sample oracle、COMMIT、gain、pause/resume、loop/one-shot、lateなしを確認した。clock／DDR PHY／LVDSは既存の機能モデルを使っており、HD実機の検証ではない。詳細は[QSPI_REPORT.md](QSPI_REPORT.md)。

88秒・無操作autoplayをPC Cエンジンで走査し、全7場面と警告内5時点をPNG保存。録画用フレームは1,896枚。Tk GUI描画とpygame 48kHz初期化もsmoke成功。ブラウザHTMLの手動全操作試験は未実施。後続の実機captureはPC記録と別に`build/midnight-hardware/`へ保存した。PC音声ミックスを実機録音に読み替えていない。

## PC計測（ハードウェアの値ではない）

|測定|値|
|---|---:|
|論理時間|88,000ms|
|PC preview tick平均|{pc['pc_tick_ms_mean']:.3f}ms|
|PC preview tick P95|{pc['pc_tick_ms_p95']:.3f}ms|
|PC preview tick最大|{pc['pc_tick_ms_max']:.3f}ms|
|PRESENT回数（準備の黒PRESENT含む）|{pc['present_count']:,}|
|Host素材WRITE byte（抽象adapter）|{pc['host_asset_bytes']:,}B|
|実C SDK descriptor数（PCM起動を含む）|{wire['commands']:,}|
|PC protocol register WRITE byte|{wire['traffic']['write_bytes']:,}B|
|PC protocol register READ byte|{wire['traffic']['read_bytes']:,}B|
|PC protocol transaction数|{wire['traffic']['transactions']:,}|

preview tickはPython backend・trace生成を含むがPNG圧縮／Tk描画／音声mixを含まない。33ms刻みの仮想時計による計測で、平均値の逆数を実機FPSとは扱わない。静止時にはPRESENTを省くため、全PRESENT数／88をアニメーションFPSとも扱わない。通常の雨と満杯後の警告スクロールは33msごとの更新を狙い、警告増殖は130msごとの行追加。

独立register/pixel Model経由のC SDK実行は平均{wire['pc_tick_ms_mean']:.3f}ms／P95 {wire['pc_tick_ms_p95']:.3f}ms／最大{wire['pc_tick_ms_max']:.3f}ms。Pythonの画素単位BLIT snapshotに時間を費やす検査用モデルで、これもHost／FPGAの処理速度ではない。全88秒の実descriptorと毎秒集計を`out/wire-descriptors.jsonl`、`evidence/wire-report.json`へ保存した。

後続実機測定では、開始指示→最初の画像約20.16秒、背景再構築約3.5秒、最初の画像→次BOOT約95秒。通常schedulerは概ね30Hz、警告増殖は一部0.65–3Hz、満杯後は約19–20Hz。これはPRESENT／HDMI refreshの直接測定ではない。1周末尾wire 6,753,735B／839,060 transactions／transaction時間57.60秒、最長352µs、timeout 0。FENCE単体・PRESENT ACK単体・physical SCKは未測定。5MHzのPIO設定を30fpsの達成と同一視しない。同期ロード・細かいtransactionの削減は残課題で、性能目標は未達。

## ROM / RAM

Pico SDK 2.1.1、GNU 14.2.1、RP2040 Cortex-M0+のリンク成功。text {build['text_bytes']:,}B、data {build['data_bytes']:,}B、BSS {build['bss_bytes']:,}B。4KiB stackを別途明示した。`.su`でtext rendererのローカル枠1,136B、mt_tick 224B、既存SDK transfer 192Bを確認した。これは関数単体の静的値であり、割込みを含む実測stack high-waterではない。全文字／全FramebufferはRP2040 RAMへ配置していない。配置先のFlashアドレスとstack symbolは`evidence/rp2040-build.json`。

実機向け版は既存filesystemの開始640KiBより小さくするため、BGMを可逆LZへ圧縮し、32KiBのhistory RAMからPSRAMへ64Bずつ展開・全量照合する。USB CDCで開始指示・ログ・復旧を扱える。PC DLLは非圧縮の元PCMを使うため、そのPCコマンド集計を実機版の全量読戻し付き起動コストとは同一視しない。

MSVCの既存SDK部分にC4389とC4701の警告がある。保護対象SDKをこの作業で修正していない。Arm Cビルドでは新規Cの警告はなく、TinyUSBを固定submoduleから取得したためUSB未取得警告も解消した。

## 証跡と保護

各時刻のFramebuffer CRCは`evidence/frame-crc.json`。PNGは別合成のcursorを含み、CRCはindex framebufferのみなのでPNGファイルCRCと比較しない。コマンドtraceは`out/commands.jsonl`（抽象命令）、`out/sdk-command-trace.json`（15時点のSDK）、`out/wire-descriptors.jsonl`（全周SDK）。

保存した278個のRTL／board／制約／既存SDK／候補04入力・Bitstream hashは`tools/preserve.py --check`で一致。既存のSTA資格を再認定するものではない。既存未コミット変更を保持し、FPGA回路／PLL／制約／Bitstream／FPGA Flashは変更していない。ユーザーの後続明示承認によりRP firmware Flashを変更し、既存候補をFPGA SRAMへ1回投入した。元RP全Flashを退避し、既存filesystemを保持した。Merge／Releaseは未実施。
'''
(ROOT/'REPORT.md').write_text(report,encoding='utf-8');print('Evidence, memory map and report saved. Release NOT READY.')
