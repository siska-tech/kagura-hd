> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD統合実機キャンペーン結果：メモリ・描画PASS、音声A0で停止

## 1. 結論

指定された`fix/upload-word-rmw-01`候補を変更せず、固定したキャンペーンを連続実行した。**Stage 1～4の67ケースとStage 5の描画5ケースはPASS。Stage 6の最初の音声A0が事前基準を満たさず停止した。** 72 PASS / 1 FAIL、後続PCM2条件と競合Stage 7は未実施。キャンペーン全体は不合格であり、`release_ready=false`を維持する。

実機の初発異常はPSRAMデータ比較ではなく、保存したHDMI音声の左右サンプル一致率である。音源・HDMI経路とキャプチャ経路のどこで差が生じたかは未確定。失敗後の再試行、基準緩和、別bitstream投入、RTL/周波数/位相変更は行っていない。

自動復旧は完了し、KAGURA-9のABI(0,6)、console状態、HDMI表示を確認した。FPGA/RP2040 Flash書込み0、FW/filesystem変更0、Git Push/Merge/Releaseなし。

## 2. 固定条件と承認範囲

- Campaign ID：`RMW-CAMPAIGN-01`。
- bitstream SHA-256：`90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`。
- 計画SHA-256：`997e6a271ced4487346460e6a001de8c06a694a968b879f1f8b14fd42e1be726`。
- 128入力（計画、刺激、RAM-only driver、測定器、実行器）を投入前にhash固定。終了後に全hash不変を確認。
- 30分上限、Device command timeout 3000ms、raw REPL job 50秒、SRAM投入上限1、再試行0。実行開始から復旧・記録まで163.047秒。
- Hostは以前と同じRAM-only method loaderとbitbang QSPI `half_period_us=5`。PIO 1MHz/5MHz試験とは異なり、pad周波数は未測定。
- FPGA/system設計値54MHz、PSRAM CK54MHz/67.5度、LAT14/RDL6、32B分割、CA/CR0/PHY/SDC/CSTを変更しない。
- 全ケースの成功で次へ進み、比較不一致、timeout、予期しないCSR/status/測定応答で停止。復旧以外の後続操作を行わない。

Preflight中に、過去のKAGURA-9 Flash保存記録のfs SHA `2d00ee52…f133d9`と現在そのパスのファイルSHA `ec26b922…20dfc`が一致しないことを発見した。両workspace内の244個のfsを検索したが、過去hashに一致する実体は見つからなかった。**ユーザーの「とりあえずそれはいいのでテスト優先して」により、この復旧fsファイルhash項目だけを保留して進めた。** 既存FlashからのReprogram復旧経路を使用し、復旧用の別fsは投入していない。既存FPGA Flash内容のbinary hashを確認したとは主張しない。

## 3. Preflightと測定系

|確認項目|観測・判定|
|---|---|
|KAGURA-9|ABI(0,6)、last_error=None、paused=False、事前HDMI画面確認|
|JTAG|1 device、ID0x1100481B、GW1NR-9C|
|COM7|RP2040 VID:PID=2E8A:0005|
|COM8|FTDI VID:PID=0403:6010。通信しない|
|RP2040全2MiB Flash|前後とも7134077f…96a6da6、private backupと一致|
|boot.py|9ef26228…b62b0、試験前一致|
|復旧RP2040 bin/UF2|既存manifestとhash一致、ファイル保護|
|PIO/GPIO|console pause/close、PIO解放。GP2..5入力、GP6 Low、GP7 High|
|候補fs|投入直前・終了後とも指定SHA一致|
|HDMI取得|UGREEN 15390、1280×720/60、RGB24の長さ検査、PNG保存|
|音声取得|同じUGREENのnative48kHz/16bit/stereo。投入前1秒のAV取得で形式・frame数を確認|
|PC測定器|既知RGB/PCMの受入、誤色と無音の拒否を確認。追加package不要|
|FPGA復旧fs file hash|上記の限定保留。既存FlashのReprogramによる復旧を実測確認|

映像はPCで生成した期待色と、指定された一様領域8×8画素のRGB平均を比較する。許容差は投入前に各成分50/255と固定し、実測最大差は11だった。全画面のbit単位一致とは区別する。

