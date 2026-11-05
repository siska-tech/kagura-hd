# 性能報告 — BEYOND 16 COLORS

実機の有限1周測定を追記した。PCのregister modelは3回のstatus pollingで完了させる機能モデルであり、PIO・GPIO固定費・PSRAM仲裁・HDMI vblank・PCM prefetchの時間を再現しない。以下のPC時間はネイティブC/SDK/modelのCPU実行時間。論理時間で割った通信量は「この描画を指定頻度で更新するための要求量」であり、実機がその量を処理できる証拠ではない。

## 指定比較表

|指標|MIDNIGHT TERMINAL実測|MEGADEMO PC|MEGADEMO実機|
|---|---:|---:|---|
|Host transactions/s|8832.21（約95秒で除算）|61748.39（論理150秒で除算）|14742.34（startup除外）|
|wire bytes/s|71091.95|329312.32（要求量）|80593.57|
|平均frame time|未計測|0.0345ms CPU/model|79.531ms（描画呼出し）|
|FENCE待機|未計測|0.708µs CPU/model呼出し全体。物理待機は未モデル化|211.19µs（Host completion確認）|
|実更新fps|通常scheduler約30Hz、増殖0.65–3Hz、scroll19–20Hz|30.347論理更新/s。実機fpsではない|11.022全体、scene3.9–21.0|
|PCM underrun|0（前作観測）|未モデル化。PCM制御fault=0、オフラインPCM生成欠落=0|STATUS fault0、capture低RMS欠落0。独立counterなし|

前作の57.60秒はtransaction累積時間でありGPU内部描画時間ではない。元ログの測定区間・startup包含と95秒の周回区間は厳密一致が保証されないため、上の前作rateは指定基準値からの参考算出。異なる作品間の高速化倍率は算出しない。

## 同条件Before/After

同一Cシーン・seed 0xB1616・33ms論理schedule・同一model。通常SDK＋CAPS非cache → opt-in descriptor burst＋session CAPS cache。

|指標|Before|After|
|---|---:|---:|
|GPU commands|1,029,051|1,029,051|
|Host transactions|10,428,231|9,262,259|
|Wire bytes|50,973,583|49,396,848|
|本編WRITE upload bytes|0|0|

transactionは11.18%削減。全シーン代表画素CRC一致。これは通信回数の削減で、実機速度の改善宣言ではない。GPU command数は変わらない。

## Scene別PC結果

|Scene|更新数|command/s要求|transaction/s要求|wire B/s要求|平均CPU ms|最悪CPU ms|
|---|---:|---:|---:|---:|---:|---:|
|BOOT|304|3521.6|31702.8|169062.0|0.0172|0.1174|
|HYPERSPACE|607|3160.8|28452.8|151736.4|0.0160|0.0876|
|RASTER WAVES|607|7290.9|65623.6|349980.6|0.0344|0.1664|
|PLASMA ENGINE|607|4085.7|36776.1|196126.8|0.0364|0.1733|
|ROTOZOOM|758|9729.0|87565.4|467004.5|0.0517|0.1838|
|BLIT STORM|758|3645.7|32816.1|175007.5|0.0188|0.0944|
|VECTOR WORLD|607|17608.5|158481.5|845223.0|0.0708|0.2209|
|FINALE|304|1655.0|14901.4|79459.2|0.0085|0.1550|

描画負荷は依然大きい。30/60fps、無停止遷移、実機音声の安定性はいずれも未証明。選んだ標準64 stars／32 objectsはPCでの保守的設定であり、実機安定上限として選定した値ではない。

## 負荷段階試験

|対象|個数|2秒の更新数|commands|transactions|wire bytes|BLIT pixels|CPU平均µs|
|---|---:|---:|---:|---:|---:|---:|---:|
|stars|64|61|6739|60707|323640|0|17.85|
|stars|128|61|11428|102908|548712|0|27.50|
|stars|256|61|20500|184556|984168|0|47.43|
|objects|8|61|2909|26237|139800|439296|8.98|
|objects|16|61|4906|44210|235656|876544|13.78|
|objects|32|61|7950|71606|381768|1756160|20.11|
|objects|64|61|11751|105815|564216|3481600|28.26|
|objects|128|61|15246|137270|731976|6962176|41.00|

全組合せでmodel command error=0／BUSY上書き=0。FENCE物理待機と実機fpsは未実行。個数が増えるとHost要求量が増える事実をそのまま記録した。

40件の転送／GPU／PCMベンチは[benchmarks.json](evidence/benchmarks.json)。RAW/CSR等の実機測定は[計画書](HARDWARE_PLAN.md)を参照。

## 実機の判定

全8sceneを150秒で正常STOP。30fps目標はFAIL、Release NOT READY。実機Before/Afterは未実行で、PCの11.18%を実機速度改善としない。[実機結果とScene別実測](HARDWARE_RESULT.md)。
