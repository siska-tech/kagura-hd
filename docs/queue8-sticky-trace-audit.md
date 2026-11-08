# Sticky設定元観測の試作

2026-11-07。原因は未確定。実機追加試験は未実施。

設定元（不正SUBMIT/未定義CSR、audio external_error、cmd_error）を
sticky_errorの既存設定優先順と同じ順序で保持する試作を実装。
sticky!=0時だけ識別CSRを診断読出しへ転用する診断専用設計。
製品ABIへ採用する変更ではない。

56 bit保持版はQSPI Queue8回帰を通過したが、
P4/R2でSetup -1.168 ns、違反4端点。
設定元3 bit＋要求アドレス5 bitの8 bit保持版は
Setup -0.994 ns、違反5端点。
両方ともHold違反0。通常の数値STA基準を満たさず実機投入を見送った。
8 bit版の専用診断経路テストは未実施。firmwareは双方ともビルド成功。

正確なRTLと全入力はbuild/queue8-sticky-trace/native/source-snapshot、
build/queue8-sticky-trace/compact/source-snapshotへ保存。
STAは各qspi-depth-8/result.json。
診断SDK試作はbuild/queue8-sticky-trace/trace-sdk.c。
試作を本線から除き、RTLを作業前のSTA改善版へ、
SDKを既存のGPU_RET診断版へ戻した。
FPGA SRAM・Flash、RP2040への書込みは今回0回。

観測追加で新たなSTA違反が発生するため、この方法のまま実機測定しても
元のsticky障害との切分けが困難になる。
次候補は追加の保持FFを用いず、既存sticky_errorの上位bitへ設定元を
診断専用に符号化する構成。現在の3設定経路を識別できるか、
合成後STAと異常注入試験を行う必要がある。
