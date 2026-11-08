# PCMストリーミング専用実機Host

RP2040用の単一RAM実行ELF。既存のKFB Cドライバと120 MHz／5 MHz QSPI PIOを再利用する。USBシリアルで開始指示を受けてから、KFBの識別とE3の `0x51` を照合する。PSRAMの `0x40000–0x43fff` に左右それぞれ4 KiB×2半面を確保する。初期の4半面はすべて書いてFENCEした後に全byteを読み戻し、別の半面やチャネルとエイリアスしていないことも確認する。

|入力|試験|
|---|---|
|`g`|所有権のない半面への公開、古いtoken、二重公開の拒否。300半面を連続補充し、255→0の周回を確認。補充を止めて両chのunderrunと停止を確認し、ドレイン後に再開して4半面を補充。|
|`b`|150秒間、所有権のポーリングの間にページ0の32×32 COPYを実行しながら補充。ページ0の上端を書き換える合成負荷。|
|`l`|1時間の連続補充。|
|`q`|再生ループを打ち切り、停止・ドレインを試みる。|

各実行の終端は `STOP rc=...`。正常完了は `rc=0`。ログに処理段階、公開半面数、token周回、COPY件数、所有権確認後の最大補充時間、通信タイムアウトを出す。成功の公開は全WRITEの完了後に行い、tokenが1進んだことを確認する。補充に85,333 µsを超えた場合は失敗にする。この値は半面の再生時間であり、Hostのポーリング前の待ち時間は計測に含まれない。実際のunderrun有無とHDMIキャプチャも合わせて評価する。

左右は独立した既知のsigned PCM8方形波。周期は左64サンプル、右32サンプル。各半面の最初の64サンプルだけ振幅が `24 + ((半面通番 + 37 × チャネル番号) % 64)` になり、残りは振幅72。チャネル番号は左0、右1。開始と再開で半面通番は0に戻る。HDMI録音で4096サンプル境界の欠落、重複、左右ずれを照合するためのマーカー。USBの合格表示はキャプチャ波形の合否を含まない。COPY負荷モードの描画内容はBLIT STORM本編およびメガデモと別の試験。

```powershell
./diagnostics/pcm-stream-rc1/hardware-host/build.ps1 -Output build/pcm-stream-rc1/hardware-host-ram
```

RP2040をBOOTSELにし、対象を特定してから以下でRAM実行する。FPGAには別途対象のストリーミング画像をSRAMへ投入する。USBシリアルで `PCM STREAM RC1 RAM HOST` のバナーを確認してモード文字を送る。1回の起動につき1モード。再起動で常設ホストに戻る。

```powershell
./build/midnight-hardware/picotool/picotool/picotool.exe load -v -x build/pcm-stream-rc1/hardware-host-ram/pcm_stream_hw.elf
```

ビルド時にELFの全LOADセグメントをSRAM範囲と照合する。今回のビルドは単一LOADセグメントで開始 `0x20000000`、エントリ `0x20000001`、text/data/bss合計47,240 byte。ELF SHA-256は `A2C877076E11A180B069DBF16C8BA4C200349B7BAD9B3F4984C5298D855A3280`。

## SRAM投入とプロトコル試験

2026-11-08、+0.090 nsのFPGA画像をSRAMに投入し、User Code `0x00009B86` を確認した。RP2040のELFもRAMへ投入し、picotoolのRAM検証とUSBバナーを確認した。USBシリアルの `g` は `STOP rc=0`。初期4半面の読み戻し、所有権のない公開と古い・二重tokenの拒否、300半面の補充、token周回1回、意図した左右underrun（両方 `0x08`）、ドレイン後の再開4半面が成功した。最大補充30,368 µs、timeout 0、device_error 0。

HDMI録画の初回再生区間では、初期2半面と補充300半面のマーカーが左右とも302/302一致し、10 msの低RMS区間は左右0。録画のサンプル位相は左右共通で終端までに約20サンプルずれ、固定サンプル位置での全波形照合は不合格だった。出力とキャプチャのクロック要因は未分離。マーカー照合を、個々のサンプルの欠落・重複がない証明とは扱わない。

