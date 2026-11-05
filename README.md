# KAGURA-HD

Tang Nano 9K（GW1NR-9C）向けのフレームバッファ型グラフィックスエンジンです。RP2040などのSPI/QSPIホストからPSRAM上の画面を更新し、HDMIへ映像と音声を出力します。

**実機Demoで使用したPCM2・ABI 1.4・QSPI Bitstreamを最終版として選定しました。** [公開用成果物とチェックサム](releases/pcm2-qspi-final/README.md)を用意しています。**SPI版はSTA不合格のためexperimentalへ隔離し、通常配布から除外しました。DO_NOT_PROGRAMを付けています。** [Release添付一覧](releases/README.md)。リポジトリの公開用スナップショットです。GitHub Release・タグはまだ作成していません。

[▶ 実機動作動画を見る（YouTube）](https://youtu.be/PA18OeB-7Fw?si=ddc6YioPDyehEmua)

## 最終版

|項目|内容|
|---|---|
|Bitstream|[kagura-hd-qspi-pcm2.fs](artifacts/validated/kagura-hd-qspi-pcm2.fs)|
|SHA-256|`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`|
|FPGA / Tool|GW1NR-LV9QN88PC6/I5 / Gowin Standard V1.9.12.04|
|Host|QSPI Mode 0、MSB先行、`KFB1` / ABI **1.4** / CAPS `FF`|
|映像|640×360、4bpp、16色RGB444パレット。整数2倍で1280×720・60Hz HDMI出力|
|画面メモリ|PSRAM、2ページ。PRESENTで垂直帰線中にページとパレットを反映|
|描画|FILL、READ/WRITE、overlap・ページ間対応の不透明COPY_RECT（BLIT）|
|BLIT制約|Xと幅は偶数、送受Xの差は8画素の倍数|
|カーソル|32×32・2bpp、透明色＋独立3色、形状2バンク、垂直帰線で反映|
|音声|signed8 PCM **2ch**、48kHz、左右GAIN・MASTER、HDMI stereo出力|
|SDK|[C](software/kagura_fb/kagura_fb.h)、[MicroPython Device](software/kagura_fb/kagura_fb.py)、[PCM Audio](software/kagura_fb/kagura_fb_audio.py)|

最終版の音声はPCM2専用です。旧6ch音源のHost設定は使用しません。ABI 1.2の描画・カーソル・BLITを継承し、音声CSRとCOMMITを追加しています。[Host ABI・音声契約](docs/kagura-fb-host-api.md)を参照してください。

## 実機Demoと確認範囲

- [BEYOND 16 COLORS](software/beyond16/README.md)：150秒・全8シーンを実機完走。Host timeoutと観測されたPCM STATUS faultは0。実更新3.9–21fpsで、目標30fpsは未達。[実機結果](software/beyond16/HARDWARE_RESULT.md)。
- [MIDNIGHT TERMINAL](software/midnight_terminal/README.md)：会話・演出・PCM2の同時再生を実機HDMI録画で確認。[実機結果](software/midnight_terminal/HARDWARE_RESULT.md)。
- [6シーンのMicroPython Showcase](software/kagura_fb/showcase/README.md)：PCプレビューと実機試験記録を区別しています。

両C Demoが使用したFPGA Bitstreamは上記SHA-256と同じです。RP2040のDemo firmwareは別の成果物です。FPGAのSRAM投入は電源断で消え、既存Flashの構成へ戻ります。

内部STAはSetup **+0.160ns**、Hold **+0.484ns**、Setup/Hold違反 **0/0**。Logic 7796、FF 5239、CLS 4247、BSRAM 19です。実機試験はnominal PIO QSPI 5MHzの有限試験で、最大通信速度、外部PSRAM I/Oの全PVT適合、全画面のbyte一致、長時間・複数基板の保証は含みません。SPI版はSTA未達・テスト未実施のため[experimental](artifacts/experimental/spi-sta-fail/README.md)へ隔離し、通常Releaseから除外しています。過去の評価JSONの`release_ready=false`は当時のゲート結果として保持します。[公開準備状況と制限](docs/release-validation.md)。

## ビルドと検証

QSPI版は実機で動作した既存Bitstreamをそのまま固定しています。再ビルドで採用ファイルを上書きしません。元のビルド入力40ファイルとSHA-256を[成果物ディレクトリ](releases/pcm2-qspi-final/)へ保存しました。

Windows、Gowin Standard V1.9.12.04、Python 3で、リポジトリルートから実行します。

```powershell
python tools/check-release.py
./tools/check-dependencies.ps1
./tools/build-fb.ps1 -Transport qspi
```

`-GowinExe 'C:/path/to/IDE/bin/gw_sh.exe'`で配置先を指定できます。出力は`build/kagura-fb-qspi/impl/pnr/kagura_fb.fs`です。Place1/Route2、Setup ≥0.100ns、Setup/Hold違反0を検査します。[正確な入力・ビルド手順](docs/standard-build.md)。

WSL/LinuxではPython 3、C11、g++、make、Verilator **5.032**、bash、flock、timeoutを使用します。

```sh
python3 tools/check-release.py
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-fb-verilator.sh
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-common-verilator.sh
bash tools/test-fb-audio-qspi.sh
bash tools/test-fb-wrap32.sh
bash tools/test-fb-wrap32-integration.sh
bash tools/test-fb-drivers.sh
# 任意：Unix MicroPython v1.26.0
MICROPYTHON=/path/to/micropython bash tools/test-fb-micropython.sh
```

[今回の統合後回帰](docs/release-preparation-validation.md)ではFB全26件、共通22構成、wrap統合12件、SDK29件、Demo PC20件が合格しました。[CI](.github/workflows/kagura-fb.yml)でもRTL・SDK・公開成果物を検証します。実機試験の再実行には配線・復旧手順と各Demoの手順を使用してください。

## 資料と出典

[資料案内](docs/README.md)、[配線・Host API](docs/kagura-fb-host-api.md)、[BLIT](docs/kagura-fb-blit.md)、[カーソル](docs/kagura-fb-cursor.md)、[整理内容](docs/cleanup.md)を参照してください。`artifacts/validated/`は実機確認済みQSPI、`artifacts/experimental/spi-sta-fail/`は書込み禁止のSPI実験物です。`build/`は作業用・録画・退避物で、公開対象から除外しています。日付付き文書は各時点の開発履歴です。

公開先は[siska-tech/kagura-hd](https://github.com/siska-tech/kagura-hd)。Kagura-9の`f562b2ec84605860fdb9f701f5b2e197b5ed4432`を基盤とし、内部RTL名`kagura_fb_*`と既存SDKパスを継承しています。本体は[Apache-2.0](LICENSE)。[NOTICE](NOTICE)、[THIRD_PARTY](THIRD_PARTY.md)、[出典](docs/sources.md)の表記を保持します。第三者コードと生成IPの条件はそれぞれの許諾に従います。
