# 最終版のStandard Editionビルド

採用版はGowin **Standard V1.9.12.04**（build 89079）、GW1NR-9C / GW1NR-LV9QN88PC6/I5、SystemVerilog 2017、Place1/Route2、QSPIです。実機使用済みBitstreamは[公開用ディレクトリ](../releases/pcm2-qspi-final/README.md)に固定しています。

## 通常の再ビルド

Python 3と対象デバイスを利用可能なStandard環境を用意し、リポジトリルートで実行します。

```powershell
python tools/check-release.py
./tools/check-dependencies.ps1
./tools/build-fb.ps1 -Transport qspi -GowinExe 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe'
```

出力は`build/kagura-fb-qspi/`です。過去のログを保持する場合は先に別名へ退避してください。採用ファイルのある`releases/`を出力先には使用しません。SPIも`-Transport spi`で生成しましたがSTA未達のため[experimental](../artifacts/experimental/spi-sta-fail/README.md)へ隔離しています。通常配布対象外・書込み禁止です。

`rtl/fb/sources.f`、board top、platform serializer/clock/PHY、`phase1.cst`と`host.cst`の連結、`kagura-fb.sdc`を使用します。Setup ≥+0.100ns、Setup/Hold違反0、負の解析なしを検査します。ReportOnlyを合格判定に使用しません。

## 元ビルドを再現する入力

採用版の元入力は`releases/pcm2-qspi-final/build-inputs/`の40ファイルです。`source-input-manifest.json`と照合できます。元の生成HDMIと、元の`tools/build-fb.tcl`も含みます。ルートのスクリプトには配置配線option指定などの利便性変更があるため、元スクリプトを別途保存しています。

元入力だけで独立実行する場合は、`build-inputs/`全体を新しい作業ディレクトリへコピーし、その直下に空の出力ディレクトリを作成、出力ディレクトリ内から次を実行します。

```powershell
& 'C:/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe' ../tools/build-fb.tcl qspi
```

`build-inputs`の生成HDMIを保持するため、この再現経路ではHDMI生成スクリプトの再実行は不要です。STA/P&RレポートとBitstreamを保存・照合してください。生成時刻ヘッダやツール環境によりファイル全体のhashが異なることがあるため、再生成物を元の実機確認済みファイルと同一扱いしません。

採用結果はSetup +0.160ns、Hold +0.484ns、Logic 7796、FF 5239、CLS 4247、BSRAM 19。ビルド成功だけで実機試験を代替しません。
