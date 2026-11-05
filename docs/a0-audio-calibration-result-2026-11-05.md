> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# A0左右差の追加解析とUGREEN既知入力較正

## 結論

**元A0とほぼ同じ左右差を、FPGAを接続しないPC→UGREEN経路でも再現した。** 左右完全同一のPCMを再生したにもかかわらず、旧キャンペーンと同じDirectShow AV取得では、A0共通波形のdual-mono入力に対して差RMS **1.38913LSB**、±2LSB以内 **93.3960%**だった。元A0はそれぞれ **1.38884LSB / 93.3815%**である。

この左右差だけをKAGURA-HD音声故障の証拠にはできない。一方、WASAPI排他取得でも差が残り、既知参照への厳密サンプル一致・時間軸保存は確認できなかった。したがって**元A0の固定判定FAILは維持し、新しいA0/A1/A2キャンペーンとStage 7は開始していない**。新しいbitstream、PHY変更、FPGA/RP2040操作は不要であり、今回も実施していない。

較正終了後、ユーザーがHDMI入力を元のFPGAへ戻した。KAGURA-9の復帰画面を取得・目視確認済み。

## 1. 原本の保護と解析条件

対象は`build/rmw-campaign-2026-11-05-v1/A0.wav`。48kHz、signed16 little-endian、stereo、144096frame、3.002秒。

SHA-256：`b93f10d1fb2cbfab809faf5cee282cedfe3c4cdc91e5643c0a646a0064b308df`。追加解析の前後で一致し、原本および旧キャンペーンの計画・判定を変更していない。

定義：差d=L−R、共通波形c=(L+R)/2。「差あり」はd≠0、「旧基準超過」は|d|>2。WAV先頭を時刻0とし、HDMI packet境界やFPGA内部時刻への同期を仮定しない。

NumPy 2.5.4 / Matplotlib 3.11.2で解析し、CSV・JSON・PNG・PDFを保存した。図は出力後に目視確認した。

## 2. 差分ヒストグラム

|L−R [LSB]|sample数|L−R [LSB]|sample数|
|---:|---:|---:|---:|
|−7|1|0|41747|
|−6|7|+1|31960|
|−5|58|+2|14607|
|−4|711|+3|4028|
|−3|4019|+4|639|
|−2|14551|+5|71|
|−1|31694|+6|3|

平均差 **+0.001048LSB**、RMS **1.38884LSB**、中央値0、最大絶対差7。非zero差は102349frame（約71.03%）、旧基準超過は9537frame（6.6185%）。|差|の95/99 percentileは3/4LSB。中心がほぼ0の小振幅分布であり、単純な片側DC offsetを主因とする形ではない。

![A0のヒストグラム、時間分布、波形、スペクトル](../build/audio-a0-analysis-2026-11-05/overview.png)

## 3. 発生時刻・連続性

- 最初の非zero差：sample0。
- 最初の|差|>2：sample35、約0.729ms。
- 最後の|差|>2：sample144094、約3.001958秒。
- 最大差−7：sample5920、約0.123333秒。
- |差|>2の連続長：1sampleが8165回、2sampleが607回、3sampleが50回、4sampleが2回。最大4sample（約83.3µs）。

差は冒頭だけ・末尾だけに集中していない。10msの完全300区間では超過率3.54～9.58%、平均6.62%。区間count分散を同じ平均のIID binomial分散で割った記述値は1.00056だった。ただしこれだけで独立確率過程とは断定しない。sample lag1の符号付き差の自己相関は**−0.12959**、超過indicatorのlag1相関は+0.00918である。

sample index mod16/32/48/64/96/128/192/256/480/800も保存したが、実packet位相は不明で、多重比較の補正を行った周期故障検定ではない。HDMI 192-frame境界に故障を結び付ける根拠としては使わない。

全非zero差のsample/time/L/R/d/傾きは[イベントCSV](../build/audio-a0-analysis-2026-11-05/difference-events.csv)、10ms集計は[時間CSV](../build/audio-a0-analysis-2026-11-05/time-10ms.csv)に保存した。

## 4. 波形との相関

|記述量|値|
|---|---:|
|corr(d, c)|+0.001060|
|corr(d, dc/dsample)|+0.016083|
|corr(abs(d), abs(c))|−0.002484|
|corr(abs(d), abs(dc/dsample))|+0.002411|
|corr(abs(d)>2, abs(c))|+0.000543|
|corr(abs(d)>2, abs(dc/dsample))|−0.000978|

