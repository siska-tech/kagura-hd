# 実機基板のQSPI速度試験（2026-11-23）

**今回の実機では8 MHzまで照合成功、10 MHzは識別情報が不一致**でした。
通常運用は従来の5 MHzを維持し、8 MHzは追加検証用の設定として扱います。
RP2040 CPUは120 MHz固定。FPGAは実行中のKFB1 / ABI 1.4 / CAPS FF構成です。
ユーザー製作のPico Carrier RevAに搭載したPicoとTang Nano 9Kで測定しました。

## 測定結果

次表はC SDK＋PIO＋64-byte書込みDMAの実測です。
読出しは既存transportのCPU FIFO処理を使用し、DMA化していません。
速度はアプリの有効payloadのKiB/s（1 KiB=1024 bytes）。
PSRAMの値にはコマンド発行、完了待ち、メタデータ転送を含みます。
ステージングは64-byte windowへの書込みAPIの所要時間で、PSRAM書込み完了速度ではありません。

| SCK設定 | PSRAM書込み KiB/s | PSRAM読出し KiB/s | ステージング書込み KiB/s | 照合 |
|---:|---:|---:|---:|---|
| 1 MHz | 158.5 | 163.8 | 361.5 | 成功 |
| 2 MHz | 230.8 | 243.9 | 659.4 | 成功 |
| 4 MHz | 295.7 | 304.9 | 1122.8 | 成功 |
| 5 MHz | 310.0 | 308.6 | 1304.8 | 成功 |
| 5.714 MHz | 315.6 | 308.6 | 1408.8 | 成功 |
| 6.667 MHz | 322.0 | 308.6 | 1547.2 | 成功 |
| 8 MHz | 328.8 | 308.6 | 1720.2 | 成功 |
| 10 MHz | — | — | — | identity不一致で停止 |

5→8 MHzのPSRAM書込み改善は約6%、ステージング書込みは約32%です。
読出しは約309 KiB/sで頭打ちです。CPUによるFIFO処理、64-byte単位のコマンドと
完了待ちが含まれるため、SCKの上昇率がそのままアプリの転送速度にはなりません。
速度を改善する次の候補は読出しDMA、コマンド／完了処理の負担削減です。

先行したPIO＋CPU FIFOのみの試験も8 MHzまで成功し、10 MHzはidentityで停止しました。
同試験の5〜8 MHzはPSRAM書込み約292 KiB/s、読出し約310 KiB/sでほぼ横ばいでした。

## 試験内容と限界

- 速度段階はPIO divider 10 / 5 / 2.5 / 2 / 1.75 / 1.5 / 1.25 / 1。
  SCK公称値は120 MHz ÷ divider ÷ 12。小数dividerには周期の揺らぎがあります。
- 各段階でidentity 1,024回、64-byte stagingの書込み／読戻し256回を照合。
- PSRAM `0x3f0000..0x3f3fff`の16 KiBを退避し、各段階で8種類のpatternを試験。
  各成功段階は128 KiB書込み＋128 KiB読戻し。0、FF、AA/55、walking-one、疑似乱数を使用。
- 最初の不一致・エラーで速度上昇を停止。10 MHzではPIO版がidentity照合3回目、
  DMA版が1回目で不一致。PSRAMの速度測定には進めていません。
- 最高成功設定8 MHzで、さらに128往復（計2 MiB書込み＋2 MiB読戻し）を実施。
  両版とも不一致、device error、timeoutは0。DMA版は33,024 DMA transfers、DMA error 0。
  この追加試験は約13秒で、長時間の連続運転試験ではありません。
- 終了後に1 MHzで退避領域を復元し、全16 KiBを照合。両版とも復元成功。
- 波形・実SCK周期・電圧・温度・位相余裕の測定はしていません。
  8〜10 MHzの間は未測定です。全アドレス・全負荷・個体差の保証ではありません。
- **これはネイティブC transportの測定です。現在配置済みのMicroPython bit-bangドライバの
  実効速度や上限を測った結果ではありません。MicroPython側の設定は変更していません。**

## 実行と復旧

試験プログラムは`no_flash` ELFで、全LOAD領域がRP2040 SRAM内であることを確認してから
picotoolでRAMへ配置しました。FPGA構成・FPGA Flash・RP2040 Flashへの書込みは0回です。
FPGAの表示ページとpaletteは変更していません。

RP2040 Flash全2 MiBを実行前後に読取り・比較し、両試験とも一致しました。
SHA-256は`3b2cc600ebc837b6aff6efc0289e39d0d783d4857fccaabc268cbd058f51062e`。
MicroPython 1.26.0へ復帰し、日本語ドライバ・フォント等の配置ファイルと
FPGA identity、STATUS=02（idle・timing errorなし）を確認しています。

実行前後の全Flashイメージは個人データを含む可能性があるため`build/`内のみで保持します。
USB上でRAM版のserial numberが`EEEEEEEEEEEEEEEE`となるため、RAM版のポートは
該当するVID/PIDの唯一の機器であることを確認しました。

## 証拠

- [PIO結果JSON](evidence/pio-2026-11-23.json) / [実行ログ](evidence/pio-2026-11-23.log)
- [DMA結果JSON](evidence/dma-2026-11-23.json) / [実行ログ](evidence/dma-2026-11-23.log)
- JSONの`test_rc=-100`は意図的に試した10 MHzのidentity不一致を示します。
  `restore_rc=0`、`flash_unchanged=true`が復旧確認です。
  失敗した段階のstatus/error値は未取得なので、JSON内の初期値0を正常判定には使いません。

ローカルの実行一式は`build/qspi-board-2026-11-23-v2/`と
`build/qspi-board-2026-11-23-dma/`にあります。

## ビルド

既存デモと同じ`software/midnight_terminal/toolchain/`のPico SDK・Arm GCCと、
`.deps/cmake/data/bin/cmake.exe`、`.deps/bin/ninja.exe`、`out/pioasm/pioasm.exe`を使用します。
`PICO_SDK_PATH`と`PICO_TOOLCHAIN_PATH`を設定して次を実行します。

```powershell
cmake -S software/qspi_benchmark -B build/qspi-benchmark -G Ninja -DPICO_BOARD=pico -DPICO_NO_PICOTOOL=1 -DCMAKE_BUILD_TYPE=Release
cmake --build build/qspi-benchmark --parallel 4
# DMA版は別buildディレクトリで -DBENCH_DMA=ON を追加
```

起動直後はUSB接続と`g`入力を待ちます。終了後の`r`でBOOTSELへ戻ります。
高速度試験ではFPGAのsticky timing faultが残る可能性があり、その場合は
基板再起動等の復旧が必要です。自動的に失敗コマンドを再送しません。
この試験で得た8 MHzを製品の保証周波数へ変更するものではありません。
