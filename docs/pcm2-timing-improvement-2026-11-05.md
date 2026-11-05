> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PCM 2ch構成のタイミング改善評価

**最終結果：候補04はGowin Standard V1.9.12.04で内部実装ゲートPASS。Setup +0.160ns、Hold +0.484ns、違反0/0、配置・全配線完了、Bitstream生成済み。実機未投入・外部PSRAM I/O未確認のためrelease_ready=false。**

## 対象と保護

Gowin **Standard V1.9.12.04**、GW1NR-LV9QN88PC6/I5。PCM専用ABI 1.4の親は`build/audio-pcm2`、独立候補は`build/pcm2-timing-01`〜`04`。元のPCM2候補とRMW/RX32のSTA合格成果物を保存し、親ソース全体のSHA-256一覧で照合する。FPGA書込み、Flash/FW変更、Push/Merge/Releaseは実施しない。`release_ready=false`、`DO_NOT_PROGRAM.txt`を維持する。

親のStandard結果はSetup −1.234ns、Hold +0.484ns、Setup/Hold違反3/0、CLS 4215/4320、FF 5206、BSRAM 19。配置・配線完了はSTA合格を意味しない。

## 最初の候補01でSTAから選んだ変更

|経路|親のSetup|変更|
|---|---:|---|
|cursor held → position|−1.234ns|pixel側にfree-runningの62bit payload受信段を設け、描画位置レジスタの配置要求からCDC着地点を分離|
|HDMI cx → cursor logical_x|−0.624ns|cx/cyを局所登録し、1段分をlookahead 4→5で補償|
|copy_command → fill row_word|−0.033ns|既存DECODE/EXECUTE期間にY operandを登録し、descriptor選択muxと行アドレス演算を分割|
|cursor edit_bank → shape/error CE|+0.041/+0.088ns|各bankのlock/loaded検査を先に行い、結果を最後にbank選択|

Host windowの+0.094ns経路は今回変更しない。最終STAでは、この経路を含め全経路に同じ+0.100ns以上のゲートを適用する。悪化した経路や未達条件を省略しない。

受信段追加はrequest toggleの2段同期、vblank適用、ack、queued coalescingの順序を変えない。payloadはackまで保持される既存契約を使う。同期フラグだけで多bitデータの物理安全性を証明したとは扱わない。既存10nsのCDC上限制約を維持し、新しいfalse pathは追加しない。

座標補償は1650×750の連続走査とreset後のcounter=0を前提とする。任意にジャンプする座標入力に対する一般的な等価変換ではない。vblank検出は元のcx/cyを使用する。RGB出力レジスタとbackground経路は変更しない。

Y登録はfill engineへのoperandだけに適用する。16bit descriptor全幅の範囲検査、command FSM、応答latency、fill_burstそのものは維持する。

Controller/PHY、32B split、upload RMW、音声回路、SDK/ABI、PLL、SDC/CST、Place1/Route2は親と同一。

## PC検証

- cursor: 保護した親RTLをreferenceとしてCSR応答・IRQ・RGB・position/bank/visible/ackをサイクル比較。既存の独立RGBオラクルも維持。7,425,424画素PASS。bank交換、負座標、hotspot、coalescing、busy/range/partial-shape、warm resetを含む。
- 座標補償: 1,237,500走査位置とreset後初回のlogical pairを独立計算で全数比較しPASS。
- BLIT: 1,150ケースPASS。独立pixel oracle、byte phase、overlap、範囲・alignment、error/reset、46,341 interleaveを含む。
- command bounds: 1,222ケースPASS。不正要求がmemoryへ到達しないことを確認。

全FB、wrap統合、Controller、RX32、shared component、実top QSPI PCMの回帰結果および固定Standard実装結果は、完了後に以下へ追記する。

## 固定条件と評価ゲート

機能回帰PASS後に40入力をhash固定し、Standard Place1/Route2を1回実行する。SDC緩和・seed探索・別位相は行わない。Setup ≥+0.100ns、Setup/Hold違反0、負のRecovery/Removalなし、配置・全配線完了を内部実装ゲートとする。

内部ゲートがPASSしても、外部PSRAM I/Oのmin/max・PVT適合、HDMI/PCMの実機動作、Releaseは未確認のままとする。

## 候補01の実測結果

**不採用。** PC全検証はPASS、配置・配線とBitstream生成は完了したが、Standard STAはSetup −2.737ns、Hold +0.456ns、Setup/Hold違反73/0へ悪化した。

|項目|親PCM2|候補01|
|---|---:|---:|
|Logic|7776/8640|7790/8640|
|FF|5206|5305|
|CLS|4215/4320|4227/4320|
|BSRAM|19/26|19/26|
|Setup|−1.234ns|−2.737ns|
|Hold|+0.484ns|+0.456ns|
|Setup/Hold違反|3/0|73/0|

