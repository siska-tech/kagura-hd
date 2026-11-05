> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD 統合ショーケース PC評価

**6シーンのHost実装、独立oracle検証、PCプレビュー生成を完了。実機未実施、release_ready=false。**

## 成果物

- [ソース・動作手順・ABI監査・録画構成](../software/kagura_fb/showcase/README.md)
- [対話プレビュー](../build/showcase/preview/index.html)、[720p MP4](../build/showcase/preview/kagura-hd-pc-preview.mp4)
- [6画面一覧](../build/showcase/preview/contact-sheet.png)、[元の非圧縮音源](../build/showcase/preview/tiny-horizon.wav)
- [検証JSON・ソース/成果物hash](evidence/kagura-hd-showcase-pc-2026-11-05.json)
- 配布用ZIP：`build/showcase/kagura-hd-showcase.zip`（PCでのみ生成、実機への自動senderなし）

## 既存コードの監査

root既存Device/6bit protocolをそのまま使用。音声facadeはPCM2 STA合格候補から同一hashで再利用し、ABI1.4/CAPS FFを厳密照合する。旧KAGURA-9の別ABIや1.3の6ch prototypeと同一視しない。文字opcodeを仮定せず、既存KAGURA Hostフォントを小さなscanlineへ展開してWRITEする。

BLITは偶数x/幅・同一x modulo8・範囲内を検証。PRESENTはFENCEと既存同期waitでVBlank ACKまで待つ。Cursorはinactive bankへの全shape転送とACKを守る。PCMはSTOP確認、384000B×2の初回供給、PREPARE/READY、単一COMMITの順に開始する。

## PC結果

|確認|結果・実行範囲|
|---|---|
|新デモ16試験|PASS。6章×2周、計576更新、開始/終了/ループ|
|FILL|clip、odd nibble、末尾画素、複数領域を独立unpacked pixel oracleで比較|
|BLIT|上下左右・斜めの重なり、guard、無効phaseの送信前拒否|
|窓の意味的再合成|全48位置でCOPYを使わない新規合成画像と一致。影の範囲と透明cornerの残像を検出・修正|
|PALETTE/PRESENT|Mock上でACK前は旧page/palette、ACK後は対で反映。前半24更新のFB無変更、後半の交互pageと色循環を検査|
|Cursor|両pageの前後CRC一致、移動中FILL/WRITE/COPYなし、bank lock、形状/色変更、edge clip|
|PCM|全byte upload readback、独立mix式、RMS/peak、READY/ACTIVE/STOP、faultによる停止|
|異常処理|BUSY前投入ゼロ、completion timeout、device error、不確かなsubmit、PCM underrun。再送/自動reset/cleanupなし、復旧後fresh instanceのみ|
|既存ドライバ|C/Python 15件＋QSPI 4件 PASS|
|MicroPython Unix|128KiBと192KiBの各ヒープで全12シーン/2周 PASS（storage-free sink）|
|RAM loader|13 packet読込み後、192KiBで全12シーン/2周 PASS。GPIO/serial/filesystem書込みなし|

新デモの検証は実Device/Audioドライバを通した**behavioral wire Mock**。新しいpacket列のVerilator replay、HDMI実機取得、外部PSRAMの物理検証は行っていない。既存RTL回帰を今回新規実行したとは扱わない。

## メモリ・性能の意味

Hostは320B scanline、256B PCM生成、必要時256B検証、256B cursorを使い、全FBを持たない。PC oracleの460800B/4MiB MockをRPへ持ち込まない。Unix heapのGC後保持/観測最大は下表の通り。GC前の最大値はgarbageを含み、native RP2040のheap/stack保証ではない。

|Unix fixture|GC後保持 B|観測最大 B|観測最小free B|
|---|---:|---:|---:|
|micropython-128k.log|56096|109568|19968|
|micropython-192k.log|56096|184960|9344|
|ram-loader.log|84992|165728|28576|


動画は36秒、1280×720、60fps container、48kHz stereo。Hostは仮想8Hz更新を繰り返したもので、実機GPU/Host処理時間の測定ではない。シーン構築の黒待機や初回768000Bロード時間も動画へ含めていない。実機ではwork時間が125msを超えれば更新を遅くし、sleep・実更新Hz・PRESENT待機・errorを別記録する。

PCM源「Tiny Horizon」はオリジナル生成の120BPM/8秒2track。WAV stereo peakは[10250, 11220]、clip sample 0。メーターは生成PCMとGAIN/MASTERのRMS/peakで、位置はHost時刻推定。HDMI音声の解析結果やFFT、FIFO水位の実測と称しない。

## 保護・安全・未確認

FPGA固定40入力、元のSTA Bitstream群、root RTL/boardsと既存Deviceを保護しhash照合。新しいBitstream、Flash/FW/filesystem変更、実機操作、Git Push/Merge/Releaseを行っていない。既存DO_NOT_PROGRAM/release_ready=falseを維持。

次はPSRAM統合試験PASS後、別承認済みの有限実機計画で、静止画→BLIT/PRESENT/cursor→PCM/連続動作。SRAMのみ一時投入し、正常/異常どちらも既存KAGURA-9復旧とFlash hash/banner/HDMI確認を完了条件とする。復旧image hashの過去の保留を今回解決済みとは扱わない。

未確認：native RP2040のheap/stackとloader、実帯域/描画更新の滑らかさ、HDMI AV capture、真のsample位置/FIFO水位、長時間AV drift、PSRAM外部I/O/PVT、実機復旧。詳細と具体的な起動・停止手順はREADMEを参照。
