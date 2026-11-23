# PIO QSPIとHDMI REPL

`rp2040_pio.py`は標準MicroPython 1.26の`rp2.StateMachine`、`rp2.DMA`、
Viperを使うHD向けQSPI transportです。ファームウェア再ビルドは不要です。
KAGURA-9のPIO命令列・12 cycles/SCK・転送前の方向切替えを継承し、
HDの6-bitレジスタ、1-byte dummy、タグ付きGPUコマンドに合わせています。
旧ABIのbyte単位BUSYフラグは送りません。

## PIO接続

```python
from rp2040_pio import connect
dev = connect()  # QSPI 5 MHz / GP2..5 data, GP6 SCK, GP7 CS
dev.fill_rect(0, 0, 0, 640, 360, 0)
dev.present(0)
dev.transport.deinit()
```

CPUクロックは変更しません。指定できるSCKは100 kHz〜8 MHzで、通常は5 MHzを使用します。
PIO0/1のSM番号は`connect(sm_id=...)`で指定できます。同じSMとGPIOを他のtransportや
アプリから同時に所有しないでください。タイムアウト・Ctrl-C時はCSを解除して
DMA/PIOを停止・再初期化し、結果の不確かな転送を自動再送しません。

短い制御転送もCSから最終SCKまでを1回のViper呼出しで実行します。
16〜64 bytesの書込みはTX/RXの2 DMA channelを使用します。読出しFIFOはViperで処理します。
高水準のGPUコマンド組立て・ポーリングはPythonのため、ネイティブCの速度と同一ではありません。
`dma=False`でDMAを使わずに接続できます。

## HDMI REPL

以下をボードへ配置します。既存の`kagura_fb.py`も排他制御追加版へ更新します。

- `rp2040_pio.py`
- `kagura_fb.py`、`kagura_framebuf.py`、`kagura_ja.py`
- `kagura_terminal.py`、`kagura_console.py`
- `kagura_keyboard.py`（XIAO UART入力）
- `kagura_glyph_atlas.py`（12px版のBLIT字形キャッシュ）
- `fonts/mplus12.kmf`（標準）、任意で`fonts/mplus10.kmf`とフォントライセンス

```python
import kagura_console
console = kagura_console.start()
print('こんにちは、KAGURA！')
```

USBから入力し、プロンプト・式の評価結果・`print()`・例外出力をUSBとHDMIへ出します。
HDMI側に独立したPythonインタープリタが増えるわけではありません。
XIAOのUSB Hostからの入力は[キーボードブリッジ](../software/xiao_keyboard/README.md)と
`kagura_keyboard.py`で対応します。標準でUART0 GP0/GP1・115200 8N1を使用し、
`keyboard=False`で無効化できます。USB REPL入力も併用できます。

`os.dupterm`の出力は4 KiB ringへ蓄積し、soft timerで最大128 bytesずつ、
改行または約25 msの文字処理予算で区切って描画します。更新完了後、出力待ちなら5 ms、
待ちがなければ20 msでワンショットタイマーを再設定するため、遅い描画中に周期callbackが蓄積しません。
GPUコマンド実行中、非同期コマンドの完了待ち中、PIO transaction中は更新を待ちます。
スクロールはGPU BLITとFILLを使い、画面全体を再転送しません。
12px版ではASCIIを非表示ページ1へ常駐させ、字形もCOPY_RECTでページ0へ描画します。
95字形×4通りの横位置位相を固定保持し、日本語等は残り160枠のFIFOで保持します。
初回は79,040 bytesのASCII画像を準備するため待ち時間があります。
BLIT表示中はPico側で同じ字形を再描画・再スクロールせず、`pause()`時にGPU画面を
RAM bufferへ読み戻します。画面保存が必要なpause/resumeは通常の入力より時間がかかります。
`blit=False`ならページ1を字形キャッシュに使わず、従来の部分WRITE方式で起動します。
UTF-8、CR/LF、backspace、tab、CSI A/B/C/D・H/f・G・d・s/uとJ/Kの0/1/2に対応します。
入力位置はFPGAの下線カーソルで表示し、位置変更時だけ更新します。pause/closeで非表示にします。
完全なVT100端末の実装ではありません。全角文字途中での編集はMicroPython自身の行編集仕様にも依存します。

大量の出力は表示が追いつかない場合があります。`console.dropped`が破棄byte数、
`console.last_error`が描画エラーです。USB REPLへの出力自体は抑制しません。

## 起動とアプリの切替え

動作確認後、`software/kagura_fb/examples/boot_hdmi_repl.py`を`/boot.py`として配置すると
起動時にHDMI REPLを開きます。READY/BUSYを最大2秒確認し、FPGA不在なら
エラーメッセージをUSBへ出して通常のUSB REPLを残します。
起動処理は115,200-byte framebufferを先に確保し、PIO importによるheap断片化を避けます。

```python
console = kagura_console.console
console.pause()
try:
    dev = console.device  # 別のPIOTransportを作らず既存Deviceを再利用
    dev.fill_rect(1, 0, 0, 640, 360, 4)
    dev.present(1)
finally:
    console.resume()  # コンソールのbufferとpaletteを再転送・表示
```

