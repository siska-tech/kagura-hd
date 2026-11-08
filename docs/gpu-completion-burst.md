# Queue完了読出しのtransaction削減 — 2026-11-07

後続の[同一firmwareによるA/B/A/B反復・100 ms間隔の照合](gpu-completion-abab.md)と、
[sticky確認の短縮候補・ACK待機観測設計](gpu-ack-observation-design.md)を追加した。

[前回の切り分け](gpu-queue-waits-lettering.md)で、Queue回収時の完了情報読出し＋ACKに
約46 µsのCPU観測時間があった。今回も同じ暫定承認の深さ8 bitstreamを使用し、
FINALE文字結合と1/64計測を両版で有効にして、完了読出しだけを比較する。

## 候補の動作

`B16_COMPLETION_BURST=1` で、Queue回収の最初のpollだけreg27..30を連続読出しする。
4 byteはstatus、完了tag低位／高位、完了error。
DONEが成立していれば、そのsnapshotを使い、独立したreg28..30読出しを省く。
sticky error（reg7）の確認とACK（reg31）は従来どおり実施する。

DONE未成立なら、同じsnapshotのtag/errorは無視する。その後はstatus単独pollへ戻り、
DONE成立後にreg28..30を改めて読む。最初の4-byte読出し自体が失敗した場合は停止する。
tag不一致はACKせず停止、IO／timeout／device／transport faultはラッチして再送しない。

深さ8 RTLは完了slotをACKまで保持し、次の命令実行も完了slotのACKまで止める。
そのためstatusでDONEを観測した後のtag/errorは、1所有者・resetなしの契約内で保持される。
statusが未成立なら、転送途中で完了が発生してもmetadataを採用しない。
新しいRTLやABI、FIFO、クロック、SDCは追加していない。

COPY／PRESENTなど同期命令の完了待ちは従来方式のまま。
Queue回収中であることをSDK内の専用flagで区別し、snapshotはそこだけで有効にする。
長い同期命令が未完了の間に余計なtag/error読出しを繰り返すことはない。
既定値は無効で、Queue深さ8の明示的な実験ビルドだけが対象。

## 制御試験

descriptor packed有無×1/64計測有無×snapshot有無の8構成で、次の9ケース（計72）をPASSした。

- 正常：116件のFILL／PALETTE、tag周回、満杯＋DONE、順序ACK、同期COPY／PRESENT／raw FENCE。
- device error、tag不一致、遅延完了、status未成立のsnapshotと不一致metadata。
- timeout、transport fault、partial-read IO failure、sticky error。

正常ケースでは、snapshot有効側の独立完了読出しは同期命令3回だけで、
無効側119回から116回減った。遅延／raceでは不成立snapshotを捨てて再読出しすることを確認。
誤tag、IO、transport、timeoutでACKやsubmitを再送しないことも確認した。
これは制御mockの試験であり、物理波形の独立検証ではない。

## 計測と比較条件

最初の4-byte読出しにはtag/errorも含まれるため、従来の3-byte metadata読出しの時間が
`poll_us` 側へ移る。`metadata_us`だけの減少を高速化とは扱わず、
poll＋metadata＋ACKの合計を比較する。
いずれもホストIO、IRQ、計測自身を含み、純粋なGPU実行時間やDONE→ACK保持時間ではない。

QBURSTには本編中のsnapshot試行数・DONE成立数・未成立数・fallback回数を記録する。
試行数は全Queue回収call数、成立＋未成立は試行数、fallbackは未成立数と照合する。
従来側はすべて0。これはソフトウェア計数で、独立したハードウェアoccupancyカウンタではない。

RP2040 120 MHz、CPU＋PIO、profile OFF、Queue8、文字結合有効、relative33、seed0xb1616、stars64／objects32。
同じFPGA上で従来→候補を各150秒、HDMI映像＋48kHz/2ch音声を録画する。
bitstream SHA-256は `5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77`。
Setup +0.050 nsという暫定承認条件を維持し、FPGA Flashは変更しない。

```powershell
./software/beyond16/tools/build_rp2040.ps1 -Profile 0 -GpuQueue 8 -QueueMetrics -MergeLettering -BuildDirectory "$PWD/build/completion-burst-20261107/fw-baseline"
./software/beyond16/tools/build_rp2040.ps1 -Profile 0 -GpuQueue 8 -QueueMetrics -MergeLettering -CompletionBurst -BuildDirectory "$PWD/build/completion-burst-20261107/fw-burst"
```

## 実機結果

両版とも全8シーン150秒を完走し、STOP rc=0、Queue error=0、timeout=0、PCM STATUS fault=0。
従来317,872件、候補324,894件を全件回収し、最大未回収8、終了時残件0。
周回の描画frame時刻・幾何が変わるため、総件数差を処理速度へ直接換算しない。

