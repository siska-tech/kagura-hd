> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 音源Host CSR/ABI拡張の独立設計案

状態：設計提案。RTL実装・合成・bitstream生成・実機投入は行っていない。

後続：[独立実装結果](audio-host-csr-implementation-2026-11-05.md)。音声CSR/SDKとPC検証を実装したが、配置不合格で実機版は未生成。実装上は省資源のためCOMMIT待ちDATA writeをBUSY拒否し、PCMの順序検証は既存prefetcherへ委譲する契約へ変更した。以下は元の設計提案として保存する。

## 1. 問題と方針

現行候補`fix/upload-word-rmw-01`の音源設定固定は、**Bring-up topの配線・定数設定による制限**であり、6ch音源コアがHost制御を実装できないという制約ではない。

確認した既存機能：

- `rtl/audio/kagura_audio_registers.sv`：ch別shadow/snapshot、ENABLE、STEP、GAIN、phase reset、MASTER、AUDIO_COMMIT用capture/apply_busy、PCM設定とPREPARE/STOP/CLEAR/STATUS。
- `rtl/fb/kagura_fb_core.sv`：cfg入力、audio_apply/ready/done/error、PCM設定・prepare/stop/clear/status、既存synth/prefetch/controlへの接続。
- `boards/tang-nano-9k/kagura_fb_top.sv`：現在はcfgを定数接続し、起動FSMからPREPARE/APPLYを発行。Hostからこれらへ到達する経路がない。

上記パスは評価worktree `build/upload-rmw-worktree/`のソースを指す。root HEADだけでは評価時の未commit差分を再現できないため、統合評価の入力manifestも基点にする。

**既存コアを再利用してHostとの接続・admission・ABIを追加する。** 音声CSR開発はPSRAM実機検証と別課題・別branchで扱う。現行fs SHA `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`、PHY、Controller、SDC/CST、復旧imageを保護する。

## 2. 初版の構成

追加候補module `kagura_fb_audio_endpoint.sv`がCSR要求を受け、`kagura_audio_registers #(.PCM(1))`をインスタンス化する。

```text
Host SPI/QSPI → existing request dispatch
              ├ 00..1F: existing framebuffer endpoint
              ├ 20..35: existing cursor endpoint
              └ 36..3F: new audio endpoint
                           ├ existing audio_registers shadow/snapshot
                           ├ commit admission / completion generation
                           └ cfg / PCM command wires → existing fb_core
                                                       ├ synth
                                                       ├ pcm_control
                                                       └ pcm_prefetch
```

音声制御はsystem54 domain。既存Host dispatchの登録slotとready/valid契約を維持し、応答を要求時に選択したbankへ固定する。待機中に現在のreq_addrを見てresponse muxを切り替えない。

`fb_core`の外部cfg/PCM interfaceを利用し、synth、audio_transport、pcm_control、pcm_prefetchの基本アルゴリズムとsample cadenceは変更しない。Host endpointからaudio_ready/done/errorを受ける。Host enable後の起動FSMとの二重駆動を禁止する。

## 3. 提案するCSR配置と互換性

現cursorの定義済み領域はabsolute32..53（0x20..0x35）。54..63は現在未定義で、cursor側ではwrite error/read zeroとなる。この予約領域を新機能として割り当てる案であり、現行bitstreamに既に存在する仕様ではない。

