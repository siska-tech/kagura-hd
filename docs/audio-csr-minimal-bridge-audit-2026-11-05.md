> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 音声Host CSR比較監査・最小ブリッジ案（2026-11-05）

## 結論と作業停止

KAGURA-9には要求されている6ch設定とPCM 2ch制御が既に存在する。今回のHD案は音源機能の新規開発ではなく、既存音源へのHost接続である。それに対して専用generation、IRQ、error bank、COMMIT FSM、待機処理を追加したため、最小構成から外れている。推奨は **既存audio_registersを一度だけ接続し、INDEX/DATAの2 CSRと既存タグ付きコマンドによるCOMMITを提供する案**。BSRAM化の必要性は現時点では立証されていない。

本監査ではRTLを変更していない。合成、配置配線、Bitstream生成、実機操作、Mergeも行っていない。動作中のビルドは確認されなかった。省資源化途中のRAM_READBACK変更は未検証の作業状態として保存し、採用しない。直前の試験起動はshellのCRLFによる`pipefail`エラーでコンパイル前に終了しており、RAM案の検証結果ではない。

**注意:** 既存実装報告の「最終ソースは05と一致」「次はBSRAM検討」は05保存時点の記述である。現在の未検証WIPへ適用できない。本監査が今後の方針を置き換える。

## 証拠と比較の基点

- KAGURA-9: ローカル`../Kagura`、HEAD `694a15ea641f86ddab4f2b11538fe4fa04a8742e`。RTL、C/MicroPython SDK、PCM demoを確認。
- 元HD: `build/upload-rmw-worktree`。HEADだけでは再現できないRX32/RMW差分を含むSTA合格構成を使用。
- 新案: `build/audio-host-csr-worktree`、branch `design/audio-host-csr-01`。保存済み03（通常Snapshot）、05（LOCKED_SNAPSHOT）と、停止時WIPを分ける。
- [ソースhash・保存済み合成内訳・保護hash](evidence/audio-csr-minimal-bridge-audit-2026-11-05.json)。raw SHAの違いは改行差を含む。K9と元HDのaudio_registers、pcm_control、pcm_prefetchはCRLF正規化後に一致。audio_synthはHD既存のnoise_zeroレジスタ化が差分であり、今回追加したものではない。新案のsynth/control/prefetchは元HDとraw SHAも一致する。

合成値は保存済みXMLを読み取った値であり、今回再合成した値ではない。最小案の物理実装結果は未確認である。

## 1. 機能の完全な分類差分

|機能|KAGURA-9|元HD|今回の新案|監査判断|
|---|---|---|---|---|
|6ch STEP/DUTY/左右GAIN/ENABLE/phase reset|Host操作済み|core入力あり、top固定|Host接続|既存機能の公開|
|wave length、noise period、master gain|Host操作済み|既存core|Host接続|既存機能の公開|
|INDEX/DATA、合法性・settings検査|既存audio_registers|同モジュールあり、top未接続|endpointに接続|必要な接続|
|Shadow/Snapshot、one outstanding、sample境界適用|既存|core適用機構あり|既存regs＋独立endpoint FSM|regsとcoreは再利用、外側FSMは統合可能|
|PCM START/END/LOOP/左右GAIN/ENABLE|2ch既存|core/control/prefetchあり、固定設定|Host接続|既存機能の公開|
|PCM PREPARE/STOP/CLEAR/STATUS|既存|coreポートあり|Host接続|既存機能の公開|
|音声commit完了|既存engineの順序制御＋apply_done|起動制御|専用16bit generation＋上位byteラッチ＋completed|専用保存状態は不要|
|IRQ/error|既存共通機構|既存GPU共通機構、音声集約あり|音声専用6bitイベント、error、追加status|重複管理を削除候補|
|Host応答制御|K9既存bus処理|HD既存request/response|第3 bank、pending/6cycle待機|必要な応答保持だけ残す|
|固定設定からの起動変更|既存Host初期化|bring-up固定音|無音起動＋Host設定|起動方針変更。音源の新機能ではない|
|LOCKED_SNAPSHOT|通常shadowとsnapshotを分離|既存regsは通常方式|05でshadowをsnapshotとして固定、BUSY DATA拒否|互換性変更。原則採用しない|
|RAM_READBACK|なし|なし|停止時WIP、readback RAM追加|未検証。必要性未立証|
|Host SDK|C/MicroPython、PCM demoあり|HD transport/GPU SDKあり|別Audio facade、generation待機|既存APIをtransport適応する方が小さい|
|Host wave RAM upload/bank swap|K9実装済み|topは固定ramp読出し|今回も未提供|完全なK9音声互換とは言えない|
|C音声SDKのHD適応|実装済みK9 API|HD固有API|今回の新規facadeはMicroPython中心|Cの移植完了を主張できない|

