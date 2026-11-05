# 実機試験・保護・復旧計画

**以下は投入前に固定した計画。2026-11-06、明示承認後にbackup・投入・有限ベンチ・150秒完走を実施済み。[実行結果](HARDWARE_RESULT.md)を参照。元Flash復旧は未実行で、現在はBEYONDのフィナーレ画面・音声停止。`release_ready=false`。**

## 固定するもの

- FPGAは既存STA合格候補のみ：`build/pcm2-timing-04/build/standard-timing-04/impl/pnr/kagura_fb.fs`、SHA-256 `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。
- RTL／Controller／PHY／SDC／CST／PLL／clock／Host ABI／FPGA Flash／PSRAM物理／PCMハードウェアは変更しない。
- RP2040のPico SDK、GNU compiler、PIO、C入力は[evidence/source-sha256.json](evidence/source-sha256.json)へ固定。ELF/bin hashとsector範囲は[evidence/rp2040-build.json](evidence/rp2040-build.json)。hashが変わったら旧承認を流用しない。
- 元Flash全2MiBの既存退避：`build/midnight-hardware/recovery/current-flash-2MiB.bin`、SHA-256 `7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。今回もファイルhash／サイズ一致を確認した。
- 前作C版書込み後の保存像：`build/midnight-hardware/recovery/after-native-flash.bin`、SHA-256 `7ea52cb9898e6dbd3b44eb1b80861b28a3fd8026d858973162e05f5df32ee596`。これは前回の保存像であり、現在実機の再読出しではない。

## 承認後、投入前に必要な順序

1. 停止の時刻・現状HDMI映像・USBログ保存先・復旧対象（現在C版か元システムか）を記録。現在の再生を止める操作も承認対象。
2. ボードUID、RP2040とFlash容量、QSPI配線を確認。COM番号は前作値を盲目的に使わず、その場で同定する。
3. **現在Flashを新しい別名へ全量バックアップ**し、2MiB／hash／再読出し一致を確認。既存2ファイルは上書きしない。現在像が前作保存像と違えば理由が分かるまで停止する。
4. firmware `.bin` のhashとELFを確認。消去対象は先頭から`ceil(bin_bytes/4096)*4096`まで。現在のbuildでは[evidence/rp2040-build.json](evidence/rp2040-build.json)に具体的終端を記録。必ず`0x100a0000`より手前に収まることを再検証。filesystemはoffset `0xa0000`以降、物理Flash末尾まで保護。
5. FPGA Flashを書換えず、必要な場合だけ固定候補をSRAMへ1回投入する。既に同候補が動いていると証明できれば不要。候補不一致・Programmerエラーで自動再試行しない。
6. RP2040 firmwareを書込むのは新バックアップが検証済みの場合のみ。erase-all／format／自動retryは禁止。書込み後に全Flashをreadbackし、bin本体一致、丸めsector末尾以降が新バックアップと完全一致、filesystem全体一致を確認する。
7. 再起動後はUSB入力待ち。**自動再生は始まらない**。`b`は有限ベンチ、`g`は150秒autoplay。実機書込みやprogrammerを呼ぶスクリプトは本成果物に含めていない。

## 測定キャンペーン

条件：同一候補hash、RP2040 120MHz、nominal QSPI 5MHz、PIO divider2、同じ電源／配線／室温／USB logging条件。初期画面、scene時刻、seed 0xb1616、standard stars64、objects32を固定。nominal値とscope実測値を分ける。HDMI 720p60は出力信号であり実更新fpsではない。

### 1. Before/After通信

最初に`KFB_PACK_DESCRIPTOR=0`＋CAPS非cache版、次に最適化版を同条件で比較する。現状の配布ELFは最適化版なので、baseline実機版を作る場合は別名・別hashにして承認へ提示し、暗黙に書換えない。PC Before/Afterは完了済みだが、実機の2firmware比較はこの承認と別に書込み順序を明示する必要がある。

`b`モードはPCM停止中、asset事前配置＋PCM0再生中の2phaseで以下を有限実行する。

