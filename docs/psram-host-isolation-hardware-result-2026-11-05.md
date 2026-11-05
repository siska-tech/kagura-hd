> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PSRAM独立診断案A：upload echoでFAIL、KAGURA-9復元済み

後続の継続調査で、[CSR受理後→upload SP出力の境界を特定し、FF対照の一致を確認](host-window-boundary-result-2026-11-05.md)。
以下は最初の案A試験の記録。

2026-11-05。ユーザーが承認した案AのSRAM単回投入・4B1ケースを実施した。
**PSRAMを介さないupload窓のechoで不一致を確認し、その場で停止した。**
Controller相当へのWRITE要求と独立READ応答注入には進んでいない。
既存KAGURA-9への復元、RP2040全Flash hash一致、起動banner/HDMIを確認して終了。
新規Bitstream生成、PHY変更、追加pattern/再送/周波数変更、Flash/FW変更はない。

## 1. 観測された結果

|項目|結果|
|---|---|
|case|ISO1-1、upload window offset0、4B|
|候補|`host-isolation-standard/candidate-v2/impl/pnr/host_isolation.fs`|
|候補SHA256|`e64886ab3b80342d628b2f89655f95a759e4b00b12ead91c6c8b4cbf3cb6a3e2`|
|内部STA/配線|既存作成時Setup+2.071ns、Hold+0.708ns、違反0/0、全配線。投入前に再監査|
|JTAG|GW1NR-9C、ID0x1100481B、1device|
|SRAM Program|`--run 2`を1回、Finished、4.05s。readback verify実施の主張なし|
|GPIO|READY1、BUSY0、IRQ_N1|
|診断識別|`49 53 4F 31 00 01 04`、ISO1/status0/case1/4lanes、一致|
|Host経路|既存FW PIOTransport engine＋RAM上の6bit CSR adapter|
|SCK|PIO設定1,000,000Hz、4lanes、SM0。pad周波数/位相は未測定|
|送信意図/期待|**ED 0F 21 43**|
|Host受信|**4F 27 21 43**|
|XOR|**A2 28 00 00**|
|不一致|先頭2byte、計算5bit|
|WRITE要求snapshot|未到達|
|独立READ応答注入/download試験|未実施|
|PSRAM転送|設計上なし。Controller/PHYを含まず両die非選択/reset保持|

ここでの300032は後続のstub要求に使う予定だった論理addressであり、今回echoの
物理PSRAM addressではない。操作した窓はCSR25のpointer0からCSR24を4byte。

保存raw REPL応答：

```text
ISO1 {"stage": "diagnostic_identity", "test_id": 1, "actual": "49534f31000104"}
ISO1 {"length": 4, "test_id": 1, "xor": "a2280000", "stage": "upload_echo", "expected": "ed0f2143", "address": 300032, "match": false, "error_bytes": [0, 1], "actual": "4f272143"}
ValueError: ISO1 mismatch; STOP, no retry: upload_echo
```

`run_write`はecho比較に成功した後だけ`write_intent`をemitし、Device.write_bytesを呼ぶ。
今回はその前に例外停止。ソフトからのmemory WRITE/READ submitはともに0。
不一致後にCSR counterを追加READしてはいないため、post-failure内部counterの直接観測
とは区別する。UART受信は0byteで、要求snapshotの生成も確認されていない。

UART watchdogはWRITE段階をecho前からarmしていたため、要求未発行のまま期限が切れた。
ログの`UART capture deadline`を独立したUART回路故障やPSRAM timeoutとは扱わない。
次回の測定器では「echo段階」と「要求発行後のUART待ち」を明確に分ける必要がある。

## 2. 言えること／まだ言えないこと

**観測済み事実：** この案A・1回・PIO設定1MHzでは、PSRAMに依存しない
Host→CSR/upload window→CSR→Hostの往復が一致しなかった。
したがって今回の不一致をPSRAM READ latency、CA45、32B wrap、PSRAM WRITE timingで
説明する必要はない。まずHost/CSRと今回のRAM診断アダプタを切り分ける。

**未確認：** 次のどこで初めて値が変わったかは直接観測していない。

1. RP2040の送信ピンに出た値（現在分かるのはRAM内の送信意図）。
2. FPGA transport/CSRで受理したwrite byte。
3. upload SPへのcommit値と保存/読出し値。
4. window_group/lane選択後のCSR response。
5. FPGA QSPI出力とRP2040 PIO受信。

IDの一致だけでは全種類のCSR/window転送の正当性を保証できない。
SPモデルを含むPC統合PASSも、実I/O・SP入力timing・PIO間隔の正当性を保証しない。
今回追加したRAM-only PIO adapterの問題も排除できない。

## 3. 元の4B FAILとの比較

|条件|元KAGURA-HD FAIL|今回案A FAIL|
|---|---|---|
|期待|ED 0F 21 43|ED 0F 21 43|
|観測|0D 23 21 43|4F 27 21 43|
|XOR|E0 2C 00 00、6bit|A2 28 00 00、5bit|
|段階|PSRAM WRITE/READ後のHost受信|PSRAMを使わないupload echo|
|本体構成|GPU/scanout/音声と32B分割Controller/PHYあり|Host/CSR＋stub、Controller/PHYなし|
|先行負荷|boot初期化/scanout等あり|PSRAM転送なし|
|Host transport|保存identity.pyではQSPITransport(5)、software bitbang。正確なpad SCK未測定|既存PIO engine＋新RAM adapter、設定1MHz。pad SCK未測定|
|共通点|先頭2B不一致、後半2B一致|同左。ただし誤値・経路・配置・条件は異なる|

