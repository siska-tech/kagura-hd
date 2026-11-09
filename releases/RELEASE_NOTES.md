# KAGURA-HD 2026-11-09 — PCMストリーミング（QSPI・SPI）とFMデモ

Tang Nano 9K（GW1NR-LV9QN88PC6/I5）向けのフレームバッファ型グラフィックスエンジンです。640×360・16色、720p60 HDMI、2ページ、FILL・READ/WRITE・aligned BLIT、独立カーソル、Queue8を備えます。音声は48 kHzのPCM2と、Hostから連続補充するPCMストリーミングに対応します。

## 添付ファイル

|ファイル|内容|
|---|---|
|`kagura-hd-qspi-pcm-stream.fs`|選定版bitstream（Tang Nano 9K用）|
|`four-operators.uf2`|FOUR OPERATORS：ソフトウェアFM音源の132秒メガデモ（Raspberry Pi Pico用）|
|`midnight-terminal.uf2`|MIDNIGHT TERMINAL — FM EDITION：104秒の短編（Raspberry Pi Pico用）|
|`kagura-hd-spi-pcm-stream.fs`|SPI版bitstream（任意の構成。下記「SPI版」）|
|`four-operators-spi.uf2`|FOUR OPERATORSのSPI版（SPI版bitstreamと組み合わせる）|
|`midnight-terminal-spi.uf2`|MIDNIGHT TERMINALのSPI版（SPI版bitstreamと組み合わせる）|
|`demo-licenses.zip`|UF2に含まれるソフトウェアとフォントのライセンス文書|
|`SHA256SUMS`|上記ファイルのSHA-256|

## デモを試す

1. Tang Nano 9Kに`kagura-hd-qspi-pcm-stream.fs`を書き込みます（Gowin Programmerの「embFlash Erase,Program」など。Verify付きの操作は使わないでください）。
2. Raspberry Pi Pico（RP2040）を[配線表](https://github.com/siska-tech/kagura-hd/blob/main/docs/kagura-fb-host-api.md#配線転送)のとおりにつなぎ、GNDを共通にします。
3. PicoのBOOTSELボタンを押しながらUSBをつなぎ、現れたドライブ`RPI-RP2`へUF2をコピーします。
4. Tang Nano 9KのHDMIを、720p60と音声に対応した表示機へつなぎます。

Picoは起動から約5秒後に、自動でデモを始めます。もう一度見るときは、Picoの電源を入れ直してください。UF2を書き込むと、Picoにそれまで入っていたプログラムは消えます。起動から5秒以内にシリアル端末でPicoのUSBポートを開くと、`g`の入力を待ってから始まり、終了時に結果を表示します。

実機の動画：[FOUR OPERATORS](https://youtu.be/iypg81KaGmQ)、[MIDNIGHT TERMINAL](https://youtu.be/ocwRtPimfRQ)

## 選定版bitstream

SHA-256は`fad1537627f969abf3181eebc14ce18e252a740e99ab57f4f5abb46a4286b7db`（UserCode `0x00008039`）です。Gowin Standard V1.9.12.04で合成したあと、Place3/Route2で配置配線し直しました。内部STAはSetup +0.177 ns、Hold +0.527 ns、違反0/0です。

試作段階で観測した音声の断続を受けて、設計監査と実機の再現試験を行いました。そのうえで、窓RAMの書込み選択をワード単位に変えた実装を採用しています。正式認定では計53回の実機試験を行い、陽性対照・陰性対照が正しく振る舞う中で、候補の49条件はすべて再現なしでした。BEYOND 16 COLORSの150秒メガデモ（全8シーン）も、timeout・PCM fault・音声欠落0で完走しました。

CSR 31のbit1は診断用です。アプリケーションからは書き込まないでください。従来のPCM2版（`kagura-hd-qspi-pcm2.fs`）は置き換え済みです。

## SPI版（任意の構成）

QSPIを使えないHost向けに、同じ機能のSPI版を用意しました。SHA-256は`e9f67c683df4ab9c5f9ee382433d0a46f101578dbdcf66684da14992ce8c1767`（UserCode `0x0000694E`）です。QSPIとSPIはビルド時にどちらか一方を選ぶ別々の構成で、選定版QSPIのbitstreamは変わりません。配線は同じで、IO0がMOSI、IO1がMISOです。IO2とIO3は使いません。FPGAとUF2は、必ずSPI同士、QSPI同士で組み合わせてください。

内部STAはSetup +0.159 ns、Hold +0.456 ns、違反0/0です。SPI 5 MHz（既定）で3つのデモを完走し、2つのSPI版UF2も自動開始から完走しました。timeout、audio fault、音声の10 ms欠落はどれも0です。SPIの帯域はQSPIの1/4なので、5 MHzでは描画のフレーム数がQSPIより3〜14%少なくなります。音声には影響しません。

SPIクロックは5、6、8、10 MHzで試しました。8 MHzは3デモを完走した任意の高速設定で、動作を保証する周波数ではありません。10 MHz以上は、起動時の識別読出しから失敗するため非対応です。詳しくは[SPIパッケージ](https://github.com/siska-tech/kagura-hd/blob/main/releases/pcm-stream-spi/README.md)を参照してください。

## UF2の確認

2つのUF2は、それぞれ同じ基板で1回ずつ実行しました。FPGAには選定版をSRAMへ投入し、Picoには添付と同じUF2を書き込みました。ホストからは開始の指示を送らず、終わるまでUSBのポートも開いていません。どちらも自動で始まり、`STOP rc=0`、QSPI timeout 0で完走しました。HDMI録音の10 ms単位の欠落は左右とも0です。PCで生成した基準との1秒ごとの相関は、FOUR OPERATORSが中央値0.993、MIDNIGHT TERMINALが中央値0.997でした。UF2の中身がELFの内容と一致することもブロック単位で確かめています。

手順1のFlashへの書込みも、実機で確かめました。Tang Nano 9KのFlashに選定版を書き込み、Flashから起動したFPGA（UserCode `0x00008039`）で`midnight-terminal.uf2`を実行しました。結果は`STOP rc=0`、音声の欠落0、相関の中央値0.998です。

Flashへの書込みは、Gowin Programmer 1.9.11.03（Education版）の「embFlash Erase,Program」で成功を確認しています。このbitstreamはSecurityBitがONのため、Flashを読み戻せず、「Verify」付きの操作は必ず失敗します。また手元の基板では、1.9.12.04の`programmer_cli`での書込みが「Program failed」になり、Flashの内容が壊れました（1.9.11.03で書き直して回復）。

## 範囲

実機評価は有限の試験で、QSPI版もSPI版も1枚の基板で行いました。全PVT、長時間運用、複数基板での動作は保証の範囲外です。元入力、検証記録、ライセンスと出典はリポジトリ内に保存しています。MIDNIGHT TERMINALの絵は、プロジェクトの所有者が画像生成AIで作成したイラストを16色にしたものです（[出典](https://github.com/siska-tech/kagura-hd/blob/main/software/midnight_terminal/LICENSES.md#絵の出典)）。
