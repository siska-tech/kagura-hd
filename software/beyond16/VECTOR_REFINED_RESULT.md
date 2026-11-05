# VECTOR マスク方式の追加改善

低解像度版を基準として、次を適用した。

1. 差分矩形を作る際、同じ最終色なら変更済みでないセルを通って矩形を伸ばせるようにした。色の異なるセルへ過剰描画せず、最終画素を保つ。
2. ロゴ期間の全面dirty消去と前回mask全失効を撤廃。各BLITが覆った4x4セルだけ前回maskを255（未知）へ戻す。次の同じback pageのframeで旧ロゴ跡を最終mask色へ修復してから新ロゴをBLITする。

607時刻・VECTOR20秒の両Framebuffer全byteが低解像度版と一致。commands156770→139766（10.85%減）、transactions1411058→1258022。直前実機版相当の同じPC時刻列298131commandsに対して53.12%減。平均230.26commands/frame（scene入口処理込み）。見た目をさらに粗くする変更は加えていない。

独立GPUモデル画素oracle・全scene完走・fault非再送・timeout/tag wrap/boundsの4テストPASS。RP2040 CビルドPASS、text315588B、bss210540B、stack設定8192B。RAM使用量は前の低解像度版と同じ。Flash容量検査PASS。

実機未書込み・fps未測定。230命令/frameは現在のHost条件ではなお多く、30fps達成を宣言しない。通信区間の固定費削減は別の独立変更と実機A/Bが必要。計測負荷ON/OFFの切分けも未実施。release_ready=false。

証跡：evidence/vector-refined.json、tools/test_vector_refined.py。比較DLLはout/vector-lowres-before/optimized.dll。