候補の本編Queue回収324,744回のうち、最初のsnapshot成立は309,430回（95.284%）。
残り15,314回は不成立snapshotを捨て、status-only pollと独立metadata読出しへ戻った。
全fallbackが正常完了し、試行＝成立＋未成立、fallback＝未成立、試行＝本編Queue回収数を照合した。
成立件数分の独立したmetadata読出しをソフトウェア上で省略できた。
独立した物理CS波形やGPU内の停止サイクルを測った値ではない。

### 回収サンプルのCPU経過時間

未回収8件から次の投入前に回収するreason=0のサンプルは、従来4,456件、候補4,562件。

| 区間の平均 µs | 従来 | 候補 |
|---|---:|---:|
| poll（候補ではsnapshotのmetadata転送も含む） | 21.85 | 23.87 |
| metadata／sticky確認 | 33.62 | 16.58 |
| ACK | 13.61 | 12.95 |
| **合計** | **69.09** | **53.40** |

合計はサンプル平均で約22.7%短縮した。metadata単独の減少率では評価しない。
COPY前の回収は合計66.22→50.97 µs、PRESENT前は65.64→48.98 µs。
同期COPYの投入→完了ACKは163.24→163.04 µsで、候補を適用していない区間はほぼ同じだった。

### メガデモ性能

| 指標 | 従来読出し | Queue回収snapshot |
|---|---:|---:|
| 全体 実PRESENT fps | 29.483 | 29.680 |
| p95 PRESENT間隔 ms | 49.995 | 49.994 |
| 最悪PRESENT間隔 ms | 83.348 | 100.013 |
| 最悪描画call ms | 82.344 | 83.188 |
| VECTOR WORLD fps | 25.134 | 26.544 |
| FINALE fps | 29.950 | 30.050 |
| 記録deadline miss | 195 | 166 |
| transaction/s | 41,212.7 | 39,515.1 |
| wire byte/s | 200,650.7 | 196,595.3 |

全体は+0.668%、VECTORは+5.612%、transaction/sは約4.12%減。
一方、p95はほぼ同じで、最悪間隔と最悪callは悪化した。
平均側の改善を最悪遅延の改善と解釈せず、全scene安定30 fpsも未達とする。
相対33 ms scheduler、vblankの位相、USB／IRQを含む単発・固定順の結果であり、
有意差・PVT安定性や将来の最大性能は証明していない。
製品既定の深さ1とsnapshot既定OFFは維持し、検討用の実験オプションとして保存する。

## 映像・音声・保持

[従来の全8シーン](evidence/gpu-completion-burst/baseline/contact-sheet.png)、
[候補の全8シーン](evidence/gpu-completion-burst/burst/contact-sheet.png)を記録し、明らかな表示崩れは見られなかった。
実機の全画素CRC／全frameの照合ではない。
両版とも48kHz/2ch音声spanは150.00秒、左右の低RMS欠落10 ms blockは0、capture buffer full記録0。
各sceneの2秒BGM照合の最低相関は従来0.994654、候補0.994302。
独立underrun counterや全sample照合ではない。

RP2040は各書込み前に新規2 MiB退避を2回取得して照合し、書込み後・試験後も全量一致を確認。
消去終端以降、filesystem `0x100a0000` 以降、既存validated画像・凍結済み8構成firmwareの保持はPASS。
今回のRP2040書込み2回、FPGA SRAM投入1回、FPGA Flash書込み0回。

- 従来firmware: `b100fc708260c3d1797df6fe4635d34a882af295095675d81784fc2677848ed0`
- 候補firmware: `c83545b61127dba78944037543f80b849fd8d87b6cb41e1b2bbeed280d74b008`
- 開始前の復旧像: `build/completion-burst-20261107/hardware/baseline/before.bin`
  （SHA-256 `4b700cfef2d8b645bc3dba93309b70ae209625d5a3878df2939c60ec8108a088`）。
- ELF text: 277,756→277,924 byte（+168）。BSS: 175,256→175,260 byte（+4）。

実機はsnapshot有効・文字結合有効・計測有効のQueue firmwareを保持し、PCM停止、USB明示開始gateで待機。
FPGA SRAM構成は電源断で失われるため、再実行前に同じ承認bitstreamを再投入する。

## 証跡と再現

[比較JSON](evidence/gpu-completion-burst/comparison.json)、[実行ledger](evidence/gpu-completion-burst/campaign.json)、
[投入ソースhash](evidence/gpu-completion-burst/source-sha256.json)。
[ホスト制御試験](evidence/gpu-completion-burst/host-tests.json)、
[追加のビルド設定・入力hash](evidence/gpu-completion-burst/firmware-inputs.json)も保存した。
USB原ログにはQBURST／QRET／QSYNCと全frame時刻を保持する。
原動画・WAV・退避像は `build/completion-burst-20261107/hardware/` 以下。

```sh
KAGURA_QUEUE_TEST_DIR=build/completion-burst-retire-tests bash software/beyond16/tools/test_gpu_queue.sh
```

通常SDK15件×2設定、音声CSR10件もPASS。
offline解析は `analyze_queue_demo.py --campaign-dir build/completion-burst-20261107/hardware --evidence-dir docs/evidence/gpu-completion-burst`。
