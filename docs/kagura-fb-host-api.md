# KAGURA-HD ホストABI 1.4

現行の選定版は **ABI 1.4 / CAPS FF / QSPI / Queue8** で、PCM2に加えてPCMストリーミング（下記）に対応しています。以下の描画・カーソル・BLIT契約はABI 1.2から継承します。実機Demoではnominal PIO QSPI 5MHzを使用しています。最大速度の保証ではありません。

SPI版はテスト未実施・STA未達のため[experimental](../artifacts/experimental/spi-sta-fail/README.md)へ隔離しました。通常Releaseから除外し、DO_NOT_PROGRAMを付けています。

## PCM2音声（ABI 1.4）

CSR `0x36`（54）がINDEX、`0x37`（55）がDATAです。PCM0はindex `0x60`、PCM1は`0x80`をbaseとし、各chのSTART/END/LOOP、左右GAIN、ENABLEを設定します。MASTERは`0xE0`、全体STATUSは`0xE1`、error clearは`0xE2`です。旧6ch index `0x00..0x5F`は使用できません。

ch base + `0x0F`の制御はPREPARE=1、STOP=2、CLEAR=4。ch STATUSはREADY bit0、ACTIVE bit1、DONE bit2、UNDERRUN bit3、CONFIG_ERROR bit4、MEMORY_ERROR bit5、PREPARING bit6です。両ch停止→PCM転送→FENCE→設定→PREPARE→READY確認→MASTER→opcode **7 AUDIO_COMMIT**→tag完了待ちの順に開始します。COMMIT descriptorはopcodeとtag以外0で、既存DONE/error/IRQ経路を使用します。

PCMは48kHz signed8 mono ×2を合成し、HDMIへsigned16 stereoを送ります。アドレスはHDのdie-relative byte address、ENDは排他です。`0x400000`の排他ENDは表現できません。FBとPCMの領域を重ねず、Host呼出しを直列化してください。

### PCMストリーミング（選定版 `kagura-hd-qspi-pcm-stream.fs`）

audio indexの `E3` を読むと `0x51` が返ります。この値でストリーミング対応を確認できます。各chは8192 byte境界から始まる8 KiB（START、END=START+8192、LOOP=START）を使い、4096 byteの半面2つを交互に再生します。左右は一組で扱います。

|index|読出し|書込み|
|---|---|---|
|`E3` STREAM_CTL|識別子 `0x51`|1=ARM、0=停止|
|`E4` STREAM_TOKEN|次に公開する半面のtoken（bit0が半面A/B）|一致するtokenを書くと、その半面を公開する|
|`E5` STREAM_STATUS|bit0 HALF_FREE、bit1 ARMED、bit2 READ_PENDING|—|

開始手順は次のとおりです。

1. 両chを停止・CLEARする。
2. START/END/LOOP、左右GAINを設定し、ENABLE（ch base＋`0x0E`）に3を書く。
3. 2つの半面を書き込み、FENCEで完了を待つ。
4. MASTERを設定する。
5. `E3`に1を書く。STATUSがARMEDになり、HALF_FREEが0であることを確認する。
6. 両chをPREPAREし、READYになるのを待つ。
7. AUDIO_COMMITを発行する。

再生中は、HALF_FREEになったら次の手順で補充します。

1. `E4`のtokenを読む。
2. `token&1` の半面を、左右とも全WRITE完了まで書き込む。
3. 同じtokenを`E4`に書く。
4. tokenが1進んだことを確認する。

半面1つは85.3 msです。この時間内に補充を終えてください。古いtokenや二重公開は拒否されます。実装例は[PCMストリーミングHost](../diagnostics/pcm-stream-rc1/hardware-host/main.c)と[FOUR OPERATORS](../software/fm_megademo/README.md)を参照してください。

CSR 31のbit1は、この画像では診断用です。アプリケーションからは書かないでください。bit0（ACK）の意味は従来と同じです。

