# KAGURA-HD PCMストリーミング SPI（任意の構成）

Tang Nano 9K（GW1NR-LV9QN88PC6/I5）用です。[選定版QSPI](../pcm-stream-qspi/README.md)と同じ機能（ABI 1.4、Queue8、48 kHzステレオのPCMストリーミング）を、SPIのHostから使えるようにしたbitstreamです。2026-11-09に配布対象にしました。

QSPIとSPIは、ビルド時にどちらか一方を選ぶ別々の構成です。実行時の切替えや、1つのbitstreamでの両対応はしません。QSPIを使えないHost向けの任意の構成で、選定版QSPIのbitstreamと入力は変えていません。

- [bitstream](../../artifacts/validated/kagura-hd-spi-pcm-stream.fs) — SHA-256 `e9f67c683df4ab9c5f9ee382433d0a46f101578dbdcf66684da14992ce8c1767`、UserCode `0x0000694E`
- [manifest](manifest.json)、[元入力のSHA-256](source-input-manifest.json)（45ファイル）、[パッケージのSHA256SUMS](SHA256SUMS)
- [再現ビルド](reproduce.ps1)：`build-inputs/` から `tools/build-fb.tcl spi 4 2 8 0 1 auto` を1回実行します。照合するのは次の4点です。
  - netlist本体のSHA-256
  - `.bin`
  - `.fs`（作成時刻の行を除く）
  - STA
- [STA](timing/)、[検証記録](validation/)

## 構成

元入力は、選定版QSPIの41ファイルに次の4ファイルを足したものです。

- `rtl/spi/` の差し替えRTL（[説明](../../rtl/spi/README.md)）
- `tools/build-fb.tcl`：`spi` のときだけ、同じ名前のファイルを差し替える

差し替えの中身は次のとおりです。

- SPIでもCSデグリッチを有効にする
- パレットとカーソル色のクロスドメインをBSRAMに移す
- READ/WRITEのアドレスと行ごとの値をレジスタに入れる

機能は元のRTLと同じで、目的はSTAを通すことです。

配線はQSPIと同じです。IO0がMOSI、IO1がMISOで、IO2とIO3は使いません（FPGAは出力しません）。Host側は、デモのC transportでCMakeに `-DKAGURA_HOST_LANES=1` を指定すると、Kagura-9のPIOプログラム `kagura_spi` を使うSPIになります。

## 検証

|項目|結果|
|---|---|
|STA|Setup +0.159 ns、Hold +0.456 ns、違反0/0、Recovery +8.190 ns、Removal +0.533 ns（CLS 4245/4320、BSRAM 25/26）|
|再現ビルド|一致（[結果](validation/reproduce-result.json)）|
|シミュレーション|`tools/test-fb-spi.sh` の11項目がPASS（[log](validation/spi-regression.log)）。凍結版とSPI版のscanoutを全画素で比較、cursorを参照モデルと比較、/CSグリッチ、LANES=1のHost試験とボード試験|
|実機 SPI 5 MHz|3デモとも完走（[記録](validation/hardware/)）。timeout・audio fault・HDMI音声の10 ms欠落はいずれも0|
|配布UF2|`four-operators-spi.uf2` と `midnight-terminal-spi.uf2` が自動開始して完走。UF2の中身がELFと一致することも確認（[結果](validation/uf2-elf-check.json)）|

実機の各回では、RP2040のFlashを書き戻して全2 MiBの一致を確認し、FPGAのSRAMを承認済みのQueue8に戻しました。FPGAのFlashには書き込んでいません。

## SPIクロック

Host側のPIO分周だけを変えて測りました。SCK = 120 MHz ÷（12 × 分周）です。benchはBEYOND 16 COLORSのもので、512 byteの中央値です。PSRAMの読出しは、書き込んだ内容と照合しています。[clock-sweep.json](validation/clock-sweep.json)にすべての値があります。

|SCK|位置づけ|生書込み|PSRAM 書込み / 読出し|BEYOND 16 COLORS|FOUR OPERATORS|MIDNIGHT TERMINAL|
|---|---|---|---|---|---|---|
|QSPI 5 MHz|参考|1.14 MB/s|0.296 / 0.313 MB/s|4452フレーム|3429フレーム|3036フレーム|
|SPI 5 MHz|**既定**|0.57 MB/s|0.201 / 0.206 MB/s|4310フレーム|2961フレーム|2891フレーム|
|SPI 6 MHz|試験済み|0.67 MB/s|0.222 / 0.228 MB/s|4359フレーム|3128フレーム|―|
|SPI 8 MHz|**任意の高速設定**|0.89 MB/s|0.254 / 0.264 MB/s|4388フレーム|3263フレーム|3004フレーム|
|SPI 10 MHz|**非対応**|―|―|起動時の識別で失敗|起動時の識別で失敗|―|

- **5〜8 MHz：** 試した組合せはすべて完走しました。照合の失敗、timeout、audio fault、音声の10 ms欠落はどれも0です。音声の半面の数は、どの周波数でもQSPIと同じでした。
- **転送速度：** 生転送は周波数にほぼ比例します（理論値の約90%）。デモの描画は命令やPSRAMのオーバーヘッドの比率が大きいので、差は小さくなります。8 MHzでのフレーム数の差はQSPIの1〜5%です。
- **8 MHz：** 1枚の基板で3デモを確かめた高速設定です。動作を保証する周波数ではありません。使うときはCMakeに `-DKAGURA_SPI_PIO_DIV=1.25` を指定します。6 MHzと8 MHzは端数のある分周なので、SCKの周期が1 PIOクロック分揺らぎます。
- **10 MHz以上：** 現在の実装では非対応です。FPGAはSCKを54 MHzで同期化してから立ち上がりを検出し、約3 system cycle後にMISOを更新します。読出しの期限は、要求から1 SCK周期以内です。10 MHzではこの余裕が足りず、識別用の読出しから値が崩れました。

## 注意

- **配置への依存：** Setupの余裕は0.159 nsで、配置に強く依存します。同じnetlistでもP3では−3.427 ns、P2では−4.370 nsでした。入力やP&Rの条件を変えたら、STAと実機の確認をやり直してください。
- **評価していない範囲：** PVT、外部I/O（SPIのパッドタイミング）、長時間運用、複数基板。
- **組合せ：** FPGAとHostは、必ずSPI同士、QSPI同士で組み合わせます。QSPIのHostをSPI版のFPGAにつなぐと、IO1で出力がぶつかります。
- **MicroPython：** SPIヘルパー（SoftSPI 1 MHz）は、このbitstreamでは試していません。
- **UF2の配布：** 配布用UF2はリポジトリに含めず、GitHub Releaseに添付します。SHA-256は[manifest](manifest.json)にあります。
