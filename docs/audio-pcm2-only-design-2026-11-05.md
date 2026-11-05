> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# PCM 2ch専用構成への切替設計

> 後続の[実装評価](audio-pcm2-result-2026-11-05.md)を完了した。設定回路286 FF、全体5206 FFで配置配線・Bitstream生成に到達したが、Setup 3件でSTAは不合格。本稿の未実装・予測は設計時点の記録。

## 方針

KAGURA-HDではPCM 2chを優先し、6ch合成音源を構成時に除外する方針が妥当である。6ch版はHost管理を最小化し、snapshot192 bitを6 BSRAMへ移しても、固定Place1/Route2で未配置113 LUT相当・111 REGが残った。PCM専用化は保存状態だけでなく、6chの演算・位相・readback・選択回路も除去できるため、より大きな削減が見込める。

これは6ch音源がGW1NR-9上で一般に実装不能という結論ではない。現在のHD GPUとの同時収容を優先する製品構成の変更である。6ch版・snapshot192版は比較証跡として保全する。

今回実施したのは既存RTL・仕様・資源の調査と本設計の作成のみ。PCM専用RTL、PC検証、合成/P&R、Bitstream、実機投入はまだ実施していない。元STA候補とrelease_ready=falseを維持する。

## 残す機能

|項目|PCM専用構成|
|---|---|
|入力PCM|既存のsigned 8bit mono ×2、48kHz|
|出力|既存のsigned 16bit stereo、HDMI音声|
|音量・pan|各PCMのGAIN_L/GAIN_R、MASTER_GAIN|
|範囲|各ch START/END/LOOP、LOOP_ENABLE|
|制御|PREPARE/STOP/CLEAR、READY/ACTIVE/DONE/UNDERRUN/CONFIG_ERROR/MEMORY_ERROR/PREPARING|
|適用|GAIN/ENABLE/MASTERをShadow/Snapshot経由でsample境界適用|
|Host|既存6bit protocol、INDEX/DATA、tag付きCOMMIT、FENCEによるメモリ転送順序|
|HDMI受渡し|既存async FIFO、prefill/mute、48kHz tick、ACR/audio packet|

PCM 2chは「2本のmono sourceを左右gainでstereoへ混合する」既存機能を意味する。16bit PCM入力、2本のstereo stream、可変再生速度、resamplerは追加しない。

addressはHDのdie-relative byteのまま。22bit端点の制限も維持し、KAGURA-9の0x400000..0x7FFFFF絶対addressへ無条件に読み替えない。排他END=0x400000の表現問題を今回へ混ぜない。

## 除外する回路

- Pulse 3ch、noise 1ch、wave 2chと、そのphase・LFSR・period・DUTY・wave address/index・STEP選択。
- 6chのENABLE/STEP/DUTY/GAIN/PHASE_RESET/LEN/NOISE設定shadow/snapshot。
- 6ch readback cacheと設定合法性検査。
- topのbring-up wave ramp供給など、合成音源だけが使う信号。

Host CSRだけを消して演算器を残す構成にはしない。`PCM_ONLY`等の構成時parameterで使わない経路を除去する。既存6ch moduleのdefault構成は保全し、既存PCM演算を含む同じmoduleのPCM専用modeとして分離する案を第一候補にする。

L/R乗算器、乗算入力register、PCM加算・MASTER scaling・飽和処理は維持する。乗算入力pipelineを潰すと過去のsample漏れ問題を再導入し得るため、PCM専用化と演算最適化を同時に行わない。

## 資源見込み

901 FFの実測内訳から、6ch固有の状態だけを除いた算術見積りを示す。

|保持目的|6ch＋PCM版の実測FF|PCM専用で残す見積りFF|
|---|---:|---:|
|6ch/global shadow|292|8（MASTER）|
|PCM shadow|180|180|
|受理済みsnapshot|318|42（PCM GAIN/ENABLE 34＋MASTER 8）|
|capture制御|8|2|
|readback cache|64|16|
|INDEX/応答/検査|19|18|
|WRITE pipeline/settle|12|12|
|PCM命令pulse|6|6|
|sticky fault|2|2|
|**合計**|**901**|**286**|

