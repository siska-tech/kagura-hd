# ISO2：Host/CSR 6点観測とupload FF対照

後続[全word RMW診断](../../docs/host-window-rmw-result-2026-11-05.md)も限定4Bの全6点で一致。
BSRAM16/FF1415を維持、CLS1749、Setup+3.483ns。KAGURA-9復元済み、本体未統合。

[実測報告・仕様差・最小修正方針](../../docs/host-window-boundary-result-2026-11-05.md)。

SP実機：transport/CSR受理=ED0F2143、upload出力以降=AF0F2143。
FF対照：全6点＋Host受信=ED0F2143。各1ケース、復元済み、Release禁止。
製品RTL/Controller/PHYを変更していない。

```powershell
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/host-window-observe/prepare.py
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/host-window-observe/prepare_test.py
wsl bash diagnostics/host-window-observe/test.sh
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/host-window-observe/test_decode.py
uv --cache-dir build/uv-cache run --offline --no-project python diagnostics/host-window-observe/prepare_ff.py
wsl bash diagnostics/host-window-observe/test-ff.sh
```

`prepare.py`は元Hostと観測版の逆変換一致を検査する。観測版を製品へ置換しない。
SP/FF build Tclはupload leaf選択以外の論理/clock/IO/P&R設定を揃える。
`audit.py <build dir>`は内部STA・配線・pin・PSRAM非選択・compile hashを監査。
新しい空buildディレクトリを使い、保存候補を上書きしない。

PDT1：136B、source4/case2、20records、CRC32。payload slots：
0 transport受理4B、1 CSR受理4B、2 8cycle後upload32、3 first READ時upload32、
4 CSR応答4B、5 dispatch応答4B、6 tx_count、7 flags/rx_count/write_count/csr_count、8 read_count。
残りは0。`decode.py`は保存済みファイル専用でCOMを開かない。
CSR32..38はISO2/status/case2/LANES、CSR39 write1が1回限りのarm。
完了またはwatchdogでfreeze。全信号をUARTへ連続出力しない。

`prepare_hardware.py`は承認された個別trialのRAM/復旧ファイルを準備するだけ。
COM/JTAGを開かず既存trial directoryを上書きしない。自動sweep/自動再送なし。
今回の2ケースは終了済み。`fix-candidates/`はPCのみのRMW案で、実機投入物ではない。
