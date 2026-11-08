# デグリッチ RC1 PCMストリーミング試作

RC1の保存済みビルド入力に [stream.patch](stream.patch) を適用する。48 kHz signed8ステレオ専用で、PSRAMに左右各8 KiBを確保する。各チャネルの32 byte先読みFIFOとQueue8のWRITE経路を再利用する。左右両方の最終応答がFIFOに格納されてから、Hostに半面を返す。

PowerShell 7でリポジトリルートから実行する。入力のSHA-256を検査し、新しい出力ディレクトリでGowin P4/R2を実行する。

```powershell
./diagnostics/pcm-stream-rc1/build.ps1
```

## 初回結果

|項目|RC1|試作 P4/R2|
|---|---:|---:|
|CLS|4212 / 4320|4262 / 4320（+50）|
|BSRAM|23 / 26|23 / 26（+0）|
|Setup|+0.659 ns|−0.692 ns|
|Hold|+0.527 ns|+0.527 ns|
|Setup / Hold 違反端点|0 / 0|552 / 0|
|Recovery / Removal|+10.146 / +0.533 ns|+8.029 / +0.751 ns|

Gowin V1.9.12.04の配置配線は完了した。Setupの最悪経路は `core/cursor/held_colors_17_s1/Q` から `core/cursor/sample_mailbox.value_43_s0/D`。出力はタイミングゲート不合格のため実機投入対象外。実機での補充期限と描画競合は未測定。初回のレポートは `build/pcm-stream-rc1/native/timing-status.json` と `build/pcm-stream-rc1/native/impl/pnr/kagura_fb.rpt.txt` にある。

## STA改善の比較方法

初回のSetup違反はsystem54内に548、pixel74内に3、カーソルのsystem54→pixel74に1。system54の上位には `memory_ctrl` の状態FFからTXデータ・マスクのCEへの経路が集中した。FILLのアドレス演算とHDMIの音声クレジットにも違反があった。

同じ合成済みネットリスト、CST、SDCで配置配線条件を比較する。出力ごとに入力のSHA-256とタイミングレポートを保存する。再現時は、初回ビルドの出力先を `-SourceTrial` に指定する。

```powershell
./diagnostics/pcm-stream-rc1/reroute.ps1 -Place 3
./diagnostics/pcm-stream-rc1/reroute.ps1 -Place 1
./diagnostics/pcm-stream-rc1/reroute.ps1 -Route 1
./diagnostics/pcm-stream-rc1/reroute.ps1 -MaxFan 16
```

RTL候補は、TXデータ512 bitとマスク64 bitのロード・シフト制御を1サイクル前に登録する。ロードとシフトの実行サイクルが従来の条件と一致することをシミュレーションでassertする。`tb_fb_burst_ctrl` のランダムマスク書き込み、1〜16 word、境界分割、リセット試験は通過した。

```powershell
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -Output build/pcm-stream-rc1/sta-tx-registered
```

|条件|Setup|Setup / Hold 違反端点|状態|
|---|---:|---:|---|
|初回 P4/R2|−0.692 ns|552 / 0|タイミング未達|
|P3/R2|−1.310 ns|33 / 0|タイミング未達。最悪経路はdescriptor RAM→COPY範囲判定|
|P1/R2|—|—|194本が未配線|
|P4/R1、P4/R2 MaxFan 16|—|—|配線完了レポート未取得|
|TX制御登録 P4/R2|−0.756 ns|30 / 0|CLS 4250、BSRAM 23。PSRAMバーストとQueue8 QSPI基板トップの回帰は通過|
|TX制御登録＋窓選択分割 P4/R2|−0.738 ns|1 / 0|CLS 4263、BSRAM 23。QSPI基板トップ回帰通過|

配線結果は `build/pcm-stream-rc1/sta-*` の `build.log` と `timing-status.json` に出力する。TX制御登録版の配置配線結果は同版の `native/` 以下に出力する。

TX制御登録版では、最悪経路が `window_write` からアップロードRAM入力へ移った。上位25経路は同じ選択信号を起点とする。CLSは初回より12減り、追加BSRAMも0なので、この版を次の比較基準にする。Hold +0.484 ns、Recovery +9.680 ns、Removal +0.551 ns。

次の候補 `window-sta.patch` は、CPU窓書き込みの受付判定を8個の保持FFへ登録し、64 bitごとにRAM入力を選択する。合成で再統合されないよう `syn_preserve` / `syn_keep` を指定する。512 bitのデータ保持段は追加せず、同じcommit edgeを維持する。CSR受付条件、Queue空き、ポインタ範囲を含む判定が従来のbyte_commitと一致することをassertし、QSPI基板トップのPCM2回帰が通過した。