**計算値:** 設定回路で615 FF減の見込み。FF版最小ブリッジ6309 FFを起点に、設定回路だけの差を引くと5694 FFとなる。これは合成値ではなく、PCM専用の合法性decode等の増減も未測定。

加えて、既存synth全体には実測757 FF・793 LUT・103 ALU・MULT18×2がある。このうち6ch固有部分がさらに削減対象となる。ただし共有PCM mixerも含むため、757 FF/793 LUTを丸ごと引いてはいけない。削減後の総FF/LUT/CLS、収容、STAは合成・配置で確認する必要がある。

**基点はsnapshot192版ではなく、BSRAM追加のないFF版最小ブリッジとする。** PCM専用で不要になる6 BSRAMを持ち越さず、最初の候補では全体BSRAM 19を出発点とする。追加の保存媒体変更を同時に行わない。

## 適用・sampleタイミング

sample境界の1125 system cycle分周、PCM prefetch/control、apply_boundary、FIFO/HDMIを維持する。現在のmixerは6ch＋PCMで31 cycle/sample。6chの処理を飛ばして単純に11 cycleへ短縮すると、PCM入力を読む時刻やsample_validが20 cycle早まる。

初期候補は既存のcycles counterを使って先頭の20 cycleを待ち、その後PCM0/1を従来と同じ時刻に処理する構成を検討する。6chの位相・波形演算は実装せず、既存PCM入力の取得時刻・出力時刻を保つ。これによりunderflow/memory errorが境界近傍で生じた場合も、従来のPCM経路と比較しやすい。

この待機は新しいqueueや音源機能ではない。新しいcounterを追加せず、既存cycle counterと最小状態で表現する。具体的な実装・面積・cycle一致はまだ未検証である。低latency化や加算幅短縮は別課題へ分ける。

## Host ABI / SDK

- INDEX/DATA 0x36/0x37、PCM index 0x60/0x80、global E0/E1/E2、COMMIT opcode 7は維持する。
- 旧6ch index 00..5Fは明示的にunsupported/errorとし、silently ignored/PASSにはしない。
- PCM gain/enable/masterのShadow/Snapshotと、適用待ち中の次shadow編集を維持する。専用generation/IRQ/error bankは追加しない。
- PCM START/END/LOOPはPREPARE時、gain/enable/masterはCOMMIT時という区別を維持する。
- 6ch prototypeと識別できるよう、実験版のABI minorを1.4へ進める案を推奨する。既存CAPS bit7はHost audio CSRの存在とし、ch数を表すbitへ黙って変更しない。追加CSRでのrevision/capability保持は不要。
- SDKは既存PCM helperを維持し、tone/noise/wave/6ch設定APIは送信前にunsupportedを返す。未公開1.3 prototypeの6ch APIとの非互換を明記する。既存GPU command/ABI1.2実機候補は変更しない。

ABI 1.4は本設計での提案であり、現行RTL・SDKのversionを変更したものではない。

## 最初の単独variantと品質ゲート

1. FF版最小ブリッジから独立copyを作り、PCM専用parameterとABI/SDK識別だけを実装。GPU、PCM prefetch/control、Hostメモリ窓、Controller/PHY、clock/SDC/CSTは維持。
2. 6chを無効にした元mixerをreferenceに、PCM全signed8値域、GAIN 0/255、左右独立mix、MASTER、正負飽和、sample取得時刻、apply時刻、resetを比較。
3. PREPARE/STOP/CLEAR/STATUS、loop/one-shot、error/timeout、次shadow編集、SPI/QSPI実top、未対応6chアクセス拒否、既存GPU/wrap/Controller/RX32の必要回帰を確認。
4. 固定Place1/Route2で合成・配置配線・STA・Bitstream生成を1回評価。Setup +0.100ns以上、Setup/Hold違反0、全配線完了。失敗時の自動再試行や条件探索はしない。
5. 実機投入は別段階。PC/内部STAのPASSを外部PSRAM I/O、音声capture、PVT、Release承認と同一視しない。

本調査の[実測根拠とFF見積りJSON](evidence/audio-pcm2-scope-2026-11-05.json)を保存した。元STA候補のhash一致も確認済み。6ch版・snapshot192版を削除せず、release_ready=falseを維持する。
