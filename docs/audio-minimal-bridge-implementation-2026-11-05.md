> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 最小音声Hostブリッジ実装・PC評価（2026-11-05）

> 後続の[Standard合成資源評価](audio-minimal-synthesis-result-2026-11-05.md)は完了した。以下の「未合成」は本PC評価完了時点の記録であり、現在の測定値は後続報告を参照。

比較監査の推奨案を、独立したソースコピー`build/audio-minimal-bridge`へ実装した。元STA合格構成と旧`design/audio-host-csr-01`のRAM作業状態は変更していない。音源演算・PCMコアを変更せず、通常のShadow/Snapshotを使ってHost操作する。実機、合成、配置配線、Bitstream生成、Mergeは今回行っていない。`release_ready=false`。

## 実装した接続

|要素|最小案|
|---|---|
|Host CSR|0x36 INDEX、0x37 DATA。連続2byte書込み可能|
|COMMIT|既存16byte descriptor、opcode 7、argument=0、byte4..15=0、byte2..3は既存tag|
|完了|既存CSR 27～31、既存tag/error/IRQ。実際のaudio_doneまで完了しない|
|音声status|既存内部index E1。PCM statusは6F/8F|
|設定保持|元の`kagura_audio_registers #(.PCM(1))`をそのまま一度だけ接続|
|適用|command FSMへSNAPSHOT/SEND/WAITを追加。4bit状態幅を維持|
|CSR応答|1回の登録応答＋既存settleによるbackpressure。専用pending FSM・固定6cycle待機なし|
|エラー|不正CSRは既存共通sticky errorへBAD_COMMAND=2。COMMITの不正設定はRANGE=3、apply errorは既存MEMORY_ERROR=4|
|機能検出|ABI 1.3 / CAPS bit7。音声専用CAPS/REVなし|

専用generation、generation上位ラッチ、completed、音声IRQ bank、音声error bank、独立COMMIT FSMを削除した。LOCKED_SNAPSHOT/RAM_READBACKは使っていない。readback RAMソースはこの候補に含めない。既存registersのraw SHAがSTA基点と一致することを検査している。

Host dispatchの第3 bank payloadは保持している。これはローカルなrequest保持であり、追加queueではない。さらなるbus共有や保持幅変更は今回加えていない。

## 適用順序とShadow/Snapshot

受理済みdescriptorの合法性、settings_valid、apply_busy、settleをcommand側で確認する。EXECUTEでcapture、次のSNAPSHOT状態で既存regsのsnapshotが確定し、その後SENDからapplyを発行する。readyで一度だけ受理し、WAITでaudio_done/errorを待つ。

captureと同じedgeの新しいCSR書込みはbridgeのreq_readyで抑止する。その後は既存の登録書込みpipelineにより、適用待ち中でも次shadowを編集できる。現在のsnapshotは変更しない。元regsのphase-reset self-clearも再利用する。

COMMITはGPU/memoryと同じone-outstanding command経路を通る。HostはCOMMIT完了後に次のcommandを送る。次のFENCEもその順序に従う。一方、INDEX/DATAは適用待ち中も操作できる。audio_doneが来ない場合はcommandもBUSYのままであり、既存SDKの有限timeoutで終了する。自動再送はしない。

## SDK

MicroPythonの既存Audio helperを最小transportへ適応した。`write(index,value)`はINDEX/DATA連続書込み、`status()`はE1、`commit(wait=False)`は既存command tagを返し、`wait(tag)`はDevice.waitへ委譲する。旧generation API、専用IRQ ACK、BUSY shadow lockは削除した。

Cは既存kagura_fb.c/.hへ`kfb_audio_write`、`kfb_audio_read`、`kfb_audio_commit`の3入口だけを追加した。COMMITはtagを返し、待機は既存`kfb_wait`を使用する。PCMの新しい抽象化層や状態を増設していない。

例（PC候補用。既存実機Bitstreamへは使用しない）:

```python
audio.channel(0, step=153791, gain_left=2, gain_right=2,
              duty=128, enabled=True, phase_reset=True)
tag = audio.commit(wait=False)
# 適用待ち中に次のshadowを編集可能
audio.write(4, 3)
audio.wait(tag)
audio.commit()
```

## PC検証と証拠

