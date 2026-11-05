> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD PSRAM 独立診断・証拠比較報告

最新追補：[upload全word RMW案の生成・実機4B一致](host-window-rmw-result-2026-11-05.md)。
本体未統合・実PSRAM未評価。Release禁止は継続。

最新：[CSR受理後→upload SP出力で破損、FF対照は一致](host-window-boundary-result-2026-11-05.md)。
主仮説はupload SPのbyte-enable構成/適用仕様、port timing。PSRAM固有原因と同一とは未確定。

後続承認により案Aを完成・生成した。[Standard評価と投入前の結果報告](psram-host-isolation-standard-2026-11-04.md)。
さらに[2026-11-05の単回実機試験](psram-host-isolation-hardware-result-2026-11-05.md)で、
PSRAM非介在のupload echoがED0F2143→4F272143となり停止、KAGURA-9復元済み。
以下の作業状態は最初のPC調査時点を記録する。Release禁止は継続。

2026-11-04。対象は `eval/rx32-scanout-01`。本報告の作業はPC上のみ。
新しい合成・P&R・Bitstream生成・COM/JTAGアクセス・実機試験は実施していない。
製品RTL、元診断RTL、SDC/CST、Flash/FW、復旧像を変更していない。
`release_ready=false`、既存 `DO_NOT_PROGRAM.txt` を維持する。

表記：**観測**は保存証跡または今回のPC実行、**計算**はRTL/数式からの値、
**仮説**は未実証の説明、**未確認**は測定または仕様同定が必要な項目。

## 1. エグゼクティブサマリー

**観測：4B FAILの原因は未特定。WRITE/READのどちらかはまだ分離できない。**
今回の300032/4Bは32B境界を跨がないため、境界wrapだけでは説明できない。
過去4B PASSと今回FAILのPHYソースは同一だが、Controller・パターン・Host経路・
先行転送・配置が異なる。同じPHYソースは同じpad timingの証明ではない。

今回、既存Controller/PHYを両系統ともコピー保存し、RX32 Controllerで過去の
`F1 16 3B 60`と今回の`ED 0F 21 43`をPDR1シリアル波形までPC比較した。
両者とも理想pairモデルでPASS。既存モデルに今回の故障を予測する能力は確認できない。
Host/CSR用には独立応答注入stub、境界観測用には選択式有限長recorderを追加した。
詳細と再現手順は[診断環境](../diagnostics/psram-isolation/README.md)。

**最初の実機候補はHost/CSR専用・PSRAM非選択構成（案A）。**
Host送信→upload→Controller要求と、独立ROM応答→download→Host受信を分離する。
その後、案Bで4B・CA・TX/RX pairを記録する。位相やCR0を同時変更しない。
完成したboard用トップ、Standard/外部I/Oゲート、投入ハッシュはまだない。
新規Bitstream作成とSRAM投入は別途承認が必要。

| 問い | 現在の回答 |
|---|---|
|Q1 WRITEはどこまで正しいか|実機はHost意図のみ確認。CSR受理・Controller TX・PHY DQは未観測。今回のPC独立経路は要求境界まで検証|
|Q2 READはどこから壊れるか|実機Host受信で不一致確定。PHY入力・RX512・窓を遡る証跡なし|
|Q3 READ/WRITEのどちらか|未確定。同じPHY経由のwrite/read一致も相殺誤りを排除しない|
|Q4 再現性・依存性|今回は1回のみ。パターン・起動・順序依存を評価できない|
|Q5 整合する仮説|Host窓、WRITE先頭pair/OE/mask、READ先頭pair/固定捕捉、初期化/先行負荷、CAを維持|
|Q6 分割後の追加破損|今回の非cross 4Bも壊れる。分割の機能正当性と物理正当性は別。元64B残差との同一原因も未証明|
|Q7 最小修正|原因確定前は選べない。初めて壊れる境界を観測後、当該境界だけ修正し単独比較する|

## 2. 過去4B PASSと今回4B FAIL

出典：[過去4B](psram-4b-hardware-result.md)、[今回4B](rx32-hardware-result-2026-11-04.md)。
保存fsを今回再hashし、両方とも記録値と一致。

