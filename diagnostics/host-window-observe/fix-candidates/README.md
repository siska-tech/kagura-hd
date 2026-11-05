# 未統合の修正候補（RMW診断4Bは実機一致）

[2026-11-05の生成・実機結果](../../../docs/host-window-rmw-result-2026-11-05.md)。
RMW候補はSetup+3.483ns/Hold+0.708ns、違反0/0、全配線。限定4Bは全6点一致。
KAGURA-9復元済み。製品未統合、実PSRAM未評価、Release禁止。

`kagura_fb_upload_word_rmw.sv`は、動的native byte-enableを使わず、既存wordの
byteをmergeしてSPに32bit全書込みする対照案。SP32×16、parallel512出力と
既存CSR interfaceを保持する可能性があるが、製品RTLは変更していない。

連続partial write間には少なくとも1read edgeが必要。既存CSRのwrite_recovery/
SP出力安定待ちとの組合せをvendor SPモデルと既存window testbenchで検証する。
2026-11-05 PC検証PASS：byte write/readback、6 READ completions、18 COPY captures、warm reset。
モデルPASSはGW1NR-9の全物理条件の保証ではない。実機一致の範囲も1回の4Bのみ。
FF版のPASSをRMW版へ流用しない。機能回帰、配置/資源/STA再評価を経ず本体へ戻さない。

実行：`wsl bash diagnostics/host-window-observe/fix-candidates/test-rmw.sh`。
拡張PC検証は`prepare_rmw.py`→`wsl bash diagnostics/host-window-observe/test-rmw.sh`。
全mask128ケース、既存CSR、QSPI/UART、全word限定ゲートの正負テストを行う。
製品leafと同名moduleなので、診断用compile listで明示選択し、同時に含めないこと。
