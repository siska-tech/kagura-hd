> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD アーキテクチャ再設計・実現性評価 — 独立技術監査

後続評価の更新：本書の提案したscanout RX32単独実験は、機能回帰後のStandard単回ビルドでsetup +0.898ns・違反0/0・全配線を達成した。[後続の実測結果](rx32-scanout-standard-result-2026-11-04.md)を参照。本書本文は実装前監査の記録として保持する。実機・外部PSRAMの未解決事項は継続。

監査日：2026-11-04。対象：Tang Nano 9K、GW1NR-LV9QN88PC6/I5、Gowin Standard V1.9.12.04、system54 / pixel74、ABI 1.2。

**今回の実施範囲は既存ファイル・合成ネットリスト・STA・資源表・回帰ログの読取りと比較設計である。製品RTL、SDC/CST、既存証跡には変更していない。新規合成/P&R、シミュレーション回帰の再実行、実機操作、Git commit/Push/Merge、Releaseは実施していない。本報告書のみ新規作成した。**

## 1. エグゼクティブサマリー

**フル機能維持での成立は未証明だが、断念を正当化する証拠もない。最も合理的な次の方針は、ABIの64B窓を残し、内部の受信・記憶・転送を32bit単位へ段階的に変更するハイブリッド方式である。パレットCDCは独立した第2実験として扱う。** 帯域よりも、同時保持するデータの複製、制御配布、異なるclock/CE/resetを持つFF群の配置が当面の制約である。

実装開始前に報告すべき3点を先に固定する。

1. **推奨アーキテクチャ：案E（ハイブリッド）。** 64BのホストABI、32B絶対境界分割、6ch＋2ch PCM、HDMI音声、cursor、BLITを維持。内部は32bit受信から段階移行し、パレットは事前転送方式を別評価する。公式IP/PHYの評価はさらに別の実験にする。
2. **最初の評価実験：scanout RXだけを32bitでline RAMへ直接送る。** controllerの既存512bit READ応答はhost/BLIT用に残し、line fetchの512bit bufferだけを除去する。PSRAMのCS/CA/CK、32B分割、仲裁順、音声Phase 1、パレット、制約を固定する。一つの仮説「line fetchの複製保持を除くと、全体の物理実装に有効な余裕が生まれるか」を検証する。
3. **撤退条件：** 同一条件の機能・cycle境界検証に失敗、受信を止める必要が生じる、期限違反、想定した512bit保持の除去が合成後に確認できない、または配置配線/全体STAを悪化させて説明可能な構造改善もない場合、この候補を不採用として停止する。1回の不合格でフル機能全体を不可能とは判定しない。無制限のseed探索へは進まない。

|問い|現時点の判定|
|---|---|
|Q1 主因は配置か構造か|**双方。** パレット9経路は直接FF間配線。TX制御、CSR選択、過去の音声選択には構造的要因がある。高CLSだけを根因とはしない|
|Q2 192bit/512bitは主要コストか|パレットは現在の最悪STA群。512bit保持は実資源を消費するが、バス宣言全部をMUX/FFと数えるのは誤り。RX/TX/line buffer/CSRに分解すべき|
|Q3 狭幅化は効くか|重複保持と広い選択が実際に消えれば有望。変換adapterとFIFOを追加するだけなら逆効果。パレットは単純狭幅化でFFが増える|
|Q4 フル機能で現実的な道はあるか|**検証する合理性はある。成立の保証はない。** 分割後も既存回帰では映像/PCM期限に余裕があり、受信保持の削減候補がある。外部I/Oと追加破損は別問題|
|Q5 最初と撤退条件|上記scanout RX実験。次にパレット事前転送、次にupload窓/内部TX。各差分は独立評価し、不合格成果物を昇格しない|

本報告では **観測**＝今回読んだソース/既存成果物で確認、**計算**＝明示したモデルから算出、**仮説**＝将来の合成・配置で検証が必要、**未確認**＝証跡不足、と区別する。工数・新規テスト本数は計画上の概算であり実績ではない。

### 証拠の範囲と出典

ローカル作業ツリーのHEADは既存資料の基準 `1d46c6db71eb48e486a8e038d41e5a44342fe699` と関連する。評価worktreeには未コミット差分があり、**HEADだけでは評価入力を特定できない**。再実験時はmanifest/patch/hashを用いる。今回、既存の変更・未追跡ファイルを保持した。

|ID|読んだ主要証跡（リポジトリ相対）|用途|
|---|---|---|
|S1|`rtl/fb/kagura_fb_{core,scanout,line_fetch,line_banks,arbiter,burst_ctrl}.sv`|現行データフロー/CDC/仲裁|
|S2|`rtl/fb/kagura_fb_{registers,upload_word,commands,fill_burst,pcm_port,cursor}.sv`|窓/RAM/BLIT/PCM/cursor|
|S3|`boards/tang-nano-9k/{kagura_fb_top.sv,kagura-fb.sdc}`|初期化、クロック、制約|
|E1|`docs/standard-timing.md`、`docs/physical-placement.md`|基準、追加段、配置試行の失敗|
|E2|`build/psram-wrap32-worktree/rtl/fb/kagura_fb_burst_ctrl.sv`、同`build/kagura-fb-qspi/timing-status.json`|32B分割実装と43違反|
|E3|`build/asp-preselect-worktree/build/analysis/phase1-report.md`|音声Phase 1、回帰/資源/STA|
|E4|`build/upload-local-select-worktree/build/analysis/{phase2-report.md,phase2-setup-paths-table.txt}`|Phase 2の14違反と回帰|
|E5|同worktree `build/kagura-fb-qspi/impl/gwsynthesis/{kagura_fb.vg,kagura_fb_syn_resource.html}`、`impl/pnr/kagura_fb.rpt.txt`|合成実体と階層資源/P&R資源|
|E6|`build/palette-placement-audit/{report.md,analysis.json}`|384FF接続比較、部分配置、9経路|
|H1|`docs/psram-{4b,boundary,wrap-target}-hardware-result.md`、`docs/psram-investigation.md`、`docs/evidence/psram-wrap-target-hardware-decoded.json`|実機観測と未解決事項|
|T1|`sim/tests/tb_fb_{scanout,line_fetch,line_fetch_control,line_banks,burst_ctrl,burst_bounds,burst_service,fill_chain,blit,contention,register_window,board}.sv` など|再利用する検証仕様|
|A1|`docs/kagura-fb-host-api.md`、`docs/kagura-fb-implementation.md`|ABI/歴史的性能値の識別|

