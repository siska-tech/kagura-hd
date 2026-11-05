> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD scanout RX32：第1段階の機能評価

追記：本書は合成前の機能評価記録。後続のStandard 1回で数値STAゲートを通過した。最新結果は [Standard評価結果](rx32-scanout-standard-result-2026-11-04.md) を参照。実機検証は未実施。

評価branch：`eval/rx32-scanout-01`。独立worktree：`build/rx32-scanout-worktree`。

**評価範囲：32B分割＋音声Phase 1を維持し、scanoutの512bit受信bufferだけを32bit直接書込みへ変更する。新規合成・P&R・STA・実機操作は実施していない。** 元の作業ツリー、既存の不採用ビルド、SDC/CSTは変更していない。commit/Push/Merge/Releaseも行っていない。

## 変更と仮説

旧フローは `PHY pair → controller RX512 → done → fetch buffer512 → 16cycle drain → line RAM`。

新フローは `PHY pair → 16bit前半保持 → 32bit word tap → 非表示line RAM`。controller RX512はhost/BLIT/PCM用に維持する。arbiterは受信wordをscanout ownerにだけ渡し、controller FSM/PSRAM出力信号/既存doneは変更しない。

line fetchは16words×5要求の完了を確認し、正常な最終rsp_done後だけbank公開を許す。word欠落・余剰・memory error・resetは完了/所有権を取り違えない。word tapは転送中に停止できず、開始前のline RAM所有権・容量確保を前提とする。次要求は旧DRAINを待たず発行するため、競合順やfetch完了cycleは変わり得る。

RTL保持bitの差は**−460bit**（buffer−512、count/overflow＋2、tap＋50）の算術見積り。合成FF/CLS/LUT削減の実測ではない。追加BSRAMの記述はなく、PHY/外部timingには手を加えていない。

## 検証結果

**機能評価PASS。** Verilator 5.032、seed1。各runnerはexit0で完了した。物理評価は未実施。

|検証|結果/観測|
|---|---|
|新規word tap対照比較|381ケース、34,024edgeで既存出力・PSRAM出力信号・完了一致。2,124wordをbyte oracle照合。109位相のreset sweepを含む|
|新規fetch契約|776シナリオPASS。全720行/page、gap、最終word/done同時・遅延、short/overrun、error/reset/recovery|
|既存FB回帰|26/26 PASS|
|共通部品回帰|22/22 PASS（HDMI VIC1/VIC4を含む）|
|32B wrap controller|既存272/272 PASS、direct READ最大106cycle|
|32B wrap統合|12/12 PASS（同じ独立wrapモデルでBLIT/scanout/core/host/boardを検証）|
|driver / QSPI pin oracle|15/15＋4/4 PASS。デバイス接続なし|
|line fetch飽和|同じ既存TBで最大659→643cycle、期限1920を維持|
|単独arbiter競合|line612cycle、PCM186cycle。対照と同じ|
|host BLIT競合|SPI line最大813、QSPI817cycle。両方1920以内、PCM進捗あり|
|全画面FILL/BLIT（孤立）|130200 / 289809cycle、対照と同じ|
|core HDMI/audio|1843200 RGB＋1843200 TMDS画素、2387復号stereo samples、49 ACR。PCM2＋合成6ch同時動作PASS|
|scanout|1843200画素/試験、page/palette atomic flip、正常系とunderrun系PASS|
|board top|両FB page/PCM初期化、音声開始、SPI identityと表示PASS|

16cycle短縮を80cycle短縮や実機性能向上へ外挿しない。request発行の早期化による仲裁位相の変化を含む。この有限刺激比較は全状態形式証明やPSRAM pad timing保証ではない。

## 入力保護・証跡

評価worktreeの `build/analysis/` に以下を保存した。

- `phase1-base-manifest.json`：引継ぎ元ファイルのhash。HEADが同じでも未コミット差分が異なることを明示。
- `rx32-source-manifest.json`：評価RTL・PHY・SDC・top・referenceのhash。
- `full-input-hashes.json`：RTL/試験/board制約/runnerのhash一覧。
- `unchanged-boundaries.json`：音声Phase 1、PHY、SDC、topの引継ぎ元とのhash一致。
- `controller-scope-proof.json`：tap追加部分を取り除いたcontroller本文が対照と一致する検査。FSM無変更の根拠。合成/形式証明ではない。
- `cst-unchanged.json`：board CSTの引継ぎ元とのhash一致。
- `rx32-only.patch`：Phase 1対照に対するRX32だけの5 RTL差分。分割/音声の引継ぎ差分と分離。
- `test-rx32-reset-sweep.log`：新規2TBの最終結果。
- `test-fb-verilator.log`、`test-common-verilator.log`、`test-fb-wrap32.log`、`test-fb-wrap32-integration.log`、`test-fb-drivers.log`：回帰ログ。
- `functional-status.json`：機能段階PASS、STA/資源/実機未評価を分離した機械可読の結果。

個々のbuild/run logは評価worktreeの `build/{rx32-verilator,fb-verilator,common-verilator,fb-wrap32-integration}/`。実装・再実行方法は同worktreeの `docs/rx32-scanout-evaluation.md`。新候補に `DO_NOT_PROGRAM.txt` を置いた。

## 次の判定

この段階で確かめたのは機能・データ順・旧controller境界の維持である。**資源改善仮説とSTA収束は未判定**。既知のpalette CDC、system側TX/CSR違反、外部PSRAM I/O未保証、元64Bの追加16B/46bit破損は解決済みとしない。今回の物理比較対照はPhase 1（既存setup −1.321ns、16違反、CLS4217、FF5370）である。Phase 2のpalette9＋system5という分布を、未実行の新候補の違反数として転記しない。

次は同じ入力を固定してStandard V1.9.12.04、GW1NR-LV9QN88PC6/I5、同SDC/CST、Place1/Route2で1回の独立評価を行い、buffer除去・追加tap・全資源・全配線・全clock STAを測る段階。setup≥+0.100ns、setup/hold違反0、全配線完了の品質ゲートを維持する。

機能/期限違反、buffer除去不成立、追加保持で利益消失、未配線、説明可能な改善を伴わないSTA悪化なら、この差分を不採用として停止する。global gate不合格でも限定的な資源改善が実測されれば、製品採用とは分けて次の判断材料にする。paletteやTXを同時に変更して結果を混ぜない。
