# MIDNIGHT TERMINAL

深夜のバー、雨、店員ミオとの短い会話。端末を調べると、美咲の架空ログが画面へ侵入し、「警告：この記憶はあなたのものではありません」を残して日常へ戻る。オリジナルの日本語ADV／KAGURA-HD技術ショーケース。

**PCプレビュー、RP2040 C版のFlash投入、5MHzでの実機autoplay 1周とHDMI映像・音声captureを確認済み。性能目標は未達。Demoの性能目標は未達です。FPGA Bitstreamは[PCM2 QSPI最終版](../../releases/pcm2-qspi-final/README.md)として選定済みです。** [実機結果・録画](HARDWARE_RESULT.md)。

## 見る・遊ぶ

Windowsでこのディレクトリを起点に実行する。既存の機器を必要とせず、シリアル・JTAG・USBを開かない。

```powershell
./tools/run_preview.ps1
```

640×360、16色、2倍の整数拡大。↑↓で注文を選択、Enterで決定／会話を全文表示。Rで最初から、SでPNG保存、Fで低頻度の部分色変化を切り替える。初期設定は点滅抑制。無操作でも88秒で一周し、ループする。選択肢の回答は3種類あり、その後は共通の異常シーンへ進む。実機RP2040版はUARTの`w`/`s`/Enter入力に対応します。

Python、Tk、Pillow、pygame-ceが必要。ネイティブC DLLがなければMSVCでビルドする。今回取得した依存はローカルの`.deps/`に置いた。音声機器を初期化できない場合も映像は動く。GUI smokeでTk描画・48kHzミキサー初期化を確認したが、スピーカーからの聴感試験は行っていない。

生成済みの[オフライン再生ページ](out/index.html)には、Cエンジンで記録した全シーンのフレーム、再生／停止、シーク、章ジャンプ、88秒のPC音声ミックスがある。外部サーバー不要。ブラウザの音声許可のためPLAYを押す。ここでは記録済みautoplayを再生し、分岐操作は上記ライブ版で行う。[一覧画像](out/contact-sheet.png)も参照。これはPC版で、[実機録画](../../build/midnight-hardware/midnight-terminal-hardware.mp4)とは別。

## 再現手順

Python 3.12とMSVC 2022 x64開発ツールを使用した。別環境では`build_pc.ps1`のvcvarsパスを調整する。

```powershell
python -m pip install --target .deps -r requirements.txt
python tools/generate.py
./tools/build_pc.ps1
python tools/test.py
python tools/test_device.py
python tools/preview.py --headless
python tools/mix_audio.py
python tools/preview.py --smoke-gui
```

`generate.py`は保存した配布アーカイブのみを使う。ネット接続・OSフォントに依存せず、字形、PNG、4bpp、C配列、PCM/WAVを再生成する。配布物のSHA-256が保存値と違えば停止する。

個別の変換入口は`tools/convert_mplus.py`、`tools/convert_misaki.py`。`story.json`のUTF-8から必要文字を抽出し、欠字を検出して停止する。M+のJIS0208はEUC-JP経由でUnicodeへ変換し、半角カナは**公式JIS0201差分**をオフライン適用する。美咲はUnicode BDFを使う。BBX・ベースライン・DWIDTHを保持した1bpp行データとUnicode索引を、独立したFlash上のグリフ配列へ変換する。

M+は12px系だが、実配布の`FONTBOUNDINGBOX`は12×13、ascent 11／descent 2、全角送り12・半角送り6。美咲ゴシックは8×8、ascent 6／descent 2、送り4／8。警告画面ではASCIIも8pxセルに配置する。両subsetは各300字。実際に使う字に検査用文字・ASCIIを加えた小さな集合で、全文字を展開しない。

RP2040ビルドはArm GNU 14.2.Rel1（GCC 14.2.1）、Pico SDK 2.1.1を使用する。SDKは`toolchain/pico-sdk`、展開したコンパイラは`toolchain/arm/bin`へ置く。SDK commitは`bddd20f928ce76142793bef434d4f75f4af6e433`。

