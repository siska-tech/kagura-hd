# 改善第3段階・実機測定準備

RASTERの帯を32x9の一時sourceへ9 FILLで合成し、各3段の描画を1 BLITへ変更。最後に他方pageの同一sourceから背景を復元する。source領域はx0..31/y300..308で、既存装飾を保持する。両pageが初期化済みで、この領域の唯一の更新者がこの同期関数であることが前提。途中エラーではPRESENTせず停止する。

旧版との150秒4,546時刻比較で両Framebuffer全byteとpalette一致。累積transactions 9,374,036→5,919,458（36.85%減）、commands 1,039,258→655,416（36.94%減）。startup込みの同一時刻列比較であり、実機高速化倍率ではない。独立画素oracle・異常系を含む4テストPASS。

デモ専用b16_qspi.c/.hへ既存transportを複製し、begin、transfer、endの累積usを追加。既存MIDNIGHT transportは変更なし。BUS行を1秒毎に出す。transferはPIO FIFO供給・受信・期限確認を含み、PIOのみの純粋な時間ではない。begin/endもGPIO・CS待ち等を含むHost区間で、GPU/PSRAM内部の分離測定ではない。計測自体の追加負荷があるため、比較時は同じ計測設定を使う。

FRAME詳細はRAMに最大4,600件保存し、音声停止後に出力する。通常の33ms schedulerで150秒最大4,546frameのため収容可能。将来scheduler高速化時は容量を再評価する。USB切断時など出力停止のリスクは終了後に限定される。1秒PERF/FAULT記録は再生中も維持。

hardware_run.pyはKAGURA_CAMPAIGN_DIRで新campaignを指定可能、既存one-shot markerとflash-write-verified.json必須条件を維持。BUS保存対応。旧campaignは再利用しない。この収集変更は構文検証のみで実機未実行。STOP到着時間はログ排出時間も含むため、映像終了時刻はFRAME timestampとcaptureで判定する。

RP2040最終ビルドPASS：text314900B、bss188648B、stack設定8192B。リンク成功、Flash filesystem境界検査PASS。RAM使用量増はframe記録147200Bが主因。実機のstack high-waterは未測定。

実機のBefore/After、PRESENT完了間隔とp95、音声再検証はNOT RUN。既存実機証跡のhashは旧binaryに対するもの。新binaryを実機確認済みと扱わない。RTL/ABI/clock/FPGA Flash変更0、release_ready=false。

残る通信の変更（CSR連続read、idle省略、IRQ等）は新しい区間測定結果と契約確認が必要なため未採用。30fps達成は実機で判定する。
