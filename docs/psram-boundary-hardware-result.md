> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 独立PSRAM 8B境界診断：Step 9でFAIL、切り分けとして有用

2026-11-04。指定BitstreamのSRAM投入1回、トリガ1回だけ実施した。
**実機の線形8B境界転送はFAIL**。Step 7のsame-start READは一致したが、
Step 9の絶対address 300064の独立4B READが不一致となった。
固定FSMはそこで停止し、**Step 10のguard READは未実施**。
追加診断・再trigger・診断reset再試行はない。
KAGURA-9構成・画面・console・RP2040 FWを復元/保持確認済み。正式Releaseは禁止。

## 事前確認と投入

- Gowin Standard V1.9.12.04、GW1NR-LV9QN88PC6/I5。
- 指定SHA-256を投入直前に再照合:
  `6c52669e3965d2d18ce993944a0e05d6af16f44caece545f328f3cb87afca657`。
- 数値ゲートを再確認: Setup +5.514ns、Hold +0.708ns、違反0/0、全配線完了。
  製品の品質ゲート・SDC・RTL/ABIには変更なし。
- JTAG scan: GW1NR-9C、ID `0x1100481B`、1 device。
- pin制約/PnR照合: in-package PSRAM=LVCMOS18、UART TX pin17とtrigger pin42=3.3V。
  UARTはCOM8 (FTDI USB 0403:6010)、115200 8N1受信専用。
  COM7は既存RP2040 (2E8A:0005)。配線・電圧設定を変更していない。
- KAGURA-9 ABI(0,6)、PIOTransportを確認し、pause/closeでPIO所有権を解放。
  `_closed=True`, `_active=False`、GP2..5入力、GP6 Low、GP7 High。
  RP2040のdevice file/FWは変更せず、RAM上の操作のみ。
