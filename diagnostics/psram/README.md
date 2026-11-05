# 独立PSRAM診断Top：4B実機1回PASS

2026-11-04。製品RTL、ABI、製品SDC、品質ゲートを変更せず、専用ディレクトリに作成。
Gowin Standard V1.9.12.04で生成。後続の明示許可でFPGA SRAMへ1回投入し、
[限定4B診断がPASS、KAGURA-9へ復元済み](../../docs/psram-4b-hardware-result.md)。
以下の作成・STA記録は投入前の準備履歴を含む。Flash/FW書込みはない。
KAGURA-HD本体は実機不合格、正式Release禁止のまま。

## 固定した最初のケース

- die0、address **300032 (0x49400)**、**1 word / 4B**、case ID 1。
- 既存`rtl/fb/kagura_fb_burst_ctrl.sv`と`rtl/memory/kagura_hyperram_phy_gowin.sv`を無改変で使用。
- CR0=8F1F、LAT=14、RDL=6、54MHz DDR、CK位相67.5°を維持。
- 初期化のCR0書込み後は待機。既存host CSのpin42 (`trigger_n`, Pico GP7)の
  High→Lowを同期して1回だけ起動。**UART RXや新規配線は追加しない**。
- 4B WRITE→4B READ→全バイト比較→UART結果1パケット→freeze。
  正常・不一致・error・timeoutのどの結果でも再起動・次ケース・再送はしない。
- timeoutは試験の各command区間100000 cycle（約1.85ms）。受理後のtimeoutは
  完了不明として扱い、勝手にresetや同一命令再投入を行わない。
- PSRAM以外の描画/audio/host staging窓は含まない。die1は非選択/reset/Hi-Z。
  メモリは揮発性scratchのみ破壊し、restore書込みはしない。

この候補が調べるのは、host窓を除いた最小4Bのcontroller/PHY経路。
32B/64Bラップをこの1ケースだけで確定することはできない。
WORDS/address/seedを変えた合成物へ今回のSTA結果を流用しない。

## 最終候補とゲート

出力: `build/psram-probe-standard/candidate-v3/impl/pnr/psram_probe.fs`

SHA-256:
`f6619b747171c92ea9fdb0aa562acfadfdf7af37940d2d6286b9535eebca62ac`

| 項目 | 最終値 |
| --- | --- |
| Logic | 906 |
| FF | 1249 total (fabric 1246 + I/O 3) |
| CLS | 824 / 4320 |
| BSRAM | 0 / 26 |
| Setup | +6.276ns |
| Hold | +0.708ns |
| Setup/Hold違反 | 0 / 0 |
| 配線 | PnR完了・Bitstream生成成功、error/unroutedメッセージなし |
| 数値ゲート | **PASS**: Setup>=+0.100ns、Hold>=0、違反0、全配線完了 |
| 実機/Release | **限定4B1回PASS / Release禁止** |

最悪Setupは`controller/state_1_s1/Q → phy/dq_txn_q_0_s1/D`。
PLL CK位相を専用SDCで明示。triggerのfalse pathは外部入力→最初の同期FFのみ。
LEDと非同期UART出力、resetの例外を専用SDCに分離した。
**外部DQ/RWDSのmin/max入力出力遅延、data eye/PVT、ODDR TXの全端子経路は
保証していない**。内部数値STAのPASSで、物理PSRAM動作のPASSとはしない。
PLL未使用CLKOUTDのwarningが1件あり、機能未接続として確認。

生成過程の証跡も保持:

| build | 結果 | Logic / FF / CLS / BSRAM | Setup / Hold |
| --- | --- | --- | --- |
| failed-constraint | 初回SDCの合成後FF名誤りでP&R前停止 | 未確定 | なし |
| candidate (v1) | UARTの可変512bit選択経路でFAIL、Setup違反17 | 1338 / 1208 / 1343 / 0 | -2.210 / +0.708ns |
| candidate-v2 | 比較器の可変512bit選択経路でFAIL、Setup違反2 | 1382 / 1208 / 1096 / 0 | -3.131 / +0.708ns |
| candidate-v3 | 送信・比較をbyte shift方式へ変更、PASS | 906 / 1249 / 824 / 0 | +6.276 / +0.708ns |

