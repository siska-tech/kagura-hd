# KAGURA-HD 外部測定器なしのQSPI異常調査

## 送信経路の監査

| 段階 | 確認結果 |
|---|---|
| SDKと呼出し元 | kfbの記述子・バッファ・ACK、b16の音声アクセス、起動の識別読出しは、b16_cached_ioを経てmt_qspi_ioのread_regs/write_regsへ到達。ベンチの生アクセスは通常のBLIT STORMとは別の開始キー。識別CSR0は起動時READ、書込みは定義済みCSRの範囲に収まる。 |
| ヘッダ | write_regsはregとincrement bit 6、read_regsはさらにbit 7をセット。生のWRITE(0,false,data,1)は入力検査を通る。increment WRITEは64を越すと周回する。最短の周回WRITEはCSR63から2バイト。耐久ループに直接WRITEと周回WRITEの呼出しは見つからなかった。 |
| FIFO投入 | ヘッダをPIOワードのbits 29:22に置く。WRITEはヘッダ→データ。READはヘッダ→count→dummy→読出しクロック。countのワードにだけIO解放bit 30を設定。実験はB16_TRANSPORT=0で同期ポーリング。DMAは有効構成でも条件を満たす非incrementデータ窓WRITEのデータ部だけに使う。 |
| CSとPIO | CS high中にSMを停止し、4本を出力へ設定して再開。CS low、setup待ち、FIFO投入。READはcount後にPIOでIOを解放し、その後のdummyと受信区間を同じCSで進める。TX FIFO emptyかつPCがpullを指すまで待ち、hold後にCS high、次までhigh間隔を確保。 |
| 並行性と寿命 | 単一コアの同期呼出しで、IRQまたは第2コアが同じPIOを使う経路は対象ソースに見つからなかった。スタックのヘッダ・記述子はtransfer中に消費され、呼出し間でポインタを保持しない。USB割込みや履歴追加が実際の間隔へ及ぼす影響は残る。 |
| 中断 | 失敗時はSMを無効化、TX/RX FIFOをclear、SMをrestartしてpullへ戻し、SCKをlow、CSをhigh、IOを入力へ戻す。faultedが立つので後続の開始を拒否する。物理波形やFPGA同期後のCS境界はこの状態から推定できない。 |

## 履歴と検証

診断ソースは build/queue8-host-history/source。製品ソースへの一時差替えはビルド後に元へ戻した。FPGAはPhase 2の40 bit診断画像と同じSHA256を照合し、同じ画像を投入した。

静的リング8192エントリ、1件8バイト、管理情報を含め65544バイト。動的確保・ロックなし。
CSアサート成功の直後、ヘッダ投入前に予定ヘッダ、転送長、WRITE先頭バイトを保存する。
開始CSR、方向、incrementはヘッダのbitをデコードする。
最初のpio_sm_putの後で、その呼出しに渡したワードからヘッダを記録しPUTを立てる。
PIO完了待ちとCS解除後にCLOSED、異常終了ではABORTEDを記録する。
連番はCS区間ごとに1つで、READのcountやdummy、WRITEデータ部には増やさない。
連番はリングのインデックスと最新番号から復元できる。1時間の規模は32 bit周回の範囲内。

異常回収時はstickyを読んだ直後に凍結し、5バイトのFPGA診断READとACKは記録外になる。
エラー停止時にUSBへ1度出力する。通常時の追加ログなし。
過去の履歴を保持する範囲は直近8192区間。任意の長時間検出遅延を保証しない。
今回の事象は直近のエラークリア送信候補から検出までの全区間を含む。
エラークリアがピン上およびFPGAで受理されたことの独立観測はない。

- リング単体はヘッダ、長さ、連番、周回、abortフラグ、凍結後の保持を確認。
- 実際のドライバを使うPIOモックは、CSR0 READ 0x80、完了バースト0xDB、sticky READ 0x87、ACK 0x1Fを個別のCS区間として照合。9001区間を経て凍結し、その後の診断READでも連番が不変。
- Queue8 SDK回帰は満杯受付、順序、連続回収、異常時停止を確認。
- 実機はpeak 8の負荷で凍結履歴全8192件を取得。端点を含む連番に欠落なし。
- ビルド変更でCS内のソフトウェア時間とfirmware配置は変わり得る。再現までの時間差を故障率の差と解釈しない。

## 実機耐久

BLIT STORMを25秒周期、Queue8、completion burst、QSPI 5 MHzで実行。
ホストのSTOP観測は1442.703秒。履歴出力後の値を含み、検出そのものの時刻は別計測していない。
最終PERFは1437685 ms、43551フレーム、timeouts=0、audio_fault=0。
1252479件投入、1252471件回収、peak 8、pending 8、errors 1。
期待・受信タグ30163、completion_error=0、sticky=2、STOP rc=-5。

    GPU_TRACE cause=2 addr=0 write=1 data=0x00 header=0x00 phase=3

凍結範囲41271069–41279260。8192件すべて予定・PIO投入値が一致し、
PUTとCLOSEDが成立。直接またはincrementによるCSR0 WRITEは0件。

| 連番 | 予定/PIO投入ヘッダ | データ長 | 意味 |
|---:|---|---:|---|
| 41279257 | 0x47 | 17 | sticky clearと記述子のpacked WRITE、先頭0x00 |
| 41279258 | 0x1A | 1 | SUBMIT、値0x01 |
| 41279259 | 0xDB | 4 | 完了バーストREAD |
| 41279260 | 0x87 | 1 | sticky READ、検出直後に凍結 |

## 確定した境界と次の最小観測

履歴がカバーする区間についてはケースB。RP2040が通常のWRITE(0)を
生成した、またはPIO FIFOへヘッダ0x00を投入したという証跡はない。
FPGAは0x00をヘッダとして保持し、WRITE addr=0へ一貫して変換している。
発端をPIO投入後からFPGAのヘッダ組立までの区間に絞った。
FPGAの異常イベントとHost連番の一対一対応は未取得で、
PIOピン出力、物理信号、同期サンプリング、CS境界のどれかは未確定。
data=0x00がpacked WRITE、READのdummy、別の波形のどれに由来するかも確定できない。

必要な追加観測は、FPGAが同期後のCS開始とヘッダの最初の2ニブルを
認識した順序を保持すること。CS開始数と完成ヘッダ数を別々に記録し、
同一CS内のPIO分割、abort、ヘッダなしCSを区別する。
HostとFPGAの数値をそのまま同一視せず、既知のREAD列を基点として
ヘッダ列と数の差を照合する。元の40 bitトレースは保持する。
これで余分なCS開始、短いCS、ヘッダのbit値異常を区別してから
該当する箇所だけの修正を選ぶ。製品RTLの修正は未実施。

## 証跡と復旧

原ログはbuild/queue8-host-history/hardware/candidate/demo-usb.log。
history-analysis.jsonに連番、書込み候補の全件検査と直近区間を保存。
test-history.log、test-driver.log、test-sdk.logとsha256.jsonを同じディレクトリに保存。
FPGA Flash書込み0。RP2040 Flash二重バックアップ、firmware・filesystem・末尾照合後に試験。
承認済みQueue8 SRAMと元firmwareへ復旧し、全FlashのSHA256
c7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a
の一致を確認。復旧証跡はrecovery/result.json。
