> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 音声registers 901 FFの保持目的と限定削減案

> 後続の[192 bit単独variantの実装・評価](audio-snapshot192-result-2026-11-05.md)を完了した。PCはPASSしたが配置は不合格。本稿の「未実装・未測定」は設計時点の記録である。

## 結論

既存合成netlistの`kagura_audio_registers`内を全件集計し、**901個のDFFが階層resource XMLの901 FFと一致**した。内訳の大半はHost shadowと受理済みsnapshotであり、同じ寿命の不要コピーではない。音源coreのEXTERNAL_SNAPSHOT=1で不要になるpending設定データのDFFも残っていなかった。

単純な重複削除だけで配置不合格を解消できるとの根拠はない。次の単独候補として、**受理済みsnapshotのうち192 bitだけを6個の32bit SP BSRAMへ置き換える設計**を推奨する。shadow・readback・音源core・PCMを変えず、新しいミラーやqueueを作らない。残るsnapshot 126 FFはそのままにする。BSRAMは全体19→25/26となる。

これは未実装の設計案である。今回は読み取り解析のみで、RTL変更、シミュレーション再実行、合成/P&R、Bitstream生成、実機操作を行っていない。`release_ready=false`。

## 証拠・数え方

対象は`build/audio-minimal-bridge/build/standard-minimal-pnr-01/impl/gwsynthesis/kagura_fb.vg`。module境界内のDFF系primitiveを数え、instance名からRTL信号へ分類した。FF primitiveの内訳はDFFR 53、DFF 38、DFFS 3、DFFRE 797、DFFSE 10、合計901。

Gowinが`channel_data`配列をRAMREGというinstance名へ変換しているが、ここでは実際にDFFとして出力されている48個を数えた。名前だけを見てBSRAMと扱っていない。分類未所属・重複所属なしを検査した。

[全901 instanceのprimitive・Q/D/CE/reset、信号群、分類、対象192 bit](evidence/audio-register-storage-inventory-2026-11-05.json)を保存。`tools/analyze-audio-register-storage.py`で既存netlistから再現できる。

## 1. 完全な用途別内訳

|用途|実測FF|構成|
|---|---:|---|
|6ch/global shadow|292|STEP 120、DUTY 24、左右GAIN 96、ENABLE 6、PHASE_RESET要求6、wave length16、noise period16、master8|
|PCM shadow|180|START/END/LOOP各48＝144、LOOP_ENABLE 2、左右GAIN 32、ENABLE 2|
|受理済みsnapshot|318|STEP120、DUTY24、左右GAIN96、ENABLE6、RESET6、LEN8、MASTER8、PERIOD16、PCM左右GAIN32、PCM ENABLE2|
|capture制御・reset要求保持|8|capture_pending 1、captured_resets 6、apply_busy 1|
|readback cache|64|channel_data 6×8＝48、global_data8、pcm_data8|
|INDEX・READ応答・検査|19|index8、rdata8、read_legal1、write_legal1、settings_valid1|
|WRITE pipeline・settle|12|dw_q1、wd_q8、settle_sr3|
|PCM命令pulse|6|PREPARE/STOP/CLEAR各2|
|sticky fault|2|underflow1、overflow1|
|**合計**|**901**||

shadowは292＋180＝472 FF。noise ch3のSTEPはRTL宣言上24 bitあるが、書込み・使用がないため合成済みnetlistでは除去され、shadow/snapshotともSTEPは120 FFである。この48 bit分を今後の削減余地へ再計上してはいけない。

STEP bit23とlength上位bitは不正値のreadback/検査にも使われる。SDKが通常送らないという理由だけで切り捨てると、不正値を合法値へ変えるおそれがある。24bit PCM addressの上位bitも、HDの22bit幅検査・readbackのために保持されている。検査契約を無視した幅削減は採用しない。

## 2. 保持期間と共有可否

