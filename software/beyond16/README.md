> 最新：[連続読出しA/B/A/B・100 ms照合](../../docs/gpu-completion-abab.md)。全体平均29.483→29.688 fps、VECTOR 25.105→26.605 fpsで2組とも改善を再現。100 msはA/B双方のFINALE初回文字描画で発生。安定30 fpsは未達。[sticky確認短縮候補・ACK待機観測](../../docs/gpu-ack-observation-design.md)も追加。

> 前段：[Queue完了読出しburst](../../docs/gpu-completion-burst.md)。独立metadata readを省く実験オプション。

> 前段：[Queue待ち時間切り分け／FINALE文字結合](../../docs/gpu-queue-waits-lettering.md)。両pageの画素等価を確認し、実機の最悪描画callを148.982→82.330 msへ短縮。

> 深さ8の暫定承認候補で[Queue実機負荷比較](../../docs/gpu-queue-demo-hardware.md)を実施。直列／Queue各150秒完走、320,062件回収、全体29.366→29.480 fps。実験オプションで、製品既定は深さ1を維持。

> 最新の8構成実機比較：[実機結果](HARDWARE_HEADROOM_RESULT.md)。全8周完走・音声/Flash照合、30fps目標は未達、Release NOT READY。

> Host最適化候補（実機未投入）：[Headroom総合報告](HEADROOM_REPORT.md)。画素等価command削減、排他計測、DMA実験、8構成ビルド。実機CPU余力はNOT MEASURED、release_ready=false。

> 最新の改善と実機測定：[Host A/B結果](HARDWARE_HOST_AB_RESULT.md)。主要scene約30fps、VECTOR25.7fps。RTL変更0、release_ready=false。下記の初期版記録も履歴として保持しています。動画本体・Flash復旧像はローカルout/buildに保持。

# KAGURA-HD — BEYOND 16 COLORS

**ONE TINY FPGA. A WHOLE WORLD OF PIXELS.**

RP2040のネイティブCから、既存KAGURA-HD PCM2 ABI 1.4を使う150秒のオリジナルデモ。16色のクローム文字、3D風星、波、プラズマタイル合成、低解像度Rotozoom、球体・アイコンのBLIT、固定小数点ワイヤーフレームを音楽の500msビートへ同期する。

**実機の有限ベンチと150秒・全8シーン完走を確認。Host timeout／PCM STATUS fault=0。実更新3.9–21fpsで30fps目標は未達。Demoの性能目標は未達です。当時のFPGA Bitstreamは[PCM2 QSPI版](../../releases/pcm2-qspi-final/README.md)です。2026-11-08の選定版（[PCMストリーミング版](../../releases/pcm-stream-qspi/README.md)）でも150秒の回帰試験を行い、全8シーンの完走と、音声の欠落0を確認しました。** [実機結果・録画](HARDWARE_RESULT.md)。現在はフィナーレ画面・音声停止、BEYOND firmwareを保持。

## 見る

- [実機HDMI録画150秒](../../build/beyond16-hardware-2026-11-06/beyond16-hardware.mp4)、[実機8シーン一覧](evidence/hardware/contact-sheet.png)

- [150秒のPCプレビュー動画](out/beyond16-pc.mp4) — Cエンジン＋実SDK＋機能モデルを30fpsの論理時刻で記録。HDMI captureではない。
- [8シーン一覧](evidence/contact-sheet.png)、[150秒のPC音声](out/beyond16-pc.wav)
- [最終判定](STATUS.json)、[通信・性能比較](PERFORMANCE.md)、[原因分析](DRIVER_ANALYSIS.md)
- [PSRAM/Flash配置](memory.json)、[実機試験と復旧計画](HARDWARE_PLAN.md)

ライブ版はrepo rootで次を実行する。実機のUSB・シリアル・JTAGは開かない。

```powershell
./software/beyond16/tools/run_preview.ps1
./software/beyond16/tools/run_preview.ps1 --scene 5 --seed 0xb1616
```

