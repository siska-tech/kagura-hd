# 30fps達成に向けたソフトウェア性能監査

2026-11-06。対象は実機150秒完走時のC実装と保存ログ。**実機操作・再書込み・RTL変更は行っていない。改善案は未実装で、改善後のfpsは未測定。** Release NOT READYを維持する。

## 結論

30fpsに向けた余地は大きい。ただしドライバの小修正だけで全シーン30fpsになる根拠はない。BLIT STORM／星は背景消去の統合、PLASMAは上書き前の消去撤廃と更新タイルの選別、ROTO／VECTORは描画命令数そのものの削減が優先。通信経路の改修は独立に評価する。

「30fps」の判定は実際にPRESENTが完了した更新間隔で行う。720p60信号、PC論理30fps、静止フィナーレのPRESENT回数は動画エフェクトの30fps達成の証拠にならない。

## 実測と不足分

|Scene|実更新fps|平均描画呼出ms|実機描画commands/frame※|30fpsに必要な更新速度比|
|---|---:|---:|---:|---:|
|BOOT|14.50|59.71|118.1|2.07|
|HYPERSPACE|15.35|56.69|105.1|1.95|
|RASTER WAVES|8.35|110.45|242.9|3.59|
|PLASMA ENGINE|11.65|76.55|136.2|2.58|
|ROTOZOOM|6.52|143.18|323.1|4.60|
|BLIT STORM|14.40|60.70|120.1|2.08|
|VECTOR WORLD|3.90|246.59|570.0|7.69|
|FINALE|21.00|26.17|37.1|1.43|

※scene集計を記録frame数で除算。境界処理・文字描画込みで初期frameに計測上の偏りがある。FINALEは動的3秒と静的7秒の混合。速度比は必要量であり実現予測ではない。

実機Host callback内累積113.65秒／148.52秒＝76.5%。GPU描画時間とは異なる。FILL/BLIT32×32は有限ベンチで約0.68–0.69ms、FENCE投入約0.438ms＋完了確認約0.211ms。小さいFILL主体の本編に32×32の時間を一律適用してはいけない。PRESENT平均約6.94–8.19ms、最大16.94msでvblank位相を含む。

再解析した `次FRAME.ms − 現FRAME.ms − 現FRAME.us/1000` の中央値は主要sceneで7.3–8.0ms。これはログ出力、sleep、ループ処理、時刻丸め等の合計で、UART単独の実測ではない。FINALEではscheduler待ちを含み21.66msとなる。

## 優先1：命令数を減らす

既存PCモデルで各sceneのt=1066..2980msを33ms間隔で59frame実行し、descriptorを分類した。以下はPC上の決定的な命令数であり、実機の異なる描画時刻における命令分布ではない。生traceと再実行用scriptを保存した。

- **背景消去（全scene）**：`clear_dirty()` は8px行ごとに横runを消し、縦に同じrunが続いても別FILLにする。BLIT STORMのサンプルでは背景消去約99件に対しsprite約28件。縦方向のrun統合、矩形union、bounding rectangleへの統合を比較する。背景は動的領域では黒なので、過剰に黒く消してから全オブジェクトを描き直せる。header／caption／source atlasは絶対に消さない。命令削減とPSRAM書込み面積増のトレードオフがあるため、大矩形FILLの実機面積別ベンチが必要。
- **PLASMA**：108 BLIT＋24消去＋palette/PRESENT。576×192を不透明タイルで全て上書きする定常frameの24消去は不要。各pageに前回のtile IDを保持し、変わったtileだけBLITする。scene遷移時は旧sceneの外周残像を消す。更新率が高ければ108枚から54／27枚への大型タイル化と位相設計を試す。大型atlasは現行BLITがpage内sourceしか参照できず、任意PSRAM素材へBLITできない制約を先に解決する配置設計が必要。
- **ROTOZOOM**：288セルFILL＋24消去＋7 BLIT。同色の横runをまとめ、さらに同じrunを縦統合する。セル背景の全上書き部分は消去不要。page別のセル色cacheを使う場合、前回spriteが重なったセルを必ず無効化する。spriteがchecker矩形外へ出るため、その外側の旧sprite消去は残す。これでも不足なら24×12→12×6等の格子変更を画質比較する。72セルでも現行通信では余裕が乏しく、統合も併用する。
- **VECTOR**：サンプル約448線分用FILL＋104消去。現行 `line()` は線を5×2ドットに分解する。単なるBresenham化は命令数を増やす場合がある。CPU側の低解像度maskへ全線を合成し、同色spanを統合してFILLへ変換する案、形状／辺数／線密度の調整を比較する。色・重なり順を保存する必要がある。小領域uploadは64B毎のWRITEコストを含めて比較し、全面uploadへ逃げない。30fpsに最も大きな再設計が必要なscene。
- **RASTER**：162帯FILL＋55ロゴBLIT＋約24消去。3段の陰影付き帯をatlasへ事前配置できれば3 FILLを1 BLITへ置換できるが、既存source帯との容量競合を確認する。ロゴを8px→16px単位のsliceにすると55→約28命令になるが波形形状は変わる。帯を1段化／間引く場合も画像品質を別判定する。これら単独では30fps保証なし。
- **HYPERSPACE／BOOT**：星描画自体が約64 FILL/frameなので、消去統合だけでも現行通信では33.3msに収まる保証がない。星64/128/256の負荷sweep、同一色span統合、通信改善と組み合わせる。個数削減は画質変更として明記する。
- **FINALE／scene境界**：`caption()` が文字の各pixelを1×1 FILLする。最悪509msの発生源候補として文字描画を優先計測するが、内訳未測定なので原因確定とはしない。captionをglyph BLITか横spanへ置換し、finale文字を事前配置できるか検討する。両page初回の重い処理を定常frameと分けて計測する。

