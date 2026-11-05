> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 音声snapshot192：6 BSRAM単独variantの実装・評価

**結果：PC全検証PASS、Standard配置FAIL（PR0003）。** FFは6309→6118へ191減り、未配置REGも273→111へ改善したが、未配置LUT相当113が残った。配線・STAには進めず、Bitstreamは未生成。条件変更・再試行・7-bank拡大は行っていない。

## 変更範囲

[901 FF保持状態の解析](audio-register-storage-analysis-2026-11-05.md)で提案した、受理済みsnapshot192 bitだけを6個のSP32へ置換するvariantを`build/audio-snapshot192`に実装した。親`build/audio-minimal-bridge`、元STA候補、停止した旧RAM mirror案は変更していない。実機投入・Flash/FW変更・Push/Merge/Releaseは行わない。`release_ready=false`。

- 置換対象: 左右GAIN各48 bit、STEPのch1/2/4/5各24 bit、合計192 bit。
- 既存shadow472 FF、残りsnapshot126 FF、readback、PCM、COMMIT FSM、音源演算、Host SDK、Controller/PHY、SDC/CSTは維持。
- `SNAPSHOT_BSRAM192` parameterのdefaultは0。最小HD endpointだけが1を指定する。
- `.BIT_WIDTH(32) / READ_MODE=0 / WRITE_MODE=00 / RESET_MODE=SYNC`のSPを6個使用。全word固定address、全byte有効、full-word write。CPU byte write、native partial mask、RMWは使わない。
- RAMはaudio_captureのedgeで書き、次edgeでREADする。既存FF snapshotが更新されるedgeと揃えるため、COMMIT FSMの状態や適用時刻を変えない。
- 対象shadowのreset値は全て0。共通reset_delay 1 FFで次edgeにその0を書き、SPの同期RESETで出力を0にする。全address clear FSMや新規queueはない。

実装差分は、既存audio_registersの保存媒体選択、新規snapshot_word primitive wrapper、endpointのparameter指定、sources.f、対応PC試験だけ。既存upload_wordは変更していない。

## PC検証

Verilator 5.032。FF referenceは変更していない親のaudio_registersを別module名で使用する。新moduleのdefault modeとRAM modeの双方を、referenceとcycle単位で比較する。

|集中検証|結果・範囲|
|---|---|
|通常モデルのcycle比較|PASS、64 rounds / 8608 transaction / 112 capture / 40 warm reset / 44363 cycle|
|Gowin SP modelのcycle比較|PASS、同じ全ケース。インストール済みV1.9.12.04のSP moduleを無改変で抽出して使用|
|Host bridge集中試験|PASS、86 CSRアクセス。tag、次shadow編集、PCM幅検査、error、pending中reset|

各cycleでdefault/RAM modeの全27出力を比較した。Walking 1/0と固定seedの擬似乱数で全選択bankを更新し、capture直後の最短next-shadow write、WRITE/READ間のreset、適用待ち中のreset、resetとcaptureの同時assert、phase-resetの消費と次COMMITを含む。snapshotだけでなくreadback、合法性、busy、settle、PCM pulseも比較した。

Gowin model使用時にはAD下位4 bitが全て1であることも検査した。vendor moduleのbytesはローカルbuild内にのみ置き、配布ログarchiveへ含めない。元libraryと抽出moduleのhashを保存する。

これらはデジタルなcycle等価試験であり、I/O timingやPVTの証明ではない。

既存FB26件、QSPI実top、wrap12件、共通22件もすべてPASS。[PC証拠JSON](evidence/audio-snapshot192-pc-2026-11-05.json)へ最終結果とsource hashを保存した。SDKはsource hash不変で、今回API変更も再インストールもしていない。

## 固定する物理評価条件

