# KAGURA-HD PCMストリーミング QSPI — Release本文案

Tang Nano 9K / GW1NR-LV9QN88PC6/I5向け。640×360・16色、720p60 HDMI、2ページ、FILL・READ/WRITE・aligned BLIT、独立カーソル、Queue8を備えます。音声は48 kHzのPCM2と、Hostから連続補充するPCMストリーミングに対応します。

配布対象は`kagura-hd-qspi-pcm-stream.fs`と`SHA256SUMS`です。Bitstream SHA-256は`fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db`。Gowin Standard V1.9.12.04、合成後にPlace3/Route2で再配置配線しました。内部STAはSetup +0.177 ns、Hold +0.527 ns、違反0/0です。

試作段階で観測した音声の断続を受けて、設計監査と実機の再現試験を行いました。そのうえで、窓RAMの書込み選択をワード単位に変えた実装を採用しています。正式認定では計53回の実機試験を行い、陽性対照・陰性対照が正しく振る舞う中で、候補の49条件はすべて再現なしでした。BEYOND 16 COLORSの150秒メガデモ（全8シーン）も、timeout・PCM fault・音声欠落0で完走しました。

CSR 31のbit1は診断用です。アプリケーションからは書き込まないでください。SPI版は引き続き通常配布から除外しています。従来のPCM2版（`kagura-hd-qspi-pcm2.fs`）は置き換え済みです。

実機評価は有限の試験です。全PVT、長時間運用、複数基板での動作は保証の範囲外です。元入力、検証記録、ライセンスと出典はリポジトリ内に保存しています。公開時には、最終ソースのrevision・タグと、適用される生成物/IPの条件を記録してください。
