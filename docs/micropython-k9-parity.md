# MicroPython実装のKAGURA-9相当化

2026-11-23。Native＋字形BLIT版を基準として保存し、標準MicroPythonのまま通信処理と端末操作を改善しました。
実機には改善版を配置済みです。FPGAのRTL・bitstream、MicroPython本体、XIAO firmwareは変更していません。

## 基準と計測

変更前のPythonソースを[ZIP](measurements/micropython-k9-baseline-2026-11-23.zip)に保存しました。
[基準manifest](measurements/micropython-k9-baseline-2026-11-23.json)はファイルごとのSHA-256と従来の計測値です。
フォントはこのリポジトリの`software/kagura_fb/fonts/`を使用します。

Pico Carrier RevA、RP2040 125 MHz、標準MicroPython 1.26.0、PIO QSPI 5 MHz・DMA有効、M+ 12pxで測定しました。
基準版を一時的に再配置して測定した後、改善版を再配置し、同じPC接続で測定しています。
表示負荷は同じ648 bytes・8行です。毎回最下行から開始し、全行でスクロールさせています。
基準版はカーソルなし、改善版はハードウェアカーソルの追従も有効です。

| 処理 | 基準版 | 改善版 | 改善倍率 |
|---|---:|---:|---:|
| 648 bytes表示・中央値 | 6,860 ms | 3,118 ms | 2.20倍 |
| 4 KiB書込み | 399,977 µs | 78,120 µs | 5.12倍 |
| 4 KiB読出し | 225,779 µs | 104,498 µs | 2.16倍 |
| COPY_RECT 100回 | 338,115 µs | 121,481 µs | 2.78倍 |

表示3回の生値は基準版6,904 / 6,860 / 6,773 ms、最終配置版3,154 / 3,118 / 3,118 msです。
別起動での改善版の中央値3,390 msも記録しており、起動状態等による変動があります。
転送値は各1回の実測で、コンソールを閉じた状態です。使用したPSRAM領域は読戻し照合後に復元しました。
表示の初期記録7,367 msとは開始位置を揃えていないため、この比較では上記の再測定値を使います。
[測定値と配置ハッシュ](measurements/micropython-k9-parity-2026-11-23.json)を保存しています。

再測定にはpyserialを導入し、キーボード入力を止めた状態で次を実行します。画面内容は変わります。

```sh
python tools/bench-hdmi-repl.py --port COM14 --repeat 3 --stress-lines 128 --output result.json
```

## 実装

- GPUのidle確認、error解除、payload転送、descriptor投入、タグ付き完了確認、ACKをViperの1呼出しへ集約。
  CSごとの転送は従来と同じPIO/DMA kernelを使います。各コマンドの完了を確認し、失敗したコマンドは再送しません。
- 検査・クリッピングを行うNativeDeviceは維持し、メモリ転送・palette・present等も直接の`@micropython.native`でコンパイル。
  非対応transportは通常のsubmit/wait経路を使い、`native=False`も利用できます。
- WRITEマスクは64回の多倍長整数更新から範囲式へ変更。転送先以外のbyteを保持する規則は同じです。
- 固定FPGA構成を所有するPIO接続のcapabilityと、常駐ASCII字形の送り幅を再利用し、文字ごとの不要なレジスタ読出し・フォント探索を削減。
  FPGAを再構成したら接続を作り直します。汎用transportのcapability読出しは従来どおりです。
- CSI A/B/C/D、H/f、G、d、s/u、J/Kの0/1/2を実装。画面消去前に未転送の描画をflushします。
- FPGAの独立したカーソルを下線形状で使用。位置変更時だけ非同期更新し、pause/closeで非表示、resumeで再構築。
  点滅・ANSI色指定・完全なVT100互換は実装していません。
- カーソルAPIもDeviceの排他制御へ組み込み、soft callbackによる途中割込みを防止。
- close後にtimer callbackがConsoleを保持しても、115,200-byte画面などの大きな参照を明示的に解放。

## 確認結果

- 英数・日本語混在の128行スクロール：描画エラー0、ring破棄0。計測後の空きheapは約40 KiB。
- USB Ctrl-Cで実行中ループを中断し、描画更新とREPLへ復帰。`2+3`相当の評価結果5を確認。
- 2回のsoft resetでNative有効、atlas準備完了、ハードウェアカーソル可視、描画エラーなし。
- 配置した9モジュールと2フォントをPC側とSHA-256照合。利用者からUSBキーボード入力の正常動作を確認済み。
- 実機ログは[受入記録](measurements/micropython-k9-parity-acceptance-2026-11-23.log)。
- 実際のMicroPython Unix runtimeでNativeの通常／一括dispatch両経路、クリッピング、タグwrap、非整列転送、
  BLIT、UTF-8、CSI、カーソル追従、close時の資源解放を検証。
- GPU kernelの制御フローをレジスタモデル上で実行し、payload、error ACK、古いタグ、タイムアウト、
  途中転送失敗時の再送禁止を検証。CIにも追加しました。

## KAGURA-9との差

KAGURA-9の「Pythonへ何度も戻らず転送をまとめる」方針をHDにも反映しました。
ただし、KAGURA-9のタイル番号転送・SCROLL_Yと、HDの字形COPY・画面COPYは別のABIです。
HDは文字ごとのGPUコマンドと最大64-byteのpayload窓を使用し、KAGURA-9の連続VRAM転送と同じ速度にはなりません。
今回の倍率はHD基準版に対するもので、KAGURA-9と同じ端末速度を達成したという意味ではありません。

HDは640×360のRAM shadowを保持するため、KAGURA-9のタイル端末よりRAM消費も大きくなります。
1時間以上の耐久試験、負荷中の実キーボードCtrl-C、KAGURA-9との同一内容の直接比較は未実施です。
frozen module配布と、HD ABIでの複数文字・メモリ転送全体の追加集約も今後の改善余地です。