`docs/architecture.md`、`docs/memory-access-schedule.md` は旧Kagura-9の継承資料であり、そこにある720pの4倍拡大/4800cycle等は今回の640×360・2倍構成へ適用しない。既存回帰PASSはE3/E4の記録を監査したもので、今回再実行した結果ではない。

## 2. 現行アーキテクチャのボトルネック分析

### 2.1 実測が示す構造と配置の相互作用

|構成|Logic|FF total|CLS /4320|BSRAM|setup ns|setup違反|hold違反|全配線|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|Standard基準|7713|5346|4208|19|+0.097|0|0|完了|
|32B分割|7708|5369|4193|19|−3.407|43|0|完了|
|分割＋音声Phase 1|7717|5370|4217|19|−1.321|16|0|完了|
|Phase 2局所MUX|7720|5370|4225|19|−3.056|14|0|完了|

**観測：** 分割はCLSを基準より15減らしながら43違反を生じた。CLS使用率とslackの単調な関係は成立しない。音声Phase 1はFFを1増やしてpixel内部違反22→0、Phase 2はFF増加なしでupload入力違反9件を消した。しかし全体P&Rが変わり、別経路が悪化した。

Phase 2の内訳はsystem→pixel 9件、system内部5件、pixel内部0件。system内部は `state→tx[21]` −1.362ns、`state→tx_mask[36,3,5]`、`data_addr[3]→window_group[25]`。pixel側最小setupは+0.160nsであり、そこも大きな余裕はない。過去の追加段ではHDMI packet assemblerやline制御へ律速が移った。

パレットbit27はsource R26C2[0][B]→capture R20C31[0][B]、中間LUT0、data fanout1、C2Q 0.458ns、route 7.436ns。arrival=15.266ns、required=12.210ns、slack=−3.056ns。**同じclock条件で+0.100nsにはroute≤4.280ns、3.156ns短縮が必要**。これはLUT段数削減の対象ではない。Phase 1/2の384FFのclock/CE/reset接続一致は、論理接続の不変性と物理実装の変化を支持する。ただし全scanoutネットリストの完全同一性を意味しない。

送受信はclock/CE/resetが異なり、同じCLSのA/Bに必ず収まるという前提は誤り。384FF全配置と周辺占有/全192対のSTAは依然未取得。上位25経路だけで全配置を復元しない。bit99の距離15で5.476ns、bit35の距離31で4.926nsなので、グリッド距離をnsへ線形換算しない。

**観測：** Phase 2はLogic 7720/8640、fabric FF 5362/6480、CLS 4225/4320（97.80%、空き95）、BSRAM 19/26（空き7）。FF空きとCLS空きは別物であり、共有制御・LUTとのpacking・RAM位置・配線による制約がある。CLS90%以下（3888以下、Phase 2比337減）を探索目標にすることは可能だが、達成予測や採用ゲートにはしない。

### 2.2 合成後に確認できる費用

以下はE5階層表の**当該階層の行**であり、親子合算値ではない。ALUとLUTを独自換算してCLSへ変換しない。

|階層|REG|ALU|LUT|主な実体|
|---|---:|---:|---:|---|
|host/registers|255|0|1227|CSR、window選択、16 SPのDI/制御（SPは子階層）|
|host/commands|242|104|246|192bit編集palette、検査/選択|
|commands/fill|231|277|472|FILLとCOPYを共有する矩形engine|
|core/display|532|0|287|held/active palette各192、scanout制御/色選択|
|display/fetch|539|18|567|512bit line buffer、drain/アドレス制御|
|core/memory_ctrl|1219|18|1492|TX512、RX512、mask64、CA/分割/FSM等|
|core/scheduler|12|0|33|owner保持・要求選択|
|core/pcm_port|88|20|50|32bit cacheとbyte応答|
|core/cursor|424|75|311|位置/色/CDC/overlay。bitmap子はLUT4、BSRAM1|

ネットリストprimitive再集計でもline_fetchはDFFR3＋DFFRE536=539、controllerはDFFR4＋DFFRE1215=1219、schedulerは12で一致する。**512bit保持が複数あることは観測だが、schedulerに512FFや3入力512bit MUXがあるという主張は否定される。** `core` は書かないscanout/PCMにも同じhost_wdata/maskをbroadcastしている。

`tx>>16`、`buffer>>32` は固定シフトであり、一般の512bit barrel shifterと呼ばない。それでも各bitのload/shift/holdと制御配布が残る。RXはone-hot captureで可変書込みMUXを既に避けている。upload窓もFF512ではなく明示SP16個である。狭幅化による削減見込みはこれら既存対策を差し引く必要がある。

## 3. 192bitパレットCDCの再設計比較

### 3.1 現在の原子性と制約

commandsの編集palette192→scanoutのheld_palette192→pixelのactive palette192で、データ保持だけで計576bit。request/ACK toggle各2FF同期、sourceはACKまでhold、pixelは登録済みVBlankでpageとpaletteを同時commitする。一度に1 PRESENT。commands/CSRは実行中の次commandを書き換えない。resetは両domain同時assertを前提とし、解除はcoreでdomainごとに同期する。

10nsはper-color同期器の保証ではなく**bundled-dataの到着上限**である。SDCはpalette専用でなくsystem↔pixel全体へmax_delay10nsとcross-domain hold false pathを適用しており、他mailbox/FIFO Gray pointerも影響を受ける。STAのrequiredにはPLL/clock latencyが入り、単純な「route<10ns」ではない。物理制約として維持しつつ、受信イベントまでの最短時間、payload launchとのskew、同期器初段/次段、reset位相、Gray pointerのskewを経路ごとに別レビューする。2FFやASYNC_REG属性だけでデータ一貫性/MTBFを証明しない。現制約が安全性証明を全て代替するとも主張しない。

### 3.2 比較表

データbit数は制御・FF化されるMUXを除いた構造見積り。LUT/CLSは新規合成未実行のため未確認。

