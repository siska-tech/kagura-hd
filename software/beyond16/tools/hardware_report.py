from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];E=R/'evidence/hardware';p=json.loads((E/'performance.json').read_text());a=json.loads((E/'audio.json').read_text());f=json.loads((E/'flash-write-verified.json').read_text());rate=p['runtime_rate_window']
s='''# 実機結果 — BEYOND 16 COLORS / 2026-11-06

**有限ベンチと150秒本編の全8シーンを実機で完走。STOP rc=0。30fps目標は未達、Release NOT READY / `release_ready=false`。**

RP2040/Pico + Tang Nano 9K、固定PCM2 ABI 1.4、nominal PIO QSPI5MHz、seed0xb1616、stars64／BLIT32、USBとUARTログ有効。FPGA RTL／Controller／PHY／SDC／CST／PLL／Host ABI／FPGA Flashは変更0。既存STA合格候補をFPGA SRAMへ1回投入した。

- [実機HDMI動画・本編150秒](../../build/beyond16-hardware-2026-11-06/beyond16-hardware.mp4) — 1280×720/60Hz capture。実更新fpsとは別。
- [実機8シーン一覧](evidence/hardware/contact-sheet.png)
- [フルHDMI原記録](../../build/beyond16-hardware-2026-11-06/demo-hdmi.mkv)、[生USBログ](evidence/hardware/demo-usb.log)
- [実測JSON](evidence/hardware/performance.json)、[音声解析](evidence/hardware/audio.json)、[有限ベンチ全行](evidence/hardware/bench-raw.json)

## 完走・速度

'''
s+=f'gから停止まで{p["g_to_stop_s"]:.3f}秒。最初のBGM開始まで約{p["estimated_audio_epoch_from_g_s"]:.2f}秒（USBログからの推定、事前展開を含む）。本編PCMの実音は{a["audible_span_s"]:.2f}秒。初期frameは個別FRAMEログ対象外。以下のfpsは各sceneの論理秒数で、記録された実PRESENT更新数を除算した値。最初の1frameと境界の半端frameには約1frameの偏りがある。\n\n'
s+='|Scene|実更新fps|平均frame ms|最悪frame ms|描画commands|BLIT pixels|\n|---|---:|---:|---:|---:|---:|\n'
for x in p['scenes']:s+=f'|{x["name"]}|{x["effective_fps"]:.2f}|{x["mean_frame_ms"]:.2f}|{x["worst_frame_ms"]:.2f}|{x["drawing_commands"]:,}|{x["blit_pixels"]:,}|\n'
s+=f'\n全体のframe呼出し平均{p["mean_frame_ms"]:.2f}ms、最悪{p["worst_frame_ms"]:.3f}ms。本編の通信rateはstartupを除いたhost {rate["first_ms"]}–{rate["last_ms"]}msの{rate["seconds"]:.3f}秒で計算。\n\n|指標|実測|\n|---|---:|\n|Host transaction/s|{rate["transactions_per_s"]:.2f}|\n|wire bytes/s|{rate["wire_bytes_per_s"]:.2f}|\n|平均transaction時間|{rate["transaction_average_us"]:.3f}µs|\n|最長transaction時間（startup含む累積max）|{p["maximum_transaction_us"]}µs|\n|transaction累積時間（上記window）|{rate["cumulative_transaction_us"]/1e6:.3f}秒|\n|描画command/s（最終counter÷150秒）|{p["drawing_commands_final_counter"]/150:.2f}|\n|BLIT pixels/s（最終counter÷150秒）|{p["blit_pixels_final_counter"]/150:.2f}|\n|Host timeout|0|\n|GPU command API error|0観測（正常STOP）|\n|PCM STATUS fault|0観測|\n'
s+='''
command counterは描画・palette・PRESENTを数え、PCM COMMITなどは含まない。全GPU opcode数の独立ハードウェアcounterではない。transaction累積時間はHost callback内の時間で、GPU描画時間ではない。

Host callback内にwindow時間の約76.5%を費やしたこと、FILL/BLITが1件約0.7msであること、sceneのcommand数増加に伴いfpsが下がることが今回の観測。PIO、GPIO切替、GPU受付、PSRAM内部を別々に計った値ではない。UART/USB printfも有効で、frame時間の外側のログ負荷は実更新間隔へ影響し得る。

同条件の実機Before/Afterは**未実行**。今回書き込んだのは最適化版だけ。PCでの11.18% transaction削減と今回の物理値を混ぜて高速化倍率を作らない。前作と今回の平均transaction時間はアクセス構成が違うため、単純比較でドライバ改善効果としない。

## 有限ベンチ

|項目|PCM停止中|PCM0再生中|試行数/phase|
|---|---:|---:|---:|
'''
for op,label,field in [('fence','FENCE submit','issue_us'),('fence','FENCE completion確認','completion_us'),('fill','FILL 32×32','us'),('blit','BLIT 32×32','us'),('present','PRESENT','us')]:
 x=[z for z in p['bench'] if z['op']==op];s+=f'|{label}|{x[0][field]["mean"]:.2f}µs|{x[1][field]["mean"]:.2f}µs|{x[0]["samples"]}|\n'