```powershell
./tools/build_rp2040.ps1
./tools/build_qspi_tests.ps1
python tools/test_qspi.py
# WSL + Verilator がある場合（実機操作なし）
wsl -e bash software/midnight_terminal/tools/test_qspi_rtl.sh # repo rootから
```

[ELF](out/rp2040/midnight_terminal.elf)・[bin](out/rp2040/midnight_terminal.bin)を生成する。CMakeのupload/programターゲットは設けていない。TinyUSBをSDKの固定submodule版で取得し、USB CDCとUARTを有効にした。実機版はUSBの`g`で事前診断・再生開始、`q`で停止する。`build_rp2040.ps1`は元PCMを可逆圧縮してからビルドし、既存filesystemより手前に収める。元字形・元音声を再生成した際も同じ手順でよい。この実行環境では32bitコンパイラがサンドボックス内でDLL再配置エラーになるため、通常環境で同じビルドを実行した。

## C実装とSDK契約

|責務|実装|
|---|---|
|シーン管理、時刻ベース演出、入力、選択肢、差分スケジューラ|`src/mt.c` / `src/mt.h`|
|UTF-8、Unicode索引、2フォント、禁則・折返し、会話タイプライター|同ファイル内の独立した関数群|
|素材管理・固定シナリオ・独立グリフアトラス|`generated/assets.inc`、`generated/story.inc`、`story.json`|
|GPU・パレット・カーソル・PCMアダプター|`src/mt_device.c` / `mt_device.h`|
|RP2040、UART入力・診断出力|`src/rp2040_main.c`|
|KAGURA-9由来の5MHz PIO QSPI、timeout・転送統計|`src/mt_qspi.c/h`、`vendor/kagura_host.pio`|
|PC framebuffer・記録・キーボード・音声|`tools/preview.py`から同じCエンジンを呼ぶ|
|独立画素／行順序・SDKレジスタモデル検査|`tools/test.py`、`tools/test_device.py`|

小さな作品なのでCの各責務を関数単位にまとめた。新規VMやスクリプト実行系はない。既存`../kagura_fb/kagura_fb.c/h`を**変更せずリンク**する。PCM CSR補助は既存ABI 1.4のPython facade／保存されたRTL契約を照合してCで実装した。

開始時は`KFB1`、major 1／minor 4、GPU CAPS低7bitを照合し、bit7があればPCMを使う。GPU CAPS不足は停止。音声CAPSなし、PREPARE失敗、STATUS fault等は診断を保持して映像へfallbackする。未知のGPU命令、GPU文字描画、透明BLIT、任意PSRAMアドレスからのBLITは仮定しない。

- FILL／BLIT／WRITE／PALETTE／PRESENTは既存C SDK経由。
- 4bppは偶数Xが上位nibble、stride 320B。WRITEはSDKが4B整列、最大64B、maskへ変換する。
- BLITはpage間／page内だけ。X・幅は偶数、`sx % 8 == dx % 8`。Yは1px単位。重なりは既存契約を使う。
- 背面ページの更新後にPRESENT。静止部分は再転送せず、会話は新しく現れる文字だけを更新する。シーン準備前は黒パレットをPRESENTして両ページ再構築を隠す。
- 32×32、MSB-first 2bppカーソルを独立bankへ設定し、会話送り／選択位置を示す。PC画像はカーソルを別合成し、画素CRCはFramebuffer本体のみを対象とする。
- 音声はINDEX/DATA 54/55、PCM0 0x60／PCM1 0x80、MASTER 0xE0、COMMIT opcode 7。START/END/LOOPはPREPARE、GAIN/ENABLE/MASTERはCOMMITのsnapshotで適用する。効果音のCOMMITでも両chの所有shadowを再設定し、BGM設定を保持する。
- 既存制御のSTOP→非ACTIVE確認→CLEAR→範囲設定→PREPARE→READY確認→COMMIT。各待機はtimeout付き。再生エラーは1秒ごとにSTATUSを監視し、映像fallbackへ移る。不確かな送信を再送しない。

## 演出と素材

