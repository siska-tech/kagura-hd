# 実機結果 — BEYOND 16 COLORS / 2026-11-06

> この報告は実機評価時点の記録です。使用したFPGA Bitstreamは、その後 [PCM2 QSPI最終版](../../releases/pcm2-qspi-final/README.md)として選定しました。本文の性能目標未達・未検証項目・当時の機器状態は記録として保持しています。


**有限ベンチと150秒本編の全8シーンを実機で完走。STOP rc=0。30fps目標は未達、Release NOT READY / `release_ready=false`。**

RP2040/Pico + Tang Nano 9K、固定PCM2 ABI 1.4、nominal PIO QSPI5MHz、seed0xb1616、stars64／BLIT32、USBとUARTログ有効。FPGA RTL／Controller／PHY／SDC／CST／PLL／Host ABI／FPGA Flashは変更0。既存STA合格候補をFPGA SRAMへ1回投入した。

- [実機HDMI動画・本編150秒](../../build/beyond16-hardware-2026-11-06/beyond16-hardware.mp4) — 1280×720/60Hz capture。実更新fpsとは別。
- [実機8シーン一覧](evidence/hardware/contact-sheet.png)
- [フルHDMI原記録](../../build/beyond16-hardware-2026-11-06/demo-hdmi.mkv)、[生USBログ](evidence/hardware/demo-usb.log)
- [実測JSON](evidence/hardware/performance.json)、[音声解析](evidence/hardware/audio.json)、[有限ベンチ全行](evidence/hardware/bench-raw.json)

## 完走・速度

gから停止まで159.625秒。最初のBGM開始まで約9.65秒（USBログからの推定、事前展開を含む）。本編PCMの実音は150.01秒。初期frameは個別FRAMEログ対象外。以下のfpsは各sceneの論理秒数で、記録された実PRESENT更新数を除算した値。最初の1frameと境界の半端frameには約1frameの偏りがある。

|Scene|実更新fps|平均frame ms|最悪frame ms|描画commands|BLIT pixels|
|---|---:|---:|---:|---:|---:|
|BOOT|14.50|59.71|149.79|17,124|1,053,696|
|HYPERSPACE|15.35|56.69|142.63|32,260|0|
|RASTER WAVES|8.35|110.45|225.88|40,563|3,527,040|
|PLASMA ENGINE|11.65|76.55|175.78|31,730|25,767,936|
|ROTOZOOM|6.52|143.18|225.76|52,669|1,133,568|
|BLIT STORM|14.40|60.70|125.62|43,227|10,266,624|
|VECTOR WORLD|3.90|246.59|358.84|44,459|147,840|
|FINALE|21.00|26.17|509.06|7,790|845,568|

全体のframe呼出し平均79.53ms、最悪509.063ms。本編の通信rateはstartupを除いたhost 1038–149556msの148.518秒で計算。

|指標|実測|
|---|---:|
|Host transaction/s|14742.34|
|wire bytes/s|80593.57|
|平均transaction時間|51.907µs|
|最長transaction時間（startup含む累積max）|336µs|
|transaction累積時間（上記window）|113.651秒|
|描画command/s（最終counter÷150秒）|1798.81|
|BLIT pixels/s（最終counter÷150秒）|284948.48|
|Host timeout|0|
|GPU command API error|0観測（正常STOP）|
|PCM STATUS fault|0観測|

command counterは描画・palette・PRESENTを数え、PCM COMMITなどは含まない。全GPU opcode数の独立ハードウェアcounterではない。transaction累積時間はHost callback内の時間で、GPU描画時間ではない。

Host callback内にwindow時間の約76.5%を費やしたこと、FILL/BLITが1件約0.7msであること、sceneのcommand数増加に伴いfpsが下がることが今回の観測。PIO、GPIO切替、GPU受付、PSRAM内部を別々に計った値ではない。UART/USB printfも有効で、frame時間の外側のログ負荷は実更新間隔へ影響し得る。

同条件の実機Before/Afterは**未実行**。今回書き込んだのは最適化版だけ。PCでの11.18% transaction削減と今回の物理値を混ぜて高速化倍率を作らない。前作と今回の平均transaction時間はアクセス構成が違うため、単純比較でドライバ改善効果としない。

## 有限ベンチ

|項目|PCM停止中|PCM0再生中|試行数/phase|
|---|---:|---:|---:|
|FENCE submit|439.34µs|438.22µs|64|
|FENCE completion確認|212.38µs|211.19µs|64|
|FILL 32×32|679.88µs|678.88µs|8|
|BLIT 32×32|688.38µs|692.62µs|8|
|PRESENT|6939.75µs|8194.75µs|8|

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
