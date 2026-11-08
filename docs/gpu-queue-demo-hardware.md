# 深さ8 Queueメガデモ実機比較 — 2026-11-07

後続の[待ち時間切り分け／FINALE文字結合](gpu-queue-waits-lettering.md)では、
画素等価な命令削減により最悪描画callを148.982→82.330 msへ短縮した。
以下は最初の直列／Queue比較時点の記録。

ユーザーの暫定承認に基づき、深さ8 FPGAでBEYOND 16 COLORSを直列ホスト／Queueホスト各150秒再生した。
両版とも全8シーン完走、STOP rc=0、timeout=0、PCM STATUS fault=0。
Queue版は320,062件を投入・同数回収し、最大未回収8件、終了時残件0、エラー0だった。
**この有限負荷試験は正常完了。安定30 fpsと正式リリースの判定は保留する。**

## 構成と試験方法

- FPGA: Tang Nano 9K / GW1NR-9C、ID `0x1100481B`。
- 深さ8、QSPI、8分割payload、62-bitカーソルmailbox、packet-first分割有効、音声credits保持無効。
- place=4 / route=2、Setup +0.050 ns / Hold +0.470 ns、違反0件。
  従来のSetup余裕+0.10 ns基準は未達のまま。暫定承認で実機へ進めた。
- bitstream SHA-256: `5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77`。
- FPGA SRAMへ1回投入、FPGA Flash書込み0回。クロック／配線／PSRAM設定は変更しない。
- RP2040 `E663A837CB73512D`、120 MHz、既存CPU＋PIO QSPI、profile OFF、relative33 scheduler。
- seed `0xb1616`、stars64／objects32、同じC描画・音楽・150秒タイムライン。
- 同じ深さ8 FPGA上で、直列ホスト→Queueホストの固定順序で各1周。深さ1 FPGAとの同時比較ではない。
- UGREEN HDMIで1280×720/60Hz映像と48kHz/2ch音声を実録画。capture buffer full記録0。

既存SDKは1命令ずつ完了待ちするため、実験用 `B16_GPU_QUEUE=8` を追加した。
FILL／PALETTEのみ受付後に戻り、ソフトウェアの未回収tagを最大8件保持する。
満杯なら最古の完了を回収し、COPY／PRESENT／READ／WRITE／FENCE／PCM操作の前には全件回収する。
BUSYは受付容量を示すため、完了確認はDONEを独立に検査する。
tag不一致はACKせず停止し、IOやdeviceエラーはラッチして再送しない。
既存SDKの既定動作は変更せず、この1デバイス・1所有者の実験だけで有効にした。
同条件のELFでBSSは174,836→174,888 byte（+52 byte）、textは275,908→276,380 byteだった。

開始前に8件の色違いFILLを送り、FENCE後の32-byte読戻しを全比較した。両版ともPASS。
最大未回収8はソフトウェアの計数であり、独立したハードウェアFIFO占有率カウンタではない。

## 性能

実PRESENT fpsは連続した完了時刻から `(N-1)/経過時間` で計算した。
CPUがDONE/tag/error/ACKまで観測した時刻であり、HDMI走査時刻ではない。

| 指標 | 直列ホスト | Queueホスト |
|---|---:|---:|
| 全体 実PRESENT fps | 29.366 | 29.480 |
| PRESENT間隔中央値 ms | 33.334 | 33.334 |
| p95間隔 ms | 49.998 | 49.995 |
| 最悪間隔 ms | 150.012 | 166.663 |
| 最悪描画call ms | 148.999 | 149.591 |
| 記録deadline miss | 222 | 189 |
| transaction/s | 42,126.5 | 41,289.0 |
| wire byte/s | 204,189.8 | 201,105.1 |

| Scene | 直列 fps | Queue fps |
|---|---:|---:|
| BOOT | 30.353 | 30.353 |
| HYPERSPACE | 30.326 | 30.326 |
| RASTER WAVES | 29.975 | 29.975 |
| PLASMA ENGINE | 30.100 | 30.100 |
| ROTOZOOM | 30.120 | 30.160 |
| BLIT STORM | 30.320 | 30.320 |
| VECTOR WORLD | 24.532 | 25.342 |
| FINALE | 29.548 | 29.546 |

