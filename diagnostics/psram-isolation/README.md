# PSRAM境界診断（案A upload echo実機FAIL、復旧済み）

後続[ISO2の6点観測](../host-window-observe/README.md)で、CSR受理は正しくupload SP出力から
破損することを確認。FF対照は一致、両試験後KAGURA-9復元済み。

2026-11-05、別承認のSRAM単回試験で、PSRAMを使わないupload echoが
ED0F2143→4F272143となり停止。WRITE要求/READ注入は未実施、KAGURA-9復元済み。
[実機結果と次の観測案](../../docs/psram-host-isolation-hardware-result-2026-11-05.md)。

案Aの生成結果は[Standard評価報告](../../docs/psram-host-isolation-standard-2026-11-04.md)。
最終候補は `build/host-isolation-standard/candidate-v2/impl/pnr/host_isolation.fs`。
Setup +2.071ns / Hold +0.708ns、違反0/0、全配線、PSRAM非選択netlist確認済み。
SHA256 `e64886ab3b80342d628b2f89655f95a759e4b00b12ead91c6c8b4cbf3cb6a3e2`。
SRAM投入1回・復元1回。Flash/FW変更なし。実機不合格・Release禁止。

[日本語技術報告書](../../docs/psram-independent-diagnosis-2026-11-04.md)を参照。
GPU/製品Controller/PHY/旧診断は編集しない。COM/JTAG/Flashへアクセスしない。

```powershell
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/psram-isolation/prepare.py
wsl bash diagnostics/psram-isolation/test.sh
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/psram-isolation/check.py
```

`prepare.py`は過去PASS/root、今回FAIL/RX32 worktreeのController/PHYを保存し、
既存PDR1 engineとpin-level Host tasksから独立PC testbenchを生成する。
既存baselineの内容が変わった場合は上書きせず停止する。
`test.sh`はRX32 Controllerで旧/新4B patternのUART149B、選択recorder、
実SPI/QSPI endpoint＋独立response stubを検証する。全て機能pair/デジタル試験。
ODDR/IDDR実遅延・PVTは検証しない。

追加RTL部品：`psram_host_stub.sv`、`psram_boundary_capture.sv`。
`oracle.py`はHost独立期待値/CA/chunk/別物理block guardのoffline planのみ。
自動実機実行機能はない。walking1/0はbyteごとのbit位置巡回であり、
全payload中の単独1bit/0bit試験は必要なら別ケースとして追加する。

`build/psram-isolation/`にコピーbaseline、生成harness、build/run logs、
`verification.json`を保存。PDR1 binaryは既存出力ディレクトリの別名
`build/psram-probe-sim/isolation-p*.bin`へ保存し、旧packetを上書きしない。

追加完成：`host_isolation_top.sv`＋`host_isolation_core.sv`、ISO1識別、
PDT1 snapshot serializer/decoder、pin/IO/netlist監査、Standard STA。
案AではController/PHYを使わず、全8境界の同時観測はしない。
外部Host IO min/maxと実機検証、案B/Cは未実施。

追加PC検証：

```powershell
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/psram-isolation/prepare_board_test.py
wsl bash diagnostics/psram-isolation/board-test.sh
wsl bash diagnostics/psram-isolation/vendor-test.sh
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/psram-isolation/test_trace.py
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/psram-isolation/test_host_case.py
```

SPI/QSPI正常＋QSPI異常要求停止、実UART波形136B×2を検証。Standard同版SPモデルでも
behavioralモデルとUART全byte一致。CRC破損/欠落/余分packet/意味矛盾をrejectする。
`host_case.py`は接続機能を持たないRAM診断関数。PCで第1UART frameを検証するまで
`run_read`を呼ばない。`run_one`にも必須`confirm_frame` callbackを設けている。

PDT1 recordsは20個の同時snapshot（cycle=0）。record0=byte address、1=words＋write bit5、
2/3=mask低/高32bit、4..19=payload512。source2は受理WRITE、source3は独立READ応答。
header flags bit0は要求異常。136B/frame、IEEE CRC32、case ID1。
CSRs32..38=`ISO1`、status、test ID1、LANES。status bit5 trace busy、bit4 log pending、
bit3 fault、bit2 frozen、bits1:0 request count。未定義診断bankは0、writeは無作用。
製品base bankのKFB1/capabilityは互換再利用のため残るが、GPU機能試験に使わない。

再生成は新しい空のbuild/配下から`build-host.tcl`。既存candidateは上書き禁止。
`tools/check-nano9k-timing.ps1 -BuildDir <dir> -BaseName host_isolation -ReportOnly`後に
`audit_build.py <dir>`で数値/端子/非選択/compile入力hashを監査する。
旧候補v1はmask guardが過剰でsuperseded。v2も今回upload echoでFAIL。
承認済みの単回試験は終了しており、再投入・追加診断へ自動的に進まない。
