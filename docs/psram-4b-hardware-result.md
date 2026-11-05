> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PSRAM独立4B診断の実機結果

2026-11-04。ユーザーが許可した1ケースのみ実施し、**4B WRITE/READはPASS**。
追加診断は行わず、既存KAGURA-9環境へ復元した。
KAGURA-HD本体の64B不一致、実ダイ同定、3ps例外は未解決。正式Releaseは禁止のまま。

## 投入前の確認

- Standard V1.9.12.04候補SHA-256:
  `f6619b747171c92ea9fdb0aa562acfadfdf7af37940d2d6286b9535eebca62ac`、一致。
- Setup +6.276ns、Hold +0.708ns、違反0/0、PnR/Bitstream生成完了、数値ゲートPASS。
- JTAGは1デバイス、ID `0x1100481B`、GW1NR-9C。対象partはGW1NR-LV9QN88PC6/I5。
- 専用CSTと実PnR pin reportを照合。PSRAM端子は内蔵die用LVCMOS18。
  UART TX=pin17/3.3V、trigger=pin42/3.3V、clock27=pin52/3.3V、reset/LED=1.8V。
- COM8はUSB 0403:6010 (FTDI)、115200 8N1、受信専用。COM7はRP2040 2E8A:0005。
  UART受信をSRAM投入前から開き、トリガ前の出力は0 byte。
- RP2040は元KAGURA-9 ABI(0,6)、PIOTransportを確認。console pause/close後、
  `_closed=True`, `_active=False`。GP2..5入力、GP6 Low、GP7 Highを確認。
  FW/ファイルを変更せず、RAM上だけで所有権を解放した。
- 現行RP2040全2MiB FlashのSHA-256は事前backupと一致:
  `7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。
  /boot.pyも既知SHA `9ef26228ee5039efa193938d4d11cc036d4b2589289250719f484647716b62b0`と一致。
  実Flash backupとround-trip確認済みrecovery UF2を保持し、両ファイルのhashも再照合。
  private recovery imageは公開証跡に含めない。
- 既存KAGURA-9のHDMI表示を事前captureとして保存した。

## 1回の実行と全UART証跡

Programmer `--run 2` **SRAM Program**を1回実行、Finished、3.01s。
programmer readback verifyを実施したとは主張しない。
初期化待機後、GP7を10ms Low→Highへ1回だけ操作した。
Topのarmed LEDを直接撮影・読出しする機構はないため、armed状態の独立観測はない。
SRAMロード後十分待った上でトリガし、応答packetによって初期化/起動成立を確認した。

| 項目 | 実測 |
| --- | --- |
| case ID | 1 |
| address | 300032 (0x49400) |
| length | 1 word / 4B |
| 期待値 | **F1 16 3B 60** |
| 実測値 | **F1 16 3B 60** |
| status | **0 (pass)** |
| 不一致byte | 0 |
| 全packet | 149B、PDR1/header/XOR/END!を検証 |
| packet後の無出力観測 | 約2.038s、余分なpacket/byteなし |

PDR1のエラーコードはstatusに統合され、1=mismatch、2=controller error、3=timeout。
今回はstatus=0。独立したcontroller error register値を読むpacket fieldはないので、
その値を取得したとは記録しない。expected/actualは64B field、意味のある先頭4B以外は0。
全149Bのraw binaryは`build/psram-probe-eval-4b/uart-full.bin`、
公開可能なhexコピーは[全UART packet](evidence/psram-4b-uart-packet.hex)。
SHA-256は`bd2ed2f03877b6267937c38c421fc78965faea9743b7a7fbd625301ed80c39af`。
[機械可読結果](evidence/psram-4b-result.json)にも保存した。

保存済みpacketを`diagnostics/psram/decode.py`で解析しstatus/data一致を確認した。
同decoderの`hardware_pass=false`は「packet単独で本体実機合格としない」という固定scopeで、
今回の限定4B結果は別の`single_case_pass=true`として記録する。
停止の実機観測はpacket終了後のUART無出力とトリガHighまで。PSRAM pinの外部scope等で
内部停止を独立実測したとはしない。固定FSMのfreeze設計とPC検証は別証拠。
再トリガ・長転送・境界試験・位相変更・CR0変更は一切実施していない。

## 復元と保持確認

Programmer `--run 1` **Reprogram**で既存FPGA FlashからSRAMを再ロード、Finished、0.49s。
Flashのerase/programは行っていない。GP7はHigh、旧PIOは解放済みのまま復元した。
RP2040全Flashを同じXIP範囲で再hashし、投入前と完全一致。
その後、通常soft resetで元のKAGURA-9 HDMI console (QSPI 5MHz)、
MicroPython v1.26.0 (2026-11-03)の起動bannerを確認した。
復元後capture `build/psram-probe-eval-4b/kagura9-restored.png`を目視し、
元のKAGURA-9 banner/REPL画面が表示されることを確認。
FPGA Flash/RP2040 Flash書込みは**0**。RP2040 FW/boot file、製品RTL/ABI/SDC、品質ゲートは無変更。
GitHub Push、Releaseなし。

## この結果で言える範囲

この配置・条件の1回4B transferでは、host staging窓を使わないcontroller/PHY/PSRAM
経路が正しい値を返した。全ての短転送やPVT/全域動作を保証するものではない。
元の64B周期不一致は未解消で、category1のwrap仮説と追加のlane偏り誤りをまだ分離できない。
PASSによる自動昇格・追加診断は行わず、ここで終了した。

private local evidenceは`build/psram-probe-eval-4b/`。
preflight/GPIO・FW hash、JTAG scan、SRAM program、全UART raw/metadata/decoded JSON、
1回トリガ、復元log、soft reset、復元映像を保持した。