`pause()`中のHDMI向け出力は破棄します。USB REPLは使用できます。
`close()`はdupterm・timer・font・PIO/DMAを解放します。
閉じたConsoleからは大きな画面・字形キャッシュへの参照も解放します。
コンソールは全画面bufferを1枚保持するため、同時に2枚目の全画面FrameBufferを
RP2040のRAMへ確保する余裕はありません。独立した全画面アプリへ切り替える場合は
コンソールを閉じ、参照を解放して`gc.collect()`してから起動してください。

## フォント選択

| M+版 | 半角幅 / 全角幅 | 行高 | 半角列数 | 全角列数 | 行数 |
|---|---|---:|---:|---:|---:|
| 12px | 6 / 12 px | 13 px | 106 | 53 | 27 |
| 10px（半角W5） | 5 / 10 px | 11 px | 128 | 64 | 32 |

640×360の論理画面を2倍表示するため、**標準は漢字の読みやすさを優先した12px版**です。
ログやコードを多く並べたい場合は10px版が便利で、全角の表示可能文字数は約43%増えます。
原本の上下余白を保持するため、行高はそれぞれ13と11です。

10px版を使う場合は起動時の呼出しを次へ変更して再起動します。

```python
kagura_console.start(font_path='fonts/mplus10.kmf')
```

両版とも7,155 glyph、半角カナ付きです。再生成は
`tools/gen-mplus-font.py ARCHIVE OUTPUT --size 10`（または`--size 12`）で行えます。
現行COPY_RECTはXと幅が偶数、送受Xの差が8pxの倍数という制約があります。
12px版の送り幅6/12pxは4位相の字形で対応できます。10px版の半角5pxはこの制約に合わないため、
現在の10px端末は部分WRITE方式です。読みやすさに加え、BLIT適合性でも12px版が標準です。

## 実機確認（2026-11-23）

Pico Carrier RevA上のRP2040、標準MicroPython 1.26.0、CPU 125 MHzのまま、
PIO QSPI公称5 MHz・DMA有効で確認しました。

- PSRAM 4 KiB書込み／読戻しと、1・63・65・257-byteの非整列転送を照合。
  退避した4 KiBの復元も照合済み。STATUS=02、timing errorなし。
- 4 KiB有効payloadの所要時間は書込み415,166 µs、読出し240,093 µs。
  約9.6 / 16.7 KiB/s。PythonでGPUコマンドを組み立てる現実装の値で、C版の実測値とは異なります。
- 32行の連続出力・スクロール後、描画エラーなし、ring破棄0。
- 実行中のループをUSB Ctrl-Cで中断し、REPLへ復帰。HDMI更新も有効のまま。
- pause/resume、soft reset後の自動起動、通常USB REPLで`2+3`の結果`5`と`>>>`復帰を確認。
- 最終配置9ファイルはPC側ソース／生成フォントとSHA-256一致。
  GC後の空きheapは約94 KiB、12px版106半角列×27行。

初期の周期タイマー版は長いスクロール試験でUSB応答が停止しました。
最終版では処理後に再予約するワンショット方式へ変更し、行消去をGPU FILLへ変更して再試験しています。
長時間・大量ログの耐久試験は未実施です。XIAO経由のUSBキーボードは実機で
`help()`と`2+3`→`5`の入力・表示を確認しています。
ローカルのログ・配置manifest・変更前のFlashバックアップは`build/pio-repl-2026-11-23/`に保存しています。

### Native版とBLIT版の追試

`rp2040_pio.connect()`と`kagura_console.start()`は標準で`native=True`です。
GPUコマンド処理を直接の`@micropython.native`でコンパイルした`NativeDevice`を使い、
転送部分はViperとDMAを使います。`native=False`で通常のPython版Deviceを選べます。
`micropython.native`を実行時にimportして別名でdecorateする方式はNative化されないため採用していません。
生成元は`tools/gen-native-commands.py`です。

- Pico実機でNative版の4 KiB書込み／読戻しを照合。書込み399,977 µs、読出し225,779 µs。
- COPY_RECT 100回は通常Python版713,307 µsからNative版338,115 µsへ短縮。
- 同じ648-byte・8行の表示は初期版14,036 msからNative＋字形BLIT版7,367 msへ短縮。破棄0。
- Native版HDMI起動後は字形atlas準備完了、描画エラーなし、空きheap約51 KiB。
- 実機の`/boot.py`へ自動起動を再配置し、2回の起動でNative有効・atlas準備完了・描画エラーなしを確認。

計測ログは`build/xiao-keyboard/evidence/native-hardware.log`、
`display-direct-native.log`に保存しています。上記9ファイル・94 KiBの記録は初期版の値です。
今回のUSB専用起動への修復では、利用者の指定に従ってFlashの別途退避は行っていません。

続くGPU一括Viper化・メモリ転送Native化・CSI／カーソル拡充により、同条件の表示中央値は
基準版6.86秒から最終配置版3.12秒になりました。[基準ソースと実機比較](micropython-k9-parity.md)を参照してください。
