# RTL

現行最終版はPCM2 ABI 1.4 / QSPIです。合成対象は[`fb/sources.f`](fb/sources.f)、board topは[`kagura_fb_top`](../boards/tang-nano-9k/kagura_fb_top.sv)です。採用Bitstreamの入力とルートRTLの一致を`python tools/check-release.py`で確認します。

|ディレクトリ|用途|
|---|---|
|fb|Host・CSR・命令・FILL/BLIT・PSRAM転送・scanout・cursor・audio endpoint|
|audio|PCM2合成、prefetch、音声CSR、HDMI向けclock crossing|
|hdmi|720p映像、TMDS、音声packet|
|memory|RAM wrapper、async FIFO、PSRAM PHY/controller|
|platform|Gowin PLL・CLKDIV・GSR・serializer|
|bus|SPI/QSPI transportと継承Host adapter|
|core / vdp / boot|旧Kagura-9の共通部品・診断構成。現行Host ABIの入口ではありません|

共通audio synthは旧6ch構成も実装できますが、現行HD topはPCM_ONLYを選択します。FPGAの最終版入力、元ツール設定、STA結果は[公開成果物](../releases/pcm2-qspi-final/README.md)、検証入口は[sim](../sim/README.md)を参照してください。
