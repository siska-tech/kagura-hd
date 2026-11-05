> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 最小音声ブリッジ：Standard配置評価結果（2026-11-05）

> 後続の[901 FF保持目的・限定削減案](audio-register-storage-analysis-2026-11-05.md)を作成した。解析のみで、この配置不合格RTLを変更・再試行していない。

**配置不合格。** 固定した最小ブリッジをPlace1/Route2で1回実行したが、Placement Phase 2後にPR0003となった。未配置は **124 LUT相当・273 REG**。配線・STAへ進めず、Bitstreamは生成されなかった。失敗後の条件変更・再試行は行っていない。`release_ready=false`、DO_NOT_PROGRAMを維持する。

## 実施条件・承認範囲

- Gowin Standard V1.9.12.04、GW1NR-LV9QN88PC6/I5、QSPI 4lane、Place1/Route2。
- 評価directory: `build/audio-minimal-bridge/build/standard-minimal-pnr-01`。PC全検証PASS・合成評価済みと同じ40入力を別directoryへ固定し、全hash一致を確認。
- RTL、SDC/CST、clock、Controller/PHY、音源演算/PCMは変更していない。
- 当初はBitstreamを生成しない段階停止方法を調査した。組込み`run -h`はsyn/pnr/all、`set_option -h`にはBitstream抑止・配置のみ停止の公開設定が見つからなかった。通常のP&RがBitstream生成を含むことは[公式Software User Guide](https://cdn.gowinsemi.com.cn/SUG100E.pdf)にも記載される。
- ユーザーの「とりあえずBitstream生成までやっちゃっていいですよ」を受け、通常の`run all`による再合成→配置配線→STA→生成を1回だけ実行する範囲へ変更した。実機書込み、Flash/FW変更、Merge・Releaseは含めない。

初回のhelp調査では`help run`が未対応で終了し、正式な`run -h`/`set_option -h`へ訂正した。設計実行前の調査であり、この時点で配置やBitstream生成は行っていない。調査ログは候補の`build/analysis/gowin-stage-help*.log`へ保存。

## 初発エラーと到達段階

```text
[10%] Placement Phase 0 completed
[20%] Placement Phase 1 completed
[30%] Placement Phase 2 completed
ERROR (PR0003): Failed to place with
124 LUT(s)(equivalent, include LUT/MUX/ALU) unPlaced,
273 REG(s) unPlaced
```

|段階|結果|
|---|---|
|再合成|完了、直前の合成測定とFF/LUT/ALU/BSRAM/SSRAM総数一致|
|配置|不合格、PR0003、全CLSを使用|
|配線|未実施|
|Standard Setup/Hold|未評価。slackも違反数も不明。0/0と扱わない|
|Bitstream|未生成、SHAなし|
|実機試験|未実施、programming 0|

process exit=1。配置報告・pin報告は生成されたが、タイミング報告と.fsは存在しない。品質ゲートはFAIL。

## 資源と過去案の比較

以下は**P&R側**のresource report。合成XMLの数と区別する。

|構成|P&R Logic|FF|CLS|未配置LUT相当|未配置REG|
|---|---:|---:|---:|---:|---:|
|元STA合格RMW|7368/8640|4932|4171/4320|0|0|
|03 通常Snapshot＋旧endpoint|8581/8640|6372|4320/4320|136|340|
|05 locked Snapshot＋旧endpoint|8638/8640|6053|4320/4320|193|93|
|今回：通常Snapshot＋最小ブリッジ|8570/8640|6309|4320/4320|124|273|

今回の内訳: LUT 7582、ALU 892、RAM16 16、Logic FF 6301/6480、I/O FF 8/291、BSRAM 19/26、IOLOGIC 28/97。合成時はLUT 7593・Logic 8581だったが、P&R処理後は11 LUT少ない。合成値と混ぜて改善量を計算しない。

**計算:** 03からFF −63、P&R Logic −11、未配置LUT相当 −12、未配置REG −67。簡略化の効果はあるが収容には不足した。05との比較では通常Snapshotの契約を復元しているため、FFと未配置REGは増える。05のBUSY中DATA拒否へ戻して解決したことにはしない。

## 分かったこと・断定しないこと

**観測済み:** 専用generation/IRQ/COMMIT FSMを除去し、既存Shadow/Snapshotを再利用しても、この固定構成はPlace1/Route2で配置できなかった。endpoint管理部分は合成で18 FFまで減っている。BSRAMは19のままで増設していない。

**解釈:** 合成上のLogic/FF総数が単独の上限内でも、LUTとFFの同時収容・packing・配置条件を満たすとは限らない。全CLS使用と未配置資源が残る結果は、その制約と整合する。ただし、未配置インスタンスの個別リストやpacking制約の寄与は今回の集計では特定できていない。

**未確認:** 273 FFを削れば配置できるという下限は得られていない。未配置数は固定配置試行の結果であり、必要削減量そのものではない。別Place/Route条件なら成功するとも、BSRAM化すれば必ず成功するとも断定しない。今回それらは試していない。

## 次の修正判断に必要な範囲

この失敗を理由に音声制御全体をBSRAM化しない。まず既存audio_registersの901 FFを、shadow、受理済みsnapshot、readback cache、PCM address/状態、pipelineへ分類し、必要寿命と削減可能量を示す設計評価が必要である。

shadow/snapshot/activeの寿命、適用待ち中の次shadow編集、phase-reset一度消費、PCM PREPARE時取込み、既存settleを維持する。もし保存方式の変更が必要なら対象bankを限定し、追加BSRAM、LUT/FF削減、読書き遅延、commit atomicityを事前評価する。演算コアやPHYを変える理由にはしない。

本試行後のRTL修正・BSRAM化・別条件P&Rは未実施。次の候補を作る前に、上記の保存状態内訳と互換性を整理するのが妥当である。

## 保護と成果物

元STA候補RMW fs `90b5b26189b198326818488056b9c8fb84e515973cdd2432e04287be3a91ef2e`、RX32 fs `a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`は再計算して一致した。RMW基点と停止した旧audio/RAM作業コピーも保存manifestと全件一致。実機・復旧イメージは操作していない。

最小候補のDO_NOT_PROGRAM.txtを配置不合格の現状へ更新した。元候補のマーカーは変更していない。`release_ready=false`を維持し、Git Push/Merge/Releaseは行っていない。

- [機械可読の判定・未配置数・資源・保護hash](evidence/audio-minimal-pnr-2026-11-05.json)
- [rawログ・P&R報告・cfg/cmd・入力manifest](evidence/audio-minimal-pnr-raw-2026-11-05.zip)
- [直前の合成資源評価](audio-minimal-synthesis-result-2026-11-05.md)

freeze-audio-minimal-pnr.pyは既存directoryを上書きせず、同じ40入力だけを固定する。summarize-audio-minimal-pnr.pyは失敗も含めて保存し、配置未完了をSTA PASSとして扱わない。
