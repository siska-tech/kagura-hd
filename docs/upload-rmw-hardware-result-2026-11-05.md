> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 32bit保持RMW統合候補：限定実機4B試験PASS

2026-11-05。ユーザーの「実機試験行きましょう」を受け、[統合評価](upload-rmw-integration-result-2026-11-05.md)の候補をFPGA SRAMへ1回投入した。**元の失敗アドレス300032（10進byte address）でED 0F 21 43が一致した。** upload窓5ケース、PSRAMの17回の4B比較はすべて一致した。予定した限定試験を終了し、KAGURA-9への復元とHDMI表示を確認済み。`release_ready=false`を維持する。

## 対象・前提・来歴

- branch `fix/upload-word-rmw-01`、`build/upload-rmw-worktree`。元RX32候補は保護。
- fs SHA-256：`90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`。
- GW1NR-LV9QN88PC6/I5 / GW1NR-9C、Standard V1.9.12.04。Setup +0.717ns、Hold +0.407ns、違反0/0、全配線。PC全回帰は統合報告参照。
- 変更はupload leafとCSR registersの2 RTLだけ。Controller/PHY、32B分割、clock/制約、GPU機能は基準と同一。配置は異なる。
- JTAG 1 device、ID `0x1100481B`。COM7はRP2040、COM8はFTDIと照合。COM8への通信は行わない。
- RP2040の既存KAGURA-9 ABI(0,6)/PIOTransportを確認し、console pause/close、PIO解放、GP2..5入力・GP6 Low・GP7 Highを確認した。
- 既存の38分割method loaderをRAMにだけロード。同じQSPITransport(half_period_us=5)とDeviceを使用。これはPythonによるbitbang QSPIであり、5MHz設定や1MHz PIOと混同しない。pad周波数は未測定。
- RP2040全2MiB Flashおよびboot.py、private復旧bin/UF2のhashを試験前に確認。ファイル/FWへのインストールなし。

## 実測結果

SRAM Program `--run 2` は1回、Finished、4.1秒。readback verifyを実施したとは主張しない。READY=1、BUSY=0、IRQ_N=1、識別 `KFB1 01 02 7f`。READYを観測してからHost操作した。電源投入からの経過時間、pad波形は未計測。再電源投入なし。

Hostからメモリcommandをsubmitする前に、以下をCSRでechoした。本体は起動時のメモリ初期化・表示アクセスを行うため、CS非assert診断ではない。

|Test ID|窓offset|長さ|期待値|結果|
|---|---:|---:|---|---|
|U4-0|0|4B|ED 0F 21 43|一致|
|U4-60|60|4B|43 21 0F ED|一致|
|U8-28|28|8B|12 34 56 78 AA 55 55 AA|一致|
|U32-0|0|32B|ホスト生成(i×37+11) mod 256|全byte一致|
|U64-0|0|64B|ホスト生成(i×37+53) mod 256|全byte一致|

計112Bのecho。FPGAのREAD結果を期待値生成に使用していない。

次にFENCEを確認し、scratch領域のguardを300000=`AA 55 AA 55`、300064=`55 AA 55 AA`として各4B WRITE/READし一致を確認した。これらはFB2面（0..230399）、既存PCM領域（240000..240127）の外。新しい描画・音声操作は送信していない。

|Test ID|byte address|WRITE値|直後READ|連続READ|guard別READ後＋10ms待機READ|
|---|---:|---|---|---|---|
|P4-ED|300032|ED 0F 21 43|一致|一致|一致|
|P4-REV|300032|43 21 0F ED|一致|一致|一致|
|P4-1234|300032|12 34 56 78|一致|一致|一致|

各patternについて両guardを独立アドレスの4B READで比較し、変更がないことを確認した。合計WRITEは5 command（guard2+対象3）、READ比較は17 command（対象9+guard8）。全XOR=00000000、error byte=[]。失敗・timeout・識別異常はなかった。予定範囲終了後に追加の転送はしなかった。

## 過去FAILとの直接比較と解釈

|条件|旧RX32候補|今回|
|---|---|---|
|fs SHA先頭|a99c5f83…|90b5b261…|
|upload|動的native byte enable SP|共有merge＋32bit完成word保持、全word SP|
|Controller/PHY|基準実装|ソースhash同一|
|System / PSRAM CK|54MHz / nominal54MHz|同じ|
|CK位相 / LAT / RDL|67.5度 / 14 / 6（設計値）|同じ|
|CA[45] / 初期化設定|基準RTL|変更なし|
|Host driver|38分割RAM-only、bitbang half_period_us=5|同じ保存method jobs|
|address / length / expected|300032 / 4B / ED0F2143|同じ|
|actual|0D232143|**ED0F2143**|
|先行操作|識別→FENCE→対象4B|識別→upload echo5件→FENCE→guard2件→対象4B|
|起動条件|SRAMロード後、READY確認|同様。ただし電源投入からの時間等は一致未証明|
|配置 / pad timing|旧配置、未測定|別配置、未測定|