s+='''
1/2/4/8/16/64/512Bのraw CSR write/readとscratch PSRAM write/readは全てrc=0。512B raw READはABI上限256Bにより2transaction。raw WRITE1Bは45/47µs、WRITE512Bは2582/2588µsを観測。ただし各長さ各phase1回だけで、warm-up・割込み等を分離していない。これだけで固定費を一意に決定しない。PSRAM write512Bは7470/7502µs、read512Bは6895/6853µs。readbackは全長一致。PRESENTのPCM再生中最大値は16,941µsで、vblank位相を含むためPCMによる遅延と断定しない。

## 音声

HDMIの48kHz/16bit stereoを物理capture。全sceneのBGM 2秒区間と元PCMの正規化相関は0.9947–0.9976。150.01秒の実音区間に10ms RMS窓の低音量欠落は検出しなかった。PCM STATUS fault=0。

独立したunderrun counterは公開されていないため「全sampleのunderrun=0を証明」とはしない。1秒pollingとcaptureによる有限1周の観測であり、全PVT・長時間試験や聴感評価は未実行。PCM1の8境界では既知stingerとの相関ピークも観測したが、BGMを完全分離した評価ではない。

captureのサンプル時計を基準にした元BGM位相差は140秒で約2.31ms。FPGA音声clock、capture resampling、RP2040時計を分離したppm測定ではない。scene07のstingerは目標境界より約245ms遅れ、描画負荷でscene検知自体が次frameまで遅れる影響が見える。累積フレーム回数によるシーン延長は起きず、150秒で終了した。

## 映像と検証限界

実機8シーンをPNGへ抽出して目視確認。既存page BLIT、波打つロゴ、plasma合成、checker回転、BLIT Storm、立方体／八面体／トンネル、最終コピーの表示を確認。静的header/source帯の色校正付きRGB一致率は約96.8–97.3%。YUV/圧縮captureの形状確認であり、Framebuffer readback CRCではない。実機全画素CRCは未実施。

星64/128/256、object8/16/32/64/128の実機sweepは未実行。今回の64星・32objectsを安定上限とは宣言しない。30fps／軽量60fps、最悪frame抑制、演出完成度は改善課題。VECTORはFILL線分のcommand数、ROTOはセルFILL数が大きいため、次のC側最適化優先対象。RTL変更を解決策にしない。

## 書込み・復旧可能性・現在状態

現在Flashの全2MiBを新規保存し、readback verifyとSHA一致を確認してから投入した。バックアップSHAは`7ea52cb9898e6dbd3b44eb1b80861b28a3fd8026d858973162e05f5df32ee596`、以前のC版保存像と一致。元システムのSHA `713407...`のバックアップもそのまま保持。

RP2040 bin SHAは`c66308e09ad46a2104d3924d0a7913b98937b05e7408ade4b523940a6cee200b`。書込み後の全Flash SHAは`29001ff651a227cf2d4d8b2286c4dbc67af385ede3d205e1f124518b4295aa4a`。firmware 316,292B、erase終端0x1004e000、filesystem開始0x100a0000。erase終端以降とfilesystem全域は投入前とbyte一致。FPGA Flash書込み0、固定候補SRAM投入1回。

現在はBEYOND firmwareのまま、正常STOP後のフィナーレ画面、音声停止、QSPI deinit済み。自動再生を繰り返していない。前作へのFlash復旧は行っていない。直前backupと復旧手順を保持している。再起動後はUSB g/b入力待ちとなる。

picotool backupの最初の呼出しは引数順序の解析で拒否され、device転送前に終了した。既に確認済みの正常STOPを繰り返さず、backup読み取り段階だけを修正して実行した。実機異常やuncertain transactionの自動再送はない。

判定：C/PC/oracle/PCM生成PASS。GPU命令互換はこの実機runでも確認。実機全scene完走PASS、実機音声は有限1周の観測PASS、実機30fps性能目標FAIL。Release NOT READY。
'''
(R/'HARDWARE_RESULT.md').write_text(s,encoding='utf-8')
