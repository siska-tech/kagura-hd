# 通常のRelease配布対象

2026-11-08から、**PCMストリーミング QSPI版**を通常のGitHub Releases添付対象とします（[選定版パッケージ](pcm-stream-qspi/README.md)）。従来のPCM2 / ABI 1.4 / QSPI版は置き換え済み（superseded）で、`artifacts/validated/` に記録として残しています。リポジトリ公開とGitHub Release作成は別です。Releaseはまだ作成していません。

|添付asset|保存先|
|---|---|
|`kagura-hd-qspi-pcm-stream.fs`|[validated artifact](../artifacts/validated/kagura-hd-qspi-pcm-stream.fs)|
|`kagura-hd-spi-pcm-stream.fs`|[validated artifact](../artifacts/validated/kagura-hd-spi-pcm-stream.fs)（SPI、任意の構成）|
|`SHA256SUMS`|[直接添付用チェックサム](SHA256SUMS)|

2026-11-09から、**PCMストリーミング SPI版**も添付対象です（[SPIパッケージ](pcm-stream-spi/README.md)）。QSPIとSPIは、ビルド時にどちらか一方を選ぶ別々の構成です。SPIのデモ用UF2（`four-operators-spi.uf2`、`midnight-terminal-spi.uf2`）のSHA-256は、パッケージの`manifest.json`に記録しています。旧PCM2のSPI実験物（STA不合格）は、[experimental/spi-sta-fail](../artifacts/experimental/spi-sta-fail/README.md)に記録として残しています。この実験物は引き続き書込み禁止です。

[選定版の元入力・検証](pcm-stream-qspi/README.md)、[SPI版の元入力・検証](pcm-stream-spi/README.md)、[旧PCM2 QSPIの元入力・実機記録](pcm2-qspi-final/README.md)、[SPIの生成履歴](pcm2-spi/README.md)、[候補台帳](candidates.json)、[Release本文案](RELEASE_NOTES.md)を保持しています。各variantの`SHA256SUMS`は、そのディレクトリ内のメタデータ・元入力・ログ用です。Bitstream本体は`artifacts/`だけへ配置しています。

## Queue8 QSPI CSデグリッチ RC1

[フルHDMIのローカル配布候補](queue8-qspi-deglitch-rc1/README.md)。
数値STA、QSPI回帰、実機メガデモ150秒・全8シーンを通過。
公開条件の確認待ちで、GitHub Releaseは未作成です。