640×360／16色を1280×720へ整数拡大。SでPNG、Escで終了。シーン単独再生は指定シーンの時間区間を一度再生する。入力はプレビュー制御のみで、作品は時刻によるautoplay。Python 3.12、Pillow、Tk、pygame-ceを使用。既存`midnight_terminal/.deps`があればWindows版は再利用する。

## 再現・ビルド

```powershell
python3.12.exe software/beyond16/tools/generate.py
./software/beyond16/tools/build_pc.ps1
python3.12.exe software/beyond16/tools/test.py
python3.12.exe software/beyond16/tools/test_assets.py
python3.12.exe software/beyond16/tools/benchmark.py
python3.12.exe software/beyond16/tools/preview.py --smoke-gui
./software/beyond16/tools/build_rp2040.ps1
python3.12.exe software/beyond16/tools/mix_audio.py
python3.12.exe software/beyond16/tools/record.py
python3.12.exe software/beyond16/tools/collect.py
```

動画生成のみffmpegが必要。生成済み素材を使う通常ビルドにネット接続は不要。Arm GNU GCC 14.2.1、Pico SDK 2.1.1の既存配置を使う。32bit ArmコンパイラはこのWindows sandbox内でDLL relocationエラーとなるため、ビルドのみ通常権限環境で実行して検証した。ELF/bin生成だけで、upload/flash/UF2ターゲットは設けていない。

Linux headless CIは`bash software/beyond16/tools/ci.sh`。Pillowなしでも画素配列照合と全タイムライン比較は動く。PNG保存にはPillowが必要。[CI定義](../../.github/workflows/beyond16.yml)。WindowsとWSLの両方でCビルド・テストを確認した。実行時間の集計JSONは最後にWindowsで再測定した値。

## 構成とGPU契約

|責務|実装|
|---|---|
|scene manager、time line、scheduler、dirty map、固定小数点演算|`src/b16.c` / `src/b16.h`|
|GPU command adapter|既存`../kagura_fb/kagura_fb.c`。描画ドライバを重複実装しない|
|PSRAM展開、PCM0/1制御、palette controller|`src/b16.c`内の独立関数群|
|PIO transport|前作の`../midnight_terminal/src/mt_qspi.c`、既存PIOをそのままリンク|
|実機時計、USB開始ゲート、計測、停止|`src/rp2040_main.c`|
|PCレジスタ機能モデル|`src/pc.c`。高速化のためpacked byteで描画。実時間の模倣はしない|
|独立画素oracle|`tools/test.py`＋既存`../kagura_fb/tests/model.py`|
|素材／FM風PCM生成、圧縮|`tools/generate.py`、既存可逆LZ compressor/decoderを再利用|

コマンドはFENCE/FILL/PALETTE/PRESENT/WRITE/READ/BLIT/PCM COMMITの既存0–7のみ。BUSY中にdescriptor/dataを変更しない。キュー深度1のためコマンドの並列投入はしない。BLITはpage矩形のみ、偶数X/幅、`sx%8==dx%8`を厳守。spriteのXは8pxへ量子化する。透明BLIT、GPU線分、GPU回転、任意アドレスBLITは使用しない。

両Framebufferの上部ロゴ・下部素材帯を開始前に展開し、動的領域はy88–279へ限定する。素材帯は隠しVRAMではなく、画面下に見えるasset galleryとしてデザインしている。8個の球／アイコンと8個の32×32プラズマタイルを両pageに持つ。背景の動的領域は単色なので、各pageの8×8 dirty mapを行方向へまとめたFILLで復元する。各pageに固定文字を一度だけ描き、背面page完成後にPRESENTする。本編中のHost PSRAM uploadは0B。追加PSRAM背景の架空BLITは行わない。

Paletteはshadowへ設定し、次のPRESENTによるvblank反映後に表示される。走査線palette変更は行わない。640×360の4bpp表示／16エントリのRGB444であり、「BEYOND」は作品名と見た目の目標であって表示色数の増加ではない。

## シーン