詳細なindex配置は[C SDK](../software/kagura_fb/kagura_fb.h)と[MicroPython Audio](../software/kagura_fb/kagura_fb_audio.py)を参照してください。Cは`kfb_audio_write/read/commit`、MicroPythonは`Audio`を使用します。Cの`KFB_PACK_DESCRIPTOR=1`は任意の通信削減optionで、既定は0、ABIは不変です。


起動時の診断初期化が完了すると、SPIまたはQSPIで1命令ずつ受け付けます。既存Kagura-9のレジスタABIとは互換ではありません。命令キューの深さは1です。CとMicroPythonのドライバは同じデバイスへの呼出しを直列化して使用してください。

## 配線・転送

|信号|Tang Nano 9Kピン|RP2040 GPIO|
|---|---:|---:|
|IO0 / MOSI|28|2|
|IO1 / MISO|29|3|
|IO2（QSPI）|30|4|
|IO3（QSPI）|33|5|
|SCK|35|6|
|CS_n|42|7|
|BUSY|26|8|
|READY|27|9|
|IRQ_n|49|10|

IRQ_nはオープンドレイン出力です。使用する場合は3.3 Vへのプルアップを設けます。

ビルドは `tools/build-fb.ps1`（QSPI既定）、`-Transport spi`（実験用・STA未達のSPI）です。両端で同じレーン数を選びます。Mode 0、MSB先行。初期動作確認用は1 MHz、実機Demoはnominal PIO QSPI 5MHzです。実機の最大クロックは未測定です。QSPIは1バイトを上位・下位の順に2ニブルで転送します。IOの方向切替と読み出しダミーを守ってください。

レジスタ転送ヘッダは `bit7=read, bit6=address increment, bit5:0=address` です。書込みはヘッダの直後にデータを送ります。読出しはヘッダ、読出しバイト数、ダミー1バイト、その後データです。CSを転送全体でLowに保ちます。24番データ窓はアドレス増分を無効にし、内部ポインタだけを進めます。

## レジスタ

|アドレス|機能|
|---|---|
|0–3|ASCII `KFB1`|
|4 / 5|ABI major=1 / minor=4|
|6|能力ビット0 Fill、1 Palette、2 Present、3 Write、4 Read、5 Cursor、6 Aligned Copy、7 Audio CSR（値0xff）|
|7|sticky error。任意値の書込みでクリア|
|8–23|16バイト命令ステージング|
|24|64バイトデータ窓。読書きで内部ポインタ増加|
|25|データ窓ポインタ、0–64。64でのアクセスは範囲エラー|
|26|読出し：credit 0/1。書込み1：submit|
|27|status：bit0 BUSY、1 enabled、2 video error、3 audio error、4 DONE、7 SPI late|
|28–29|直近の完了タグ、little endian|
|30|直近の命令エラー|
|31|bit0 IRQ状態（完了またはエラー）。書込みbit0=1で完了フラグだけを解除|

BUSY中は命令・データ窓への変更とsubmitを拒否します。状態読出しは可能です。タグとDONEを併せて完了を判断します。Presentの完了は垂直帰線での反映後です。IRQ_nは完了またはsticky errorでLowになります。エラー番号は0正常、1 busy、2命令不正、3範囲、4メモリ、5窓範囲、6転送遅延です。SPI lateはリセットまで保持されます。

カーソルは独立したCSR32～53を使い、CSR54～55は音声INDEX/DATAです。入力の保持・検証を含め、カーソルendpointの応答は2 sys edgeです。[カーソル仕様・API](kagura-fb-cursor.md)を参照してください。

## 命令

すべてlittle endian。byte0=opcode、byte1=argument、byte2–3=tagです。未使用バイトは0にしてください。