|absolute CSR|名前|アクセス|提案契約|
|---|---|---|---|
|0x36|AUDIO_INDEX|R/W|既存8bit index。自動incrementなし|
|0x37|AUDIO_DATA|R/W|選択indexの既存shadow値またはSTATUS/PCM_CMD|
|0x38|AUDIO_COMMAND|W|値1でAUDIO_COMMIT。その他は拒否|
|0x39|AUDIO_STATUS|R|b0 APPLY_BUSY、b1 FIFO_UNDERFLOW sticky、b2 FIFO_OVERFLOW sticky、b3 MUTED、b4 COMMIT_DONE、b5 endpoint error、b6 ENDPOINT_READY、b7予約0|
|0x3A|AUDIO_GENERATION_LO|R|成功apply回数の下位。読出し時に上位をlatch|
|0x3B|AUDIO_GENERATION_HI|R|上のlatch値。16bit modulo、reset0|
|0x3C|AUDIO_ERROR|R/W0C|endpointの最初の8bit error code。0を書いて消去、非zero書込みは拒否。source faultの消去とは別|
|0x3D|AUDIO_CAPS|R|b0 6ch制御、b1 PCM2制御、b2 COMMIT completion、b3 PCM STATUS、b4 raw FIFO fault観測、b7..5予約0|
|0x3E|AUDIO_IRQ_STATUS|R/W1C|b0 commit完了、b1 underflow新規event、b2 overflow新規event、b3 PCM0 fault、b4 PCM1 fault、b5 endpoint error。新event優先|
|0x3F|AUDIO_ABI_REV|R|初版1。feature detection用|

既存6bit addressとSPI/QSPIのwire headerを維持する。製品ABIは**1.3候補**とし、既存CAPS bit0..6を維持、bit7をAUDIO_CSRに割り当てる案。予約bitの使用と既存driver挙動は実装前にABI仕様・テストで確定する。現行1.2/0x7Fを厳密比較する診断は新構成を意図的に拒否するため、新ABI対応を別途追加する。現行実機スクリプトをそのまま流用しない。

## 4. 既存indexed registerの公開範囲

初版は既存index layoutをそのまま公開し、同じ設定を別形式へ複製しない。DATA読出しは原則shadowであり、「現在sampleに適用中の全設定を読み戻せる」とは規定しない。適用確定はGENERATION/COMMIT_DONEで確認する。

|index|公開対象|
|---|---|
|0x00..0x5F、ch stride0x10|既存6ch。pulse3、noise1、wave2|
|ch+0..2|STEP24bit（noise chは既存どおり対象外）|
|ch+3|DUTY（pulse ch）|
|ch+4 / +5|GAIN_L / GAIN_R|
|ch+6|b0 ENABLE、b1 phase/noise reset要求|
|ch+7|wave length（wave ch）|
|ch+8 / +9|noise period（noise ch）|
|0x60..0x7F / 0x80..0x9F|PCM0 / PCM1。START/END/LOOP、GAIN、CONTROL、CMD/STATUS|
|0xE0|MASTER|
|0xE1|既存audio_registers STATUS|
|0xE2|既存event clear。source level/raw faultとは区別|

未定義index/offsetのread/write legality、noise/wave固有の無視されるフィールドは既存実装と仕様を照合して確定する。初版wrapperでコアにない設定や状態を捏造しない。

波形データ供給はcoreのwave_read/address/data interfaceを維持する。現Bring-upのwave内容もtop由来である。今回のCSR初版は既存の波形内容を使った制御を対象とし、Host wavetable uploadは別の設計範囲として明示する。

## 5. AUDIO_COMMITの整合性と順序

1. INDEX/DATAでshadow設定を構成する。registerのsettle中は次要求を待たせる。
2. COMMAND=1を受けた時、endpoint ready、settings_valid、apply_busy=0、snapshot captureの空きを確認する。条件不成立は副作用なしで拒否する。
3. **受理した1回だけcaptureを発行する。** 拒否時・backpressure中のcapture連打は禁止。
4. 既存registersは次cycleのcapture_pendingでsnapshotを保持する。そのcycleにshadow writeを通さず、既存の最低2edge要求間隔とsettle条件を守る。
5. snapshot完成後にcoreへaudio_applyを発行し、audio_readyで1回だけ受理させる。EXTERNAL_SNAPSHOT=1のため、sample boundaryで適用されるまでsnapshotを固定する。
6. coreのaudio_doneを待ってGENERATIONを1回進め、COMMIT_DONE/IRQを立て、commit_doneを既存registersへ返す。受理時点やready時点で「適用済み」にしない。
7. audio_error時は成功generationを進めずerrorを保存する。失敗commitを自動再送しない。