**観測済み：** 修正候補のHost窓と本体経由の限定PSRAM4B往復は一致した。以前の独立6点診断でCSR受理後のSP出力から破損し、FF/RMW対照で改善した証拠と整合する。

**支持される方針：** upload native partial-write依存を除く局所修正を維持し、今後のPSRAM試験の入力経路として用いる。

**未確定：** 元の0D232143の全原因がuploadだけだったか、WRITE/READのどちらで追加破損したかは今回だけでは確定しない。配置と先行操作も異なる。内部tapを追加していないため、Controller TX/PHY WRITE/READの境界ログ、DQ/RWDS/CK pad波形は取得していない。READ/WRITEを独立した物理オラクルで証明した結果でもない。

32B wrapと64B時の追加破損は未評価。今回のPSRAM転送は全て32B境界を跨がない4Bであり、uploadの64B PASSをPSRAM64B PASSとして扱わない。

## ソースから計算した条件（実測と区別）

対象300032は32B整列、Controller word index=75008、halfword address=150016。4Bは1word/1chunk、Host禁止mask=`fffffffffffffff0`、有効chunkの4byteは禁止mask=0。CA予測はWRITE=`200049400000`、READ=`a00049400000`。CA[45]=1は変更していない。実CA・maskをpinから観測した値ではない。

基準RTLはLAT=14、RDL=6、CS_HIGH_CYCLES=2、INIT_CYCLES=4096、CR送出値8F1F。54MHzからの単純換算では4096周期≈75.85µs、CS-high 2周期≈37.04ns。ただしこれらは設計カウンタ値の換算であり、実ダイのmin/max適合判定ではない。READはRWDS strobeを使わない固定capture方式を維持した。

## 復旧と保護

1. QSPI deinit、CS High/SCK Low、DQ入力を確認。
2. `--run 1` Reprogramで既存FPGA FlashからKAGURA-9をSRAMへ復元。1回、Finished、0.46秒。Flash erase/programではない。
3. RP2040全2MiBを再hashし、前/backupと一致：`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。
4. 単一raw REPL接続を終了し通常soft reset。KAGURA-9 QSPI5MHz / MicroPython v1.26.0の起動bannerを確認。
5. 最初のHDMI画面はKの1文字で止まり、5秒間5枚とも同一だった。この時点では復旧完了としなかった。consoleはlast_error=None、paused=False、ABI(0,6)、busy=0、updating=Falseを確認。
6. 既存console API `resume()`で画面資源を再初期化し、`KAGURA-9 RECOVERY CONFIRMED (0, 6) None`を表示。取得3枚中の最終画像を目視し、全文とREPLプロンプトへの復帰を確認した。K停止の直接原因は未確定。診断再開・hard reset・FW変更なし。

Flash hashは復元後・通常soft reset前の比較。soft reset/resume後の追加Flash読出しとは区別する。boot.py試験前hash=`9ef26228ee5039efa193938d4d11cc036d4b2589289250719f484647716b62b0`。SRAM投入1、Reprogram1、診断再試行0、FPGA/RP2040 Flash書込み0。

元bitstream SHA `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`と元DO_NOT_PROGRAM SHA `d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546`を再照合した。保護状態に変更なし。

## 次の最小試験

今回の実機操作は終了した。次は同じ候補・同じHostで、300060の8B境界跨ぎを、300032のwrap先guardと300064の独立READで検証する。境界前後を4Bずつ比較し、同一起点8B READは補助判定に留める。これが通った後に16/32/64Bへ段階的に進む。位相・CA・CR0・latencyは同時に変更しない。

cold reset、全pattern/全offset、die終端、PVT、物理I/O min/max、GPU映像・音声の受入は未実施。今回のPASSはRelease条件達成ではない。

## 証跡

- [機械可読結果・全17比較](evidence/upload-rmw-hardware-2026-11-05.json)
- ローカル `build/upload-rmw-hardware-2026-11-05/`：prepared-inputs、method-jobs、serial-worker、controlのraw/log/result、SRAM/復元ログ、前後HDMI画像、復旧追加確認ログ、result、evidence-sha256。
- `tools/prepare-upload-rmw-hardware.py`と`tools/save-upload-rmw-hardware-result.py`は準備・証跡検証用。自動で実機再試行しない。保存済みdirectory/markerにより再送を拒否する。

復旧private imageは公開証跡に含めない。
