# SPI版PCM2 ABI 1.4のSTA違反を解消する

追跡Issue：[https://github.com/siska-tech/kagura-hd/issues/1](https://github.com/siska-tech/kagura-hd/issues/1)


## 問題

現行PCM2 / ABI 1.4をSPI（HOST_LANES=1）で新規ビルドしたところ、Bitstream生成は完了したものの、内部STAが不合格となった。

- Gowin Standard V1.9.12.04、GW1NR-LV9QN88PC6/I5、Place1/Route2。
- Setup最悪値 **−3.359 ns**、違反 **4件**。
- Hold最悪値 **+0.506 ns**、違反 **0件**。
- 最悪経路：`core/display/held_palette_49_s0/Q` → `core/display/palette_49_s0/D`。
- SPI SHA-256：`4e9ef3fe73d72ad245bbd659e8ede4de9837175fce32c2e86dd39bf7d497b719`。
- 回帰・実機試験はこのSPIビルドでは未実施。QSPI版の実機結果をSPIへ流用しない。

## 証拠と隔離

`artifacts/experimental/spi-sta-fail/`に`kagura-hd-spi.fs`、`timing-report.txt`、`SHA256SUMS`、`DO_NOT_PROGRAM.txt`を保存する。**FPGAへの書込みは禁止し、通常のRelease assetから除外する。** 元入力・ビルドログ・詳細STAは`releases/pcm2-spi/`に保持する。

## 再現

クリーンな作業出力先で、記録したStandard環境から`./tools/build-fb.ps1 -Transport spi`を実行する。元入力は`releases/pcm2-spi/build-inputs/`と`source-input-manifest.json`に固定している。

## 改善方針・完了条件

- palette bundled-data crossingを含め4違反端点の原因を分析し、RTL/配置への必要な対処を検討する。原因はまだ断定しない。
- SDCの安易な緩和やReportOnlyによるゲート回避は行わず、Setup ≥+0.100 ns、Setup/Hold違反0、負のRecovery/Removalなしを満たす。
- 修正後の影響範囲の回帰とSPI実機確認を別途実施・記録し、成果物のSHA-256と元入力を更新する。
- 認定完了後にのみvalidatedへ昇格し、通常Releaseへ追加する。
- 既存QSPI実機確認済みファイルは維持する（SHA-256 `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`）。
