from pathlib import Path
import json,statistics,re
r=Path('software/beyond16');ev=r/'evidence/hardware-optimized';old=json.loads((r/'evidence/hardware/performance.json').read_text());new=json.loads((ev/'performance.json').read_text());audio=json.loads((ev/'audio.json').read_text());state=json.loads((ev/'demo-result.json').read_text());frames=[]
for line in (ev/'demo-usb.log').read_text().splitlines():
 if line.startswith('FRAME '):frames.append({k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',line)})
rows=[]
for a,b in zip(old['scenes'],new['scenes']):
 fs=[f for f in frames if f['scene']==b['scene']];gaps=[(y['ms']+y['us']/1000)-(x['ms']+x['us']/1000) for x,y in zip(fs,fs[1:])];sg=sorted(gaps)
 rows.append({'name':b['name'],'old_fps':a['effective_fps'],'new_fps':b['effective_fps'],'mean_ms':b['mean_frame_ms'],'worst_ms':b['worst_frame_ms'],'completion_interval_p95_ms':sg[int((len(sg)-1)*.95)],'interval_over_33_34_fraction':sum(x>33.34 for x in gaps)/len(gaps)})
bus=state['bus'];dt=(bus[-1]['ms']-bus[0]['ms'])/1000;parts={k:(bus[-1][k]-bus[0][k])/1e6 for k in ('begin_us','transfer_us','end_us')}
report={'scenes':rows,'bus_window_s':dt,'bus_cumulative_s':parts,'scope':'one old and one new run; logging and instrumentation differ','release_ready':False}
(ev/'comparison.json').write_text(json.dumps(report,indent=2))
lines=['# 改善版 実機結果','', '有限ベンチと150秒全8scene正常完走。前回とログ／通信計測設定が異なるため、厳密な同条件Before/Afterではない。改善版の観測値として報告する。','', '|Scene|前回fps|改善版fps|平均frame ms|最悪frame ms|完了間隔p95 ms|','|---|---:|---:|---:|---:|---:|']
for x in rows:lines.append(f"|{x['name']}|{x['old_fps']:.2f}|{x['new_fps']:.2f}|{x['mean_ms']:.2f}|{x['worst_ms']:.2f}|{x['completion_interval_p95_ms']:.2f}|")
lines+=['',f"timeout={new['timeouts']}、PCM status fault={new['pcm_status_faults']}。音声実音{audio['audible_span_s']:.2f}s、10ms RMS低音量欠落の最長{audio['longest_observed_low_rms_ms']}ms。独立underrun counterはなく全sampleの無欠落証明ではない。",'',f'通信区間 window={dt:.3f}s、累積秒={parts}。transferはFIFO処理と時刻確認を含み、GPU内部時間ではない。計測負荷込み。','', '現在は改善版firmwareのフィナーレ保持、音声停止。全Flashバックアップと読戻し比較でfilesystem／erase終端以降の一致を確認。FPGA Flash書込み0、固定候補SRAM投入のみ。RTL変更0。release_ready=false。','', '証跡：evidence/hardware-optimized/、原HDMI動画とFlash backup：build/beyond16-hardware-optimized-2026-11-06/。前回記録は保持。']
(r/'HARDWARE_OPTIMIZED_RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps(report,indent=2));print('audio',audio['audible_span_s'],audio['longest_observed_low_rms_ms'])
