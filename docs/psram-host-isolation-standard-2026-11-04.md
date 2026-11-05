> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PSRAM独立診断案A：Host/CSR専用候補の作成・Standard評価

後続の単回実機評価は**upload echoでFAIL、KAGURA-9復元済み**。
[2026-11-05の実機結果](psram-host-isolation-hardware-result-2026-11-05.md)。
以下は投入前の作成/PC検証記録。内部STAのPASSは維持するが、実機合格ではない。

2026-11-04。前報告への「承認するので進めてください」を受け、案Aの残りの実装、
PC検証、新規Bitstream生成を実施した。**実機SRAM投入は未実施。Flash/FW変更なし。**
前報告で区別した投入前の結果提示をここで行う。

## 結果

**案Aの内部STA・PC機能・端子/非選択監査はPASS。実機のHost/CSR正当性は未確認。**
PSRAMには転送しない構成なので、この候補でREAD/WRITEの物理正当性を証明することは
できない。元の4B FAIL、32B wrap以外の破損、実ダイ/CA45/初期化の課題は継続する。

最終候補：
`build/host-isolation-standard/candidate-v2/impl/pnr/host_isolation.fs`

SHA-256：
`e64886ab3b80342d628b2f89655f95a759e4b00b12ead91c6c8b4cbf3cb6a3e2`

|項目|観測値|
|---|---|
|Tool / device|Gowin Standard V1.9.12.04 / GW1NR-LV9QN88PC6/I5、GW1NR-9C|
|clock|27MHz入力、PLL system54MHz、PSRAM CK生成なし|
|Place / Route|1 / 2。探索・seed sweepなし|
|Setup / Hold|**+2.071ns / +0.708ns**|
|Setup / Hold違反|**0 / 0**|
|配線|完了、Bitstream生成完了、ERROR/unroutedなし|
|Logic / Register|4535 / 2412（fabric2404＋I/O8）|
|CLS|2589 / 4320|
|BSRAM / DSP|16 / 26、4 / 10（tool report単位）|
|PSRAM出力|両die CS High、CK Low、CK# High、RESET Low|
|PSRAM DQ / RWDS|全18本Hi-Z。合成後TBUF OEN=VCCを検査|
|端子|CSTとPnR pin report一致、PSRAM内部端子LVCMOS18|
|品質範囲|内部STAと静的非選択。外部Host IO min/max・実機は未評価|
|状態|`hardware_tested=false`、`release_ready=false`、SRAM投入は別承認|

最悪Setup：`core/trace/state_1_s1/Q → core/trace/crc_29_s0/D`。
最悪Hold：UART divider内。Recovery/Removalのworst tableは本reportに存在せずnull。
これを独立したreset timing保証とは扱わない。
PLL未使用CLKOUTDのwarning1件があり、機能未接続。SDC対象不存在のエラーはない。

## 構成と観測可能範囲

製品のSPI/QSPI adapter、Host dispatch、CSR/upload SP、commandsを無改変で再利用。
GPU core、scanout、HDMI、音声、製品burst Controller/PHYはインスタンス化しない。
Host endpoint内commandsには従来のcommand decode/fill helperが残る。診断専用に
製品RTLの機能を削除/最適化せず再利用したため、16個のupload SP等の資源を消費する。
通常のGPU起動クリア/描画/音声は実行しない。

新規board topとcoreは、die0/1を常に非選択/reset保持。SD端子もHi-Z。
生成netlistの各OBUF定数、全TBUF無駆動、内部PSRAM端子の自動割付/LVCMOS18を監査。
これは合成/PnR証拠であり、padの実測ではない。

診断bank CSR32..38は `ISO1`、status、test ID=1、LANES=4。
互換base bankのKFB1/ABI/capabilityは既存endpointから返るので、必ずISO1を先に照合する。
この候補に対しGPU/カーソル/音声等のcommandを試さない。

1. Hostが送った4Bをupload窓からechoする。
2. 300032/4B WRITE要求をstub境界で受理してaddress/words/mask/TX512をfreeze。
   UARTのPDT1 source2で136B出力する。
3. PC側が第1frameのCRC/metadata/dataを検証するまでREADへ進まない。
4. 同address/4B READ要求に対し、PSRAMを使わず独立address式の応答を注入する。
   `((address+i)*13+0x5b)&255`。先頭4Bの期待値は**5B 68 75 82**。
   source3 frameに実stub応答を保存し、download窓→Host受信と比較する。
5. 要求数2でfreeze。追加memory要求を受理せず、再試験にはresetが必要。
   予期しないaddress/長さ/順序/使用byte maskはfault、最初の要求後でもfreeze。

snapshotは同一edgeの20recordsで、先頭16bit cycleは全0。継続波形ではない。
READ/WRITE snapshotの間、UARTがbusyなら新しい要求を受理しないため上書きしない。
UARTは54MHz/DIV469、計算baud115138.6（115200比約−0.053%）。
1frameは1360bit、約11.812ms、合計約23.624ms。実測baudではない。

案Aで独立に確かめる境界は、Host送信→upload echo、Controller相当要求受理、
独立応答→download→Host受信。CSR個々の受理時刻・PSRAM CA/TX/RXはこの候補の
直接trace対象ではない。echoと要求snapshotが一致しても実PSRAMのWRITEを保証しない。

## mask条件の追加発見

