# KAGURA-HD MicroPython GPU runtime

アプリケーションに依存しないRP2040用のGPU制御FWです。
MIDNIGHT TERMINALのコード・画像・フォント表・音色・譜面・時刻・シーンを含みません。
FWを更新せず、ファイルシステム上のPythonアプリを差し替えて使います。

|モジュール|役割|
|---|---|
|`kagura_gpu.Device`|GPUの所有権、FILL/COPY/WRITE/READ/PALETTE/PRESENT、bitmap・glyph描画|
|`kagura_fm`|Pythonで定義する4オペレータ音色、7声の発音、サンプル時刻付きコマンド|
|`kagura_repl`|実機フレームバッファREPL、XIAOキーボード、アプリへの画面引継ぎ|
|`kagura_framebuf` / `kagura_ja`|標準framebuf互換の4bpp surface、任意のKMFフォント|
|`_kagura`|C拡張。SPI/QSPI、GPU ABI、PCM転送、設定可能なFM・ノイズ・打楽器DSP|

C拡張はPythonから渡された音色・描画データ・時刻付きコマンドを実行します。
曲、楽器プリセット、アプリの効果音レシピ、画像ID、シーンを選ぶコードはありません。
汎用FMのディレイ・ピッチ／音量ランプ・量子化・ループ効果も、Pythonが明示的に指示します。

## Framebuffer REPL / キーボード

`boot.py` と `main.py` がない環境では起動時にREPLを自動で開始します。
既存の起動スクリプトがある場合はそれを尊重して自動開始せず、次で開始できます。

```python
import kagura_repl
kagura_repl.start()
```

既存の `boot.py` が旧 `kagura_console.start()` を呼んでいる場合は、
その呼出しを `kagura_repl.start()` に置き換えます。2つのコンソールは同時に開始しません。
USB REPLも併用できます。FPGAがない・準備できていない場合は、USBとキーボード入力を
残して表示だけを無効にします。エラーは `kagura_repl.console.last_error` に残ります。

ASCII用8×8フォントは標準で使用できます。`fonts/mplus12.kmf` を配置すると、
M+の日本語フォント（UTF-8）で表示します。フォントもFWに埋め込みません。
`tools/package.py` で共通ファイルを `build/kagura-runtime/files/` に用意できます。

XIAOには[HD用キーボードブリッジFW](../xiao_keyboard/README.md)が必要です。
XIAO D6/GP0 TX → Pico GP1 RX、XIAO D7/GP1 RX ← Pico GP0 TX、UART0 / 115200 / 8N1です。
XLINKのCRCを検証してキーをREPL文字列に変換し、フレームを直接入力へ流しません。
矢印、編集キー、Shift、Ctrl-C/D/Eなどは既存のキーボードモジュールを共有します。
状態は `kagura_repl.console.keyboard.connected` / `bridge_version` / `bad_frames` で確認できます。

`Device` や `Synth` の `with` に入ると、コンソールはカーソルを隠し、
画面をPSRAMへ保存してPIOを解放します。XIAO入力とCtrl-Cの受信は継続します。
正常終了・例外・Ctrl-C時はアプリのPIO・音源を解放してから、画面とREPL位置を復元します。
soft reset時もC側の所有するPIOとFMスレッドを終了します。
タイマーの再設定や通常の出力処理でモジュールを再importしないため、
アプリ実行中もキーボードのポーリングを低負荷で継続できます。
起動・画面退避中のCtrl-Cでも、C側の実際の所有権を確認して画面を回復します。

独自のバックエンドを実装する場合、`generation()` はGPU取得に成功するたびに増える整数、
`is_open()` は現在の取得状態を返します。Python側のフラグ更新直前の中断も検出できます。
ネイティブの `interrupt_guard(callback, recovery)` は、スケジュールされたコールバックで
発生したKeyboardInterruptを前景VMへ通知し、必要なら先に `recovery()` でタイマーを再設定します。
それ以外の例外はそのまま伝播します。