```powershell
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -Output build/pcm-stream-rc1/sta-tx-window
```

窓選択分割版のHoldは+0.539 ns、Recovery +10.133 ns、Removal +0.833 ns。最悪は `held_palette_11_s0`（R13C19[2][B]）から `palette_11_s0`（R8C19[1][B]）への転送。データ配線遅延5.118 ns、全データ遅延5.576 nsで、Setup −0.738 ns。次点のpalette bit 184も+0.018 nsなので、採用基準+0.100 nsには両方の改善が必要。3位はHDMI cxカウンタの+0.132 nsであり、全体の余裕も小さい。

次は、この合成済みネットリストを基準としてpalette bit 11と184の送受信FFの近接配置を小規模に比較する。各候補で全経路のSTAを再評価し、他の違反への移動も確認する。局所配置で収束しない場合は、PRESENTの保持データをpixel側で先に受ける段の追加を検討する。その場合、ACK以前の保持期間、vblankでの反映、pageとpaletteの原子性を検証し、追加FFによるCLS増分も測定する。今回得られた候補は数値ゲート未達であり、実機投入は未実施。

### 残るパレット経路の改善検討

現レポートのclock skewとFF遅延を固定して計算すると、Setup +0.100 nsに必要なデータ配線遅延は4.280 ns以下。bit 11は5.118 nsから0.838 ns以上、bit 184は4.362 nsから0.082 ns以上の短縮が必要。再配置でclock配線も変わるため、これは候補選定の目安であり保証値ではない。

|対象|送信FF|受信FF|現在のSetup|
|---|---|---|---:|
|bit 11|R13C19[2][B]|R8C19[1][B]|−0.738 ns|
|bit 184|R21C18[2][B]|R14C17[0][B]|+0.018 ns|

優先案は既存4 FFの近接配置。追加FF・BSRAMとも0を目標にする。受信側を送信側へ寄せる案、送信側を受信側へ寄せる案、両者を中間へ寄せる案を比較する。送信側を動かすとSYS側のpalette入力経路、受信側を動かすとPIX側の色選択経路が延び得る。候補位置は既存セルの占有とclock/reset/enableの配置制約を確認して決め、現在座標だけから空きサイトを断定しない。bit 11単独、bit 184単独、両方の順に比較し、全体Setup最小値とTNSで採否を決める。

過去のQueue8では局所配置で違反が他のpalette/cursor bitへ移っているため、局所配置での収束には不確実性がある。今回もHDMI cx経路が+0.132 nsと近く、0.032 nsの悪化で採用基準を割る。旧netlistのINS_LOC指定を今回のnetlistへそのまま流用せず、今回のnetlist・CST・SDCをhash固定して比較する。

受信段追加は第2案。pageとpaletteをまとめる場合、少なくとも193 FFと制御が増える。現状の空きCLSは57であり、総FFの空きから収容可否は判断できない。また `held_palette→新受信FF` も同じ10 nsのクロック間制約を受けるため、段追加だけで現在の配線違反が解消するとは限らない。新受信FFを送信側近傍へ置き、以降をpixel内の経路に分けられる場合に評価価値がある。

現行はREQを2段同期した後、vblankでpageとpaletteを同時反映し、そのedgeでACKを返す。受信段を追加するなら、データ取得とrequest世代を対応させ、vblankまでにsnapshotが有効になった場合だけ適用する必要がある。vblank直前のREQで1フレーム遅れる可能性も評価する。初回表示、連続PRESENT、後続PALETTE、reset、ACKとline_pageの一致を試験対象とする。

保持共有化は優先度を下げる。既存の別試作で192 FF削減に対しCLS削減は13、Setup −3.569 nsだった。まず下記の近接配置を評価する。

### 近接配置の実測

窓選択分割版の合成済みネットリストを再利用し、P4/R2で内部FFの配置を比較した。`reroute.ps1` は元のネットリスト・CST・SDCと、追加したCSTのSHA-256を各出力先に保存する。

|条件|Setup / Hold|Setup / Hold違反|CLS|最悪Setup経路|
|---|---:|---:|---:|---|
|配置指定なし|−0.738 / +0.539 ns|1 / 0|4263|palette bit 11|
|受信側寄せ|−0.137 / +0.527 ns|2 / 0|4241|palette bit 89|
|送信側寄せ|−1.935 / +0.533 ns|58 / 0|4279|upload_group_select → window_write_word|
|中間配置|−1.061 / +0.527 ns|3 / 0|4239|palette bit 17。bit 11の受信FFにCT1094|
|受信側寄せ＋bit 77/89/125|−0.539 / +0.527 ns|3 / 0|4262|HDMI data_island_period → first_local|

