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

## 経過（2026-11-09、ブランチ `spi-palette-bsram`）

SPI対応は任意です。通常Releaseの要件ではありません。目的は、QSPIを使えないHostでも動かせるようにすることです。SPIとQSPIはビルド時にどちらか一方を選びます。実行時の切替えや、同じbitstreamでの両対応はしません。

**構成。** SPIだけの変更は `rtl/spi/` に置きます（[README](../../rtl/spi/README.md)）。`tools/build-fb.tcl` は `spi` のときだけ、同じ名前のファイルをこちらに差し替えます。QSPIのビルドは凍結した入力をそのまま使います。ブランチからビルドしたQSPIのネットリスト本体のSHA-256は、選定版と同じ `79434504…` でした。`check-release.py` も通ります。

**最新版の入力（PCMストリーミング、Queue8、PACKET_FIRST）での推移。** SPI、P4/R2で比べます。

|段階|Setup|違反|CLS|
|---|---|---|---|
|変更なし|−0.834 ns|17|4278|
|SPIにもCSデグリッチ|−2.747 ns|20|4283|
|＋パレットをBSRAMへ|−0.274 ns|5|4249|
|＋READ/WRITEアドレスをレジスタに|−0.35 ns（P3）|5|4259|
|＋行条件と行の半分を行末でレジスタに|−0.234 ns|1|4249|
|＋カーソル色を2スロットBSRAMでクロスドメイン|**+0.159 ns**|**0**|4245|

最終版はHold +0.456 ns、Recovery +8.190 ns、Removal +0.533 ns、BSRAM 25/26です。`.fs` のSHA-256は `e9f67c683df4ab9c5f9ee382433d0a46f101578dbdcf66684da14992ce8c1767` です（作業出力。成果物としては未固定）。

**効果がなかったもの。**
- 配置配線オプション：place 0〜4、route 0〜2、maxfan 0/16/23/32、replicate
- `opt_goal` の変更：areaは既定と同じネットリスト、timingは悪化
- Queue4への縮小：記述子がBSRAMからLUT RAMへ移り、CLSが増えた

**試験。** `bash tools/test-fb-spi.sh` で次を確かめました。
- 凍結版とoverlay版のscanoutを全画素で比較（3 seed）
- cursorを参照モデルと比較（mailbox 0/1）
- /CSグリッチ（フィルタなしで壊れることも含む）
- `tb_fb_host` とPCM2ボード試験（LANES=1、Queue8）

主な変異は検出できることを確認済みです。

**実機（2026-11-09）。** Tang Nano 9K、RP2040（120 MHz）、SPI 5 MHz（Kagura-9の `kagura_spi` PIO。配線はQSPIと同じで、IO2とIO3は使わない）。FPGAには上のSPI bitstream（`e9f67c68…`）をSRAMへ投入し、終了後に承認済みのQueue8へ戻しました。Host側は `B16_HOST_LANES=1`（CMakeの `-DKAGURA_HOST_LANES=1`）でビルドしています。QSPIのビルド（既定値）は、3本とも変更前と同じバイナリになりました。

|デモ|結果|SPI|QSPI（参考）|
|---|---|---|---|
|FOUR OPERATORS（RAM ELF）|完走、timeout 0、音声の10 ms欠落 0/0、相関の最小値 0.912|2961フレーム、最悪 63.2 ms|3429フレーム、54.6 ms|
|MIDNIGHT TERMINAL（Flash、後で書き戻し）|完走、timeout 0、音声の10 ms欠落 0/0、相関の最小値 0.983|2891フレーム、最悪 70.2 ms|3036フレーム、56.5〜59.2 ms|
|BEYOND 16 COLORS（Flash、後で書き戻し）|完走、全8シーン、timeout 0、audio fault 0、音声の10 ms欠落 0/0|4310フレーム|4452フレーム|

音声の半面の数はQSPIと同じです。帯域がQSPIの1/4なので、描画フレーム数は3〜14%減ります。RP2040のFlashは書き戻し、全2 MiBが一致することを確認しました。FPGAのFlashには書き込んでいません。BEYOND 16 COLORSは [`diagnostics/spi-hardware/run-beyond16.py`](../../diagnostics/spi-hardware/run-beyond16.py) で動かしました。ほかの2本は各デモの `run_hardware.py --image` で動かしています。

**SPIクロックのスイープ（2026-11-09）。** 同じSPI bitstreamを使い、Host側だけPIOの分周を変えて測りました。SCK = 120 MHz ÷（12 × 分周）です。6 MHzと8 MHzは端数のある分周になるため、SCKの周期が1 PIOクロック分揺らぎます。BEYOND 16 COLORSのbenchは、PSRAMの書込みと読出しを内容の照合込みで行い、512 byte転送の中央値を取りました。

|SCK|通信|生書込み 512 B|PSRAM書込み / 読出し|BEYOND 16 COLORS|FOUR OPERATORS|
|---|---|---|---|---|---|
|QSPI 5 MHz（参考）|OK|451 µs（1.14 MB/s）|0.296 / 0.313 MB/s|4452フレーム（選定版の検証）|3429フレーム、最悪 54.6 ms|
|SPI 5 MHz|OK|897 µs（0.57 MB/s）|0.201 / 0.206 MB/s|4310フレーム、全8シーン|2961フレーム、最悪 63.2 ms|
|SPI 6 MHz|OK|760 µs（0.67 MB/s）|0.222 / 0.228 MB/s|4359フレーム、全8シーン|3128フレーム、最悪 62.6 ms|
|SPI 8 MHz|OK|577 µs（0.89 MB/s）|0.254 / 0.264 MB/s|4388フレーム、全8シーン|3263フレーム、最悪 57.8 ms|
|SPI 10 MHz|**不可**|―|―|benchの起動時の識別で `KFB_DEVICE`|識別で `KFB_VERSION`（rc=−4）|

5〜8 MHzでは、照合の失敗、timeout、audio fault、音声の10 ms欠落がどれも0でした。10 MHzでは識別用の読出しから値が崩れます。FPGAは54 MHzでSCKを同期化しているため、立ち上がりを検出してからMISOが変わるまでに約3 system cycleかかります。さらに、読出しの期限は要求から1 SCK周期以内です。10 MHzでは、この余裕が足りないと考えています。8 MHzでは、BEYOND 16 COLORSのフレーム数はQSPIとの差が1.4%、FOUR OPERATORSは4.8%まで縮まりました。MIDNIGHT TERMINALは5 MHzでだけ試しています。基板は1枚で、有限時間の試験です。PVTは評価していません。

**解決（2026-11-09）。** MIDNIGHT TERMINALも8 MHzで完走しました（3004フレーム、音声の欠落0）。これで8 MHzは3デモとも確認済みです。SPI 5 MHzの配布UF2（FOUR OPERATORS、MIDNIGHT TERMINAL）は、自動開始から完走しました。SPI版は [releases/pcm-stream-spi](../../releases/pcm-stream-spi/README.md) にまとめ、[artifacts/validated/kagura-hd-spi-pcm-stream.fs](../../artifacts/validated/kagura-hd-spi-pcm-stream.fs) へ昇格させました。既定は5 MHz、8 MHzは任意の高速設定（保証しない）、10 MHz以上は非対応です。旧PCM2のSPI実験物は、記録として `artifacts/experimental/spi-sta-fail/` に残しています。
