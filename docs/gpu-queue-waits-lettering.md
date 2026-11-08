# Queue待ち時間の切り分けとFINALE文字展開 — 2026-11-07

後続の[Queue完了読出しburst](gpu-completion-burst.md)では、独立したmetadata読出しを省く候補を実機比較した。
以下は文字結合と待ち時間切り分けの時点の記録。

[前回の深さ8実機比較](gpu-queue-demo-hardware.md)では、Queue使用で小幅な改善を観測したが、
FINALEの約150 msの描画停止が残った。今回は同じ暫定承認bitstreamを使い、
Queueホストのまま待ち時間の内訳を測り、文字展開の画素等価な命令削減を比較する。

## 計測

`B16_QUEUE_METRICS=1` で、各分類の最初と以降64回に1回を測る。
通常のprofileはOFF。起動時の素材展開と初回frame後に計測値をリセットし、本編を対象とする。
全件のcall数は保持し、サンプル数は `ceil(calls/64)` と照合する。

Queue回収を次の4分類に分け、サンプルごとに時間を3区間へ分けた。

| reason | 回収契機 |
|---:|---|
| 0 | ソフトウェアの未回収数が8件に達した後、次の投入前 |
| 1 | COPYの直前 |
| 2 | PRESENTの直前 |
| 3 | 公開raw submit／PCMなどその他の同期操作前 |

- `poll_us`: kfb_wait開始→最初にDONEを観測。status読出しとGPU待ちを含む。
- `metadata_us`: DONE観測→完了tag/error、sticky検査後。ホストIOを含む。
- `ack_us`: ACK書込み開始→戻り。ホストのACK transaction時間。

別にopcodeごとの同期命令を同じ頻度で測り、先行Queue回収時間と、
descriptor投入→完了ACKの時間を分ける。引数検証やCOPYのCAPS参照はこの区間外。
COPY前に未回収命令があったcall数も全件で数える。
このopcode集計はSDKのexecute経路が対象で、公開raw submit経由のPCM COMMITは含めない。

これらはCPUから観測した区間で、IRQと計測自身の時間を含む。
ハードウェアがDONEを出してからホストが回収を始めるまでの保持時間は測れない。
FPGA内部のACK待ち停止サイクルや、純粋なGPU COPY時間とは扱わない。
周期サンプリングは無作為抽出ではなく、平均を全実行時間へ単純換算しない。

## 文字展開候補

`B16_MERGE_LETTERING=1` で、同一glyph・同色の横spanを縦方向へ結合する。
captionで既に用いている手法を、FINALEのscale 2/3文字へ適用した。
glyphがdot描画範囲の境界にかかる場合は元の行span処理を使い、
「範囲外の矩形を丸ごと拒否する」既存仕様も維持する。
dirty map、文字・palette・描画位置、表示タイミングの条件は変更しない。

PCでは、3 seed×15時刻で両115,200-byte framebuffer、active palette、表示pageが一致した。
143秒以降の両pageへの初回展開後は、描画命令が合計1,118件減少した。
機能モデルでの照合であり、実機画面の全byte CRCではない。

Queue制御はdescriptor packed有無×計測有無の4構成で、正常／device error／tag不一致を試験した。
満杯＋DONE、tag周回、順序ACK、バリア、再送禁止に加え、計測分類とリセットもPASSした。
計測有効の両ELFはBSS 175,240 byteで同じ。文字結合によりtextは277,340→277,652 byte（+312 byte）。
計測なしの前回Queue版からはBSSが352 byte増えている。実行時stack watermarkは測定していない。

## 再現

```powershell
./software/beyond16/tools/build_rp2040.ps1 -Profile 0 -GpuQueue 8 -QueueMetrics -BuildDirectory "$PWD/build/queue-wait-20261107/fw-baseline"
./software/beyond16/tools/build_rp2040.ps1 -Profile 0 -GpuQueue 8 -QueueMetrics -MergeLettering -BuildDirectory "$PWD/build/queue-wait-20261107/fw-merged"
```

実機は同じdepth8 QSPI bitstream（SHA-256 `5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77`）。
RP2040 120 MHz、CPU＋PIO、profile OFF、relative33、seed0xb1616、stars64／objects32。
計測有効の従来文字→結合文字を固定順序で各150秒再生する。
FPGAはSRAM投入のみ。Setup +0.050 nsという暫定承認の条件と、製品既定深さ1を維持する。

## 実機結果

両版とも全8シーン完走、STOP rc=0、timeout=0、PCM STATUS fault=0。
従来文字318,066件／結合文字317,431件のQueue投入を全件回収し、最大未回収8、終了時残件0、エラー0。
全件数には起動時処理を含む。計測カウンタは本編だけを対象にしている。
動作時刻によって実際に描くframe数・幾何が変わるため、周回全体の件数差をそのまま文字削減数にはしない。

| 指標 | 従来文字＋計測 | 結合文字＋同じ計測 |
|---|---:|---:|
| 全体 実PRESENT fps | 29.430 | 29.473 |
| p95 PRESENT間隔 ms | 49.996 | 49.997 |
| 最悪PRESENT間隔 ms | 150.001 | 83.346 |
| 最悪描画call ms | 148.982 | 82.330 |
| 最初の文字展開call ms | 148.982 | 82.319 |
| 次pageの文字展開call ms | 148.975 | 81.410 |
| FINALE 実PRESENT fps | 29.548 | 30.000 |
| VECTOR WORLD 実PRESENT fps | 24.983 | 25.054 |

