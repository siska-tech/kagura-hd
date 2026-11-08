# KAGURA-9の実績値を再利用した5MHz QSPI

RP2040エントリポイントの診断用bitbangを、PIO QSPIへ置き換えた。GPU／PCMアダプターと既存HD SDKの契約は維持する。本稿のPC試験後、ユーザーの明示承認で実機投入・1周captureも実施した。最新の結果は[HARDWARE_RESULT.md](https://github.com/siska-tech/kagura-hd/blob/52fd69f6507b22c8c58d4112fd335562c7f9c57f/software/midnight_terminal/HARDWARE_RESULT.md)。`release_ready=false`。

## 再利用した内容

|項目|設定／出典|
|---|---|
|原PIO|`../Kagura/software/pico/kagura_host.pio`を無変更コピー|
|RP2040 system clock|120MHz、同`main.c`の設定|
|PIO divider|2、SCK = 120MHz / 2 / 12 = 5MHz|
|クロック方式|mode 0、MSB first、Low末尾で入力sampleし、その後SCKを上げる|
|配線|GP2..5 IO0..3、GP6 SCK、GP7 CS|
|CS guard|fall→clock:250ns、last fall→rise:40ns、high:250ns|
|pad|2mA、slow slew、データ入力Schmitt有効|
|read|header→count（0=256）→1 dummy byte→N data bytes|
|turnaround|count後、最初のdummy edgeより前に全IOを解放|

設定値はKAGURA-9の`kagura_host.c`、`main.c`、C版実機合格記録のREADMEを確認して再利用した。出典SHA-256は`vendor/qspi-provenance.json`。RP2040のsystem clock変更はC実行時の設定であり、FPGA PLL／制約を変更するものではない。

5MHzはbyte内のSCK設定値。PIOのpull・分岐・IO方向切替・CPU FIFO供給やCS guardによる隙間があり、連続データの実効転送量2.5MB/sを保証する表現ではない。

## HDへの適合

HDの`kagura_spi_adapter`は`REG_ADDR_BITS=6`で、KAGURA-9と同じcount／dummy／pre-rise samplingの契約を持つ。Cのレジスタ範囲を0..63へ広げ、bit5を保持し、incrementはHD endpointに委ねる。特に音声INDEX/DATAの54/55とcursorの32以上を5bitでaliasさせない。

原PIOのbit31（BUSY待ち指定）は0に固定する。KAGURA-9のVRAM_WRITE等のqueue-consumingレジスタ番号やBUSY規則はHDへ持ち込まない。HDは既存`kfb_*` SDKがdescriptor受付・完了を待つ。GPIO8..10への新しい依存も追加していない。

CPUはTX/RX両FIFOを処理し、write時にもRXを排出する。readのcount byteだけreleaseフラグを付ける。transaction全体に100ms timeoutを設け、RX停止・TX停止・最後のpull到達待ちの停止を検出する。失敗時はSMを止め、SCKをLow、CSをHigh、IOを入力にし、faultをラッチする。同じ不確かな操作を再送しない。

UART診断にwire byte、transaction数、合計transaction時間、最長transaction時間、timeout数を追加した。これらは将来の実機実行時に取得する値で、現在のPCモデル値を実測として記入していない。同期SDKは継続使用するため、作品全体の非ブロッキング化は別の残課題。

## PC検証

`tools/test_qspi.py`の8テストPASS。実際の`src/mt_qspi.c`をPico SDK seamでPCコンパイルし、全64レジスタ、6bit wrap、1〜256byte read、count=0、1 dummy、releaseフラグ、read/write切替、引数拒否、PIOリソース不足、clock不一致、3種のtimeout／安全解放／再送禁止を検査した。既存HD C SDK→新C transport→独立レジスタ／画素モデルの経路で、probe・奇数X FILL・mask WRITE／READ・音声CSRも検査した。

公式pioasmで生成した**原PIOの命令列**を、KAGURA-9から保存したcycle modelへ入力した。60MHz PIO instruction clock、32種類のFPGA出力遅延、read長1/2/7/64/256で合格。byte内SCK周期200ns、High/Low最小100ns、host setup最小100ns、IO競合なし。これは物理配線のモデルではない。元のPythonモデルにはfile handleのResourceWarningがあるが、ソース同一性を保ち、実行結果への影響はない。

さらに候補04の**変更していないRTL**をVerilator 5.032で動かし、既存PCM2 board-topテストベンチを5MHz連続mode-0クロック、CS guard 250/40/250nsへ調整したテストに合格した。Host upload/readback/FENCE、PCM2 PREPARE、COMMIT、ゲイン、pause/resume、loop/one-shot、unsupported拒否、画面の最終エラーなしを確認。sticky `late=0`、IO競合なしも明示検査した。

このRTLテストは既存のclock／DDR PHY／LVDS stubと独立メモリモデルを使う機能シミュレーション。PIOとRTLを一つの物理モデルへ結合した試験や、STA／PVT／配線品質の証明ではない。原RTL、Controller/PHY、PLL、SDC/CST、Bitstreamは変更していない。

## 再現

repo rootから：

```powershell
./software/midnight_terminal/tools/build_rp2040.ps1
./software/midnight_terminal/tools/build_qspi_tests.ps1
python software/midnight_terminal/tools/test_qspi.py
wsl -e bash software/midnight_terminal/tools/test_qspi_rtl.sh
python software/midnight_terminal/tools/preserve.py --check
```

Pythonはローカル環境では`python3.12.exe`を使用。Windows host pioasmはPico SDK同梱ソースからMSVCでビルドする。RTL試験にはWSLのVerilator/g++/Python3と保存済み`build/pcm2-timing-04`が必要。出力先は全てショーケースの`out/`・`evidence/`に限定する。

証跡：`evidence/qspi-tests.log`、`qspi-timing.json`、`qspi-rtl-harness.json`、`qspi-rtl-run.log`。最終RP2040 ELF/binのhashとサイズは`evidence/rp2040-build.json`。

**後続の実機では5MHz設定のC版でPSRAM/GPU事前診断と本編1周を確認し、映像とPCM0/PCM1の共存をcaptureした。physical SCK波形は未測定、警告30fps等の性能目標は未達。Release NOT READY。**
