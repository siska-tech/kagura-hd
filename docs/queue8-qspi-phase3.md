# KAGURA-HD QSPIヘッダ異常調査 Phase 3

## サイクル単位の静的監査

Phase 2の縮小backpressure入力とHost履歴firmwareを基準とした。
比較対象のHDMI送出は省略し、音声の元のbackpressureは維持する。

| FPGAの処理 | 54 MHzでの観測と更新 |
|---|---|
| 入力同期 | 各posedgeでSCKとCSを各2 FFへ、IOをio_sync0→io_sync1へ進める。エッジ判定は同期済みCS/SCKとその前サイクルを使用し、そのサイクルのio_sync1を採る。別々の同期器なので、物理的に近接する遷移の相対順序を静的に保証できない。 |
| CS開始 | activeかつ前サイクルCS highをstartとする。この分岐がニブル取得より優先。phase=HEADER、chunk=0、discard=0、出力シフトと先読みフラグを初期化。開始と同じサイクルはriseの条件から外れる。 |
| ヘッダ | HEADERの1回目のriseで上位ニブルをin_shiftの下位へ取り込む。2回目のriseでその4 bitとio_sync1を連結してbyte_inにし、受信ヘッダ、R/W、increment、offsetを同じposedgeで更新。READはCOUNT、WRITEはDATAへ移る。 |
| READ | COUNTの2ニブルを取得後DUMMYへ移る。DUMMY先頭のriseでIOを駆動し、先行fetchでread要求を作る。次バイト境界で先読みデータを出力する。個数が尽きた後は追加要求を出さない。 |
| WRITE | DATAの2ニブル目でreq_valid、req_write、req_addr、req_wdataを更新。incrementならoffsetを進める。DATAで不正WRITEが記録されたのは、ヘッダをHEADERで取得した後にWRITEデータが完成したため。 |
| dispatch | BUS_IDLEでreq_validを受け、バンクと要求を保持。BUS_ISSUEで当該バンクのreadyを待ち、BUS_WAITで応答を返す。未受理要求があると後続byteの発行を抑止しlateをセットする。 |
| CS終了 | 同期後CS highが見えたサイクルでは、riseを処理せずphase=HEADER、discard=1、IO出力無効。chunkは次のstartで0にする。in_shift自体は保持するが、正常な2ニブルで古い値は押し出される。発行済みreq_validとREAD応答待ちはCS解除で取り消さず、独立に完了。次開始時に残っていればlate。 |

RP2040はCS high中にSMを停止してIOを出力へ設定し、再開後CSをlowにしてsetupを待つ。
ソフトウェアはPIO TX FIFOへ上位・下位ニブルを含む1ワード/byteを投入する。
PIOはpull、制御bit処理、SCK lowで上位ニブル出力、SCK high、SCK lowで下位ニブル出力、
SCK high、SCK lowへ戻って次のpullの順。READ countのワードだけ末尾でIOを入力へ切り替える。
CPUがTX emptyかつpull位置を確認してからhold、CS high、high待ちを実行する。
abortはSM停止・FIFO clear・restart・pullへ復帰・SCK low・CS high・IO入力を行い、
faultをラッチする。通常ループは同期ポーリング、DMAは無効で、同じSMへの並行アクセスは確認されなかった。
この監査はPIOピンの実測ではなく、H1–H4はいずれも実機原因として未確定の状態で試験を開始する。

## 追加観測と取得サイクル

製品と分離した build/queue8-phase3/compact-inputs の3 RTLだけを変更。
kagura_spi_adapterは既存同期後のstartごとに16 bitのCS番号を増やし、
最後のヘッダニブルごとに16 bitのヘッダ番号を増やす。
startで直前phaseと同期SCK、3サイクル未満のCS highを保存。
2ニブルを個別にラッチし、2番目の時点のphaseと前回完成ヘッダを保持。
直前のCSがHEADERのまま終了した場合にprior_incompleteを立てる。
完成済みWRITEヘッダでデータなしの終了はprior_incompleteの対象外。