|方式|データ保持/概算|配線・追加費用|判定|
|---|---|---|---|
|A 現行維持|576bit＋既存制御、BSRAM0|CDC192本。新規FF0。全384位置/全対STA取得後なら再割当てを検討可能|低機能リスクだがsystem5違反は残る。局所交換失敗済み、無根拠な追加固定は勧めない|
|B PRESENT時に16色送信|編集192＋snapshot192＋pixel shadow192＋active192＋mailbox16=784bit程度|現行比データ+208bit＋index/handshake/FSM。192→16本でも16:1 RGB選択/受信decode追加|素朴案は面積悪化、VBlank直前要求が次フレームへ遅れる|
|B' source snapshotを除去|編集192＋shadow192＋active192＋16=592bit程度|現行比+16bit＋制御。PRESENT中編集禁止を流用|FF大幅減ではない。転送開始がPRESENT後なら同じframe問題|
|C pixel二重bank|pixel384＋system編集192＋mailbox16=592bit程度（snapshot省略時）|bank read選択/書込decode、bank整合維持。snapshot追加ならさらに192bit|原子切替は容易だがFF節約は自明でない|
|D 事前差分転送＋shadow/active|pixel shadow192＋active192＋mailbox16=400bit＋制御。system編集192を残す版は592bit|palette commandごとに転送してACK後command完了。PRESENTはpage/toggleのみ|狭幅CDCの第一候補。system側編集を除けば現行比データ−176bitだが内部API変更が必要|
|D RAM版|shadow/activeを小型RAM/二重bank、mailbox16＋制御|原理的には1 BSRAMに収容可能。read latency/enable/modeの検証、FF→RAM推論保証が必要|FF/広域配線を減らす仮説。BSRAM1の消費とpixel pipeline再設計を伴うため初回に混ぜない|

### 3.3 推奨する事前転送プロトコル（将来の独立実験）

1. resetでpixel shadowを `fff_eee_..._000`、activeを現行と同じ0に初期化。初回boot PRESENTはshadow初期化済みを確認してから許可する。RAM版なら16色初期化FSMとready交換が要る。旧topのboot用192bit定数palette選択を同じ初期化契約へ置換する。
2. PALETTE命令を検査後、system側16bit `{index, RGB444}` を登録しupdate toggleを反転。ACKまでこのpayloadを固定。pixelは2FF同期したtoggleを検出し、shadowの1色だけを書き、ACKを反転/一致させる。systemは2FF ACK確認後に既存tag/error付きPALETTE完了を返す。
3. PALETTEは表示activeを変えない。既存の1 command outstandingを流用し、転送中のSUBMIT/編集はBUSYとして拒否。別の深いqueue/FIFOを追加しない。連続16命令は順に完了させ、更新0件のPRESENTも許可する。
4. PRESENT受付時点で全PALETTE転送は既に完了している。sourceはpageをholdし、従来のpresent toggle同期・VBlank判定・ACKを使う。同じpixel edgeで `active_page<=held_page; active_palette<=shadow` とする。shadowはPRESENT ACKまで不変。line0要求のpage選択/generationを現行と同時に更新する。
5. ACKは転送完了ACKとPRESENT commit ACKを区別する。shadowに届いただけでPRESENT DONEにしない。PRESENT待ち中に次paletteを受け付けないため16色のsnapshot世代が混ざらない。次PRESENTは旧ACKがsystemへ戻ってBUSY解除された後だけ受理する。
6. 共通resetでpending/seen/toggle/ACKを初期値へ戻し、初期化ready交換前は受理を禁止する。単独domain reset対応を暗黙に追加しない。必要ならepoch付き再同期を別仕様にする。途中reset後に旧ACKを新requestへ誤適用しない。

54MHz=18.519ns、74.25MHz=13.468ns。保守的な機能モデルとしてrequest検出最大3 pixel edge、ACK最大3 system edge、送出/受信処理各1 edgeを見込むと、1色およそ0.10〜0.15µs、16色逐次で約1.6〜2.4µs（実FSM次第）。転送量は極小だが、**PRESENT後にこの時間を追加するとVBlankを跨ぎ最大1 frame遅れ得る**。平均が短いことは互換性の証明にならない。事前転送ならPRESENTのaccepted→commit→ACK境界を旧版とcycle比較できる。

PALETTE完了レイテンシは旧版より延びる。ABIは固定cycle応答を規定していないが、状態/タグ/エラーと「shadow変更完了」を維持し、driver timeoutを確認する。内部module単体APIが任意のpresent_paletteを毎要求に渡せる性質は変わるので、システムABI互換とmodule cycle互換を混同しない。bootおよび単体テストに明示adapterが必要。

### 3.4 二重bankの落とし穴

bank swap後、旧active bankは最新の編集paletteと一致しない。次frameで1色だけ差分更新すると他15色が古いままになる。対策は (a) 毎回全16色を非表示bankへ再転送、(b) ACK後にactiveからinactiveへ16色copyし、その間palette更新をbackpressure、(c) 全更新を両bankへ適切な時期に複製する、のいずれか。各bank valid/epochまたはdirty bitmap16bitが必要になる。shadow→active並列copy方式はこの追随問題がないが、pixel内192bitのcommit/CE配布が残る。CをB/Dより自動的に有利とは評価しない。

制約変更なしの16bit bundled mailboxでも全payload/setup/hold検査と同期器配置を必要とする。RAM CDCならdual-clock RAMのポート衝突/所有権/読出しlatencyを証明し、新endpointに適切な制約を与えることが別条件になる。広域false path追加でCDC違反を消す方法は採用しない。

## 4. 512bit並列データパスの再設計比較

### 4.1 クライアント別に残す状態・なくせる状態

|対象|現在の実体|32bit化で狙うこと/残るもの|
|---|---|---|
|upload/download/CSR|16個のSPに各32bit、DI選択512bit、64bit window_groupとbyte選択|16×32bit一斉アクセスを1個の深さ16以上の32bit RAMへ集約する仮説。byte write保持。16 SP→1なら15 BSRAM回収可能だが、ABI byte応答の遅延とBLIT captureを再設計する必要|
|controller TX|512bit shift、mask64bit|32B staging RAMまたは事前充填FIFOから16bit DDR pairを供給。512FFを消すには並列adapterを残さないこと|
|controller RX|512bit one-hot捕捉＋slot32bit|16bit pair→32bit beat、ownerへ配送。host/BLIT保存先を統合して初めてRX512を除去できる|
|arbiter|owner/last_owner、要求選択。WRITE busはbroadcast済み|req descriptorとbeatのownerを一致。幅だけで512bit×3のMUX削減とは数えない|
|scanout|64B受信後512bit bufferを16回shift、line RAMへ80words|受信beatを非表示line RAMへ直接write。完了前のline公開を禁止|
|FILL|color4bit反復で512bit生成、edge_data32bit、mask64|生成データは元から定数複製。512FF削減とは数えない。beat位置からmaskを生成しnibble端は32bit RMWを保持|
|BLIT/COPY_RECT|FILL engineを共有し、READをupload窓へcaptureしてからWRITE|source chunkの保存は必要。窓を共有し続ければ専用FIFOを増やさずに済む。overlap方向を保持|
|PCM|1word要求、cache32bit、byte応答|既に狭い。32bit streamと自然に合うがdeadline/flush/errorを変えない|
|初期化|topが64B zero WRITEを順次要求、両page＋PCM領域、初回PRESENT|zero beat生成、230400BのFB初期化とPCM領域を保持。起動readyを早めて未初期化表示しない|