今回追加した音源演算機能はない。初期試案の重複PCM順序比較は02で削除済み。残る上位address幅検査はHD固有の安全対策であり、削除対象の汎用機能とは区別する。有限PCMのDONEをfault扱いしない集約mask修正も、Hostからone-shotを使うための整合対応である。

## 2. ABI・アドレス・コマンド順序の差

|項目|KAGURA-9|HD元構成／新案|
|---|---|---|
|ABIとHost幅|0.6、5bit CSR|1.2→新案1.3、6bit CSR|
|INDEX/DATA|0x0C/0x0D|新案0x36/0x37。HDの0x0C/0x0Dはdescriptorに属し流用不可|
|COMMIT|COMMAND 0x0Eへ0x04|新案0x38へ1。HD既存opcode4はPSRAM WRITEで流用不可|
|indexed ch設定|ch×0x10、STEP+0..2、DUTY+3、GAIN+4/+5、CONTROL+6、LEN+7、NOISE+8/+9|基本的に既存regsを再利用|
|indexed global|E0 master、E1 status、E2 error clear|同じ内部indexを利用可能|
|indexed PCM|60/80、stride20。START+0..2、END+4..6、LOOP+8..A、GAIN+C/D、CONTROL+E、CMD/STATUS+F|同じindex。ただしaddress意味は異なる|
|PCM address|Host絶対0x400000..0x7FFFFF、END排他で0x800000可、coreで相対変換|HDはdie相対22bit。0x400000という排他ENDは現core入力で表現不能|
|wave upload|0x9800+(ch−4)×256のHost shadow領域、commitでswap|同じ領域・経路なし|
|適用順序|既存VRAM FIFO内のAUDIO_SEND/WAIT|新案はGPU commandと独立したaudio FSM|
|次shadowの編集|前commit待ち中も別shadowへ書込み可|05はBUSY時DATA拒否。既存backendの書込み後idle待ち手順を移植できない|
|FENCE|共通engineの順序に従う|新案専用endpointのaudio完了はGPU FENCEでは保証されない|

PCM GAIN/ENABLEはAUDIO_COMMITに含まれるが、START/END/LOOP/LOOP_ENABLEはPREPARE時に取り込まれる。全PCM設定がCOMMITだけで反映するという抽象化は誤り。メモリupload完了→FENCE→停止/設定/CLEAR/PREPARE→READY確認→GAIN/ENABLE→COMMITの順序をSDKに明記する。

K9のC `kh_audio_write`とMicroPython `audio_write`はINDEX/DATAの連続2byteアクセスを使用する。HDでも2 CSRを連続配置し、6bit transportへ適応できる。K9 C commit helper、MicroPythonのbusy事前待機、非同期backendの手順は同一ではないため、API名だけで同一視しない。

K9 underflowはtoggle同期からeventを生成する。新案のsticky level立上り検出ではclear後の再発検出が同じになるとは限らない。通知方式は元HDのクロック領域と信号意味を確認して適応し、K9回路を無条件コピーしない。

## 3. 推奨する最小ブリッジ

1. 0x36 INDEX / 0x37 DATAをHD既存Hostに追加。既存`kagura_audio_registers #(.PCM(1))`を一度だけ接続する。元のShadow/Snapshot方式を保持。
2. COMMITは既存16byte descriptorの未使用opcode（候補7）へ割当て、既存SUBMIT、16bit tag、DONE、error、IRQで受理・完了を管理する。新queueは作らない。新opcodeと予約byte規則は将来のABI仕様で固定する。
3. 成功受理時だけcaptureし、snapshotが安定してからaudio_applyを発行する。core readyで一度だけ受理し、audio_done/errorで既存commandを完了、同時にregs.commit_doneを通知する。
4. 既存command FSMは4bit、使用状態0..8。SEND/WAIT追加は状態幅を増やさず表現できる。snapshot settleは既存DECODE等とのサイクル関係を設計し、単にcaptureとapplyを同一cycleへ短絡しない。
5. statusは既存E1とPCM 6F/8F、clearは既存E2/PCM CLEARを使用。ABI minor/CAPS bitによる一度の機能検出は残してよい。音声専用CAPS/REV、generation、error bank、IRQ bankは不要。
6. PCM上位bit拒否、初期化前拒否、readbackのsettle、合法index、書込み応答は残す。既存Host応答経路で待たせ、専用の固定6cycleカウンタの必要性を再検討する。共通errorへ渡す小さなstrobeは必要になり得る。
7. 既存snapshotを保つことで適用待ち中の次shadow編集を維持する。二重COMMITは拒否する。capture近傍のhazardは既存settle/admission条件を尊重する。

