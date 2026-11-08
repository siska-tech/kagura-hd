> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# Hardware approval and recovery plan

**未承認・実機操作0。release_ready=false / Release NOT READY。** 今回はUSB/serial/JTAG/device discovery、Flash read/write、FPGA SRAM投入を一切行わない。本書は実行承認ではない。

## 投入前

HEADROOM_STATUS.json、evidence/headroom-firmware.json、MEMORY_MAP.mdと全ログをレビューする。RTL/boards/releases、既存STA bitstream、2MiB復旧像をevidence/headroom-protected-before.jsonのSHA-256と照合する。選定bitstream SHA-256は642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7。既存backupを上書きしない。今回のfirmwareはout/headroom-firmware/<variant>/beyond16.bin/.elf/.elf.mapであり、歴史的evidence/rp2040-build.jsonのfirmwareとは別物。

実機の現在状態は履歴に基づく情報だけで未照会。前回reportでは音声停止・FINALE保持。承認後、接続対象と現状を確認し、全Flash2MiBを新しい日時付き専用pathへbackup、長さと二重readのhashを照合する。既存復旧像のhashとfilesystem境界0x100a0000を確認。必要なら今回直前の復旧像を第一復旧対象とする。FPGA Flashは書き換えない。既存STA bitstreamを無断SRAM投入しない。

## 承認後の有限順序

1. 全Flash backup、既存backup／bitstream hash確認。各bin/ELF hashとソースmanifestを固定。
2. PCM OFFでAの有限transport、続いてB/C。各10サイズ16反復、CS/READ波形確認、異常時は即停止。
3. 同じ試験をPCM ON。PCM0/1 STATUSと音声captureを併記。
4. A/B/Cを同じprofileで交互比較。Cの閾値はこの結果で選び、採用firmwareを再hashする。
5. A-off/summary/detailedで計測負荷を評価。その後work0/16/64/256/1024を同一計測で比較。
6. GPU協調cacheはDMA OFFの独立候補で試験。PRESENT中callback禁止と検知遅延を確認。
7. BLIT STORM単独、VECTOR単独、RASTER、scene境界を観測。
8. 全150秒autoplay、8scene、HDMI映像＋48kHz音声capture。
9. 全Flash readback、firmware領域、erase終端以降、filesystem全量を直前backupと照合。
10. offline解析とrelease判定。別途承認なしにGit merge／releaseしない。

固定条件: RP2040 120MHz、既存5MHz QSPI/PIOdiv2、同じFPGA候補／配線／素材／seed0xb1616、-O2、同じログ／計測。profile比較だけはprofileを変え、それ以外は固定。ABI KFB1/1.4/CAPS255確認前のPSRAMアクセス禁止。

## 合否と停止

GPU command error0、BUSY overwrite0、timeout0、PCM STATUS fault0、所有権違反0。deadline miss、PRESENT中央値/p95/最悪／33.333ms超過率、実更新fps、scene切替gapを報告する。音声10ms RMSだけを全sample健全性証明としない。DMAはCPU work増加と通信時間短縮を分けて採否判断する。PC PASSは物理PIO/DREQ/信号品質／PCM安全性の証明ではない。

timeout／不明command／PCM fault／readback相違時は自動再送、reset、probe再試行をしない。ログを保全し、停止を確認してから復旧可否を判断。DMA/PIO停止とCS解放を確認する。復旧のFlash書戻しも別途実機承認範囲を確認し、検証済みの今回直前backupを使用、書戻し後に全量readback比較する。既存backupは常にread-only扱い。FPGA Flash、保護対象clock/ABI/RTLを変更して回避しない。
