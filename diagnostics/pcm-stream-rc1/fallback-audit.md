# PCMストリーミング RC1 実機試験前監査

対象は `build/pcm-stream-rc1/sta-short-control/native/impl/pnr/kagura_fb.fs`。SHA-256は `DE71D3FB2F45F2F119413659EF199AD72569BD8A74C6C1B68AD5AE44F119CBCB`。STA HTMLのSHA-256は `A13F3DE87C0FCC45E0090BF6E0ADDFBA4E54FDBAAF61D21D671D4E8EF84D59D6`。Setup +0.090 ns、Hold +0.530 ns、違反0/0、Recovery +9.601 ns、Removal +0.830 ns。ユーザー指定の試験条件1を満たす。従来のSetup +0.100 nsゲートは未達。

|範囲|照合結果|残る事項|
|---|---|---|
|SDCとクロック|RC1とSDCのSHA-256が一致。27 MHz、371.25 MHz、74.25 MHz、54 MHz、PSRAM 54 MHzの67.5°位相を保存RTLとSTAに照合。|数値は当該制約で解析された経路の範囲。|
|system54 / pixel74 CDC|PRESENT、ライン要求・タグ、カーソルは同期したトグルとACKで保持データを引き渡す。HDMI音声FIFOはGrayポインタを2段同期。両方向に10 nsのmax-delayとhold除外。|一律の制約であり、信号クラス別の制約やGrayバスのskew制約はない。構造照合は行ったが専用CDCツールによる網羅検証は未実施。|
|Host QSPI|SCK、CS、IOはsystem54で2段サンプリング。入出力はSDCでfalse path。CSTとHost配線指定はRC1から継承。|Hostのパッド上の入力位相・出力setup/holdはSTA対象外。今回のデモは既存5 MHz環境での機能確認。|
|PSRAM・HDMI外部I/O|PSRAMの位相クロックとピン設定、HDMIピン設定はRC1から継承。SDCに外部の `set_input_delay` / `set_output_delay` がない。|PSRAMの外部min/max、基板伝搬、HDMI電気特性およびPVTは未認定。|

JTAGでGW1NR-9C系ID `0x1100481B`を検出。復旧用の承認済みQueue8画像はSHA-256 `5592AE2CB18E4AA0BD70417B168A2D63D098BD3D14A5D19560636DE7E6C97A77`。Programmerの操作2で候補と復旧画像をSRAMへ入れる。RP2040は既存のBEYOND 16 COLORSのバナーを受信した。この実行系は従来PCM2を使い、試作CSR E3–E5を駆動しない。実行できる150秒デモは従来PCM2との互換回帰として記録し、ストリーム境界、所有権、補充競合、長時間ストリームの合否は別に扱う。

残りの実機試験は、E3–E5を実装したホスト実行系で次を照合する。

- 48 kHz・左右別の既知PCMパターンで、4096サンプル境界の欠落・重複と左右ずれをキャプチャで確認する。半面の返却前、古いtoken、二重公開が拒否され、E4の255→0周回を越えて正しい半面だけが公開されることを記録する。
- 意図的に補充を止め、両ch停止と異常表示を確認する。STOP後はarmedと応答待ちが落ちるまで待ち、新しいデータで再開する。
- BLIT STORMと150秒メガデモの間もE3–E5補充を継続する。補充時間、最大の補充間隔、Queue完了、FPGA側の異常、HDMI音声の連続性を同時に記録する。4096サンプルは約85.33 ms。平均だけで期限達成を判定しない。
- 長時間試験は1時間を試験値とし、token周回、補充失敗、underrun、Queueエラー、音声欠落を集計する。

## 150秒の実機互換回帰

候補をProgrammer操作2でFPGA SRAMへ1回投入した。User Code `0x00009B86`、Status `0x0003F020`、Finishedを照合。全8シーン、4452更新、Queue 324803件投入・同数回収、pending 0、Queueエラー・通信timeout・従来PCM fault各0で終了した。FPGA Flashの書込みは0回。RP2040 Flashを前後に全2 MiB読み出し、SHA-256が一致した。承認済みQueue8をSRAMに復旧し、User Code `0x00004068` とホスト再起動を確認した。

HDMI録画は1280×720/60 fps、48 kHzステレオ。音声の有効区間150.01秒を10 msごとに集計し、低RMSブロック（閾値20/32768）を左60、右68、左右同時59ブロック検出した。左右同時の連続区間は9箇所で、最長80 ms。RC1の保存済み検証では同じ集計で0ブロックだった。FPGA側の従来PCM faultとキャプチャ側のバッファ超過報告はともに0であり、原因は特定していない。録画のSHA-256は `8E9A80BAB60CBE8285191DD74B4E7747D61C2759EE7D977E0B24B0CFDE8002EC`。

試験条件1の数値と条件2の監査を記録し、条件3のSRAM投入を完了した。条件6の150秒デモは完走したが、音声の連続性は合格扱いにしない。現行ホストは従来PCM2のため、条件4・5と条件6の長時間ストリーミングは未実施。採用保留。実機ログ、計数、録画、復旧記録は `build/pcm-stream-rc1/fallback-hardware/`。録画集計は保存済みNumPyと互換のPython 3.12を使用した。