offset・共通振幅・傾きを使う線形回帰の説明分散は**0.02598%**。単純なgain差・固定時間ずれだけで差の大部分を説明できる結果ではない。回帰係数を実際の物理gain/遅延として認定しない。傾きのquantile別にはRMS約1.30～1.61LSBの差もあり、あらゆる非線形依存を否定したわけではない。

Welch PSDの差分電力は10～24kHz帯が約67.0%。広帯域で弱く形状付けされた小振幅誤差と整合するが、dither/量子化/再サンプリングと断定はできない。元A0だけではFPGA内部と取得系を識別できない。

![波形相関・自己相関](../build/audio-a0-analysis-2026-11-05/correlation.png)

## 5. 較正の実施条件

ユーザーがPCのHDMI出力をUGREENのHDMI入力へ接続したことを確認し、Windowsでも`UGREEN-UHD (HD Audio Driver for Display Audio)`の新しいrender endpointを確認した。

Campaign `UGREEN-CAL-01`、計画SHA-256：`428f7217eefd93018760873f6deba83e2982eeb15375cce17de9ca7fb76a8647`。

|項目|固定条件|
|---|---|
|PC再生先|UGREEN-UHD、WASAPI endpoint13（この列挙時点）、明示選択。既定スピーカーを使用しない|
|再生形式|48kHz、16bit、stereo、WASAPI排他、explicit sample format、application dither_off/clip_off|
|取得先|UGREEN 15390、WASAPI endpoint14（この列挙時点）/同名DirectShow入力|
|取得経路D|旧キャンペーン同様のDirectShow AV、1280×720/60＋native48kHz stereo、FFV1/PCMで保存|
|取得経路E|WASAPI排他、explicit int16/48kHz/stereo、RawInputStreamで144000frame取得|
|刺激|無音、小振幅440/660/880Hz、A0共通波形dual-mono、固定seed小振幅PRNG、振幅4096の1kHz、固定seed中振幅PRNG|
|参照ファイル|各10秒。全fileでLとRのsample列が完全同一であることとSHAを検査|
|反復|6刺激×2経路、各1回・約3秒。自動再試行0|
|停止|API異常、端点曖昧、再生underflow、取得overflow、参照枯渇、形式異常|
|実行結果|12取得完了、API失敗0、render status flags0、input overflow0|

較正では「左右差の存在」が測定対象であり、既存FPGAキャンペーンの失敗caseを再試行したものではない。全12条件は較正前に固定し、良い結果が出るまで反復していない。

Sounddevice 0.5.6 / PortAudio V19.7.0-develを使用し、ローカル実装のWASAPI仕様と形式照会を確認した。排他出力はsoftware mixerを迂回する設定だが、**物理HDMI端子のbit列を別測定器で検証してはいない**。したがって評価対象はPC render/driver→HDMI→UGREEN→OS/取得API全体であり、UGREEN silicon単独への帰属ではない。OS既定音量・拡張処理設定は変更していない。

## 6. 較正結果

|参照|D：差RMS [LSB]|D：±2以内|E：差RMS [LSB]|E：±2以内|
|---|---:|---:|---:|---:|
|無音|0.67481|100.0000%|1.21603|96.5701%|
|小振幅multitone|0.69596|99.8715%|1.21525|96.6090%|
|A0共通波形dual-mono|**1.38913**|**93.3960%**|1.21588|96.5778%|
|小振幅PRNG|1.39295|93.3423%|1.21396|96.6139%|
|1kHz、振幅4096|1.38890|93.4079%|1.21246|96.6903%|
|中振幅PRNG|1.41621|92.8393%|1.24327|96.1021%|

元A0との差：DのA0 dual-monoはRMS比**1.000209**、±2以内の割合の差**+0.01453 percentage point**。signed histogramのtotal variationは**0.002070**、Jensen–Shannon divergenceは**0.00002519bit**だった。これは非常に近い分布である。

![A0と既知dual-monoの比較](../build/ugreen-audio-calibration-2026-11-05/a0-versus-calibration.png)

**観測済み事実：FPGAなしでもA0規模の差が発生する。** よって「d≠0」「±2を超える割合」だけでは、FPGAの左右不一致を測定系から分離できない。