試験後、承認済みQueue8をFPGA SRAMへ復旧し、RP2040の全2 MiB Flashの前後一致と常設HostのCOM5復帰を確認した。COPY競合、BLIT STORM／メガデモ中のストリーミング、1時間再生は未実施。証跡は `build/pcm-stream-rc1/stream-host-hardware/` の `result.json`、`stream-usb.log`、`capture-analysis.json`、`stream-hdmi.mkv`。

## 順序付き実機試験

1. `b` は150秒完走。1757半面、token周回6回、COPY 377998件、最大補充30,368 µs、通信timeoutとdevice errorは0。録画の1756半面を照合し、マーカー不一致、10 ms低RMS区間とも左右0。FPGAとHostを復旧し、RP2040 Flash全量の前後一致を確認した。証跡は `build/pcm-stream-rc1/stream-host-hardware-b/`。
2. [位相解析](analyze-phase.py) で左右の方形波の位相を半面ごとに追跡し、位相補正後にマーカーの振幅を照合した。 `g` では302半面で+20サンプル・16.32 ppm、`b` では1756半面で+117サンプル・16.28 ppm。両録画とも変化は隣接半面で最大1サンプルで、左右は同時に開始した。負荷に依存しない共通レート差と整合する。FPGAの公称音声レートは74.25 MHz×8÷12375＝48 kHzで、HDMIのACRもCTS 74250／N 6144で整合する。実機の送出クロックとキャプチャのサンプルクロックを独立に測っていないため、約16 ppmの帰属は保留。

後続の実描画用に `build.ps1 -DrawingTests` でビルドする。BEYONDの描画ソースから生成したローカル翻訳単位を使い、音声の生成と補充は専用Hostが担当する。FILL、COPY、PALETTE、PRESENTのコマンド境界で返却半面を確認する。同期コマンドで動かすため、Queue8版の描画速度と同じとは限らない。 `s` は本編のBLIT STORM区間を25秒、`m` は全8シーンを150秒実行する。RAM限定ELFを別ディレクトリ `build/pcm-stream-rc1/hardware-host-drawing/` に保存。今回のELFは133,508 byte（text/data/bss）、LOAD領域はSRAMのみ。

3. `l` は1時間完走。42187半面、周回164回、最大補充30,368 µs、通信timeoutとdevice errorは0。録音は42186半面のマーカーが左右とも全件一致し、10 ms低RMS区間は0。終端までの共通位相差は約2809サンプル（16.26 ppm）で短時間試験と整合した。証跡は `build/pcm-stream-rc1/stream-host-hardware-l/`。
4. `s` は587フレーム、COPY 16344件、292半面、最大補充30,782 µs、通信timeoutとdevice errorは0で正常終了した。映像＋音声キャプチャでは10 ms低RMS区間が左9・右8、位相は段階的にずれ、291半面の照合で左右各220件のマーカー不一致。位相推定は周期波形に基づくため、不一致数を失われた半面数とみなさない。証跡は `build/pcm-stream-rc1/stream-host-hardware-s/`。
5. 手順4の録音ゲートで停止し、`m` は開始していない。

切り分けとして `s` を音声のみのキャプチャで再実行した。診断用ELFはE2でHDMI FIFOのsticky状態を試験前にクリアし、E1を開始前と終了後に読む。再試験もCOPY 16345件、292半面、最大補充30,782 µs、E1は前後とも0x00でHost上は成功。録音では10 ms低RMS区間が左6・右8、マーカー不一致が左220・右219となり、映像収録を外しても再現した。HDMI FIFOの観測フラグは発火していない。FPGAのHDMI送出からキャプチャデバイスまでのどの箇所で乱れたかは未特定。証跡は `build/pcm-stream-rc1/stream-host-hardware-s-audio-only/`。診断ELF（133,700 byte）は同じ描画ビルド先を更新したため、初回ELFのhashは初回のresult.jsonに記録。

すべての投入はFPGA・RP2040のSRAMのみ。各試験後に承認済みQueue8を復旧し、RP2040 Flashの前後一致と常設Hostへの復帰を確認した。採用判定は保留。
