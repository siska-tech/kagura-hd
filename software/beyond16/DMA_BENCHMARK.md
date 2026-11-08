> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# DMA benchmark

実機DMA評価 **NOT RUN**。以下の全サイズの物理時間、CPU仕事量、stall時間、timeout率はNOT MEASURED。fakeの時間をRP2040性能へ換算しない。

|WRITE bytes|A CPU|B DMA eligibility|C threshold|
|---:|---|---|---|
|1/2/4/8/16/32|CPU|CPU fallback|未選定|
|64/128/256/512|CPU|non-inc reg24/25のみDMA|未選定|

READは全variant CPU。READ512Bは最大256Bを2transactionに分ける。PSRAM commandはSDKの64B window単位で、512B raw benchmarkと異なる。

firmwareの明示b入力でPCM STOPPED→PCM PLAYINGの各有限試験。10サイズ×16反復、raw pointer WRITE、CSR READ、PSRAM WRITE/READ照合、64fence、8FILL/BLIT/PRESENTを行う。PSRAM scratch=0x100000..0x101000、音声素材とpageの外。ABI 1.4 admission gate前のPSRAMアクセスは禁止。実機では未実行。

BENCH各callの総usと、サイズblockごとのbegin/CPU transfer/end/DMA setup/DMA completion wait/PIO terminal wait/FIFO無進捗iteration数/timeout/GPU errorを記録。stage行は4種callの累積deltaなので個別call時間と混同しない。DMA completionはCPUが観測した完了で、wire完了は別。profile regionと既存begin/end統計は異なる階層なので重複加算しない。FIFO stallは反復数であって物理stallのusではない。

CPUが実行した仕事は別workload試験のchecksum付きround数で比較する。現版のDMA waitはtight pollingで、そこでsynthetic workを走らせない。通信が短縮してもsetup/pack/pollによりCPU余力が低下し得る。DMAでCPU serviceが不要になってもwire時間が短縮するとは限らない。現在はどちらも実測なし。

threshold選定: 同一profile/seed/clock/PCM/logでA/Bの順序を交互にし、warmup後の中央値/p95/最大、setup込み総時間、達成work量、deadline miss、errorを比較。最小1回の交差点やPC fakeから選ばない。結果が小さい／不安定／安全条件未確認ならA維持。

証跡: evidence/dma-fake.jsonは4構成の機能PASS。evidence/headroom-firmware.jsonはbin/ELF SHA-256固定。実機性能表は承認後のcaptureで埋める。release_ready=false。
