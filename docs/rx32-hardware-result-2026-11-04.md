> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD RX32 実機評価 — 4B PSRAM不一致で停止

2026-11-04。**実機評価はFAIL。最初の4B WRITE/READで不一致を確認し、それ以降の試験を行わず、既存KAGURA-9へ復元した。** 内部STAの数値合格は維持するが、KAGURA-HDの実機合格・Releaseにはしない。

## 対象と事前確認

- Tang Nano 9K / GW1NR-LV9QN88PC6/I5、JTAG ID `0x1100481B`、1 device。
- 独立branch `eval/rx32-scanout-01`。32B分割＋音声Phase 1＋scanout RX32、QSPI、ABI1.2。RTL/SDC/CSTを追加変更していない。
- Standard V1.9.12.04、setup +0.898ns、hold +0.530ns、違反0/0、全配線の対象と同じbitstream。
- 投入直前のbitstream SHA-256：`a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`。
- Programmer V1.9.12.04、`--run 2` SRAM Programを1回、Finished、4.12s。programmer readback verifyを行ったとは主張しない。
- COM7はRP2040（2E8A:0005）、COM8はFTDI（0403:6010）。COM8への送受信はしていない。
- 既存KAGURA-9 ABI(0,6)/PIOTransportを確認。console pause/close、`_closed=True/_active=False`、GP2..5入力、GP6 Low、GP7 Highを確認してホスト所有権を解放。
- RP2040全2MiB Flash hashが既存のprivate backupと一致：`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。復旧UF2も保存hashと照合。boot.py hashも既知値一致。
- 診断ドライバは既存検証済みのmethod loaderでRAM上へ38分割ロード。RP2040のファイル/FWへはインストールしていない。

通常権限でのCOM7/カメラアクセスはOSアクセス拒否で開始できず、必要な権限を持つ実行で接続した。失敗ログも保持した。この段階の失敗では診断commandは送信されておらず、FPGA投入や不確実なWRITEを再試行したものではない。

## 実測結果

|項目|結果|
|---|---|
|SRAM投入|Finished、1回|
|初期化GPIO|READY=1、BUSY=0、IRQ_N=1|
|識別|`KFB1 01 02 7f`、ABI1.2/全能力一致|
|FENCE|PASS|
|PSRAM最初の4B WRITE/READ|**FAIL**|
|境界8B/独立guard READ|未実施：最初の不一致で停止|
|64B/全offset/byte mask|未実施|
|FILL/PRESENT/palette/BLIT/cursor|未実施|
|KAGURA-HD HDMI画素/音声の受入|未実施|

対象addressはdie0内の**byte address 300032**。FB2page（0..230399）と診断PCM領域（240000..240127）の外であり、32B境界に整列する。

```text
FENCE_PASS
PSRAM_READ single4-seed 300032 EXPECTED ed0f2143 ACTUAL 0d232143
AssertionError: PSRAM mismatch: single4-seed; stop before drawing
```

|byte offset|期待|実測|XOR|
|---|---|---|---|
|0|ED|0D|E0|
|1|0F|23|2C|
|2|21|21|00|
|3|43|43|00|

2/4byte、6bit不一致。これは本体のホストcommand経由で得たREAD結果である。WRITE終了/READ終了とホスト側受信のどの段階で破損したかは、今回の1回では分離していない。

診断は最初のseedの直後にassert停止し、`finally: deinit()`でQSPI pinsを解放した。残り2個のseed、8B WRITE、独立guard READ、64B WRITEは実行されていない。不確実なcommandのreplay、再trigger、別patternでの再試行はない。

## 解釈と限界

1. **内部STA合格だけでは外部PSRAMのデータ整合性は保証されないことを実測した。** 現SDCの外部I/O未保証、固定RDL/READ捕捉、CA/初期化等は引き続き未解決。
2. 今回の4Bは32B境界を跨がない。したがって、この不一致を境界跨ぎwrapだけで説明できない。一方、32B分割を実機で否定/確認する境界試験自体は未実施である。
3. 以前の独立4B診断PASSは別bitstream/配置/刺激の結果。今回の本体で4BがPASSする根拠として流用できない。今回の失敗だけで、その過去のPASSが誤りだったとも判断しない。
4. 先頭16bitだけの不一致は今回の観測であり、latency/位相/turnaroundの原因確定ではない。host upload/download、WRITE出力、READ捕捉の各可能性を残す。
5. scanout RX32の機能・資源・STA成果を否定する証拠ではないが、本体実機の成立は未達。ここからpalette小幅化やさらに広い内部stream化へ進む根拠にはしない。

## 復旧

- 診断停止後、公式Programmer `--run 1` Reprogramを1回、Finished、0.49s。既存FPGA FlashからSRAMへKAGURA-9を再ロードした。Flash erase/programではない。
- 復旧用の別RAM commandでQSPI deinit、CS High/SCK Low、旧PIO閉鎖状態を再確認。PSRAM診断は再開していない。
- RP2040全2MiBを同じXIP範囲で再hashし、投入前/private backupと完全一致。
- 単一raw REPL接続を閉じ、その後に通常soft resetで既存KAGURA-9を再開。QSPI5MHz console / MicroPython v1.26.0の起動bannerを確認。
- 復元後のHDMI captureを目視し、既存KAGURA-9 banner/REPLへの復帰を確認した。これはKAGURA-HDの映像PASSではない。

SRAM候補投入1、復元1、fault後の診断retry0、FPGA/RP2040 Flash書込み0、FW/boot/file変更0。復旧private imageは公開証跡に含めない。scratch PSRAMの内容は使い捨てで、初回不一致後に追加WRITEで修復していない。

## 次に必要な最小切分け

今回の実機操作は終了した。次の実験は以下を独立に具体化する。

1. **同じ合格bitstreamのまま、PSRAM command前のupload窓へ書いた4BをCSRから読み返す。** ホスト入力/窓保存をPSRAMから切り離す。READ download側の経路も独立に評価する方法を用意する。
2. **READとWRITEを分離できる診断を設計する。** 既知の単独4B診断との比較、独立read方式/受信pairの観測等により、先頭pair/後半pairを切り分ける。対照bitstreamの再投入が必要なら、対象hash/STA/復旧と実施回数を別途固定する。
3. 実ダイID/CR・CA[45]・固定LAT/RDL・CK/DQ/RWDS/CSのpad timingを一次資料/実測に照らす。CR0/CA45/位相を推測で変更した修正版は作らない。

最初の狙いは、この4B破損がhost窓・WRITE・READのどこで生じるかを一つずつ狭めること。新規合成/P&R、PHY/設定変更、追加実機試験は今回行っていない。

## 証跡

ローカル `build/rx32-hardware-eval/` に保存：

- `jtag-scan.log`、`sram-program.log`、`restore-fpga.log`
- `control/001-preflight.{log,result.json}`、`ram-load.log`
- `control/020-identity.{raw,log,result.json}`
- **`control/030-psram-basic.{raw,log,result.json}`**：不一致のraw REPL応答・失敗をそのまま保存
- `control/090-restore-verify.{log,result.json}`、`restore-soft-reset.log`
- `kagura9-before.png`、`kagura9-restored.png` とcapture logs
- `result.json`、`evidence-sha256.json`：機械可読判定と証跡hash

実行済み `psram-basic.py` は計画した後続試験のコードも含むが、実施済み範囲はログの最初の4Bまでである。コードにあることを実行済み/合格とは扱わない。