音声はnative PCM WAVを保存し、連続480frame以上のstereo zeroがないこと、100ms区間RMS>1、baseline左右差±2LSB以内が99%以上であることを固定した。これらの閾値はキャプチャ系のbit透過性を保証する較正結果ではなく、保守的な受入条件である。合成6chの個別ON/OFF、FIFO個別カウンタはこの固定topのHostから観測できないことを事前記録した。

## 4. アドレス・guard・オラクル

PSRAM scratchは10進byte address **299968～326143**。Display2面0～230399、固定PCM240000～240127と非重複。Stage 6だけは明示的にPCM領域へ既知データを書き込む計画だった。

各メモリcaseのaddress、length、payload、非zero初期値、禁止mask、最終期待値、guard address/期待値をPCで事前生成した。guardは対象の直前・直後・離れた箇所、および領域外に存在する場合のwrap先を使う。初期化後に独立READし、対象WRITEの前後でも独立READする。各caseの全guard配置は[機械可読ケース一覧](evidence/rmw-campaign-2026-11-05.json)に保存。

READ結果から期待値を生成しない。masked WRITEでは事前初期値とPC maskから保持byteも含めた期待値を生成する。対象は独立した4B READ、guard READ、同一起点の補助READ、連続READ、別アドレスREAD後の再READで確認した。

比較は計**1164回・8736byte**、うちguard比較**564回**。全てexpected=actual、XOR=0、error byte=[]。この数にはA0前のPCMゼロ領域READも含む。全比較を[JSONL](evidence/rmw-campaign-comparisons-2026-11-05.jsonl)に保存した。

## 5. Stage 1～4の実測

|Stage|ケース数|結果|範囲|
|---|---:|---|---|
|1 upload/echo|15|全PASS|4/8/16/32/64B、先頭/末尾/32B近傍、旧ED0F2143含む|
|2 境界8B|1|PASS|300060、012345678AACCEF0、独立guard|
|3 転送長/開始位置|11|全PASS|16/32/64B、整列/word非整列/byte非整列、旧64Bパターン|
|4 offset/pattern/mask|40|全PASS|32B内の全4B offset×5長。pattern/maskは有限巡回割当|

Stage 1はuploadのCSR echoであり、独立したdownload応答注入試験ではない。download/bulk captureは後続の実PSRAM READを通じて評価した。

Stage 2の主観測：

|address|役割|expected|actual|XOR|
|---:|---|---|---|---|
|300060|前半独立4B|01234567|01234567|00000000|
|300064|後半独立4B|8AACCEF0|8AACCEF0|00000000|
|300032|wrap先guard|90919293|90919293|00000000|
|300056|直前guard|88898A8B|88898A8B|00000000|
|300068|直後guard|B4B5B6B7|B4B5B6B7|00000000|
|300096|離れたguard|D0D1D2D3|D0D1D2D3|00000000|

この観測は、過去の「同一起点READの偽PASS、後半がwrap先へ移動」を今回のcaseでは否定する。前半・後半の順序とguard保持を独立に確認できた。

chunk数とCAはRTL/Host driverから事前計算したmetadata。例えばStage 2は4B+4Bの2chunk、32B整列64Bは32B+32B、word offset4からの64Bは28B+32B+4Bを予測する。byte非整列64BはHost窓による別request分割も含めて計算した。**物理CS回数やCAをpinで数えたわけではない。** 結果は予測した分割とデータ順序に整合するが、内部tap・padタイミングの証明とは区別する。64Bには32B境界を跨がない条件は存在しない。

## 6. 元64B破損との比較

旧記録ではaddress300000の64Bに32B wrapの予測からさらに16byte/46bitの残差があった。今回S3-009は同じaddressと`(i×37+11) mod256`の64Bを使用し、16回の独立4B READ、全64B READ、guard、反復/別アドレス後のREADが一致した。S3-010の300004/64B・salt53も一致した。

**今回の有限条件では残差を再現しなかった。** 旧Controllerのwrap問題とupload修正を一つの原因と断定しない。今回は32B分割とupload RMWを含む別配置の統合候補であり、単独変更対照ではない。電源再投入、PVT、全アドレス、全mask/全pattern総当たりでの保証へ拡張しない。