- RP2040全2MiB Flashと保存済みbackupのSHA-256一致:
  `7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。
  /boot.pyの既知hashも一致。元Flash backupと復旧UF2のファイルhashを照合して保持。
  private recovery imageは公開証跡へ含めない。
- 事前のKAGURA-9映像をcaptureし、UARTを開いてからSRAMをロード。
  トリガ前UART出力は0 byteだった。

Programmer `--run 2` SRAM Programのみ1回、Finished、3.06s。
Programmer readback verifyを実施したとは主張しない。
GP7を10ms Low→Highへ1回だけ操作し、実装済み固定Step 0–10の実行を開始した。
armed LEDを直接読み出した独立証拠はなく、待機後の完全な応答で初期化/開始成立を確認した。

## 実測Step一覧

byte順で表示。WRITEのstatus0はcontroller完了であり、その時点でのmemory読戻し保証ではない。
WRITE packetのactual fieldは0埋めで**実測データではない**。

| Step | 操作/address | 期待値 | 実測値 | status |
| --- | --- | --- | --- | --- |
| 0 | WRITE 300032/4B | ED 0F 21 43 | N/A | 0 |
| 1 | WRITE 300060/4B | 21 43 65 87 | N/A | 0 |
| 2 | WRITE 300064/4B | 65 87 A9 CB | N/A | 0 |
| 3 | READ 300032/4B | ED 0F 21 43 | ED 0F 21 43 | 0 |
| 4 | READ 300060/4B | 21 43 65 87 | 21 43 65 87 | 0 |
| 5 | READ 300064/4B | 65 87 A9 CB | 65 87 A9 CB | 0 |
| 6 | WRITE 300060/8B | 01 23 45 67 8A AC CE F0 | N/A | 0 |
| **7** | **READ 300060/8B** | **01 23 45 67 8A AC CE F0** | **01 23 45 67 8A AC CE F0** | **0** |
| 8 | READ 300060/4B | 01 23 45 67 | 01 23 45 67 | 0 |
| **9** | **READ 300064/4B** | **8A AC CE F0** | **65 87 A9 CB** | **1 (mismatch)** |
| 10 | guard READ 300032/4B | ED 0F 21 43（予定） | **未実施** | N/A |

Step 9は4 byte全て不一致で、実測はStep 5で確認した初期seed Cと同じ。
error codeはPBC1 statusに統合（1=mismatch、2=controller error、3=timeout）。
独立したerror register値を返すfieldはなく、別のerror codeを取得したとはしない。
controller error/timeout packetは観測されず、最初の異常はStep 9のデータ不一致。

## UART証跡と停止確認

全binary: `build/psram-boundary-eval-8b/uart-full.bin`。
**10 packet ×149B =1490B**、受信後約2.019s無出力、余分なStep/byteなし。
`diagnostics/psram-boundary/decode.py`でPBC1、Step順0..9、各address/words/write flag、
全expected/actual field、status/data整合、XOR、END!を検証した。
decoder exit=1は不完全captureではなく、**完全な診断FAIL packetの正常解析結果**。

- [全1490Bのhexコピー](evidence/psram-boundary-hardware-uart.hex)
- [全Step decoded JSON](evidence/psram-boundary-hardware-decoded.json)
- [機械可読結果](evidence/psram-boundary-hardware-result.json)

UART SHA-256:
`11cb74d0cf6f38730f555f34626f4083dbd3b63ca9d57e33c0949669829c7097`。
元のrawファイルとport/時刻関連metadata、1回トリガのsent/result記録も保持。
UART無出力とGP7 Highは実測。内部bus停止を外部scopeで独立計測したとはしない。
停止後の追加probeは実施せず、固定FSMのfreeze設計/PC検証は別証拠として扱う。

## 合否と原因特定への有用性を分けた判断

**機能合否: FAIL。診断の有用性: 高い。**

1. Step 3–5は3 seedを書いた後もそれぞれ正しい。少なくともその時点で、
   これら3開始位置が常に同じ場所になる単純な恒久address aliasとは整合しにくい。
2. Step 7は8B全て一致し、Step 8は先頭4Bの絶対位置でも一致。
   それでもStep 9は境界後の旧seedを返した。同じ開始点のWRITE/READだけで
   合格する方法が、実機で偽PASSになることを確認できた。
3. 全1490BをPC上の32B wrap仮説モデルcaptureとオフライン比較し、**完全一致**。
   仮説は300060..300063の次に300032..300035へwrapし、READも同じ経路をたどるため
   Step 7は一致、絶対address 300064は更新されずStep 9で旧seedを返す。
4. この診断には製品host QSPI/staging窓がない。従って今回の不一致をその窓だけに
   帰することはできず、controller/PHY/PSRAMのburst経路に絞る証拠となる。

分類は**category 1（PSRAM設定/バースト仕様の不一致）を強く支持**。
ただし、現物のID/CR0実読出し、物理CA/CK/DQ/RWDS波形は今回取得していない。
設定値8F1Fと参照仕様の32B wrap解釈は既存の根拠で、実ダイ型番確定ではない。
controller処理やREAD/WRITE位相によるtransaction依存のaliasを完全排除しない。

**Step 10未実施なので300032への上書きは実測していない。**
モデルの上書き予測を実測値や読出し結果へ転記していない。
この境界は16B境界にも重なるため、この1ケースだけでwrap長32Bを一意に確定できない。
「32B wrap仮説に一致」と「現物のwrap長/上書き先を確定」は区別する。
初回64B評価の追加lane偏りbit化けも、今回の一致だけで解消扱いにはしない。
本体RTL修正、CR0変更、位相変更、次の試験は一切実施していない。

## KAGURA-9復元・保持

Programmer `--run 1` Reprogramで既存FPGA FlashからSRAMへ復元、Finished、0.50s。
Flash erase/programではない。RP2040全Flashを同じXIP範囲で再hashし、投入前と完全一致。
その後、通常soft resetで元KAGURA-9 HDMI console (QSPI 5MHz)と
MicroPython v1.26.0 / 2026-11-03の起動bannerを確認した。
これはKAGURA-9復帰用resetであり、診断のreset再試行ではない。
復元映像`build/psram-boundary-eval-8b/kagura9-restored.png`を目視し、
元のKAGURA-9 banner/REPLが表示されることを確認。

FPGA Flash/RP2040 Flash書込み0、SRAM診断投入1、trigger1、診断再試行0、追加診断0。
製品RTL/ABI/SDC・品質ゲートは無変更、GitHub Pushなし、Releaseなし。
復旧backupも保持。KAGURA-HD本体の実機不合格/Release禁止と元の3ps例外は継続。
