# 完了連続読出しのA/B/A/Bと最悪PRESENT間隔

2026-11-07、[前回の連続読出し比較](gpu-completion-burst.md)を同じfirmwareで反復した。
Aは独立metadata読出し、BはQueue回収の最初だけreg27..30を連続読出しする版。
両方ともQueue8・文字結合ON・1/64計測ONで、描画やschedulerは変更しない。
sticky確認と独立ACKをすべて維持する。

**全体・VECTOR WORLDのfps改善は2組とも再現した。安定30 fpsと最悪間隔の改善は未達。**

## 反復結果

| 実行 | 全体fps | VECTOR fps | 最悪PRESENT ms | 投入＝回収 |
|---|---:|---:|---:|---:|
| A1 | 29.486 | 25.105 | 100.011 | 317,616 |
| B1 | 29.690 | 26.616 | 100.004 | 324,975 |
| A2 | 29.480 | 25.105 | 83.341 | 317,496 |
| B2 | 29.686 | 26.594 | 100.006 | 325,061 |

全体の2回平均は29.483→29.688 fps（+0.696%）、VECTORは25.105→26.605 fps（+5.978%）。
隣接A/Bの全体改善率は+0.690%／+0.701%、VECTORは+6.023%／+5.934%。
両指標ともBの小さい側がAの大きい側を上回った。固定順2反復の範囲で再現性を確認した結果であり、
統計的有意差・環境変動全般の保証とはしない。
p95間隔は全周49.992～49.997 ms、最悪callは82.333～83.162 msで、最悪遅延は解消していない。

4周合計1,285,148件を全件回収した。全周150秒・全8シーン、STOP rc=0、最大未回収8、終了残件0、
Queue error／timeout／PCM faultは0。
左右音声の低RMS欠落10 ms blockは全周0、音声spanは150.00～150.01秒、
8区間BGM照合の最低相関は0.994466、capture buffer full記録も0。
4周の全8シーンcontact sheetを目視し、明らかな表示崩れは見られなかった。
全画素CRC・全音声sample照合・独立underrun counterの検証ではない。

B1/B2のsnapshot成立は309,539／309,547回で、その回数分の独立metadata readを省略した。
未成立15,286／15,364回はすべてfallbackし、試行＝成立＋未成立、未成立＝fallback、
試行＝本編Queue回収call数を照合した。

### 回収時間と、確実にACK前保持しているsample区間

| 実行 | 満杯回収sample数 | poll＋metadata＋ACK平均 µs | DONE確認後→ACK呼出し前 平均 µs | 同区間sample合計 µs |
|---|---:|---:|---:|---:|
| A1 | 4,453 | 68.55 | 33.62 | 149,691 |
| B1 | 4,563 | 53.89 | 16.64 | 75,933 |
| A2 | 4,451 | 68.21 | 33.62 | 149,646 |
| B2 | 4,565 | 53.67 | 16.62 | 75,868 |

回収全体のCPU観測時間の短縮も2組で再現した。
右2列はreason=0の実測sample区間で、後続descriptorがあることと現行RTLの条件から、
その区間にdispatchを止めていると判断できる。純GPU時間ではなく、保持全体の下限側の部分観測である。
snapshotはtag/error転送をpoll区間へ移すため、33.62→16.6 µsだけを内部総停止の短縮率にしない。

## 条件と証跡

A1→B1→A2→B2の順で各150秒・全8シーン、HDMI映像と48 kHz/2ch音声を取得する。
RP2040 120 MHz、CPU＋PIO、profile OFF、relative33、seed0xb1616、stars64／objects32。
前回の二つのbinをそのまま使用し、投入source manifest 14ファイルも前回と完全一致した。

- A firmware SHA-256: `b100fc708260c3d1797df6fe4635d34a882af295095675d81784fc2677848ed0`
- B firmware SHA-256: `c83545b61127dba78944037543f80b849fd8d87b6cb41e1b2bbeed280d74b008`
- FPGA SRAMは同じ暫定承認画像 `5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77`。
- Setup +0.050 nsの暫定条件を維持し、FPGA Flash変更なし。
- RP2040は各書込み前に新規2 MiB backupを2回取得・照合し、書込み後と試験後も全量照合する。
  filesystemと消去終端以降の保持を検証する。

[比較JSON](evidence/gpu-completion-abab/comparison.json)、
[実行ledger](evidence/gpu-completion-abab/campaign.json)、
[firmware再利用確認](evidence/gpu-completion-abab/firmware-reuse.json)、
[PRESENT区間分解](evidence/gpu-completion-abab/present-gaps.json)。
生動画・WAV・Flash backupは `build/completion-abab-20261107/hardware/` に保存する。

## 100 msの原因照合

既存FRAMEログだけで、各PRESENT間隔を次の3区間へ分解する。

```text
前回PRESENT完了 → 今回draw_start → 今回present_before → 今回present_after
                 開始まで          描画等               PRESENT call
```

全frameについて3区間の和がPRESENT間隔に厳密一致することをassertする。
開始までにはschedulerと前frameのPRESENT後処理が含まれる。
描画区間にはCPU処理・FILL投入・途中のQueue回収・COPY等が含まれ、純GPU実行時間ではない。
PRESENT callにはQueue drain、descriptor投入、GPU／vblank待ち、error確認、ACKが含まれる。

