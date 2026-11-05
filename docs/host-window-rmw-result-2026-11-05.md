> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Upload全word RMW：独立診断4Bが実機一致

2026-11-05。ユーザーの継続指示を受け、診断専用RMW leafのPC検証、Standard生成、
SRAM投入1回・4B1ケースを実施した。**RMW版でも全6観測点とHost受信が一致した。**
実機操作は終了し、既存KAGURA-9へ復元済み。製品RTL/PHYは未変更、PSRAM転送は0。

## 1. 結論と適用範囲

元の動的byte-enable SP版はCSR受理まで正しくupload出力から破損し、FF対照と今回の
全word RMW版は一致した。upload SPのnative partial write依存を外す局所修正方針を
支持する結果である。**対象SPのbyte-enable適用仕様・入力timing・mappingのうち、
どれが直接の機序かは未確定**。配置差もあるため単一原因を断定しない。

今回合格したのは、PIO設定1MHz・ED0F2143・upload窓先頭4B・1回のechoだけ。
全アドレス/全pattern/PVT、download bulk capture、Controller WRITE/READ、
実PSRAM、元KAGURA-HD候補の合格へは拡張しない。製品への統合も行っていない。

## 2. 3構成の実測比較

全variantで共通：ISO2-1、PIO設定1,000,000Hz、4lanes、同じRAM-only adapter、
同じCSR操作と6点recorder、clock/SDC/CST、Gowin Standard V1.9.12.04、Place1/Route2。
pad周波数は未測定で、配置自体はvariantごとに変わる。

|境界|元SP|FF対照|全word RMW|
|---|---|---|---|
|transport受理|ED 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|CSR受理|ED 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|書込み後8cycleのupload出力|AF 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|first READ時のupload出力|AF 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|CSR応答|AF 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|transportへ渡す応答|AF 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|Host受信|AF 0F 21 43|ED 0F 21 43|**ED 0F 21 43**|
|判定範囲|4B不一致|限定4B一致|**限定4B一致**|

RMWのUARTはPDT1/source4/case2、136B、CRC32一致。RX/write/read/CSR response/
transport response countは各4、flags=0、header fault=false。
UARTはHost QSPIとは別経路で実interfaceを記録している。
RMWの全136BはPC pin-levelシミュレーションのpacketとも同一で、期待値を受信値から
生成していない。

## 3. RMW変更点と契約

修正仮説は診断専用
`diagnostics/host-window-observe/fix-candidates/kagura_fb_upload_word_rmw.sv`。
元のSPの動的`AD[3:0]=byte_enable`を使用せず、byte_enableで新しいbyteと既存wordの
read値をmergeし、`AD=14'h000f`固定で32bit全wordを書き込む。

- interface、SP32×16、parallel512出力、書込み中のread出力保持という論理契約を維持。
- partial write前にはSP read値が安定している必要がある。少なくともread edgeを挟む。
- full-word bulk writeは旧read値に依存せず、連続writeも可能。
- 既存CSRのwrite_recovery/出力安定待ちと組み合わせて検証した。

SP版との共通compile入力hashは一致し、差はupload leafとそれを選択するbuild Tclのみ。
製品のregisters/adapter/commands、観測回路、clock/IO制約は変更していない。
元のleafは保存し、製品moduleを直接書き換えていない。

合成後netlistでも、16個のSP全てでADが上位10bit GND・下位4bit VCCになっていることを
機械検査した。DI mergeを含むBSRAM入力はSTAの対象に現れ、最悪Setupの終点もSP DI。
これは外部PSRAMのtiming sign-offではない。

## 4. PC検証

Verilator 5.032、Standard付属SPモデルをbuild内へ抽出して使用。

|検証|結果|
|---|---|
|leaf独立oracle|16 mask×8 data系列=128ケース、保持laneも比較してPASS|
|連続bulk write|read edgeを挟まない連続全word write、安定後partial writeがPASS|
|既存CSR/window testbench|即時byte write/readback、6 READ completions、18 COPY captures、warm reset PASS|
|QSPI/実UART波形|6点snapshot・freeze・再arm拒否・全136Bが既存oracle packetと一致|
|全word限定ゲート|RMWの全writeが通過。元leafは動的partial write時に期待どおりreject|

