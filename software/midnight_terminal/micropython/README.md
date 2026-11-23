# MIDNIGHT TERMINAL / MicroPythonアプリ

[汎用KAGURA-HD GPU FW](../../kagura_runtime/README.md) 上で動くPythonアプリです。
専用のCモジュールや専用FWは不要です。作品固有のコードや素材を汎用FWへfreezeしません。

|作品固有の内容|Python側の編集先|
|---|---|
|台詞、選択肢、ログ、文字送り速度、シーン境界|[story.py](../tools/story.py)|
|全7シーン、描画指示、フェード、まばたき、グリッチ|[midnight_show.py](midnight_show.py)|
|画像・字形・タイトルの読み込みと描画|[midnight_graphics.py](midnight_graphics.py)|
|FM音色の全オペレータ設定・プリセット|[midnight_instruments.py](midnight_instruments.py)|
|BGMの全譜面、音楽シーケンサ、ミキシング指示、ピッチ・音量・ループ効果|[midnight_music.py](midnight_music.py)|
|文字送り・選択・心音・警報などの効果音レシピと時刻|[midnight_fm.py](midnight_fm.py)|
|再生ループ・開始・停止・フレームコールバック|[midnight_terminal.py](midnight_terminal.py)|

ネイティブFWに残るのは、汎用GPU ABIと、Pythonから設定されるFMサンプル合成・
PCM転送などの基本処理です。画像・フォント表・音色・譜面・104秒の時刻・シーンを含みません。
リポジトリ内の既存C単体版は別の実装として残し、汎用FWのビルドには使いません。

## 用意・実行

```powershell
./software/kagura_runtime/tools/build.ps1
python software/kagura_runtime/tools/package.py
python software/midnight_terminal/tools/package_micropython.py
```

1. `build/kagura-runtime/qspi/kagura-micropython.uf2` を使います。
   SPI接続の場合は `-HostLanes 1 -Output build/kagura-runtime/spi` でビルドします。
2. `build/midnight-terminal/micropython-app/` の内容を、Picoのファイルシステムのルートへ配置します。
   `.py` と `mt_data/` の両方が必要です。
3. 日本語Framebuffer REPLには、共通ファイル `build/kagura-runtime/files/fonts/` も配置します。
   XIAO側には[キーボードブリッジFW](../../xiao_keyboard/README.md)が必要です。

これらのホストコマンドは、ボードへの書込みを行いません。
音源にはPCM STREAM対応FPGAが必要です。QSPI/SPIと配線は汎用FWの説明に従います。

```python
import midnight_terminal
result = midnight_terminal.run()
print(result)
```

Framebuffer REPLは自動で画面とPIOをアプリへ渡し、終了・Ctrl-C・例外時に復帰します。
デモ中もXIAOの入力受信とCtrl-Cは有効です。USB REPLも残ります。
結果にはフレーム数・シーン別フレーム数・音声補充回数・最大遅延・FMピークとクリップ数が入ります。

`run(script=my_story)` で独自の台本を渡せます。
`run(asset_dir='other_data')` で画像・字形の場所を変えられます。
`run(on_frame=callback)` は各描画後に `callback(show, ms, synth)` を呼びます。
音声再生中の長い計算では `synth.service()`、待機では `synth.sleep_ms()` を使います。

## 作品の音色だけを鳴らす

```python
from midnight_fm import Synth
with Synth(autostart=False) as fm:
    fm.note_on(60, voice=0, instrument='ep', velocity=180, gate_ms=500)
    fm.start()
    fm.sleep_ms(1000)
```

`ep`、`bass`、`vib`、`blip`、`chime`、`sting`、`siren`、`drone` の8音色です。
`note_off(voice)`、`all_off()` も使えます。音色の名前とオペレータ設定はすべてこのアプリのPython側です。
一般のアプリは `kagura_fm.Patch` / `operator` で独自の音色を定義し、`kagura_fm.Synth` を使います。

## 素材と再ビルド

`mt_data/` の画像3枚は生の640×360・4bpp、各115,200 bytesです。
目の差分・2種類の字形表も別ファイルで、MCUに画面全体を保持しません。
通常のPython変更や画像ファイルの差替えにはFWの再ビルドは不要です。

字形は作品で使用する文字のサブセットです。未知の文字はハードウェアを開く前にエラーになります。
新しい字を追加するときは `tools/build_assets.py` で素材とPythonメタデータを再生成し、
`package_micropython.py` を再実行してファイルを更新します。汎用FWの変更は不要です。
各フォントのglyph indexはbyte単位なので、1種類あたり256字までです。

## 検証範囲

```sh
python software/kagura_runtime/tests/test_runtime.py
python software/midnight_terminal/micropython/test_runner.py
python software/midnight_terminal/tools/check_micropython_port.py
```

ホスト上で2回・計6240フレームの両ページ・表示ページ・パレットをC参照描画と比較します。
ファイル素材を読む新しい描画アダプタも比較に含めます。
Pythonから作った全104秒の譜面を汎用FMへ渡して音声を生成し、
ライブ発音／停止、8音色、7声、gate、キュー上限を検査します。

異常シーンの乱数は、DSPの内部状態への依存を取り除き、Python側へ移しました。
そのため異常シーン以降の音声は旧C版とサンプル単位では一致しません。
結果は `build/midnight-micropython-host-checks/result.json` に保存します。
実機での映像・音声の連続性・実時間性能・キーボードからの中断／復帰は未検証です。

[素材のライセンス](../LICENSES.md)。配布ファイルにはフォントのライセンスも含めます。
