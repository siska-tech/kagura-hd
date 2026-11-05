# Host固定費 実機A/B

同じ-O2・低解像度VECTOR・ログ・区間計測条件で、FAST OFF/ONを各1周。各150秒、各有限ベンチ。単発測定であり分散・PVTの保証なし。

|Scene|OFF fps|ON fps|ON平均call ms|
|---|---:|---:|---:|
|BOOT|30.20|30.20|19.80|
|HYPERSPACE|30.25|30.30|19.99|
|RASTER WAVES|29.90|29.95|32.35|
|PLASMA ENGINE|30.00|30.20|17.21|
|ROTOZOOM|30.00|30.12|27.85|
|BLIT STORM|30.32|30.32|17.46|
|VECTOR WORLD|22.10|25.70|37.17|
|FINALE|29.20|29.30|16.67|

OFF: timeout=0, PCM status fault=[0], 平均transaction=18.235us, 全体fps=28.975, 最悪call=182.416ms。

ON: timeout=0, PCM status fault=[0], 平均transaction=13.359us, 全体fps=29.527, 最悪call=149.040ms。

Release NOT READY。最後はON firmwareで音声停止、フィナーレ保持。両投入で全Flash backupと読戻しを実行し、filesystemとerase終端以降一致。FPGA Flash変更0。RTL/clock/ABI変更0。

旧未最適化版との比較はコンパイラ設定とVECTOR画質も異なるため、Host変更の効果判定には上記OFF/ONを使用する。詳細audio／bench／scene PNGはevidence/host-ab-OFF, host-ab-ON。原captureと復旧像はbuild/beyond16-host-ab-2026-11-06。

音声：両版とも実音150.00秒、10ms RMS低音量欠落0、PCM status fault0。独立underrun counterはなく全sampleの証明ではない。

scene fpsは名目scene秒数で記録frame数を除算し境界に約1frameの偏りがある。約30fpsは全frame期限内を意味しない。完了間隔近似のp95／最悪／33.5ms超過率はevidence/host-ab-timing.json。近似時刻はFRAME開始+call時間で、PRESENT直後そのものではない。

初回CMake環境指定不足とUSB再列挙前の機器検出で試験開始前に停止した。完了済み書込み・ベンチは再送せず、未開始段階のみ継続。実機timeout・GPU faultによる再試行はない。