Verilator 5.032、既存回帰seed1。**以下はすべてPASSし、最終保護監査もPASSした。** 詳細の最終判定とログhashは[証拠JSON](evidence/audio-minimal-bridge-pc-2026-11-05.json)、全rawログと変更patchは[ログ一式](evidence/audio-minimal-bridge-rawlogs-2026-11-05.zip)に保存した。

- 集中試験86 CSRアクセス: 6ch readback、snapshot保持と次shadow編集、phase-reset消費、ready backpressure、実apply完了/tag、FENCE、不正descriptor/settings、PCM両chの幅検査・PREPARE/STOP/CLEAR、未実装CSR拒否、pending中reset。
- 実board top SPI: 起動時無音、Host設定から左右同一の+31/−32sample、両PCM個別PREPARE/ENABLE/STOP、tag完了、不正PCM範囲でメモリ要求抑止、表示pixel。
- 実board top QSPI: 同じoracleを4laneで実行。INDEX/DATAの連続2byte転送、共通sticky errorへの通知とclearも確認。clock/DDR PHY/LVDSはstubであり物理I/O評価ではない。
- SDK新規7件: C/MicroPython、tag wrap、snapshot分離、timeout、不確実submitの非再送、旧ABI拒否、PCM範囲拒否。SDKのモデルはRTL物理タイミングを保証しない。
- 既存driver15件＋QSPI driver4件。
- 既存FB26件、32B wrap統合12件、共通component22件を、この候補のソースで回帰して全件PASS。

集中試験の初回は、PCM登録pulseの到達をテストが待たずに比較して失敗した。既存settle契約に合わせてテスト側の待機を修正し、初回ログ`build/analysis/initial-pcm-check-failure.log`を保持した。この修正でRTLの合格条件やPCM実装は変更していない。

rawログは候補内`build/analysis/`、`build/audio-csr/`、`build/audio-qspi/`、`build/fb-verilator/`、`build/fb-wrap32-integration/`、`build/common-verilator/`に保存する。基点からの変更patchは`build/analysis/minimal-feature.patch`。

## 資源と未確認事項

実測合成資源はまだない。旧wrapperは保存済み03/05合成で81 FFだった。新wrapperのRTL宣言は同期6＋過去値2＋応答10＝18bitであるが、これは合成後FF数ではなく、配線・packing・STA改善量も示さない。通常snapshotを復元したため、05のlocked方式に比べて既存registers側の319 FF削減は失う。全体が小さくなる、配置に収まる、STAが通るとは現段階で判断しない。

最小案にも設定保持と可変制御による回路復活が必要である。BSRAM化の判断は、今後この候補を合成して資源内訳を確認してから行う。現時点でBSRAM化は実施していない。

PCMはHDのdie相対22bit addressを維持する。排他END=0x400000は表現不能で、上位bitを切り捨てて使わない。K9の絶対address APIはそのまま使用できない。Host wave RAM uploadも未提供。underflow event方式のK9との差、外部PSRAM I/O/PVT、実HDMI captureは本PC検証では解決しない。

旧ABI1.3 prototypeの0x38 COMMIT/generation方式との互換性はない。旧案は配置不合格でBitstream未生成・未Releaseのため、今回は同じ未公開ABI1.3の設計改訂として扱う。実機のABI1.2 fsは変更していない。

## 再現と保護

root toolsのprepare-audio-minimal-bridge.py → implement-audio-minimal-bridge.py → prepare-audio-minimal-tests.py → prepare-audio-minimal-sdk.py → prepare-audio-minimal-qspi.pyで独立コピーとPC用候補を準備した。最初のprepareは既存出力がある場合は上書きを拒否する。テストは候補内の対応shell scriptを使用する。audit-audio-minimal-bridge.pyで元候補の不変、保護11入力、Bitstream不在、ログを検査する。

RMW fs `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`、RX32 fs `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`を保持する。旧RAM作業コピーにも書込みを行っていない。新候補にもDO_NOT_PROGRAM.txtを設置し、release_ready=falseを明示する。

次の評価は、この最小案自体の合成資源内訳の測定である。今回のPC PASSから配置可能性やStandard STAを推定して合格扱いせず、新規Bitstream生成・実機投入へは進めていない。
