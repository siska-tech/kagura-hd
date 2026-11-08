> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# CPU Headroom — offline implementation report

release_ready=false。実機CPU Headroom: **NOT MEASURED**。新firmwareの実機試験: **NOT RUN**。

## ベースラインと現行との差

最新実機根拠はHARDWARE_HOST_AB_RESULT.mdとevidence/host-ab-ON。FAST ON平均transaction 13.359µs、全体29.527fps、最悪call149.040ms、timeout0、PCM status fault0。既存CPU_HEADROOM.md／bounds JSONは今回着手前の未追跡ファイルとして保持した。
core0経過148.95sの58.6% Host内／12.1% 描画内Host外／29.2% 描画外はwall-time分類。CPU使用率、WFE率、DMA回収率への換算は禁止。名目scene時間あたりfpsも期限遵守率ではない。
READMEの前作transport直リンク記述と異なり、現行は専用src/b16_qspi.c。既存のpalette cache、152×48 mask、ページ別差分、縦矩形化、ロゴ領域invalidは既に存在。古いrp2040-build.jsonのBSS 41KBは現在のframe log／mask構成の基準に使わない。直近Host資料はBSS約210KB。

## 計測

src/b16_profile.h/.cのcore0専用stack profiler。push/pop時に直前の最上位regionだけへ経過時間を加算する。親から子への遷移は排他的で、親子を二重加算しない。24段のoverflowを計数し、不正な深さは以後のpopで回復する。IRQ、USB割込み、時刻取得の費用が混入する。cycle-accurateなCPU実行時間やidle counterではない。

|選択|内容|
|---|---|
|PROFILE_OFF / B16_PROFILE=0|region hookを除去。既存transaction計測、frame記録、PRESENT時刻は共通で残す|
|PROFILE_SUMMARY / 1|main、renderer、SDK、begin/end、wire、DMAの大区間|
|PROFILE_DETAILED / 2|さらに方向、CS setup/hold、TX/RX FIFO service、無進捗、期限確認|

main: draw/no-draw、USB、log、scheduler、sleepを分類。renderer: geometry（線走査の子時間を除く）、mask走査、矩形抽出、descriptor生成、submit、DONE、PRESENT。transport: begin、方向、CS setup、FIFO供給／回収、無進捗、deadline、wire terminal、CS hold/interval、end。各functionの分類されない制御命令は最寄りの親へ残る。無進捗regionはそのiterationのtight_loop区間であり、PIOの全物理stall時間ではない。PRESENT配下のDONE時間をPRESENT自身へ再加算しない。region番号はheader enumに対応。

計測windowは初回tick後のmain loopから、finish／保存ログ出力前まで。初期preload・停止後の全frame dumpは含めない。frame logは4600×24B（旧32B）へ削減し、累積command/pixelは既存PERFへ残した。ログoverflowが起きたrunは無効にする（frame_count上限4600、通常33msで4546frame）。

詳細計測のclock読出しと関数callは短いtransactionへ大きく作用し得る。同一seed0xb1616、120MHz、QSPI既存設定、-O2、同じ素材／ログ／rendererでA-off／summary／detailedを複数回比較する。PC fake時刻は計測加算の検証専用。実機の計測負荷はNOT MEASURED。現時点で補正率を提示しない。

## 実仕事による余力試験

B16_WORK_ROUNDS=0が既定。work64候補は描画間の残り時間が2msを超えるtickで、64roundを1batch実行する。2msは安全保証ではなく試験開始条件。各roundは32bit shift×3、xor×3、add×2（loop制御を除く8算術演算）を持つ。入力と戻り値checksumを連鎖し、終了後に同じbatch数を再計算して照合する。volatileだけに依存しない。fake testにはPython独立oracleもある。

WORKログ: batches、rounds、実測work_us、checksum、valid、call_over_budget、deadline_misses。実行round数=batches×rounds、上記算術演算数=round数×8。単一batchがdeadlineを越える可能性をframe記録で評価する。0/16/64/256/1024roundを段階的に比較し、PRESENT間隔、deadline miss、GPU error、timeout、PCM STATUS faultを併記する。音声underrunの独立counterは存在しない。

実測前なので、利用可能演算/秒、CPU空き率、DMA解放率は全てnull／NOT MEASURED。DMA版は現在pollingで待つため、DMA化だけで別のCPU仕事を実行したとは扱わない。

## Core1

対象アプリ、リンク設定、関連native transportにcore1起動／multicore FIFO操作はない。アプリはcore0のみ。core1は今回使用せず、共有workspaceも追加しない。将来のcore1導入ではowner、release/acquire barrier、IRQ/FIFO、RAM競合を別試験とする。

再現: tools/build_headroom_matrix.ps1、tools/test_dma.py、tools/test_headroom_variants.py、tools/test_headroom_render.py。結果とメモリ量はHEADROOM_STATUS.json／MEMORY_MAP.md。
