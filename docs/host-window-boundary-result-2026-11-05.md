> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Host/CSR破損の境界特定：SP出力で初めて不一致、FF対照は一致

後続：[全word RMW診断も4Bの全6点で実機一致](host-window-rmw-result-2026-11-05.md)。
以下のRMW未実施という記述は、SP/FF比較時点の履歴。

2026-11-05。ユーザーの継続調査指示に基づき、追加2候補を各4B1ケースずつ観測した。
**今回の最初の破損境界は、CSRで受理した正しいbyte列からupload SP出力までの間。**
同じ観測回路のupload leafだけをFFに置き換えた対照では、全6点とHost受信が一致した。
両試験後にKAGURA-9へ復元し、Flash hashとbanner/HDMIを確認。追加実機操作は終了した。

製品GPU/Controller/PHY/SDC/CSTと元のSTA合格成果物は変更していない。
FF置換は診断専用であり、製品への修正統合や実PSRAM試験を行ったものではない。

## 1. 観測値（独立UARTとHostの比較）

期待4Bは全て`ED 0F 21 43`。両者とも同じPIO設定1MHz、4lanes、同じRAM adapter、
同じCSR操作順序、同じclock/pin/Place1/Route2。pad周波数・波形は未測定。

|観測境界|SP版 実測|FF対照 実測|
|---|---|---|
|transportが受理したwrite 4byte|**ED 0F 21 43**|ED 0F 21 43|
|CSRが受理したwrite 4byte|**ED 0F 21 43**|ED 0F 21 43|
|最後のCSR write受理から8system cycle後のupload出力|**AF 0F 21 43**|ED 0F 21 43|
|最初の窓READ要求受理時のupload出力|**AF 0F 21 43**|ED 0F 21 43|
|CSRから返した4byte|AF 0F 21 43|ED 0F 21 43|
|transportへ渡した応答4byte|AF 0F 21 43|ED 0F 21 43|
|Host受信|**AF 0F 21 43**|**ED 0F 21 43**|
|XOR|42 00 00 00（計算2bit）|00 00 00 00|
|記録数|RX/write/read/CSR response/transport response 各4|同左|
|protocol flags / UART header fault|0 / false|0 / false|

UARTはPDT1 source4・test ID2、136B、CRC32一致。HostのQSPI受信とは別のFTDI UART経路。
記録器はデータを期待patternから再生成せず、各実interfaceをtapして保存する。
RX/CSR受理の正しさと、upload出力で既に誤っていることを直接比較できた。

8cycleは54MHz設定からの計算で約148.15ns。これは4番目のCSR write受理からの
間隔であり、padで実測したRAM timingではない。READ要求時にも同じ誤値なので、
単にHostがSP出力安定前の1cycleだけを読んだという説明を優先する根拠は乏しい。
ただしSPの実際のDI/WRE/ADを今回直接snapshotしたわけではない。

## 2. 到達した切り分けと限界

**観測済み事実：** SP版の今回の不一致は、Host送信意図→transport受理→CSR受理までは
伝搬せず、upload出力で初めて確認された。その後のCSR/transport/PIO受信は、その誤値を
そのまま返した。今回の差分をQSPI返送時の新たな誤りで説明する必要はない。

**強く支持される範囲：** CSR受理後のcommit、SP入力制御/データ、SP設定、SP物理実装、
SP出力に調査対象を限定できる。FF対照は、この範囲のうちSP leafへの依存を支持する。

**未確定：** 動的byte-enableのデバイス対応、DI/WRE/ADのtiming、tool mapping、
SPの動作条件のどれが直接原因かは未確定。FF置換でも配置が変わるため、SP自体の
シリコン不良や単一信号の故障と断定しない。各variant1ケースなので再現率/PVT保証もない。

|元の問い|今回の回答|
|---|---|
|Q1 Host WRITEデータはどこまで正しいか|今回の4Bはtransport/CSR受理まで実測一致。SP出力では不一致|
|Q2 READ結果はどこから壊れるか|Host窓echoでは、CSR READ応答生成前のupload出力が既に誤り|
|Q3 元PSRAM試験はREAD/WRITEどちらか|まだ未確定。今回見つけたHost窓問題でWRITE前に壊れ得るが、元試験の実TX値は未観測|
|Q4 パターン/配置依存|同じED0F2143でも以前ISO1は4F272143、今回SPはAF0F2143、FFは一致。固定不変の誤値ではない。原因が配置か起動かは未分離|
|Q5 PHY timing仮説はどうなるか|今回のHost窓故障にはPSRAM/RWDS/CK/CAが関与しない。Host窓修正前にPHY位相探索へ進まない|
|Q6 32B分割後の追加破損|wrapと独立したHost窓破損の存在を確認。元64B残差の全てを説明したとは言わない|
|Q7 最小修正|uploadのnative byte-enable依存を除く局所案が優先。製品統合/外部PSRAM正当性は別ゲート|

