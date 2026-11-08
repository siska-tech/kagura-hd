# 通常のRelease配布対象

2026-11-08から、**PCMストリーミング QSPI版**を通常のGitHub Releases添付対象とします（[選定版パッケージ](pcm-stream-qspi/README.md)）。従来のPCM2 / ABI 1.4 / QSPI版は置き換え済み（superseded）で、`artifacts/validated/` に記録として残しています。リポジトリ公開とGitHub Release作成は別です。Releaseはまだ作成していません。

|添付asset|保存先|
|---|---|
|`kagura-hd-qspi-pcm-stream.fs`|[validated artifact](../artifacts/validated/kagura-hd-qspi-pcm-stream.fs)|
|`SHA256SUMS`|[直接添付用チェックサム](SHA256SUMS)|

SPI版はSTA不合格のため[experimental/spi-sta-fail](../artifacts/experimental/spi-sta-fail/README.md)へ隔離しました。**SPIは通常のRelease添付対象から除外し、FPGAへの書込みを禁止します。**

[選定版の元入力・検証](pcm-stream-qspi/README.md)、[旧PCM2 QSPIの元入力・実機記録](pcm2-qspi-final/README.md)、[SPIの生成履歴](pcm2-spi/README.md)、[候補台帳](candidates.json)、[Release本文案](RELEASE_NOTES.md)を保持しています。各variantの`SHA256SUMS`は、そのディレクトリ内のメタデータ・元入力・ログ用です。Bitstream本体は`artifacts/`だけへ配置しています。

## Queue8 QSPI CSデグリッチ RC1

[フルHDMIのローカル配布候補](queue8-qspi-deglitch-rc1/README.md)。
数値STA、QSPI回帰、実機メガデモ150秒・全8シーンを通過。
公開条件の確認待ちで、GitHub Releaseは未作成です。