前回Bの100.013 msは本編143.017秒、FINALEの初回文字描画のframeだった。
16.830 ms＋70.871 ms＋12.312 msで、描画call自体は83.188 ms。
前回Aの83.348 msは143.001秒で、1.011 ms＋79.663 ms＋2.674 msだった。
前回の文字描画はBで約8.8 ms短かったが、描画開始前とPRESENT内の待ちで差が相殺された。

| 実行の最悪間隔 | 本編時刻 ms | scene／処理 | 開始まで ms | 描画等 ms | PRESENT call ms |
|---|---:|---|---:|---:|---:|
| A1 100.011 ms | 143,017 | FINALE初回文字 | 17.078 | 79.899 | 3.034 |
| B1 100.004 ms | 143,017 | FINALE初回文字 | 16.847 | 70.913 | 12.244 |
| A2 83.341 ms | 139,685 | VECTOR WORLD | 1.015 | 68.187 | 14.139 |
| B2 100.006 ms | 143,017 | FINALE初回文字 | 16.919 | 70.874 | 12.213 |

A1にも100 msが発生しており、連続読出し固有の新しい100 ms停止という説明は支持されない。
一方でBの最悪間隔が改善したともいえない。

コードのscene=7は143秒を境に、各pageで一回ずつ`final_ready[page]`を立てて文字列をまとめて描く。
relative33は各draw開始時刻msへ33 msを足して次回を決めるため、短く終わった前frameのあとに
約1 vblank分の開始待ちが残る場合がある。文字描画は33 ms予算を大きく超え、
PRESENTは次のvblankで完了するので、位相によってPRESENT間隔が約83／100 msへ量子化されると考えられる。
開始待ち・描画負荷の位置はログとコードで確認できるが、PRESENT内のGPU処理とvblank待ちは
個別timestampがないため厳密に分離していない。IRQやUSBの寄与を0とは断定しない。

改善する場合は、初回文字描画を複数frameへ分ける／事前生成する設計と、
実PRESENT時刻を踏まえたschedulerの別実験が対象になる。途中の文字が見えるか、page間の整合性、
開始時刻や音声同期への影響を決める必要がある。今回のA/Bでは変更していない。

## sticky確認とACK、内部待機

[安全な短縮候補とACK観測設計](gpu-ack-observation-design.md)にまとめた。
現行QSPIはtransaction中の方向切替えに対応しないため、sticky readとACK writeを直接一体化できない。
read-to-ACKも誤tag／IO失敗時の保持契約を破る。
次候補は別ABIでstickyを完了snapshotへ隣接させ、ホストの全確認後に独立ACKする方式。
実装・投入はしておらず、今回の測定firmwareにエラー確認の省略はない。

内部ACK待機は、現行RTLの`completed && queue_count!=0 && !active`をsimulationで観測した。
後続あり28完了のACKを各100 cycle早めると、dispatch停止が2,800 cycle減った。
実機ではreason=0のDONE確認後→ACK呼出し前のsample区間だけを「確実に完了を保持している区間」として集計する。
これは内部総停止cycleではなく、metadataの差だけを総停止時間の削減へ換算しない。
直接測定にはcounterとatomic snapshotを備えた新しい観測bitstreamが必要となる。

## 再現

既存campaignの上書き・再開・開始済みdemoの再送はしない。新しいbuild下directoryを用意し、
現在のFlash全量hashを確認したうえで、固定bin二つを`fw-baseline`／`fw-burst`へ配置する。

```powershell
& "$env:USERPROFILE/.local/bin/python3.12.exe" software/beyond16/tools/hardware_queue_demo.py --campaign-dir build/<new-campaign> --completion-burst --abab --expected-flash-sha256 <current-full-flash-hash>
```

```sh
bash tools/test-fb-ack-observe.sh
python3 software/beyond16/tools/analyze_queue_demo.py --campaign-dir build/completion-abab-20261107/hardware --evidence-dir docs/evidence/gpu-completion-abab
```

1/64 sampleはランダム抽出ではなく、2反復は信頼区間やPVT保証には足りない。
表示はCPUがACKまで観測したPRESENTで、HDMI scanout時刻ではない。安定30 fpsを判定するには平均だけでは足りない。

## 実機の最終状態

RP2040書込み4回、FPGA SRAM投入1回、FPGA Flash書込み0回。
各周の前後全Flash照合・filesystem保持・既存validated画像保持はPASS。
実機はB版Queue firmware、PCM停止、明示USB開始gateで待機している。
最終全Flash hashは開始前と同じ `c7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a`。
今回の開始前復旧像は `build/completion-abab-20261107/hardware/baseline-1/before.bin`。
製品既定の深さ1、連続読出しOFF、release_ready=falseを維持する。

## 検証コード

ACK観測の遅延0／100比較、既存深さ2/4/8のregistered head統合試験、深さ1のregister window互換試験をPASSした。
追加Python 3ファイルの構文、shell試験の構文、差分の空白検査も通過。
測定firmware／SDK／製品RTLは前回と同一であり、今回はhost 72ケースを再実行せず、
前回の[試験証跡](evidence/gpu-completion-burst/host-tests.json)を参照する。
[解析入力hash](evidence/gpu-completion-abab/analysis-inputs.json)と
[今回のsimulation証跡](evidence/gpu-completion-abab/regression-tests.json)を保存した。