各案のBSRAMは23/26。受信側寄せの次点はbit 125の−0.077 nsとbit 77の+0.033 ns。追加試験では受信側寄せの4 FFを維持し、この3本も受信側へ寄せた。追加案で最悪のpalette経路はbit 90の+0.415 nsになった。残る違反はHDMIの2経路とPSRAMコントローラのcursor更新1経路で、Recovery +9.616 ns、Removal +0.542 ns。全体Setupは受信側寄せ単独の−0.137 nsが4案中最良で、+0.100 nsの採用基準にはいずれも未達。

パレット転送を基準内にできたため、追加の受信段を入れる優先度は下がった。次の設計評価では、追加案に残ったHDMI `first_local` とPSRAM `cursor` の経路を対象にし、受信側寄せ単独の結果も比較基準として保持する。各試作のSTAレポートと配置条件は `$trial/sta-p4-r2-f23-palette-*` にある。

```powershell
$trial = 'build/pcm-stream-rc1/sta-tx-window'
foreach ($placement in 'near-rx','near-tx','mid','near-rx-followup') {
    ./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement "diagnostics/pcm-stream-rc1/palette-$placement.cst"
}
```

### HDMIとPSRAM制御の経路短縮

パレット5本を近接配置した版では、HDMIの違反経路はデータ配線が10.968 nsで、組合せ遅延は2.181 nsだった。`first_local` を算出する際に5 bitカウンタの加算結果をデコードする処理を、既存の登録済み `first` / `last` からの選択に置き換えた。resetでは1、data island中は前サイクルのlast、それ以外はfirstを選ぶ。更新サイクルは従来と同じ。

PSRAM `cursor` の17 bit加算は、既存のCHECKまたはバースト間隔の間に下位8 bitの桁上がりを登録し、PREPAREで上位9 bitと下位8 bitを別々に更新する。追加状態は1 FF。PREPAREの桁上がりが現在アドレスに対応することをシミュレーションでassertする。コマンド発行サイクルとアドレスは従来どおり。

HDMIの参照実装とのパケット比較は3 seedで通過。PSRAMのマスク付き読み書き、境界分割、リセット回帰も通過した。当初追加したword 508から16 wordの転送は512 word境界であり、今回分割した2048 word境界の桁上がり確認にはなっていなかった。下記の監査後回帰で補完した。Queue8 QSPI基板トップのPCM2回帰も通過した。

```powershell
$trial = 'build/pcm-stream-rc1/sta-short-control'
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -Output $trial
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-near-rx-followup.cst
```

|経路短縮版の配置条件|Setup / Hold|Setup / Hold違反|CLS|最悪Setup経路|
|---|---:|---:|---:|---|
|P4/R2、内部配置指定なし|+0.090 / +0.530 ns|0 / 0|4265|palette bit 181|
|P4/R2、旧palette 5本の近接指定|−1.109 / +0.536 ns|19 / 0|4268|descriptor RAM → FILL終端演算|
|P4/R2、palette bit 181のみ近接指定|−1.971 / +0.498 ns|53 / 0|4273|scanout generation → line_generation|
|P3/R2、内部配置指定なし|−2.766 / +0.523 ns|84 / 0|4250|PSRAM TXロード制御 → データ保持FF|
|P4/R0、内部配置指定なし（監査後追加）|−0.659 / +0.536 ns|2 / 0|4265|HDMI TMDS ctrl2 → tmds|

全案のBSRAMは23/26。最良は内部配置指定なしのP4/R2。Recoveryは+9.601 ns、Removalは+0.830 ns。Setup/Hold違反は0だが、Setup +0.100 nsの数値ゲートには0.010 ns不足した。bit 181だけの配置指定でも全体の配置が変わり、違反が増えた。最良版を比較基準として保持する。実機試験は未実施。

監査後のP4/R0も同一ネットリスト・CST・SDCをhash固定して比較したが不採用。Recovery +8.230 ns、Removal +0.827 ns。証跡は `build/pcm-stream-rc1/sta-short-control/sta-p4-r0-f23/`。再現コマンドは `./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial build/pcm-stream-rc1/sta-short-control -Route 0`。

