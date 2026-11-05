# MIDNIGHT TERMINAL 実機投入結果 — 2026-11-05（日本時間）

> この報告は実機評価時点の記録です。使用したFPGA Bitstreamは、その後 [PCM2 QSPI最終版](../../releases/pcm2-qspi-final/README.md)として選定しました。本文の性能目標未達・未検証項目・当時の機器状態は記録として保持しています。


**RP2040のC版を書込み、5MHz QSPIで本編を1周再生・HDMI録画できた。現在はループ再生中。Release NOT READY / `release_ready=false`。**

## 投入と保護

ユーザーの「実機投入」「RAMには投入できないんで書き換えてください」により、今回のRP2040 firmware Flash書換えを実施した。FPGAは既存のPCM2候補04をSRAMへ1回だけ投入した。FPGA Flash、RTL、Controller/PHY、PLL、SDC/CST、既存Bitstreamは変更していない。

|項目|結果|
|---|---|
|対象RP2040|Pico / Flash UID REDACTED_DEVICE_UID|
|元の2MiB Flash SHA-256|`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`|
|元Flash退避|ROMから全量save＋verify、MicroPython経由の事前SHAとも一致|
|投入FPGA SRAM SHA-256|`642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`|
|投入RP bin SHA-256|`a0bbf0d6f2058eed09414f162e8bc462d7ac8fdf7e019766c25d5a1414aec027`|
|C bin長|480,308B|
|RP消去sector上限|`0x10076000`|
|既存filesystem|`0x100A0000..0x10200000`、書換え後の全Flash readbackで元とbyte一致|
|RP write / FPGA SRAM write|各1回、診断再試行なし|
|STA保護|278ファイルのSHA不変|

当初の非圧縮USB版は約762KBで、既存filesystemの開始640KBに重なることがROM metadataで判明した。**その版は書いていない。** BGM 384,000Bを独自の可逆LZで101,338Bへ圧縮し、480KBの版を作ってから書いた。32KiB履歴で64BずつPSRAMへ展開し、全chunkをreadback比較する。元のsigned8 PCMとの完全一致、履歴wrap、重なりmatch、壊れた入力、sink失敗で止まることをPCのC試験4件で確認した。音声を短縮・劣化して収めたものではない。

## 実機確認

- KFB1 / ABI 1.4 / CAPS FFを確認。
- 5MHz設定のPIOでPSRAM scratch `0x3E000`を使用。72件の長さ・offset・32/64B境界・周辺guard検査に合格。
- 奇数Xの4bpp FILL、別ページへのBLIT、readback比較に合格。
- USB開始指示`g`から、BOOT→BAR→CHOICE→ANOMALY→SYSTEM→RESTORE→ENDING→BOOTを確認。
- 実HDMIを1280×720、60fpsのcapture設定で録画。日本語会話、警告ログ、中央警告文、復旧台詞を画像で目視した。これはPCプレビュー画像ではない。
- 1周のログではPCM status fault 0、transport timeout 0。後の読み取り専用観測でも、host約479秒の時点で同じ状態を確認した。

## 映像・音声の数値確認

実キャプチャ音声は48,000Hz signed16 stereo。44–46秒の会話区間を、元BGM・GAIN=155・MASTER=180から作る独立デジタル参照と比較した。8秒の位相と±1000ppm/100ppm格子を有限探索し、左右とも相関約**0.999692**、振幅比約**0.99966**。最良格子は0ppmだが、時計誤差ゼロの証明ではない。

BGMを局所的に推定除去した上で、PCM1の決定音も元PCMに対して相関約**0.999914**、振幅比約**0.99936**。BGMとPCM1 one-shotの共存を実音声で確認できた。全効果音・全エラー系をcapture oracleで確認したわけではない。

会話画像の静止背景ROI 145,948論理画素を、16色素材のindex期待値と比較した。UGREENの色変換とH.264を考慮し、ROI内の色中央値で較正して最近傍分類した一致率は**99.33%**。雨・目の差分は除外した。これは全Framebuffer readback CRCの合格判定ではない。全画面のbyte一致やVBlank原子性はまだ未確認。

## 実測された性能上の課題

|測定|観測|
|---|---|
|開始指示→最初の本編画像|約20.16秒（事前検査、BGM全chunk照合、素材ロードを含む）|
|開始指示→次のBOOT画像|約115.16秒|
|最初のBOOT画像→次のBOOT画像|約95.0秒|
|シーン記述の論理時計|88秒だが、同期処理の完了後に描画される|
|通常区間のC scheduler|概ね30Hz。PRESENTそのものの直接測定ではない|
|場面準備|主な背景再構築で約3.5秒の停止|
|警告増殖中|一部約0.65–3Hz、満杯後のスクロールは約19–20Hz|
|1周末尾の転送統計|wire 6,753,735B、839,060 transactions、累積transaction時間57.60秒|
|同区間の最長transaction|352µs、timeout 0|

**60〜90秒の実表示周回と警告30fpsの目標は未達。** PIOの5MHz設定を、アプリケーションの実効速度や非ブロッキング動作と同一視しない。小さな同期レジスタtransactionの多さ、背景2ページへのHost再転送、時刻に追い付く警告差分転送が主な改善対象。FENCE単体の待機とHDMI physical SCKのオシロ測定は行っていない。

## 成果物・現在の状態

- [実機MP4録画](../../build/midnight-hardware/midnight-terminal-hardware.mp4)（H.264/AAC、視聴用）
- `build/midnight-hardware/midnight-terminal-hardware.mkv`（原録画、音声PCM）
- `build/midnight-hardware/hdmi-audio.wav`（数値検査用PCM）
- [会話](evidence/hardware/bar.png)、[警告](evidence/hardware/warning.png)、[中央警告](evidence/hardware/final-warning.png)、[復旧](evidence/hardware/restore.png)、[Ending](evidence/hardware/ending.png)
- `evidence/hardware/analysis.json`、`visual-comparison.json`、`native-usb.log`、`flash-write-verified.json`

RP2040はこのC版で、FPGAは揮発SRAMの候補04で再生している。**FPGAの電源を切るとSRAMの作品用構成は消え、既存FlashのKAGURA-9構成へ戻る。** 作品を再開するには同じ候補のSRAM投入が必要。RP2040 C版は起動後USBの`g`を待ち、別ABIにはPSRAM刺激前に停止する。USB CDCは今回COM5として認識された。小文字`w`/`s`/Enterで選択、小文字`q`で停止できる。

元のKAGURA-9へ戻す場合は、`python tools/hw_restore.py --restore-original`を明示実行する。これは現在再生中のC版を止め、非公開バックアップからRP2040 Flashを復元・全量照合し、FPGAは既存FlashからReprogramする専用操作。今回、成功後の復元は実行せず、作品を再生したままにした。バックアップは`build/midnight-hardware/recovery/`に保存し、Git配布対象にしない。

実機での全3分岐、全効果音の個別照合、全画面CRC、長時間／電源再投入／PVT、性能目標は残る。**Release NOT READY。**
