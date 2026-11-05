> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PCM 2ch専用・ABI 1.4 実装評価

**結果：PC全検証PASS、配置・配線完了、Bitstream生成完了。ただしStandard STAはSetup 3件でFAIL。** PCM専用化により収容は達成したが、実機投入・Releaseの条件は未達である。release_ready=false。

## 実装

[承認済み設計](audio-pcm2-only-design-2026-11-05.md)に従い、BSRAM追加のないFF版最小ブリッジから`build/audio-pcm2`を分離した。snapshot192版の6 BSRAMは持ち越していない。

- signed 8bit mono ×2、48kHz入力、signed 16bit stereo HDMI出力を維持。
- PCMのSTART/END/LOOP、左右GAIN、ENABLE、MASTER、PREPARE/STOP/CLEAR/STATUS、Shadow/Snapshot、tag付きCOMMITを維持。
- `PCM_ONLY`のdefaultは0。HD topだけが1を指定し、6ch固有のphase/noise/wave/設定保持/readbackを構成時に除去する。既存6ch modeを削除していない。
- 既存cycles counterで先頭20 cycleを待ち、PCM取得を境界後22/25 cycle、sample_validを31 cycleに揃えた。乗算器入力register、加算・MASTER scaling・飽和演算は維持。
- PCM prefetch/control、audio transport、HDMI、GPU各機能、command FSM、Host dispatch、upload window、Controller/PHY、clock/SDC/CSTは変更しない。

旧6ch prototype、snapshot192、元STA候補は保全。実機投入、Flash/FW/filesystem変更、Push/Merge/Releaseは行わない。release_ready=false。

## ABI / SDK

実験版ABIは1.4。既存CAPS bit7はHost audio CSRの存在を表し、channel数へ意味を変えていない。

|操作|PCM2 profile|
|---|---|
|INDEX/DATA|0x36/0x37、連続2byte write可能|
|PCM0 / PCM1 index|0x60 / 0x80 base、既存配置を維持|
|MASTER / STATUS / error clear|E0 / E1 / E2|
|COMMIT|opcode7、既存16bit tag/done/error/IRQ|
|旧6ch 00..5F|DATA read/writeをBAD_COMMANDで拒否|

MicroPython Audio.channelはNotImplementedError、旧6ch indexのread/writeは送信前にValueError。Cの旧6ch index操作はKFB_ARGUMENT。raw Hostで送った場合は既存共通sticky error=2で検出できる。新しいgeneration、IRQ bank、queue、revision CSRは追加していない。

新SDKのaudio helperはABI1.4を要求し、未公開1.3 prototypeを拒否する。GPU操作は従来のmajor1/base capabilityを維持。PCM addressはHDのdie-relative、排他END=0x400000は引き続き表現不能。KAGURA-9の絶対addressをそのまま使わない。

## PC検証

### Mixer

6chを無効にした保護済み元mixerをreferenceに、全10種の制御・sample出力を1153203 cycle比較しPASS。さらに独立整数オラクルで1024 stereo sampleを比較した。

- 両PCMの全signed8値域を、実際の取得edgeで網羅。
- gain 0/1/128/255、MASTER 0/32/128/255、左右pan、ENABLE、正負飽和。
- PCM入力を毎system cycle変化させ、取得時刻のずれを検出。
- 1125 cycle周期、取得22/25・出力31 cycle、apply ready/done/busy/boundary、pending中と演算中resetを比較。

出力計算は`clamp16(((PCM0*GAIN0)+(PCM1*GAIN1))*MASTER >> 8)`を独立に評価し、FPGA出力やREAD結果から期待値を作らない。

### Host / PCM integration

endpoint348アクセスPASS。全96個の旧6ch indexのDATA read/write拒否、PCM/MASTERの次shadow編集、snapshot不変、tag/FENCE、reserved byte、不正長/幅・PCM command、resetを確認。

SPI実topではHostからPSRAMへPCM0=0x40（+64）、PCM1=0xE0（−32）を各64B書き、Host READで全byte比較し、FENCE後にPREPARE/COMMITした。期待値はHost定数とgain設定から生成。

|状態|期待L/R|
|---|---|
|PCM0のみ、GAIN=4/2、MASTER32|32 / 16|
|PCM1をGAIN=2/4で追加|24 / 0|
|PCM0左gain8をshadowへ書いただけ|24 / 0|
|COMMIT後|56 / 0|
|PCM0 pause|−8 / −16|
|PCM0 resume|56 / 0|
|両ch STOP、one-shot終了後|0 / 0|

loop、one-shot DONE/CLEAR、DONEをfault扱いしないこと、READY polling、未対応6ch拒否、表示pixelも確認した。clock/DDR PHY/LVDSはstubのため実機波形/I/Oの証明ではない。

SDK10件、既存driver15件＋QSPI driver4件もPASS。既存FB26件、QSPI実top、wrap12件、共通22件、Controller272ケース、RX32 tap381ケース/fetch776 scenarioもすべてPASS。[PC判定・source hash](evidence/audio-pcm2-pc-2026-11-05.json)へ最終結果を保存した。共通回帰にはdefaultの既存6ch modeの整数オラクル試験も含む。

## 固定するStandard評価

全PCゲート完了後、Gowin Standard V1.9.12.04、GW1NR-LV9QN88PC6/I5、QSPI、Place1/Route2で1回のみ実行した。40入力を`build/standard-pcm2-01/inputs/`へ固定した。Setup +0.100ns以上、Setup/Hold違反0、全配線完了を数値ゲートとし、失敗後の再試行や条件探索は行っていない。

