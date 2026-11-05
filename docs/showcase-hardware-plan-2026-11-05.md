> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# SHOWCASE-HW-01 実機固定計画

今回のユーザー指示「実機で検証しましょう」により、PCM2 STA候補SHA `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`だけをSRAMへ最大1回投入する。Flash/FW/RP filesystem変更なし、再試行なし、最初の不一致/timeout/応答異常で停止し復旧する。release_ready=false / DO_NOT_PROGRAMは維持する。

最大3600秒、通常job最大120秒、コマンドtimeout3000ms、全デモ1周だけ最大900秒。新しいRTL/SDC/CST/Bitstream生成、Push/Merge/Releaseを行わない。

順序：COM/JTAGとKAGURA-9映像→RP全Flash/boot.py/UF2 hash→console/PIO解放とGPIO安全状態→RAM13packet load/空きheap→1回SRAM→ABI1.4/CAPS FF→PSRAM67ケース→5章12画像とページCRC→PCM silence/左/右/2tone→BGM24 chunkのCRCとguard→BGM capture/reference相関→6章288更新を1周。

PSRAM scratchは299968..326143、FBは0..230399、PCMは0x80000..0xDDBFF / 0xE0000..0x13DBFF。BGM guardは各buffer直前/直後16Bで固定。旧の67ケースと同じ独立4B・guard・offset・mask・旧64B条件を新配置で再確認する。

各静止画はPC独立pixel oracle由来の両ページCRC、RGB ROI許容50/255、明部pixel probe95%、cursor probe80%/許容60で判定。PAL/PRESENT検査にだけ右下page markerを追加する。静止状態のpage/palette対応を検査し、全VBlankの物理原子性を証明したとは扱わない。

音声は較正済みUGREEN DirectShow/native48kHz stereoで取得。左右bit一致を要求しない。silence RMS<=8、単独toneの周波数±3Hz/振幅±25%、非駆動ch<=max(20LSB,信号RMSの1%)、2tone pan比5±15%/説明energy>=85%。BGMは独立PCM参照のdownsample4・±1000ppm/100ppm stepの有限相関探索でmono>=0.90、各ch>=0.85、gain±25%。時計/PVTやbit透過性の保証ではない。測定器selftestを投入前に行う。

全デモは実時間telemetryとAV録画、6章終了/288更新/cursor CRCを確認。FPGA出力sample位置やFIFO水位の未公開項目は未確認のまま。Capture側異常ではraw実行を1回だけ中断し、診断再送せず復旧する。

終了時はQSPI deinit/安全GPIO→既存FlashからKAGURA-9へReprogram→RP全Flash hash→通常soft reset/banner→console resume/HDMI確認。過去にユーザーが保留を承認した復旧fs file hash不一致は保留のまま、別復旧fsを投入しない。RP bin/UF2/boot.py hash不一致は保留せず投入を禁止する。

凍結manifest、全条件・期待値、原本ログは`build/showcase-hardware-2026-11-05-v1`。失敗後に条件を変更したり別候補を投入しない。