このコンソールは115,200-byteのRAM framebufferを保持しません。
文字はFPGAへ直接描画し、出力リング・字形・フォントキャッシュだけをRAMに持ちます。
画面退避のため、コンソールから引継いだアプリはPSRAMの
**`0x80000..0x9c1ff`** を使わないでください。
通信障害で復元できなかった場合もUSB／XIAO入力は残り、エラーを調べられます。
アプリ終了後に `console.close()` → `start()` で表示を再初期化できます。

## GPUの例

```python
from kagura_gpu import Device
from time import sleep_ms

with Device() as gpu:
    gpu.palette(1, 0x38f)
    gpu.fill_rect(0, 0, 0, 640, 360, 1)
    gpu.present(0)
    sleep_ms(1000)
```

終了するとREPLの画面へ戻ります。画像はアプリが任意のファイル・配列から
`write_bytes(address, buffer)` で送ります。PSRAMはbyte-address、表示ページは各115,200 bytesです。
`copy_rect` のX／幅は偶数、コピー元と先のXは同じmod 8で指定します。
`bitmap` は任意のMSB-first 1bpp字形、`glyph_run` は任意の字形表を描画できます。
基本操作の実装は [kagura_gpu.py](kagura_gpu.py)、低レベル引数は [modkagura.c](native/modkagura.c) を参照してください。

通常の `framebuf` と同じRAM描画を使う場合は、次のようにできます。

```python
from kagura_gpu import Device
from kagura_framebuf import FrameBuffer
with Device() as gpu:
    fb = FrameBuffer(gpu)
    fb.fill(0)
    fb.text('hello', 16, 16, 15)
    fb.show()
    # ここで必要な処理を行う。with終了時にREPLへ復帰。
```

## PythonでFM音源を定義

```python
from kagura_fm import Synth, Patch, operator

sound = Patch((operator(ratio=1, level=16000, attack_ms=5, release_ms=300),
               operator(ratio=2, level=6000, decay_ms=250),
               operator(), operator()))
with Synth([sound], autostart=False) as fm:
    fm.note_on(60, voice=0, instrument=0, velocity=180, gate_ms=500)
    fm.start()
    fm.sleep_ms(1000)
```

音色は1–16個、声は0–6、MIDI音程は0–127、強さは0–255です。
各音色の4オペレータについて、周波数比・detune・レベル・attack/decay/sustain/releaseを
Pythonで指定します。アルゴリズムはserialまたは2-stack、feedback・vibrato・delay sendも指定できます。
既定の曲やアプリ固有の音色はありません。`note_off(voice)`、`all_off()` も使用できます。
打楽器・ノイズの周波数、減衰、フィルタ、パン、確率、ディレイ長も
Pythonの `effects(**parameters)` で定義し、`Synth(..., dsp=...)` へ渡します。
パラメータ名は `EFFECT_FIELDS` にあり、C側に作品用の打楽器・雨音設定は持ちません。

`Schedule` は `<IBBBBII` の16-byteレコードを昇順で蓄積します。
先頭は48 kHzのsample frame時刻、次にop/channel/a/b、最後にvalue/durationです。
`Schedule.at_ms()` はmsから換算します。NOTE/OFF/GAIN/DRUM/NOISE/PITCH/MASTER/CRUSH/
STUTTER/PITCH_RAMP/MASTER_RAMP/ALL_OFF/DELAYを指定できます。
意味と検証範囲は [kagura_fm.py](kagura_fm.py) と [fm.c](native/fm.c) にあります。
スケジュールは最大128 KiB、ライブコマンドのキューは32個で、満杯を黙って捨てません。
再生用スケジュールは1 KiB単位で保持し、大きな連続ヒープ領域を必要としません。

音声再生中の待機は **`fm.sleep_ms()`**、計算の合間は **`fm.service()`** を使います。
PCMの補充期限は約85 msです。長い `time.sleep_ms()` やREPLでの手入力待ちは補充を停止させます。
`service()` は空きPCMバッファの補充を完了してから戻ります。
開始後の発音変更にはPCM先読みで最大約340 ms＋処理待ちの遅延があります。
開始前の発音予約は先頭サンプルから鳴ります。