全word限定ゲートは汎用SPモデルに追加した**自作の保守的な構成検査**である。
元leafのnegative test abortは想定結果であり、実チップ故障を再現したものではない。
観測したAF等の誤値はモデルへハードコードしていない。
対象デバイスのbyte-enable適用問題は[前報告の一次資料照合](host-window-boundary-result-2026-11-05.md#4-byte-enable仕様とモデルの重要な相違)を維持する。

## 5. Standard生成・品質ゲート

候補：`build/host-window-observe/standard-rmw/impl/pnr/host_isolation.fs`

SHA-256：
`487c81c0ce99d4a795e3edea48b46d19e0aeccbf932359469c00d3888edab38a`

|項目|元SP診断|RMW診断|差分|
|---|---:|---:|---:|
|Logic|2248|2751|+503|
|Register total|1415|1415|0|
|CLS|1462|1749|+287|
|BSRAM|16|16|0|
|Setup slack|+3.837ns|**+3.483ns**|−0.354ns|
|Hold slack|+0.708ns|**+0.708ns**|0|
|Setup/Hold違反|0/0|**0/0**|維持|
|配線|完了|**完了**|維持|

対象はGW1NR-LV9QN88PC6/I5、GW1NR-9C。FFはfabric1407＋I/O8。
最悪Setupは`rst_pipe_2_s0/Q → core/endpoint/registers/upload_words[10].ram/storage/DI[23]`。
生成は1回。P&R option/clock/制約/seedを変える探索は行っていない。
pin reportとCST、内蔵PSRAM端子LVCMOS18、両die CS High・RESET Low・DQ/RWDS Hi-Zを確認。
Host外部IO min/maxとPSRAMの物理動作は保証していない。

**資源上の留保：** FF/BSRAM増は避けられたが、診断では+287CLSを要した。
本体の既存4144/4320という使用量に対し、単純置換が収まる保証はない。
診断の資源差を本体にそのまま加算することもsign-offにはならない。
本体用の資源・critical pathは独立に評価し、他GPU機能を削る/無関係な配置調整で
押し込む作業へは進まない。

## 6. 実機手順・停止・復旧

1. 候補とprivate復旧backup/UF2のhashを照合。JTAG1device/ID0x1100481Bを確認。
2. 元KAGURA-9 ABI(0,6)/PIOTransportと画面を確認し、console/PIO所有権を解放。
   GP2..5入力、SCK Low、CS Highを確認。RAM-only adapterを準備。
3. adapterロード後の空きRAMが少なかったため、FPGA投入前に`gc.collect()`を1回実施。
   138096byte空きを確認してから継続。転送の再送やFW変更ではない。
4. COM8を115200 8N1受信専用で先に開き、fs hash再照合後に`--run 2` SRAM Programを1回。
   Finished、4.05s。readback verifyを行ったとは主張しない。
5. ISO2/status0/case2/4lanesを照合。4B write→echoを1回。全6点とHostが一致。
6. 追加pattern、長転送、再arm、Controller要求、PSRAM転送を行わず停止。
7. GPIO解放後、`--run 1`で既存FPGA FlashからKAGURA-9をSRAMへ復元。Finished、0.49s。
8. RP2040全2MiB再hashが投入前/backupと一致。単一raw REPL接続を終了。
9. 通常soft resetで元bannerを確認。console last_error=None、paused=False。
   5秒間の保存PNG5枚は全て同一で、以前復旧確認したFF試験後の画面PNGともbyte単位で一致。
   これを今回のHDMI復帰確認として記録し、新規のhard resetや追加試験は行っていない。

RP2040全2MiBの前後hash：
`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`

hashは診断終了/FPGA復元後、通常soft reset前の照合。soft reset後の再読出しとは区別する。
SRAM投入1、復元1、再試行0、FPGA/RP2040 Flash書込み0、FW/device file変更0。
KAGURA-9復元済みで、実機操作は終了した。

## 7. 未完了と次の判断

今回の3構成の結果は、uploadのnative partial write依存を外す方針を支持する。
元SPの正確な故障機序と、元の実PSRAM4B/64B破損の全ての原因を確定したものではない。

次は、このRMW方式のより広いHost窓/境界/長さと、独立READ応答のbulk capture/downloadを
診断専用構成で確認する。本体統合は別branchの資源/STA評価を伴い、元のSTA合格構成を
保護したまま行う必要がある。実PSRAMはHost入力/出力経路を確認した後に再評価する。

統合ゲートは全回帰、wrap12件、Controller272ケース、RX32、HDMI/PCM/BLIT/cursor、
Standard Setup>=+0.100ns、setup/hold違反0、全配線、外部PSRAM I/O。今回の限定PASSで
Releaseに昇格しない。`release_ready=false`、元DO_NOT_PROGRAMを維持する。

## 8. 証跡

- PC：`build/host-window-observe/sim-rmw/`、mask test/CSR window/QSPI/negative gate logs。
- 生成：`standard-rmw/`内のsource manifest、inputs、timing、pin、gate、extra-audit。
- 実機：`hardware-rmw/`内のraw REPL、UART136B、decoded/result、hash、GPIO解放、
  SRAM投入/復元、soft reset、console状態、HDMI PNG/ログ、evidence manifest。
- [機械可読結果](evidence/host-window-rmw-2026-11-05.json)、
  [全UART hex](evidence/host-window-rmw-uart-2026-11-05.hex)。private復旧imageは公開しない。

元GPU fs、過去4B PASS fs、製品upload leaf/PHY、元worktree DO_NOT_PROGRAMは再hash一致。
製品RTL、ABI、製品SDC/CST、本体STAアーキテクチャは変更していない。
