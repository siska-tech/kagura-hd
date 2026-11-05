# KAGURA-HD — 16 Colors, One Tiny FPGA

720p HDMI向け6シーンのHost側ショーケース。PCプレビューはFPGA/HDMIの実機録画ではありません。後続の実機試験ではタイトル描画後のreadbackでtimeoutし、全6シーンは未完了です。[実機結果](../../../docs/showcase-hardware-result-2026-11-05.md)。実機で完走したC Demoと採用Bitstreamは[最終版案内](../../../README.md)を参照してください。 RTL、SDC/CST、Bitstreamは変更しない。ABI 1.4 PCM2専用構成を対象とし、rootの既存`kagura_fb.Device`と、STA候補から変更せず再利用した`kagura_fb_audio.Audio`を使用する。

## PCですぐ見る

リポジトリrootからPython 3標準ライブラリだけで実行できる。接続機器を必要とせず、シリアル/JTAGも開かない。

```sh
python3 software/kagura_fb/showcase/tests/test_showcase.py
python3 tools/preview-showcase.py
python3 tools/bundle-showcase-ram.py
```

`build/showcase/preview/index.html`をブラウザで開く。再生/停止、先頭へ戻る、6章へのジャンプ、Scene 6のオリジナル音声再生を備える。HTMLは画像・WAVを内包し、外部サーバやCDNを使わない。ブラウザが音声を抑止した場合は音声プレイヤーのPlayを押す。

生成物は`contact-sheet.png`、`scene_1.png`〜`scene_6.png`（1280×720）、全288フレーム、`tiny-horizon.wav`（48kHz stereo signed16）、JSONL telemetry、result.json。

任意のFFmpegがあるWindowsでは、次のコマンドで60fpsコンテナの720p MP4を生成できる。**Host描画更新は8Hzを仮定して繰り返したPCプレビューで、実機60fps描画の証拠ではない。** AAC動画音声は視聴用、数値検証は非圧縮WAV/生成PCMを使う。

```powershell
./tools/encode-showcase-video.ps1
```

全回帰と任意のMicroPython Unix検証：

```sh
MICROPYTHON=/path/to/micropython bash tools/test-showcase.sh
```

MicroPythonを指定すると192KiB/128KiBヒープを各1回、2周ずつ実行する。これはFB記憶を持たないsinkによる構文・メモリsmokeであり、FB oracle試験の代替ではない。GPU機能は別のCPythonワイヤMockで検証する。Cドライバ回帰にはC11 compilerが必要。

## シーンと録画構成

|章|見せ場|既定更新数 / 名目時間|主なGPU機能|
|---|---|---:|---|
|1 BOOT & TITLE|Kロゴ、16色帯、パレットフェード、仕様カード|32 / 4秒|FILL、Host文字WRITE、PALETTE、PRESENT|
|2 FILL / GRAPHICS ENGINE|40タイルの色変化、6矩形/step、実FILL+BLIT累積命令数|48 / 6秒|FILL、差分再生、背面描画|
|3 BLIT / WINDOW MOVEMENT|レトロGUI、前景窓の重なり移動、上下左右COPY|48 / 6秒|overlap BLIT、露出stripだけ背景復元、PRESENT|
|4 PALETTE / DOUBLE BUFFER|前半はFB無変更の色循環、後半はPAGE 0/1交互表示|48 / 6秒|palette shadow、VBlank atomic PRESENT、backbuffer|
|5 HARDWARE CURSOR|矢印→照準、専用色変更、HOVER/SELECT、四辺クリッピング|48 / 6秒|2bpp独立bank、hotspot、VBlank cursor commit|
|6 AUDIO / VISUAL SHOWCASE|独自BGM、L/R RMS数値・バー、source波形、PCM status/MASTER|64 / 8秒|PCM2、PREPARE/COMMIT/STOP、同時描画|

1周は名目36秒、終了後は再びタイトルへ戻る。`Demo.run(cycles=None)`で連続ループ、既定`cycles=1`で有限実行。シーン準備中はPRESENTした黒パレットで転送を隠し、構築完了後のページとパレットを同時反映する。タイトルは黒からフェードし、構築途中や全輝度の一瞬のflashを見せない。

PC動画は準備時間を省いた仮想タイムライン。実機では初回PCM生成・転送、文字転送、PRESENT待機に時間がかかる。**初回ロード時間や実機Host更新速度は未測定。** 8Hz targetは`interval_us=125000`で変更できるが、実作業が長ければsleepを0にして自動的に更新を遅らせる。HDMI 60HzとHost更新頻度を分けて記録する。BLITの最小x移動8pixelはABI制約に由来し、滑らかさは今後の実機転送性能評価が必要。

録画では、タイトル4秒→タイルと命令数→窓の重なりと復元→同一画素から色だけが変わる瞬間→FBに触れないcursor→音声と波形、の順で見せる。HTML/MP4は構成確認用で、実機映像と取り違えない。字幕に「16色FB＋独立cursor palette」「48kHz PCM2」「Host更新実測値」を分けて示すことを推奨する。

