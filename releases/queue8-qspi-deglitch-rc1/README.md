# KAGURA-HD Queue8 QSPI CSデグリッチ RC1

フルHDMI・PCM2・ABI 1.4のローカル配布候補。対象はTang Nano 9K
（GW1NR-LV9QN88PC6/I5）、QSPI 5 MHz、Queue8。
承認済みbitstreamを復旧用に保持し、試用はFPGA SRAMへ一時投入する。

- [bitstream](../../artifacts/experimental/queue8-qspi-deglitch-rc1/kagura-hd-qspi-queue8-cs-deglitch-rc1.fs)
- [bitstream SHA-256](../../artifacts/experimental/queue8-qspi-deglitch-rc1/SHA256SUMS)
- [画像と構成のmanifest](manifest.json)
- [元入力のSHA-256](source-input-manifest.json)
- [実機計数・音声分析](validation/hardware-summary.json)
- [全8シーンの映像サンプル](validation/contact-sheet.png)

STA改善Queue8の保存済み入力からQSPIアダプタだけを変更した。
同期済みCS highの3連続サンプルで終了を確定する。
READのIO出力許可は同期済みCS highで解放する。
Gowin V1.9.12.04、P4/R2、元のクロックとSDCで生成。
再ビルドにはbuild-inputs/tools/build-fb.tclへ
`qspi 4 2 8 0 1 auto`を渡し、別の出力ディレクトリで実行する。

同一波形の異常注入、Queue8・READ・COPY・PRESENT、PCM/PSRAM回帰が通過。
Setup +0.659 ns、Hold +0.527 ns、違反0端点。
元のQueue8 firmwareでメガデモ150秒・全8シーンを完走し、324936件を全件回収。
Queueエラー、timeout、PCM faultは0。録画の左右音声に10 ms単位の欠落検出0。
元firmware全Flashの一致と承認済みQueue8 SRAMの復旧を確認。
RP2040 Flash・FPGA Flashの書込みは0回。

Phase 5縮小版は短Highを観測せず1時間完走した。
フルHDMI版は今回の150秒1回の結果で、自然発生した短Highに対する実機抑制は未確認。
短Highの発生源は未確定。外部I/Oタイミング・PVTの認定は今後の範囲。

GitHub公開は認証復旧と適用されるGowin再配布条件の確認待ち。
公開用ファイル一覧はbitstream、bitstream用SHA256SUMS、本文案。