## 7. Stage 5：描画の独立比較

|ID|操作|Framebuffer READ|HDMIの独立比較|
|---|---|---|---|
|G1|page0青/page1赤、緑矩形、同一page重複BLIT、PRESENT1|赤/緑/青のサンプルbyte一致|移動先緑・背景赤一致|
|G2|PRESENT0・page切替|page0青一致|青2領域一致|
|G3|palette index2赤→黄、PRESENT1|index2保持|背景黄・緑矩形一致|
|G4|hardware cursor形状/位置更新|下地index2保持|白cursor・黄下地一致|
|G5|cursor非表示、両page黒初期化、PRESENT0|両pageのサンプルbyte一致|黒2領域一致|

全5ケースPASS。CSR DONEだけの判定ではなく、FramebufferサンプルとHDMIを組み合わせた。全Framebufferの全byte検査・全画面全画素差分ではない。PNG/RGBと各ROI expected/actual_meanを保存した。[cursor画面](../build/rmw-campaign-2026-11-05-v1/G4.png)には緑矩形・黄背景・白cursorが写っている。

## 8. Stage 6：初発異常と保存音声解析

A0では既存のPCM両loop64Bをゼロに書き、両領域の全byteをREADして一致を確認した。topで固定された6音源は左右同gainで動作するため、baselineでは左右一致を期待した。直前CSR status=2 / error=0。

|測定|値|固定基準との関係|
|---|---:|---|
|形式|48000Hz、16bit、stereo|一致|
|frame数|144096（約3.002秒）|140000～148000内|
|最大stereoゼロ連続|2frame|480未満|
|100ms区間の最小RMS|74.986LSB|>1|
|左右差±2LSB以内の割合|**93.3815%**|**99%以上を満たさずFAIL**|

このFAILで停止し、後続A1/A2のPCM既知波形、Stage 7の競合試験は実施していない。停止後に別音声を取得したり、閾値を緩和してPASSへ変更していない。A0後のCSR/FIFO状態読出しも実施していないため、3秒間のFIFO故障ゼロを断言しない。

保存WAVの追加解析（再測定ではない）：左右RMS=77.5229/77.5215、差RMS=1.38884LSB、最大差7LSB。整数lag −4～+4sampleの中ではlag0が最小差。最小二乗gain R/L≈0.999821。左の440/660/880Hz成分振幅≈60.31/39.05/51.07LSBを観測した。音声が取得されていることを示すが、6chを個別に保証する証拠ではない。

維持する仮説：

1. UGREEN/OS音声処理・量子化・dither/resampling等の取得経路で、小さな左右差が付加された。
2. HDMI音声packet/channel処理、synth/mixer、PCM fetchのいずれかで左右差が生じた。
3. baseline左右完全一致を仮定した受入測定系が、必要なbit透過較正を満たしていなかった。

小さい差、近いRMS、lag0だけでは一意に選べない。次の切分けは既知の左右同一デジタル音声源で取得経路の誤差分布を較正し、保存packet/sampleとの独立比較方法を確立すること。今回の結果を修正完了とせず、今回禁止されたRTL/PHY/clock変更には進まない。

Stage 7は音声FAILによって停止。加えて、事前計画でも固定topの個別6ch/FIFO詳細の非可観測性から完全な先行合格を証明できない場合は実行しないと定めていた。10秒/最大10反復/Host最大1280Bという案は未実行であり、stress PASSとして計上しない。

## 9. 安全復旧・保護

失敗後は診断WRITEを送らず、QSPI deinit→GPIO安全状態→`--run 1`で既存FlashからKAGURA-9へ復元（Finished、0.47秒）→RP2040全Flash再hash→単一raw REPL終了→通常soft reset→既存console `resume()`→banner/console/HDMI確認を実行した。

`KAGURA-9 RECOVERY CONFIRMED (0, 6) None`、`RECOVERY_STATE None False`を確認し、最終[HDMI画像](../build/rmw-campaign-2026-11-05-v1/kagura9-restored.png)も目視した。SRAM Programは1回、Finished、4.05秒。readback verifyを実施したとは主張しない。Reprogram1回、診断再試行0、追加電源cycleなし。