## 3. 診断差分と品質ゲート

診断専用`kagura_fb_host_observe`は製品Hostのコピーに観測output/assignだけを追加。
逆変換すると元ソースに一致することを生成scriptで検査した。元のregisters/adapter/
commandsは無改変。通常GPU、PSRAM Controller/PHYを含めない。

追加観測は上表の6点、カウンタ/flags、arm/freezeのみ。CSR39への1回のarm後、
4byte write/4byte echoを記録して136Bを1回送信し、再armを拒否する。
完了しなければ54Mcycleのwatchdogで部分snapshotとflagsを保存する。
PC試験では正常SPI/QSPI、watchdog、再arm拒否、CRC/破損packet rejectを確認。

|項目|SP版|FF版|
|---|---|---|
|Tool/device|Standard V1.9.12.04 / GW1NR-LV9QN88PC6/I5|同左|
|Setup / Hold|**+3.837 / +0.708ns**|**+4.632 / +0.708ns**|
|Setup/Hold違反|0/0|0/0|
|配線|完了|完了|
|Logic / total Register|2248 / 1415|2309 / 2439|
|CLS|1462/4320|2083/4320|
|BSRAM|16/26|0（PnR reportは0行省略、netlistにBSRAM primitiveなし）|
|DSP|0（同様にprimitiveなし確認）|0|
|PSRAM I/O|両die非選択/reset保持、DQ/RWDS Hi-Zをnetlist/pinで確認|同左|
|外部Host IO|非同期oversampling。基板min/maxは未保証|同左|

SP SHA256：
`08bb172eb68f10ea03ad3ab362ad03a0d43cc52f054be2db0b49da8f3b234752`

FF SHA256：
`5f10672147b575d226e788c59e72df6a2a696908382b5578cd3b9165487c7848`

両compile manifestの共通入力hashは全一致。異なる入力はupload leafと、そのleafを選ぶ
build Tclだけ。clock/SDC/CST/P&R設定は同じ。ただし配置自体の同一性は主張しない。
FF版はlogical write-hold/read behaviorを維持し、実FF数差1024は32bit memory＋32bit
read resultを16word実装した値と一致した（計算）。この資源増を本体へそのまま戻さない。

## 4. byte-enable仕様とモデルの重要な相違

現leafはSP BIT_WIDTH=32、AD[3:0]にbyte_enableを接続し、CPU byte writeのDIを
同じbyteの4回複製にする。これが意図通り動くには、そのデバイス/構成がnative byte writeを
サポートしている必要がある。内部STA PASSだけではその機能対応を確認できない。