要求発行と同じエッジで56 bitの観測を要求へ付随させる。
kagura_fb_hostはBUS_IDLEの受理エッジで観測を要求と一緒に保持し、
その時点でCS high、または要求が保留中にCS highを観測済みならendedを付ける。
kagura_fb_registersは既存40 bitトレースと同じsticky初回設定分岐で56 bitを保持する。
コマンド完了起源の56 bitはCSR要求がないため0。エラー設定の優先順位は元の分岐順。
非同期信号を追加でサンプリングせず、全観測と受渡しは54 MHzの同一ドメイン。

診断画像限定でstickyが非ゼロの間のCSR8–14に7バイトを返す。
順序はcontext、2ニブル、前回ヘッダ、完成数の下位・上位、CS開始数の下位・上位。
context[7:6]はstart前phase、[5:4]は完成phase、[3]は直前の不完全ヘッダ、
[2]はstart時SCK high、[1]は短いCS high、[0]はdispatch前の終了・再開始。
既存40 bitは引き続きCSR0–4から取得する。
CSR7 clearとリセットは両方の記録を消す。Hostはsticky検出時に8192件履歴を凍結し、
CSR0–4、8–14を読み終えてから停止処理へ進む。この間はstickyをクリアしない。
同期後CS・ニブルの記録なので、外部ピン上の実波形は記録しない。
16 bit番号は周回し、FPGA resetとHost開始は別時点。番号一致だけで対応を保証しない。

PIOは120 MHzをdiv 2で動作。データ出力のout pins [4]は5命令クロック、
in pinsは1、SCK highのnop [5]は6。同一byte内のSCK立上り間隔は
12命令クロック（200 ns）で、byte境界にはpull、制御、IO解放や待ち時間が加わる。
したがって5 MHzはニブル間の設定であり、全CS内のSCK間隔を一律200 nsとは扱わない。

## ゲート評価中の比較

CS越境を16 bit番号比較で判定した初版はSetup +0.991 ns、Hold +0.423 ns、
違反0、CLS3742、BSRAM20。新しいCS開始と旧要求受理が同時のとき
番号更新前の判定を使うため、同時startも検出する構成を別に試した。
同時start検出版はSetup -0.830 ns、Hold +0.508 ns、Setup違反14。
最悪経路はFILL rmwからPSRAM送信FF。CLS3760、BSRAM20。
どちらも実機へは投入せず、最終候補は保留中のCS highを1 bitで保持する構成。

## 最終ゲート

保留中のCS highを1 bitで持つ版は同一クロック、SDC、QSPI Queue8、P4/R2で
Setup +2.038 ns、Hold +0.484 ns、Setup/Hold違反0、Recovery +10.295 ns、Removal +0.548 ns。
CLS 3761/4320、BSRAM 20/26。最悪Setupは表示bank tag_0からpixel_tag_0。
新規の非同期入力はなく、CS/SCK/IOは既存同期器の出力を読む。
既存SDCの外部I/O評価範囲は引き継ぐ。
画像SHA256は662d626100dfb7b88b5b564548c97672b943e03fb42a84b28377a1410800ed11。
入力とfirmwareはbuild/queue8-phase3/sha256.jsonに保存した。

5 MHz波形でCS setup/highを250–332 ns、holdを40–122 nsで変化させた。
各正常READ/WRITEの2ニブル・組立ヘッダ・開始と完成phaseを照合。
1ニブルと2ニブル直後のCS解除、CSR0不正WRITE、不正SUBMIT、周回、
音声・完了エラー、既存stickyの最初の記録、短い連続CSを検証。
1ニブル中断は次回にprior_incompleteを通知し、ヘッダ完成数に入れなかった。
独立試験でreq_readyを止め、次CSのヘッダが来ても旧要求の56 bitが保持され、
受理前のCS越境が検出されることを確認。
Queue8の満杯・順序・READ・COPY・PRESENT、ボードのPCM/PSRAM回帰は通過。
FIFO単体のRTLは同じなのでregistered headの深さ8回帰結果を共用。
証跡はcompact-boundary.log、compact-sim.log、compact-board.log、queue.log。

