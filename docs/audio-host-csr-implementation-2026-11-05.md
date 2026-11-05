> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 音声Host CSR/ABI実装結果（PC機能PASS・配置不合格）

> 保存済みvariant05時点の履歴。後続RAM案は未検証のまま停止した。「次はBSRAM」の方針は[比較監査](audio-csr-minimal-bridge-audit-2026-11-05.md)で置き換えた。現在の独立候補は[最小ブリッジ実装](audio-minimal-bridge-implementation-2026-11-05.md)を参照。この本文の「最終ソース一致」は現在の旧worktree WIPを保証しない。

## 現在の判定

`design/audio-host-csr-01` / `build/audio-host-csr-worktree`に、Hostから既存6ch音源とPCMを制御するCSR、top接続、ABI1.3、SDKを実装した。**機能PC検証はPASSだが、GW1NR-9Cの配置を完了できず、STA合格構成にはなっていない。** 新しいbitstreamは全試行で未生成、実機操作0。`release_ready=false`とDO_NOT_PROGRAMを維持する。

現行実機候補fs SHA `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`を保護し、PSRAM/混合音声の実機キャンペーンへこの実装を持ち込んでいない。Push/Merge/Releaseなし。

## 実装したもの

|ファイル（新worktree内）|変更|
|---|---|
|rtl/fb/kagura_fb_audio_endpoint.sv|新規。CSR36..3F、indexed設定、COMMIT受理・適用待ち・generation、PCM幅検査、詳細状態/IRQ/error|
|rtl/fb/kagura_fb_host.sv|AUDIO_CSRパラメータ追加。audio bankを別応答slotへdispatch。既定0では従来ABI/経路を維持|
|rtl/fb/kagura_fb_registers.sv|有効時の識別minor3・CAPS FF。従来0ならminor2・CAPS7F|
|boards/tang-nano-9k/kagura_fb_top.sv|AUDIO_CSR=1、既存cfg/PCM wireへ接続。起動時の固定発音/PREPARE/APPLYを外し無音起動|
|rtl/fb/kagura_fb_core.sv|audio_muted観測portを追加し、既存transport出力を接続。演算・制御アルゴリズムは変更しない|
|rtl/audio/kagura_audio_registers.sv|既存レジスタを再利用。既定OFFのLOCKED_SNAPSHOT省資源optionを追加。後述|
|rtl/fb/sources.f|新endpointと既存audio_registersをcompile対象へ追加|
|software/kagura_fb/kagura_fb_audio.py|既存Deviceに接続するAudio facade。旧ABIをwrite前に拒否。COMMIT待機、PCM操作、timeout後の非再送|
|sim/tests / tools|単体・実top SPI・原実装との既定モード等価検証・SDK試験|

音源演算`kagura_audio_synth`、`kagura_audio_transport`、`kagura_pcm_control`、`kagura_pcm_prefetch`、PSRAM Controller/PHY、clock、SDC/CST、build Tclは継承元とbyte単位で同一。HDMI/BLIT/cursor等の機能削除やP&R option探索はしていない。

## ABIと実装契約

CSR配置は[設計案](audio-host-csr-abi-design-2026-11-05.md)の36=INDEX、37=DATA、38=COMMIT、39=STATUS、3A/3B=GENERATION、3C=ERROR（0書込み消去）、3D=CAPS、3E=IRQ W1C、3F=REV1を採用した。SPI/QSPIの6bit address/packet形式は変更しない。

INDEX/DATAは既存6chのENABLE/STEP/GAIN/DUTY、noise/wave固有設定、MASTER、PCM START/END/LOOP/GAIN/ENABLE/PREPARE/STOP/CLEAR/STATUSへ到達する。readはshadowまたは既存STATUSであり、現在適用中の全設定のreadbackとは限らない。

