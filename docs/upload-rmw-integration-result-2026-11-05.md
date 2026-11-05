> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# Upload window共有RMWの本体統合評価（2026-11-05）

追記：後続の[限定実機試験](upload-rmw-hardware-result-2026-11-05.md)ではupload5件とPSRAM4Bの17比較が一致し、KAGURA-9復旧確認まで完了した。以下の「未書込み」はこのPC統合評価時点の記録。外部I/O signoffとReleaseは依然未達。

## 結論と評価範囲

独立診断で観測したupload windowの破損に対し、native byte enableを使わず全32bitを書き込む修正を、別branch `fix/upload-word-rmw-01` / `build/upload-rmw-worktree` に統合した。32bit完成word保持案はStandard Setup +0.717ns / Hold +0.407ns、違反0/0、全配線を達成し、FB全26回帰もPASSした。元のRX32候補は変更していない。これはHost/CSR境界の修正候補であり、実PSRAM READ/WRITEの正当性を保証する結果ではない。`release_ready=false`を維持し、本体候補は実機未書込み。

前段の実機証拠は[境界観測](host-window-boundary-result-2026-11-05.md)と[独立RMW診断](host-window-rmw-result-2026-11-05.md)を参照。transport RXとCSR受理が正しく、その後のSP出力で不一致を観測し、FFおよび全word RMWの独立診断で同一4BがPASSした。native byte enable依存を回避する根拠になるが、実ダイ仕様・物理的な破損機構の確定とは区別する。32B wrapと追加破損は独立した未解決問題。

## 来歴と保護

基点はHEAD `1d46c6db71eb48e486a8e038d41e5a44342fe699`に、評価時の未commit変更を含めたRX32 worktree。HEADだけでは再現できないため279ファイルの継承manifestと、Standardの38入力の固定snapshotを保存した。

- 証跡: `build/upload-rmw-worktree/build/analysis/inherited-source-manifest.json`
- 固定入力: `build/upload-rmw-worktree/build/standard-shared-rmw/inputs/`
- 現候補の固定入力: `build/upload-rmw-worktree/build/standard-latched-rmw/inputs/`
- 監査: `tools/audit-upload-rmw-integration.py` → `build/analysis/upload-rmw-provenance.json`
- 評価済みソースに対する修正だけの差分: `build/analysis/upload-rmw-only.patch`

監査では279継承ファイルのうち変更は2 RTLと新worktreeのDO_NOT_PROGRAMのみ、固定38入力と現在ソースの一致、元279ファイルの不変を確認した。元bitstream SHA-256は `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`、元DO_NOT_PROGRAMは `d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546` のまま。

## RTL変更

`rtl/fb/kagura_fb_registers.sv`で、対象byteだけ置換するmergeを1か所に共有し、各SPにはbyte_enable=1111を渡す。16個のSP、512bit並列uploadインターフェース、応答周期、busyと回復周期を維持する。最初の共有案は既存64bit window_groupに古い値を保持した。後述のSTA不合格を受け、現候補ではCSR受理時に完成した32bitを書込み専用レジスタへ保持し、既存commit周期で対象SPに書く構成へ変更した。8bit write_dataを32bitへ置換するため、論理上の増分は24bit。read用window_groupの用途は元に戻した。

`rtl/fb/kagura_fb_upload_word.sv`では書込みデータを明示的にmergeし、SP AD[3:0]を常時1111にする。本体接続ではmergeが合成で消え、全word入力となる。behavioralモデルも同じ読出し保持・全word書込み契約にした。部分書込みを単独使用する場合は古いrdataが確定した読出し周期が必要。

Controller、PHY、32B分割、RX32、HDMI、音声、BLIT、cursor、palette、clock、SDC/CSTは継承元と同一。機能削除やP&R設定変更は行っていない。

## PC検証

Verilator 5.032 / seed 1で以下を確認した。実行ログは新worktreeの`build/analysis/`に保存。

|検証|結果|ログ|
|---|---|---|
|共通component|22/22 PASS|rmw-common-regression.log|
|FB全回帰（SPI/QSPI、表示、音声/PCM、BLIT/cursor、実topを含む）|26/26 PASS|rmw-fb-regression.log|
|32B分割Controller|272ケース PASS|rmw-controller272.log|
|RX32 tap / fetch|381 / 776ケース PASS|rmw-rx32.log|
|driver / QSPI oracle|15 / 4テスト PASS|rmw-drivers.log|
|CSR window既存試験|PASS|shared-rmw-window.log|
|Gowin SPモデルのwindowとleaf mask oracle|PASS（mask/pattern 128ケース等）|shared-rmw-vendor.log|
|共有group競合追加試験|behavioral / Gowin SPともPASS|shared-rmw-interleave.log|
|32B wrap統合|12/12 PASS|rmw-wrap12-integration-resumed.log|

追加試験は64byteの非zero独立オラクルを用い、descriptor READを各書込みに挿入して64か所を置換し、毎回全窓を検証する。窓端64の拒否、busy中の拒否、commit中resetも確認した。Gowin SPモデルには部分ADでの書込みを拒否するassertionを加え、native byte enable依存が残らないことを検証する。このassertionは設定検査であり、実機破損の再現モデルではない。

