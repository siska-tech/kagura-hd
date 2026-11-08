"""Freeze a completed physical campaign report. Offline only."""
from pathlib import Path
import argparse,hashlib,json

R=Path(__file__).resolve().parents[1];ROOT=R.parents[1]
p=argparse.ArgumentParser();p.add_argument('campaign',type=Path);args=p.parse_args();base=args.campaign.resolve()
campaign=json.loads((base/'campaign.json').read_text())
assert campaign['success'] and campaign['failure'] is None and len(campaign['variants'])==8
E=R/'evidence/headroom-hardware';comparison=json.loads((E/'comparison.json').read_text())
assert comparison['campaign_success'] and len(comparison['variants'])==8
results={r['name']:r for r in comparison['variants']}
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
initial=(base/'A-off/before.bin').read_bytes();ledger=[]
for record in campaign['variants']:
    name=record['name'];folder=base/name
    assert record['success'] and record['full_readback_unchanged'] and record['filesystem_unchanged']
    before=(folder/'before.bin').read_bytes();duplicate=(folder/'before-confirm.bin').read_bytes()
    after=(folder/'after.bin').read_bytes();final=(folder/'after-tests.bin').read_bytes()
    firmware=R/'out/headroom-firmware'/name/'beyond16.bin';f=firmware.read_bytes();erase=(len(f)+4095)&~4095
    assert before==duplicate and after==final and after[:len(f)]==f
    assert before[erase:]==after[erase:] and after[0xa0000:]==initial[0xa0000:]
    assert sha(firmware)==record['firmware_sha256']
    r=results[name];assert r['timeout']==0 and r['pcm_status_fault']==0 and r['stop_rc']==0
    assert r['audio']['low_10ms_blocks']==0
    ledger.append(dict(name=name,firmware_sha256=sha(firmware),before_sha256=sha(folder/'before.bin'),
                       after_sha256=sha(folder/'after-tests.bin'),bytes=len(final),erase_end=hex(0x10000000+erase),
                       duplicate_backup_equal=True,full_after_tests_equal=True,filesystem_equal_initial=True))
protection=json.loads((R/'evidence/headroom-protection.json').read_text())
assert protection['status']=='PASS'
(E/'campaign.json').write_text(json.dumps(campaign,indent=2))
(E/'flash-ledger.json').write_text(json.dumps(dict(variants=ledger,initial_backup_sha256=hashlib.sha256(initial).hexdigest(),
    protected_bitstream_sha256=protection['bitstream_sha256'],fpga_programming=0,fpga_flash_writes=0,
    release_ready=False),indent=2))

