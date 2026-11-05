# KAGURA-HD PCM2 QSPI — 実機確認済み最終版

実機Demoで使用したファイルは[artifacts/validated/kagura-hd-qspi-pcm2.fs](../../artifacts/validated/kagura-hd-qspi-pcm2.fs)へ配置しています。通常のGitHub Releasesへ添付する正式なBitstreamです。

- SHA-256：`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。
- Tang Nano 9K / GW1NR-LV9QN88PC6/I5、QSPI / PCM2 ABI 1.4。
- Gowin Standard V1.9.12.04、Place1/Route2。
- 内部STA：Setup +0.160 ns、Hold +0.484 ns、違反0/0。

Bitstreamは実機で使用した元ファイルから変更していません。正確な元入力40ファイル、PC/STA記録、統合後の回帰ログ、ライセンス・出典をこのディレクトリに保持しています。`source-input-manifest.json`と`build-inputs/`は元入力、`preparation-validation.json`と`validation-logs/`は統合後の記録です。`manifest.json`のartifact参照はvalidated配下を指します。

このディレクトリの`SHA256SUMS`は元入力・メタデータ・ログ用です。直接配布するBitstream用には[一つ上のSHA256SUMS](../SHA256SUMS)を添付してください。リポジトリルートで`python tools/check-release.py`を実行すると、成果物と元入力を検査できます。元入力は改行を含めバイト単位で保持し、現在のFPGAテキストソースとの照合だけはGitのLF/CRLF変換を許容します。

[ビルド手順](../../docs/standard-build.md)、[Host配線](../../docs/kagura-fb-host-api.md)、[BEYOND実機結果](../../software/beyond16/HARDWARE_RESULT.md)、[MIDNIGHT実機結果](../../software/midnight_terminal/HARDWARE_RESULT.md)を参照してください。有限の実機確認であり、最大通信速度・全PVT・長時間・複数基板を保証しません。生成物・IPの配布条件とライセンス表記は[公開資料](../../docs/release-validation.md)に記録しています。

SPIは[STA不合格の実験物](../../artifacts/experimental/spi-sta-fail/README.md)として隔離し、通常Releaseから除外しています。
