> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 最小音声ブリッジ：Standard合成資源評価（2026-11-05）

> 後続の[配置評価](audio-minimal-pnr-result-2026-11-05.md)はPR0003で不合格となった。本稿の「配置未評価」は合成完了時点の記録。

最小案はGowin Standard V1.9.12.04の**合成のみ完了、エラー0**。FF 6309、LUT 7593、ALU 892、BSRAM 19。通常Snapshot案03からendpoint管理のFFを81→18へ削減できたが、全体のLogic削減は11にとどまる。**配置・配線・Standard STAは未評価**であり、収容可能とはまだ判断しない。`release_ready=false`。

## 評価条件・範囲

- 対象: GW1NR-LV9QN88PC6/I5（GW1NR-9C）、QSPI 4lane、54MHz system / 74.25MHz pixel。clock/IO制約・Controller/PHY・音源演算/PCMは既存候補のまま。
- 入力: PC全検証PASSの`build/audio-minimal-bridge`から40入力を固定。`build/standard-minimal-syn-01/inputs/`とsource-input-manifest.jsonを保存。
- 既存build-fb.tclを固定コピーし、最後の`run all`だけを`run syn`へ置き換えた専用adapterで実行。元script・RTLは変更していない。
- 実行ファイル: `C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe`。合成HTMLにV1.9.12.04 (64-bit)を確認。process exit=0、GowinSynthesis finishあり。
- 評価directory: `build/audio-minimal-bridge/build/standard-minimal-syn-01`。pnr directoryと.fsは存在しない。実機・Flash/FW・Merge・Push・Release操作なし。

## 実測比較

|保存済み構成|FF|LUT|ALU|SSRAM/RAM16|BSRAM|Logic換算|
|---|---:|---:|---:|---:|---:|---:|
|STA合格RMW基点|4932|6457|703|16|19|7256|
|03 通常Snapshot＋専用endpoint|6372|7589|907|16|19|8592|
|05 locked Snapshot＋専用endpoint|6053|7646|907|16|19|8649|
|今回：通常Snapshot＋最小ブリッジ|6309|7593|892|16|19|8581|

FF/LUT/ALU等は階層合成XMLの総数。今回のLogic 8581は合成HTMLの直接記載値であり、単なるLUT＋ALU＋SSRAM個数ではない。上記ではRAM16が1個当たり6のLogicに相当し、`7593+892+16×6=8581`。比較欄のLogicは同じ換算で算出した。配置後CLSとは異なる。

**今回の合成レポート:** Logic 8581/8640＝99.317%、残り59。Register 6309/6771＝93.177%、残り462。パーセントは計算値であり、HTMLの丸め表示はそれぞれ100%/94%。この残量からpacking・配置・配線・STAの成功を推定しない。05の合成Logicが8640を超えていることと、既存の配置段階まで進んだ結果も区別する。合成、実装前処理、配置の資源判定は同じものではない。

## 重複削除の効果

|階層|03 FF|今回FF|03 LUT|今回LUT|
|---|---:|---:|---:|---:|
|audio endpoint全体|982|919|821|720|
|うち既存audio_registers|901|901|676|688|
|うちbridge管理部分|81|18|145|32|
|Host全体|880|880|2131|2188|
|core全体|4440|4440|4363|4408|

**観測:** 管理部分は63 FF、113 LUT、15 ALU減った。通常Snapshotの901 FFは維持している。全体ではFF −63、LUT +4、ALU −15、Logic −11となった。endpoint以外のLUT差が削減を相殺しているため、局所の削減を全体削減として報告できない。core演算RTLのhashは不変であり、階層別LUTの増加を新しい音源機能の追加量とは扱わない。合成の最適化・マッピング文脈を含む差で、その個々の要因は未分離。

**計算:** 基点からのFF増分1377＝既存registers 901＋bridge 18＋Host増14＋core増444。以前の約6.3k FFという予測範囲内で、FFの内訳を実測で確認できた。一方、Logicに大きな余裕を作れるとの根拠は得られていない。

05からはFF +256、LUT −53、ALU −15、Logic −68。これはBUSY中shadow編集可能という元の契約を復元した結果を含む。05よりFFが増えたことを失敗として隠さず、互換性のために保持した状態と、削除した管理状態を分ける。

## 警告・品質上の限界

警告12件: EX2478×4（既存HDMI宣言時初期値）、EX3073×2（PLL未接続出力）、EX3780×2（既存packet定数）、NL0002×4（packet instance最適化除去）。03にも同じcode/countがあり、今回の新規警告codeはない。全警告原文を保存した。これは警告一般を無害と保証するものではなく、今回の差分として新たな警告種別がないという比較結果。

合成レポート内の推定タイミングをStandard STAのSetup/Holdとして採用していない。Setup/Hold slack、配線完了、PSRAM外部I/O timing、HDMI実キャプチャ、PVTは未確認。PC全回帰のPASSは[PC評価報告](audio-minimal-bridge-implementation-2026-11-05.md)の範囲に限る。

## 次の判断

現時点でBSRAM化が必要とは断定しない。次はツールの段階停止方法を確認した上で、**今回と同じ固定RTL・同じ制約・同じPlace1/Route2を使い、Bitstreamを生成しない配置評価を1回行う**のが妥当。未配置LUT/REG、packing、配置資源を測り、成功した場合に配線・Standard STAの評価範囲を定める。無関係なP&R条件探索、機能削除、snapshot契約変更、clock/PHY変更はしない。

今回の作業は合成資源測定で終了しており、配置評価はまだ実行していない。元STA候補のSetup/Hold値をこの候補へ転記しない。

## 来歴・保護・成果物

固定40入力はPC候補・固定コピー・manifestのhashが一致。停止した旧audio/RAM作業コピーとRMW基点の保存manifestも全件不変を確認した。元fsは以下と一致。

- RMW: `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`
- RX32: `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`

[機械可読の資源・入力hash・警告・保護結果](evidence/audio-minimal-synthesis-2026-11-05.json)、[合成rawログ・資源HTML/XML・実行adapter・入力manifest](evidence/audio-minimal-synthesis-raw-2026-11-05.zip)を保存した。freeze-audio-minimal-synthesis.pyとsummarize-audio-minimal-synthesis.pyで固定と集計を再現できる。既存評価directoryの上書きは拒否する。
