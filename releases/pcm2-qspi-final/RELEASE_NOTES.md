# KAGURA-HD PCM2 / ABI 1.4 — Release本文案

Tang Nano 9K / GW1NR-LV9QN88PC6/I5向け。640×360・16色、720p60 HDMI、2ページ、FILL・READ/WRITE・aligned BLIT、独立カーソル、48kHz PCM2音声を備えます。

配布対象は実機Demo使用済みの`kagura-hd-qspi-pcm2.fs`と`SHA256SUMS`です。Bitstream SHA-256は`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。Gowin Standard V1.9.12.04、Place1/Route2、内部STAはSetup +0.160 ns、Hold +0.484 ns、違反0/0。

SPI版はSetup −3.359 ns・違反4件のため通常配布から除外しています。リポジトリの`artifacts/experimental/spi-sta-fail/`にDO_NOT_PROGRAM付きで調査用に隔離しています。

QSPIではBEYOND 16 COLORSとMIDNIGHT TERMINALの実機HDMI動作を確認しました。Demoの目標30fps、最大通信速度、全PVT・長時間・複数基板の保証は含みません。元入力・ログ・ライセンスと出典はリポジトリ内に保存しています。公開時には最終ソースrevision・タグと適用する生成物/IP条件を記録してください。
