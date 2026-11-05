> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Dynabook での KAGURA-HD 検証準備

この手順は後日の実機検証用です。今回の監査はローカルの合成とシミュレーションを対象とします。

1. 本リポジトリ全体、Gowin Education 1.9.11.03、Python 3、RP2040 用 MicroPython 環境を用意します。
2. `tools/build-fb.ps1` と `-Transport qspi` を個別に実行し、ログ、timing-status.json と bitstream SHA-256 を保存します。SPI は `build/kagura-fb/impl/pnr/kagura_fb.fs`、QSPI は `build/kagura-fb-qspi/impl/pnr/kagura_fb.fs` です。
3. `boards/tang-nano-9k/host.cst`、`phase1.cst` と [ホストAPI](kagura-fb-host-api.md) の配線表で、使用基板、共通 GND、3.3 V、レーン数、IRQ プルアップを照合します。
4. 書込みを行う担当者が対象デバイスとビットストリームを照合した後、Gowin Programmer の手順で対象へ書き込みます。
5. HDMI 表示と起動完了を確認します。SPI は 1 MHz から開始し、ID、ABI、能力、READ/WRITE、FILL、PRESENT、カーソル、重なり BLIT の順で確認します。QSPI は専用ホスト転送実装で方向切替とダミーを検証します。
6. PSRAM 全域・境界・長時間負荷、HDMI 映像と音声の同時出力、クロック許容範囲、再起動を記録します。診断には `kagura_fb_memtest_top.sv` と `tools/build-fb-memtest.tcl`、継承した診断 Top と制約を使います。

持参するファイルは上記 bitstream と SHA-256、ビルドログ、タイミング報告、`software/kagura_fb/kagura_fb.c`、`.h`、`.py`、ホストAPI資料、基板制約、診断 Top とその依存 RTL です。ソース一式を持参すると再ビルドできます。

MicroPython SPI の最小例は次のとおりです。GPIO は上記配線表に合わせてください。

```python
from kagura_fb import connect_rp2040

dev = connect_rp2040(baudrate=1000000)
dev.fill_rect(1, 0, 0, 640, 360, 1)
dev.present(1)
dev.fence()
```

外部 PSRAM I/O タイミング、CDC 制約の妥当性、映像・音声品質、実機最大 SPI/QSPI 速度、基板間の再現性は実機での確認が必要です。公開音声制御 API は後続の対象です。