|時間|Scene|実装|
|---|---|---|
|0–10|OPENING|大きいクロームロゴ、星、球、ビート色変化|
|10–30|HYPERSPACE|hash seed、透視除算、カメラ旋回、星の尾、ビート速度変化|
|30–50|RASTER WAVES|3層サイン帯、陰影3段、振幅と位相変化、headerの55枚BLITによる波打つロゴ|
|50–70|PLASMA ENGINE|18×6枚の事前配置tileをリアルタイムsine位相で選択・BLIT合成＋palette。全画面動画再生ではない|
|70–95|ROTOZOOM|固定小数点の逆回転・拡縮座標を24×12セルで評価、FILL＋前面の球。低解像度fallback|
|95–120|BLIT STORM|標準32個、2周波の軌道。8/16/32/64/128の別負荷試験あり|
|120–140|VECTOR WORLD|立方体→八面体→回転トンネル＋ロゴ、透視、線分を短いFILL spanへ分解|
|140–150|FINALE|星＋BLITから仕様・コピーへ。未測定の実機性能数値は表示しない|

共通時刻150,000msで終了し、フレーム回数でシーンを決めない。遅延時は古い時刻のフレームを追いかけず次の現在時刻で評価する。実機epochはBGM COMMIT完了直後。BGM準備・全asset展開はepoch前に終える。48kHz音声とRP2040時計の長期clock driftを補正する再生位置CSRはなく、150秒中のドリフト／初期AV offsetは実機測定が必要。

## 音楽

原曲「Beyond the Gate」は120BPM、4小節／8秒のFM bass、arpeggio、pad、kick、snare、hatをオフライン合成。PCM0でloop、PCM1で4種類のscene stinger。シーン別にBGM gainを変えて強弱を作る。150秒の展開は短い同一曲の反復＋強弱＋stingerで、150秒を通した別旋律の作曲ではない。8bit signed mono 48kHz原データは384,000B、可逆圧縮193,656B。音声は開始前にPSRAMへ一度展開し、再生中の書込み／streamingは行わない。

STOP→inactive確認→CLEAR→START/END/LOOP→PREPARE→READY→COMMITの契約を守り、COMMITでは両chのgain/control shadowを再設定してBGMを維持する。ENDはexclusive、loop範囲は全8秒、アドレスは22bit／die-relative。STATUSを1秒ごとに検査し、faultでは停止。PC音声ファイルはsigned8からHDMIと同じscaleの16bit stereoへソフトウェアmixしたもの。実機音声・聴感・prefetch安全性の検証を代替しない。

## 検証範囲と残る制約

PC全150秒、Before/After画素CRC、20時刻×2variantの独立oracle、seed再現、時間スキップ、両pageと全PCMの展開一致、16色制約、異常停止、既存SDK15件×2設定、既存QSPI4件、GUI画像／48kHz mixer初期化を確認。ログは`evidence/`。

実機1周で3.9–21fps、平均frame79.53ms／最悪509.063msを観測。30fps／軽量60fpsは未達。標準scheduler自体は約30Hzで、60Hz更新profileは未実装。descriptor burstは実機でも正常完走。独立した物理PIO波形・全Framebuffer CRC・実機負荷sweepは未実行。モデルはvblank待ち・PSRAM仲裁・PCM prefetchを再現しない。

連続的なロゴ形状morphと、密な3D格子は今回の実装範囲に含まれない。GPU制約に合わせたオリジナルの基本8シーンは完走するが、デモシーン作品としての演出拡張と実機の負荷上限選定は残る。未確認の目標を達成としない。

[ライセンス](LICENSES.md)。作業前の未コミット変更は保持。RTL／Controller／PHY／SDC／CST／PLL／FPGA bitstream／FPGA Flashは変更0。既存STA候補と復旧バックアップはhash一致。後続の「実機にいきましょう」という明示承認で前作を正常停止し、新規全Flash backup確認後にRP2040を書換え、固定候補をFPGA SRAMへ1回投入した。filesystemは全量readback一致、FPGA Flashは書換え0。前作への復旧は未実行。