### 配線設定と単一FF配置の追加比較

最良版の余裕が少ない上位はpalette bit181 +0.090 ns、bit5 +0.177 ns、HDMI TMDS +0.272 ns、palette bit37 +0.316 ns。最良版の同一ネットリストを使い、SDCは変更せず追加比較した。

|条件|Setup / Hold|違反端点 Setup / Hold|判断|
|---|---:|---:|---|
|P4/R2、MaxFan 24|+0.090 / +0.530 ns|0 / 0|改善なし。Recovery +9.601、Removal +0.830 ns|
|P4/R2、MaxFan 22|未取得|未取得|10分超で停止。最終ログはRouting Phase 1完了。run-status.jsonに停止記録|
|P4/R1、MaxFan 23|未取得|未取得|10分超で停止。最終ログはRouting Phase 1完了。run-status.jsonに停止記録|
|P4/R2、bit181送信FFのみ1行移動|−2.901 / +0.508 ns|97 / 0|不採用。最悪はdisplay generation加算|

送信FFのみの試験は `palette-181-source-step.cst` でR26C22[0][B]からR25C22[0][B]へ寄せ、受信側は指定しない。小さな配置指定でも全体配置が変わり、以前の送受信固定案と同様に悪化した。Recovery +8.339、Removal +0.533 ns。この指定を標準ビルドには組み込まない。

MaxFan 24はCLS 4265、送信FF移動案はCLS 4284で、両方BSRAM 23。最良版は引き続きMaxFan 23のP4/R2（CLS 4265、Setup +0.090 ns）。4候補の追加比較では数値ゲート達成に至らなかった。次段階は、局所INS_LOCの追加より、PRESENT mailboxの受信段追加を設計変更として評価する。REQ同期後のデータ安定、vblankでのpage/palette同時反映、ACK前の保持、直前REQの扱いを試験で保証し、追加FFのCLS収容性も合成で判断する。現在の空き55 CLSに収まるとは事前に断定しない。

```powershell
$trial = 'build/pcm-stream-rc1/sta-short-control'
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -MaxFan 24
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -MaxFan 22
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -Route 1
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-181-source-step.cst
```

今回はRTL変更がないため機能回帰の再実行は行っていない。監査後の全11実行が対象としたRTLと同じネットリストを使用している。これらの配置配線試行を、実機動作の検証とは扱わない。

```powershell
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-181-near-rx.cst
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -Place 3
```

### PRESENT受信段の試作

`-PresentRxStage` は、システム側がACKまで保持するpageとpaletteの193 bitをピクセル側で毎サイクル受ける。2段同期後のREQをvblankで消費する際、同じ受信値で表示ページ、パレット、先頭行取得先を更新する。既存のREQとACKの更新条件を使うため、同期済みREQを最初に使えるvblankで反映する。最初のREQサンプルから次のピクセルエッジまでにデータが受信FFへ到着することが成立条件であり、既存SDCの10 ns境界を維持してSTAで確認する。