|条件|過去PASS|今回FAIL|
|---|---|---|
|Bitstream SHA256|`f6619b747171c92ea9fdb0aa562acfadfdf7af37940d2d6286b9535eebca62ac`|`a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`|
|Controller SHA256|`872e921d306a0fc7a1fb1eeb7d3cddcdccdffd9b66e441fe072b8bc74e931544`|`4d2189aadf187a40df48e25fe892f28db7a3c8569ade747dfcb29bdff7bb8f5c`|
|PHY SHA256|`e20611d49ed5ebebb84db01cbee732f9198db57ec4e4ff8ef43b1a84b69d72c0`|左と同一|
|byte address / WRITE・READ長|300032 / 各4B|300032 / 各4B|
|Expected / Actual|F1 16 3B 60 / 同値|ED 0F 21 43 / 0D 23 21 43|
|mask|RTL定数0、pad未観測|driver意図FFFFFFFFFFFFFFF0（後続調査で訂正）、要求・pad未観測|
|CA|両者 `rd,registers,1,halfword[31:3],13'b0,halfword[2:0]`|同一式。pad未観測|
|LAT / RDL / CR0|14 / 6 / 8F1F|同じRTL設定。実CR読出しなし|
|CK周波数・位相|54MHz / 67.5°設定|同設定。両者実pad位相未測定|
|READ捕捉|LAT+RDL後のregistered enableでIDDR pair捕捉|同じ固定捕捉方式、RX32 word tap追加|
|RWDS|PHY IDDR存在、topでは出力未接続|Controllerの有効判定には不使用。今回実測なし|
|reset/init|独立PLL lock同期reset、INIT=4096、半分RESET Low、CR0 WRITE|pixel/system lockからreset、同INIT/CR0。実pad波形不明|
|起動待機|初期化後十分待ってGP7 trigger、正確な時間は不明|READY後identity/FENCE→試験、正確な時間は不明|
|先行PSRAM転送|初期CR0のみ→単独WRITE/READ|画面2面クリア・PCM準備等のboot転送、scanout/音声のアクセスを含む|
|Host順序|RP2040所有権解放→GPIO trigger→UART受信|RAM driver→identity→FENCE→upload→WRITE→READ→download|
|結果取出し|Host窓不使用、UART PDR1 149B|SPI/QSPI CSR・staging窓・Host driver|
|配置/内部STA|CLS824、FF1249、+6.276/+0.708ns|CLS4144、FF4910、+0.898/+0.530ns|
|初期化条件の一致|ソフト設定の部分一致のみ|起動経路・先行転送・実pad条件の同一性は成立しない|

SHAは過去`source-manifest.json`と今回`build/analysis/standard-input-manifest.json`にも照合。
保存先は `build/psram-isolation/baseline/{pass,fail}`。root branchは
`bringup-dynabook-standard`、評価branchは別worktreeであり、混用を避ける。
Controller変更は32B分割のPREPARE状態、chunk間RX slot継続、RX32 tap追加。
4Bではchunkは1個だが、要求からCAへのcycle数・配置は同一ではない。

**計算：** XORは`E0 2C 00 00`、2byte/6bit。先頭pairだけの不一致はREADの証明ではない。
**未確認：** 実際のCA・mask・write data、初回read以前の他clientとの順序、電源履歴。

## 3. Controller/PHY/Hostデータフロー

WRITE：Host bytes→`kagura_spi_adapter`→host内registered dispatch→
`kagura_fb_registers` byte commit→16個のupload SP→`kagura_fb_commands`
要求（byte address[21:2]、words、mask）→arbiter→burst Controller TX512→
16bitずつshift→PHY fabric register→ODDR→IOBUF→PSRAM。

READ：PSRAM DQ→IOBUF→IDDR（system clk、RWDS strobe不使用）→
Controller one-hot RX pair→RX512→commands read_result→registers bulk capture→
SP出力安定待ち→CSR窓group/lane選択→adapter→Host。
RX32は同じ捕捉pairから2pairを組み立てる別tap。Hostはlegacy RX512経由。