def fmt(v):return f'{v:.3f}'
lines=['# 8構成 実機比較結果','',
       '同じ描画・seed 0xb1616・RP2040 120MHz・既存QSPI設定・FPGA・配線で、固定hashの8構成を各1周150秒、PCM OFF/ON有限ベンチで比較した。FPGA投入0、FPGA Flash書込み0、release_ready=false。',
       '', '## 全体結果','',
       '|構成|実PRESENT fps|間隔中央値 ms|p95 ms|最悪間隔 ms|33.333ms超過 %|最悪call ms|記録deadline miss|',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for r in comparison['variants']:
    s=r['present_intervals_us']
    lines.append(f"|{r['name']}|{fmt(r['actual_present_fps'])}|{fmt(s['median']/1000)}|{fmt(s['p95']/1000)}|{fmt(s['worst']/1000)}|{fmt(r['interval_over_33_333ms_rate']*100)}|{fmt(r['worst_call_us']/1000)}|{r['deadline_misses']}|")
lines+=['','実PRESENT fpsは連続完了区間から(N-1)/経過時間で算出。名目scene秒数あたりframe数とは異なる。PRESENT完了はCPU観測のDONE/tag/error/ACK後で、HDMI edgeそのものではない。absolute30とrelative33のdeadline定義も異なるためmiss数だけで順位を付けない。',
        '', '## Scene別 実更新fps','', '|Scene|'+'|'.join(results)+'|', '|---|'+'|'.join(['---:']*8)+'|']
scene_names=['BOOT','HYPERSPACE','RASTER WAVES','PLASMA ENGINE','ROTOZOOM','BLIT STORM','VECTOR WORLD','FINALE']
for i,name in enumerate(scene_names):lines.append('|'+name+'|'+'|'.join(fmt(r['scenes'][i]['actual_update_fps']) for r in results.values())+'|')
lines+=['','## 長時間停止の位置','',
        '最悪callはいずれも約143秒、FINALE開始から3秒後の静的文字展開にある。A-offは143.167sで149.002ms。src/b16.cのcase7 / t>=3000で両pageへ初回letteringを展開する時刻と一致する。scene境界captionだけを最適化しても、この停止は残る。次の優先候補は画素等価なlettering矩形結合／展開手順の分割で、今回の8構成のソースとhashは変更しない。',
        '', '## 計測負荷','',
        'OFF/SUMMARY/DETAILEDのfps差は、詳細計測が再生を乱すことを示す。regionはIRQ・計測自身を含む排他的wall-timeであり、CPU実行率／idle率へ換算しない。短いBENCH transactionはUSBログIRQ位相にも影響され、16反復の中央値でも一般的な定数補正とは扱わない。DETAILEDは診断専用とし通常再生には採用しない。',
        '', '## DMA finite benchmark','',
        '以下はPCM ON、raw non-increment reg25 pointer WRITEの総時間中央値（16反復、us）。SDK PSRAM command全体とは区別する。',
        '', '|B|A-summary CPU|B-summary DMA eligible >=64|C-test128 DMA eligible >=128|', '|---:|---:|---:|---:|']
def bench(r,n):return next(b for b in r['bench'] if b['phase']=='PCM_PLAYING' and b['op']=='raw_pointer_write' and b['n']==n)['us']['median']
for n in (1,2,4,8,16,32,64,128,256,512):lines.append(f"|{n}|{bench(results['A-summary'],n)}|{bench(results['B-summary'],n)}|{bench(results['C-test128'],n)}|")
lines+=['','64B以上でDMAの総時間短縮が観測された。測定範囲の評価候補閾値は64B。ただし採用閾値は変更しない。DMA waitはpollingのままでCPU仕事を同時実行しておらず、CPU解放量は未測定。本編描画のdescriptor/CSRは短く、長いuploadは素材展開時だけなので、DMAによる本編fps改善の根拠は得られていない。',
        '', '凍結済み有限ベンチのscratchデータは全zeroであり、値を交互に変える実機DMAデータ完全性試験を代替しない。PC fakeはnonzero patternを検証した。PIO/READ方向/CSの独立logic analyzer波形、実機Framebuffer全byte oracleはNOT RUN。DMAの一般採用は保留する。',
        '', '## CPU workと協調処理','']
w=results['work64']['work'];a=results['A-summary'];work=results['work64']
cooperative=next(s for s in results['cooperative']['profile'] if s['region']=='COOP_WORK')
lines+= [f"work64: {w['batches']} batches × {w['rounds']} rounds = {w['rounds_completed']} rounds、定義した算術演算{w['arithmetic_operations']}回。演算区間wall-time {w['us']/1e6:.6f}s、checksum={w['checksum']}、再計算照合valid={w['valid']}。",
        '', f"同条件A-summaryのdeadline miss {a['deadline_misses']}、work64のmiss {work['deadline_misses']}。元からVECTOR／境界で期限超過があるため、全frame期限を守れるCPU Headroom上限を証明したとは扱わない。1idle tickに1batchという試験量であり最大負荷sweepではない。実仕事量はMEASURED、deadline準拠の割当可能能力はNOT ESTABLISHED。",
        '', f"GPU待機協調処理の計測window内seed生成は{cooperative['calls']}回、排他的wall-time {cooperative['exclusive_us']}us。CPU専用seed cacheのみで、DMAとの同時有効化なし。次frame VECTOR mask二重化やcore1は未実装。cooperative結果は1周の有限観測であり、わずかなfps差を有意な改善としない。",
        '', '## 音声・保護・残る条件','',
        '|構成|音声span s|10ms低RMS欠落blocks|BGM相関 最低|全Flash試験後一致|', '|---|---:|---:|---:|---|']
for r in results.values():
    audio=r['audio'];corr=min(s['correlation'] for s in audio['bgm_quiet_segment_correlations'])
    lines.append(f"|{r['name']}|{audio['audible_span_s']:.2f}|{audio['low_10ms_blocks']}|{corr:.6f}|PASS|")
lines+=['','8構成ともtimeout=0、PCM STATUS fault=0、STOP rc=0。音声は物理HDMI 48kHz/2ch capture、低RMS閾値20、10ms窓。各sceneのstinger後2秒を既知BGMへ相関照合。独立underrun counterはなく、全sampleの正常性保証ではない。BUSY overwriteの独立実機counterもなく、SDK直列化契約とPC回帰の範囲を区別する。',
        '', '各書込み前に新しい2MiB backupを2回保存して一致確認。書込み後と試験後の全量一致、erase終端以降の保持、filesystem 0x100a0000以降の全構成同一を検証。既存backupと保護対象248ファイルのhash不変。元のFlashへ戻す場合は今回A-off/before.binを第一復旧像とし、既存backupを上書きしない。',
        '', '最初のA-off demoはUSB再列挙raceで開始前に停止。開始markerもg送信もなく、完了済みbenchを繰り返さず、全Flash一致を再確認して未開始demoのみ継続した。再開時のログ上書き防止によるPC停止も記録。GPU timeout／不確定commandの再送は0。',
        '', '単発・固定順序比較であり、反復周回／順序無作為化／温度PVT／物理波形の証明はない。VECTOR平均30fps、全sceneの安定30fps、長時間停止削減は未達。CPU＋PIOを既定に保ち、DMA／cooperative／schedulerの採用変更とGit releaseは行わない。実機は最後のwork64 firmwareを保持し、PCM停止、g/b明示開始gateで待機。',
        '', '## 証跡','',
        '- [比較JSON](evidence/headroom-hardware/comparison.json)：全scene、PRESENT間隔、transition、profile、work、有限ベンチ、audio。',
        '- [Flash ledger](evidence/headroom-hardware/flash-ledger.json)：各firmware・新backup・試験後全量hash。',
        '- [Campaign](evidence/headroom-hardware/campaign.json)：段階と開始前停止の履歴。',
        '- 原HDMI動画・WAV・復旧像：'+str(base.relative_to(ROOT)).replace('\\','/')+'（既存記録を上書きせず保管）。']
(R/'HARDWARE_HEADROOM_RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
status=json.loads((R/'HEADROOM_STATUS.json').read_text());status.update(
    hardware_DMA='MEASURED finite transport latency; adoption deferred',hardware_CPU_headroom='MEASURED synthetic work; deadline-qualified capacity NOT ESTABLISHED',
    CPU_headroom='NOT ESTABLISHED (all-frame deadline qualified maximum)',hardware_30fps_stability='MEASURED / TARGET NOT MET',
    RAM_Flash_protection='PASS (8 physical full readbacks, filesystem equal, protected hashes unchanged)',
    hardware_operations='authorized campaign; 8 RP2040 firmware writes, FPGA operations 0',release_ready=False,release='NOT READY',
    latest_hardware_report='HARDWARE_HEADROOM_RESULT.md',
    limits=['one run per variant; no randomized replication/PVT',
            'no physical PIO/DMA waveform or hardware framebuffer byte oracle',
            'frozen scratch pattern all-zero; changing-pattern physical DMA test deferred',
            'no independent underrun or BUSY-overwrite hardware counter',
            'deadline-qualified maximum CPU headroom not established',
            'strict vblank-pair/present-completion scheduler integration deferred',
            'no runtime stack watermark'])
(R/'HEADROOM_STATUS.json').write_text(json.dumps(status,indent=2))
for name in ('CPU_HEADROOM_REPORT.md','DMA_DESIGN.md','DMA_BENCHMARK.md','SCHEDULER_REPORT.md','RENDER_OPTIMIZATION.md','HEADROOM_REPORT.md','HARDWARE_TEST_PLAN.md'):
    file=R/name;text=file.read_text(encoding='utf-8')
    banner='> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。\n\n'
    if not text.startswith(banner):file.write_text(banner+text,encoding='utf-8')
file=R/'README.md';text=file.read_text(encoding='utf-8');banner='> 最新の8構成実機比較：[実機結果](HARDWARE_HEADROOM_RESULT.md)。全8周完走・音声/Flash照合、30fps目標は未達、Release NOT READY。\n\n'
if not text.startswith(banner):file.write_text(banner+text,encoding='utf-8')
print('PASS: 8 physical runs, full Flash ledger, final reports; release_ready=false')
