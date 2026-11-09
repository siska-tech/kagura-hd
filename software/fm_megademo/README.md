# KAGURA-HD — FOUR OPERATORS

[![実機動画（YouTube）](https://img.youtube.com/vi/iypg81KaGmQ/maxresdefault.jpg)](https://youtu.be/iypg81KaGmQ?si=ItaV4tVjuPjqaDHs)

**A SOFTWARE FM SYNTH MEGADEMO.** RP2040 の C で書いた、132 秒のオリジナルデモです。音は、RP2040 の 2 つ目のコアで動くソフトウェア FM 音源がすべてリアルタイムに合成します。合成した 48 kHz ステレオは、[選定版 bitstream](../../releases/pcm-stream-qspi/README.md) の PCM ストリーミングで HDMI へ送ります。映像は 640×360・16 色で、8 つのシーンがあります。

## 構成

|部分|内容|
|---|---|
|音源（[fm.c](src/fm.c)）|4 オペレータ FM を 6 声。4 種のアルゴリズム、オペレータごとの ADSR、フィードバック、ディレイ付きビブラートを持つ。キック、スネア、ハットも合成する。ステレオエコーと TPDF ディザをかけて signed8 に変換する。描画処理はすべて整数演算|
|曲|A マイナー、120 BPM、65 小節のオリジナル曲。イントロ → 主題 → 展開 → ブレイクダウン → クライマックス → フィナーレの順に進み、最後の和音の余韻で終わる|
|ストリーミング（[stream.c](src/stream.c)）|FPGA が半面（4096 フレーム）を返すたびに補充する。補充は 64 byte 単位に分け、描画コマンドの合間に進める。返却から 45 ms を過ぎた場合だけ、残りを一括で書く|
|映像（[demo.c](src/demo.c)）|FILL・COPY・PALETTE・PRESENT・WRITE だけを使う。静止画をパレット循環で動かすシーンでは、画像を前のシーンの再生中に裏ページへ 64 byte ずつ書き込んでおく|
|コア分担（[rp2040_main.c](src/rp2040_main.c)）|core 1 は合成だけを担当し、最大 12288 フレーム先まで生成する。core 0 は描画とストリーミングを担当する。画面の時刻は、音声の再生開始（AUDIO_COMMIT 完了）からの経過時間で決める|

|# |シーン|内容|
|---|---|---|
|0|INTRO|コッパーストライプ。タイトルの文字が拍に合わせて現れる|
|1|PLASMA|パレット循環のプラズマ|
|2|TUNNEL|パレット循環のトンネル|
|3|SCROLLER|8 px 単位の BLIT スクローラー、コッパー、6 声分のレベルメーター|
|4|VECTOR|フラットシェーディングの正二十面体（20 面、4 px の走査線）と星空|
|5|SCOPE|再生中の音のオシロスコープと、24 個のオペレータエンベロープ|
|6|MOIRE|2 つの波源による干渉縞|
|7|FINALE|クレジットとフェードアウト|

## 見る・作る

すぐに実機で見るときは、[Releases](https://github.com/siska-tech/kagura-hd/releases/latest)の`four-operators.uf2`を使います（SPI版のFPGAと組み合わせるときは`four-operators-spi.uf2`）。手順は[ルートのREADME](../../README.md#すぐに試す)にあります。このUF2は、下のRAM ELFと同じプログラムを`copy_to_ram`の形式にしたものです。起動時にFlashからSRAMへ写して実行し、約5秒後に自動で始まります。

PC プレビューの作り方です。KFB の振る舞いモデルに、実物の SDK・デモ・音源をつないで描画します。

```bash
# WSL / Linux。FFMPEG に Windows の ffmpeg.exe を指定してもよい
software/fm_megademo/tools/preview.sh build/fm-megademo
```

RP2040 用の RAM 専用 ELF をビルドします。`-Release` を付けると、配布用の UF2（`build/fm-megademo/rp2040-release/four_operators.uf2`）を作ります。UF2 への変換には picotool 2.x を使います。

```powershell
./software/fm_megademo/tools/build_rp2040.ps1
./software/fm_megademo/tools/build_rp2040.ps1 -Release
```

実機で実行します。手順は、選定版 bitstream を FPGA の SRAM へ投入し、RAM ELF を実行し、HDMI を映像と音声ごとキャプチャし、承認済みの Queue8 に戻し、RP2040 の Flash が変わっていないことを照合する、の順です。

```powershell
python software/fm_megademo/tools/run_hardware.py build/fm-megademo/hw-XX `
  --elf build/fm-megademo/rp2040/four_operators.elf --elf-sha <sha256> --reference build/fm-megademo/pc.wav
# 配布用UF2：RP2040のFlash全体を退避してから書き込み、ホストから開始せずに自動開始を待つ。終了後に書き戻して照合する
python software/fm_megademo/tools/run_hardware.py build/fm-megademo/hw-XX --flash --autostart `
  --uf2 build/fm-megademo/rp2040-release/four_operators.uf2 --elf build/fm-megademo/rp2040-release/four_operators.elf `
  --elf-sha <sha256> --reference build/fm-megademo/pc.wav
```

SPI版のFPGA（`kagura-hd-spi-pcm-stream.fs`）で使うときは、Hostも同じくSPIでビルドします。`-HostLanes 1` を付けると、Kagura-9のPIOプログラム `kagura_spi` を使ったSPI 5 MHzになります。`-SpiPioDiv 1.25` を足すと8 MHzです（任意の高速設定で、動作を保証する周波数ではありません）。実機ではSPI版のbitstreamを `--image` で渡します。

```powershell
./software/fm_megademo/tools/build_rp2040.ps1 -Release -HostLanes 1 -Output build/fm-megademo/rp2040-release-spi
python software/fm_megademo/tools/run_hardware.py build/fm-megademo/hw-XX --flash --autostart `
  --uf2 build/fm-megademo/rp2040-release-spi/four_operators.uf2 --elf build/fm-megademo/rp2040-release-spi/four_operators.elf `
  --elf-sha <sha256> --reference build/fm-megademo/pc.wav `
  --image artifacts/validated/kagura-hd-spi-pcm-stream.fs --image-sha e9f67c683df4ab9c5f9ee382433d0a46f101578dbdcf66684da14992ce8c1767
```

## 実機結果

2026-11-08、Tang Nano 9K と RP2040（120 MHz、QSPI 5 MHz）で 1 回実行しました（`build/fm-megademo/hw-03`）。FPGA には選定版 `kagura-hd-qspi-pcm-stream.fs`（`fad15376…`）を、RP2040 には RAM ELF（`87a142fc…`）を SRAM へ投入しています。FPGA と RP2040 の Flash への書込みは 0 回です。終了後は承認済みの Queue8 に戻し、RP2040 の全 Flash が実行前と一致することを確認しました。

|項目|結果|
|---|---|
|終了|`STOP rc=0`、QSPI timeout 0、device error 0|
|PCM ストリーミング|1546 半面を補充、token の周回 6 回。HALF_FREE を検出してから公開するまでの最悪は 54.6 ms（期限は 85.3 ms）|
|FPGA の状態|ch STATUS は左右とも 0x03（READY・ACTIVE。UNDERRUN と fault はなし）、HDMI STATUS は 0x00|
|合成|core 1 の稼働率は約 51%（132 秒中 68.0 秒）。core 0 が合成を待った回数は 0。ピークは 42253、ハードクリップは 0|
|HDMI 録音|基準に音がある区間で、録音が 10 ms 単位で欠けた箇所は左右とも 0。PC で生成した基準との 1 秒ごとの相関は、中央値 0.994、最小 0.827。最小はベルが長く伸びるブレイクダウン区間で、ラグは区間ごとに追い直している。キャプチャとのクロック差は約 16 ppm（132 秒で 104 フレーム）|
|フレーム数|3429。シーン別には 472 / 471 / 477 / 480 / **262** / **194** / 478 / 595|

パレット循環のシーンとスクローラーは約 30 fps で動きます。VECTOR は約 16 fps、SCOPE は約 12 fps です。どちらも、ほぼすべてを同期式の FILL で描くため、QSPI の通信量で速度が決まります（1 コマンドあたり約 180 µs）。同じ時間には、音声の補充（1 半面あたり 128 回の WRITE）も行われています。

この結果は 1 枚の基板、1 回、132 秒の有限試験です。速度の目標は設けていません。相関が 1 にならないのは、初期化時の `sinf`/`pow` が PC と RP2040 で末尾のビットまで一致しないため、位相がわずかにずれるからです。実機の画像は [contact sheet](evidence/hardware-contact-sheet.png) にあります。結果の JSON と USB ログも [evidence/](evidence/) に保存しました。

### 配布用 UF2

2026-11-09 に、配布用 UF2（`6c8a2fd9…`、ELF `4df2009e…`）を同じ基板で 1 回実行しました（`hw-uf2-auto`）。RP2040 の Flash 全体を退避してから UF2 を書き込み、ホストからは開始の指示を送らず、終わるまで USB のポートも開いていません。デモは自動で始まり、`STOP rc=0`、QSPI timeout 0 で完走しました。録音の 10 ms 単位の欠落は左右とも 0、PC の基準との相関は中央値 0.993、最小 0.914 でした。フレーム数は 3425 です。終了後に退避した内容を書き戻し、全 2 MiB が実行前と一致することを確認しています（RP2040 の Flash 書込みは 2 回、FPGA の Flash 書込みは 0 回）。UF2 の中身が ELF の内容と一致することも、ブロック単位で確認しました。記録は [release-uf2-result.json](evidence/release-uf2-result.json) です。

RAM ELF を既定の設定でビルドし直すと、読み込まれる内容は `hw-03` の ELF と比べて、埋め込まれたビルド日付の 1 バイトだけが異なりました。

途中の不具合と修正です（`hw-01`、`hw-02`）。

- 130 秒で再生を止めていたため、最後の和音の余韻が切れていた。終了を 132 秒にした。
- SCOPE が、曲全体の時刻ではなくシーン内の時刻で波形を読んでいた。そのため実機では波形が平らになっていた。
- VECTOR の走査線を 3 px から 4 px にした（12.4 fps → 16 fps）。

## ライセンス

[LICENSES.md](LICENSES.md)
