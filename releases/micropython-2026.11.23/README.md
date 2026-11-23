# KAGURA-HD MicroPython 初回リリース

公開タグ: [`v2026.11.23-micropython.1`](https://github.com/siska-tech/kagura-hd/releases/tag/v2026.11.23-micropython.1)

MicroPython v1.26.0をベースにした、RP2040用の汎用GPU／FM音源FWです。
HDMI Framebuffer REPL、任意のKMF日本語フォント、XIAOのキーボードブリッジ入力、
Pythonから設定する4オペレータ×7声のFM音源を搭載しています。
MIDNIGHT TERMINALの演出・進行・音色・譜面はPythonアプリとして別配布し、FWには含めません。
写真のPico Wでも動作確認していますが、無線機能は含みません。

## 配布ファイル

|ファイル|用途|
|---|---|
|`kagura-micropython-qspi.uf2`|実機検証済みのQSPI版。通常はこちら|
|`kagura-micropython-spi.uf2`|SPI版。ビルドとUF2整合性を確認。今回のFWのSPI実機再生は未検証|
|`kagura-runtime-files.zip`|日本語REPL用フォントとGPU／FMのPythonサンプル|
|`midnight-terminal-micropython.zip`|任意で転送するPythonアプリと画像・譜面・音色・ライセンス|
|`kagura-hd-qspi-pcm-stream.fs` / `kagura-hd-spi-pcm-stream.fs`|既存の選定済みFPGA構成。今回RTLの更新はありません|
|`micropython-licenses.zip`|プロジェクト、MicroPython、SDK、関連ライブラリのライセンス文書|
|`release-manifest.json` / `SHA256SUMS`|バージョン、検証範囲、添付ファイルのSHA-256|

## 導入

1. Tang Nano 9KにQSPI版の`kagura-hd-qspi-pcm-stream.fs`を書き込み、
   [配線表](../../docs/kagura-fb-host-api.md#配線転送)のとおりRP2040へ接続します。
   既存のPCMストリーミングQSPI構成を使用中なら、FPGAの再書込みは不要です。
   FPGAの書込み方法は[トップREADME](../../README.md#ネイティブc版デモを試す)を参照してください。
2. PicoのBOOTSELを押しながらUSB接続し、`RPI-RP2`ドライブへ
   `kagura-micropython-qspi.uf2`をコピーします。既存のFWは置き換わります。
   ファイルシステムの配置は標準Picoの640 KiB FW／1408 KiB FSに合わせていますが、
   元FWによっては初回起動時にFSが初期化されます。
3. HDMIを接続します。`boot.py`／`main.py`がないFSではFramebuffer REPLが自動起動します。
   USBシリアルREPLも使用できます。既存の起動スクリプトがある場合はそれを尊重します。
4. 日本語REPLを使う場合は`kagura-runtime-files.zip`を展開し、
   `fonts/`をPicoのルートへ転送して再起動してください。未転送でもASCIIフォントで起動します。

mpremoteでフォントを転送する例です。`COM14`は自分のポートに置き換え、ZIPを展開した場所で実行します。
同じコマンド内で表示用フォントを閉じてから転送します。

```sh
mpremote connect COM14 exec "import kagura_repl; c=kagura_repl.console; c and c.close()" fs cp -r fonts :
mpremote connect COM14 reset
```

既存の起動スクリプトへREPLを追加する場合:

```python
import kagura_repl
kagura_repl.start()
```

SPIを使う場合は、FPGAもUF2もSPI版にそろえてください。実行時のSPI／QSPI切替えはありません。

## Pythonアプリと音源

`midnight-terminal-micropython.zip`の中身をPicoのルートへ転送すると、REPLから実行できます。
Pythonファイル群と`mt_data/`を同じルートに配置し、ライセンス文書も保持してください。
FWを書き換えず、Python側の演出・譜面・音色を編集できます。

```python
import midnight_terminal
midnight_terminal.run()
```

アプリ終了・Ctrl-C時はFramebuffer REPLへ戻ります。
独自の描画・発音は[GPU／FM API](../../software/kagura_runtime/README.md)を参照してください。
XIAOを使う場合は[HD用ブリッジFWと配線](../../software/xiao_keyboard/README.md)が必要です。

## 実機検証

- Tang Nano 9K＋RP2040、120 MHz、QSPI、HDMI 720p60。
- MIDNIGHT TERMINAL 104秒を完走。2671フレーム、平均25.68 fps。
  従来のネイティブC版は同じ104秒で3036フレーム、約29.19 fpsです。
- FMハードクリップ0、PCM補充最大30.944 ms、OBSのフレーム落ち増加0。
- OBS録音のクリップ0。基準波形との相関中央値は約0.994。
- 音源スレッドの起動・終了20回、譜面初期化40回、USB Ctrl-C試験10回、アプリ再起動3回を通過。
- ホスト33テスト、6240画面の参照比較、104秒分のFM検証を通過。
- XIAOブリッジv1の応答と不正フレーム0を確認。USBキーボードは未接続で、実打鍵は未検証です。

1台での有限試験です。SPI版のFWはビルド確認までです。
[詳細記録と写真](../../software/kagura_runtime/evidence/improvement-2026-11-23/summary.json)、
[確認画像](../../software/kagura_runtime/evidence/improvement-2026-11-23/contact-sheet.png)を保存しています。

## ビルドとライセンス

[ビルド手順](../../software/kagura_runtime/README.md#ハードウェアとビルド)と
[ソース](../../software/kagura_runtime/)を公開しています。MicroPython本体はMIT、
KAGURAの追加コードはApache-2.0です。依存ライブラリ・フォント等は添付ライセンスを参照してください。