|opcode|argument|byte4–15|
|---|---|---|
|0 Fence|0|すべて0|
|1 Fill|page 0/1|x:u16、y:u16、width:u16、height:u16、color:u8、残り0|
|2 Palette|index 0–15|RGB444:u16、残り0|
|3 Present|page 0/1|すべて0|
|4 Write|word数1–16|byte address:u32、byte mask:u64|
|5 Read|word数1–16|byte address:u32、残り0|
|6 Copy|bit0 src_page、bit1 dst_page、他0|src_x:u16、src_y:u16、dst_x:u16、dst_y:u16、width:u16、height:u16|
|7 Audio Commit|0|すべて0|

Read/Writeは4バイト整列、1 word=4バイト、4 MiBの単一ダイ内です。Writeは事前にデータ窓へアップロードし、maskの1はそのバイトの書込みを禁止します。Read完了時にデータ窓を更新します。Fillは640×360内の矩形を受け付けます。画面はpage0=0、page1=115200バイト、stride=320バイト。偶数xが上位ニブル、奇数xが下位ニブルです。Paletteはシャドウを変更し、Presentでページと16色を同時に反映します。Fenceは先行命令が完了してから発行する同期点です。

PCM2のHost制御は上記の音声CSRとopcode7を使用します。起動時の診断用PCM初期領域240000–240127バイトとFBを避けてPCMを配置してください。文字描画opcodeはなく、Hostで4bppへ展開してWRITEします。

## 不透明BLIT（Copy）

能力bit6を確認してからopcode6を使います。送受ページは0/1、Xと幅は偶数、
`src_x % 8 == dst_x % 8`が必要です。Y・高さは1画素単位です。矩形全体をページ内に
収めてください。RTLは範囲外をエラー3、予約bitや未対応の整列をエラー2でメモリ要求前に拒否します。
同一ページの重なりはコピー開始前の画像を基準に保存します。全16色を不透明色として複写します。
幅・高さ0、同一ページ同一座標も全入力検証後に成功します。

Cは`kfb_copy_rect(dev, src_page, sx, sy, dst_page, dx, dy, width, height)`、
MicroPythonは`copy_rect(src_page, sx, sy, dst_page, dx, dy, width, height)`です。
両APIは**クリップせず**、範囲・整列不正を送信前に拒否します。空矩形・同位置は送信しません。
実際のコピーには能力bit6が必要で、古いfirmwareならCは`KFB_VERSION`、Pythonは`ValueError`です。
任意位置や透過が必要な場合はアプリ側で再描画してください。

コピーは内部で64 Bデータ窓を使うため、完了後の窓内容・ポインタはアプリで保存した値として扱えません。
CPUからの窓アクセスは引き続き実行中ロックします。非同期利用には既存`submit/wait`と上表の記述子を使えます。
カーソルCSRはBLIT実行中も操作できます。エラーやタイムアウト後の部分更新は巻き戻されず、自動再送しません。

```python
# page1の内容を16行上へ移す。page1が背面で、内容が有効なこと。
gpu.copy_rect(1, 0, 16, 1, 0, 0, 640, 344)
gpu.fill_rect(1, 0, 344, 640, 16, 0)
gpu.present(1)
```

```c
int rc = kfb_copy_rect(&gpu, 1, 0, 16, 1, 0, 0, 640, 344);
if (rc == KFB_OK) rc = kfb_fill_rect(&gpu, 1, 0, 344, 640, 16, 0);
if (rc == KFB_OK) rc = kfb_present(&gpu, 1);
```

例は1回の更新です。次回の背面ページにも正しい世代の内容が必要です。
[BLIT設計・検証](kagura-fb-blit.md)の差分再生と失敗時の再生成を参照してください。

## C