- raw pointer CSR25 nonincrement WRITE 1/2/4/8/16/64/512B。GPU IDLEを確認して実施し、値は0のみ。
- raw CSR0 nonincrement READ 同サイズ。READ512BはABI上限256Bにより2transactionと明記。
- scratch `0x100000`へPSRAM WRITE/READ、ガード領域を含むreadbackを追加確認。
- FENCE64件：submit呼出し時間とtag/DONE/error確認時間を別記。安全なserial throughputを記録。
- 32×32 FILL／BLIT／PRESENT 各8件。PRESENTはHost視点vblank完了待ちを含む。

`b`中のFILLは表示を変える。現在再生中のデモへ勝手に実行しない。有限ベンチの後はSTOPして入力待ちへ戻らずidleする。再試験はログ保存・原因確認後に判断する。

rawの長さ別時間は`T(n)=固定費+転送量依存項`として回帰するが、これはHost視点の合成モデル。PIO／GPIO／GPU受理／PSRAMを分離した実測とは呼ばない。PIO SCKとCS、IO方向切替、IRQ/BUSY/READYを外部logic analyzerで同期観測できる場合に限り内訳へ対応付ける。外部観測がなければ「測定不能」のまま残す。IRQはopen drainのpull-upとGPIO10配線の確認が必要で、現firmwareは使用しない。SPIへの切替は凍結QSPI候補では行わない。

### 2. 実描画と音声

`g`の初回asset loadは音楽開始前。load所要時間、BGM COMMIT時刻、最初のPRESENTを記録。以後のscene進行はそのepochからの実時刻であり、遅いframeの回数で延長しない。

`FRAME`は描画した1frameのCPU呼出し時間、累積描画command、BLIT pixelsを記録。`PERF`は1秒ごとのtransaction、wire bytes、transaction累積時間、最長、timeout、frames、skip、平均算出用sum、worst、audio_faultを出す。framesの差分と実時間で実更新fpsを求め、command/sとtransaction/sは別に集計。初期loadを本編rateから除外する。

各frameのprintfは時間計測の外でも次frameへ影響する可能性がある。logging有効条件を固定し、無logging比較を行う場合は別build/hashとして比較する。FILL/BLIT/FENCE/PRESENT個別値は`b`で確認し、全sceneのFENCE値を未測定のまま捏造しない。

星64/128/256とBLIT8/16/32/64/128の実機sweepは`b16_load_test`を使う各別buildで行う。PC sweep結果から実機の上限を決めない。現配布ELFでUARTから個数を変更する機能はない。

HDMI映像＋音声を150秒より前からcaptureし、scene境界、画面更新、stingerとbeatのoffset、8秒loop端、音切れ、STATUS fault bit0x38を検査。1秒status polling間の一過性現象はstatusだけで完全証明できないため、captureと照合する。PCM再生位置の公開CSRがないため、RP時計との150秒のdriftは音声波形／映像で測る。30fps、60fps、音声underrun0は測定後にのみ判定する。

### 3. 異常時

最初のHost timeout／SPI late／不明ABI／GPU error／PCM status fault／画面破壊／readback不一致で停止。uncertain commandを再送せず、ログとcaptureを保存する。transport fault時に無理なSTOP命令を追加しない。RTL起因と疑われてもこの場でRTLを直さず、最小再現・条件・hashを記録して停止し、別提案とする。

## 復旧

新キャンペーン開始直前の全Flashバックアップへ戻すことを基本とする。元システム復元を選ぶ場合のみSHA `7134...`の保存像を使い、前作C版へ戻す場合はSHA `7ea5...`の保存像を使う。復旧対象は承認時に確定する。復旧は保存像のhash確認後、全内容readback一致・filesystem一致・再起動・HDMI/音声確認まで行う。FPGA Flashは一度も書換えず、SRAMは電源再投入または既存固定候補の復帰で扱う。現時点では復旧操作も未実行。

## 投入前の残チェック

PC PASSは[STATUS.json](STATUS.json)、具体的hashは[evidence/protection.json](evidence/protection.json)、sector境界とELFは[evidence/rp2040-build.json](evidence/rp2040-build.json)。新バックアップと現在実機同定だけは承認後の実機操作が必要。承認なしに実施できる準備は完了しているが、実機の性能・音声・完走を理由にRelease READYへ変更してはいけない。
