# PCM2 SPI — STA不合格ビルドの履歴

**通常のRelease配布対象から除外しました。Bitstreamは[artifacts/experimental/spi-sta-fail/](../../artifacts/experimental/spi-sta-fail/README.md)へ隔離し、DO_NOT_PROGRAMを付けています。**

2026-11-06、現行PCM2 / ABI 1.4ソースをGowin Standard V1.9.12.04、SPI / HOST_LANES=1、Place1/Route2で生成しました。Bitstream生成は完了しましたが、既存の数値ゲートでビルドスクリプトは終了コード1となりました。

Setup −3.359 ns、違反4件。Hold +0.506 ns、違反0件。回帰・実機試験はこのビルドでは実施していません。元入力40ファイル、実効lane設定、生成ログ、STAレポート、ライセンス・出典を調査用に保存しています。`manifest.json`は隔離先のファイルを参照します。

このディレクトリにBitstream本体は置きません。`SHA256SUMS`は元入力・メタデータ・ログ用です。隔離先にも専用の`SHA256SUMS`と`timing-report.txt`を保持します。将来の改善IssueでSTA未達を解消し、必要な認定を完了するまでvalidatedへ移動しません。
