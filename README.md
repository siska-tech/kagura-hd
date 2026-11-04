# KAGURA-HD

Tang Nano 9K（GW1NR-9C）向けのフレームバッファ型グラフィックスエンジンです。SPI/QSPI ホストから PSRAM 上の画面を更新し、HDMI へ映像と音声を出力します。

公開先は [siska-tech/kagura-hd](https://github.com/siska-tech/kagura-hd) です。Kagura-9 の `f562b2ec84605860fdb9f701f5b2e197b5ed4432` を基盤に開発しました。公開名称は KAGURA-HD、内部 RTL 名は `kagura_fb_*`、ホスト識別は `KFB1`、現行 ABI は **1.2** です。既存の C/MicroPython API とソースパスを継承しています。

## 現行仕様

|項目|実装|
|---|---|
|映像|論理 640×360、4bpp、16 色 RGB444 パレット。整数 2 倍で 1280×720・60 Hz HDMI 出力|
|画面メモリ|内蔵 PSRAM、2 ページ。PRESENT を垂直帰線で反映|
|描画・転送|FILL、PSRAM READ/WRITE、不透明 COPY_RECT（BLIT）|
|BLIT 制約|X と幅は偶数、送受 X の差は 8 画素の倍数。重なり・ページ間コピーに対応|
|カーソル|論理 32×32・2bpp、透明色と独立した 3 色、形状 2 バンク、垂直帰線で反映|
|音声回路|6 音源＋PCM 2ch の合成と HDMI 音声出力|
|ホスト|SPI/QSPI Mode 0、MSB 先行。ホストと bitstream のレーン数を一致させる|
|ソフトウェア|ポータブル C、MicroPython。公開 API の範囲はホスト ABI 資料に記載|

起動時に画面と無音 PCM データを初期化してから命令を受け付けます。ABI 1.1 の命令・カーソル機能に、ABI 1.2 で aligned BLIT を追加しました。詳細は [ホスト ABI と API](docs/kagura-fb-host-api.md)、[BLIT](docs/kagura-fb-blit.md)、[カーソル](docs/kagura-fb-cursor.md) を参照してください。

公開音声制御 API、任意位置・透過 BLIT、文字描画は後続の対象です。HDMI・音声・PSRAM を接続した実機での正常動作確認は完了していません。

## WSL/Linux のクリーン検証

Python 3、C11 コンパイラ、g++、make、Verilator **5.032**、bash、flock、timeout を用意します。MicroPython 試験には Unix 版 **v1.26.0** が必要です。固定コミットとビルド設定は [CI](.github/workflows/kagura-fb.yml) にあります。

公開後の取得と、リポジトリルートでの実行例です。

```sh
git clone https://github.com/siska-tech/kagura-hd.git
cd kagura-hd
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-fb-verilator.sh
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-common-verilator.sh
bash tools/test-fb-drivers.sh
MICROPYTHON=/path/to/micropython bash tools/test-fb-micropython.sh
```

Windows からはリポジトリルートで `wsl -- bash tools/test-fb-verilator.sh` を実行できます。HDMI 派生ソースは各入口が固定された原版から自動生成します。FB 回帰ログは `build/fb-verilator/`、共通回帰ログは `build/common-verilator/` に出力します。

## Windows の Gowin ビルド

Gowin Education **1.9.11.03** と Python 3 を導入し、リポジトリルートで実行します。

```powershell
powershell -NoProfile -File tools/check-dependencies.ps1
powershell -NoProfile -File tools/build-fb.ps1 -Transport spi
powershell -NoProfile -File tools/build-fb.ps1 -Transport qspi
```

Gowin の配置先が既定と異なる場合は `-GowinExe 'C:/path/to/IDE/bin/gw_sh.exe'` を指定します。SPI の生成先は `build/kagura-fb/impl/pnr/kagura_fb.fs`、QSPI は `build/kagura-fb-qspi/impl/pnr/kagura_fb.fs` です。スクリプトは合成・配置配線エラー、Setup 余裕 0.10 ns 以上、タイミング違反 0 を検査します。

## 検証結果

2026-11-04 の分離後クリーンビルドでは、Verilator 5.032・seed 1 の FB 全 **26 件**、共通 HDMI・音声・メモリ全 **22 構成**、C/Python ドライバ **15 件**、MicroPython **3 グループ**が合格しました。BLIT・FILL・READ/WRITE・PRESENT、カーソル、SPI/QSPI、HDMI 映像と音声の結合を含みます。

|Gowin 構成|Logic|FF 合計|CLS|BSRAM|DSP|Setup ns|Hold ns|
|---|---|---|---|---|---|---|---|
|SPI|7815|5227|4245|19|1|1.122|0.558|
|QSPI|7795|5230|4223|19|1|0.660|0.552|

両構成の Setup/Hold 違反は 0 です。整理前後で資源と slack が一致し、`.bin` はバイト単位に一致しました。`.fs` と `.binx` は生成時刻ヘッダだけが異なりました。公開用スナップショットでの再検証結果と SHA-256 は [公開検証記録](docs/publication-audit.md) に記載しています。

## 実機検証

CDC 制約の妥当性、外部 PSRAM I/O タイミング、映像・音声品質、SPI/QSPI 最大速度、長時間負荷と基板間再現性が未検証です。数値 STA は実機動作の保証とは区別して扱います。`timing-status.json` の `release_ready` は false です。

Dynabook で用意するファイル、配線、診断 Top、記録項目は [実機検証手順](docs/kagura-fb-dynabook.md) にあります。

MicroPython の SPI 接続例です。`software/kagura_fb/kagura_fb.py` をホストへ配置し、資料の配線を確認して使用します。

```python
from kagura_fb import connect_rp2040

gpu = connect_rp2040(baudrate=1000000)
gpu.fill_rect(1, 0, 0, 640, 360, 1)
gpu.present(1)
gpu.fence()
```

## 資料と継承元

- [資料案内](docs/README.md)
- [ソースマニフェスト](rtl/fb/sources.f)
- [基本設計の記録](KAGURA-FB-design.md)
- [実装・試行の記録](docs/kagura-fb-implementation.md)
- [Kagura-9 との関係と Desktop 移管](docs/kagura-fb-separation.md)

Kagura-9 専用ソフトウェアと Desktop・ゲームは分離しました。共通 RTL、直接回帰、ハードウェア診断 Top は保持しています。継承資料の過去の数値は各時点の記録で、現行の仕様と検証結果はこの README とホスト ABI 資料を参照してください。

本体のライセンスは [Apache-2.0](LICENSE) です。継承元の著作権・出典と第三者コードの表記は [THIRD_PARTY.md](THIRD_PARTY.md) と [出典](docs/sources.md) に記載しています。hdl-util/hdmi の著者 Sameer Puri、Copyright 2019 の表記と MIT / Apache-2.0 の両ライセンス本文を保持し、Apache-2.0 を選択して利用しています。
