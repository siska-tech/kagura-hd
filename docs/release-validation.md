# 公開スナップショットと成果物の区分

実機Demoで使用したPCM2 / ABI 1.4 / QSPI版を最終版とします。リポジトリ公開とGitHub Release作成は別です。通常のRelease assetはQSPIだけで、Release・タグはまだ作成していません。

## Validated

[artifacts/validated/kagura-hd-qspi-pcm2.fs](../artifacts/validated/kagura-hd-qspi-pcm2.fs)。SHA-256は`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。実機で使用したファイルを改変せず移動しました。内部STAはSetup +0.160 ns、Hold +0.484 ns、違反0/0です。

[QSPI元入力・記録](../releases/pcm2-qspi-final/README.md)に40入力、STA/PC結果、統合回帰ログ、ライセンス・出典を保存しています。実機確認は[BEYOND](../software/beyond16/HARDWARE_RESULT.md)と[MIDNIGHT](../software/midnight_terminal/HARDWARE_RESULT.md)の有限試験です。全PVT・長時間・複数基板・最大通信速度の保証は含みません。

## Experimental：SPI STA failure

[artifacts/experimental/spi-sta-fail/](../artifacts/experimental/spi-sta-fail/README.md)へ`kagura-hd-spi.fs`、`timing-report.txt`、`SHA256SUMS`、`DO_NOT_PROGRAM.txt`を隔離しました。**FPGAへ書き込まないでください。通常のRelease assetには含めません。**

現行PCM2 / ABI 1.4 / SPI / HOST_LANES=1、Gowin Standard V1.9.12.04、Place1/Route2で生成。Setup −3.359 ns、違反4件、Hold +0.506 ns、違反0件です。Bitstream生成後、既存の数値ゲートでビルドスクリプトは終了コード1となりました。回帰・実機試験はユーザー指定によりこのSPIビルドでは実施していません。

SPI SHA-256は`4e9ef3fe73d72ad245bbd659e8ede4de9837175fce32c2e86dd39bf7d497b719`。[元入力とログ](../releases/pcm2-spi/README.md)、[改善Issue #1](https://github.com/siska-tech/kagura-hd/issues/1)（[記録](issues/spi-sta-fail.md)）を保持します。STA修正と必要な認定が完了するまでvalidatedへ昇格しません。

## 公開・配布記録

[通常配布一覧](../releases/README.md)と[候補台帳](../releases/candidates.json)に区分を記録しています。`releases/SHA256SUMS`は直接添付するQSPIファイル用です。各variant配下の同名ファイルは、元入力・ログ・メタデータ用です。隔離SPIには専用のチェックサムがあります。

ライセンスキー、認証情報、全Flashバックアップは公開しません。Apache-2.0、NOTICE、第三者表記と生成IPの条件を保持します。過去の調査でGowin生成物/IPの再配布条件が未確認と記録されていた点は、解決済みとは扱いません。過去の`release_ready=false`は記録として保存します。
