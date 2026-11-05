# Host通信の原因分析と限定最適化

以下はPC凍結時点の調査記録。後続の実機有限1周では平均transaction51.91µs、全体11.02fpsを観測した。[実機結果](HARDWARE_RESULT.md)を優先し、以下の「実機未実行」はPC段階の状態として読む。実機Before/Afterは未実行。

## Phase A：前作の確定値と分析可能な範囲

実機の5MHz PIO QSPI、wire 6,753,735B、transactions 839,060回、累積57.60秒、平均約68.65µs、最長352µs、周回約95秒、論理88秒、背景停止約3.5秒をそのまま採用する。57.60秒はGPU内部描画時間ではない。

前作`evidence/hardware/native-usb.log`は累積カウンタとscheduler区間の記録であり、transaction別のCSR/opcode/長さ/時刻traceを持たない。839,060回のうち各要因が何回だったかの確定分解、PIO転送・GPIO方向切替・GPU受理・PSRAM・FENCE内部時間の分離は**測定不能**。後から推定を実測へ置換しない。

ソースで確認できる発生源は次の通り。

- SDKの1 command：IDLE status、sticky clear、16B descriptor、submit、DONE polling、tag/error、sticky error、IRQ ACK。
- BLITは加えて毎回CAPS CSR6を読む。
- WRITE/READは最大64Bの窓に分割。WRITEはpointer resetとdata転送を追加、READは完了後pointer/data読出しを追加。
- 前作のBGM展開は64BごとのWRITEに加えて毎chunk READ検証を行う。背景は複数のシーンで両pageを再構築し、font/新規文字も小さいWRITEが多い。
- FILL/BLITは同期型。PRESENTはvblank反映まで待ち、DONE polling中にもtransactionが発生する。

前作の別PC記録`evidence/wire-report.json`には57,742 commands、680,154 transactionsがある。これは**前作PCモデルの88秒＋startup条件**で、839,060回の実機分類ではない。元ログの情報以上の割合は断定できない。

## Phase B：採用した2変更

1. **不変CAPSのsession cache**。`b16_cached_io`はprobeのID blockからCSR6を保存。以降のCSR6単独readだけを代替する。STATUS、DONE、tag、error、PCM statusはcacheしない。cacheは初期化で失効し、再接続時は新sessionとする。外部reset中の継続利用は認めない。
2. **sticky clearとdescriptorの連続write**。既存SDKに`KFB_PACK_DESCRIPTOR=1`というopt-inを追加。IDLE確認後にreg7..23を17B increment writeする。payload uploadがある場合もdata準備後にまとめて設定し、reg26 submitは独立のまま。descriptorはBUSY中に触らない。通常SDKの既定動作は変更しない。[独立差分](evidence/sdk-opt-in.patch)。

正常1 commandのtransactionを1回、BLITなら追加でCAPS1回削減する。結果は[Before/After](evidence/before-after.json)。全150秒で1,029,051 commandsを保ち、10,428,231→9,262,259 transactions、11.18%減。Wire bytesは50,973,583→49,396,848B。本編upload 0B。物理的な速度改善は未測定。

回帰：既存SDK suiteを既定・opt-inで各15件PASS。デモの独立画素oracle、両page、palette、PCM snapshot、fault/timeout、tag wrap、引数境界、submit ack失敗時の非再送もPASS。物理PIO波形を新たに測ったわけではない。

## その他の候補

|優先|候補|判断|
|---|---|---|
|A|不変CSR read削減|CAPSのみ採用。状態の古いcacheで安全性を壊さない|
|B|command batching|queue深度1なので複数descriptor投入は不可。1 descriptor内の連続CSR burstだけ採用|
|C|polling最適化|tag＋DONE＋error確認を維持。IRQ_nはGPIO10／open drain、pull-up実装未確認のため未採用。固定sleepでGPU完了を仮定しない|
|D|事前配置|両pageのheader/source strip＋PCMを開始前に展開。本編WRITE 0B。実機startup時間は未測定|
|E|差分|page別dirty mapを横runへ合併して背景FILL。波／rotoのようにほぼ全域を変えるsceneはFILL多めである|
|F|PIO/DMA/割当削減|実測で支配性を示せないため変更なし。PIO transportは前作を再利用、DMA新設なし。render loopはheapなし|

## 調査項目の実際

|項目|ソースで確認した契約|新メガデモ実測|
|---|---|---|
|1/2/4/8/16/64/512B|PSRAM転送は64B単位、raw READ上限256B。512B raw READは2 transaction、WRITEは512B可|PC CPU/modelベンチ済み。実機未実行|
|CSR READ/WRITE|6bit reg、READ header/count/dummy、WRITE header。increment/nonincrement|実機未実行|
|descriptor|16B、IDLE後にsubmit、queue1|既定/opt-in PC照合済み|
|tag/DONE polling|両方を確認しstickyとcommand errorを確認、IRQ ACK|PC異常系PASS。待機時間は実機未実行|
|FENCE|opcode0、命令完了境界。内部PSRAM時間とは分離されていない|CPU/model呼出時間のみ計測|
|PSRAM upload/read|4B alignment/mask、最大64B、die-relative4MiB|PCで全asset byte一致。物理時間未測定|
|BLIT/FILL|page矩形、範囲とalignmentを維持|PC count/bytes/CPU時間。物理描画時間未測定|
|PRESENT|vblank反映後DONE|PCは即時機能反映。待ち時間モデルなし|
|PCM|INDEX/DATA54/55、PREPARE/COMMIT/STATUS、22bit|PC制御・展開一致。prefetch/underrunモデルなし|
|IRQ|完了/エラーIRQ_n、open drain、pull-up必要|配線未確認、未使用|
|SPI/QSPI|レーン数はFPGA buildとHostで一致が必要|凍結候補QSPIのみ。SPI切替試験不可／未実施|
|PIO clock|120MHz RP、divider2、12 cycles/SCK、nominal5MHz、byte2nibble|設定・既存test再利用。物理SCK未scope測定|

連続throughputは「前のcommand完了を待って次をsubmit」の安全な形でしか測れない。GPU受付とPSRAM処理の独立の内部信号をHostだけで直接測定できない。次回はraw CSR長さ別curve、submitとwait別、PCM停止中／再生中の比較によりHost視点を細分化する。

プラズマ案の比較：全面115,200B/frame転送は不採用。低解像度CPU uploadも通常WRITE負荷が増えるため不採用。静止paletteのみは演算要素を欠くため不採用。事前配置tile＋リアルタイムsine位相合成＋paletteを採用。別案の実機比較測定は未実行で、採用案が最速とは断定しない。