**一次資料：** 現行メーカー英語版
[DS117-3.2.4E §2.5.4、印刷p.29](https://cdn.gowinsemi.com.cn/DS117E.pdf)
ではbyte-enableの対象をGW1NR-2/2B/2C/4Dに限定しており、GW1NR-9は列挙されない。
対象C版への例外は今回確認できていない。このためGW1NR-9Cで動的AD[3:0]方式を
安全な実装とする仕様根拠が不足している。これは主仮説を強める資料で、今回の各誤bitが
その仕様制限だけで一意に説明できたという意味ではない。

以前参照したメーカー発行の旧版
[DS117-2.9.3E §3.5.4、印刷p.33](https://dl.sipeed.com/fileList/TANG/Nano%209K/6_Chip_Manual/EN/DS117-2.9.3E_GW1NR%20series%20of%20%20FPGA%20Products%20DataSheet.pdf)
は系列一般の説明で、後版の機種限定注記を含んでいない。
系列全体の説明を対象デバイスの対応保証に広げていた点は、今後の検証ゲートで訂正する。

Standard付属UG285-1.4E（2025-10-17）にもdevice/revisionに依存するBSRAM構成注記がある。
同guideだけの一般的SP幅表で、個体のbyte-enable対応を保証しない。
版・対象C revision・IP生成設定・実primitive mappingはメーカー確認事項として残す。
PDF本文のWeb直接取得が403/timeoutとなったものは、取得成功とは記録しない。
上記DS117の機種限定注記は公式検索インデックスの当該節全文でも確認した。

**ローカル一次コード：** Standard付属`simlib/gw1n/prim_sim.v`のSPは、dwidth32時に
AD[0..3]ごとに8bitを更新する汎用モデル。対象device capabilityを選ぶparameterはない。
そのため、モデルがbyte-enableを実行してPASSしても、GW1NR-9Cがその構成を
実装できることの証明にはならない。故障値をモデルへ書き込むのではなく、対象deviceの
capability gateを別に設け、未対応/未確認構成を合格扱いにしない必要がある。

## 5. 最小修正方針（製品未変更）

**方針：** PHYを変える前にupload SPでの動的native byte-enable依存を外す。
FF全置換は診断対照としてのみ採用した。本体はCLS4144/4320であり、今回のFF増を
無評価で統合する余裕があるとは言えない。現在のSTA合格アーキテクチャへはまだ戻さない。

局所案として、既存word値と新byteをmergeし、SPへ常に32bit全wordを書くRMW leafを
`diagnostics/host-window-observe/fix-candidates/`に分離して作成した。
byte-enableに頼らず、SP16個とparallel512出力interfaceを維持する可能性がある。

この案はpartial write前にSP read結果が安定している必要がある。既存CSRの
write_recovery/安定待ちとの組合せを、vendor SPモデル＋既存
`tb_fb_register_window`でPC検証しPASS：即時byte write/readback、6 READ completions、
18 COPY captures、warm reset。**RMW案の合成/P&R/STA/実機は未実施**。
FF版の実機PASSをRMW案へ流用しない。SPのDI/WRE/AD traceや対象仕様確認も残る。

次の順序：

1. 対象GW1NR-9Cのbyte-enable/32bit SP構成を一次資料・メーカー回答で固定。
2. RMWの安定待ち契約をPCで拡張し、DI/WRE/ADの独立port観測を設計する。
3. 同一4Bの診断専用RMW候補を別ゲートで合成/STA/実機確認する。
4. Host uploadが保証できた後に、独立READ注入/download bulk captureも確認。
5. その後に元のPSRAM WRITE/READとguardを再評価し、PHY固有の残課題を分離する。

本体統合時は別branchで全回帰、wrap12件、Controller272ケース、RX32、
HDMI/PCM/BLIT/cursor、Standard Setup>=+0.100ns・違反0/全配線、外部PSRAM I/Oを再要求。

## 6. 実施範囲・復旧・保持

今回の継続指示後：新規診断候補2、SRAM投入2、復元2、各1ケース。
SP不一致後の同候補再送/追加READなし。復旧確認後にFF対照を実施し、FFの1ケース後も停止。
新たなPSRAM転送0、FPGA Flash書込み0、RP2040 Flash書込み0、FW/device file変更0。
private復旧像を公開していない。

各試験の投入前とFPGA復元後（通常soft reset前）のlive全2MiB Flash hash：
`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`、全て一致。
既存UF2のhashとGPIO/PIO解放、JTAG1device/ID0x1100481Bも確認。
通常soft resetで元banner、console last_error=None/paused=False、HDMIの復帰を確認した。

復旧映像の初回プレビューが不完全だったため途中画像も保持し、最終FF復旧では
5秒連続キャプチャの5枚を保存。保存PNGのhashは全5枚同一で、最終画像はbanner/REPL。
復旧確認のため通常REPLで状態を読んだが、診断要求の再開やhard resetは行っていない。
途中プレビューの原因をFPGA故障や特定codecの問題と断定しない。

正本：`build/host-window-observe/{standard-sp,standard-ff,hardware-sp,hardware-ff}/`。
各hardware directoryの`uart-full.bin`、`decoded.json`、`result.json`、
`evidence-sha256.json`、raw REPL/Flash hash/復元/HDMIを保持。
[SP結果](evidence/host-window-sp-2026-11-05.json)、
[FF結果](evidence/host-window-ff-2026-11-05.json)、
[比較と入力差分](evidence/host-window-comparison-2026-11-05.json)を公開可能な証跡として保存した。

元GPUのfs SHA `a99c5f...31cf`、過去4B PASS fs `f6619b...62ac`、
元DO_NOT_PROGRAMのhashは一致。`release_ready=false`を維持する。
現時点で得たのは破損境界と局所修正方針であり、PSRAM READ/WRITEの合格ではない。