未完了COMMITは1件のみ。shadowはsnapshot確定後に次設定の準備へ書けるが、2件目COMMITはBUSY拒否。snapshotを上書きしない。phase resetは受理したsnapshotにだけ入り、既存capture時のself-clear契約を維持する。

endpoint error code案は0=正常、1=BUSY、2=BAD_COMMAND、3=BAD_ARGUMENT、4=BAD_INDEX、5=ADDRESS_RANGE、6=APPLY_ERROR。PCMのMEMORY_ERROR等は既存PCM_STATUSで報告し、このcodeへ無条件に置換しない。IRQ_STATUS bit0のW1CでCOMMIT_DONEもACKし、generation自体は消去しない。数値error codeにbit単位W1Cを適用しない。

音声COMMITは音声endpoint内で順序化し、GPU command queueを無断で共用しない。**GPU FENCEは音声applyの完了を保証しない**ことを新ABIに明記する。SDKのaudio_commit(wait=True)が音声generationを待つ。Hostの送信順だけでPSRAM/FILL/PCM/音声applyの横断順序を推定しない。

## 6. PCM PREPARE/STOP/STATUS

- START/END/LOOP/LOOP_ENABLEはPREPARE受理時にprefetcherが使う契約を維持する。GAIN/ENABLEはAUDIO_COMMITのsnapshotで適用する。
- PREPARE/STOP/CLEARは既存PCM_CMDのbitをDATA経由で公開する。開始/終了を重複する別CSR命令は追加しない。
- PREPARE直後は既存settleが解除されるまで次要求を待たせる。STATUS即時READがcommand前のcacheを返す挙動にしない。
- READY、ACTIVE、DONE、UNDERRUN、CONFIG_ERROR、MEMORY_ERROR、PREPARINGを既存PCM_STATUSから公開する。AUDIO_STATUSのFIFO faultとPCM underrunを混同しない。
- PREPARE→READY確認→ENABLE shadow→COMMIT→適用完了が再生開始順序。STOPは既存どおり即時停止。停止後の再開には再PREPAREが必要な契約を維持する。
- PCM状態/設定に関する要求も、snapshot captureの保護cycleには通さない。PREPAREとCOMMIT、STOPとapply boundaryの競合は既存control契約をそのままテストする。

アドレス幅に注意：audio_registersは各ch24bit、現在fb_coreのPCM inputは各ch22bit。**上位bitを黙って切り捨てない。** PREPARE前にwrapperで値とrangeを検証し、現coreが表現できるbyte addressへ限定する。現22bit ENDではexclusiveの0x400000（4MiB終端そのもの）を表現できない。初版はこれを非対応と明記し、START<END<=0x3FFFFF、loop有効時START<=LOOP<ENDを満たさない要求を拒否する案とする。この上限仕様はprefetcherの現条件とテストで確定し、端点対応が必要なら独立したcore/address-width課題に分離する。

CPUがPCM領域を書き換える前にSTOP→停止確認→既存PSRAM WRITE完了→PREPAREを行うSDK手順を提供する。現在のscratch試験とactive PCM領域を無秩序に共有しない。

## 7. fault/CDC/reset/起動

FIFO underflow/overflow等のsource levelがstickyであれば、frontendのW1Cだけで物理sourceが消えたと扱わない。system54へ同期したsource levelをraw faultとして保持し、IRQ通知のW1C ACKと区別する。現在のaudio_transportのsticky sourceをclear可能にするためだけにコアを変更しない。rawが1のままならSTATUSは異常を表示し続け、再発回数を数えたとは主張しない。