全体+0.386%、VECTOR WORLD+3.304%、transaction/sは約1.99%減。
単発の固定順比較で、反復統計上の有意差や最大性能を証明する数値ではない。
p95はほぼ同じで最悪間隔は悪化しており、Queue追加だけで安定30 fpsや長時間停止を解消したとは判定しない。
COPYとPRESENTは同期バリアのまま。ACKまで次のGPU実行が止まる仕様も残っているため、
深さ8を8命令並列実行と解釈しない。CPU使用率や最大割当可能余力も測定していない。

## 映像・音声

両版の全8シーン画像を確認し、明らかな画面崩れは見られなかった。
[直列版一覧](evidence/gpu-queue-demo/serial/contact-sheet.png)、
[Queue版一覧](evidence/gpu-queue-demo/queued/contact-sheet.png)。
静止サンプルの確認であり、全フレームのbyte CRC照合やscanout欠落カウンタの検証ではない。

両版とも実音声spanは150.00秒。左右各chの10 ms窓で、RMS<20となる欠落blockは0。
各sceneのstinger後の2秒を既知BGMと照合し、相関の最低値は直列0.994764、Queue0.994514。
これは物理HDMI音声の有限観測であり、独立underrunカウンタや全sample照合ではない。

## 書込み・保持・終了状態

RP2040は各書込み前に新規2 MiBバックアップを2回取得して一致確認し、
書込み後と試験後も全量を照合した。消去終端以降とfilesystem `0x100a0000` 以降の保持はPASS。
公開済みvalidated画像と凍結済み8構成firmwareのhashも不変だった。
RP2040 firmwareの書込みは2回、FPGA SRAM投入1回、FPGA Flash書込み0回。

| 対象 | SHA-256 |
|---|---|
| 直列firmware | `a3a2044a0cdd8b78a0698451a061c6a58b834ca74a78c7aae2b3484102ac796e` |
| Queue firmware | `79042cca5328e9b293a53f251091f1aeb6b1f35adab180db03aa3e6a47e33387` |
| 元の全Flash復旧像 | `0298d14b33e86f470eaa8987d4654e198c9de493d981aec542aa9e03a2226c86` |

実機は深さ8 SRAM FPGAとQueue firmwareを保持し、PCM停止、USBの明示的開始gateで待機している。
FPGA SRAM構成は電源断で失われるため、再実行前には同じ承認bitstreamを再投入する。
元のRP2040復旧像は `build/queue-demo-20261107/hardware/serial/before.bin`。
既存のバックアップは上書きしていない。製品既定のQueue深さ1とrelease_ready=falseは維持する。

## 証跡と再現

- [集計JSON](evidence/gpu-queue-demo/comparison.json)、[実行ledger](evidence/gpu-queue-demo/campaign.json)、[入力hash](evidence/gpu-queue-demo/source-sha256.json)。
- [追加のfirmware入力hash](evidence/gpu-queue-demo/firmware-inputs.json)、[ホスト試験記録](evidence/gpu-queue-demo/host-tests.json)。
- USB原ログ・tag計数・PRESENT解析・Flash照合は同ディレクトリのserial／queued以下。
- 原HDMI録画・WAV・全Flash退避像は `build/queue-demo-20261107/hardware/` 以下。
- ホスト制御試験: `bash software/beyond16/tools/test_gpu_queue.sh`。
  descriptor packed有無それぞれで満杯＋DONE、tag周回、バリア、異常時再送禁止をPASS。
  通常SDKは15件×2設定、音声CSRは10件PASS。
- offline解析: `python3.12.exe software/beyond16/tools/analyze_queue_demo.py`。
- 実機runner `hardware_queue_demo.py` は新規出力先・書込み前hashを固定し、開始済み試験を再送しない。
  再度の実機試験は、新たな出力先・現在のFlash確認・bitstream照合を準備して行う。

次の性能改善では、ACK待ちによる実行停止とCOPYバリアの影響を分けて測る。
またFINALEの文字展開停止をQueueだけで解消できるとは仮定しない。
