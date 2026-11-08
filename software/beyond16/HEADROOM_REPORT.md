> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# BEYOND 16 COLORS — Host optimization candidate

PCでの実装・回帰とRP2040 firmware 8構成を作成。実機操作0、RTL変更0、release_ready=false。

画素等価なロゴBLIT／caption結合により、固定seedの150秒でGPU commandsを486,788→476,117（約2.19%減）へ削減した。4,546frameすべての両Framebuffer全byte・palette・表示pageとseed再現が一致。これは実機fps／CPU余力の改善証明ではない。

|項目|判定|
|---|---|
|CPU計測実装|PASS（排他的wall-time分類＋checksum workload。CPU使用率ではない）|
|PC描画検証|PASS|
|DMA fake test|PASS|
|Host安全契約|PASS（PC回帰・コード確認の範囲）|
|RP2040ビルド|PASS（8構成）|
|RAM/Flash保護|PASS（offline境界・既存hash照合）|
|実機DMA評価|NOT RUN|
|実機CPU Headroom|NOT RUN / NOT MEASURED|
|実機30fps安定性|NOT RUN|
|RTL変更|0|
|Release|NOT READY|

既定はCPU＋PIO FAST ON、PROFILE_OFF、relative33ms、synthetic workなし、GPU協調処理なし。DMA、absolute30Hz、協調seed計算は分離した実験variant。Hybrid閾値は未選定。30fps到達、VECTORの速度向上、149ms停止の実機短縮は未検証。

|資料|内容|
|---|---|
|[CPU_HEADROOM_REPORT.md](CPU_HEADROOM_REPORT.md)|区間・排他計測・負荷比較・実仕事・core1確認|
|[DMA_DESIGN.md](DMA_DESIGN.md)|KAGURA-9参照、所有権、TX/RX、終端、異常停止、協調処理|
|[DMA_BENCHMARK.md](DMA_BENCHMARK.md)|サイズ・PCM別の有限試験、閾値選定条件|
|[SCHEDULER_REPORT.md](SCHEDULER_REPORT.md)|deadlineとPRESENT、実装範囲／未採用設計|
|[RENDER_OPTIMIZATION.md](RENDER_OPTIMIZATION.md)|画素等価性とBefore/After|
|[HARDWARE_TEST_PLAN.md](HARDWARE_TEST_PLAN.md)|承認後の投入順・保護・復旧|
|[MEMORY_MAP.md](MEMORY_MAP.md)|8構成のRAM/Flash量とlinker map|
|[HEADROOM_STATUS.json](HEADROOM_STATUS.json)|機械可読の判定と限界|

今回未実装の大きな変更は、VECTOR次frame maskの二重workspace、次sceneの先行描画／音声分割、真のHDMI vblank timestampによる2周期schedule、PRESENT完了基準scheduleのfirmware統合、core1利用。既存処理と安全に比較するため、効果を測れる小さな候補を先に用意した。残る案を実装済み・採用済みとは扱わない。

再現手順（実機ツールなし）:

```powershell
./software/beyond16/tools/build_pc.ps1
python3.12.exe software/beyond16/tools/test_headroom_variants.py
python3.12.exe software/beyond16/tools/test_headroom_render.py
python3.12.exe software/beyond16/tools/test_scheduler.py
python3.12.exe software/beyond16/tools/test_dma.py
python3.12.exe software/beyond16/tools/test_headroom_sdk.py
python3.12.exe software/beyond16/tools/test.py
python3.12.exe software/beyond16/tools/test_assets.py
./software/beyond16/tools/build_headroom_matrix.ps1
python3.12.exe software/beyond16/tools/verify_headroom.py
```

variant試験はHEADのソースをoutへ復元して旧版DLLを再構築する。比較基準commitはevidence/headroom-variants.jsonに記録。最終firmwareはout/headroom-firmware/<variant>/beyond16.binとELF、hashはevidence/headroom-firmware.json。Armコンパイラはsandbox内で既知のDLL relocation障害があり、通常権限のオフラインビルドで確認した。デバイスへのアクセスは不要。

履歴の実機レポート・backup・旧source freezeは上書きしない。今回の検証結果はheadroom接頭辞のevidenceへ分離した。既存STATUS.jsonは前回実機campaignの履歴として保持する。