### 4.2 方式比較

|方式|FF/BSRAM/LUT/CLSの見込み|配線/帯域/リスク|
|---|---|---|
|A 512bit維持|資源は既知。追加なしでも合法位置/局所制御の改善余地はあるが未測定|もっとも既存回帰を再利用できる。広域load/shift/hold制御とCSR選択が残る|
|B 64bit stream|beat8＋mask8。32B FIFOは4beats=256bit＋mask32bitで、32bit案と同容量|64Bを8beatsで搬送。PSRAMが16bit/clkなので1beat/4clk。幅を倍にしても外部帯域は増えない。32bit line RAMへ分解器が必要|
|C 32bit stream|beat16＋mask4。32B FIFOは8beats=256bit＋mask32bit。count/pointer/valid追加|64Bは16beats、外部は1beat/2clk。line RAM/PCMと一致。中間512保持を廃止できれば有望。ready網/owner制御を局所登録する|
|D 近傍adapterだけ|既存512保持＋stream FIFOを両方残すと純増しやすい|段階移行の足場。どの512保持を消すか指定しない案は採用しない|
|E 境界限定ハイブリッド|ABI64B、内部32bit、共有RAMへ段階集約。初回はline buffer512除去のみ|既存PSRAM pin timingを維持し、一度に変える範囲を小さくできる。最終CLS/LUTは仮説|

狭幅beat用skidを32bit＋mask4＋valid等で40bit程度とすると、各clientに2段×3clientを置けば約240FF、それにTX/RX stagingが加わる。既存512保持を残したままでは逆効果になる。64bit版は同じbeat深度なら約2倍だが、同じbyte容量なら大差ない。BSRAM1個の追加にも固定配置/ポート制約がある。全clientに独立FIFOを置かず、1 outstandingとowner固定を流用するのが有利という**仮説**である。

### 4.3 共通契約

- command descriptor `{write,addr,total_words,owner}` とdata beat `{valid,ready,data,strb,last}` を分離。`valid&&!ready` 中はpayloadを固定。strbを使うなら現行の「mask=1で禁止」との反転をadapterで明記する。
- PSRAMのCS Low中は任意ready stallを許さない。WRITEはchunk全体を事前bufferするか、供給をcycle保証する。READはchunk8word分の受入容量を予約してから開始。32bit/64bitの転送間隔を仕様にする。CSを途中で不用意に延ばす設計は別PHY評価になる。
- 32B境界は**絶対byte address**で分割。最大32Bでも非整列開始なら分割が必要。READはbeat順、partial word、lastの一致を検査。64Bは非整列なら3chunkになり得る。
- arbiterは最後のbeatではなく最終CS-high recovery後のdone/errorまでownerを保持。初回は現行の非preemptive64B論理要求を維持し、32Bごとの再仲裁を混ぜない。後者はPCM応答を改善し得るがfairnessとscanout/GPU割当ての別実験になる。
- BLITは同pageで下方向重なりなら下→上、同row右移動なら右→左。各chunkはsource全体を保存してからdest WRITEし、未読sourceを壊さない。32bit毎READ→WRITE交互にするだけではchunk内部overlapを破壊し得る。現行の偶数x/幅、src/dst同byte phase制約を保持する。
- atomic completionとは「全chunk終了後に一度だけtag/errorを返す」こと。メモリ全体の不可分更新/rollback保証ではない。途中WRITE errorで書込み済みprefixを戻せるとは言わない。他のwriterはcommand全体で直列化し、scanout/PCMのREADのみburst間介入を許す。
- READ成功前にdownload窓を公開しない。途中失敗は窓validを戻し、未完了のline bankも公開しない。resetでowner/beat/FIFO/予約を同時flush。既存PCM RESPONSE_TIMEOUT=4096を維持。新たなstream停止watchdogは内部abort/quiesceと対応させ、旧ABIにないエラーを無断追加しない。現controllerに独立timeoutが実装済みとは扱わない。

### 4.4 レイテンシの定量比較

system54で512bitを32bit busへ単純にserializeすると1要求16cycle（0.296µs）、64bitなら8cycle（0.148µs）。loadとdrainを完全直列化すれば往復32/16cycleが追加される。PSRAMは64Bのdataだけで32cycle（0.593µs）必要なので、適切に重ねれば32bitで十分だが、追加adapterを前後に直列配置すると性能低下がある。

scanoutは現行で1line=5×64B=320B、80回のline RAM書込みをREAD終了後に行う。直接streamならその80cycleの多くを外部READ data期間に重ねられる。ただし、これをそのまま659−80=579cycleの予測実測とはしない。split間、arbiter、line done、pipelineの位相が変わるからである。

フルFILLは1800個の64B、フルBLITは1800組のREAD/WRITE。1要求に32bit変換16cycleが完全追加される悪い実装では、FILL +28800cycle=0.533ms、BLIT +57600cycle=1.067ms。64bitならその半分。これは重なりなしの追加費用例であり最終性能予測ではない。FIFOを使った重なりの証明なしに「狭幅化は無料」としない。

## 5. PSRAM転送構造の比較

### 5.1 実機前提

H1の4B単独PASS、境界8Bの同開始READ偽PASS、境界後独立READの旧seed残存、300032の独立READ=`8A AC CE F0`を確認した。32B wrap仮説は強く支持される。元64Bにはwrap予測との差16B/46bitが残り、実ダイ、CA[45]、READ/WRITEどちらの残差か、外部timing/PVTは未解決。

既存32B splitは絶対境界で切り、TX/mask shiftとRX slotをchunk間で継続する。2つ目の512bit bufferは追加していない。既存48件＋統合12件＋controller272caseは既存記録でPASSだが、STA不合格かつ実機未投入。これはpin-levelの正しさの証明ではない。

### 5.2 RTLからのcycle計算