Bitstream生成は承認範囲だが、実機プログラミングは含めない。PC/内部STAの合格を、PSRAM外部I/O・PVT・HDMI capture・Releaseの合格に変換しない。

## 実測資源

|項目|最小6ch＋PCM FF版|PCM専用|差|
|---|---:|---:|---:|
|設定回路FF|901|286|−615|
|mixer FF|757|277|−480|
|mixer LUT|793|258|−535|
|全体FF|6309|5206|−1103|
|全体合成LUT|7593|6695|−898|
|全体合成ALU|892|858|−34|
|全体合成Logic換算|8581|7649|−932|
|P&R Logic|8570/8640|7776/8640|−794|
|CLS|4320/4320、配置FAIL|4215/4320、配置完了|−105|
|BSRAM|19/26|19/26|追加0|

表の合成値とP&R値は混ぜていない。PCM版P&RはLUT6684/ALU996/RAM16×16、Logic7776であり、合成LUT6695/ALU858から変化している。FFの減少は設定615＋mixer480＋topのwave_data 8＝1103と一致した。

mixer netlistのDFFも277個と階層XMLに一致し、phase/noise/STEP/wave等の6ch固有名を持つFFは残っていなかった。6chのENABLEをHostから隠しただけの構成ではない。共有PCM演算器・MULT18×2は保持している。

## STA結果と判定

|項目|結果|
|---|---|
|Gowin process|exit0、配置・配線・Bitstream生成完了、tool ERRORなし|
|Setup|最悪 **−1.234ns**、違反endpoint **3**|
|Hold|最悪 **＋0.484ns**、違反endpoint **0**|
|Recovery / Removal|＋10.096ns / ＋0.539ns|
|数値ゲート|**FAIL**、Setup +0.100ns以上と違反0を未達|
|外部PSRAM I/O / PVT / 実HDMI capture|未評価|

### 違反経路

|slack|from → to|clock・制約|
|---:|---|---|
|−1.234ns|core/cursor/held_6_s1 → position_x_6_s0|system54→pixel74、既存max-delay 10ns|
|−0.624ns|core/hdmi/protocol/cx_1_s0 → core/cursor/logical_x_2_s0|pixel74内、13.468ns|
|−0.033ns|host/commands/copy_command_s0 → fill/row_word_14_s1|system54内、18.518ns|

最悪経路はCDC bundleの既存制約に対する違反で、表のData Delay 6.072ns、Clock Skew 4.732ns、Arrival13.444ns/Required12.210nsと報告されている。Data Delay単独が10ns未満という理由でwaiveしない。別の2件は同一clock内の違反なので、CDCだけを扱っても合格にはならない。

さらにcursorのedit_bank→shape_completeは＋0.041ns、edit_bank→last_errorは＋0.088ns、Hostのdata_addr→window_groupは＋0.094nsで、要求余裕＋0.100ns未満である。負の3経路だけを0nsにすれば完了という判定にはしない。

cursor、BLIT/fill、upload_word、SDC/CSTのsource hashは元の最小FF版と不変。Host registersはABI minor定数だけの変更で、upload回路本文は不変であることを照合した。元STA合格RMWの全体最悪Setupは＋0.717nsであった。ただし今回の3経路familyは旧レポートの上位25経路に含まれず、同一bitの旧slackは不明。存在しない比較値を補っていない。

**解釈:** 音声の構成変更に伴う物理実装の変化が、未変更部分のタイミングへ影響した結果と整合する。clock skew・logic・配線の寄与を分離した原因の一意特定はまだしていない。PCM機能の誤りやPSRAM PHY破損の証拠として扱わない。

この作業の範囲はPCM専用化と固定条件1回評価であり、STA違反後のcursor/BLIT/Host RTL修正、制約緩和、別Place/Route試行は行っていない。次の作業は、この限定したtiming課題と＋0.100ns未満経路への対策を別途設計・検証することになる。

## 生成物

不合格の証跡Bitstream:

`build/audio-pcm2/build/standard-pcm2-01/impl/pnr/kagura_fb.fs`

SHA-256: `3c61f8d87a407e25e2d348f09fa22abb8826361b6c3c93244e58fc200e36b034`

STA未達のため実機投入しない。新SDKのRP2040インストールもしていない。DO_NOT_PROGRAMにはimplementation gate FAILを記載し、release_ready=falseを維持する。

- [資源・STA・Bitstream hash・固定入力](evidence/audio-pcm2-result-2026-11-05.json)
- [STA上位経路・旧RMWとの読み取り比較](evidence/audio-pcm2-sta-comparison-2026-11-05.json)
- [PC/Standard全rawログ・報告・差分patch](evidence/audio-pcm2-raw-2026-11-05.zip)

raw archiveへBitstreamそのものは含めず、hashとローカルpathで識別する。

## 来歴・保護

prepare-audio-pcm2.pyは独立copyを作り、prepare-audio-pcm2-unit-tests.py / prepare-audio-pcm2-host-tests.pyで測定系を準備した。初回準備で重複置換のassert、初回mixer benchで予約語instance名のcompile errorが発生し、製品シミュレーション前に修正した。初回benchエラーはbuild/analysis/initial-mixer-test-syntax.logに保存。機能比較のFAILを無視して続行したものではない。

audit-audio-pcm2.pyは変更範囲、FF親・snapshot192・旧audio/RAM・RMW基点の不変、元fsのhashを確認する。freeze-audio-pcm2.pyは全PCゲートとsource hashを確認して固定入力を作り、既存directoryの上書き/再試行を拒否する。

保護fs:

- RMW `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`
- RX32 `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`

独立variantにもDO_NOT_PROGRAM.txtを維持する。新SDKをRP2040へインストールしておらず、実機は操作していない。