## 実装構造

- `demo_main.py`：将来の明示的な実機入口。自動接続なし。
- `gpu_api_adapter.py`：既存Device/Audioの薄いadapter、Host文字strip、局所clip、計測。
- `scene_manager.py`：6章の開始/終了/ループ、黒パレット遷移、停止ラッチ。
- `scenes.py`：6章の実装。固定の小さな構成に合わせ1ファイルへまとめた。
- `music.py`：独自曲「Tiny Horizon」、stateless整数PCM生成、upload/prepare/stop。
- `diagnostics.py`：集約カウンタとstreaming JSONL。Hostにログ配列を蓄積しない。
- `framebuffer_oracle.py`、`pc_mock.py`：**PC限定**。RP2040 runtimeからimportしない。
- `vendor/fonts.py`：KAGURA-9の既存Host `BitmapFont8`をそのまま再利用。
- `vendor/ascii_rows.py`：既存KAGURA HostのASCII glyph 760B、字形を変更していない。

文字描画opcodeは存在しないため仮定しない。既存フォントのglyphを最大320Bの4bpp scanlineへ展開し、既存WRITEで転送する。GPUにフォント機能を追加していない。BGは既知のopaque文字。BLIT背景復元時はclipされたstrip内だけFILL/Host文字を再生する。

## ABI監査とコマンド

|機能|使用する既存契約|
|---|---|
|識別|`KFB1`, major 1, minor 4, CAPS FFを厳密照合|
|FENCE / FILL|opcode 0 / 1、640×360、4bpp、Device側clip|
|PALETTE / PRESENT|opcode 2 / 3。16 entry RGB444 shadowをPRESENTでpageと同時反映。同期`wait(tag)`がVBlank ACKまで待つ|
|WRITE / READ|opcode 4 / 5。SDKが任意byte要求を4B整列・最大64Bへ分割しmaskで周辺を保持|
|BLIT|opcode 6。x/幅は偶数、`sx % 8 == dx % 8`、範囲内。x移動を8の倍数に限定。Yは1pixel単位|
|AUDIO_COMMIT|opcode 7。既存tag/DONE/errorを待つ。6ch音源設定は使わない|
|Cursor|CSR32〜53、256B shape、3 RGB444、inactive bankへ全転送後に位置/bankをcommit。`cursor_wait`でACK|
|PCM|CSR54/55 INDEX/DATA、PCM0 60h/PCM1 80h、START/END/LOOP、L/R GAIN、ENABLE、MASTER E0h|
|PCM制御|+0F PREPARE=1、STOP=2、CLEAR=4。READY後だけCOMMITで再生開始。停止待ちはbounded poll|
|PCM状態|b0 READY、b1 ACTIVE、b2 DONE、b3 UNDERRUN、b4 CONFIG_ERROR、b5 MEMORY_ERROR、b6 PREPARING|

BLITの原画を先にsnapshotする独立pixel oracleと、packed byteで処理するwire Mockを別実装にしている。Scene 3はページごとに前回の窓位置を保持し、**背面上でoverlap COPY→露出strip復元→PRESENT**の順を守る。前面の描画中に窓を動かさない。COPY footprintは4pxの影を含む228×132。opaque COPYで運ばれる影の角の背景も新位置で復元し、全48位置をCOPY未使用の新規合成画像と比較する。

FIFO占有量、正確なPCM再生sample位置、HDMI出力sampleの読戻しCSRは存在しないため仮定しない。メーターは実際の生成PCMとGAIN/MASTERからRMS/peakを計算し、再生位置だけをcommit後のHost時刻から推定する。表示は`SOURCE / HOST-TIMED`、telemetryも推定と明示する。source波形をFFTやHDMI実測と称しない。

## 音源とメモリ

「Tiny Horizon」は独自の120BPM・4小節・8秒曲。lead/chord風arpeggioとbass/percussionを2本のsigned8 monoへ合成。外部の録音・楽曲素材を使わず、ソースと生成音源は本プロジェクトのApache-2.0。フォントのみ`vendor/font-license.txt`の既存許諾を適用する。出典hashは`provenance.json`。

|用途|byte address / 使用量|
|---|---|
|FB page0|0 .. 115199|
|FB page1|115200 .. 230399|
|PCM0|0x80000 .. 0xDDBFF（384000B、exclusive END 0xDDC00）|
|PCM1|0xE0000 .. 0x13DBFF（384000B、exclusive END 0x13DC00）|
|Host scanline|320B|
|Host PCM生成|256B、検証有効時だけ追加256B|
|Host cursor shape|256B（転送中のみ）|
|Font rows|760B＋小さなクラス/文字列|

ページや既存診断領域240000/300000付近とPCMを重ねない。他のHostアプリは停止し、PSRAMを排他所有する。2面の全FBはFPGA側PSRAMだけに置く。Hostは小さなpatch/位置/パレット状態だけ保持する。PC oracleは460800Bを使うがRP2040にはロードしない。