```powershell
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -PresentRxStage -Output build/pcm-stream-rc1/sta-present-rx-new
```

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --present-rx-stage --output build/pcm-stream-rc1/present-rx-regression-new
```

Verilatorで全13実行が成功。専用試験で最初の反映可能エッジ、入力変更後の保持、ページとパレットの同時更新、先頭行取得先、連続要求、保留中リセットを確認した。スキャンアウト試験では1,843,200画素を比較し、欠落行は0。回帰と合成の入力41ファイルは改行差を除いて一致した。試験証跡は `build/pcm-stream-rc1/present-rx-regression-v2/`。

P4/R2で配置配線は完了したが、Setup −3.021 ns、Hold +0.456 ns、Setup/Hold違反端点28/0で不採用。Recovery +6.509 ns、Removal +0.830 ns。CLSは4281/4320（最良版比+16）、BSRAMは23/26。最悪経路は `held_palette_190_s0/Q` → `present_rx_190_s0/D` で、元のクロック間経路が新しい受信FFまでの区間に残った。FILL終端演算やHDMI TMDSにも違反が出た。SDCのSHA-256はRC1と一致する。レポートは `build/pcm-stream-rc1/sta-present-rx-v3/native/` に保存した。

### 色単位の領域配置とFILL終端加算

最良版の合成済みネットリストで、色15（bits 180–191）の送受信FF計24個に対し、座標範囲を指定した。範囲内のサイト選択はツールに任せる。広い領域はR17–25/C20–26、狭い領域はR18–23/C22–26。Gowinは両CSTを受理し、制約エラーを報告しなかった。通常のSTAレポートで全24 FFの配置座標までは照合していない。[Gowinの物理制約構文](https://www.gowinsemi.com/upload/database_doc/2/document/5bfcfd099cf5f.pdf)

`-FillEndAdder` はFILL/COPYで使う終端の丸めを、座標と幅の上位部の加算に桁上がりとして組み込む。端数ビットがどちらか1なら繰り上げる。新旧の格納値は下位10 bitの全1,048,576組で一致した。既存の範囲検査、FSM、メモリ発行サイクルを維持する。FILL画素照合、COPY 1,150ケース、基板トップ、PCMを含む全13回帰に成功し、回帰と合成の入力41ファイルは改行差を除き一致した。

|P4/R2条件|Setup / Hold|違反端点 Setup / Hold|CLS|最悪Setup経路|
|---|---:|---:|---:|---|
|最良版|+0.090 / +0.530 ns|0 / 0|4265|palette bit 181|
|色15、広い領域|−0.652 / +0.527 ns|5 / 0|4261|表示世代カウンタ|
|色15、狭い領域|−4.521 / +0.527 ns|153 / 0|4245|アップロード窓グループ選択|
|FILL終端加算のみ|+0.066 / +0.433 ns|0 / 0|4274|HDMI TMDS|

全案ともBSRAMは23/26、SDCはRC1と同じ。広い領域では最悪のパレット経路がbit 175の+0.308 nsまで改善したが、世代カウンタとFILLチャンク長に違反が移った。FILL終端加算版のRecoveryは+8.405 ns、Removalは+0.824 ns。全案がSetup +0.100 ns基準に未達で、最良版を比較基準として保持する。

```powershell
$trial = 'build/pcm-stream-rc1/sta-short-control'
foreach ($region in 'wide','compact') {
    ./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement "diagnostics/pcm-stream-rc1/palette-color15-$region.cst"
}
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -FillEndAdder -Output build/pcm-stream-rc1/sta-fill-end
```

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --fill-end-adder --output build/pcm-stream-rc1/fill-end-regression
```

再実行時は新しい出力先を指定する。STA証跡は最良版出力下の `sta-p4-r2-f23-palette-color15-*` と `sta-fill-end/native/`、回帰証跡は `fill-end-regression/` に保存した。

### 表示世代カウンタの桁上がり先行計算

広い領域案で最悪だった16 bit世代加算を対象にした。上下8 bitに分け、上位へ渡す桁上がりを1 FFで先に計算する。通常サイクルでは下位が0xff、vblankで増分するサイクルでは下位が0xfeのときに次サイクル用の桁上がりを立てる。これによりvblankが連続する入力でも桁上がりが一致する。表示と先頭行要求は同じ次世代値を使う。

```powershell
$trial = 'build/pcm-stream-rc1/sta-generation'
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -GenerationCarry -Output $trial
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-color15-wide.cst
```

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --generation-carry --output build/pcm-stream-rc1/generation-regression-v2
```

全13回帰が成功。専用試験は下位8 bitの桁上がり、16 bitの周回、vblank連続・間欠入力、先頭行の世代一致を確認した。スキャンアウトは1,843,200画素を欠落行ゼロで照合。回帰と合成の入力41ファイルは改行差を除き一致し、SDCのSHA-256はRC1と一致した。再実行時は新しい出力先を指定する。

|P4/R2条件|Setup / Hold|違反端点 Setup / Hold|CLS|最悪Setup経路|
|---|---:|---:|---:|---|
|広い領域、世代加算変更前|−0.652 / +0.527 ns|5 / 0|4261|表示世代カウンタ|
|世代加算変更、領域指定なし|−1.345 / +0.539 ns|6 / 0|4269|palette bit 51|
|世代加算変更、広い領域|−0.322 / +0.539 ns|2 / 0|4270|アップロードRAM→窓書込みワード|

全案BSRAMは23/26。広い領域案はSetupを0.330 ns改善し、以前の世代カウンタ違反を解消した。残る違反はアップロードRAM→窓書込みワードと、descriptor RAM→COPY範囲判定（−0.068 ns）。次点はpalette bit 154（+0.023 ns）。制約対象bit 182の送受信座標はR17C20とR17C21で、指定範囲内だった。領域指定なしの最良版+0.090 nsを比較基準として保持する。STA証跡は `sta-generation/native/` と `sta-generation/sta-p4-r2-f23-palette-color15-wide/`。

### アップロード窓のバイト合成をコミット側へ移動

`-WindowCommitMerge` は、CSRの読み出しに使っている64 bitグループ保持FFを窓書き込みでも共用する。CSR受付時に選択済みグループ、書き込みバイト、アドレスを保持し、既存のコミットエッジで対象バイトを合成してRAMへ書く。32 bitの合成済みワード保持を8 bitのバイト保持に置き換えるため、RTLの保持量は24 bit減る。アドレス増分後も、合成のレーン選択には受付時に保持したアドレスを使う。CPU応答、RAM書き込み、ポートのリカバリー順序は既存どおり。

```powershell
$trial = 'build/pcm-stream-rc1/sta-window-merge'
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -GenerationCarry -WindowCommitMerge -Output $trial
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-color15-wide.cst
```

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --generation-carry --window-commit-merge --output build/pcm-stream-rc1/window-merge-regression
```

