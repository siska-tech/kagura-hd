# M+ BITMAP FONT

`mplus10.kmf`も同じ原本から生成しています。10px版は193,193 bytes、
半角5px・全角10px・行高11px、7,155 glyphです。
`fonts_j/mplus_j10r.bdf`と`mplus_j10r-iso-W4`に原本のW5差分・JIS X 0201差分を
適用してUnicode形式へ変換しています。生成時は`--size 10`を指定します。

`mplus12.kmf`はM+ BITMAP FONTS 2.2.4の`mplus_j12r.bdf`、
`mplus_f12r.bdf`、`mplus_f12r-jisx0201.diff`から生成したものです。
フォントの著作権と利用条件は同梱の[LICENSE_MPLUS](LICENSE_MPLUS)を参照してください。
ドライバのApache-2.0とは別のライセンスです。

- 7,155字形、221,813 bytes。ASCII、Latin-1、日本語、半角カナ。
- 半角の送り幅6px、全角12px。原本のFONT_ASCENT=11、FONT_DESCENT=2を保持して行高13px。
- JIS X 0208をUnicodeへ変換。未収録文字は描画時に`?`へ置換。
- 原本は[DebianのM+原本ミラー](https://deb.debian.org/debian/pool/main/x/xfonts-mplus/xfonts-mplus_2.2.4.orig.tar.xz)から取得。
- 原本SHA-256: `4c973ef85e3e17cb3894a6193b85256ca75aab94d01919175d308a76fa420b94`。

再生成（CPython、外部パッケージ不要）:

```sh
python tools/gen-mplus-font.py build/mplus-font/mplus.tar.xz software/kagura_fb/fonts/mplus12.kmf
python tools/gen-mplus-font.py build/mplus-font/mplus.tar.xz software/kagura_fb/fonts/mplus12.kmf --check
```

KMF1形式は8-byte header `<4sBBH`（magic、行高、行byte数、字形数）と、
Unicode昇順の固定長recordから成ります。recordは`<IB`（コードポイント、送り幅）と
上から順・左がMSBのbitmapです。この配布物は各行2 bytes、各record31 bytes。
KAGURA-9のKJ8F形式とは互換性がありません。