元の失敗を「Host/CSR原因で確定」とはしない。同一原因・別原因の双方を維持する。
ただしHost/CSRを正常と仮定してPHY位相評価へ進む根拠は失われた。
過去の独立4B PASSはHost窓を迂回しており、今回の結果と矛盾しない。
32B wrapの独立実機証拠と元64B残差16B/46bitも、そのまま別課題として維持する。

## 4. 投入前確認と復旧

投入前：候補fs、RP2040のprivate 2MiB backup、復旧UF2のhashを保存値と照合。
live全2MiB Flash hashも下記と一致し、boot.pyも既知hash一致。
KAGURA-9 ABI(0,6)/PIOTransport、元banner画面を確認した。
console pause/closeでPIO所有権を解放し、GP2..5入力、GP6 Low、GP7 Highを確認。
診断driver/helperは36分割でRAMへ読み込み、FWやdevice filesystemには書いていない。

試験後：

- 不一致後のdiagnostic再送・別pattern・追加READは0。
- QSPIをdeinitし、GP2..5入力、CS High/SCK Low、旧PIO closedを確認。
- Programmer `--run 1` Reprogramを1回。既存FPGA FlashからSRAMへ再ロード、Finished、0.45s。
- RP2040 live全2MiBを再hashし、投入前/backupと完全一致。
- 単一raw REPL接続を閉じ、通常soft reset1回で元のKAGURA-9 bannerを確認。
- 最終MJPEG captureを目視し、元のbannerとREPL画面を確認。追加FPGAロードやRP2040
  hard resetは行っていない。

RP2040全2MiBの前後hash：
`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`

boot.py hash：
`9ef26228ee5039efa193938d4d11cc036d4b2589289250719f484647716b62b0`

復旧hashは試験終了/FPGA復元後、通常soft reset前に照合した。
soft reset後にFlashをもう一度読み直したとは主張しない。
FPGA Flash書込み0、RP2040 Flash書込み0、FW/boot/device file変更0。

通常権限のCOM7/映像取得はOSアクセス拒否。操作開始前の失敗を保存し、必要な権限で
接続した。そこで不確実なdiagnostic commandを再送したことはない。
PC上のRAM-loader生成もstaticmethod扱いで1回停止したが、この時点ではRAM job未送信。
オフライン修正後に生成した36jobをそれぞれ1回だけ送った。

復旧時、raw YUY2キャプチャ2枚は先頭のKのみだった。通常REPLからconsoleの
`last_error=None`、`paused=False`を確認し、過去証跡と同じMJPEG形式では完全なbanner/REPLを
得た。YUY2画像だけで復旧PASSとはせず、最終MJPEGを根拠とした。形式依存の詳細原因は
未確定であり、PSRAM/Hostの故障と同一原因としない。

## 5. 仮説と次の最小観測（未実施）

|優先|維持する仮説|必要な観測|
|---|---|---|
|1|Host送信/FPGA受理不一致、今回RAM adapter/PIO timing|CSR24へ受理された先頭4byteをUARTで独立snapshot|
|1|CSR byte commit/SP保存または出力timing|受理byteと、commit安定後のupload_data[31:0]を比較|
|1|CSR read group/lane/responseまたはFPGA QSPI出力/PIO受信|upload値・CSR応答4byte・Host受信の三者比較|
|保留|PSRAMのREAD/WRITE、CA45、phase/latency、wrap以外の残差|上のHost/CSRが正しいと確認できるまで評価再開しない|

**次の第一候補は案A2：CSR受理・upload低32bit・CSR応答の3点観測。**

- 製品GPU/Controller/PHYは無変更。診断専用Host wrapperから既存CSRの受理interface、
  upload_data低32bit、CSR responseを観測端子として出す。
- 同じED0F2143/4B、PIO設定1MHzを維持し、まずCSR24のwrite受理4byteを記録。
  最後のcommit後に十分なsystem cycleを待ってupload低32bitをsnapshotする。
- Host echo時のCSR response4byteも保存し、UARTで独立に取り出す。
  全内部信号を同時streamせず、これら96bit程度＋valid/index/statusの限定snapshotとする。
- CSR受理から誤り：Host/transport/PAD/adapterを優先。
  受理正・upload誤：commit/SPを優先。
  upload正・CSR応答誤：window read pipeline。
  CSR応答正・Host誤：FPGA出力/PIO受信を優先。
- 診断観測の追加で配置が変わるため、偶然PASSしても修正完了としない。
  元候補・失敗条件・全結果を残し、対応する境界を証拠で比較する。
- 新top/Bitstream作成、SRAM投入は未実施。1回の承認を追加実験へ流用しない。

単なる再READ、長転送、全pattern、PHY位相sweepは今回の次手にしない。
診断案A2を具体化・PC検証した後、新規生成/実機計画の承認を別途得る。

## 6. 証跡・保持状態

ローカル正本：`build/host-isolation-hardware-2026-11-05/`。
`control/030-write.{raw,log,result.json}`が不一致の正本。
preflight/identity、SRAM投入/復元、GPIO解放、全Flash再hash、soft reset、
全キャプチャと初期アクセス失敗、UART watchdog、RAM生成/送信ログを保持。
`result.json`と`evidence-sha256.json`に判定・file hashを保存した。

公開可能なコピー：
[機械可読結果](evidence/host-isolation-hardware-result-2026-11-05.json)、
[失敗応答全文](evidence/host-isolation-upload-failure-2026-11-05.txt)。
private復旧imageを公開証跡へ追加していない。

元GPU候補fs、過去4B PASSのfs、元worktreeのDO_NOT_PROGRAMは再hash一致。
製品RTL/SDC/CST、STA合格アーキテクチャは変更なし。
案Aも実機FAIL、`release_ready=false`とRelease禁止を維持する。
