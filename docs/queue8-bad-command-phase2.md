# KAGURA-HD BAD_COMMAND 根本原因調査 Phase 2

## 静的監査

| 層 | 確認した実装と観測 |
|---|---|
| RP2040 SDK | 通常の耐久経路で、識別CSR 0–6はREAD。キュー受付はエラークリア7、記述子8–23、SUBMIT 26。packed書込みはヘッダ0x47と17バイトで7–23まで。データ窓のWRITEは24に固定、ポインタは25、ACKは31。カーソルは32–53の範囲、音声設定は54–55。いずれも実行中のWRITEがCSR0へ周回する長さではない。 |
| 送信ヘッダ | 下位6 bitが開始CSR、bit 6がincrement、bit 7は1でREAD。生APIはWRITE(0, false, data, 1)を許す。increment WRITEで開始アドレスから64に達すると受信側で0へ周回する。最短はWRITE(63, true, data, 2)。この2経路を波形注入で区別できる。 |
| 完了回収 | 連続READは0xDBで27–30を取得する。DONE未取得時は再ポーリング、必要時は28–30を読み直す。タグ一致時にCSR7をREADしてから、別CSの0x1FでACK。バースト内にWRITEは含まれない。0xDBのR/Wだけが反転しても開始先は27であり、CSR0には別のアドレス変化または十分な周回が必要。 |
| PIO/CS | 1転送内でヘッダ、READ count、turnaround、dummy、payloadを順に処理する。READはcountの末尾でIOを解放。PIO TX FIFO emptyとpull位置を確認し、CS hold/high間隔を置く。abortはSMとFIFOを止め、CSを解放しfaultをラッチする。 |
| DMA/割込み | 使用firmwareはB16_TRANSPORT=0、B16_COOP=OFF。PIOの送受信は同期ポーリングで、QSPIを呼ぶ並行IRQまたは第2コアの経路は対象ソースに見つからなかった。DMA有効時も使用先は非incrementの24/25で、別の固定バッファ、同期待機、チャネル異常検査を持つ。IRQによる遅延や実際の電気信号は静的監査の範囲外。 |
| FPGA受信 | SCK、CS、IOを別々に2FFで同期。CS立下り検出でHEADER、chunk=0に戻る。HEADERからWRITEはDATA、READはCOUNT、DUMMY、DATA。WRITEは完全なデータbyteでreq_write=1、READは先行fetchでreq_write=0。アドレスは6 bit increment。CS highで出力を解放し、未完成byteを捨てる。発行済みreqとREAD応答は独立に完了し、次CS開始時に未完了ならlateを設定する。 |
| FPGA dispatch | BUS_IDLEでreq_valid/readyと同時にバンクとペイロードを保持。BUS_ISSUEで選択バンクのreadyを待ち、BUS_WAITで応答を返す。base CSRは0–31、音声は54–63、その他の上位領域はカーソル。CSR側はreq_validとreq_readyが成立したWRITEで判定する。 |

送信側の正常な引数と理想波形を前提とすると、耐久ループが意図してCSR0へのWRITEを生成する経路は確認できなかった。SCK/CS/IOのサンプルずれ、ヘッダ破損、誤ったCS境界、内部変換の異常は仮説として残す。同期後のヘッダを記録してもピンの物理波形とHostの意図までは識別できない。

## 診断の実装

製品ツリーから分離した build/queue8-phase2/inputs を使用。縮小backpressure版の入力から以下の3ファイルを変更した。

- rtl/bus/kagura_spi_adapter.sv は既存同期後に組み立てたヘッダを保持し、要求発行時にphaseと一緒にスナップショットする。既存の要求と同じクロックでラッチする。
- rtl/fb/kagura_fb_host.sv はBUS_IDLEの受付で診断情報をペイロードと一緒に保持する。音声応答の診断には音声バンクの保持アドレスと書込みデータを使う。
- rtl/fb/kagura_fb_registers.sv は既存stickyの優先順位と同じ順序で40 bitを保持する。既存のエラークリアで記録も消去する。診断画像限定で、stickyが立っている間にCSR0–4を読むと記録を返す。試験用の旧RTLにあったsticky設定後のCSR0 WRITE診断応答は外した。

診断のbyte 0は書込みデータ、byte 1はphase[7:6]とアドレス[5:0]、byte 2はヘッダ、byte 3はWRITE[7]と発生源[6:0]、byte 4は形式識別0xB2。発生源1はSUBMIT拒否、2は未定義CSR WRITE、3はAudio応答、4は完了エラー。完了起源には対応するCSR要求がないためbyte 0をcmd_errorとし、ヘッダ、phase、アドレスを0とする。phaseは要求を発行した時点でHEADER=0、COUNT=1、DUMMY=2、DATA=3。完了タグは従来のホスト診断で別に記録する。

