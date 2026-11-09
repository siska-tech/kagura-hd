# 公開スナップショットと成果物の区分

2026-11-08から、**PCMストリーミング QSPI版**を最終版とします。従来のPCM2 / ABI 1.4 / QSPI版は置き換え済み（superseded）として、下の節に記録を残します。リポジトリの公開とGitHub Releaseの作成は別の作業です。2026-11-09から、任意の構成としてSPI版も通常のRelease assetに加えました。QSPIとSPIは、ビルド時にどちらか一方を選びます。Releaseとタグはまだ作成していません。

## Validated（選定版）

[artifacts/validated/kagura-hd-qspi-pcm-stream.fs](../artifacts/validated/kagura-hd-qspi-pcm-stream.fs)。SHA-256は`fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db`です。内部STAはSetup +0.177 ns、Hold +0.527 ns、違反0/0。

- **入力と再現：** [パッケージ](../releases/pcm-stream-qspi/README.md)に、元入力41ファイル、P&R設定、STA、検証記録、再現スクリプトを保存しています。
- **実機での確認：** G1正式認定（53回）、BEYOND 16 COLORSの150秒回帰、[FOUR OPERATORS](../software/fm_megademo/README.md)の132秒完走。いずれも有限の試験です。
- **経緯：** [設計監査報告書](../diagnostics/pcm-stream-rc1/design-audit-report.md)を参照してください。
- **保証の範囲外：** 全PVT、長時間運用、複数基板、最大通信速度。

## Validated（SPI、任意の構成）

[artifacts/validated/kagura-hd-spi-pcm-stream.fs](../artifacts/validated/kagura-hd-spi-pcm-stream.fs)。SHA-256は`e9f67c683df4ab9c5f9ee382433d0a46f101578dbdcf66684da14992ce8c1767`です。内部STAはSetup +0.159 ns、Hold +0.456 ns、違反0/0。SPIだけの差し替えRTL（[rtl/spi/](../rtl/spi/README.md)）を使い、QSPI版の入力は変えていません。

- **入力と再現：** [パッケージ](../releases/pcm-stream-spi/README.md)に、元入力45ファイル、STA、検証記録、再現スクリプトを保存しています。
- **実機での確認：** SPI 5 MHzで3デモを完走し、配布UF2の自動開始も確かめました。5〜8 MHzのクロックスイープも行っています。既定は5 MHz、8 MHzは任意の高速設定（保証する周波数ではない）、10 MHz以上は非対応です。いずれも有限の試験です。
- **保証の範囲外：** 全PVT、長時間運用、複数基板、8 MHzを超える周波数。

## Validated（置き換え済み：PCM2）

[artifacts/validated/kagura-hd-qspi-pcm2.fs](../artifacts/validated/kagura-hd-qspi-pcm2.fs)。SHA-256は`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。実機で使用したファイルを改変せず移動しました。内部STAはSetup +0.160 ns、Hold +0.484 ns、違反0/0です。

[QSPI元入力・記録](../releases/pcm2-qspi-final/README.md)に40入力、STA/PC結果、統合回帰ログ、ライセンス・出典を保存しています。実機確認は[BEYOND](../software/beyond16/HARDWARE_RESULT.md)と[MIDNIGHT（旧PCM2版）](https://github.com/siska-tech/kagura-hd/blob/52fd69f6507b22c8c58d4112fd335562c7f9c57f/software/midnight_terminal/HARDWARE_RESULT.md)の有限試験です。全PVT・長時間・複数基板・最大通信速度の保証は含みません。

## Experimental：SPI STA failure（旧PCM2、SPI版で置き換え済み）

[artifacts/experimental/spi-sta-fail/](../artifacts/experimental/spi-sta-fail/README.md)へ`kagura-hd-spi.fs`、`timing-report.txt`、`SHA256SUMS`、`DO_NOT_PROGRAM.txt`を隔離しました。**FPGAへ書き込まないでください。通常のRelease assetには含めません。**

現行PCM2 / ABI 1.4 / SPI / HOST_LANES=1、Gowin Standard V1.9.12.04、Place1/Route2で生成。Setup −3.359 ns、違反4件、Hold +0.506 ns、違反0件です。Bitstream生成後、既存の数値ゲートでビルドスクリプトは終了コード1となりました。回帰・実機試験はユーザー指定によりこのSPIビルドでは実施していません。

SPI SHA-256は`4e9ef3fe73d72ad245bbd659e8ede4de9837175fce32c2e86dd39bf7d497b719`。[元入力とログ](../releases/pcm2-spi/README.md)、[改善Issue #1](https://github.com/siska-tech/kagura-hd/issues/1)（[記録](issues/spi-sta-fail.md)）を保持します。このファイル自体は昇格させません。STAを通したSPI構成は、上の「Validated（SPI、任意の構成）」です。

## 公開・配布記録

[通常配布一覧](../releases/README.md)と[候補台帳](../releases/candidates.json)に区分を記録しています。`releases/SHA256SUMS`は直接添付するQSPIとSPIのbitstream用です。各variant配下の同名ファイルは、元入力・ログ・メタデータ用です。隔離SPIには専用のチェックサムがあります。

ライセンスキー、認証情報、全Flashバックアップは公開しません。Apache-2.0、NOTICE、第三者表記と生成IPの条件を保持します。過去の調査でGowin生成物/IPの再配布条件が未確認と記録されていた点は、解決済みとは扱いません。過去の`release_ready=false`は記録として保存します。
