# SPI STA failure — 実験用隔離

追跡Issue：[https://github.com/siska-tech/kagura-hd/issues/1](https://github.com/siska-tech/kagura-hd/issues/1)

**置き換え済み（2026-11-09）：** SPIの配布物は [validated/kagura-hd-spi-pcm-stream.fs](../../validated/kagura-hd-spi-pcm-stream.fs)（[パッケージ](../../../releases/pcm-stream-spi/README.md)）です。このディレクトリは旧PCM2のSPIビルドの記録として残します。下の注意は、このディレクトリのファイルについてのものです。


**DO NOT PROGRAM。FPGAのSRAM・Flashへ書き込まないでください。通常のRelease配布対象ではありません。**

現行PCM2 / ABI 1.4をSPI / HOST_LANES=1、Gowin Standard V1.9.12.04、Place1/Route2で生成した実験成果物です。

- Setup −3.359 ns、違反4件。Hold +0.506 ns、違反0件。
- 最悪経路：`core/display/held_palette_49_s0/Q` → `core/display/palette_49_s0/D`。
- 数値ゲート：Setup ≥+0.100 ns、Setup/Hold違反0。
- 回帰・実機試験：このSPIビルドでは未実施。
- SHA-256：`4e9ef3fe73d72ad245bbd659e8ede4de9837175fce32c2e86dd39bf7d497b719`。

[timing-report.txt](timing-report.txt)に元Gowinタイミングレポートを保存しています。[元入力・生成ログ・STAメタデータ](../../../releases/pcm2-spi/README.md)は別途保持します。将来の改善Issueで追跡し、修正と認定完了までvalidatedへ移動しません。
