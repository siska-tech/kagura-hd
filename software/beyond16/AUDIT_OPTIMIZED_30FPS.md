# 改善版から30fpsへ：再監査

対象：改善版firmware 9102def69ab613f53587d2426ec1b08f6105484f2850d427372ea5acae62a574 の有限実機1周と現行ソース。保存記録を再解析した。実機操作・C実装変更なし。release_ready=false。

## 結論

最短の達成候補はBLIT STORM。全scene30fpsには、Host固定費低減に加えRASTER／ROTO／VECTORの命令数削減が必要。VECTORは画素等価の小修正だけで達成できる見通しが立っていない。現在の結果からRTL制約でソフト改善不能とは結論できない。

|Scene|実測fps|30fpsへの必要速度比|平均描画commands/frame|平均call ms|
|---|---:|---:|---:|---:|
|BOOT|19.40|1.55|91.9|49.67|
|HYPERSPACE|17.40|1.72|99.9|56.24|
|RASTER|11.95|2.51|143.2|82.48|
|PLASMA|20.60|1.46|68.2|44.43|
|ROTO|15.28|1.96|105.6|64.08|
|BLIT STORM|28.16|1.065|57.8|34.16|
|VECTOR|4.20|7.14|482.6|238.08|
|FINALE|21.40|1.40|35.1|26.35|

command平均はscene遷移処理込み。FINALEは動的3秒と静的7秒の混合で、平均callが33ms未満でも動的30fpsの証明にはならない。callにはPRESENT、時にはPCM pollを含む。必要速度比は要求量で、達成予測ではない。

## 1. 最優先：Host固定費と計測負荷を切り分ける

148.217秒window中、Host callback合計124.193秒（83.8%）。約206万transactionで平均60.28us。

|区間|累積秒|transaction当たりus|wall時間比|
|---|---:|---:|---:|
|begin|34.018|16.51|23.0%|
|transfer|60.559|29.39|40.9%|
|end|16.393|7.96|11.1%|
|callback内・上記以外|13.223|約6.42|8.9%|

beginはGPIO方向設定、SM停止・再開、CS setup等を含む。endはPIO停止位置確認、CS hold/間隔等。transferはFIFO処理、期限確認と計測の一部を含み、純粋なPIO線上時間ではない。残差を計測器負荷やGPU時間と断定しない。

begin/endがゼロになる非現実的な理想でも、同じ仕事・他時間不変ならwall速度比は148.217/(148.217−50.411)=1.515。vblank量子化や更新時刻変化があるので実fps予測ではない。これだけでVECTORを救うことはできない。

前回平均transaction51.91us→今回60.28us、PCM再生中FILL32x32約679us→879us。描画命令数削減を単体commandの遅延増が一部相殺している。ただしログ方式・アクセスmix・計測設定が異なるため、増分を全て計測負荷とはしない。

次の独立試験を優先する：

1. 同じ改善版描画・USB設定で、区間計測ON/OFFをcompile option化してA/B。frame集計は両方同じ。warm-up後のraw transfer、FENCE、FILL/BLITを長さ・面積別に反復する。
2. `wait_ns()` のclock取得・64bit計算を初期化時に済ませ、固定120MHzで同じ30/5/30cycle相当のsetup/hold/間隔を保つ候補を評価。生成アセンブリを先に確認し、既に定数化されていれば二重に効果を見積もらない。待ちを撤去しない。
3. FIFOループ毎の64bit時刻取得を、有限byte数や一定iteration毎に間引く候補。timeout判定の最大遅延を定義し、停止・CS解放・fault latchを回帰検証。FIFO供給不足が減るか計測する。
4. 方向切替が不要な連続WRITE等でSM操作を減らせるか状態契約を検証。READのcount直後releaseを壊さない。DMAは短いCSR主体では後順位。
5. STATUS27とtag/error28..30のburst読出しを評価。BUSY/古いDONEは棄却、tag/sticky/transport error/ACKを維持。read途中の完了更新の契約はRTL読解とモデル試験が必要。queue1の複数命令無確認投入は禁止。

## 2. BLIT STORMを最初の30fps実証対象にする

28.16fps→30fpsは更新速度約6.5%増。ただし平均call34.16msを2.4%削るだけでは、CPU外処理やvblank取りこぼしを含むため十分ではない。完了間隔p95約50ms、最悪call82msなので平均達成と滑らかさを別に判定する。

現在の `next_frame=ms+33` は各開始時刻から次を再設定し、描画後 `sleep_ms(1)` が入り、vblank位相を安定させていない。PRESENT直前／直後のus時刻、前後の描画時間を別記録し、絶対30Hz deadlineと60Hz vblankの2周期に合わせた提出を比較する。実GPU queue1のためPRESENT待機中に次descriptorを上書きしない。待ちの除去だけでGPU処理が速くなるとはしない。