全14回帰が成功。窓の参照実装と各サイクルの応答、アップロードデータ、READ 6回、COPY取り込み18回、ウォームリセットを照合した。Gowin V1.9.12.04のSPモデルでも窓照合が成功。回帰と合成の入力41ファイルは改行差を除いて一致し、SDCはRC1と同じSHA-256。回帰証跡は `build/pcm-stream-rc1/window-merge-regression/`（SP試験は `vendor-window.sh` と `vendor-window-1.log`）。再実行時は新しい出力先を指定する。

|P4/R2条件|Setup / Hold|違反端点 Setup / Hold|CLS|最悪Setup経路|
|---|---:|---:|---:|---|
|広い領域、窓変更前|−0.322 / +0.539 ns|2 / 0|4270|アップロードRAM→窓書込みワード|
|窓変更、領域指定なし|−0.305 / +0.533 ns|3 / 0|4271|palette bit 138|
|窓変更、広い領域|−0.312 / +0.527 ns|3 / 0|4238|FILL終端加算|

広い領域の同条件でCLSが32減り、空きは50から82へ増えた。BSRAMは全案23/26。窓の違反は解消した。広い領域案の残る違反はFILL終端加算2本（各−0.312 ns）とpalette bit 26（−0.220 ns）。Recovery +10.483 ns、Removal +0.539 ns。Setup +0.100 nsには未達。領域指定なしの従来最良版+0.090 nsをタイミング比較基準とし、この版は低CLSの設計候補として保存する。STA証跡は `sta-window-merge/native/` と `sta-window-merge/sta-p4-r2-f23-palette-color15-wide/`。

### 窓のコミット側合成とFILL終端加算の組合せ

広い領域で残ったFILL終端の2違反を対象に、`-GenerationCarry -WindowCommitMerge` に `-FillEndAdder` を追加した。同じ合成済みネットリストを領域指定あり・なしのP4/R2で比較する。