Eでも差が残り、APIを変更するだけでbit透過になったとはいえない。Dの小振幅multitoneはcaptured RMS約10.91LSBに対し参照約77.52LSBで、global source相関も低かった。初期状態、driver/OS処理、取得経路の時間依存などを区別できておらず、「全入力に共通の固定gain一つ」として補正することも不適切である。

## 7. 時間軸と厳密sample判定の限界

非周期PRNG参照と録音の相互相関で大域lagを求め、100msごとの局所lagも記録した。

|取得経路・小振幅PRNG|局所offsetの範囲|offset傾きの記述値|
|---|---:|---:|
|D|4sample|−33.87ppm相当|
|E|5sample|−33.28ppm相当|

独立clock/再サンプリングと整合する時間軸変化であり、物理clockの直接測定値ではない。固定lagで3秒全体を参照sampleへ合わせるだけでは正しく評価できない。PRNG・A0の固定global lagでの厳密一致率も低く、既知PCMがそのまま保存される測定系ではなかった。

較正前に「左右差±2以内99.99%以上」「source sample±2以内99%以上」「gain誤差1%以内」「API fault0」を新しいsample試験用の経路適格条件として固定した。**D/Eのどちらも経路全体として不適格**。観測結果に合わせて閾値を緩和していない。

![全較正条件の差](../build/ugreen-audio-calibration-2026-11-05/comparison.png)

## 8. 判定と次段階

ここまでで分離できたのは、「FPGAがなくても旧A0とほぼ同じ差を生む経路がある」ということ。元A0の差をすべてcapture側と断定したり、RMSを差し引いてFPGAの誤差ゼロを証明したりはしない。

今後の順序は次のとおり。いずれも新bitstream/PHY変更を前提としない。

1. **測定器の次の較正段階**：現保存PRNGで時間軸変化・周波数応答を記述し、独立したheld-out参照で予測を検証する。短いpulseや左右非対称の負例を既知入力として使い、gain/帯域/左右取り違え/小さい異常を検出できるかを、事前固定した条件で評価する。厳密bit比較が必要なら別のbit透過デジタル取得経路を用意する。
2. **独立KAGURA-HD音声キャンペーン**：測定器の適格性を満たしてから、同じ指定候補でA0/A1/A2を別計画として固定する。雑音床・時間軸・伝達特性を考慮した指標を使用する場合、正常参照と負例の検出性能を先に証明する。旧A0を後付けPASSにはしない。取得前後のCSR/FIFO集約状態も必須とする。
3. **Stage 7**：A0/A1/A2が新計画でPASSした後に、有限時間・反復・データ量・停止条件を改めて確認する。音声未合格のまま競合stressへ進まない。

今回A0/A1/A2・Stage 7を実行していない理由は、取得経路が新しい厳密sample試験に適格と確認できていないためである。ユーザーの段階順序に従い、音声/競合/Releaseの合格は未宣言。

## 9. 保護・最終接続・成果物

この作業ではFPGA/JTAG/COM/RP2040を操作していない。FPGA SRAM投入0、Flash/FW/filesystem書込み0、RTL/Controller/PHY/SDC/CST変更0。A0原本、指定候補fs、復旧imageを保護し、`release_ready=false` / DO_NOT_PROGRAMを維持する。

ユーザーがHDMIを元のFPGAへ戻し、[KAGURA-9最終画面](../build/ugreen-audio-calibration-2026-11-05/kagura9-returned.png)の`KAGURA-9 RECOVERY CONFIRMED (0, 6) None`とREPL表示を目視確認した。今回の較正では機器Flash hashの再読出しは行っていない。

- [A0全解析JSON](evidence/a0-difference-analysis-2026-11-05.json)
- [較正12条件・source alignment](evidence/ugreen-calibration-2026-11-05.json)
- [原A0との比較JSON](evidence/a0-versus-calibration-2026-11-05.json)
- A0詳細：`build/audio-a0-analysis-2026-11-05/`のCSV、PNG/PDF、manifest。
- 較正原本：`build/ugreen-audio-calibration-2026-11-05/`のreferences、12 WAV、D経路の6 MKV、取得ログ、source/plan/script hash、alignment blocks、evidence-sha256。
- 再現コード：`tools/analyze-a0-difference.py`、`prepare-audio-calibration.py`、`run-audio-calibration.py`、`analyze-audio-calibration.py`、`characterize-audio-chain.py`。

実行markerで同じ較正の再送を拒否する。次に実機音声を再開する場合は、新しい有限キャンペーンとして管理する。
