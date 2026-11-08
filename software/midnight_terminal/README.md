# MIDNIGHT TERMINAL — FM EDITION

[![実機動画（YouTube）](https://img.youtube.com/vi/ocwRtPimfRQ/maxresdefault.jpg)](https://youtu.be/ocwRtPimfRQ)

雨の夜、閉店まであと少し。バーの店員ミオと言葉を交わし、カウンターの端にある古い端末を覗きこむと、来店記録が「あなたは既に退店しています」と答える。104秒の自動再生で見せる、オリジナルの短編です。

2026-11-09に全面的に作り直しました（以前のPCM2版は git の履歴にあります）。音はすべて、RP2040の2つ目のコアで動くソフトウェアFM音源がリアルタイムに合成します。合成した音は、[選定版bitstream](../../releases/pcm-stream-qspi/README.md)のPCMストリーミングでHDMIへ送ります。タイトル、バー、端末の絵は、所有者が画像生成AIで作って提供したイラストを、16色にしたものです（[出典](LICENSES.md#絵の出典)）。

## 流れ

|時刻|シーン|映像|音|
|---|---|---|---|
|0–11 s|TITLE|雨の夜の店の外観。自販機、電柱、濡れた路面の反射。雨はパレット循環で降らせる|雨音、ゆっくりしたEPのコード|
|11–45 s|BAR|ミオ、逆光の酒棚、ペンダント照明、雨の窓、ネオン「NOCT」。会話、まばたき、選択肢|90 BPMのローファイジャズ（EP、ウォーキングベース、ヴィブラフォン、ブラシ）、文字送りの音|
|45–58.5 s|TERMINAL|ブラウン管の端末で来店記録を照合する。画面が乱れていく|ペダルのベースと不穏なアルペジオ、打鍵音、テープストップ|
|58.5–74 s|ANOMALY|赤く染まった店内に、架空のログがあふれる。BLITで画面を裂く|警報、スタッター、ビットクラッシュ|
|74–83 s|MESSAGE|「警告：この記憶はあなたのものではありません」|ドローンと心音|
|83–96.5 s|RESTORE|何事もなかったような店内。「……ご注文は、お決まりですか？」 一瞬だけ目が赤くなる|雨とコードが戻る|
|96.5–104 s|END|タイトルとクレジット|最後の和音と余韻|

## 構成

|部分|内容|
|---|---|
|台本（[story.py](tools/story.py)）|台詞、選択肢、端末の文字、ログ、すべての時刻。映像と音（文字送りや打鍵の効果音）が同じ台本を参照する|
|絵（[bar_reference.py](tools/bar_reference.py)、[ai_art.py](tools/ai_art.py)）|提供されたイラストを640×360に縮小し、16色（RGB444）へ4×4の秩序ディザで量子化する。UIやアニメーションで使う色（ダイアログ、雨の3位相、端末の画面と文字、ネオン）を固定し、残りをk-meansで選ぶ。タイトルの雨は、絵の上に重ねたパレット循環。端末の画面ガラスは単色にして、その上に文字を書く。まばたきは、目を閉じた別のイラストから目元だけを位置・傾きを合わせて合成し、赤い目は瞳の色だけを置き換える|
|素材（[build_assets.py](tools/build_assets.py)）|画像は参照窓4 KiBのDEFLATEで、3枚で約177 KB（タイトル75 KB、バー57 KB、端末45 KB）。RP2040のFlashに置く。フォントは台本で使う字だけ（M+ 126字、美咲179字）|
|音源（[mt_fm.c](src/mt_fm.c)）|4オペレータFMを7声（EP 4声、ベース、ヴィブラフォン、効果音）。ブラシ、ライド、キック、リム、雨音も合成する。ステレオディレイ、テープストップ、スタッター、ビットクラッシュをかける。描画処理はすべて整数演算|
|映像（[mt_show.c](src/mt_show.c)）|FILL・COPY・PALETTE・PRESENT・WRITEだけを使う。画像は2ページに展開して切り替える。文字は1行ずつ4bppのスキャンラインにしてWRITEで書く。選択肢を閉じたあとは、圧縮画像からその範囲だけを書き戻す|
|ストリーミング（[stream.c](src/stream.c)）|FOUR OPERATORSと同じ方式。半面の補充を、描画コマンドの合間に分割して進める|
|展開器（[mt_inflate.c](src/mt_inflate.c)）|RFC 1951の展開器（固定・動的ハフマン、4 KiBの窓）。PCでzlibの出力と一致することを確認|

旧版から残しているのは、他のデモと共有する部品だけです。

- `src/mt_lz.*`、`src/mt_qspi.*`
- `vendor/`：フォント、PIO、ライセンス
- `tools/pack_bgm.py`
- RTLの転送試験：`tools/prepare_qspi_rtl.py`、`test_qspi_rtl.sh`、[QSPI_REPORT.md](QSPI_REPORT.md)

## 作る・見る

すぐに実機で見るときは、[Releases](https://github.com/siska-tech/kagura-hd/releases/latest)の`midnight-terminal.uf2`を使います。手順は[ルートのREADME](../../README.md#すぐに試す)にあります。約5秒後に自動で始まります。

```bash
# 素材の再生成（Python 3.12、Pillow、NumPy。保存した配布フォントのアーカイブだけを使う）
python software/midnight_terminal/tools/build_assets.py build/midnight-terminal/art
# PCプレビュー（WSL / Linux）。KFBの振る舞いモデルに、実物のSDK・映像・音源をつなぐ
bash software/midnight_terminal/tools/build_pc.sh
build/midnight-terminal/mt_pc --wav build/midnight-terminal/pc.wav
build/midnight-terminal/mt_pc --video - | ffmpeg -f rawvideo -pix_fmt rgb24 -s 640x360 -r 30 -i - -i build/midnight-terminal/pc.wav -vf scale=1280:720:flags=neighbor out.mp4
```

```powershell
# RP2040のFlash用イメージ（ELF・bin・hex）。画像とフォントはFlashに置き、音源の内側のループはRAMに置く
./software/midnight_terminal/tools/build_rp2040.ps1
# 配布用UF2（自動開始。build/midnight-terminal/rp2040-release/midnight_terminal.uf2）。変換にはpicotool 2.xを使う
./software/midnight_terminal/tools/build_rp2040.ps1 -Release
# 実機での実行：FPGAはSRAMへ投入する。RP2040は、Flash全体（2 MiB）を退避してからデモを書き込み、
# 終了後に退避した内容を書き戻して、元と一致することを照合する
python software/midnight_terminal/tools/run_hardware.py build/midnight-terminal/hw-XX --flash --elf build/midnight-terminal/rp2040/midnight_terminal.elf --elf-sha <sha256> --reference build/midnight-terminal/pc.wav
# 配布用UF2：ホストから開始せず、終わるまでUSBのポートも開かずに自動開始を確かめる
python software/midnight_terminal/tools/run_hardware.py build/midnight-terminal/hw-XX --flash --autostart --uf2 build/midnight-terminal/rp2040-release/midnight_terminal.uf2 --elf build/midnight-terminal/rp2040-release/midnight_terminal.elf --elf-sha <sha256> --reference build/midnight-terminal/pc.wav
```

## 実機結果

2026-11-09に、Tang Nano 9KとRP2040（120 MHz、QSPI 5 MHz）で実行しました。FPGAには選定版`kagura-hd-qspi-pcm-stream.fs`（`fad15376…`）をSRAMへ投入し、FPGAのFlashには書き込んでいません。RP2040には、Flash全体を退避したうえで最終イメージ（`528dc2ef…`）を書き込みました。終了後に退避した内容を書き戻し、全2 MiBが実行前と一致することを確認しています（RP2040のFlash書込みは2回）。FPGAは承認済みQueue8に戻しました。

途中で見つかった不具合は次の3つで、いずれも修正済みです。

- **音声補充の停止：** 選択肢を閉じたあとの部分復元で、画像全体を展開する間に音声の補充が止まり、37秒でアンダーランした（`hw-ref`、rc=−20）。展開中も64バイトごとに補充を回すようにした。
- **グリッチの引数エラー：** 異常シーンのグリッチで、コピー範囲が画面の下端を越えることがあり、SDKが引数エラーにしていた（`hw-flash1`、rc=−1）。範囲を制限した。
- **Flashの書き戻し失敗：** 同じ回で、実行スクリプトの引数の順序が誤っていたため、Flashの書き戻しに失敗した。退避した内容を手で書き戻し、読み戻しで一致を確認したうえで、スクリプトを直した。

|項目|結果|
|---|---|
|終了|`STOP rc=0`。QSPI timeout 0、device error 0|
|開始前の画像の展開と転送（2ページ）|約1.2 s|
|PCMストリーミング|1218半面。HALF_FREEを検出してから公開するまでの最悪は56.5 ms（期限85.3 ms）|
|FPGAの状態|ch STATUSは左右とも0x03（UNDERRUNとfaultはなし）、HDMI STATUSは0x00|
|音源|core 1の稼働率は約61%（104秒中63.0秒）。core 0が合成を待った回数は0。ハードクリップは0|
|HDMI録音|基準に音がある区間で、録音が10 ms単位で欠けた箇所は左右とも0。PCで生成した基準との1秒ごとの相関は、中央値0.997、最小0.983。キャプチャとのクロック差は約16 ppm|
|映像|3035フレーム（平均約29 fps）。シーン別には330 / 985 / 405 / 445 / 244 / 405 / 221。まばたきもHDMIで確認した（[静止画](evidence/hardware-blink.png)）|

実機の画像は[contact sheet](evidence/hardware-contact-sheet.png)、記録は[evidence/](evidence/)にあります。この結果は、1枚の基板で1回ずつ実行した有限の試験です。

### 配布用UF2

配布用UF2（`aa37c59d…`、ELF `00d0910a…`）も、2026-11-09に同じ基板で1回実行しました（`hw-uf2-auto`）。Flash全体を退避してからUF2を書き込みました。ホストからは開始の指示を送らず、終わるまでUSBのポートも開いていません。デモは自動で始まり、`STOP rc=0`、QSPI timeout 0、3036フレームで完走しました。録音の10 ms単位の欠落は左右とも0、PCの基準との相関は中央値0.997、最小0.983でした。終了後に書き戻し、全2 MiBの一致を確認しています。UF2の中身はELFの内容とブロック単位で一致しました。記録は[release-uf2-result.json](evidence/release-uf2-result.json)です。

同じUF2を、FPGAのFlashに書き込んだ選定版から起動した状態でも1回実行しました（`--fpga-from-flash`、SRAMへの投入なし）。`STOP rc=0`、音声の欠落0、相関の中央値0.998、最小0.980で、Releasesの手順どおりの構成でも動くことを確認しています（[記録](evidence/release-uf2-fpga-flash-result.json)）。Flashへの書込みは、Gowin Programmer 1.9.11.03（Education版）の「embFlash Erase,Program」で成功を確認しています。このbitstreamはSecurityBitがONのため、Flashを読み戻せず、「Verify」付きの操作は必ず失敗します。また手元の基板では、1.9.12.04の`programmer_cli`での書込みが「Program failed」になり、Flashの内容が壊れました（1.9.11.03で書き直して回復）。

自動開始の有無は`KAGURA_AUTOSTART_MS`で切り替えます。既定のビルドでは0で、上の`528dc2ef…`と読み込まれる内容が完全に一致することを確認しました。

## ライセンス

[LICENSES.md](LICENSES.md)
