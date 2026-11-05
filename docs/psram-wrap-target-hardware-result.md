> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PSRAM 32Bラップ先観測：Status 4、300032で予測一致

2026-11-04。指定BitstreamをSRAMへ1回だけ投入、1 triggerで固定8 commandを実施した。
最終Step 7のaddress **300032**で独立4B READの実測値 **8A AC CE F0**を取得。
**Status 4: 32Bラップ先予測一致**。予測不一致でも未取得でもない。
線形メモリの正常動作、KAGURA-HD本体の実機合格、Releaseにはしない。
再trigger、追加実験、CR0/位相/RTL変更はなく、KAGURA-9へ復元済み。

## 事前安全・復旧確認

- 指定SHA-256を投入前に再照合:
  `95338d44f7c7535fe18759996f69e3849a4ee44ff814711941b67a3bfde21694`。
- Gowin Standard V1.9.12.04、GW1NR-LV9QN88PC6/I5。
  Setup +6.601ns、Hold +0.708ns、違反0/0、配線完了の数値ゲートPASSを再確認。
- JTAG ID **0x1100481B**、GW1NR-9C、1 device。
- 原版CSTと実PnR reportを照合。UART TX=pin17、trigger=pin42、各LVCMOS33/3.3V。
  内蔵PSRAM CK/DQ等はLVCMOS18/1.8V。配線・電圧設定は変更なし。
- COM8はFTDI 0403:6010、115200 8N1、受信専用。UARTへの送信0。
  COM7はRP2040 2E8A:0005。投入前からUART受信を開き、trigger前出力0 byte。
- 旧KAGURA-9 ABI(0,6)、PIOTransportを確認し、console pause/closeで所有権解放。
  `_closed=True`, `_active=False`、GP2..5入力、GP6 Low、GP7 High。
  操作はRAM上のみでdevice file/FWは変更なし。
- RP2040全2MiB Flashの事前SHA-256が保存backupと一致:
  `7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。
  /boot.pyの既知hashも一致。実Flash backupと復旧UF2を保持し両file hashも再照合。
  private復旧imageは公開証跡に含めない。
- 投入前のKAGURA-9 HDMI画面を保存した。

Programmer `--run 2` **SRAM Program**のみ1回、Finished、3.05s。
Programmer readback verifyを行ったとは主張しない。
初期化待機後、GP7を10ms Low→Highへ1回操作した。
armed LEDの独立readbackはなく、完全なUART応答で初期化/開始成立を確認した。

## 全Stepの実測結果

byte順。WRITEのactual fieldは0埋めで、メモリ実測値ではない。

| Step | 操作/address | 期待/予測値 | 実測値 | status |
| --- | --- | --- | --- | --- |
| 0 | WRITE seed A 300032/4B | ED 0F 21 43 | N/A | 0 |
| 1 | WRITE seed B 300060/4B | 21 43 65 87 | N/A | 0 |
| 2 | WRITE seed C 300064/4B | 65 87 A9 CB | N/A | 0 |
| 3 | READ seed A 300032/4B | ED 0F 21 43 | ED 0F 21 43 | 0 |
| 4 | READ seed B 300060/4B | 21 43 65 87 | 21 43 65 87 | 0 |
| 5 | READ seed C 300064/4B | 65 87 A9 CB | 65 87 A9 CB | 0 |
| 6 | WRITE 300060/8B | 01 23 45 67 8A AC CE F0 | N/A | 0 |
| **7** | **READ 300032/4B** | **8A AC CE F0** | **8A AC CE F0** | **4** |

初期化不一致、controller error、timeoutは観測されなかった。
Step 7は初期seed Aから変化し、直前8B WRITEの後半4Bそのものを返した。
今回は折り返し先を独立READで実測しており、モデル予測を実測へ転記したものではない。
全8 commandで終了し、他のaddressや転送長の試験は追加していない。

判定を明示する:

- **予測一致: 取得済み、true（Status 4）。**
- 予測不一致: false（Status 5ではない）。
- 未取得: false（Step 7まで到達し、4B全て有効）。
- 線形メモリ合格: 判定しない。
- KAGURA-HD本体合格/Release: false、禁止を継続。

## 全UART証跡・整合性

rawは`build/psram-wrap-target-eval/uart-full.bin`。
**8 packet ×149B =1192B**、受信後約2.017s無出力、余分なpacket/byteなし。
PRT1 decoderでmagic、Step順序0..7、全address/words/WRITE flag、
expected/actual全64B field、status/data整合、CR0/LAT/RDL、XOR、END!を確認。
decoder exit=0は「観測完了」を示し、線形メモリPASSではない。

- [全1192BのUART hex](evidence/psram-wrap-target-hardware-uart.hex)
- [全packet decoded JSON](evidence/psram-wrap-target-hardware-decoded.json)
- [機械可読の観測結果](evidence/psram-wrap-target-hardware-result.json)

UART SHA-256:
`60d81af6052d66202ba70082a830a1bacb2d030941b757d87fcbdb8a9905a70a`。
オフラインで既存PC上の32B wrap-model captureと比較し、全1192Bが完全一致した。
これは追加実機試験ではない。Step 7の実測値は上表のUARTから取得したもの。
停止の実機観測はUART終了後無出力とGP7 Highまでで、外部scopeで内部busを計測してはいない。
再triggerによる停止確認は実機では行っていない。

## 根拠の更新と限界

前回の8B境界実験では同一開始点READが一致し、300064は旧seedのままで、
300032のguard READは未実施だった。
今回は同じ3 seedの初期確認後、300060から8Bを書いた結果、独立address300032が
後半4Bへ変化したことを確認した。**今回の開始点・長さ・設定で、折り返し先300032の
予測を実測が支持した**。category 1（PSRAM設定/バースト仕様不一致）の根拠が強まった。

この1回の観測で実ダイID、全addressのwrap規則、DDR timing/PVT、元64Bの追加bit化け、
全clientの動作を確定しない。本体の線形転送不適合は解消しておらず、
status4を本体PASSや品質例外解消へ昇格させない。修正・追加診断は今回未実施。

## 復元と保持確認

Programmer `--run 1` Reprogramで既存FPGA FlashからSRAMへKAGURA-9を復元、
Finished、0.50s。Flash erase/programではない。
RP2040全Flashを同じXIP範囲で再hashし、投入前/backupと完全一致を確認。
通常soft resetで元KAGURA-9 HDMI console (QSPI 5MHz)、
MicroPython v1.26.0 / 2026-11-03の起動bannerを確認した。
このresetはKAGURA-9復帰用であり、観測の再試行ではない。
復元capture `build/psram-wrap-target-eval/kagura9-restored.png`を目視し、
元のbanner/REPLがHDMIへ表示されることを確認した。

SRAM診断投入1、trigger1、再試行0、追加実験0、FPGA/RP2040 Flash書込み0。
CR0・位相・RTL/ABI/SDC・品質ゲート変更なし、FW変更なし、Push/Releaseなし。
旧復旧backupも保持。生成時のgate JSONにあるdevice_programmed=falseは生成時点の
履歴であり、今回の実投入は別の実機結果JSONへ記録した。