最悪経路は変更していないupload word RAM→window_write_wordである。scanout generation、palette CDC、PCM prefetch、Controller TX等にも未達が分散した。追加回路による配置変化・混雑感度を疑うが、これを唯一の原因とは断定しない。元の3経路が上位25件に現れないことだけでは、その3経路のSTA合格を証明できない。

Gowinの既定詳細表は上位25経路であり、73違反端点の個別詳細すべてを列挙したものではない。総違反数とraw STA reportを保存する。条件の悪い候補を除外・隠蔽していない。

候補01のBitstream SHA-256は`c619ea61d2730f92bb02face35fb7f9a67b7451395a6e3cac8f30e11cf0e9311`。投入禁止。

[PC証拠](evidence/pcm2-timing-01-pc-2026-11-05.json)、[Standard証拠](evidence/pcm2-timing-01-result-2026-11-05.json)、[rawログ](evidence/pcm2-timing-01-raw-2026-11-05.zip)。

## 縮小候補02

候補01の失敗を受け、`build/pcm2-timing-02`へ分離した。62bit受信段を位置情報26bitに縮小し、palette crossingとbank検査・更新回路を親に戻した。局所座標段とBLITのY登録は維持する。制約・配置配線optionを変えた再試行ではなく、追加状態・比較回路を減らす別RTL候補である。

cursor reference比較、全FB26件、wrap統合12件、実top QSPI PCMを再実行する。共通部品22件、Controller272件、RX32は候補01から結果継承し、該当依存ソースのSHA-256一致を別JSONで保存する。これらを候補02で新規実行したと表記しない。

候補02も**不採用**。配置・配線完了、Logic 7808/8640、FF 5269、CLS 4233/4320、BSRAM 19/26。Setup −1.863ns、Hold +0.506ns、違反41/0。親の3違反より悪い。最悪はread_result→upload RAM DIで、scheduler owner→Controller TXにも複数違反がある。cursor palette CDCは−0.874ns、sampled_cx[0]→logical_xは−0.695ns。追加段だけでは問題を解消していない。

Bitstream SHA-256は`5531e7c6cc3b677fc3a4211453682b20d28284deafc57034e67910dea9213571`。投入禁止。[PC証拠](evidence/pcm2-timing-02-pc-2026-11-05.json)、[Standard証拠](evidence/pcm2-timing-02-result-2026-11-05.json)、[rawログ](evidence/pcm2-timing-02-raw-2026-11-05.zip)。

## 最小候補03

入力座標段・payload受信段・bank検査変更をすべて外し、親からはlogical X生成とBLIT Y登録だけを変更する。Xは連続1650pixelの走査に合わせ、偶数pixelごとにincrementし824→0でwrap、cx=0で2へ再同期する。元の`((cx+4)%1650)/2`と全2,475,000位置で一致する。追加の位相補償は不要で、lookaheadは元の4のまま。

このカウンタ置換も連続720p走査が前提で、任意座標へのジャンプを許す一般インターフェースではない。reset中の内部logical値は旧RTLと異なる場合があるため、外部RGB・応答・適用edgeのreference比較でreset前後を含めて評価する。元のCDC経路をRTLで除去したものではなく、その合格は最終STAの実測が必要である。

PCコンパイルはLinux一時領域で実行し、元ディレクトリとの全保存対象ソース一致を確認してrawログを回収する。共通/Controller/RX32は02と同じ依存hash付き継承、変更影響下のFB/wrap/QSPI PCMは再実行する。

候補03は配置・全配線完了、Setup **−0.199ns**、Hold **+0.451ns**、違反**1/0**。Logic 7794/8640、FF 5222、CLS 4238/4320、BSRAM 19/26。親から最悪Setupを1.035ns改善し、違反を3→1に減らしたが、合格ではない。

|残る+0.100ns未満の経路|Setup|
|---|---:|
|Host data_addr[5] → window_group[53]|−0.199ns|
|FILL current_byte[2] → row_word[7] CE|+0.030ns|
|FILL end_byte[1] → edge_data[22]|+0.044ns|

候補03はSetup違反総数が1件であり、既定の上位25件から上の未達・margin不足3経路を確認できる。元のcursor/BLIT経路は負のSetup違反ではなくなったが、未掲載の各経路の正確なslackは断定しない。

候補03 Bitstream SHA-256は`983590208f5bb29db4cf3703560f56bc0f43314bc6ee8f0d365ea10854b50d45`。未達のため投入禁止。[PC証拠](evidence/pcm2-timing-03-pc-2026-11-05.json)、[Standard証拠](evidence/pcm2-timing-03-result-2026-11-05.json)、[rawログ](evidence/pcm2-timing-03-raw-2026-11-05.zip)。

## 実測残余経路への候補04

03を保存して以下の3経路だけを切る。