観測対象の実ドライバ`Device.write_bytes(300032, ED0F2143)`はmaskを
**FFFFFFFFFFFFFFF0**にする。過去独立probeは全0。使用する先頭4Bはどちらもunmask、
後続60Bはこの4B要求では転送されない。したがってmask全64bitの差だけで原因とは言えない。
今回の実機FAILでControllerに実際に受理されたmaskは引き続き未観測である。

前報告の条件表にあった「今回driver意図0」は不正確であり、上記に訂正する。
新診断coreは先頭4bitだけを検査し、未使用byteのmask差を不正要求と扱わない。
製品Controller/PHY/driverは変更していない。

## PC検証結果

|検証|結果/範囲|
|---|---|
|pin-level統合SPI正常|ISO1、ED0F2143 echo、WRITE/READ、実UART272B、freeze PASS|
|pin-level統合QSPI正常|同上、実driver同等WRITE maskでPASS|
|QSPI異常address|300036に対しerror4/fault、1frameのみ、後続要求なし PASS|
|Standard付属SP primitive|同版simlibのSP moduleを未改変抽出してQSPI統合試験PASS。behavioralのUART272Bと完全一致|
|PDT1 decoder4件|実UART payload/metadata/CRC、fault frame、欠損/破損/余分frame/CRC正しい意味矛盾のreject PASS|
|RAM診断関数4件|実Device driverのmask、独立RX、識別不一致でWRITEなし、第1trace異常でREADなし、download異常のXOR記録 PASS|
|前段PC環境|2patternのRX32 pairモデル、recorder、Host4..64Bの既存証拠を維持。今回の統合topで大量patternを再試験したとは扱わない|

Vendor bytesはrepoソースへ追加せず、build/内だけに抽出。SPモデルはデジタルモデルであり
PVT/電源投入時のPSRAM保証にはならない。実機RP2040でRAM関数を実行したこともない。

PC正本：`build/psram-isolation/board-sim/`内のrun/build logs、`uart-l*-b*.bin`。
最終source2 WRITE payloadはED0F2143、mask FFFFFFFFFFFFFFF0。
source3 READは5B687582、mask0。UARTのCRCはPython zlibと一致。
機械判定は候補directory内`diagnostic-gate.json`、compile入力は`inputs/`に保存。
最初に収集した広いsource manifestはPC helperも含むため、合成入力の一致検査は
SV/Tcl/CST/SDCに限定し、更新したRAM helper等の最終hashは別evidenceへ保存する。

## 生成履歴と制約

|候補|結果|選択|
|---|---|---|
|v1|Setup+3.066/Hold+0.708、違反0/0、CLS2588、FF2412。全mask0を要求する過剰な診断guard|superseded、投入禁止。生成物/入力を保存|
|v2|guardを使用4Bだけに修正、PC再検証後に1回生成。Setup+2.071/Hold+0.708、違反0/0|最終候補|

Place/Route/clock/制約を変える探索はしていない。機能上の診断条件修正による2回の生成。
元GPUのSTA合格アーキテクチャ/成果物は変更していない。

SDCは27MHz/54MHz clockを明示。非同期Host入力はpad→第1同期FFだけfalse path。
第1→第2同期FFや内部logicはtimed。Host/UART/LED出力は非同期protocolとして例外。
Hostの外部基板min/max closureを主張せず、最初の実機は**QSPI SCK1MHzだけ**とする。
PC pin-level試験も1MHz。PSRAMの外部タイミングは「非アクセス」であり、PASSとしない。

## 別承認後の最初の実機試験

実施範囲はこのv2のSRAM投入1回、ISO1-1の4B1case（WRITE要求1＋READ要求1）だけ。
RP2040/FPGA Flash、FW、boot.py、既存復旧像は変更しない。新たなPSRAM WRITEは0。

1. 前報告のKAGURA-9画面、COM/JTAG識別、全Flash/復旧hash照合、PIO所有権解放を行う。
   既存復旧経路が利用可能でなければ投入しない。
2. UART COM8を115200 8N1受信専用で先に開き、Programmer SRAM Program `--run 2`を1回。
   指定fs SHA256を投入直前に再照合する。Flash erase/program禁止。
3. RP2040は既存transportをRAM上で1MHz設定。追加driverはRAMのみ。
   初期ISO1/status0を確認。想定外のUART事前出力・識別異常で停止する。
4. `host_case.run_write`でechoとWRITE要求まで。raw REPL応答とUART第1frameを永続化。
   PCでCRC・ID1/source2/address300032/words1/mask/payloadを照合。
   ED0F2143不一致・timeout・余分byteならREADしない。
5. 第1frame PASS後だけ`run_read`。Host独立期待5B687582とsource3 frameを照合し、
   statusのcount2/frozen/trace idleを確認。成功でも次pattern/周波数へ進まない。
6. 全経路の不一致/timeout/識別異常で即停止。raw/errorを保存し再送なし。
7. 成否によらず既存FPGA Flashから`--run 1`でKAGURA-9をSRAM復元。
   QSPI解放→RP2040全Flash再hash→通常soft reset→banner/HDMI復元を確認する。
   復元未確認なら次試験へ進まない。

Hash照合は次回preflightで実施する。この作業中にCOM/JTAGを開いたり、Flashを
再読みしたりはしていない。保存された過去hashを今回live再検証したとは主張しない。

案Aで不一致ならHost/CSR境界を優先して調べる。全一致でも元本体の先行負荷・配置差、
PHYのWRITE/READは未解決で、案Bを別途選択する。案AのPASSを製品Releaseへ昇格しない。
