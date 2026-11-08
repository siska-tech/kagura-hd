# KAGURA-HD QSPI CS境界異常調査 Phase 4

## CSの静的監査

RP2040のCS GPIO7はSIOで操作する。QSPI用PIO0はSCKとIO0–3を駆動し、CSを変更しない。
CSの書込み箇所はinitのhigh、begin_transactionのlow、end_transaction正常時のhigh、
abortのhigh、deinitのhigh。CS high中にbeginがPIOを一時停止しIO出力を設定して再開する。
次にCSをlowにしsetupを待ってからヘッダを投入する。
READはヘッダとcountを同じCSで送信し、count末尾でPIOがIOを入力へ変え、dummyとデータを進める。
WRITEはヘッダ、データの順に投入し、Queue8のSUBMITとACKも各々独立CS。
実験構成のB16_TRANSPORT=0では同期ポーリング、DMAなし。SDKは同一コアで逐次実行される。

TX FIFO emptyはOSR内の残りビットの完了条件にならない。
正常終了ではemptyとPC=pullを両方確認する。
PIOは最後のSCK high命令からjmpのside 0でSCKをlowへ戻し、READ countのときは
IO方向命令を通ってからpullへ戻る。ホストはこの確認後にholdを置き、SIOのCSをhighにする。
中断はSM停止、FIFO clear、restart、pullへ復帰、SCK low、hold、CS high、
high間隔を置いてIOを入力へ戻し、faultedで再開始を禁止する。
通常のIRQによる待機延長はあり得るが、対象ソースに同じCS/SMへ並行書込みする経路はない。

診断専用firmwareはUSB開始キーg/h/iで250/1000/2000 nsを選び、同じバイナリを使う。
120 MHzで要求される最小待機は30/120/240 CPUクロック。
CS highのSIO書込みの直後にSDKのbusy_wait_at_least_cyclesを実行し、
その完了後に呼出し元へ戻る。次のCS lowは別のbeginにある。
逆アセンブルでSIO OUT_SETへのstrの後にsubs #3/bcsループを確認した。
この順序による下限はCPU/SIOの制御上の値であり、実ピンを連続測定した値とは区別する。
QSPI PIO0プログラム、分周、ヘッダ生成、Queue8、描画パラメータは3条件で同一。

PIO1の空きSMはCSのパッド入力を受動観測する。GPIOの機能や出力方向を変更しない。
既存のPIO入力同期後にwait low→wait high、mov x,y、jmp pinとjmp x--で判定。
clkdiv 1、120 MHz。high認識を時刻0とすると2,4,...,設定サイクル数−2でサンプル。
いずれかでlowを見た場合だけPIO IRQ flagをラッチし、停止時に読む。
A/B/Cで最後のサンプルは28/118/238サイクル目。
これは短さの閾値観測であり、全パルスの最小幅、短パルスの個数、FPGAと同一イベントの対応は得られない。
同期や16.67 nsのサンプル間隔より短い変動、末尾の判定余裕内の短縮は見逃し得る。
PIO1はCS/SCK/IOを駆動せず、正常経路でCPUポーリング・FIFO出力・割込み処理を追加しない。

## FPGA診断

CSとSCKを各2 FFで同期し、IOの既存2段と同じclkで読む。
同期後highのたびにカウンタを0→1→2→3で飽和させ、
startは同期lowかつ前サイクルhighで、更新前カウンタを見る。
従って直前highが1回/2回なら判定時に1/2、3回以上なら3。
この数字は同期済みサンプル数であり、入力ピンの時間幅へ単純換算しない。
同期highのエッジではphase=HEADERとdiscardを設定してSCKの処理を抑え、
startでchunk=0、HEADER、discard=0。startとSCKが重なればstartが優先。
2ニブルで組み立てる既存受信動作には変更を加えなかった。

