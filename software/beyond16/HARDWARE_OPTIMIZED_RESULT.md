# 改善版 実機結果

有限ベンチと150秒全8scene正常完走。前回とログ／通信計測設定が異なるため、厳密な同条件Before/Afterではない。改善版の観測値として報告する。

|Scene|前回fps|改善版fps|平均frame ms|最悪frame ms|完了間隔p95 ms|
|---|---:|---:|---:|---:|---:|
|BOOT|14.50|19.40|49.67|116.45|50.50|
|HYPERSPACE|15.35|17.40|56.24|115.75|67.06|
|RASTER WAVES|8.35|11.95|82.48|148.90|84.03|
|PLASMA ENGINE|11.65|20.60|44.43|148.89|83.28|
|ROTOZOOM|6.52|15.28|64.08|115.59|83.99|
|BLIT STORM|14.40|28.16|34.16|82.23|50.00|
|VECTOR WORLD|3.90|4.20|238.08|365.77|317.03|
|FINALE|21.00|21.40|26.35|611.81|83.03|

timeout=0、PCM status fault=[0]。音声実音150.01s、10ms RMS低音量欠落の最長0ms。独立underrun counterはなく全sampleの無欠落証明ではない。

通信区間 window=148.217s、累積秒={'begin_us': 34.017524, 'transfer_us': 60.559014, 'end_us': 16.3933}。transferはFIFO処理と時刻確認を含み、GPU内部時間ではない。計測負荷込み。

現在は改善版firmwareのフィナーレ保持、音声停止。全Flashバックアップと読戻し比較でfilesystem／erase終端以降の一致を確認。FPGA Flash書込み0、固定候補SRAM投入のみ。RTL変更0。release_ready=false。

証跡：evidence/hardware-optimized/、原HDMI動画とFlash backup：build/beyond16-hardware-optimized-2026-11-06/。前回記録は保持。
