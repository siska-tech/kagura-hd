# FPGA artifacts

|配置|状態|
|---|---|
|[validated/kagura-hd-qspi-pcm-stream.fs](validated/kagura-hd-qspi-pcm-stream.fs)|PCMストリーミング / Queue8 / QSPI。2026-11-08選定、通常のRelease配布対象（[パッケージ](../releases/pcm-stream-qspi/README.md)）|
|[validated/kagura-hd-spi-pcm-stream.fs](validated/kagura-hd-spi-pcm-stream.fs)|PCMストリーミング / Queue8 / SPI。2026-11-09、任意のSPI構成として配布対象（[パッケージ](../releases/pcm-stream-spi/README.md)）|
|[validated/kagura-hd-qspi-pcm2.fs](validated/kagura-hd-qspi-pcm2.fs)|実機Demo使用済みPCM2 / ABI 1.4 / QSPI。置き換え済み（superseded）、記録として保持|
|[experimental/spi-sta-fail/](experimental/spi-sta-fail/README.md)|旧PCM2のSPI、STA不合格。上のSPI版で置き換え済み。記録として保持、書込み禁止|

`validated`は保存したQSPIとSPIのファイルについて、既存の内部STAと有限の実機Demo動作を確認した区分です。全PVT・長時間・複数基板の保証を意味しません。[配布用メタデータと元入力](../releases/README.md)を参照してください。