要求は受理後6clockの応答待ちを設け、既存registerのshadow write/cache/settleを跨ぐ。応答先bankは受理時に保持する。COMMITは1件のみ、snapshot安定後にaudio_applyを提示し、audio_doneでのみgenerationを進める。GPU FENCEを音声apply待ちの代用にしない。FIFO raw faultとW1Cのevent ACKは区別し、sourceがstickyのままならSTATUS異常を隠さない。PCMのDONE bit2をfaultとして扱わず、fault maskは38hを使用する。

### 設計案から明示的に変更した2点

1. **COMMIT待ちのDATA writeはBUSY拒否**。最初の案はsnapshot用FFを別保持して待ち中のshadow編集も許可したが、配置不合格となった。最終保持案は`LOCKED_SNAPSHOT=1`でshadowを固定してcoreへ渡す。既存synthがapply境界でactive設定へcopyするまでDATA writeを一切通さない。INDEX/READや専用IRQ/ERROR操作は可能。phase resetだけは既存captured_resetsに保持して、shadow self-clear後も適用まで維持する。SDKも先にBUSYを確認する。これはABI1.3開発中の契約修正であり、旧ABI1.2の変更ではない。
2. **PCM検証を二段に分ける**。24→22bitの上位bit不正はendpointがPREPAREを副作用なしで拒否する。START<END、LOOPの順序は既存prefetcherに委譲し、CONFIG_ERRORで報告する。SDKは送信前に両方検査する。実top試験で不正順序のPREPAREがCONFIG_ERRORとなり、prefetcher未configured・PCM memory requestなしであることを確認した。黙ってアドレスを切り捨てない。

`LOCKED_SNAPSHOT=0`の既存利用側は従来のshadow/snapshot動作を維持する。portsをwireとしてsaved_snapshotから駆動する内部整理はあるが、保護済み原実装とのcycleごとの全出力比較で互換性を確認した。waveform内容のHost uploadは初版の対象外で、既存wave interface/Bring-up波形を維持する。

現coreのPCM address幅22bitにより、exclusive END=0x400000は表現できない。SDK/endpointはこの端点をサポート済みとしない。初版はEND<=0x3FFFFF。端点拡張は別課題。

## SDK利用例（PC検証済みAPI、実機未投入）

```python
from kagura_fb_audio import Audio
audio = Audio(gpu)  # existing kagura_fb.Device; requires ABI1.3/CAPS bit7
audio.channel(0, step=153791, duty=128,
              gain_left=2, gain_right=2, enabled=True, phase_reset=True)
generation = audio.commit()  # waits for actual apply completion

# Write PCM data only while its channel is stopped.
audio.pcm_stop(0)
gpu.write_bytes(240000, bytes([64] * 32 + [192] * 32))
audio.pcm_clear(0)
audio.pcm_configure(0, 240000, 240064, loop=240000,
                    gain_left=4, gain_right=2)
audio.pcm_prepare(0)  # waits READY; no implicit retry
audio.pcm_enable(0)
audio.commit()
```

このコードを既存RP2040へインストールしていない。現行1.2 bitstreamではAudio初期化がwrite前に拒否する。commit(wait=False)後は、返ったgenerationをaudio.wait()で待ってから次のshadow編集へ進む。transport例外・timeout後の操作再送はしない。

## PC検証

Verilator5.032、seed1。ログは新worktreeの`build/analysis/`。

|検証|結果|主な内容|
|---|---|---|
|audio endpoint|170アクセス PASS|全6ch STEP各byte/gain readback、atomic apply、phase-reset保持、二重COMMIT/BUSY、PCM上位bit拒否、PREPARE/STOP/STATUS、IRQ不正ACKの無副作用、reset|
|default mode等価検証|300 transaction / 4518比較 PASS|保護済みaudio_registersをreferenceにし、全出力・snapshot・PCM pulse・STATUSをcycle比較|
|SDK|10件 PASS|旧ABI拒否、byte順、検証前の副作用防止、未完了書込み拒否、timeout/不確実ACKの非再送、PCM範囲、generation wrap|
|実top SPI|PASS|ABI1.3、無音起動、ch0設定から左右同一+31/−32sample、generation、両PCMの独立PREPARE/ENABLE/STOP、不正範囲のメモリアクセス抑止、表示pixel|
|共通component|22/22 PASS|既存音源/PCM/HDMI等|
|FB全回帰|26/26 PASS|Host SPI/QSPI、coreのRGB/TMDS/sample oracle、表示/BLIT/cursor等|
|wrap統合|12/12 PASS|最終版を再実行。実topでHost設定のpulseが左右同一+31/−32sampleを出すことも確認|
|Controller|272ケース PASS|32B分割・mask・guard等。RTL変更なし|
|RX32|PASS|tap381 / fetch776 scenarios。RTL変更なし|
|既存driver|PASS|15件＋QSPI oracle4件|

