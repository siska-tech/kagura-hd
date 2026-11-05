# PSRAM 32Bラップ先の専用観測Top（実機Status 4取得済み）

後続の明示承認で1回だけSRAMへ投入し、[300032の実測8A AC CE F0、Status 4](../../docs/psram-wrap-target-hardware-result.md)を取得した。
KAGURA-9へ復元済み。以下は実装・生成・PC検証時点の履歴を含む。線形メモリ合格とはしない。

2026-11-04。前回8B境界診断を基に独立派生を作成した。
**300060への8B WRITE後、300032の独立4B READ値を得ることが目的**。
線形メモリ合否の試験とは分離する。今回は実装・PC検証・Bitstream生成まで。
FPGA/RP2040へのアクセス・書込み、FW変更、Push、Releaseなし。

## 固定シーケンスと停止位置

userの論理Step 4（折り返し先READ）は、UART/internal番号では**Step 7**。
前回のStep 7（same-start 8B READ）とは別の操作である。

| UART Step | 操作 | address | byte数 | seed / WRITE値 / READ期待・予測値 |
| --- | --- | --- | --- | --- |
| 0 | WRITE seed A | 300032 | 4 | ED 0F 21 43 |
| 1 | WRITE seed B | 300060 | 4 | 21 43 65 87 |
| 2 | WRITE seed C | 300064 | 4 | 65 87 A9 CB |
| 3 | READ初期確認 A | 300032 | 4 | ED 0F 21 43 |
| 4 | READ初期確認 B | 300060 | 4 | 21 43 65 87 |
| 5 | READ初期確認 C | 300064 | 4 | 65 87 A9 CB |
| 6 | WRITE境界cross | **300060** | **8** | **01 23 45 67 8A AC CE F0** |
| 7 | READ折り返し先観測 | **300032** | **4** | **32Bラップ予測: 8A AC CE F0** |

3 seedを全て書いた後に3か所を独立READするため、seed間の単純aliasも検出できる。
初期値READの最初の不一致、controller error、timeoutでそのpacketだけを出してfreeze。
Step 7まで到達した場合は、どんな4B値でも全て保存し、予測一致/不一致を記録してfreeze。
後続command、再trigger、resetによる自動再試行はない。
same-start 8B READ、300064の事後READ、追加guard READは今回のシーケンスに含めない。
scratchは揮発性で破壊的。失敗後restore書込みを行わない。

## 判定の分離

| status | 意味 | 停止/観測 |
| --- | --- | --- |
| 0 | WRITE完了、またはseed READ一致 | 次の固定Stepへ進む |
| 1 | 初期値READ不一致 | 即停止、Step 7観測なし |
| 2 | controller error | 即停止 |
| 3 | timeout/完了不明 | 即停止、同じ命令を再送しない |
| **4** | **Step 7の値が8A AC CE F0: 32Bラップ先予測一致** | **全値保存して停止** |
| **5** | **Step 7の値が予測と異なる** | **全値保存して停止** |

4/5はいずれも正常に観測を取得した分類。**status4を線形メモリPASSにしない**。
status5も観測取得の失敗とは区別し、未知値を完全保存する。
Topのfailed LEDは1/2/3の操作異常だけを示し、最終分類はUARTで確認する。
decoderのexit=0は4/5の観測取得完了、exit=1は1/2/3による中断。
不完全/破損packetは別途エラー。`linear_memory_pass=null`、`hardware_pass=false`、
`release_ready=false`を維持する。
線形モデルのseed保持は予測不一致の一例で、実測がseedと一致しても線形メモリ全体の
合格はこの実験だけでは判断できない。

## 実装の独立性・不変条件

新規Top/engineは本ディレクトリだけ。実機PASS済み4B診断、前回8B診断、
元のPBC1 decoderは変更していない。原版UART、CST/SDCをそのまま参照する。
controller/PHY、製品RTL/ABI、SDC、品質ゲート、modelは無改変。
開始/終了時hash比較で旧診断ソースと旧Bitstreamも一致した。
manifestは`build/psram-wrap-target/preserved-inputs.json`。