## 優先2：ログとscheduler

`CMakeLists.txt` はUARTとUSBのstdioを両方有効化し、毎frame約80–100文字の `printf` を行う。既存SDKの既定UART115200bpsでは8N1の線路占有だけで約6.9–8.7ms相当（推定、FIFOにより呼出しblocking時間とは異なる）。実測frame間隙と整合するが因果分離は未実施。

毎frameの文字ログをRAM内集計へ置換し、1秒毎に要約、終了後に詳細を出す。USBのみ／UARTのみ／無出力で同一seed・演出を比較する。ログOFFでもerrorと停止記録を失わない。ログ削減だけでVECTORの約246msが33msになることはない。

`next_frame=ms+33` と `sleep_ms(1)` は30fps近傍用で60fps経路がない。絶対時刻deadline（整数us、30Hz）とPRESENT完了時刻を記録する方式へ整理する。重いframeを追いかけて連続生成せず時間を飛ばす設計は維持する。scene切替とPCMイベントを長い描画の後まで放置しないよう、命令境界で時刻確認できる設計も検討する。ただし未完了命令中の共有descriptor変更は禁止。

## 優先3：安全なHost経路改善

既存opt-inの17B descriptor burstとCAPS cacheは既に適用済み。queue深度1のため、複数GPU命令の無確認連続投入は不可。

1. **区間計測を先行**：begin/endのGPIO方向切替、CS待ち、PIO transfer、DONE poll回数、SDK完了処理を別counterへ。ログは区間外。長さ別をwarm-up後数百回、PCM ON/OFF、同一clockで測る。
2. **27..30の連続read候補**：現在はSTATUS27と完了tag/error28..30を別transaction。完了候補を4B burstで読む方式は1回減らせる可能性があるが、レジスタ読出しの時系列整合性をRTL読解とテストで確認する。BUSY／古いDONE時は棄却、tag・sticky・transport error・ACK確認を維持。poll中は転送量が増えるため常に有利とは限らない。
3. **前commandの完了証明の再利用候補**：直前wait成功から次submitまで単一ownerで状態不変ならidle readを省ける可能性がある。ただし汎用SDKではraw IO／reset／別利用者があり成立しない。専用session内の状態機械と失効処理を証明できた場合だけ独立opt-in化する。
4. **PIO/C固定費**：`wait_ns()` は毎回clock取得と64bit演算、`transfer()` はFIFOループ毎に64bit時刻取得を行う。clock固定条件で待ちcycle事前計算、期限check頻度、FIFO供給効率を計測比較する。CS setup/hold、方向release、timeout停止・fault latchは維持する。DMAは小transactionでは準備費が上回り得るので後順位。
5. **IRQ**：PRESENT中の大量pollを減らせる候補。ただし配線／pull-up／IRQ解除契約を確認し、IRQ後もtag/errorを確認する。vblank自体の待ち時間は短縮しない。GPIO未確認の現段階では実装成功扱いにしない。

nominal5MHzなら連続データの理想payload上限は2.5MB/sだが、本編約80.6kB/sは短transaction・待ち等込みであり、その比率を単純な改善余地に換算しない。PIOはbyte毎に命令準備があり純粋な連続clockではない。512B raw write約2.6msも改善調査の材料。SCKを上げる前に固定費を分離する。今回のclock／RTL凍結を維持し、単純なclock倍増を解決策としない。

## 33.33msの予算と実施順

最初は描画・Host投入を**20ms以内**、残りをPRESENTとCPU／計測に確保する暫定予算で比較する。ただしPRESENTは最大約16.9ms観測なので20ms+待ちでは毎回33.33ms以内を保証できない。60Hz vblankに対する提出位相とdeadline missを測り、必要なら描画予算をさらに縮める。

説明用に平均1描画commandが0.5msなら20msで40件、0.25msなら80件。これは感度分析で、改善後の実測値でも全形状共通の単価でもない。現在のVECTOR約570件／ROTO約323件が、通信だけの小幅改善では不足する理由である。

推奨順序：

1. 計測分離とログ軽量化を独立変更。実機Before/After条件を固定する。
2. BLIT STORMの消去統合を最小prototypeにする。8/16/32/64/128で命令数・面積・時間を測る。
3. 不要な消去撤廃、palette値の変化時のみ送信（現在は毎frame、変化は500ms単位）、caption span化。これらは画素等価を狙う。
4. PLASMA tile cache、ROTO run統合、VECTOR span化を個別に検証。画質変更がある案は別variantとする。
5. 上記結果でも不足する分にHostの区間最適化を適用し、全scene再測定。

合格判定は各動的sceneのPRESENT完了間隔の中央値・p95・最悪・33.33ms超過率、scene境界遅延、音声faultとcapture、GPUerror／timeoutを併記する。平均fpsだけで成功にしない。画素等価変更は同じtimestamp列で両pageとpaletteのoracle照合、描画方式変更は承認対象の新基準画像とoracleを用意する。tag wrap、timeout、ACK失敗時の非再送を再試験する。

## 監査証跡

- [再解析JSON](evidence/audit-30fps/audit.json)：入力hash、scene数値、PC命令分類。
- [再実行script](tools/audit_30fps.py)：既存PCモデルDLLを実行、実機IOなし。
- [元の実機結果](HARDWARE_RESULT.md)：本監査はこの有限1周の範囲を越えて性能を保証しない。
- 主なソース：`src/b16.c`、`src/rp2040_main.c`、`../kagura_fb/kagura_fb.c`、`../midnight_terminal/src/mt_qspi.c`、同 `vendor/kagura_host.pio`。

今回追加したのは監査script・trace・報告書のみ。実装C、既存測定結果、firmware、bitstreamは変更していない。
