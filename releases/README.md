# 通常のRelease配布対象

実機Demo使用済みのPCM2 / ABI 1.4 / QSPI版だけを通常のGitHub Releases添付対象とします。リポジトリ公開とGitHub Release作成は別です。Releaseはまだ作成していません。

|添付asset|保存先|
|---|---|
|`kagura-hd-qspi-pcm2.fs`|[validated artifact](../artifacts/validated/kagura-hd-qspi-pcm2.fs)|
|`SHA256SUMS`|[直接添付用チェックサム](SHA256SUMS)|

SPI版はSTA不合格のため[experimental/spi-sta-fail](../artifacts/experimental/spi-sta-fail/README.md)へ隔離しました。**SPIは通常のRelease添付対象から除外し、FPGAへの書込みを禁止します。**

[QSPI元入力・実機記録](pcm2-qspi-final/README.md)、[SPIの生成履歴](pcm2-spi/README.md)、[候補台帳](candidates.json)、[Release本文案](RELEASE_NOTES.md)を保持しています。各variantの`SHA256SUMS`は、そのディレクトリ内のメタデータ・元入力・ログ用です。Bitstream本体は`artifacts/`だけへ配置しています。