最悪callは約44.7%、最悪PRESENT間隔は約44.4%短縮した。
結合版の最悪callはFINALEではなく、139.851秒のVECTOR WORLD側へ移った。
文字以外の描画は変更せず、VECTORなどの小差を文字結合による高速化とは判定しない。
全体fpsは約0.15%増にとどまり、p95もほぼ同じで、全scene安定30 fpsには至っていない。

前回の無計測Queue版は29.480 fps、今回の従来文字＋計測版は29.430 fpsだった。
同時の計測有無A/Bではなく、単発・固定順序比較なので、一定の計測補正や有意差とは扱わない。

## COPY／完了プロトコルの観測

従来文字版の本編で、COPYは122,383回、その直前に未回収Queueがあったのは3,741回（3.06%）。
結合版も122,688回中3,744回（3.05%）で、似た割合だった。

| CPU観測のサンプル平均 | 従来文字 µs | 結合文字 µs |
|---|---:|---:|
| COPY前の先行Queue回収区間（空の場合も含む） | 13.70 | 16.19 |
| COPY投入→完了ACK（ホストIOを含む） | 163.59 | 163.21 |
| PRESENT前の先行Queue回収区間（空の場合も含む） | 167.94 | 157.91 |
| PRESENT投入→完了ACK（vblank／ホストIOを含む） | 9,942.74 | 10,394.03 |
| 未回収8件からの回収: DONEポーリング | 21.53 | 21.43 |
| 同: 完了tag/error・stickyの読出し | 33.60 | 33.63 |
| 同: ACK書込み | 12.77 | 12.79 |

COPY命令のサンプル数は1,913／1,917、PRESENTは69／70。
満杯契機のQueue回収は4,460／4,450件をサンプルし、全4分類のサンプル数を `ceil(calls/64)` と照合した。
COPY前にQueueを空にするケースだけでは、COPY全体の待ちを説明できない。
一方、各回収で完了情報とACKに合計約46 µsのホスト処理が観測された。
次の検討対象は完了読出しtransactionの削減とACKによる実行直列化だが、
この計測だけでFPGA内部の停止時間や改善可能量を断定しない。

## 映像・音声・保持

[従来文字の全8シーン](evidence/gpu-queue-waits/baseline/contact-sheet.png)、
[結合文字の全8シーン](evidence/gpu-queue-waits/merged/contact-sheet.png)を保存し、明らかな表示崩れは見られなかった。
静止サンプル確認であり、全実機framebufferのbyte照合ではない。
両版とも48kHz/2ch音声spanは150.01秒、左右の低RMS欠落10 ms blockは0、capture buffer full記録0。
8箇所の既知BGM照合の最低相関は従来0.994724、結合0.994867。
独立underrunカウンタや全sampleの完全性を保証する試験ではない。

各RP2040書込み前に新規2 MiBバックアップを2回取得して一致確認し、書込み後・試験後を全量照合した。
消去終端以降、filesystem `0x100a0000` 以降、公開validated画像・凍結済み8構成firmwareの保持はPASS。
今回のRP2040書込み2回、FPGA SRAM投入1回、FPGA Flash書込み0回。過去の証跡は上書きしない。

- 従来文字firmware: `2d94e29e23a0f8f5a886cc3525ef07415d3f76b39aa87403c7c762486d2b9128`
- 結合文字firmware: `9ad926d51c7974e02d7a53dbd03e92e3e69f9c3cdbb9e4cf9049dbdc8816c80c`
- 今回開始前の復旧像: `build/queue-wait-20261107/hardware/baseline/before.bin`、SHA-256 `d6737657592f7694049ee9758682fadaf05360c93f7505db1bbeb134c5dd26cf`

実機は結合文字＋計測有効のQueue firmwareを保持し、PCM停止、USB明示開始gateで待機している。
FPGA SRAM構成は電源断で失われるため、再実行前に同じ承認bitstreamを再投入する。
文字結合と計測はいずれも明示的なビルドオプションとして残し、通常の既定値は無効。

## 証跡

[比較JSON](evidence/gpu-queue-waits/comparison.json)、[実行ledger](evidence/gpu-queue-waits/campaign.json)、
[投入ソースhash](evidence/gpu-queue-waits/source-sha256.json)。
[PC画素比較](evidence/gpu-queue-waits/lettering-equivalence.json)、
[ホスト制御／通常SDK回帰](evidence/gpu-queue-waits/host-tests.json)、
[ビルド設定・追加入力hash](evidence/gpu-queue-waits/firmware-inputs.json)も保存した。
USB原ログにはQRET／QSYNCの全集計とframe時刻を保持した。
原動画・WAV・退避像は `build/queue-wait-20261107/hardware/`。
PC画素比較は `bash software/beyond16/tools/test_lettering.sh`、Queue制御試験は
`KAGURA_QUEUE_TEST_DIR=build/queue-wait-tests bash software/beyond16/tools/test_gpu_queue.sh` で再現する。
通常SDK15件×2設定と音声CSR10件もPASSした。

次の具体候補は、statusと完了tag/errorの連続読出しによるtransaction削減。
DONE未成立時の余分な読出しと、成立時のtag安定性を比較検証し、
sticky error確認や不確定命令の再送禁止を維持して評価する。