```powershell
$trial = 'build/pcm-stream-rc1/sta-window-fill'
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -GenerationCarry -WindowCommitMerge -FillEndAdder -Output $trial
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-color15-wide.cst
```

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --generation-carry --window-commit-merge --fill-end-adder --output build/pcm-stream-rc1/window-fill-regression
```

窓のサイクル照合、FILL、COPY 1,150ケース、スキャンアウト、基板トップ、PCMを含む全16回帰が成功した。回帰と合成の入力41ファイルは改行差を除き一致。再実行時は新しい出力先を指定する。

|P4/R2条件|Setup / Hold|違反端点 Setup / Hold|CLS|最悪Setup経路|
|---|---:|---:|---:|---|
|広い領域、FILL変更前|−0.312 / +0.527 ns|3 / 0|4238|FILL終端加算|
|組合せ、領域指定なし|−1.074 / +0.420 ns|4 / 0|4263|ラインバンクのタグ転送|
|組合せ、広い領域|−0.549 / +0.539 ns|1 / 0|4272|palette bit 81|
|組合せ、広い領域＋bit 81|−1.711 / +0.539 ns|5 / 0|4271|palette bit 167|

全案BSRAMは23/26。広い領域でFILL終端のワーストは+0.716 nsとなり、変更前にあったFILLの2違反は解消した。bit 81以外のSetupは+0.464 ns以上。bit 81の送信FFはR23C15、受信FFはR23C20で、データ配線遅延は4.929 nsだった。そこで元の色15指定に加え、bit 81の送受信FFをR22–24/C17–19の範囲へ収める候補を比較した。ネットリストとSDCのハッシュは一致し、Gowinは制約エラーを報告しなかった。bit 81は違反一覧から外れたが、別のパレットbitとメモリ範囲判定に計5違反が発生した。追加指定は不採用。全体のタイミング比較基準は従来の+0.090 ns、低CLS候補は4238 CLSの窓変更版を保持する。

```powershell
./diagnostics/pcm-stream-rc1/reroute.ps1 -SourceTrial $trial -PalettePlacement diagnostics/pcm-stream-rc1/palette-color15-wide-bit81.cst
```

### P2/R2比較とパレットRAMの単体合成

P4/R2の3候補から合成済みネットリストを再利用し、配置方式だけをP2へ変更した。元のCST、SDCと同じ条件で比較した。いずれもGowinのPR0004で終了し、完了時のSTAは取得できなかった。

|入力|内部配置指定|P2/R2未配線ネット|
|---|---|---:|
|最良版 `sta-short-control`|なし|318|
|省資源版 `sta-window-merge`|色15の広い領域|204|
|FILL改善版 `sta-window-fill`|色15の広い領域|120|

各入力の `sta-p2-r2-f23*` にコマンド、入力ハッシュ、ログを保存した。RTLの変更はなく、各入力に対する既存の機能回帰を使用した。タイミング最良版はP4/R2の+0.090 ns、低CLS候補は4238 CLS。

パレットのクロック間データ経路を減らす構造案として、既存 `kagura_ram_tdp` を32語×12 bit（16色×2面）、system側書き込み、pixel側同期読み出しで単体合成した。既定の推論はRAM16SDP4が6個。メモリ宣言に `syn_ramstyle="block_ram"` を指定すると、Gowin V1.9.12.04はSDPBを1個推論した。試作ソースとログは `build/pcm-stream-rc1/palette-ram-inference/` にある。単体合成であり、統合時のCLS削減量とSTAは未測定。

統合案では受け付けたパレットを非表示面に16語書き終えてからREQを公開する。pixel側はvblankでページとパレット面を同時に切り替え、ACKまで旧面を上書きしない。既存の色選択登録段を同期RAM読み出しに置き換えると、画素パイプラインの段数を揃えられる。16語のロード期間によりvblank直前の要求が次フレームへ遅れる可能性があり、ACKのタイミング、先頭行の取得先、reset中の表示、RAMの同一アドレス衝突を統合前に検証する。追加のBSRAM予算は1個（単体結果どおりなら合計24/26）。

### 2面パレットBSRAMの統合試作

`-PaletteRam` はPRESENT受付時に保持した16色を、表示中と反対のRAM面へ1語ずつ書く。16語目を書いた後にREQを公開する。pixel側はvblankでページとRAM面を同時に切り替え、その時点でACKする。旧面の再使用はACKの同期後。画素経路では色選択登録段を同期RAM読出しへ置き換えた。REQの公開が16 systemサイクル遅れるため、vblank直前に受付したPRESENTは次のフレームに回る場合がある。

```powershell
./diagnostics/pcm-stream-rc1/build.ps1 -RegisterTxControl -LocalWindowSelect -ShortControlPaths -PaletteRam -Output build/pcm-stream-rc1/sta-palette-ram
```

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --palette-ram --output build/pcm-stream-rc1/palette-ram-regression
```

全13回帰が成功。表示面への書込み衝突、ページとパレットの同時反映、先頭行、ロード中のreset、1,843,200画素の照合を確認した。合成と回帰の入力41ファイルは改行差を除き一致。P4/R2はCLS 4253/4320、BSRAM 24/26。従来最良版比で12 CLS減、BSRAM 1増。Setup −1.407 ns、Hold +0.385 ns、違反28/0、Recovery +10.014 ns、Removal +0.843 ns。最悪はdescriptor RAMからCOPY範囲判定へ移った。数値ゲート不合格のため、この画像の採用は見送った。STAは `sta-palette-ram/native/` に保存。

ユーザー指定の+0.090 ns版の試験前照合は [実機試験前監査](fallback-audit.md) を参照。

## 試作CSR

既存の音声INDEX/DATAを使う。ABI 1.4に試作識別子を追加したローカル契約。

|Index|Read|Write|
|---|---|---|
|E3|試作識別 `0x51`|`1`で停止中の両chをarm、`0`でストリーム停止|
|E4|現在の公開token。bit0が半面|同じtokenを公開。返却済み半面だけ受理|
|E5|bit0 現半面補充可、bit1 armed、bit2 読出し応答待ち|予約|