## 実機結果と分類

BLIT STORMを25秒周期で実行し、HostのSTOP観測285.875秒（4分46秒）で停止。
この時刻にはUSBへの診断出力を含む。245100件投入、245092件回収、
peak 8、pending 8、errors 1。期待・受信タグ42196、completion error 0、
sticky 2、STOP rc=-5。最終PERFのtimeoutとPCM faultは0。

    QSPI_BOUNDARY cs=12094 headers=12094 prev=0x47 nibbles=0x00 context=0x02
    GPU_TRACE cause=2 addr=0 write=1 data=0x1e header=0x00 phase=3

context=0x02の立っているbitはshort_highのみ。
start直前とヘッダ完成時のphaseはHEADER。直前の未完成ヘッダなし、
start時同期SCKはlow、要求受理前の当該CS終了・再開始は観測していない。
short_highは、FPGAが同期後のCS highを3回連続で観測する前にstartを検出したことを示す。
54 MHzの3サイクルは約55.6 ns、Hostの設定上のCS highは最低250 ns。
この比較は同期後の観測回数とHost設計値の比較であり、実ピンのパルス幅を測定した値ではない。

2ニブルは個別観測とも0。ヘッダ0x00との組立不一致は観測されず、
CSRはDATAで到達した不正WRITEを拒否した。今回の証拠で判明した最初の
境界異常は短いCS highを挟むstartであり、ニブル値の異常もその時点で存在した。
正常長のCSから始まるケース3の条件とは異なる。
余分なCS開始というケース1を優先調査するが、
追加startか短縮した本来のstartかを確定するには対応づけが必要なため分類はケース5を含む。
直前ヘッダが0x47という事実だけで前回DATAの再解釈（ケース2）とは確定できない。
H4を支持するニブルとヘッダの差は今回観測していない。
H1–H3のうち、RP2040の端子出力、伝送、同期入力のどこで短い区間になったかは未確定。

8192件のHost履歴は8130369–8138560。連番欠落、PIO投入ヘッダ差、CSR0 WRITEは各0。
最後の4区間は8138557=0x47、8138558=0x1A、8138559=0xDB、8138560=0x87。
8138558の下位16 bitは12094で、直前の0x47とも整合するため対応候補。
ただしHostとFPGAで開始時点が異なり、余分なCSと欠落は相殺し得るため、
この一致でSUBMIT区間と断定しない。CS数とヘッダ数の一致も16 bit剰余であり、
完成ヘッダを伴う余分なCS開始を排除しない。

## 次に検証する最小範囲と復旧

調査範囲はCSR拒否やヘッダの連結より前のCS境界とニブル取得。
次の比較では元の40 bitを維持し、短いCS highの直前直後の
同期CS/SCK/IOを小さな循環記録に取り、1または2サイクルのhigh、
直前DATAと次の最初のニブルの関係を確認する。
RP2040の別PIO SMでCS端子を受動監視できるかを検討し、
Host開始数のログとFPGA側のヘッダ列を既知のREAD列で対応づける。
計測追加のタイミング影響も比較する。
修正箇所の確定前にCSフィルタやデコーダ動作を変更しない。
修正候補は診断構成で再現条件を固定し、前後比較を行う。

実機原ログはbuild/queue8-phase3/hardware/candidate/demo-usb.logの560行。
history-analysis.jsonに連番検査を保存。
FPGA Flash書込み0。RP2040 Flashの事前二重読出しと書込み後の
firmware、filesystem、末尾の照合を実施した。
元firmwareの全Flash SHA256 c7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a
を復元・照合し、承認済みQueue8 SRAMへ戻した。
recovery/result.jsonを参照。調査用firmwareビルド後に製品ソースを復元した。
