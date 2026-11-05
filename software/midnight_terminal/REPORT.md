# 検証・性能レポート

最終状態：PCプレビュー、日本語フォント、GPUコマンド、PCMデータ、RP2040 Cビルドと独立画素検証を完了。後続のユーザー承認によりC firmware Flash書換えと既存FPGA SRAM投入を実施し、実機autoplayを1周録画した。既存filesystemはbyte一致を確認して保持。BGM stereo相関0.999692、BGM中のPCM1決定音相関0.999914。性能・全分岐・全画面CRC等は残る。[実機結果](HARDWARE_RESULT.md)。Release NOT READY、`release_ready=false`。

## 実施結果

`evidence/pc-tests.log`：8テストPASS。UTF-8正常・不正列、半角／全角、未知文字代替、独立した原BDF baseline照合、折返し／改行／基本禁則、nibble・重なり・palette/PRESENT、警告行順序・漸増・スクロール・黒画面・復旧、3分岐／ループ、PCMフォーマット・範囲を含む。

`evidence/sdk-tests.log`：6テストPASS。既存C SDKの実descriptorを、リポジトリの独立register/pixel Modelへ送った。160件のランダムFILL、128件のBLITと画素比較、不正4件の送信前拒否、非整列mask WRITE、15時点での全Framebuffer＋palette一致、PCM COMMIT snapshotのBGM保持、STOP／再開、faultによる映像fallback、実機用事前診断と最初のerrorで停止することを検査した。これはFPGAサイクル／prefetch／HDMI音声を模擬する試験ではない。BGMの可逆LZについて、別のC試験4件が元384,000byteとの完全一致・history wrap・不正stream・sink失敗での停止を検証した。

追加の`evidence/qspi-tests.log`：8テストPASS。KAGURA-9の原PIOを再利用した5MHz転送路のC実装、6bitレジスタ、dummy／ターンアラウンド、256byte、timeout停止・再送禁止と、実際にアセンブルしたPIOの周期・setup・IO競合を検査した。さらに候補04の無変更RTLを使う5MHz board-top機能シミュレーションがPASSし、Host upload/readback/FENCE、PCM2 sample oracle、COMMIT、gain、pause/resume、loop/one-shot、lateなしを確認した。clock／DDR PHY／LVDSは既存の機能モデルを使っており、HD実機の検証ではない。詳細は[QSPI_REPORT.md](QSPI_REPORT.md)。

88秒・無操作autoplayをPC Cエンジンで走査し、全7場面と警告内5時点をPNG保存。録画用フレームは1,896枚。Tk GUI描画とpygame 48kHz初期化もsmoke成功。ブラウザHTMLの手動全操作試験は未実施。後続の実機captureはPC記録と別に`build/midnight-hardware/`へ保存した。PC音声ミックスを実機録音に読み替えていない。

## PC計測（ハードウェアの値ではない）

|測定|値|
|---|---:|
|論理時間|88,000ms|
|PC preview tick平均|0.415ms|
|PC preview tick P95|0.569ms|
|PC preview tick最大|142.229ms|
|PRESENT回数（準備の黒PRESENT含む）|1,903|
|Host素材WRITE byte（抽象adapter）|2,246,734B|
|実C SDK descriptor数（PCM起動を含む）|57,742|
|PC protocol register WRITE byte|3,830,561B|
|PC protocol register READ byte|467,952B|
|PC protocol transaction数|680,154|

preview tickはPython backend・trace生成を含むがPNG圧縮／Tk描画／音声mixを含まない。33ms刻みの仮想時計による計測で、平均値の逆数を実機FPSとは扱わない。静止時にはPRESENTを省くため、全PRESENT数／88をアニメーションFPSとも扱わない。通常の雨と満杯後の警告スクロールは33msごとの更新を狙い、警告増殖は130msごとの行追加。

独立register/pixel Model経由のC SDK実行は平均10.816ms／P95 100.955ms／最大237.964ms。Pythonの画素単位BLIT snapshotに時間を費やす検査用モデルで、これもHost／FPGAの処理速度ではない。全88秒の実descriptorと毎秒集計を`out/wire-descriptors.jsonl`、`evidence/wire-report.json`へ保存した。

後続実機測定では、開始指示→最初の画像約20.16秒、背景再構築約3.5秒、最初の画像→次BOOT約95秒。通常schedulerは概ね30Hz、警告増殖は一部0.65–3Hz、満杯後は約19–20Hz。これはPRESENT／HDMI refreshの直接測定ではない。1周末尾wire 6,753,735B／839,060 transactions／transaction時間57.60秒、最長352µs、timeout 0。FENCE単体・PRESENT ACK単体・physical SCKは未測定。5MHzのPIO設定を30fpsの達成と同一視しない。同期ロード・細かいtransactionの削減は残課題で、性能目標は未達。

## ROM / RAM

Pico SDK 2.1.1、GNU 14.2.1、RP2040 Cortex-M0+のリンク成功。text 480,304B、data 0B、BSS 37,040B。4KiB stackを別途明示した。`.su`でtext rendererのローカル枠1,136B、mt_tick 224B、既存SDK transfer 192Bを確認した。これは関数単体の静的値であり、割込みを含む実測stack high-waterではない。全文字／全FramebufferはRP2040 RAMへ配置していない。配置先のFlashアドレスとstack symbolは`evidence/rp2040-build.json`。

実機向け版は既存filesystemの開始640KiBより小さくするため、BGMを可逆LZへ圧縮し、32KiBのhistory RAMからPSRAMへ64Bずつ展開・全量照合する。USB CDCで開始指示・ログ・復旧を扱える。PC DLLは非圧縮の元PCMを使うため、そのPCコマンド集計を実機版の全量読戻し付き起動コストとは同一視しない。

MSVCの既存SDK部分にC4389とC4701の警告がある。保護対象SDKをこの作業で修正していない。Arm Cビルドでは新規Cの警告はなく、TinyUSBを固定submoduleから取得したためUSB未取得警告も解消した。

## 証跡と保護

各時刻のFramebuffer CRCは`evidence/frame-crc.json`。PNGは別合成のcursorを含み、CRCはindex framebufferのみなのでPNGファイルCRCと比較しない。コマンドtraceは`out/commands.jsonl`（抽象命令）、`out/sdk-command-trace.json`（15時点のSDK）、`out/wire-descriptors.jsonl`（全周SDK）。

保存した278個のRTL／board／制約／既存SDK／候補04入力・Bitstream hashは`tools/preserve.py --check`で一致。既存のSTA資格を再認定するものではない。既存未コミット変更を保持し、FPGA回路／PLL／制約／Bitstream／FPGA Flashは変更していない。ユーザーの後続明示承認によりRP firmware Flashを変更し、既存候補をFPGA SRAMへ1回投入した。元RP全Flashを退避し、既存filesystemを保持した。Merge／Releaseは未実施。