**観測/RTL：** 窓は64B、pointerは7bit。upload/downloadは別々の物理RAMではなく
同じupload SPをREAD結果でbulk更新する。busy中の窓/descriptor操作は拒否する。
従ってupload echoだけではREAD bulk captureやdownload経路を証明しない。
mask=1はwrite禁止。pairは低byteがrise、次byteがfall、RXは`{fall,rise}`。

32B契約は `min(remaining,8-cursor[2:0]) words`、絶対境界でCSを分割。
RX512 slot/TX/maskはchunkを跨いで継続。最終CS-high recovery後done。
診断用にController/PHYの内部FSMを変更しない。

## 4. 仮説と優先順位

優先度は原因確率の断定ではなく、少ない観測で排除できる順序。

|優先|仮説|整合する点|識別観測|
|---|---|---|---|
|1|Host upload/窓/descriptorまたはdownload|独立PASSはこの経路を迂回|PSRAM非選択でTX受理snapshot、独立RX注入|
|2|WRITE先頭pair/OE/RWDS mask/CKずれ|先頭2Bに局在、同PHYでも配置差あり|CA/TX pair・実OE、既知内容への別読出し経路|
|2|READのfirst pair/固定RDL/位相|先頭pair不一致、RWDSを捕捉に不使用|pre-data含むDQ/RWDSとcapture slotの同時記録|
|3|初期化・turnaround・先行負荷|独立初回と多数転送後で条件差|reset/CS recovery、初回/再READ/別address挿入を別ケース化|
|3|CA/実CR/ダイ仕様不一致|参照仕様CA45との差、実CR不明|register read専用診断、CA全48bit、独立guard|
|低：今回4Bの単独説明|32B wrapのみ|既存cross実機証拠は強いが今回crossなし|今回4Bをwrap故障と統合しない|

同一addressへの再READで値が変わればREAD/初期化を優先できるが、READでの破壊や
別client writeを排除する必要がある。繰返し同値でもWRITE故障とは確定しない。

## 5. Host/CSR独立診断

**実装済みPC部品：** `psram_host_stub.sv`は実endpointのController応答位置を置換。
WRITE要求のaddress/words/data/maskを保存。READはWRITE echoではなく独立式
`((byte_address+i)*13+0x5b)&255`を返す。PSRAM Controller/PHYをインスタンス化しない。
生成testbenchは既存pin-level SPI/QSPI tasksを使い、GPU coreを完全に除外する。

4/8/16/32/64B、300060（32B境界直前）、upload echo→WRITE要求比較→独立READ応答→
Host窓比較を実行。不正長0はRANGE_ERROR=3かつmemory requestなし、pointer64のwriteは
BUFFER_ERROR=5、reset中requestなし、reset後全64Bゼロを確認する。
初回テストは不正長の期待codeを2と誤記しFAIL。実装契約3に修正して再実行した。
続く窓端検査では先のsticky errorが残っていたため、独立検査前にCSR7でclearするよう
診断側を修正した。最終SPI/QSPI両方がPASS。製品RTLの修正はない。
busy途中reset・全mask組合せ・全SPI速度の網羅は未実施。

**実機案A仕様：** 既存host endpoint＋このstub＋snapshot/serializerのみ。
board wrapperでdie0/1 CS=High、CK=Low/CK#=High、RESET=Low、DQ/RWDS=Hi-Zに固定。
通常GPU/boot転送を含めない。FPGA内のstubはmemory commandの有無をカウントし、
CSR窓の各byte受理は選択式recorderで取得。実endpointのABI機能advertisementを
製品機能合格とは解釈しない。診断専用識別をwrapperに追加する設計とする。

## 6. WRITE独立診断

要求受理時にaddress/words/mask/dataをfreeze。WRITE中だけ、CA3pair、
待機前後、data2pair、GAPを含む64cycleを記録する。chunkごとにCAを独立decodeし
Hostオラクルと比較。信号：CS/CK enable、DQ rise/fall、DQ widened TX、
RWDS rise/fall/OE、RESET。論理OEとPHYへ渡すwidened TXを混同しない。