PCMは両ch STOPを確認後、全768000Bを小chunkで初回生成・転送しFENCE、各chの設定→PREPARE/READY→MASTER→単一COMMITの順で開始する。初回データreadbackは`verify_reads=True`で全byte比較可能。再生中はPSRAM loopで供給し、Host割込みで逐次PCM補給しない。END=0x400000はこのABIで表現できないため使わない。

実機入口は読込み後に64KiB以上の空きheapを要求する。MicroPython Unixの128/192KiB testは参考で、RP2040のfirmware/native stack/PIO使用量や32bit object layoutの実測ではない。通常importのGC後保持量は約55KiB、RAM export loaderと試験sinkを含む場合は約83KiB（どちらもUnix参考値）。`heap_alloc_free`を将来の実機で記録する。frame境界と16回のWRITEごとにGCを実行し、その時間もHost work時間に含める。

## 記録・異常停止

JSONLはasset進捗、scene開始/終了、opcode別投入数、FILL/BLIT/PRESENT/cursor待機のcount/total/max、frame work時間とsleep、Host更新頻度、GPU status、PCM status、RMS/peak、heapを記録する。FIFO levelは`null`と理由を記録する。Mockの時間は仮想値であり実機性能ではない。

通常停止は`run_on_device(...,should_stop=callback)`または`Demo.run(...,should_stop=callback)`をframe境界で受け、PCM disable COMMIT→STOP、cursor非表示ACK、FENCE、黒パレットPRESENTで終える。古いACTIVEメーターを出したまま止めない。Ctrl-C、timeout、不確かなsubmit、デバイス/音声faultではhaltをラッチし、**再送・同じDemoの再開・自動reset・エラーを隠すcleanupをしない**。部分更新は巻き戻さない。外部復旧完了後に新しいDevice/Audio/GPU/Demoを構築する。処理中の音声を含む最終安全化は下記の既存復旧経路へ任せる。

## 初期計画の実機手順（履歴）

1. PSRAM統合キャンペーンのPASS、実機用計画の別承認を先に得る。内部STAだけで投入しない。
2. 対象SHA `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`、復旧経路、RP全Flash/boot.py/UF2、COM/JTAG、GPIO/PIO所有権を確認。不明なら停止。
3. 承認済み手順でFPGA SRAMだけへ一時投入。FPGA/RP2040 Flash、FW、既存filesystemは変更しない。
4. `python3 tools/bundle-showcase-ram.py`で生成した13個の`.repl.py`をmanifest順に、**同じRAM REPL namespaceへ**1個ずつ送る。senderは含まず、自動送信もしない。ファイルをRP2040 filesystemへcopyしない。
5. RAM loaderはMicroPythonでModuleType生成ができないため、ローカルimportの束縛だけをRAM export mapへ置換する。元sourceと変換後sourceの両hashをmanifestへ記録し、PC MicroPythonで読込みと2周を検証する。
6. 既存の安全なGPIO/PIO所有権解放とtransport生成は承認済み実機手順で実施。`_kagura_ram['kagura_fb'].Device`等で明示的に構成し、`_kagura_ram['showcase.demo_main'].run_on_device(device, qualified_bitstream_sha256=..., hardware_qualified=True, cycles=1, verify_reads=True)`へ渡す。SHAはoperatorの検証済み申告であり、FPGAからSHAを取得したとは扱わない。
7. 最初は静止画のみ、次にBLIT/PRESENT/cursor、最後にPCM/連続動作を段階評価する。`scenes.enter/tick/leave`を使った有限ケースで始め、いきなり全loopを走らせない。既存50秒raw-REPL job枠に長い初回PCM生成を無断で押し込まない。転送/生成実測後、有限timeoutを計画側で固定する。
8. 不一致・timeout・faultでは即停止しtelemetryを保存。既存のQSPI deinit→GPIO安全状態→FPGA Flashから既存KAGURA-9をSRAMへ再ロード→RP Flash hash→通常soft reset/banner/HDMI確認を実施。復旧不能なら次へ進まない。復旧image/hashの未確定を今回のデモで解決済み扱いしない。

既存手順と保留事項は[統合キャンペーン報告](../../../docs/rmw-campaign-result-2026-11-05.md)を参照。デモにはJTAG/Flash書込み・復旧image差替えコードを含めない。

## 未検証

- 新デモpacket列の実RTL replay/Verilator実行（今回はbehavioral Mock。既存RTL回帰の再実行ではない）。
- RP2040のnative heap/stack、実転送帯域、実機FILL/BLIT時間、映像の滑らかさ。
- HDMI映像/音声capture、真の再生sample位置、FIFO占有量、長時間のAV drift。
- PSRAM外部I/O timing/PVT、電源/温度変動、実機復旧。

**release_ready=false。新しいBitstream生成・実機操作・Push/Merge/Releaseは今回行わない。**