全PC検証PASS後、GW1NR-LV9QN88PC6/I5、Gowin Standard V1.9.12.04、QSPI、Place1/Route2で1回のみ実行した。Clock/SDC/CSTを変えず、41入力を`build/standard-snapshot192-01/inputs/`へ固定した。ユーザー承認済みの範囲でBitstream生成まで試したが、配置で終了した。実機プログラミング、失敗後の自動再試行、7 blockへの拡大、cache変更や無関係なP&R探索は行っていない。

## Standard実測結果

|項目|親の最小FF版|snapshot192|差|
|---|---:|---:|---:|
|audio_registers FF|901|710|−191|
|全体FF|6309|6118|−191|
|合成LUT|7593|7580|−13|
|合成ALU|892|895|＋3|
|合成Logic換算|8581|8571|−10|
|P&R Logic|8570/8640|8560/8640|−10|
|BSRAM|19/26|25/26|＋6|
|CLS|4320/4320|4320/4320|0|
|未配置LUT相当|124|113|−11|
|未配置REG|273|111|−162|

audio_registers内の6個のsnapshot storageがそれぞれBSRAM 1として出力され、FF710の内訳も192 bit置換＋reset_delay 1 bitという予測と一致した。全体FF6118も算術予測と一致。PCMや音源演算を削った結果ではない。

一方でLogic削減は10にとどまる。FF削減量と未配置数の減少は一致せず、単独資源の上限以下でも全CLSを使用して未配置が残った。これを「111 FFだけ追加削減すれば完成」と解釈しない。

```text
[30%] Placement Phase 2 completed
ERROR (PR0003): Failed to place with
113 LUT(s)(equivalent, include LUT/MUX/ALU) unPlaced,
111 REG(s) unPlaced
```

process exit=1。配線・Standard STAは未実施。Setup/Hold slackと違反数は不明であり、0/0と報告しない。.fsとBitstream SHAは存在しない。外部PSRAM I/OとPVT、HDMI音声実キャプチャは未評価。

## 判断と未解決事項

この限定BSRAM置換は、検証した条件下で既存FF版とのcycle互換性を維持し、FFを減らせることを確認した。ただし、対象デバイスへの収容は達成していない。6 blockを使ってもLUT相当の未配置がほぼ残っているため、さらに保存状態を移すだけでの解決を前提にしない。

次の調査対象は、readback/decodeのLUT構造、LUTとFFの同時packing、clock/enable/reset制約の寄与である。個別の未配置instanceや支配的control setはまだ特定できておらず、この報告では原因を一意に断定しない。7 block拡大、readback mirror、BUSY中shadow禁止、P&R条件探索は未実施。音声制御全体のBSRAM化へ自動的に進めない。

本variantは比較用の不合格候補として保全し、親のFF版・旧実験・STA合格Bitstreamと混在させない。現在のRelease判定はFAIL、release_ready=false。

## 保護・再現

prepare-audio-snapshot192.pyで親を保全した独立copyを作り、prepare-audio-snapshot192-tests.pyでFF referenceとvendor SPを準備した。audit-audio-snapshot192.pyで変更範囲・親と旧案の不変・PC結果を確認する。freeze-audio-snapshot192.pyはPC PASSとsource hash一致を要求し、既存directoryの上書きを拒否する。

元RMW fs `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`、RX32 fs `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`を保護する。DO_NOT_PROGRAMとrelease_ready=falseを維持する。

元fsのhash、FF親・RMW基点・旧audio/RAM案のsource manifest、固定41入力のhash一致を最終確認した。

- [物理評価・資源階層・未配置数・固定入力](evidence/audio-snapshot192-result-2026-11-05.json)
- [全PC/Standard rawログ・資源報告・差分patch](evidence/audio-snapshot192-raw-2026-11-05.zip)

raw archiveにはvendor SPのソースbytesとBitstreamを含めない。source-input-manifest、reference hash、レビュー用patch、失敗ログを残した。summarize-audio-snapshot192.pyは失敗も保存し、未評価STAをPASSへ変換しない。