|状態|更新・保持期間|共用/削除した場合の問題|
|---|---|---|
|Host shadow|INDEX/DATAで編集。次のCOMMITを準備できる|snapshotと同居させると、適用待ち中の次shadow編集ができない|
|受理済みsnapshot|COMMITで固定し、coreの実apply完了まで不変|shadowの最新値を直接見せると、受理後の編集が出音へ混入する|
|synth active|sample境界で更新し、現在の演算・出音に使用|pendingの設定で上書きするとsample境界適用を壊す|
|captured_resets|capture時に要求を救い、shadow要求をself-clearした後にsnapshotへ渡す|単にclear後のshadowを読むとphase-reset要求を失う|
|PCM START/END/LOOP等|PREPAREが参照し、Host readbackとして残る|prefetcherの再生位置は進むため、元STARTの代替にはならない|
|PCM gain/enable snapshot|COMMITで固定しsample境界適用|PREPARE時設定と一括共有すると、反映時点が変わる|
|readback cache|field/channel muxを段階分割し、settle後の応答を形成|論理的には再計算可能だが、除去でmux深さ・LUT・タイミングが悪化し得る|

PCM controlにはPREPARE pendingがあり、prefetcherはcfg_valid/cfg_readyで設定を受理する。元address shadowは既存仕様どおり、少なくとも受理まで安定させる必要がある。今回その経路を新しい保存方式へ置き換えることは推奨しない。

音源coreはEXTERNAL_SNAPSHOT=1であり、pending_step/duty/gain等はRTLに宣言されていても合成DFFには残っていない。残る「pending」という制御flagはapply待ちを表す状態であり、設定データの重複保存とは異なる。

## 3. 削減候補の比較

|案|算術上の効果・追加資源|判断|
|---|---|---|
|readback cache共有/直接選択|channel cache48 FFの一部/全部が候補。新mux・pipeline分は差し引く必要あり|小規模候補。旧06の直接選択はLogic8663/8640で失敗しており、主案にしない|
|BSRAM readback mirror|既存64 FF cacheの除去が上限、さらに制御が必要。RAM上へshadow値を重複保持|限定効果と重複管理が増える。旧停止WIPは未検証。再開を推奨しない|
|**snapshot192 bitの並列BSRAM置換**|**192 FFを置換、SP32×6、共通reset遅延1 FFを想定**|**推奨する次の単独候補**。既存snapshotの保存媒体だけを変える|

旧06はLOCKED_SNAPSHOT側の直接選択案であり、今回の通常Snapshot＋段階化した共有cache案が必ず失敗するという証明ではない。ただし「FFを減らせばLogicも減る」という前提は、過去結果に反する。

captured_resetsの段階統合やread-response段の共有などは数bit～十数bitの候補にとどまり、適用時刻やread pipelineの契約を変えるリスクがある。snapshot自体の削除、BUSY中の全DATA拒否、PCM address保持の省略は機能互換を失うため候補から外す。

## 4. 推奨する192 bitの対応

実際のDFFとして存在する次の192 bitを選ぶ。全てSTEP/gainで、reset値が0であり、capture時に自動clearされない。

- snapshot_l[47:0]：48 bit
- snapshot_r[47:0]：48 bit
- snapshot_step[71:24]：ch1/2の48 bit
- snapshot_step[143:96]：ch4/5の48 bit

shadow側の連結は、概念的に`P={steps[143:96],steps[71:24],gains_r,gains_l}`、192 bit。32 bitずつ6 SPへ同じedgeで書き、同じ割当てで並列出力する。ch0 STEP24 bitと残りのsnapshotは従来FFのまま。noise STEP24 bitは既存の定数化を維持する。

各RAMではaddress 0の1 wordだけを使用する。SP32、READ_MODE=0、WRITE_MODE=00、全byteを有効にする固定AD下位bit、full-word writeを使用する案である。既存upload_wordが使用する設定を参照するが、そのmoduleやUpload経路は変更しない。CPUのbyte書込みをこのRAMへ直接接続せず、RMWやnative partial-byte maskを新設しない。

物理容量の利用効率は低い。192 bit保持に6 blockを消費する理由は、既存coreへの192 bit並列出力とsnapshot一括更新を維持するためである。汎用RAM化・音声全体のBSRAM化ではない。318 bit全snapshotを同じSP32方式へ単純移植すると10 blockが必要で、空き7 blockを超える。したがって対象を限定する。

## 5. captureとREAD latencyの整合案

RAMを現在の`capture_pending`で書くと、次のREAD edgeまで新データを出せず、現在のAUDIO_SENDへ間に合わない。単にFFをSPへ置換するだけでは不正である。

推奨案は**RAMだけを1 edge早いaudio_captureで書く**。既存busはcapture同時のshadow書込みを拒否し、書込みpipeline/settleも保持する。このため選択したSTEP/gainは元のsnapshotが読む次edgeまで安定する。残り126 bitのFF snapshotとphase-reset pipelineは変えない。