RP2040全Flash hashは復元後・通常soft reset前の値。soft reset/resume後の再読出しではない。

|対象|SHA-256|
|---|---|
|RP2040全2MiB：前/後/private bin|7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6|
|復旧UF2|4edd3bdcf17411049fe8ce58322c5bd0de2cbb5c41f1933ace1c440b7afaa44b|
|boot.py：前|9ef26228ee5039efa193938d4d11cc036d4b2589289250719f484647716b62b0|
|元RX32候補fs：保護|a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf|
|元DO_NOT_PROGRAM：保護|d97c7f7b7703f6ba0d077e2c2e11eefc398bd8eaaacc67070b88b35e2df80546|

製品RTL/Controller/PHY/SDC/CSTを変更していない。継承279ファイル・固定Standard入力38ファイルの監査を再実行し、許可されたRMW候補以外の差分が増えていないことを確認した。DO_NOT_PROGRAMを維持する。

## 10. Release判定と証跡

**Release不可。** 内部STA（Setup +0.717ns、Hold +0.407ns、違反0/0、全配線）は維持するが、外部PSRAM min/max仕様適合、実ダイ同定、PVT、音声合格、競合安定性の保証は未達。今回のメモリ/描画PASSをそれらの代替にはしない。

- [全ケース・guard・hash・測定結果](evidence/rmw-campaign-2026-11-05.json)
- [全1164比較 expected/actual/XOR](evidence/rmw-campaign-comparisons-2026-11-05.jsonl)
- [固定計画](../build/rmw-campaign-2026-11-05-v1/plan.json)、[入力hash](../build/rmw-campaign-2026-11-05-v1/frozen-inputs.json)
- [実行raw総ログ](../build/rmw-campaign-2026-11-05-v1/campaign.log)、`control/*.raw` / `*.log` / `*.request.json` / `*.sent` / `*.result.json`
- [AV原本](../build/rmw-campaign-2026-11-05-v1/A0.mkv)、[音声WAV](../build/rmw-campaign-2026-11-05-v1/A0.wav)、[音声後解析](../build/rmw-campaign-2026-11-05-v1/audio-postmortem.json)
- `G1..G5.{rgb,png}`、復旧画像、JTAG/Program/Reprogram/Flash hashログ、`evidence-sha256.json`を同directoryに保存。
- 生成・PC検査・測定・実行・集計用スクリプトは`tools/*rmw-campaign*.py`。既存markerと固定入力検査で同じキャンペーンの再実行を拒否する。

private復旧imageは公開証跡にコピーしていない。

## 付録：事前定義した全ケースの判定