変更は診断器内だけ。controller/PHYの論理・配置制約・P&R option (1/2)は変えていない。
初回CLIの出力先がrepository rootになったため、生成物は確認後に専用build内の
`failed-constraint/impl`へ移した。以後build.tclはbuild/配下以外での実行を拒否する。
基準ビルドおよび元の失敗Bitstream、KAGURA-9復旧イメージは保持。

## PC検証

`bash diagnostics/psram/test.sh`（WSL、Verilator 5.032）で5ケースPASS:

1. 4B線形の正常WRITE/READ
2. 64B線形の正常WRITE/READ
3. 32B wrapモデルで64B不一致、結果status=1
4. ready未受理timeout、結果status=3
5. controller error、結果status=2、後続READなし

内部valid/readyだけでなく、UART 8N1の実シリアル波形から149Bを復元。
全期待data、正常時実data、ヘッダ、XOR、footer、stop bit、trigger前未実行、
結果後の再trigger無視・余分なパケットなしを検証した。
`build/psram-probe-sim/packet-*.bin`に全パケットを保存。
既存モデル・元の独立wrapモデルは変更していない。

`uv run --offline --no-project python diagnostics/psram/test_decode.py`は3件PASS。
実UARTシミュレーション出力5種類を読み、欠損・余分なbyte・checksum破損・
PASS/data矛盾をrejectする。PCテストをhardware PASSとして出力しない。
製品RTLが無変更のため、前段でPASSした既存Verilator48件を今回は再実行していない。

## 再現コマンド（すべてPC上のみ）

新しい空の`build/psram-probe-standard/<name>`を作成し、その中から:

```powershell
& 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe' '<repository>/diagnostics/psram/build.tcl'
```

repository rootへ戻り、対象BuildDirを明示してゲートを検査する:

```powershell
& diagnostics/psram/check.ps1 -BuildDir 'build/psram-probe-standard/<name>'
uv run --offline --no-project python diagnostics/psram/test_decode.py
uv run --offline --no-project python diagnostics/psram/decode.py '<保存済みUART binary>'
```

最後のコマンドは保存済みファイルの解析だけ。COMポート・Programmerは開かない。
decoderはstatus!=0でexit 1、欠損/破損もエラーにする。XORは簡易破損検出であり、
完全な誤り訂正や強いCRCではない。rawファイルと時刻を必ず保持する。
packetは`PDR1`、status/case ID/words/reserved、LE32 address、CR0 BE16/LAT/RDL、
expected64B、actual64B、前144BのXOR、`END!`の149B。
意味のあるdata長はwords*4、error/timeoutのactualは有効と見なさない。

## 次の実機試験（今回は未実施）

別途SRAM投入を指示された場合に、この正確なハッシュの4B候補1個だけを扱う。
まずKAGURA-9のconsole/PIO所有権を解放し、GP2..5入力・GP6 Low・GP7 Highとし、
現行RP2040 Flashと復旧イメージの同一性を確認する。旧FWがGP7を操作する状態で
ロードしない。UART出力pin17の既存USB-UARTポートと115200 8N1受信を先に確認する。
RP2040 FWは交換しない。SRAMロード後、初期化/armedを確認し、GP7を1回だけLowへ
落として戻す。完全な149Bを保存し、失敗・timeout・不完全packetなら停止する。
自動再送や64Bへの自動昇格をしない。終了後は既存FPGA Flashから再ロードし、
RP2040を通常soft resetしてKAGURA-9環境へ戻す。Flashへの書込みは禁止。

4Bで失敗した場合、長burst wrapだけでは説明できないため、次はDQ/RWDS/CA scopeを
伴う独立試験を検討する。4Bが通った場合のみ、次の境界cross/長READを1件ずつ選ぶ。
元の3ps例外、PSRAM不合格、実ダイ未同定、正式Release禁止はいずれも未解消。
