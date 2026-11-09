# SPI overlay（任意のSPI構成）

SPI（`HOST_LANES=1`）ビルドだけで使う差し替えRTLです。`tools/build-fb.tcl spi …` は、`rtl/fb/sources.f` のファイルと同じ名前のファイルがここにあると、そちらを読み込みます。QSPIのビルドは常に元のファイルを使います。そのため選定版QSPIの入力は変わらず、`python tools/check-release.py` も通ります。

SPI対応は任意で、目的はQSPIを使えないHostでも動かせるようにすることです。QSPIとSPIはビルド時にどちらか一方を選び、実行時の切替えはしません。2026-11-09に、このoverlayでビルドしたbitstreamを配布対象にしました（[パッケージ](../../releases/pcm-stream-spi/README.md)）。

|ファイル|元のファイル|変更点|
|---|---|---|
|`kagura_spi_adapter.sv`|`rtl/bus/kagura_spi_adapter.sv`|RC1の/CS Highの確定（同期後3サンプル）を、SPIでも有効にする|
|`kagura_fb_scanout.sv`|`rtl/fb/kagura_fb_scanout.sv`|`PALETTE_BSRAM=1`（既定）：192 bitのパレットを2重に保持するFFとクロスドメイン経路をなくし、2バンクの32×12 BSRAMに置き換える。`scan` の行条件は、行末（`cy` が変わるのと同じエッジ）でレジスタに入れる|
|`kagura_fb_commands.sv`|`rtl/fb/kagura_fb_commands.sv`|READ/WRITEのアドレスと語数をレジスタから出す。MEM_REQは、保持済み記述子が有効になってから2サイクル以上あとなので、遅延は増えない|
|`kagura_fb_cursor.sv`|`rtl/fb/kagura_fb_cursor.sv`|行の半分（`logical_y`）と行条件を行末でレジスタに入れる。36 bitの色は2スロットのBSRAMを通してクロスドメインさせる。要求は1回ずつ順に適用されるので、両側のスロット番号は同じ順で進む。FFで渡すのは26 bitの位置・バンク・表示ビットだけ|

どの変更も機能は元のファイルと同じで、配置配線を楽にするためだけのものです。HDMIのカウンタはリセット時に `cx=cy=0` になるので、リセット直後の値も一致します。

## パレットBSRAMの動作

PRESENTを受け付けると、system側はまず `present_palette` の16色を1サイクルに1色ずつ、表示中でない側のバンクへ書き込みます。`present_palette` は `present_done` まで変わりません。命令エンジンが `PRESENT_WAIT` で待つためです。書き終えたら、バンク番号をtoggleでpixel側へ渡します。pixel側は垂直帰線でバンクとページを同時に切り替えます。BSRAMの登録済み読出しが従来の `color_select` 段の代わりになるので、RGBの遅延は変わりません。PRESENTの完了は16 system cycle遅れます。そのため、垂直帰線の直前（約0.3 µs以内）に受け付けたPRESENTは、1フレーム後に反映されることがあります。

## 試験

```sh
bash tools/test-fb-spi.sh
```

- `tb_fb_palette_bsram`：凍結版のscanoutとSPI overlay版を同じ入力で動かし、全画素のRGBを比較する。PRESENTの時刻は乱数で決め、垂直帰線の直前も含める。読み出すバンクを誤る変異と、書込みindexをずらす変異は、どちらも検出できることを確認済み
- `tb_fb_cursor`（SPI overlay、`PIPELINE_MAILBOX=0`と`1`）：参照モデルと比較する。色スロットを逆にする変異を検出できることを確認済み
- `tb_spi_cs_glitch`：SPI 5 MHzで/CSに短いHighを入れても、フレームが切れないことを確かめる。フィルタなしで壊れることも確かめ、試験の感度を示す
- `tb_fb_host` と `tb_fb_board_qspi`：LANES=1、Queue8、PACKET_FIRST=1

## 状態（2026-11-09）

`tools/build-fb.tcl spi 4 2 8 0 1 auto`（P4/R2、Queue8、PACKET_FIRST）で、数値STAゲートを通過しました。

- Setup +0.159 ns、Hold +0.456 ns、Setup/Hold違反0/0、Recovery +8.190 ns、Removal +0.533 ns
- CLS 4245/4320、BSRAM 25/26
- 同じネットリストでも、P3は−3.427 ns、P2は−4.370 nsでした。STAの余裕は配置に強く依存します。

このビルドを [artifacts/validated/kagura-hd-spi-pcm-stream.fs](../../artifacts/validated/kagura-hd-spi-pcm-stream.fs) として固定しました。実機での確認とSPIクロックの範囲（既定5 MHz、8 MHzは任意の高速設定、10 MHz以上は非対応）は、[パッケージ](../../releases/pcm-stream-spi/README.md)にまとめています。PVT、外部I/O、複数基板は評価していません。

overlayを変えると、ネットリストも配置も変わります。STAの余裕は配置に強く依存するので、変えたあとはSTA、`tools/test-fb-spi.sh`、実機での確認をやり直し、パッケージを作り直してください。`tools/check-release.py` は、ここにあるファイルがパッケージの入力と一致することを確かめます。経緯は [docs/issues/spi-sta-fail.md](../../docs/issues/spi-sta-fail.md) にあります。