PCM STATUSはsystem domainの既存状態から取得する。pixel domain起源のunderflow/muted等はclock domainを確認して同期し、pulseをそのまま跨がせない。既存Host集約errorと音声詳細statusの関係を文書化する。COMMIT完了はsystem domainで音源が適用したことを意味し、HDMI端子から当該sampleが出力されたこととは別である。

新構成のresetはENABLE/PCM ENABLE=0、pending commit=0、generation/IRQ/error=0を基本とする。旧topが行うBring-up固定6chの自動発音・PCM自動PREPARE/APPLYは外す。Host制御とboot FSMで設定wireを同時駆動しない。起動のPSRAM初期化・framebufferクリアは維持し、Host ready条件と音声readyを明確に分ける。現在の候補のboot処理をこの設計文書だけで変更するものではない。

## 8. 実装境界と資源・STAゲート

候補変更対象：新audio endpoint、Host dispatchの0x36..0x3F振分け、topのcfg/PCM配線・起動方針、CAPS/minor ABI、SDKと対応テスト。コアinterfaceの観測wire追加が必要なら別の小差分としてレビューし、機能修正と混ぜない。

原則不変更：audio_synth、audio_transport、pcm_control、pcm_prefetchのアルゴリズム、PSRAM Controller/PHY、32B分割、RX32、表示/BLIT/cursor/palette、既存clock/SDC/CST。

現候補はCLS4171/4320、FF4932、BSRAM19。残CLS149は大きな余裕ではない。shadow/snapshotや、定数最適化されていた制御経路を復活させると資源・critical pathが増えるため、**そのまま収まるとは約束しない**。実測前に追加LUT/FFやSTA値を捏造しない。

次の開発branch候補は`design/audio-host-csr-01`。実装開始時にRX32/RMWの未commit継承manifestを含む基点を固定し、現候補とは別worktreeで評価する。収容不能・STA不合格なら、この追加機能として報告し、GPU機能削除や無関係なP&R調整で押し込まない。

## 9. PC検証・後続実機の受入条件

- CSR address全64件と既存領域の非干渉、未対応ABI拒否、旧driver互換範囲。
- 全6ch ENABLE/STEP/GAIN/DUTY、noise/wave固有設定、左右gain分離。shadow writeだけでは適用されずCOMMITで同時適用されること。
- captureの次cycle、連続INDEX/DATA、settle中request、COMMIT二重送信、BUSY拒否時のsnapshot不変、reset中の要求とpending取消し。
- READY/APPLY_DONE/generationの1対1対応、phase reset self-clear、completion/error/IRQのW1C競合。
- PCM PREPARE/STOP/STATUSの直後READ、2ch独立制御、範囲/上位bit不正、memory error、underrun、loop/終了/再準備。
- 既存音源golden sample oracleに接続して、Host操作からHDMI packet/sampleまでPCで独立比較する。PCキャプチャ較正とsample-level simulationを混同しない。
- 既存全回帰、wrap12、Controller272、RX32、HDMI/PCM/BLIT/cursorを再実行し、Standard Setup>=+0.100ns、Setup/Hold違反0、全配線を要求する。外部PSRAM I/Oは別ゲート。

実機は新CSR構成の別承認・別campaignで行う。各chを個別に発音させる機能受入と、現固定bitstreamの混合音声試験を分離する。AUDIO_COMMIT/PCM STATUSが読めたことだけでHDMI音声のPASSにはしない。

## 10. 現行キャンペーンとの関係

現在の混合音声取得は[較正報告](a0-audio-calibration-result-2026-11-05.md)の測定限界を考慮した別の固定計画で扱う。Hostへ個別制御が未接続であることを音源コアの恒久的制限と表現しない。同時に、今のbitstreamで実際には操作できないch別機能を試験済みとも扱わない。

この設計案を理由に現候補を再生成・置換してPSRAMキャンペーンを継続しない。今回追加したのは文書のみで、現在のbitstream SHA、release_ready=false、DO_NOT_PROGRAM、復旧状態を維持する。