この案ではGPU/memoryと音声commitが同じ順序経路を通る。audioのsample境界待ち中に後続GPU commandが待つことは、独立endpointからの動作差である。最大待ち時間、timeout、audioエラー時のtag完了を将来のPC検証対象にする。

代替はINDEX/DATA/COMMITの3 CSRと最小handshakeを設ける案だが、GPU FENCEとの順序が独立する。専用FSM削減と既存順序保証の再利用を優先し、今回は2 CSR＋既存command案を推奨する。どちらも設計案であり実装していない。

## 4. Shadow/SnapshotとFSMの重複判断

- shadowは次設定、snapshotは受理済みcommitの不変データ、synth activeは現在出音中の設定。それぞれ寿命が違い、3つの役割全体を重複とは扱えない。
- synthは元HDでもEXTERNAL_SNAPSHOTを使用。不要な内部pending保存を新たに追加する必要はない。
- 新endpointのstate、arm、generation、completedと既存apply_busy/doneの二重管理は、既存command状態/tagへの統合で削減できる。
- LOCKED_SNAPSHOTは05で319 FF削減したが、busy中編集という契約を削った結果である。K9互換の最小案の資源見積りに、この319 FF削減を無条件算入しない。
- PCM READY/PREPARING/ACTIVE/DONE等は既存controlにある。別のprepare queueや状態ミラーは不要。

## 5. 資源の実測内訳と不可避な増分

|保存済み構成|全FF|Host FF|core FF|追加endpoint FF|BSRAM|合成LUT / ALU|
|---|---:|---:|---:|---:|---:|---:|
|STA合格RMW基点|4932|866|3996|0|19|6457 / 703|
|03 通常snapshot|6372|880|4440|982（wrapper81＋regs901）|19|7589 / 907|
|05 locked snapshot|6053|880|4440|663（wrapper81＋regs582）|19|7646 / 907|

**計算値:** 03の増分1440 FF＝regs901＋wrapper81＋Host14＋core444。05は1121 FF増。core444は動的設定により定数最適化されなくなった回路等を含む観測差であり、全444 FFが理論的最小・不可避と証明した値ではない。音源をHost制御する以上、設定保持とactive制御、可変STEP/gain等の実回路復活は避けられないが、正確な最小値は未測定。

新案固有の削除候補はwrapperのgeneration16bit＋上位ラッチ8bit、専用error/events/completed、独立commit状態・arm、余分な応答保存等。合成後wrapper全体が81 FFであり、宣言bit数を機械的に足した値や全81 FFをそのまま削減可能量としない。最小ブリッジにもデコード・応答・handoffが必要である。Host14 FF増は新bank payload等に対応する。

LUT/ALUは合成XMLの階層総数で、配置後CLSやLogic数ではない。03は136 LUT相当/340 REG未配置、05は193 LUT相当/93 REG未配置。双方とも配線・STA・Bitstreamなし。FF削減と配置成功は同義ではない。

## 6. 最小案の予測・互換性・リスク

**予測（未合成）:** 通常snapshotを維持する場合、03の6372 FFから管理wrapper等を削り、最小handoffを戻す。比較の出発点は4932＋901＋444＝6277 FFであり、Hostの追加保持と最小制御がさらに必要になる。概算は全体 **約6.3k FF（目安6250～6400）**。この幅は設計推定であり収容・STA合格保証ではない。05の6053を下回ると主張しない。追加BSRAMは **0を目標**。LUTは削減可能だが、最小案の数値予測に十分な分離データはなく未確定。

K9既存indexed設定、6ch操作、PCM手順は再利用可能。C/MicroPythonの低層transport、CSR位置、COMMIT発行/待機、address変換はHD用adapterが必要。K9 SDKを無変更では使用できない。新しい抽象化層を増やすより既存helperのbackend適応を優先する。

22bit排他ENDの制限、Host wave upload未提供、通知eventのCDC差、COMMITの順序/timeout、snapshot取得hazardが主要リスク。K9絶対addressの上位bitを単に捨てる実装は禁止。die末端の全byte利用は現インターフェースでは保証しない。これらを隠して「K9完全互換」としない。

配置不合格解消のためのBSRAM化は結論としない。重複除去した案の将来の評価後も不足した場合に、必要な機能契約を維持したstorage実装として別途判断する。

## 保護状態と次の作業境界

STA合格RMW fs SHA-256は `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`、RX32 fsは `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`。再計算して一致した。RX32のDO_NOT_PROGRAM.txtも既存hashと一致。診断成果物、元STA候補、復旧イメージを変更していない。`release_ready=false`を維持する。

この監査で更新したのは報告書と証拠JSONのみ。現在のWIP RTLは保全し、未検証RAM案を通常案として扱わない。次の実装は本監査案への合意後に独立作業とし、まず最小ブリッジのPC検証、続いて資源評価を行う。現在の依頼範囲ではそこへ進まない。
