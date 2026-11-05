from pathlib import Path
import subprocess,sys,json,statistics,re
r=Path.cwd();app=r/'software/beyond16';base=r/'build/beyond16-host-ab-2026-11-06';reports={}
source=(app/'tools/hardware_optimized_analyze.py').read_text(encoding='utf-8')
for mode in ('OFF','ON'):
 s=source.replace("repo/'build/beyond16-hardware-optimized-2026-11-06'",f"repo/'build/beyond16-host-ab-2026-11-06/{mode}'").replace("R/'evidence/hardware-optimized'",f"R/'evidence/host-ab-{mode}'")
 script=app/f'tools/_analyze_host_{mode}.py';script.write_text(s,encoding='utf-8');subprocess.run([sys.executable,str(script)],check=True);script.unlink()
 reports[mode]=json.loads((app/f'evidence/host-ab-{mode}/performance.json').read_text())
lines=['# Host固定費 実機A/B','', '同じ-O2・低解像度VECTOR・ログ・区間計測条件で、FAST OFF/ONを各1周。各150秒、各有限ベンチ。単発測定であり分散・PVTの保証なし。','', '|Scene|OFF fps|ON fps|ON平均call ms|','|---|---:|---:|---:|']
for a,b in zip(reports['OFF']['scenes'],reports['ON']['scenes']):lines.append(f"|{a['name']}|{a['effective_fps']:.2f}|{b['effective_fps']:.2f}|{b['mean_frame_ms']:.2f}|")
for mode in ('OFF','ON'):
 p=reports[mode];lines+=['',f"{mode}: timeout={p['timeouts']}, PCM status fault={p['pcm_status_faults']}, 平均transaction={p['runtime_rate_window']['transaction_average_us']:.3f}us, 全体fps={p['runtime_rate_window']['actual_fps']:.3f}, 最悪call={p['worst_frame_ms']:.3f}ms。"]
lines+=['','Release NOT READY。最後はON firmwareで音声停止、フィナーレ保持。両投入で全Flash backupと読戻しを実行し、filesystemとerase終端以降一致。FPGA Flash変更0。RTL/clock/ABI変更0。','', '旧未最適化版との比較はコンパイラ設定とVECTOR画質も異なるため、Host変更の効果判定には上記OFF/ONを使用する。詳細audio／bench／scene PNGはevidence/host-ab-OFF, host-ab-ON。原captureと復旧像はbuild/beyond16-host-ab-2026-11-06。']
(app/'HARDWARE_HOST_AB_RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