1. upload groupの8bit one-hotを、data_addrの設定・自動increment・bulk capture・resetと同じedgeで更新する。1cycle遅れのfree-running decodeは使わない。64byte窓末尾の63→64も扱い、64以上への無効アクセスやbusy時の拒否条件は変えない。read groupはOR選択で既存window_groupへ登録し、CSR応答のedgeは維持する。
2. FILLの順方向/逆方向の行終端判定を既存WRITE_REQ以前の安定期間に登録し、WRITE_WAITのrow更新CEから加算・比較を分離する。
3. RMWの8個のnibble書換enableをgeometryが安定した期間に登録し、READ_WAITでは応答nibbleとfill_colorの選択だけを行う。非対象nibble、odd edge、byte maskを維持する。

状態追加は制御用17bitで、汎用queue、追加Shadow/Snapshot、BSRAMを導入しない。FSM状態・Host応答latencyを変えず、既存の空きcycleを利用する。Host窓の元RTLをreference化し、全応答と512bit upload内容をサイクル比較する。全FB/wrap/QSPI PCMを再実行し、共通/Controller/RX32は変更なしの依存hash付き継承とする。

## 最終評価：候補04

|項目|親PCM2|01|02|03|04|
|---|---:|---:|---:|---:|---:|
|最悪Setup ns|−1.234|−2.737|−1.863|−0.199|**+0.160**|
|最悪Hold ns|+0.484|+0.456|+0.506|+0.451|**+0.484**|
|Setup/Hold違反|3/0|73/0|41/0|1/0|**0/0**|
|CLS /4320|4215|4227|4233|4238|4247|
|FF|5206|5305|5269|5222|5239|
|BSRAM /26|19|19|19|19|19|
|配置・配線|完了|完了|完了|完了|完了|
|内部実装ゲート|FAIL|FAIL|FAIL|FAIL|**PASS**|

04はLogic 7796/8640、IOLOGIC 28/97。Recovery +10.012ns、Removal +0.542ns、負の解析なし。最悪Setupはcursor held_colors[0]→pixel_colors[0]の既存bundled-data crossingである。+0.100nsゲートに対する余裕は0.060nsであり、大きな余裕があるとは扱わない。既定上位25件に+0.100ns未満の経路はなく、総Setup/Hold違反も0/0である。ReportOnlyではない数値ゲートの実行も終了コード0。

親からの最終production RTL差分は4ファイルのみ。

- `rtl/fb/kagura_fb_cursor.sv`：logical Xを連続ラスタカウンタで生成。
- `rtl/fb/kagura_fb_commands.sv`：既存DECODE/EXECUTE期間でengine Yを登録。
- `rtl/fb/kagura_fb_registers.sv`：アドレスと同edgeでupload groupのone-hotを更新。
- `rtl/fb/kagura_fb_fill_burst.sv`：行終端とnibble patch maskを早期登録。

01のpayload受信段・bank並列検査、02の入力座標段は最終候補へ残していない。音声・Controller/PHY・clock/SDC/CST・SDK/ABIは親と同じ。最終追加FFは合成実測33で、03からは17増。BSRAMは追加していない。これは01/02の悪化と03/04の改善を比較した結果であり、各局所変更のslack寄与を個別に一意分離したものではない。

PC検証は重点5件、FB全26件、wrap統合12件、実top QSPI PCMを再実行しPASS。cursor約742万画素とHost窓の元RTLサイクル比較、独立pixel・stereo sample oracleを含む。共通22件、Controller272ケース、RX32は01で実行した結果を依存hash一致で継承。旧PCM2のmixer・endpoint・SDK検証は、音声/SDKソースを変更していないことを親manifestで確認して継承する。未実行の新規実機試験をPASS扱いしない。

成果物：

- ソース：`build/pcm2-timing-04`、固定入力：`build/pcm2-timing-04/build/standard-timing-04/inputs`。
- Bitstream：`build/pcm2-timing-04/build/standard-timing-04/impl/pnr/kagura_fb.fs`。
- SHA-256：`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。
- [PC監査・依存hash](evidence/pcm2-timing-04-pc-2026-11-05.json)、[Standard STA・資源・入力manifest](evidence/pcm2-timing-04-result-2026-11-05.json)、[rawログ一式](evidence/pcm2-timing-04-raw-2026-11-05.zip)。

## 採否と残る確認

候補04を**内部STA合格のPCM2評価候補**とする。元のSTA合格RMW/RX32と旧候補を置換・Mergeしていない。実機書込み、Flash/FW/filesystem変更、Push/Merge/Releaseは実施していない。全候補のDO_NOT_PROGRAMを維持し、04も`release_ready=false`。

外部PSRAM I/Oのmin/max・PVT適合、PCM/HDMIの実機取得、実機復旧確認は今回未実施である。次の実機試験では、この新しいSHAを明示した評価計画・投入許可が必要であり、以前のRMW Bitstreamだけを許可したキャンペーン承認へ読み替えない。