以下はINIT/CONFIG、arbiter、clientの待ちを除き、`valid&&ready` を受けたedgeから`done` edgeまでの**計算値**。LAT=14、RDL=6、CS_HIGH_CYCLES=2を固定。CA3cycleはLAT内に含むので二重加算しない。

split版：word数W、絶対32B境界で分けたchunk数kに対し、

`Twrite = 1 + 2W + 18k`、`Tread = 1 + 2W + 24k`。

CHECKの1cycle、各PREPARE1、TRANSFERのtick0..last（last+1cycle）、GAP2を数えた。既存テストの「最大106cycle」は観測側のedge数え方/ハンドオフを含み得るため、105の式と混同しない。将来は同じaccept/done edgeで比較する。

|要求|chunk|WRITE cycle|READ cycle|WRITE/READ理想サービス帯域 MB/s|
|---|---:|---:|---:|---|
|旧64B連続（実機不適合）|1、旧PREPAREなし|50|56|69.12 / 61.71|
|64B、32B整列split|2|69|81|50.09 / 42.67|
|64B、word整列だが32B非整列|3|87|105|39.72 / 32.91|
|32B、32B整列split版API|1|35|41|49.37 / 42.15|
|32B、32B非整列|2|53|65|32.60 / 26.58|
|4B PCM|1|21|27|10.29 / 8.00|

単位MB/sは10^6B/s。これは54MHz×byte/Tであり、実機保証やホスト帯域ではない。native32B版はPREPARE統合が可能なら1cycle減り得るが、タイミング悪化との交換であり未測定。

|方式|line fetch（320B）のcontroller部分|PCM/GPUへの影響|
|---|---|---|
|1 64B要求＋split|5×81=405cycle、10回CS/CA|現行論理grant中は最大3chunk保持。互換性/回帰再利用が高い|
|2 32B論理要求|10×41=410cycle、10回CS/CA|各32Bで再仲裁するならgrant overhead増。最大占有は短くなるが割当て比率は別設計|
|3 32/64bit stream＋split|stallなしなら1/2と同じ物理data/CS数|read/drain重ね合わせが利点。FIFO未充填/ready停止は別の待ちを生む|
|4 64B linear利用|仕様上安全なら旧構造の50/56が参考、line5×56=280|追加CSを省けるが現ダイ/設定では利用可能性未確認。現在の成立性判定の前提にしない|
|5 公式IP|user/PHY clock比、burst/ready/calibrationが異なるため未算定|54MHzの現controller cycleをそのまま適用できない。独立診断とadapter見積りが必要|

32B nativeでも絶対境界分割が必要。64B logicalのままでも最大3chunkに限定できるため、ABIを変える必然性はない。stream化とlogical request長変更は別の変数である。

### 5.3 映像・PCM・GPU予算

720pは物理1line=1650/74.25MHz=22.222µs、2lineの論理行=44.444µs=2400 system cycle。既存テストの1920cycleはガードを持ったより厳しいdeadlineであり維持する。VBlank45物理line=1ms=54000system cycle。60Hz、FB1page=115200B、2page=230400B。

平均scanoutは115200×60=6.912MB/s。2ch PCMが各48kHz・8bitなら有効音声データ96kB/s。連続4B cacheが効けば毎秒24000回×27cycle=648000cycle/s、約1.2% controller時間。cacheが全く効かない上限例は96000回で約4.8%。prefetchの準備/loop/flush/arbiter待ちは別途加算する。HDMI48kHz音声のpacket処理自体はPSRAM帯域ではない。

映像のsplit READサービスだけなら1800×60×81=8.748Mcycle/s、54MHzの16.2%。line drain80×360×60=1.728Mcycle/s（3.2%）と制御/競合が現方式に加わる。平均帯域は成立を否定しないが、**deadlineは平均から保証できない**。

E3/E4の既存回帰記録：line飽和659、contention612、host BLIT競合827/832cycle、PCM最大186cycle。最大832でも1920の43.3%。PCM4096cycle timeoutは75.85µs、実測186は3.44µs。ただし列挙した刺激の最大であって任意のstream stallに対する形式的上界ではない。現arbiterではscanoutが連続要求中のGPU starvationもあり得るため、有限のline要求列/空白期間を含めてGPU進捗を検査する。

full FILL130200cycle=2.411ms、full BLIT289809cycle=5.367msはsplit版の既存simulation実績。controller時間だけの下限例はFILL1800×69=124200（2.300ms）、BLIT1800×(81+69)=270000（5.000ms）。32B nativeで毎回同じ準備をするとFILL3600×35=126000、BLIT3600×(41+35)=273600で、要求数倍増だけでは速度改善しない。共通仮定は整列full-frame、孤立実行、既存LAT/RDL。競合/PVTを含む実機性能ではない。

### 5.4 公式IP・linear/hybridの扱い