内部CA/TX正当→PHY入力レジスタ正当→ODDR出力正当→PSRAMが受理、は別の命題。
内部traceだけでは最後の命題を証明できない。内蔵dieのpadに外部probeを接続可能か
基板/パッケージで確認が必要。fabric mirror GPIOの波形も実padの代用保証にはしない。

独立address guardをseed/短READ確認した後、target WRITEを1回、独立4B READで位置を
確認する。ただしseed確認も同じPHYである限界を記録する。別の信頼できるread engine
またはpad観測なしにはWRITE/READを一意に分離できない場合が残る。

## 7. READ独立診断

READ CS開始をtriggerし、CA終端からfirst pair前後を含む64cycleのDQ IDDR、RWDS IDDR、
capture_enable、capture_slotを記録。slot0/1をRX512/Host先頭4Bと突き合わせる。
capture_slotは32bitなのでRX traceの32bit内にはslot番号＋validをencodeして入れる。
RWDS IDDRはsystem clock観測でありRWDS基準の連続時間波形ではない。

最初は同じ4B1件のみ。PASS後に別承認単位で、連続READ、別address挿入、開始address変更、
長さ変更、reset後初回/2回目、WRITE直後/待機後、pattern変更を1変数ずつ比較する。
初回FAIL時は直ちにfreezeし、同じ実行内で自動再READしない。
再現性確認は事前に許可した別実行で行い、失敗条件も全記録する。

## 8. 試験パターンと独立オラクル

`oracle.py`は00/FF/AA55/55AA/ED0F2143/43210FED/12345678、walking1/0、
address式、固定seed PRNGをHost側で生成する。FPGAからのread値を期待値にしない。
全4B offset 300032..300060、境界直後300064、300092、遠隔1048576、終端4194240、
4/8/16/32/64Bのplanを生成できるが、実行機能は持たない。
全planの存在は全ケース実施・合格を意味しない。

guardはtargetと別32B blockの前後4B。die終端で片側guardが置けない場合は
離れた安全領域を追加する計画が必要。対象範囲と同じwrap block内だけのguardでは不足。
guardの初期値も独立address式で決め、各物理位置を4B単位でseed/verifyする。
単一開始READだけでPASSとしない。

エラー記録必須：Test ID、fs/FW/source hash、絶対byte address/length、expected/actual、
XOR・byte index・bit数、CA/chunk/mask、選択trace/境界、reset/init/起動履歴、
clock/位相、raw packetと受信時刻、timeout/不完全packet。まず2pattern×4BをPCで確認し、
実機最初は1件のみ。大量planや全アドレスsweepを実行しない。

## 9. 実ダイ・CA45・CR0

