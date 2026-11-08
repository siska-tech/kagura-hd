# Host固定費 改善候補

実装：固定120MHz条件下のCS待機cycleを呼出箇所で定数化（setup30/hold5/間隔30cycle）、FIFO期限確認を最初と以降最大32反復毎へ変更。終端待機の期限確認は毎反復を維持。READ release位置、PIO/clock/配線、SDK直列化、timeout後停止・非再送を維持。B16_HOST_FAST=OFFで旧経路と比較可能。

生成Armコード確認時に、既存CMakeCacheのCMAKE_C_FLAGS_RELEASEが-gのみで、デモtargetに最適化指定がないことを発見。Release名でも対象CファイルのFLAGSに-Oがなかった。targetへ明示的な-O2を追加した。過去の実機測定値を修正・置換しない。今回の新candidateはコンパイラ最適化も変わるため、個別要因のA/Bには同じ-O2でFAST OFF/ONを比較する。

PC fake SDKによる実C transport試験：旧／改善ともwrite1/2/4/8/16/64/512B、read1/2/4/8/16/64/256Bのデータ、30/30/5/30待機cycle、RX無応答/TX詰まり/終端停止位置異常の3fault、CS解放と以後非再送、誤clock拒否をPASS。fakeの反復は実機経過時間ではなく速度測定に用いない。期限確認の間引きでtimeout検出は最大31反復遅れるため、厳密なus上限は割込みも含め実機未確認。transaction終端確認を省いていない。

RP2040ビルドPASS、text279232B、bss210540B、stack8192B。以前の未最適化候補text315500Bから縮小したが、コードサイズ差は速度改善値ではない。Flash容量検査PASS。実機書込み・波形測定・実機fpsはNOT RUN。release_ready=false。

次の実機では同一描画・同一ログ・同一-O2条件でFAST OFF/ONを有限ベンチ比較し、区間計測ON/OFFの影響も別途評価する。PCのfake試験は物理方向切替・信号品質を証明しない。新候補はVECTOR画質変更も含むため旧動画との全体比較だけでは固定費改善の因果を分離できない。

証跡：evidence/host-fixed-cost-tests.json、tools/test_host_fixed.py、out/host-tests/arm-disassembly.txt（-O2適用前の定数化確認）。新firmwareはout/rp2040/beyond16.bin、現在の実機は前回投入版のまま。