dirtyの縦統合に加え、近接する消去矩形を多少大きな黒矩形へ統合するcost modelを試す。32spriteは維持し、追加PSRAM面積と削減command数を計測する。面積別FILLベンチなしに全面clearが最速とは決めない。

## 3. 各sceneの残り

- **PLASMA**：page別tile cacheで改善したが平均68command/frame。時間が飛ぶとtileが多数変わり、遅いほど差分が増える可能性がある。実機timestampをPCへreplayし、変更tile数分布を取得する。tile更新上限を設ける場合は表示遅延が生じるため新画質仕様となる。より大きなtileや低周波の位相変化も候補。約1.46倍はHost固定費改善との組合せで検証価値が高い。
- **HYPERSPACE／BOOT**：約100／92command。背景消去の面積許容merge、同色星span統合を評価。64星自体にもFILL費が残る。個数削減だけで目標達成としない。
- **RASTER**：帯の3段BLIT化後も約143command。55枚のロゴsliceが下限を押し上げる。まず同じdyの隣接sliceを結合（画素等価）。次に16px slice（約28枚）、波の列数やlayer数変更を比較するが形状は変わる。scratch帯の9 FILLと復元1 BLITも含めた総数で評価。GPUは任意PSRAM source BLITを持たず、素材事前配置にはpage内の表示領域との兼ね合いがある。
- **ROTO**：横run統合後105.6command。隣接行の同色・同範囲runを縦統合し、画素等価のままFILLを減らす。セルcacheは前回spriteが覆ったセルを無効化し、各back page別に保持する。更なる解像度低下は別画質variantとして比較。
- **VECTOR**：482.6command／238ms。必要平均call削減は少なくとも86%（他の時間を無視した必要条件）。今の5x2ドットを細かい線へ置換するだけでは増える可能性がある。CPUで小領域に全線・重なり順を合成し、最終色の水平／垂直spanや矩形へまとめる候補を試す。幾何個数・辺数・点密度を削る案は見た目変更として分離する。30fpsを保証する案は現時点でない。
- **FINALE／切替**：最悪611.812msと前回509msより悪化。文字をその場で多数FILLする境界が候補だが、区間内訳なしに原因確定しない。caption、finale lettering、音声設定を別計測。文字bitmapをglyph BLIT化、初期preload、演出中の段階準備へ移す設計を優先する。

## 4. VECTORの「低解像度uploadで解決」に注意

既存SDK WRITEは64B毎に同期command。128x64/4bppでも4096B＝最低64 WRITEで、描画復元／PRESENTが別途必要。今回512B PSRAM WRITE約7.87msを線形外挿すると4096Bは約63msとなる（予測のみ）。単純な毎frame低解像度uploadでは30fpsに届かない可能性が高い。変更chunkだけの転送やspan描画との混合を比較する。

現在bss188648Bのうち147200Bが4600frameのログbuffer。RAM264KiBにstack8192B等も必要。大きなCPU maskを足す前に、ログを短い記録形式／scene別集計へ縮小してメモリ予算を確保する。heapやstackに無検証の全画面bufferを置かない。

## 5. 次回の判定と作業順

1. 計測ON/OFF比較とPRESENT直前後の記録。現在のp95はFRAME開始＋call時間から求めた近似完了間隔で、PCM pollなどがPRESENT後に入ることがある。厳密なPRESENT時刻ではない。
2. Host固定費候補を1つずつ独立opt-in化。波形契約・timeout／tag wrap／不確定submit非再送の回帰、同timestamp両page oracleを通す。
3. BLIT STORMで30Hz deadlineと消去mergeを検証。PLASMA・星へ展開。
4. ROTO縦merge／RASTER slice結合／文字準備を実装。VECTORは小prototypeでcommand予算を確定してから統合。
5. seed・素材・scene時間・clock・計測設定を固定して実機全150秒。動的区間の実更新fps、p95／最悪間隔、deadline miss率、切替停止、PCM capture／statusを記録。

30fps平均達成と全frame期限内を区別する。静止FINALEやHDMI60Hzをエフェクト30fpsの代用にしない。性能予測を実測として表示しない。RTL・ABI・bitstream・clockの凍結を維持する。

根拠：[再解析JSON](evidence/audit-optimized-30fps.json)、[実機結果](HARDWARE_OPTIMIZED_RESULT.md)、`src/b16.c`、`src/b16_qspi.c`、`src/rp2040_main.c`、既存C SDK。
