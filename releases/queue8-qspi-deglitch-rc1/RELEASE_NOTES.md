# Queue8 QSPI CSデグリッチ RC1

Tang Nano 9K用のフルHDMI評価版。QSPI 5 MHz、Queue8、720p60、48 kHzステレオPCMを使用します。

同期済みCS highを3クロック連続で観測してからQSPI受信の終了を確定します。
同一波形の異常注入では、1・2クロックのHighから誤ったCSR0 WRITEが生じる事象を抑制しました。

内部STAはSetup +0.659 ns、Hold +0.527 ns、違反0端点。
実機メガデモは150秒・全8シーンを完走し、324,936件を全件回収しました。
Queueエラー・timeout・PCM faultは0。左右音声の欠落検出は0でした。

実機評価は有限試験です。自然発生の短Highを捕捉して抑制を確認する試験は残っています。
試用時は付属のSHA256SUMSで画像を照合し、FPGA SRAMに一時投入してください。