|ID|Stage|address / offset|length|pattern / condition|mask（禁止bit）|結果|
|---|---:|---:|---:|---|---|---|
|S1-000|1|0|4|zero|—|PASS|
|S1-001|1|30|4|ff|—|PASS|
|S1-002|1|60|4|aa55|—|PASS|
|S1-003|1|0|8|55aa|—|PASS|
|S1-004|1|28|8|address|—|PASS|
|S1-005|1|56|8|walk1|—|PASS|
|S1-006|1|0|16|walk0|—|PASS|
|S1-007|1|24|16|prng|—|PASS|
|S1-008|1|48|16|zero|—|PASS|
|S1-009|1|0|32|ff|—|PASS|
|S1-010|1|16|32|aa55|—|PASS|
|S1-011|1|32|32|55aa|—|PASS|
|S1-012|1|0|64|address|—|PASS|
|S1-013|1|0|4|original4|—|PASS|
|S1-014|1|60|4|reverse4|—|PASS|
|S2-000|2|300060|8|boundary-exact|0000000000000000|PASS|
|S3-000|3|304000|16|prng|0000000000000000|PASS|
|S3-001|3|304276|16|address|0000000000000000|PASS|
|S3-002|3|304515|16|prng|0000000000000000|PASS|
|S3-003|3|304768|32|address|0000000000000000|PASS|
|S3-004|3|305028|32|prng|0000000000000000|PASS|
|S3-005|3|305281|32|address|0000000000000000|PASS|
|S3-006|3|305536|64|prng|0000000000000000|PASS|
|S3-007|3|305796|64|address|0000000000000000|PASS|
|S3-008|3|306049|64|prng|0000000000000000|PASS|
|S3-009|3|300000|64|original11|0000000000000000|PASS|
|S3-010|3|300004|64|original53|0000000000000000|PASS|
|S4-000|4|312000|4|zero|0000000000000000|PASS|
|S4-001|4|312256|8|ff|00000000000000aa|PASS|
|S4-002|4|312512|16|aa55|000000000000fffe|PASS|
|S4-003|4|312768|32|55aa|000000007fffffff|PASS|
|S4-004|4|313024|64|walk1|bbbbbbbbbbbbbbbb|PASS|
|S4-005|4|313284|4|ff|000000000000000e|PASS|
|S4-006|4|313540|8|aa55|000000000000007f|PASS|
|S4-007|4|313796|16|55aa|000000000000bbbb|PASS|
|S4-008|4|314052|32|walk1|00000000f0f0f0f0|PASS|
|S4-009|4|314308|64|walk0|0000000000000000|PASS|
|S4-010|4|314568|4|aa55|000000000000000b|PASS|
|S4-011|4|314824|8|55aa|00000000000000f0|PASS|
|S4-012|4|315080|16|walk1|0000000000000000|PASS|
|S4-013|4|315336|32|walk0|00000000aaaaaaaa|PASS|
|S4-014|4|315592|64|address|fffffffffffffffe|PASS|
|S4-015|4|315852|4|55aa|0000000000000000|PASS|
|S4-016|4|316108|8|walk1|00000000000000aa|PASS|
|S4-017|4|316364|16|walk0|000000000000fffe|PASS|
|S4-018|4|316620|32|address|000000007fffffff|PASS|
|S4-019|4|316876|64|prng|bbbbbbbbbbbbbbbb|PASS|
|S4-020|4|317136|4|walk1|000000000000000e|PASS|
|S4-021|4|317392|8|walk0|000000000000007f|PASS|
|S4-022|4|317648|16|address|000000000000bbbb|PASS|
|S4-023|4|317904|32|prng|00000000f0f0f0f0|PASS|
|S4-024|4|318160|64|zero|0000000000000000|PASS|
|S4-025|4|318420|4|walk0|000000000000000b|PASS|
|S4-026|4|318676|8|address|00000000000000f0|PASS|
|S4-027|4|318932|16|prng|0000000000000000|PASS|
|S4-028|4|319188|32|zero|00000000aaaaaaaa|PASS|
|S4-029|4|319444|64|ff|fffffffffffffffe|PASS|
|S4-030|4|319704|4|address|0000000000000000|PASS|
|S4-031|4|319960|8|prng|00000000000000aa|PASS|
|S4-032|4|320216|16|zero|000000000000fffe|PASS|
|S4-033|4|320472|32|ff|000000007fffffff|PASS|
|S4-034|4|320728|64|aa55|bbbbbbbbbbbbbbbb|PASS|
|S4-035|4|320988|4|prng|000000000000000e|PASS|
|S4-036|4|321244|8|zero|000000000000007f|PASS|
|S4-037|4|321500|16|ff|000000000000bbbb|PASS|
|S4-038|4|321756|32|aa55|00000000f0f0f0f0|PASS|
|S4-039|4|322012|64|55aa|0000000000000000|PASS|
|G1|5|—|—|G1|—|PASS_FRAMEBUFFER_AND_HDMI|
|G2|5|—|—|G2|—|PASS_FRAMEBUFFER_AND_HDMI|
|G3|5|—|—|G3|—|PASS_FRAMEBUFFER_AND_HDMI|
|G4|5|—|—|G4|—|PASS_FRAMEBUFFER_AND_HDMI|
|G5|5|—|—|G5|—|PASS_FRAMEBUFFER_AND_HDMI|
|A0|6|—|—|A0|—|FAIL|
|A1|6|—|—|A1|—|NOT_RUN_AFTER_FIRST_FAILURE|
|A2|6|—|—|A2|—|NOT_RUN_AFTER_FIRST_FAILURE|