CR0=8F1F、LAT14/RDL6、54MHz DDR、CK位相67.5°、die0のみを維持。
die1は非選択/reset/Hi-Z。triggerは既存GP7→pin42、UART TXはpin17、115200 8N1。
FW変更や配線追加は不要。1回triggerするまでseed WRITEを含む試験を開始しない。
controller初期化のCR0 WRITEは元の動作のまま。
controller/PHYはこのTopの受理/完了インターフェースへそのまま接続する。
各command区間のtimeoutは100000 cycle（約1.85ms）。受理後の完了不明も再送しない。

## UART形式とデコーダ拡張

新magic **PRT1**、1 packet=149B。前回PBC1のframeを拡張しstatus4/5と新planを追加した。
旧decoderを壊さず、`decode.py`で既存PBC1のseed/cross WRITE plan先頭7件を再利用する。

| byte | 内容 |
| --- | --- |
| 0..3 | PRT1 |
| 4..7 | status、Step index、words、WRITE flag |
| 8..11 | byte address LE32 |
| 12..15 | CR0 BE16、LAT、RDL |
| 16..79 | seed期待値/WRITE値/最終予測値、64B field（未使用部0） |
| 80..143 | 全actual、64B field |
| 144 | 先頭144BのXOR |
| 145..148 | END! |

WRITEのactual=0は実測値ではなく、data_valid=false。
error/timeout時もdata_valid=false。seed READと最終観測READは全actualを保存する。
「最初の初期化不一致」で比較を止めても、受信済みの全data fieldはUARTへ送る。
最終観測の早期不一致も全受信値を保持する。
単純XORだけでなくmagic、順序、address、長さ、op、CR0/LAT/RDL、期待field、
status/data整合、終端、終端結果後packetなしをdecoderが検証する。
簡易XORは強いCRCではないためrawの保持が必要。

全観測まで進んだ場合は**8 packet/1192B**。初期aliasなら4 packet/596Bで停止。
一部packet欠損、途中のstatus0で終了、余分なpacket、予測の虚偽一致をrejectする。
保存ファイル専用のdecoderであり、COM/Programmerを開くコードは含まない。

## PC上のモデル識別・異常検証

Verilator **5.032**、元controllerと既存modelを使用し、実UART 8N1波形から全byteを復元。
既存wrapモデルのCA45許容は仮説modeであり、現物仕様の確定ではない。

| ケース | 最後のStep | status | 300032の最終観測 | command数 / UART bytes |
| --- | --- | --- | --- | --- |
| **32B wrap** | **7** | **4** | **8A AC CE F0** | 8 / 1192 |
| **線形** | **7** | **5** | **ED 0F 21 43** | 8 / 1192 |
| **bit5 alias** | **3** | **1** | 未取得（seed A確認で中断） | 4 / 596 |
| Step6 controller error | 6 | 2 | 未取得 | 7 / 1043 |
| Step6受理前timeout | 6 | 3 | 未取得 | 6 / 1043 |
| Step6受理後完了不明timeout | 6 | 3 | 未取得 | 7 / 1043 |
| Step4 seed READ bit化け | 4 | 1 | 未取得 | 5 / 745 |
| 最終観測bit化け（wrap） | 7 | 5 | **8B AC CE F0**も完全保存 | 8 / 1192 |
| Step7 controller error | 7 | 2 | 無効dataとして保存 | 8 / 1192 |

**9/9 PASS**。初期化失敗は本転送に進まない。controller error/timeout後のcommandなし。
起動前実行なし、結果後再trigger無視、packet数/command数、UART framing/順序/XORを検証。
bit5 aliasは後のseed CがAと同じ場所へ入り、Step3で検出される。
最終status4/5は操作異常LEDと分離されることも確認した。
テストスクリプト初回のCRLF形式エラーはPC上で修正し、上記全ケースを再実行済み。

decoder **5/5 PASS**: 3モデルの識別、全異常capture、欠損/余分/破損/終端後packet、
虚偽予測一致、target address違い/旧protocol拒否。
[全simulation一覧](../../docs/evidence/psram-wrap-target-simulation.json)を保存。
全rawは`build/psram-wrap-target/packet-*.bin`、wrap/linearのdecoded JSONも同所。
これらはPC上の値で、**実機測定値ではない**。
無改変の既存全回帰は今回は再実行していない。