**一次資料確認：** [Sipeed公式仕様](https://dl.sipeed.com/fileList/TANG/Nano%209K/1_Specification/Sipeed_Tang_nano_9K_Datasheet_ENV1.0.pdf)
は64Mbit PSRAMを記載。既存Gowin DS117証跡ではQN88Pは2×32Mbit。
本個体のメーカー/ダイ型番/revisionは未同定で、ID/CRの実読出しもない。
[Gowin IPUG525E](https://cdn.gowinsemi.com.cn/IPUG525E.pdf)の公式検索結果は
W955D8MBYAを設定例として示すが、今回本文取得は403。公式IPの実際のreset/init/
sampling設定との一致は未確認とする。

[Winbond発行W955D8MBYA A01-001、2019-06-05](https://www.mouser.com/datasheet/2/949/W955D8MBYA_85C_PKG_datasheet_A01-001_20190605-1760391.pdf)
はメーカー文書の配布コピー。CA45はmemory=0/register=1、CR0[2]は1指定、
CR0[1:0]=11は32B wrap、[7:4]=0001はlatency6、[3]=1はfixed2倍。
8F1Fはこの参照条件ならfixed12、legacy32B wrap。linear化を保証しない。
CR1 Hybrid Sleepはlinear/hybrid burst設定とは別。現RTLのCA45常時1は参照仕様と
一致しないが、未知ダイに対しCA45変更を安全な修正とは断定できない。

register読出しはControllerに公開interfaceがない。診断専用read-only CA engineが必要。
ID値だけでrevisionまで確定できるとも限らない。CR0変更を型番同定と同時に実行しない。

## 10. RWDS/CK/DQタイミング評価計画

**計算値：** 54MHz周期18.5185ns、half9.2593ns、67.5°=3.4722ns。
単純理想波形ではDQ遷移からCKまで3.472ns、次DQ遷移まで5.787ns。
参照setup/hold各0.9nsを引いた2.572/4.887nsは、clock skew・ODDR clock-to-out・
route・jitter・PVTを引く前の予算で、実slackではない。
2cycle GAP=37.037ns。参照tRWR36nsに対し理想余裕1.037nsしかなく、pad CS間隔を
primitive pipeline込みで実測/解析する。INIT4096=75.85µs、半分reset=37.93µs。
参照power-up150µsと同一ではない。SRAMロード後のwarm条件をcold起動へ一般化しない。

**PHY RTL観察：** CK enableはclk FF→negedge clk_ck FF→ODDR。CS/DQ/OEも
それぞれpipelineあり。RESETはglitch防止register。DQ/RWDSのODDRとIDDRは同一clk。
固定RDLの整数cycle変更はsubcycle位相調整ではない。RWDSは診断用のみ。
ODDR TXのfabric経路は既存STAの未保証箇所として別扱い。

評価時はGowin対象speed gradeのODDR/IDDR/IOBUF min/maxと生成clock位相を確認し、
参照ダイのtCSS/tCSHI/tRWR/tDS/tDH、DQ/RWDS tOZ/tDQSQ、最大CS Low、reset回復を
pad時間軸に並べる。unknown dieの数値を確定制約として投入しない。
内部STA0違反は外部input/output min/max、eye、PVT合格ではない。

位相探索はHost経路を排除し案Bの基準結果を得た後の別承認。
提案上限：45/67.5/90°、22.5°step、3variant、各variantは承認済み代表4B2patternまで。
変更はCK位相だけ、LAT/RDL/CR0/周波数は固定。全結果と失敗を残し、最初の異常で
そのvariantを停止・復旧。未実施。幅のあるeyeと起動再現性なしに修正完了としない。

## 11. Simulationと実機の相違

|項目|現pairモデル|必要な次段階|
|---|---|---|
|CA|linearはCA45=1前提|strict参照/未文書許容を別modeで維持|
|wrap|別モデルで絶対32B wrap再現|分割Controllerとの併用、独立guard|
|初回pair/latency|Controllerと共通の固定pair抽象|pin-level CA終端起点、primitive pipelineを独立に表現|
|RWDS|抽象ownership中心|latency通知・preamble・strobe停止・DQ相対遅延|
|CS/reset|protocol状態中心|CSごとの解放・tRWR・power-up/refreshを仕様パラメータ化|
|sampling/PVT|eye/アナログ故障なし|min/max遅延・setup/hold違反を明示検出。機能モデルとは別|

元64Bの32B周期は理想wrapで48/64B一致、残差16B/46bitは未再現。
後続cross実機ではsame-start偽PASS、独立位置旧値残存、wrap先の移動を観測済み。
それでも今回の非cross 4Bと同一故障とする根拠はない。
故障値をモデルへ固定注入して「予測成功」とは扱わない。
仕様で決めた遅延・wrap条件から未使用address/pattern/順序を事前予測し、別実機データで
一致するか評価する。今のPC PASSは論理経路のみ。新pin/PVTモデルは未実装。

## 12. 診断トップ仕様・リソース・PC検証

今回実装した部品とPC harnessはGPUを使わない。新規board wrapper/統合UART trace
packetは設計段階であり、完成Bitstreamはない。過去のprobe topを今回の完成品と扱わない。

recorderはsourceをarm時に固定、trigger後64有効sample、48bit（cycle16+payload32）、
満杯でfreeze、再trigger不可、65536cycleでoverflow freeze。最大3072bit。
同期readで1BSRAM候補、fabricなら最大3072FF相当。実mapping/STA未測定。
WRITE/RX/request/windowのうち一つを選ぶため全信号同時UART出力はしない。
RXとTXを同じトランザクションで同時に必要とする場合は別bankが必要であり、現在の
single-source recorderだけで両方の同時証拠を得たとは主張しない。
要求snapshot512+mask64+address20+words5+write1=602bitがstubで追加。
独立probeの過去CLS824/FF1249を新構成の資源保証には流用しない。

packet設計：既存PDR1の結果149Bを維持し、trace拡張は別`PDT1` frame。
`magic4,version1,source1,case_id LE16,count LE16,flags LE16,records[count] LE48,CRC32 LE32`。
CRCはIEEE reflected（zlib互換）、headerからrecordsまで。実機とPCで同じID/format。
hash/init/clock条件はHost sidecar manifestに固定しraw frame SHAと紐付ける。
PDT1 serializer/decoderの実装・破損packet負テストは次段階であり未完。
既存PDR1はXORでありCRCと誤記しない。

今回のPC検証ログは `build/psram-isolation/`。Verilator 5.032。
RX32 Controller＋旧パターン、RX32＋今回パターンの2件でUART149B・checksum・freezeまでPASS。
選択recorderのsource固定・cycle順序・4sample満杯停止・再trigger拒否PASS。
Host pin-level SPI/QSPIの結果は同ディレクトリ`host1.run.log`/`host4.run.log`を正本とする。
最終結果は両方PASS。4/8/16/32/64BのTX data/address/length/mask、独立RX注入、
不正長、窓端、resetを確認した。`verification.json`には5本のrun log SHA256と
`hardware_tested=false`、`new_bitstream_generated=false`、`release_ready=false`を保存。
`check.py`で両baselineを歴史manifestと照合し、Host関連4ソースも今回評価manifestと一致。
独立oracleのCA計算、64Bの[4,32,28]分割、guard非重複、pattern長も確認した。
既存Python診断7件、PDR1 decoder3件は今回再実行PASS。
**未実施：** 新診断Standard STA、全配線、外部PSRAM timing、実機オラクル照合。

品質ゲート：GW1NR-LV9QN88PC6/I5、Standard V1.9.12.04、正しいPLL/IO制約、
setup>=+0.100ns・hold違反0・setup違反0・全配線、機能packet/オラクル一致、
PSRAM外部min/max評価を別欄で要求。IO未評価なら内部STA PASSでも投入条件未完。

## 13. 実機安全・復旧手順

1. 承認対象は案・fs hash・case/回数・scratch範囲・停止条件で固定。新規生成の承認と
   実機SRAM投入の承認を区別し、生成後のゲート/ハッシュを投入前に提示する。
2. KAGURA-9画面/識別を保存。既存private復旧FPGA像/UF2/backup hashを照合。
   RP2040全2MiB hashは既存 `7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。
   boot.pyは既知hash照合。private像を公開証跡へコピーしない。
3. RP2040 console/PIOをRAM操作で解放、GP2..5入力、GP6 Low、GP7 High、CS High/SCK Low。
   COM7/8のVID/PIDとJTAG1device/ID0x1100481Bを確認。相違なら投入しない。
4. SRAM Program `--run 2`のみ1回。Flash erase/program・RP2040 FW/filesystem変更禁止。
   readback verifyを行っていなければ行ったと記録しない。
5. 案AはPSRAM非選択を確認。案Bは300032/4Bと独立guard範囲だけに限定。
   RAM driver/受信を準備して1trigger。timeout/不完全packet/不一致でfreeze、replayなし。
6. rawログ・hash・境界snapshotを保存。成功でも自動次caseに進まない。
7. `--run 1`で既存FPGA FlashからSRAMへKAGURA-9再ロード。Flashへの書込みではない。
   QSPI解放確認→RP2040全Flash再hash→通常soft reset→banner/HDMI復元を確認。
8. 復旧確認不能なら次試験禁止。試験後scratchを追加WRITEで修復しない。

今回実機を触っていないため、この手順を実行したとの新規主張はない。

## 14. 判定マトリクス

|観測|疑う境界/次の分岐|断定できないこと|
|---|---|---|
|Host意図≠CSR受理|transport/dispatch/CSR|PSRAM故障では説明不要|
|CSR受理正、upload誤|byte commit/SP/port待ち|READ物理タイミング|
|upload正、要求data/mask誤|commands/arbiter/lock|PHY故障|
|要求正、CA/TX pair誤|Controller/chunk/shift|実padサンプリング|
|TX内部正、独立read不一致|WRITE物理/READ物理/CA/ダイを維持|WRITE正常|
|IDDR pair誤、RWDS先頭とslotずれ|READ捕捉/RDL/phaseを優先|DQがPSRAMから正しく出たか|
|pair正、RX512誤|slot/clear/chunk再組立て|Host正常|
|RX512正、窓誤|read_result/bulk capture/SP settle|PHY修正が必要|
|窓正、Host誤|adapter/turnaround/driver|PSRAM由来|
|same-start PASS、独立位置FAIL|wrap/alias/誤CA|linear正当性|
|連続READで変動|READ/初期化/負荷を優先|WRITE誤りの完全排除|
|どのREADでも固定同誤値|WRITE/alias/系統READ誤りを維持|WRITE原因確定|

## 15. 最小実験順序と候補（最大3案）

|案|仮説/RTL差分/新規観測|手順・期待結果・異常分岐|保護/停止条件|
|---|---|---|---|
|**A 最初：Host/CSRのみ**|host endpoint再利用、Controller応答を独立stubへ置換、boardのPSRAM固定非選択。CSR受理/window/要求snapshot。GPUなし|最初は300032/4B ED0F2143 upload→echo→WRITE受理値、独立READ ROM→download。全境界一致を期待。不一致ならその最初の境界だけを修正しPSRAM試験へ進まない|新fs生成/投入は別承認、SRAMのみ、Flash/FW無変更、1case。不一致/timeout/識別異常停止→KAGURA-9復旧|
|B 固定4B＋選択trace|RX32 Controller/同PHY無改変、既存probe FSM刺激をED0F2143へ限定、recorder追加。CA、TX/OEまたはRX/RWDS/slot|Hostなし4B WRITE/READを1回。PC同一PDR1/IDと比較。内部TX誤なら論理、TX正/RX誤なら物理/CAを維持。PASSならHost/先行条件/配置差が残る|300032だけ、guard追加は別caseとして承認、位相/RDL/CR0変更なし。1trigger、全結果freeze、不一致で復旧|
|C register read専用|別診断CA engine、通常memory WRITEなし。ID/CR0/CR1受信pairとCAを記録|仕様のregister address/latencyを資料照合後に固定読出し。ID整合なら候補型番を絞る。不定/全FFならCA/READ捕捉を分離し、CR変更禁止|未知register書込み禁止、SRAMのみ、回数固定。識別異常/timeoutで停止・復旧|

案A→承認/結果確認→B→必要時C。Aのboard統合とpacket gateをPCで完成させてから
新規Bitstream生成承認を得る。今回の承認なしに候補を生成/投入しない。
最初から位相sweep、全域/全pattern、長burstへ進まない。

## 16. 未解決事項と次の承認範囲

未解決：実機で最初に壊れる境界、READ/WRITE帰属、再現性、実ダイ/revision、実CR、
padでのCA/CK/DQ/RWDS/OE、cold/warm初期化差、元64B残差との関係。
最小修正はこれらのうち観測で特定した一箇所に限定する。現時点でCA45/CR0/RDL/
位相を変更した「修正版」を推奨できる証拠はない。

次の承認対象は**案Aの新規診断Bitstream作成（合成/P&R/STA）**。
その前にboard wrapper、診断識別、snapshot packet/decoder、pin/IO固定を完成して
PC gateを通す必要がある。作成後、実fs hash・STA/IO限界・復旧準備を提示し、
**300032/4Bの1case SRAM投入**を別途承認対象とする。

本体へ修正を戻す場合は別branchで、全Verilator、wrap統合12件、Controller272ケース、
RX32、HDMI/PCM/BLIT/cursor、Standard setup>=+0.100ns、setup/hold違反0、
全配線、外部PSRAM I/O確認を改めて要求する。診断PASSでReleaseへ昇格しない。