0–12s BOOT、12–30s BAR、30–40s CHOICE、40–47s ANOMALY、47–65s SYSTEM、65–80s RESTORE、80–88s ENDING。

全画像はPillowの矩形・多角形・線と実フォントから生成したオリジナル。店員、瞬き／異常表情、雨の窓、棚・瓶、ネオン、端末、ロゴ、会話UIの編集可能なインデックスPNGを`generated/`へ保存した。RGB444へ量子化した共通16色を使い、警告時は同じindexを暗赤／白／淡シアンへ変更する。通常のindex14はネオンと照明に共有し、オプションの弱い色変化は両方へ作用する。

警告は80列×44行、3,520セル（空白を除く3,013字）＋最上部の「FICTION / 架空ログ」。文字色属性はセルごとに事前焼込みする。意味のある32種の架空ログと行番号を組み合わせる。最初はバーに数行が重なり、行がUIを覆い、満杯になった後はFramebuffer内BLITで上へ流れる。新しく露出した数pixel分だけ4bpp素材から転送し、画面全体の文字を毎フレーム送らない。任意の元行をFlashの行offsetで選び、宛先行へ置換できる。行順序・境界は独立オラクルで検査した。

ABIのBLITには任意のPSRAM素材アドレス指定がない。このため警告素材はPSRAMへ事前保存しつつ、**新しい行の供給元は同じFlash配列**とした。PSRAMバックアップをGPUが直接読めると偽っていない。スクロールの既存画素はBLITを使い、Host READを避ける。Phase後半は小刻みのY移動、局所色変化は初期無効、最終文は2.5秒、黒画面は約0.5秒。

BGM「After the Last Train」は8秒のオリジナルループ。PCM0へ低音・柔らかな倍音・短い音を合成する。PCM1は決定、文字通知、警告、復旧の4素材。全てsigned 8bit mono／48,000Hz。再生用WAVは同じsigned8をsigned16へ展開したもの。ブラウザ用88秒WAVはHostイベント時刻によるPCミックスで、HDMI音声captureではない。

## メモリ・検証・残課題

詳細は[検証・性能レポート](REPORT.md)、[PSRAM配置](memory.json)、[実機検証計画](HARDWARE_PLAN.md)、[ライセンスと出典](LICENSES.md)、[判定JSON](STATUS.json)。

最終RP2040リンク値とELF SHA-256は[`evidence/rp2040-build.json`](evidence/rp2040-build.json)。BSSはスタックを含まない。4KiBのスタックを明示し、最大のローカル枠はtext rendererの1,136B。Framebufferや全文字はRP2040 RAMに置かず、Flash上のconst素材と小さな行・配置バッファを使用する。

**転送路はKAGURA-9で実績のある5MHz PIO版へ更新した。** RP2040 120MHz／PIO分周2／12 cycles per SCK、CS 250/40/250ns、2mA・slow slew・入力Schmittを再利用した。旧5µs待ちbitbangはこの実行経路から削除した。原PIOは変更せず、HDの6bitレジスタへC側を適合した。詳細は[5MHz移植・検証記録](QSPI_REPORT.md)。

実機でPSRAM 72件・FILL/BLIT・1周再生とPCM0 BGM＋PCM1決定音の共存を確認した。通常schedulerは概ね30Hzだが、警告増殖中の一部は約0.65–3Hz、満杯後は約19–20Hz、背景ロードは約3.5秒。**30fps・非ブロッキング・60〜90秒の実周回目標は未達。** 5MHzは設定値で、SCKのオシロ測定はしていない。全画面readback CRC、全分岐・全効果音・PVTは残る。詳細は[実機結果](HARDWARE_RESULT.md)。

作業ブランチは`midnight-terminal-showcase`。作業開始時の既存未コミット変更は保持し、新規成果物は未コミット。RTL、Controller/PHY、PLL、SDC/CST、Bitstream、既存STA候補は変更していない。後続の明示承認によりRP2040 firmware Flashを書換え、既存候補をFPGA SRAMへ1回投入した。元RP Flash全体を退避し、KAGURA-9のfilesystemとFPGA Flashは維持した。Merge／Releaseは行っていない。