## Standard Bitstreamと品質ゲート

出力: `build/psram-wrap-target/candidate/impl/pnr/psram_wrap_target.fs`

SHA-256:
**`95338d44f7c7535fe18759996f69e3849a4ee44ff814711941b67a3bfde21694`**

| 項目 | 結果 |
| --- | --- |
| tool/device | Gowin Standard V1.9.12.04 / GW1NR-LV9QN88PC6/I5 |
| Place/Route | 1 / 2 |
| Logic / CLS | 1100 / 910 |
| FF | 1411 total = fabric 1408 + I/O 3 |
| BSRAM | 0 / 26 |
| Setup | **+6.601ns** |
| Hold | **+0.708ns** |
| Setup/Hold違反 | **0 / 0** |
| 配線 | PnR完了・Bitstream生成成功、error/unrouted messageなし |
| 数値ゲート | **PASS: Setup>=+0.100ns、Hold>=0、違反0、配線完了** |
| 実機/Release | **未投入 / 禁止** |

最悪Setup: `phy/dq[4].id/Q0 → controller/receive[15].pair_data_4_s0/D`。
未使用PLL CLKOUTDのwarningのみ。1回の独立ビルドでゲートPASS。
SDC/thresholdを緩和していない。外部PSRAM min/max I/O遅延、TX端子経路、PVT/eyeの
保証ではなく、内部数値STAの合格。
[gate JSON](../../docs/evidence/psram-wrap-target-gate.json)、
`candidate/source-manifest.json`、build/合成/P&R/STA reportを保持。

## PCでの再現

```bash
bash diagnostics/psram-wrap-target/test.sh
```

```powershell
uv run --offline --no-project python diagnostics/psram-wrap-target/test_decode.py
uv run --offline --no-project python diagnostics/psram-wrap-target/decode.py build/psram-wrap-target/packet-r1-a0-f0.bin
```

新しい空の`build/psram-wrap-target/<name>`からStandard gw_sh.exeへ
`diagnostics/psram-wrap-target/build.tcl`の絶対pathを渡して生成する。
repository rootで`diagnostics/psram-wrap-target/check.ps1 -BuildDir build/psram-wrap-target/<name>`を実行。
root直下でのビルドは拒否。既存buildを上書きしない。

## 別途承認後の実機試験手順（今回は未実施）

1. 上記hash、gate、JTAG GW1NR-9C/ID、pin17 UART、pin42 triggerを再確認。
   PSRAM 1.8VとUART/trigger 3.3Vの制約/PnRを照合する。
2. 既存KAGURA-9の画面、RP2040全Flash hash、保存済みbackup/復旧UF2を確認。
   console/PIOを解放しGP2..5入力、GP6 Low、GP7 High。RP2040 FWは変更しない。
3. UART受信専用115200 8N1を先に開始。受信前bufferを隠して捨てず、トリガ前の
   不審出力があれば投入/実行を止める。候補のSRAM投入自体は別途承認が必要。
4. 承認された正確な候補をSRAMへ1回だけ投入し、初期化待機後GP7を1回だけ
   Low→High。固定8 commandだけを実行する。
5. 全UART rawを保存しPRT1で検証。Step7 status4/5の実測4Bを報告する。
   初期不一致/error/timeout、不完全出力・停止しない場合は中断として保存する。
   どの場合も後続診断、再trigger、reset再試行、失敗後の復元WRITEを行わない。
6. 既存FPGA Flash構成をSRAMへ再ロードしKAGURA-9へ復元する。
   RP2040全Flash hash、通常soft reset後のconsole起動、元HDMI画面を確認する。
   この復帰resetを診断再試行に使わない。Flash/FWのerase/programは禁止。

実機で8A AC CE F0を観測しても、証明する範囲はこのWRITE後の300032の4B値。
全域wrap長、実ダイID、全機能、元64Bの追加bit化け、PVT/長期動作の確定ではない。
実機未投入の現時点では「32Bラップ先を実測した」と記録しない。
製品の3ps例外と実機不合格、正式Release禁止は継続。