左右別々の重複しない領域を使い、各STARTを8192 byte境界に置く。ENDはSTART+8192、LOOPはSTART。両半面をアップロードしてWRITE成功とFENCEを確認した後、armする。両chへPREPAREを発行してから双方のREADYを待ち、両chを同じAUDIO_COMMITで開始する。補充はE5 bit0とE4で確認した半面に行う。左右の全WRITE成功後にE4へtokenを返し、E4が進んだことを確認する。

E4は8 bitで、A/Bを含め256回の公開で周回する。Hostは単一呼出し元で操作を直列化し、読んだtokenはその補充の一回だけ使う。再送、周回を越えるtoken保持、リセット前のtoken再利用は禁止。停止または通信エラー後は古いGPU WRITEを回収してから再初期化する。停止後はE5 bit1とbit2が両方落ちてからPSRAM領域を再使用する。補充が間に合わず片側のFIFOが空になると両chが停止する。

[host.py](host.py) は既存MicroPython `Audio` / `Device` を使う呼出し例。左右別々のraw PCMファイルを `StereoStream(audio, left, right)` に渡し、`start()` の後、描画投入前に `refill()` を繰り返す。EOFまたは例外では `stop()` で終了する。64 byteの作業バッファを使う同期転送の例で、実機の補充期限は測定が必要。Queue8の完了回収を並列化したホストは今後の性能評価対象。

## シミュレーション

### 監査後の一括回帰

WSL/Linux、Python 3、Git、VerilatorとC++ビルド環境で、次を実行する。出力先は新規ディレクトリを指定する。

```sh
python3 diagnostics/pcm-stream-rc1/regress.py --output build/pcm-stream-rc1/regression-new
```

RC1の保存済み入力hashを検査し、出力先へコピーしてstream/TX/window/controlの全パッチを適用する。Windows由来の改行差はgit applyのignore-space-changeで吸収する。合成や実機操作は行わない。試験入力hash、Verilatorバージョン、実行コマンド、ログ、完了時のresult.jsonを保存し、実行中の入力変更も検出する。失敗時は非ゼロで終了し、成功のresult.jsonは作らない。

`tb_burst_carry.sv` は32 KiBのモデルで2048/4096/6144 word境界を対象に、各境界の4 word前と1 word前から16 wordをマスク付きで読み書きする。carry後に小さいアドレスへ別要求も発行する。PREPAREでcarry=1の読出し・書込み回数と3境界の到達をチェックする。HDMI・基板トップのfixtureもdiagnostics内に保存した。共通メモリモデル、serializer stub、hdl-util参照実装はリポジトリから読み、hashに含める。

2026-11-07、Verilator 5.032で全11実行が成功した。

- バーストseed 1/19/73: 各carry=1読出し6回、書込み6回、境界mask=111。最大read 106 cycles。
- HDMI REPLICATE_FIRST=0/1 × seed 1/19/73: 参照実装との比較成功。
- PCMストリーム: サンプル列、半面再使用、古いtoken、補充不足、停止・再開成功。
- Queue8 QSPI基板トップ: PCM2回帰成功。

保存証跡: `build/pcm-stream-rc1/audit-regression/run-1/`。一時領域で成功した初回のログ回収時に出力消失があったため、リポジトリ内へ直接保存して全11実行を再実行した。再構築した入力41ファイルは、最良STA版 `sta-short-control/inputs` とCRLF/LF差を除いて全件一致し、`sta-input-comparison.json` に記録した。RTL変更はなく、今回の試験追加によるFPGA資源増分はない。

Verilator 5.032。パッチ適用済みの `inputs` を作業ディレクトリとして実行する。テストファイルのパスはリポジトリの絶対パスを指定する。

```sh
verilator --binary --assert --timing --timescale 1ns/1ps -Wno-fatal \
  --top-module tb_stream -j 4 rtl/audio/kagura_pcm_prefetch.sv \
  "$REPO/diagnostics/pcm-stream-rc1/tb_stream.sv"
obj_dir/Vtb_stream
```

テストは2周の左右サンプル照合、古いtoken、重複公開、補充不足での両ch停止、未応答を残したSTOPと再開を検証する。既存 `tb_fb_board_qspi.sv` もQueue8の設定で実行し、従来PCM2の回帰を確認した。

## その後（2026-11-08〜09）

設計監査、診断ビルドT8、G1正式認定、bitstreamの固定を経て、T8画像を選定版へ昇格しました。経緯は[設計監査報告書](design-audit-report.md)の第14〜21節、配布パッケージは[releases/pcm-stream-qspi](../../releases/pcm-stream-qspi/README.md)にあります。
