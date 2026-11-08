# KAGURA-HD PCMストリーミング QSPI（選定版）

Tang Nano 9K（GW1NR-LV9QN88PC6/I5）用。Queue8・QSPI CSデグリッチ（RC1系）に、48 kHzステレオのPCMストリーミングを加えたbitstreamです。2026-11-08に[PCM2版](../pcm2-qspi-final/README.md)に代わる通常Release添付対象として選定しました。

- [bitstream](../../artifacts/validated/kagura-hd-qspi-pcm-stream.fs) — SHA-256 `fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db`、UserCode `0x00008039`
- [manifest](manifest.json)、[元入力のSHA-256](source-input-manifest.json)、[パッケージのSHA256SUMS](SHA256SUMS)
- [再現ビルド](reproduce.ps1)：`build-inputs/` から合成し、`pnr/reroute.tcl`（P3/R2/maxfan 23）で再配置配線します。照合するのは次の4点です。
  - netlist本体のSHA-256（netlistは2.6 MBのため同梱せず、ハッシュを[manifest](manifest.json)に記録）
  - `.bin`
  - `.fs`（作成時刻の行を除く）
  - STA

## 検証

|項目|結果|
|---|---|
|STA|Setup +0.177 ns、Hold +0.527 ns、違反0/0|
|CSR 31の安全性|シミュレーション2,282項目PASS（[log](validation/csr31-safety.log)）|
|G1正式認定|53回PASS（[gate.json](validation/g1-certification-gate.json)）|
|再現ビルド|一致（[結果](validation/reproduce-result.json)）|
|メガデモ回帰|BEYOND 16 COLORS 150秒、4452フレーム、全8シーン、timeout/audio fault 0、HDMI音声の10 ms欠落0/0（[summary](validation/megademo/summary.json)）|

経緯は[設計監査報告書](../../diagnostics/pcm-stream-rc1/design-audit-report.md)の第14〜20節にあります。

## 注意

- CSR 31のbit1は診断用です。プロトタイプの全語DI切替えを再び有効にします。SDKはbit0（ACK）だけを書きます。アプリはbit1を書かないでください。bit2で解除できます。
- 効果はこの配置配線に依存します。入力やP&R条件を変えて再ビルドした場合は、STAとG1をやり直してください。
- Setupの余裕は0.177 nsで、RC1（0.659 ns）より小さい値です。PVTや外部I/Oのタイミング、複数基板は未評価です。MIDNIGHT TERMINALとMicroPythonのShowcaseは、この画像では再試験していません。
- 試用ではFPGAのSRAMへ一時投入してください。今回、FPGAとRP2040のFlashには書き込んでいません。