既存40 bitと56 bitに、短いCS startの2クロック前、1クロック前、当該、次クロックの
4サンプルを追加。各byteは[7]active（同期CS low）、[6]start、[5]end、
[4]rise（取得候補）、[3:2]phase、[1:0]飽和highカウンタ。
全て54 MHzのposedgeが処理する同期済み値で、間隔は約18.52 ns。
2ニブルと組立値は既存診断にある。4サンプルには通常の後続ヘッダ取得を含まない。
要求発行、dispatch、sticky初回設定に追随して波形をラッチし、
異常後の別トランザクションから隔離する。sticky時のCSR15–18で取得。
CSR7クリアまたはリセットで従来の診断と一緒に消去する。
エラー設定分岐を共有するため、優先順位は従来どおり。

診断専用にCSR32–47の予約READへ32 bitカウンタ4本をマップした。
CS開始数、3回未満high直後の開始数、HEADER未完成でのCS終了数、完成ヘッダ0x00数。
カウンタはFPGAリセットから集計し、最終の診断READ区間もCS開始数に含む。
1回のincrement READで取得し、正常境界で値が安定する。
読み出し中の新たな異常による変化は原理的に残る。物理パルス数とは扱わない。

## 品質ゲート

5 MHz相当の波形で合法な250/1000/2000 nsを6位相で比較。
異常注入は1/2クロックhigh、high中の短いlow、不完全ヘッダ、
ヘッダ直後またはDATA途中の解除、CSとSCKの同時開始を別枠で検証。
正常幅で誤判定がなく、異常幅で診断カウンタ1/2を確認。
READ→WRITE→READ、連続短CS、CSR0 WRITEのstickyと波形の保持を確認した。
QSPI Queue8、満杯・順序・READ・COPY・PRESENT、ボードPCM/PSRAM回帰はPASS。
FIFO単体は該当RTLが同一のPhase 3結果を使用。
新しい観測は全て既存同期後の54 MHzドメインで、新規の非同期受渡しなし。

同じSDC/クロック/P4/R2でSetup +1.247 ns、Hold +0.456 ns、違反0。
Recovery +11.072 ns、Removal +0.745 ns。CLS3796/4320、BSRAM20/26。
最悪Setupはupload_group_select_1からwindow_write_word_5。
既存外部I/O制約の範囲を引き継ぐ。
RTL、試験、firmware、画像のSHA256はbuild/queue8-phase4/sha256.json。
逆アセンブルはfw-disassembly.txt。試験ログはcs.log、sim.log、board.log。

## A/B/C耐久結果

全条件に同じfirmware、同じSRAM画像を使用。3条件の書込み後全Flash SHA256も一致。
各条件でFPGAを再構成してカウンタをリセットした。BLIT STORMを25秒周期で回し、最初の異常で停止。
停止時刻はHostがSTOP行を受けた値で、診断USB出力の時間を含む。

| CS high設定 | STOP観測 秒 | 投入 | 回収 | FPGA CS開始 | 短CS | 未完ヘッダ | 0x00ヘッダ | 捕捉BAD_COMMAND | 短CS / 百万開始 | BAD / 百万開始 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A 250 ns | 1383.437 | 1201362 | 1201354 | 39313007 | 1 | 0 | 1 | 1 | 0.02544 | 0.02544 |
| B 1 µs | 1822.172 | 1583421 | 1583413 | 50496437 | 2 | 0 | 1 | 1 | 0.03961 | 0.01980 |
| C 2 µs | 170.953 | 144458 | 144450 | 4540491 | 1 | 0 | 1 | 1 | 0.22024 | 0.22024 |

全条件でSTOP rc=-5、Queue error 1、未回収8、completion error 0、
期待タグと受信タグ一致、sticky 2、観測されたtimeout/PCM faultは0。
RP2040パッド監視のshort_latchedは全条件0。
比較の分母はFPGA側の開始数で、初期化と診断READの通信を含む。
各1回であり、推定故障率や単調な頻度差としては扱わない。

最初のB試行は描画開始前にrc=-6。ProgrammerがUser code mismatchを出していた。
当初のランナーがFinished表示のみを条件に含め、mismatchを拒否しなかった。
未構成状態の応答は全0xffであり、そのカウンタは無効として比較から除外。
復旧後のB/CではUser Code 0x0000228F、Status Code 0x0003F020、
mismatchなしを開始条件にし、別出力先で試験した。コマンドの再送は行っていない。

