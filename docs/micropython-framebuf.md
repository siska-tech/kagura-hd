# MicroPython FrameBuffer・日本語表示

高速QSPI接続とUSB入力・HDMI表示のREPLは[PIO QSPIとHDMI REPL](micropython-hdmi-repl.md)を参照してください。

`software/kagura_fb/kagura_framebuf.py`は標準`framebuf.FrameBuffer`を継承した
640×360、16色の描画面です。既存のKAGURA-HD `Device`を再利用します。
`pixel`、`fill`、`line`、`hline`、`vline`、`rect`、`fill_rect`、`ellipse`、
`poly`、`scroll`、`blit`、組込みASCII `text`は使用するMicroPythonの標準実装に従います。
M+による英数字・日本語は`text_jp`を使います。

## 配置と使用例

基板のファイルシステムへ以下をコピーします。

- `software/kagura_fb/kagura_fb.py`
- `software/kagura_fb/kagura_framebuf.py`
- `software/kagura_fb/kagura_ja.py`
- `software/kagura_fb/fonts/mplus12.kmf` → `fonts/mplus12.kmf`
- `software/kagura_fb/fonts/LICENSE_MPLUS` → `fonts/LICENSE_MPLUS`

```python
from kagura_framebuf import FrameBuffer
from kagura_ja import Font

# devは既存のSPI/QSPI Device。接続を重複作成しない。
fb = FrameBuffer(dev, page=1)
dev.palette(0, 0x012)
dev.palette(15, 0xfff)
fb.fill(0)
with Font('fonts/mplus12.kmf') as font:
    fb.text_jp('こんにちは、KAGURA！\n日本語表示 / ｶｸﾞﾗ', 16, 16, font, 15)
    print(font.measure('日本語ABC'))  # (54, 13)
fb.show()
```

完成例は`software/kagura_fb/examples/framebuf_japanese.py`の`run(dev)`です。
ドライバは音源やFPGA構成を変更しません。

## メモリと転送

ローカルbufferは115,200 bytes（640×360÷2）です。別途MicroPythonオブジェクト・
通信処理用のheapが必要です。`buffer=`で同じ大きさの書込み可能bufferを渡せます。
GS4_HMSBは左pixelが上位nibbleで、HDのPSRAM配置と一致します。
`FrameBuffer`は指定ページの描画を専有し、他の描画処理と同時更新しないでください。

`show()`は全画面を既存`Device.write_bytes`で転送し、完了後に`present(page)`します。
`show(x, y, width, height, present=False)`で部分転送だけ行えます。
戻り値は転送byte数。画面外はclipされ、空領域は転送もPRESENTもしません。
奇数の左右端はpixelペアへ拡張し、隣接pixelもローカルbufferの値で更新します。
初回は`fill()`と全画面`show()`を行ってから部分更新してください。
buffer直接操作や標準描画関数の変更検出は行わないため、更新領域は呼出し側が指定します。

全画面転送は64-byteコマンドを繰り返すため、高FPS動画向けではありません。
ページの自動切替は行いません。表示中ページへの更新にはtearingの可能性があります。
未表示ページへ全画面転送してPRESENTすると途中描画を避けられます。
転送例外時はPRESENTせず例外を返します。再試行はアプリ側で画面全体を再転送してください。

## 日本語API

`Font(path)`はファイルを保持し、二分探索で必要な字形のみを読みます。
KAGURA-9 `kagura_ja.Font`のファイル所有・close・二分探索の設計を参考にしました。
HDの線形bufferへ描画するため、旧tile/map ABIは使用しません。
無制限の字形cacheや全フォント読込みはありません。

- `fb.text_jp(text, x, y, font, color=15, background=None)`：UTF-8文字列を描画。
- `font.draw(surface, text, x, y, color=15, background=None)`：任意の標準FrameBufferへ描画。
- `font.measure(text)`：改行込みの最大幅と高さ。
- `font.glyph(character)`：`(送り幅, bitmap)`、未収録なら`None`。
- `font.close()`：ファイルを閉じる。`with Font(...)`も使用可能。

色はpalette index 0..15。`background=None`では字形以外のpixelを保持します。
背景色を指定すると各文字cellを塗ります。`\n`は初期xへ戻って13px下へ進みます。
自動折返し・結合文字の合成・タブ展開は行いません。画面端のclipは標準framebufが処理します。
描画の戻り値は最後の`(x, y)`です。フォントの詳細・再生成方法は
`software/kagura_fb/fonts/README.md`を参照してください。

## 検証

```sh
MICROPYTHON=/path/to/micropython bash tools/test-fb-framebuf.sh
```

標準framebufを有効にしたUnicode対応MicroPython Unix portで実行します。
GPUレジスタモデルに対してpixel順、ページ境界、全画面・部分転送、失敗時のPRESENT抑止を確認し、
原本の「日」のbitmapと描画結果を比較します。日本語・半角カナ、fallback、clip、close、
反復描画のheap保持量も検証します。16 MiB heap指定は4 MiBのPC用GPUモデルのためです。
別の192 KiB heapテストでも描画を確認しています（字形cache追加後、Unix v1.26.0では終了時約67 KiB空き）。
これはRP2040上での空きメモリ量の測定値ではありません。
実機基板での表示・転送速度は、このテストでは検証できません。