再実行用の追加ファイルは新worktreeの`sim/tests/tb_fb_upload_shared_rmw.sv`、`tb_fb_upload_word_rmw.sv`、`tools/test-upload-shared-rmw.sh`、`test-upload-rmw-vendor.sh`。Gowinモデルはインストール済みStandard simlibからSP部分を抽出して利用し、ライブラリ本体を改変しない。rootの`tools/summarize-upload-rmw-regressions.py latched`は完了マーカーを検証し、各ログのhashを保存する。共通22件・Controller272・RX32・driverは変更RTLに依存せず、同じ継承ソースを使った先行完走ログを再利用する。FB26・wrap12・CSR/vendor/追加試験は最終RTLで再実行する。

## Standard評価

直接各SPでRMWする最初の案は、同じPlace1/Route2でCLS4206/4320、FF4910、BSRAM19となり、未配線1 net（PR0004）で不合格。bitstreamなし、有効なSTA合格値なし。`build/standard-direct-rmw/`に固定入力とresult.jsonを保存した。

共有group RMW案（`build/standard-shared-rmw/`）は中断後同じ固定入力で再実行し、全配線を完了したがSetup −2.416ns・6違反、Hold +0.501ns・0違反で不合格。CLS4149/4320、FF4910、BSRAM19、Logic7309。最悪経路は未変更のcursorのheld_colors→pixel_colorsだった。生成fsのSHA-256は `87522e8a7bcb284a34c26781cfa161ffb1d9e7850b072f92f9cf4755907810a8`。fs生成は品質合格を意味せず、専用DO_NOT_PROGRAMを配置した。

RMW以外の経路や配置設定を変更せず、merge済み32bitをCSR受理時に保持する案を`build/standard-latched-rmw/`へ固定し評価した。変更対象は引き続き2 RTLのみ。合成FF4932（基準比+22）、BSRAM19。追加試験はbehavioral/vendor両方PASSし、vendor CSR windowおよびleaf 128ケースもPASS。**最終RTLでFB全26件、wrap統合12件の再実行もすべてPASS**。ログは`latched-rmw-*.log`、機械確認とhash一覧は`build/analysis/upload-rmw-regressions-latched.json`。上表の共有group案の結果とは別に最終RTLで確認した。内部STAと外部PSRAM I/Oタイミングは別判定。

32bit保持案のStandardは完了し、**内部タイミングゲートPASS**。Setup **+0.717ns**、Hold **+0.407ns**、違反 **0/0**、全配線完了。Recovery +10.624ns、Removal +0.551ns。CLS **4171/4320**、FF **4932**、Logic7368、BSRAM19（SP16+SDPB3）、DSP1。基準比CLS+27、FF+22。bitstream SHA-256は `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`。`result.json`と`timing-status.json`、専用DO_NOT_PROGRAMを保存。過去2案の不合格結果も保持した。これは同じツール設定によるRTL構造の比較であり、位相・seed探索の結果ではない。

継承SDCはsystem54とpsram54（67.5度）、pixel74/serial371を定義するが、PSRAM外部min/max I/O契約を完備していない。Host非同期ポートはfalse pathであり、Host基板上のsetup/holdまでSTAで保証するものでもない。本修正ではこれらを緩和せず、その制限をそのまま保持する。実ダイ未同定のため、別型番の数値を流用した外部タイミング合格は出さない。

## 次の実機試験と停止条件

最初の候補はこの32bit保持RMW統合版1案に限定する。PC全回帰と内部Standardゲートは満たした。本報告のhashと手順をレビューした後、本体へのSRAM一時書込みを行う段階とする。今回はプログラミング・Flash読書き・RP2040操作を行っていない。外部I/Oゲートは未達のままである。

1. 現在KAGURA-9の復旧状態、復旧イメージhash、RP2040 Flash/FW hash、接続・識別を確認。
2. FPGA SRAMにのみ統合候補を一時ロード。FPGA Flash、RP2040 Flash/FWを変更しない。
3. Hostから明示的なPSRAM操作をsubmitする前に4B `ED 0F 21 43` のupload echoを検証する。PASS後、非zeroパターン、窓端を少数確認。本体には起動時のメモリ初期化・表示アクセスがあるため、この手順はCS非assertの独立診断とは異なる。Host窓不一致ならHostからPSRAM試験をsubmitしない。
4. 起動処理の完了を確認し、表示・音声・BLIT等と競合しない安全な試験領域と物理的に独立したguardを事前確定する。元のaddress300032は元Hostログの数値表記・進数を再確認し、その領域の安全性を確認できた場合に限り再使用する。4B WRITE/READを独立Hostオラクルで比較。CA/chunk、初期化、clock条件、expected/actual/XORとhashを保存。連続READと別アドレスREADを少数実施。本体では診断tapを追加していないため、CA/chunkはソースからの予測値と実観測を区別し、取得できない境界ログを捏造しない。
5. timeout、識別異常、最初の不一致で直ちに停止しKAGURA-9へ復元、識別とhashを確認。復旧を確認できなければ次へ進まない。

upload echoのみ改善してPSRAM比較が失敗した場合、Host修正の効果と残存PSRAM故障を分離して報告する。先頭pairだけの不一致でもREAD起因と断定しない。周波数・位相・latencyを同時に変更しない。

実機統合PASS、外部PSRAM I/O評価、wrap/追加破損の切分けは未完了。診断でのPASSを製品Release条件達成として扱わない。