## ハードウェアとビルド

RP2040 2 MiB Flash、120 MHz。QSPI: GP2–5 IO、GP6 SCK、GP7 CS。
SPI: GP2 MOSI、GP3 MISO、GP6 SCK、GP7 CS。FPGA READY/BUSYはGP9/GP8です。
GPUだけなら対応するKFB ABIのFPGAで動き、音源にはPCM STREAM対応FPGAが必要です。
FS配置は標準Picoと同じ、FW上限640 KiB・FS 1408 KiBです。

MicroPython v1.26.0、Pico SDK 2.1.1、Arm GCC 14.2.1でコンパイル確認しています。
Windowsでは既存のローカルツールキャッシュを既定値に使います。
`-PicoSDK`、`-ArmBin`、`-CMake`、`-Ninja`、`-Pioasm`、`-Picotool`、
`-MicroPython`、`-MpyCross`、`-Python` で外部のツールを指定できます。

```powershell
./software/kagura_runtime/tools/build.ps1
./software/kagura_runtime/tools/build.ps1 -HostLanes 1 -Output build/kagura-runtime/spi
python software/kagura_runtime/tools/package.py
```

出力は `build/kagura-runtime/{qspi,spi}/kagura-micropython.uf2` です。
FWの生成・共通ファイルの用意は、機器への書込みを行いません。
Linuxでは標準のMicroPython rp2ビルドに、次を指定します。

```sh
cmake -S /path/to/micropython/ports/rp2 -B build/kagura-runtime/qspi -G Ninja \
  -DMICROPY_BOARD_DIR="$PWD/software/kagura_runtime/board" \
  -DUSER_C_MODULES="$PWD/software/kagura_runtime/micropython.cmake" \
  -DMICROPY_FROZEN_MANIFEST="$PWD/software/kagura_runtime/manifest.py"
cmake --build build/kagura-runtime/qspi --parallel 4
```

## 検証範囲

`python software/kagura_runtime/tests/test_runtime.py` で、フレームバッファ出力・スクロール、
画面の退避／復元、GPU／FMとの所有権切替、例外時の復帰、引継ぎ中のXLINK Ctrl-C入力、
起動スクリプトの尊重をホスト上で検査します。
QSPI/SPIのFWビルドとUF2整合性を確認します。
2026-11-23にQSPI版を実機へ書込み、OBS経由で104秒の全編再生を確認しました。

|項目|改善前|改善版|
|---|---:|---:|
|アプリ平均fps|11.23|25.68|
|OBS録音の波形相関中央値|0.634|0.994|
|録音のクリップしたPCMサンプル（L/R）|2 / 6|0 / 0|

改善版は2671フレーム、PCM補充最大30.944 ms、FMハードクリップ0でした。
OBSの描画・エンコード落ちは試験中に増えていません。
core1起動・終了20回と譜面初期化40回、起動途中／再生中のUSB Ctrl-C各5回、
全編終了後のアプリ再起動3回で、ヒープの保持とREPL復帰を確認しています。
`tests/device_thread_restart.py` は実機上で再実行できるメモリ破損の回帰試験です。
音源終了時はcore1をROM待機へリセットし、GCが再利用したスレッドスタックを
後続のクロック設定IRQが書き換えることを防ぎます。

XIAOブリッジv1の応答・不正フレーム0を確認していますが、USBキーボードは未接続のため
実キー入力は未検証です。Flashのバックアップはユーザー指定で省略しました。
1台での有限試験で、録音の比較は聴感評価や周波数特性の保証を意味しません。
[改善版の実機記録](evidence/improvement-2026-11-23/summary.json)と
[シーン確認画像](evidence/improvement-2026-11-23/contact-sheet.png)、
[初回の実機記録](evidence/hardware-2026-11-23.json)を保存しています。

ネイティブ通信・PCM・DSPは、このリポジトリの既存実装から汎用部分を分離したApache-2.0コードです。
PIOはKAGURAの共有プログラムを使います。M+フォントの利用条件は共通ファイル内の
`fonts/LICENSE_MPLUS` に含めています。