`software/kagura_fb/kagura_fb.c` とヘッダを組み込みます。動的メモリ確保はありません。`kfb_io` のread/writeはレジスタ転送を実装して成功時0を返し、now_msは折返し可能な32bitミリ秒を返します。コールバックは6bitアドレスをそのまま送るrawレジスタ転送とし、全転送をHOST_BUSYで待たせないでください。カーソル窓はGPU BUSY中にもアクセスします。既存PIO転送関数はこの条件へ適合する必要があり、RP2040のC版PIO QSPIバックエンドは実機Demoで使用済みです。RP2350の実機検証は未完了です。

```c
kfb_device gpu;
kfb_io io = { .context = ctx, .read = read_regs,
              .write = write_regs, .now_ms = milliseconds };
int rc = kfb_init(&gpu, io, 1000);
if (rc == KFB_OK) rc = kfb_probe(&gpu);
if (rc == KFB_OK) rc = kfb_palette(&gpu, 6, 0xf20);
if (rc == KFB_OK) rc = kfb_fill_rect(&gpu, 1, 0, 0, 640, 360, 6);
if (rc == KFB_OK) rc = kfb_present(&gpu, 1);
```

Fill APIは画面外をクリップし、空領域を無操作で完了します。`kfb_write_bytes` / `kfb_read_bytes` は任意バイト境界を最大64バイトに分割し、周辺バイトを保持します。通常の描画APIは同期式で完了・タグ・エラーを確認します。`kfb_submit` / `kfb_wait` は投入と完了待ちを分離します。転送失敗時は届いたか不明な命令を自動再送しません。呼出し元で状態を確認し回復してください。

## 非同期の描画投入

Cの `kfb_submit` は16 B命令と任意の最大64 B payloadを送り、割り当てたタグを返します。`kfb_wait` でそのタグの完了を確認します。MicroPythonは `submit` / `wait` です。次の描画命令を投入する前に前のタグをwaitしてください。その間にカーソルAPIや他のCPU処理を実行できます。同一デバイスを複数呼出し元から同時操作しないでください。

```python
# 例：page1のPRESENTを投入し、待機中にカーソルを動かす
# 形状bank1は先にcursor_shapeで転送しておく
command = b"\x03\x01" + bytes(14)
tag = gpu.submit(command)
gpu.cursor_move(120, 80, 1)
gpu.wait(tag)
gpu.cursor_wait()
```

タグ用のbyte2～3はSDKが上書きします。不確かなsubmitは自動再送しません。waitせず次の描画命令で完了タグを上書きすると、古いタグのwaitはtimeoutになります。既存の `fill_rect` 等の同期APIは従来どおり使えます。

## MicroPython

`software/kagura_fb/kagura_fb.py` をボードにコピーします。接続用ヘルパーはSPI版です。FPGAの初期化を待ってから実行します。QSPIでは同じread/write契約のカスタムtransportを渡せます。

```python
from kagura_fb import connect_rp2040

gpu = connect_rp2040()  # SoftSPI 1 MHz、上記GPIO
# パレットはPresentで反映
gpu.palette(6, 0xf20)
gpu.fill_rect(1, 0, 0, 640, 360, 6)
gpu.present(1)
buffer = bytearray(64)
gpu.read_into(115200, buffer)
```

大きい読出しは呼出し元のバッファを使う `read_into` を推奨します。`read_bytes` は要求サイズ分を確保します。命令中の一時転送バッファは最大64バイトです。通常の描画APIは同期式、`submit` と `cursor_move` は非同期の投入です。

## 検証の範囲

`bash tools/test-fb-drivers.sh` はCを警告エラー扱いでコンパイルし、C/Python両方を独立レジスタモデルと照合します。`MICROPYTHON=/path/to/micropython bash tools/test-fb-micropython.sh` は実MicroPython Unixで同じ主要操作とSPIフレーミングを検査します。試験モデルが4 MiBのPSRAMを模擬するためUnix試験のヒープは16 MiBで、RP2040上の必要RAMを表す値ではありません。RTL結合試験は実SPI/QSPIピンからメモリ・画素出力まで確認します。これらは実基板上の電気特性・配線・速度を保証するものではありません。