## Standard評価：不合格試行も保存

対象GW1NR-LV9QN88PC6/I5、Standard V1.9.12.04。継承したPlace1/Route2、clock/制約を維持した。以下はseed探索ではなく、音声追加のRTL構造の評価である。

|固定directory|差分・結果|
|---|---|
|standard-audio-csr-01|最初の全snapshot版。Logic8743/8640で合成不合格|
|standard-audio-csr-02|重複するPCM順序比較を既存prefetcherへ委譲。Logic8641/8640で合成不合格|
|standard-audio-csr-03|新endpointのerror経路共有。合成後FF6372。配置136 LUT相当・340 REG未配置|
|standard-audio-csr-04|locked snapshot導入時のhost_active宣言整理ミスでcompile不合格。修正し、失敗ログも保持|
|standard-audio-csr-05|**最終保持案**。locked snapshot、Host未完了DATA拒否。合成FF6053/BSRAM19。配置193 LUT相当・93 REG未配置で不合格|
|standard-audio-csr-06|locked側read共有の試案。Logic8663/8640へ悪化し不採用。ソースは05へ戻した|

最終ソースは05の40固定入力と全hashが一致する。05はPlacement Phase2でPR0003。配線未実施、STA signoffなし、Setup/Hold値は不明（0やPASSとして扱わない）。全試行bitstreamなし。

新機能により、元topで定数最適化されていた制御も動的回路として復活する。FFを319減らすだけでは、LUTとREGの同時packingを解決できなかった。新endpointの制御だけを細かく削って収容できるとは断言しない。

次の物理実装課題は**音声CSRのshadow storage/readbackをBSRAM等へ寄せる構造の検討**。既存synth/PCM演算・PSRAM PHYを変えず、indexed低帯域busの余裕を使う案が対象になる。既知のupload native partial-write問題を再導入しないよう全word RMW等を前提に、別snapshot/PC検証で評価する必要がある。現時点ではこの案を実装・PASSしたとは報告しない。GPU機能削除、無関係なP&R調整、I/O制約の緩和は行わない。

## 来歴・保護・再現

基点HEADは1d46c6dだが、評価済みRX32/RMWの未commit差分も継承したためHEADだけでは再現できない。288ファイルの継承manifestを保存し、元worktreeが不変であることを検査した。

- `tools/audit-audio-csr-implementation.py`：全継承変更範囲、音源演算/PCM/PHY/Controller/制約10入力の不変、05固定40入力との一致、保護fsのhash、全試行のfs不在を検査。
- 新worktree `build/analysis/audio-provenance.json`、`audio-feature-only.patch`、`inherited-source-manifest.json`。
- [機械可読の検証・保護・配置判定](evidence/audio-csr-implementation-2026-11-05.json)。完了マーカーとfeature file hashを照合し、古い監査結果を再利用しない。
- 新規RTL/SDK/testは新worktree内に保存し、feature-only patchにも追加ファイルを含めた。build参照fixtureの準備にはrootのprepare-audio-default-equivalence.pyも使用する。
- `build/standard-audio-csr-01..06/inputs/`と各build.logを保持。復旧private imageはコピー・改変していない。

実機版への統合・リリースは未承認ではなく**品質ゲート未達により不可**。元のSTA合格候補を置き換えず、この音声CSR課題を独立させたまま管理する。