公式一覧はPSRAM Memory Interface 1.2、HS系等を掲載し、EULAを必要とする。監査環境のStandardインストールには `IDE/ipcore/PSRAM_HS/psramhs.ipspec` があり、label HS、version **2.1**、GW1NR-9を除外しないdevice filterを確認した。これは生成済み9K/QN88Pの動作証明ではない。公開一覧の版、IP識別版、マニュアル版は一致するとは限らない。[Gowin公式IP一覧](https://www.gowinsemi.com/en/support/ip/?page=17)

IPUG943-1.5EはGW1NR-9 C6/I5の例、初期化/校正と1:2 clock構造、暗号化RTL・非暗号化top/parameter・reference designの配布を記載する。例の1004LUT/620REGは幅/構成が異なり、本体置換後の純削減値には使えない。特徴欄とreferenceに異なるWinbond型番が現れるため、どちらも実ダイ同定の代わりにはしない。オープンな内部RTL全体の入手性は確認できない。[Gowin IPUG943-1.5E（§2〜4、9）](https://www.gowinsemi.com/upload/database_doc/2096/document/69b8610d60cca.pdf)

今回IP生成やlicense checkoutは実行していない。**QN88Pでのsingle die選択、54MHz制約、現インストール版のパラメータ適合、追加費用/再配布/商用条件、利用可能なsimulation modelとVerilator対応、追加clock/SDC/PHYの資源は未確認。** 公式IPは外部タイミング/初期化の有力な比較対象だが、既存ABI/STA/実ダイ問題を自動解決しない。初期化定数だけ暗号化IPから推測して移植しない。

参照W955D8MBYAではCR0=8F1Fのwrap32B解釈、memory CA[45]指定が現RTLと一致しない点が既存調査に残る。一般HyperBusのlinear bit解釈を実ダイへ流用しない。CR0/CA[45]/hybrid変更はID/CR実読出しとメーカー確認後の別診断案件とする。

## 6. 音声・カーソル・BLITの維持可能性

**音声：** Phase 1は選択条件の先行登録を帰納不変条件＋100万pixelの旧新版比較（VIC1/VIC4）で検証し、pixel内部違反を0にした。再設計の対照へ保持する合理性がある。ただし全体STA不合格の候補であり採用品ではない。ACR優先、due-edge、ASP4sample、take_audio/sample_ready、header/sub、InfoFrame、CTS/N、frame_baseを毎edge一致させる境界として維持する。stream化でaudio packetのcycleを変える必要はない。48kHzの音声FIFO、6ch synth、2ch PCMは残す。

**cursor：** bitmapは2bank×256B=512B、BSRAM1。親424REG/75ALU/311LUT＋子LUT4が観測された階層費用。36bit色/位置mailbox、座標演算、透明overlay、4cycle lookaheadを保持する。PSRAM帯域を消費しない。現Phase 2の上位負slackにcursorがないことは確認できるが、余裕保証ではない。削除すればbitmapと専用制御は不要になるが、背景RGB遅延の代替FF、CSR応答/能力bit等が残る。**何CLS減るかは未測定**。

**BLIT：** 方向/位置計算、sourceアドレス、COPY状態、検査は専用だが、矩形/row計算、mask、PSRAM要求、upload窓をFILL/hostと共有する。FILL engine全体231REG/277ALU/472LUTをBLIT削除額として扱うのは誤り。共有率をソース行数から出さない。専用64B copy FFが別にある設計でもない。BLIT削除によるCLS減は未確認。

将来の差分合成は、同じ入力/制約で (1) COPY disabled＋opcode stub、(2) cursor overlay/bitmapなし＋正しい背景遅延、(3)両方、を独立に比較する。専用coneと共有coneのprimitive差、BSRAM、control packing、P&R CLSを取り、単独差の和と複合差を混同しない。今回は実行していない。

フル機能の帯域予算にはまだ合理性がある。Liteの最初の検討候補は、ホスト側ソフトコピーで代替可能なBLITを外しcursor/音声を維持する構成。ただし削減額未測定であり、GUI性能悪化・能力bit/ABI応答の変更を伴う。cursorを外すと移動ごとにFB修復/再描画とPSRAM負荷が増えるため、bit数だけで優先しない。音声削減も現時点では根拠不足。

## 7. アーキテクチャ案A〜Dと追加案Eの比較

以下の資源変化/工数は明記した観測以外すべて**仮説/計画概算**。人週は1名の設計・検証作業で、実機原因調査の長期化は含めない。

|項目|A 局所改善継続|B paletteのみ|C palette＋全内部stream|D Lite|E 段階hybrid（推奨）|
|---|---|---|---|---|---|
|対象STA|palette配置、TX/CSRを個別修正|palette9本の広域CDC|palette＋TX/RX/CSR/制御配布|削除cone次第|初回はline保持/配線圧力、後続でpalette/TX/CSR|
|残る違反|一箇所改善で他へ移る実績|system5件を直接解決しない|新ready/FIFO/owner経路が発生し得る|削除外palette/systemが残り得る|初回はpalette9＋system5の直接原因を残す|
|予想資源|論理増分0の配置案もあるがCLSは変動|素朴案FF増、Dはデータ−176bit＋制御|広域保持を消せれば減、adapter/FIFOで増もある|削除差分合成までCLS不明|初回512FF削除−tap/制御追加、最終値未確認|
|配置自由度|固定LOC増は周辺を拘束|CDC幅縮小仮説、pixel内部保持は残る|改善余地大、BSRAM位置/ready網制約|空間を作れる仮説|小さな変化を測って段階拡大|
|機能互換|保持しやすい|事前転送ならABI維持可能、PAL latency延長|ABI64B維持可能、内部cycleは変わる|機能/能力宣言変更が必要|フル機能/ABI保持|
|回帰再利用|既存全48目標|全48＋CDC/command更新|全48をoracleとして移植、一部TB wiring変更|削除機能テストをstub契約へ変更、全機能維持とは呼ばない|初回全48＋12＋272を維持する目標|
|新規TB概算|0〜2（経路修正次第）|3〜5、20〜40scenario|6〜10、80〜150scenario|2〜4＋差分ビルド3組|初回2、25〜40scenario、後続はB/C相当|
|開発/実機risk|開発小〜中、収束確率不明/PSRAM未解決|CDC・frame境界中/PSRAM未解決|大/PHY非変更でも整合性risk大|中/代替描画負荷とPSRAM未解決|初回中/PSRAM pin非変更でも実機未解決|
|工数概算|調査/1候補1〜2人週、上限を設定|2〜4人週|6〜10人週|削除効果評価1〜2、製品化別|初回1〜2、後続合計4〜8人週|
|段階性|一経路ずつ可能だが既に複数失敗|事前転送/保持削減/RAM化を別差分にする|全面同時変更は比較困難|一機能ずつ評価|高い、比較可能な差分列|
|撤退条件|全配置取得不能/合法案の効果不足/1候補不合格|原子性/旧frame境界不一致、費用増かつ物理改善なし|容量/期限/回帰/全配線不成立、利益を特定不能|実測削減不足、GUI用途に不適合|各段階の仮説否定ならその差分で停止・再監査|

回帰再利用「全48」は26FB＋22共通の既存機能仕様を残すという意味で、TBファイルを無修正で使える比率の実測ではない。内部stream化では接続adapterと期待latencyをレビューするが、外部pixel/PCM/ABI oracleやdeadlineを緩めない。12統合/272controller/driver15/QSPI4も別途維持する。

## 8. 最も有望な再設計案と理由

**案Eを推奨する。** 32bitはline RAMとPCM cache、controllerのword APIと一致し、外部16bit/clkの受信を2cycleごとに運べる。64bitが必要な帯域根拠は現時点でない。ホストの64B窓/命令はそのまま残し、UIから内部beatを意識させない。

最終像は、READ beat→ownerで配送→line RAMまたは共有upload/download RAM、WRITEは共有RAM/FILL generator→32B予約buffer→DDR pair、descriptor/owner→controllerの構造。512bitを往復させるのではなく、保存先へ一度だけ書く。ただしBLITにはsource保存、WRITEには供給保証が要るため「バッファなしstream」を目標にしない。

パレットはPALETTE commandごとの16bit事前転送→pixel shadow→VBlank active copyを別段階で評価する。system編集paletteを削除できればデータFF削減を伴うが、初回からRAM二重bank/phase変更/公式IPまで混ぜない。各段階のslack改善量は未測定であり数値を予言しない。

## 9. 最初に着手すべき最小実装計画

**以下は将来の実装計画であり、今回はRTLも実験モデルも作っていない。**

### 9.1 比較ベースと変更範囲

基準は32B分割＋音声Phase 1の保存入力。Phase 2の局所MUXはこの初回に含めず、全体WNSが良かったPhase 1を対照にする（不採用候補の製品昇格ではない）。Phase 2は補助比較としてのみ用いる。同じHEAD表示でも内容が違うため、E3のcontroller/audio patchと全manifest/hashを確定してから開始する。

独立branch例 `eval/rx32-scanout-01`、独立worktreeを新設し、元worktree/既存buildを上書きしない。今回branch/worktreeは作成していない。製品統合は受入基準達成後の別段階。

|対象ファイル/module|将来の変更|
|---|---|
|`rtl/fb/kagura_fb_burst_ctrl.sv`|既存READ捕捉に32bit word tapを追加。CS/CA/tick/LAT/RDL/split/既存rdata/doneは固定|
|`rtl/fb/kagura_fb_arbiter.sv`|WAIT ownerがscanoutのときだけtapのvalidを配送。owner/FSM/req_ready/rsp_doneは同一cycle|
|`rtl/fb/kagura_fb_core.sv`|sys-domain read_word/data_valid/errorの配線追加。clock/CDC/PCM/音声不変更|
|`rtl/fb/kagura_fb_scanout.sv`|fetchへのword配線。palette/line要求/ACK/表示pipeline不変更|
|`rtl/fb/kagura_fb_line_fetch.sv`|buffer512と16cycle DRAINを除去し、READ中にwordを非表示line RAMへwrite。bank公開は全受信＋既存done後|
|`sim/experiments/`等（将来追加）|単体word tapモデルと旧新版比較TB。製品manifestに入れない|

初回はhost/BLIT/PCMの旧512bit rdata APIとcontroller RX512を残す。したがってcontroller RX512削減やupload BSRAM削減を初回成果として数えない。

### 9.2 前後フロー・状態とレジスタ

変更前：PHY pair→controller RX512→done→line fetch buffer512→16cycle drain→line RAM。これを5回。

変更後：PHY pair→16bit前半保持＋次pairで32bit word形成→scanout word valid→line RAM。controller RX512/既存doneは並行して従来どおり生成し、他clientからは同じに見える。

word tapはcapture_enableの既存有効pairだけを使い、half_validとhalf16、word32/valid、burst word index（4bit程度）を追加する。32B split間もword順を維持し、gap/CAのpairを混ぜない。各chunkはword境界で終わる。追加状態の目安は50〜64FF＋小規模制御で、**512bit削除との差は約448〜462FFという構造上の仮説**。mapping後のREG/CLS/LUT差は未確認。旧bufferのload/shift/hold選択が消えるが、567LUT全体が消えるとは数えない。

line fetchはIDLE/ISSUE/RECEIVE/WAIT_FINALのようなFSMとし、burst0..4、word0..15、総書込0..79を管理する。word valid時に `bank_addr=burst*16+word` へwrite。readyは開始時にline RAMの所有権/空き容量を確保できることを条件とする。初回内部tapはstall不可のvalid/dataとして契約し、一般ready付きstreamへ拡張する場合も「予約済みchunk中は必ずready」をassertする。

すべての16wordsを書いてから該当rsp_doneを受け、最後のburstで初めてfetch_doneを返す。rsp_error/word数不一致/resetなら途中書込みがあってもbankを公開しない。final wordとrsp_doneが同cycle/前後する場合を明示処理する。line bankへ途中データを書けることは所有権で保証し、表示中bankへ書かない。

### 9.3 cycle等価性とABI

厳密一致する境界：controller accept→CS/CA/CK/DQ/RWDS OE/tx timing→done/error/rdata、arbiterのowner/req_ready/rsp_done、host/BLIT READ captureとWRITE acceptance、ACR/ASP/audio FIFO境界、pixelのpage/palette commitとPRESENT ACK。

変わってよい内部境界：非表示line RAMへのwrite時刻、fetch次burst発行/完了の早期化。ただしline_request/公開tag/generation、pixel出力、deadline、エラー時非公開をoracleで確認する。line fetchが早く要求すると競合順が変わるため、全システムの同cycleメモリ要求一致を無理に要求しない。比較用に旧DRAIN相当の発行間隔を保持するモードを単体モデルで用意すれば、純粋なデータ保持差の検証もできる。実評価でその待ちを残すかは事前に一つへ固定する。

ABI1.2のcommand format/64B窓/完了tag/error/能力0x7f、BUSY保護、初期化を維持する。外部completionの最小cycleが仕様で固定されない箇所でも、READ結果有効化よりDONEが先行しないことを必須にする。

### 9.4 小実験モデルとテスト

最初にVerilatorだけで旧split controllerのpair captureを模したproducerと、新word tap＋line RAM sinkを結ぶ小モデルを作る。これはmapping/CLSを予測するツールではない。FF候補数/容量をソースと波形で棚卸しし、資源削減の実確認は後日の合成ネットリストで行う。

新規TB2本の計画：

1. `tb_rx32_tap`：全start word offset0..7×words1..16、READ/WRITE切替、pair順/byte順、32B split2/3chunk、gap/CA無効期間、resetを各capture位相へ挿入。read_dataとの全word一致、valid数/last/index、pin/既存done等価性を検査。
2. `tb_line_fetch_rx32`：5burst/80word、全360row/両page、owner交替、PCM/BLIT競合、最後wordとdoneの位相差、途中error、reset/再開始、line公開前のpartial data非表示。sink不readyは契約違反として検出し、黙ってdropしない。

シナリオ群は25〜40種類程度、offset×長さ等のパラメトリックcase数は別計上する。既存FB26/common22、wrap統合12、controller272、driver15/QSPI oracle4をすべて維持。特にtb_fb_boardの230400B初期化、BLIT overlap oracle、host READ completion、line contention、PCM timeout、HDMI VIC1/VIC4を省略しない。

### 9.5 評価順序と1回のStandardビルドの判定

1. 入力manifest/hashと差分範囲を固定。旧RTLとのpin/cycle等価モデル、word/ownership assertionsを先に通す。
2. 全機能回帰を実行し、既存deadline1920/4096とfull FILL/BLIT測定を保存する。公平性はline継続＋PCM飽和＋GPU進捗を同時に観測する。
3. その後に限り将来の許可範囲で、Standard V1.9.12.04、同device、同SDC/CST、Place1/Route2で**1回**の独立フルビルド。ゲート/seedを試行中に変更しない。
4. REG/LUT/ALU/BSRAM/CLS、消えたbuffer512と追加tap、owner/ready fanout、全配線、全clock WNS/TNS/違反、palette全192対、TX/CSR、pixel最悪経路を比較。上位25だけで不足なら保存済みdesignへのread-only report/exportを使い、観測のためにP&Rを繰り返さない。

**成功には二種類ある。** 仮説支持＝buffer512が消え、追加状態が限定的で、機能/期限を維持し、資源/配線の改善を実測。ただしglobal gate不合格なら製品採用は不可。製品採用可能＝後述の全品質ゲート達成。初回案が既知14違反すべてを直接消すとは予測しない。

**停止/撤退：** buffer除去不能、adapterが同等以上の保持を復活、BSRAM/制御追加で利益消失、unrouted発生、期限/等価性失敗、または全体WNS悪化に対する独立した改善証拠なし。この候補を不採用にし、次の案を同じビルドへ継ぎ足さない。改善仮説が支持されてもgate失敗なら次段階へ進む判断資料として報告し、再設計全体の達成扱いにしない。

## 10. STA・CDC・実機検証の品質ゲート

採用条件は以下を**すべて**満たすこと。

- Gowin Standard V1.9.12.04、GW1NR-LV9QN88PC6/I5、setup≥+0.100ns、setup/hold違反0、全配線完了。recovery/removal等のnegative analysisも残さない。tool exit0/bitstream生成だけではPASSにしない。
- SDC/CSTは維持を基本とする。新interfaceの制約到達/名前変更を検証し、既存max_delay対象からpayloadが落ちていないことを確認する。10ns緩和、広域false path化、clock変更による見かけ合格は禁止。
- CDCのrequest/data/ACK最短関係、同期器配置、payload hold、reset/epoch、Gray pointer skew、RAM所有権を再レビュー。新RAM/別protocolで制約変更が要るなら独立の安全性証明とSTA対比を必須にする。
- 既存Verilator機能回帰全維持。新しい内部latencyを理由にpixel/ACR/ASP/ABI完了や1920/4096 deadlineを弱めない。
- **内部STA合格と外部PSRAM I/O保証を別判定する。** 現SDCは外部I/O仕様が未完成である。CS/CA/DQ/RWDS/CK pad timing、read捕捉、固定LAT/RDL、power-up/reset、電圧/温度/個体差を測定/仕様照合する。
- 元64Bの残差16B/46bitを別途解消。独立address READ、全32B offset、mask、隣接guard、長さ、パターン/反復を使い、同一開始READの偽PASSを避ける。
- 合格候補だけを段階的実機評価へ進める。PSRAM独立診断→初期化/静止HDMI→PRESENT/palette→cursor→FILL/overlap BLIT→PCM＋6ch/HDMI音声→連続競合/長時間。各段階の表示/音声/データを別記録する。不採用bitstreamの昇格はしない。

今回これら実験を実行する承認や実機操作を求めていない。これは後続作業の受入条件である。

## 11. 未解決リスクと撤退条件

|未解決事項|次に必要な証拠|判断への影響|
|---|---|---|
|384FF全配置/局所混雑/全palette STA|保存placed designの正式export、source入力/capture出力も含むreport|局所配置Aの最終否定はまだできない|
|FF削減がCLS削減になるか|差分合成＋同条件P&R|共有制御/packingによりFF減がCLS減にならない可能性|
|palette小幅化の利益|D事前転送のnetlist/FF/制御/全STA|192本削減だけでは面積改善と断定できない|
|TX/CSR5違反|state負荷/DI/選択coneの詳細、局所配置とfanout|scanout RXだけでは直接未解決|
|pixel残余余裕|全clock STA、packet/line制御の再確認|新bank選択/同期read追加で壊れ得る|
|実ダイ/CA45/CR0/linear|メーカー・ID/CR・pin波形の独立診断|設定変更を修正扱いできない|
|追加16B/46bit破損|READ/WRITE切分け、外部timing/PVT|全内部再設計が成功しても実機不合格は残る|
|公式IPの条件/Verilator/資源|現版生成情報、EULA/ライセンス確認、独立評価|採用可否/工数/再配布に影響|
|Liteの削減量|BLIT/cursor個別差分合成と配置|未測定のCLS削減を根拠に機能を捨てない|

全体としては、(1)複製保持を除去しても必要制御/バッファで面積が戻る、(2)palette/TX/CSRを個別改善しても同条件全配線・全clock STAが成立しない、(3)GUI/PCM期限がfairness下で成立しない、(4)外部PSRAMを仕様保証できない、のいずれかが独立実験で続けば9Kフル機能案を再判定する。試行回数上限は段階ごとに事前固定し、不合格に次差分を重ねる探索をしない。

その際、LiteはBLITのみ削除の差分効果をまず測り、cursor/音声を保持する候補と比較する。BLIT削減額が足りなければ、cursor削除/音声縮小を自動採用せず、GUI用途の価値と代替処理負荷を比較する。必要なら機能を維持できる上位FPGAへの移行も別の合理的結論となる。現時点で最小削減構成の9K合格を保証する証拠はない。

## 12. 最終推奨

**「データフロー変更でフル機能KAGURA-HDをTang Nano 9Kへ成立させられるか」への回答は、現時点では未証明、ただし段階的に検証する合理的な道はある、である。**

成立を否定しない根拠は、分割後の既存機能回帰とline/PCM期限余裕、実在する512bit複製保持、upload窓の極端なBSRAM分散、構造変更で実際に解消した音声/入力違反である。成立を断言できない根拠は、97.8%のCLSと制御packing、配置の非局所性、palette直接配線9件とsystem5件の併存、外部I/O未保証・残差破損である。

したがって、局所RTL/P&R探索だけを繰り返す案A、素朴な16bit化、全機能の一括書換え、未測定のLite削減を今すぐ採用しない。**案Eのscanout RX32単独実験を最初に評価し、結果を報告してからpalette事前転送と共有RAM化を独立に判断する。** その間も32B splitの必須性と音声Phase 1の機能成果を保持し、PSRAM仕様/外部timingの解決を並行した別の合格条件として扱う。
