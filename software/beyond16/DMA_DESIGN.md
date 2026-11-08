> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# PIO + DMA design

実験実装。既定transportはA（CPU＋PIO FAST ON）。RTL、PIO program、ABI、120MHz、5MHz QSPI設定を変更しない。実機未評価につきDMA高速化は主張しない。

## KAGURA-9参照

隣接repo ../Kagura/software/micropython/kagura/transport_rp2.py の_init_dma/_xfer_dma/_abortを参照した（../kagura-9という名前のrepoは存在しない）。TX/RXの2channel、32bit転送、TX read increment／FIFO固定write、RX FIFO固定read／4B sink固定write。DREQはPIO index×8+SM、RXは+4。明示chainingなし、完了はactive polling。private word bufferとsinkが寿命を保持する。通常FIFOはTX4／RX4、autopush8bit。終端はRX回収だけでは最終SCKに先行するため前作はtail待ちを置く。

再利用するのはword packing、TX/RX paired drain、DREQ、所有権の考え方。HDは6bit register、queue depth1、descriptor16B、payload window最大64B、別のreg26 submit。KAGURA-9のqueued bit31、BUSY線制御、register gatingをコピーしない。HDはSDKのwait_idle→descriptor→submit→tag/DONE/ack直列化を維持する。

## Variant

|値|経路|
|---|---|
|A / B16_TRANSPORT=0|全て既存CPU経路。既定|
|B / 1|64〜512B、non-increment、reg24または25のWRITEだけDMA。その他CPU|
|C / 2|同条件でB16_DMA_THRESHOLD以上のみDMA。既定閾値0で無効|

64はBの安全な評価範囲の下限で、性能上の最適閾値ではない。C-test128は分岐試験用で採用閾値ではない。実測で総時間とwork量を比較するまでCの閾値は未選定。READ DMAは未導入。通常CSR/descriptorは短いためCPU、本編中PSRAM uploadは0Bで、DMAがscene fpsを改善するとは限らない。

## 所有権と順序

1. beginで方向を取得しCSを下げ、既存CS setupを満たす。
2. CPUでheaderを送信しRXを回収する。
3. caller byte bufferをprivate uint32_t words[512]へpackする。CPUがowner。非再入、core0専用、転送中buffer更新なし。
4. 2channelのcontrol blockをtransactionごと設定する。RXを先にarm、TXをstart。chaining/IRQなし。DMAがwordsのread owner、sinkのwrite owner。
5. TXとRX両完了をpollする。deadline毎確認。転送count=0とAHB READ/WRITE errorなしも確認。
6. ownershipをCPUへ返す。ただしwire完了とは扱わない。endでTX FIFO emptyかつSM PC==pull_pcを確認して最終SCK lowを待つ。
7. 既存hold→CS high→interval。その後にだけreturnする。RX drainはWRITEにも必須。

DMA stagingは2048B＋sink4B、呼出元stack bufferの寿命に依存しない。並列caller／IRQからのtransport利用は非対応。資源claim失敗は既にclaimしたchannel/SM/programを解放してIO error。黙ってfallbackしない。

## 異常

timeoutまたはDMA errorで両channel abort→PIO停止→FIFO clear／SM restart→pull PC／SCK low→CS hold／release／interval→IO入力。faulted latch後は新transactionを拒否。DMA errorとtimeoutのcounterを区別する。未確定commandの再送なし。SDKのGPU timeoutはapplication error latchでmainを停止し、以後tickを発行しない。自動probe/reset/replayなし。

READはcount byteのrelease bit30→dummy1byte→data→terminal確認を保持。GPU page、descriptor、PCM素材をDMA所有にしない。benchmarkも最初に厳密ABI 1.4／CAPS=255を確認する。

fake試験: 10長さのword同一、全READ長、方向release位置、RX喪失、TX stall、DMA TX/RX stall、TX/RX完了後のPC stuck、AHB error、資源一部失敗、CS release、fault後非再送。モデルは物理FIFO／DREQ latency／DMA errata／信号品質を保証しない。

## GPU待機協調処理（別variant）

B16_COOP=ONはDMAとの同時選択をCMakeで拒否。GPU BUSYを確認し、timeout未到達、PRESENT以外の場合にだけ星seed cacheを1要素生成する。CPU専用1024B、最大256要素、GPU source/targetにもdescriptorにも触れない。cacheはinitでseedと有効数をリセットし、未生成値は従来hashへfallback。GPU error／timeout後はcallbackを進めずapplication停止。callbackは1hash、IO／待ち／割込み禁止操作なし。完了検知の追加遅延は最大1hashの実行＋次status transaction（IRQ遅延を除く）。µs上限は実機NOT MEASUREDであり採用前に確認する。PRESENT内はcallbackを明示禁止。大きな次frame mask二重bufferは追加していない。