sdk-trace.cは異常回収時に5バイトを読み、識別値が一致するとGPU_TRACEを出力する。通常回収には追加I/Oを行わない。診断firmwareの再リンクによる配置差は残る。Host送信履歴の常時記録は今回追加していない。

## ゲート

配置配線はQSPI Queue8、P4/R2、元のクロック、CST、SDCで実施。Setup +0.975 ns、Hold +0.528 ns、違反各0。Recovery +10.693 ns、Removal +0.533 ns。CLS 3692/4320、BSRAM 20/26。SHA256と試験入力は build/queue8-phase2/sha256.json に保存。


5 MHz相当のQSPI試験はCS setup/high 250 ns、hold 40 nsで実施。
正常CSR0 READ、CSR0へのWRITE、CSR63からのincrement周回、不正SUBMIT、
未定義CSR、音声応答エラー、コマンド完了エラー、第一記録の保持、
不完全ヘッダとデータなしWRITEの中断、短い連続READ/WRITEを確認した。
最初の高速化試験はPRESENT待ちの4000ポーリングが1フレームに届かず停止。
テスト側の上限を10000へ増やした再試験は、全異常注入と
Queue8満杯・順序・READ・COPY・PRESENT回帰を通過した。
深さ8 registered head FIFO回帰と、4 lane Queue8ボードの
PSRAM upload/readback・ステレオサンプル・音声制御回帰も通過。
各ログはbuild/queue8-phase2/sim-fast.log、board.log、queue.log。
同時高負荷での偶発的な物理信号異常はシミュレーションで再現していない。

## 実機耐久と最初の不一致

BLIT STORMを25秒周期で実行し、ホスト観測2517.453秒（41分57秒）で停止。
最終PERFは2513451 ms、timeoutとPCM faultは0。
2189260件投入、2189252件回収、peak 8、pending 8、Queue error 1。
期待タグと受信タグは7927で一致。status 18、completion_error 0、sticky 2、STOP rc=-5。

    GPU_TRACE cause=2 addr=0 write=1 data=0x18 header=0x00 phase=3

発生源2は未定義ベースCSR WRITE。phase=3はDATA。
ヘッダ0x00はWRITE、incrementなし、開始アドレス0を表す。
CSR側のWRITE・アドレス0と一致し、受信した値は0x18。
今回の事象について、CSR変換でREADがWRITEに反転した証跡や
incrementによるCSR0への周回はない。
CSRのBAD_COMMAND設定は受理した無効WRITEに対応している。

通常の耐久ループの送信意図と異なるヘッダが、同期・デコード済みの観測点で
既に成立していた。今回のトレースで境界をここまで絞った。
Hostが実際に送信したバイト、ピン上のヘッダ、FPGAのサンプル値を
同一トランザクションで比較していないため、
Host生成、物理伝送、受信時のフレーミングのどこで最初に不一致が生じたかは未確定。
0x18の出所も未確定。音声backpressureとの因果関係は引き続き未確定。

トレースはsticky設定区間の先頭を保持し、通常のCSR7クリアで消える。
この設計ではホストが検出する前にクリアされた別の事象を保持できない。
今回の停止では有効な形式識別と対象の記録が回収できた。

## 次の最小観測と修正候補

CS、SCK、IO0–3をFPGA端に近い位置で同時収録し、
CS立下り後の最初の2ニブル、次の2ニブルと、直前CSの境界を確認する。
循環収録はsticky検出をトリガとし、検出前の複数トランザクションを残す。
トリガには異常検出時だけ切り替えるRP2040の空きGPIO、
またはCSR7の応答2を解釈できる外部プロトコルトリガを使う。
同時にHostの直近ヘッダ、方向、長さを小さな循環バッファへ記録して照合する。

Host意図、ピンの実測、FPGA診断の三者の最初の食い違いで修正箇所を決める。
送信ヘッダが先に崩れるならHostの生成またはPIO境界を修正する。
ピン上の波形が正しいままFPGA側だけでヘッダが崩れるなら、
再現したCS/SCK境界条件に対する受信側の修正を検証する。
物理波形が崩れる場合は波形の要因を特定し、受信側のBAD_COMMAND判定を維持する。
今回の証拠では製品修正を選定していない。

## 証跡と復旧

原ログ build/queue8-phase2/hardware/candidate/demo-usb.log の4984行から診断。
試験用FPGA、firmwareと全FPGA入力のSHA256はbuild/queue8-phase2/sha256.json。
FPGA Flash書込み0。RP2040 Flashは二重読出しでバックアップ。
診断firmware書込み後はfirmwareバイト、消去終端以降、filesystemを照合。
停止後に元の全Flash像を復元し、SHA256
c7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a
の一致を確認。承認済みQueue8 SRAM画像を復元した。
復旧証跡はbuild/queue8-phase2/recovery/result.json。
製品RTLへの診断マージと既存画像の置換は実施していない。