|edge|既存FF snapshot|候補RAM|既存command/core|
|---|---|---|---|
|E0: audio_capture|capture_pendingを立てる。出力は旧値|shadowのSをfull-word write、DOは旧値保持|EXECUTE→AUDIO_SNAPSHOT|
|E1|Sをsnapshotへ反映|WRE=0でSをREAD、edge後DO=S|AUDIO_SNAPSHOT→AUDIO_SEND|
|E2|Sで安定|Sで安定|coreがapplyを受理|

このサイクル案ではcommand FSMの追加状態・遅延変更は不要で、coreへの有効時刻を従来に合わせられる。E0以後の次shadow編集は別の既存FFへ入り、RAMに捕捉済みのSには影響しない。新しいShadow/Snapshotコピー、世代番号、dirty管理、queueは不要。

**この表はRTLとローカルGowin SPシミュレーションprimitiveを読んだ設計上の導出であり、候補RTLによる検証結果ではない。** 実装時はWRITE_MODE=00のDO保持と次READ edgeをvendor modelでも確認する。

## 6. reset案：bitごとのreset muxを増やさない

192 bit全てのDIへreset muxを追加するとLUT増分が削減を打ち消すおそれがある。対象フィールドのshadowは既存resetで0になるので、共通のreset_delay 1 FFを用い、resetの次edgeにaddress 0をそのshadow値で書く案とする。RAM出力には同期RESETを接続する。

- R0：resetで既存shadowとsnapshot FFを0、RAM出力を0、reset_delay=1。
- R1：reset_delayでRAMへshadowの0を書き、DOは0を保持。
- R2：通常READでmemoryの0を出力。

1 cycleだけのwarm resetも対象とし、bitstreamの初期値や長いreset保持には依存しない。address全域のclear loopや初期化FSMは不要。このreset案も未実装であり、capture直前/直後のreset、再reset、Host再開をvendor modelで検証する必要がある。

## 7. 資源予測と限界

|項目|現在の実測|候補の算術値・未測定部分|
|---|---:|---|
|audio_registers FF|901|901−192＋reset遅延1＝710を出発点とする|
|全体FF|6309|6309−192＋1＝6118を出発点とする|
|全体BSRAM|19/26|25/26、空き1|
|全体LUT/Logic|合成7593 LUT、Logic8581|未測定。減少を保証しない|
|未配置REG/LUT相当|273 / 124|予測不能。192 FF削減で解消するとは言えない|

上のFF算術値は、制御や合成最適化の変化を含まない。BSRAM配置・routing・reset fanoutが悪化する可能性もある。未配置273 REGは「最低273 FFを削れ」という数値ではないため、192 FF削減を十分/不十分のいずれにも断定しない。

7 blockで216 bitを移す拡大案も算術的には可能だが、全体26/26となり余裕を失う。今回の第一候補へ混ぜない。6 block版の測定前に段階を増やしたり、cache変更と同時に実施したりしない。

## 8. 将来実装時に固定する検証

1. 現在のFF版をreferenceにして、legalなbus/settle/capture契約下で全cfg・readback・busy・PCM pulseをcycle単位比較。E0前後の書込み、phase-resetのself-clear、次shadow編集、二重COMMIT拒否を含める。
2. SP32のvendor modelと通常PC modelの両方で、WRITE→READ、短いwarm reset、全6 wordの一括更新を検証。未更新word混入を許さない。
3. 6ch/PCM2、SPI/QSPI実top、tag完了、sample境界直前/直後、timeout/error/reset、既存PC回帰を確認。apply時刻が1 cycleずれないことも明示的に比較。
4. その単独variantを同じStandard条件で1回評価し、FF/LUT/BSRAM、未配置数、配置/配線/STAを記録。失敗後の自動拡大や条件探索はしない。

この案の実装・PC試験・物理評価は今回行っていない。現在の最小ブリッジは引き続き配置不合格で、実機投入できない。

## 保護状態

固定40入力、RMW基点、停止した旧audio/RAM作業コピーは保存hashと一致。901 FF解析のために追加したものは解析スクリプト・証拠JSON・本報告のみである。元STA合格Bitstream、診断成果物、DO_NOT_PROGRAMの保護方針を変更していない。`release_ready=false`。