| 条件 | 期待・受信タグ | FPGA要求データ | FPGA CS/ヘッダ番号 | Host凍結時の連番 |
|---|---:|---|---:|---:|
| A | 58470 | 0x0A | 56936 | 39313002 |
| B | 37988 | 0x00 | 33710 | 50496431 |
| C | 37409 | 0x02 | 18500 | 4540486 |

全条件でprev=0x47、nibbles=0x00、header=0x00、addr=0、write=1、
phase=DATA、context=0x02、cause=2（未定義CSR WRITE）。
凍結履歴は各8192件連続、予定とPIO投入ヘッダの差0、CSR0への直接・周回WRITE0。
凍結前の最後の4区間は全条件で0x47、0x1A、0xDB、0x87。
FPGA開始数はHost凍結番号に以降の40 bit READ、境界READ、ACK、カウンタREADの
4区間を加えた値よりA/B/Cで1/2/1多く、短CS数と一致した。
これは余分なstartの解釈に整合する。リセットの起点は独立であり、
特定のHost区間と異常startを一対一に確定する観測はない。

全条件で波形4サンプルが同じ。

| 相対クロック | byte | 観測 |
|---:|---|---|
| -2 | 0x8C | CS low、DATA、highカウンタ0 |
| -1 | 0x2C | CS high、end、DATA、highカウンタ0 |
| 0 | 0xC1 | CS low、start、HEADER、highカウンタ1 |
| +1 | 0x80 | CS low、HEADER、highカウンタ0 |

ここでのriseは4サンプルすべて0。ヘッダ取得はその後で、
既存診断の0,0から0x00が組み立てられた。1サンプルhighの観測と、
次のstartでカウンタ1を保持したことは異常注入シミュレーションの結果と整合する。
今回の記録をオフバイワンで説明する証拠は得られなかった。

## 判断と次の比較

ケース2を観測した。High設定を1 µsと2 µsに延長しても、
FPGAの同期済みCSで1サンプルhighの後に不正ヘッダが生じた。
正常な区間間待機の延長は、今回の障害を防がなかった。
Bでは短CS2件と捕捉BAD_COMMAND1件のため、短CSの集計値と異常停止は一対一ではない。
この集計はエラー後の診断通信を含む。

確定した境界は、FPGAがDATAで同期後highを1回観測し、
それをCS終了として処理して次のlowを新規HEADERとして受けたこと。
PIO1で監視したRP2040パッドでは閾値を下回るhighを検出していない。
PIO1の検出窓、独立同期、同一事象の対応未確定という制約があるため、
端子上に短パルスが存在しなかったとは判断しない。
FPGA端の物理波形と入力同期のどちらでhighが生じたかは未確定。

次の比較は、RP2040パッドとFPGA入力の両方で短い遷移の前後を
連続サンプルとして保持し、既知のヘッダ列またはトランザクション目印で対応づける。
受信側の修正候補を試す場合は、DATA中に見えた単発highでヘッダ境界を
確定しない診断版を作り、合法なCS解除、出力解放、READ/WRITEと
今回の1サンプルhigh注入を含めて前後比較する。
Phase 4では受信動作の修正と製品マージを実施していない。

## 証跡と復旧

比較のJSONはbuild/queue8-phase4/comparison.json。
原ログはhardware/250、hardware-bc/1000、hardware-bc/2000のdemo-usb.log。
初回Bの失敗はhardware/1000に保存。
Host照合はhistory-250.json、history-1000.json、history-2000.json。
全量二重バックアップとfirmware、filesystem、消去末尾以降の照合を各キャンペーンで実施。
復旧後の両キャンペーンの全Flash SHA256は初回と同じ
c7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a。
承認済みQueue8をSRAMに復元した。復旧はrecovery/result.jsonとrecovery-bc/result.json。
FPGA Flash書込み0。ビルド前後の製品firmwareソース、SDK、PIOの一致も照合した。

