# GPUコマンド受付Queue候補

後続の深さ8候補は、ユーザーの暫定承認で[メガデモ実機負荷比較](gpu-queue-demo-hardware.md)を実施した。

デコード段階化は[命令デコード改善](gpu-command-decode.md)、
続く選択信号の分割は[payload選択改善](gpu-payload-selection.md)を参照。
本書の配置結果は先頭保持段のみを追加した段階の測定として保持する。

## 現行方式

PCM2の経路は `kagura_fb_host` → `kagura_fb_registers` →
`kagura_fb_commands`。CSR 8–23に128-bit記述子、24/25に64-byte転送窓、
26にSUBMIT、27にSTATUS、28–30に完了tag/error、31にIRQ ACKを持つ。
SUBMITから完了まで `executing` が立ち、記述子・転送窓のCPU書込みを拒否する。
実行器は記述子をラッチせずCSR出力を参照し続ける。READ完了は転送窓RAMの
出力が安定するまで1クロック延期する。COPYも同じ窓を内部作業用に使う。

`rtl/core/kagura_command_queue.sv` の32件Queueは旧コア用であり、
現行PCM2の受付深さ1とは別物。

## 候補比較

深さは**実行中を含めた未完了件数**とする。

|候補|深さ2|深さ4|深さ8|制約|
|---|---:|---:|---:|---|
|記述子のみ保存（今回実装）|256 bit|512 bit|1024 bit|共有状態を使う命令はバリア|
|記述子と転送窓を毎回保存|1280 bit|2560 bit|5120 bit|READ結果、COPY作業窓、音声設定、完了Queueも設計が必要|
|既存窓を共有したまま全命令を先行受付|—|—|—|先行WRITEデータやCOPY結果を破壊し得るため不採用|

bit数は記述子／転送窓の論理保存量。配置後のFF/LUT/BSRAM使用量ではない。
現在の深さ>1構成は、これに加えて先頭記述子用128-bitレジスタと制御を持つ。
深さ2は最小コストの候補、4は短い描画バースト向け、8は受付余裕の上限評価向け。
実測による性能優劣はまだ判定していない。

## 実装とプロトコル

`kagura_fb_registers.QUEUE_DEPTH` / `kagura_fb_host.QUEUE_DEPTH`、
基板topの `GPU_QUEUE_DEPTH` に1/2/4/8を指定する。既定1は従来動作。
2/4/8は実験用であり、公開済みbitstreamやSDKを置き換えていない。

* SUBMIT成功時に記述子をFIFOへコピーし、実行中も先頭を保持する。
  完了処理でpopする。push/pop同時発生時も件数を維持する。
* 深さ>1のホスト経路では `kagura_fb_command_head` がFIFO先頭をレジスタへ
  取り込んでから実行器へ渡す。RAM読出しと命令デコードの間にクロック境界を
  置き、完了まで記述子を保持する。深さ1はこの段をバイパスする。
* 現在は深さ>1で `REGISTER_DECODE` も有効にし、記述子の検証と実行判断を
  DECODE/VALIDATEで段階化する。詳細とそのSTA結果は上記の別レポートを参照。
* FENCE/FILL/PALETTE/PRESENT（0–3）は先行受付できる。FENCEは先行命令の
  完了後に実行され、PRESENTもFIFO順を守る。並列実行はしない。
* WRITE/READ/COPY/AUDIO（4–7）、未知opcodeはQueue空時だけ受付。
  完了まで後続受付と共有窓更新を禁止する。音声設定の保護は既存音声CSR側の
  規約に従い、音声設定そのものをこのQueueに保存しない。
* 転送窓のCPU read/write/address変更は未完了記述子がある間拒否する。
* 完了tag/errorは既存の1スロット。ACKまで次の実行を開始しない。
  受付済みの後続記述子は保持する。先行SUBMITで完了フラグを消さない。
  sticky errorは従来通りCSR 7で別途クリアする。
* BUSY/CSR 26の受付可否は「満杯またはバリア実行中」を表す。
  **BUSY=0を全実行完了と解釈してはいけない。** 完了tagとACKを管理する
  専用ホスト処理が必要。非バリア命令の空きがあってもバリアSUBMITは
  未完了件数が0でなければBAD_COMMANDとなる。
* 満杯時はBUSY_ERRORで拒否し、記述子を置換しない。リセットで受付済み命令と
  完了通知を破棄する。リセット時の記述子RAM内容は無効として扱う。

ACK待ちによる直列化があるため、受付QueueだけでGPU演算速度は上がらない。
ホストの記述子送信を実行と重ねる余地は増えるが、CPU負荷削減率やFPSは未測定。
完了FIFOによる自律連続実行は別候補として残す。新ABIの識別、空き件数CSR、
SDKのタグ追跡を決めるまでは深さ1を製品既定とする。

## 再現検証

WSL/Linux、Verilator 5.032で実行:

```sh
bash tools/test-fb-command-queue.sh
```

深さ2/4/8でCSRと実際のコマンド実行器を接続し、PRESENT待機中の満杯受付、
overflow拒否、FIFO順序、完了保持、ACK再開、4周のpointer wrap、
WRITEバリア、RANGE_ERROR、READバッファの確定とロック、PALETTE値の先行受付と順序、
active/pending状態からのリセットを検証する。
深さ1は既存 `tb_fb_register_window` で保存済み参照モデルとのサイクル一致を検証。
ログは `build/fb-command-queue/depth-{2,4,8}-registered/{build,run}.log` と
`build/fb-verilator/tb_fb_register_window.*.log` に保存する。

2026-11-06の実行結果（Verilator 5.032）:

|検証|結果|
|---|---|
|Queue深さ2 / 4 / 8、上記CSR→実行器統合試験|全PASS|
|深さ1、保存済みCSR参照モデルとのサイクル一致|PASS（READ完了6回、COPY capture 18回、warm resetを含む）|
|既定構成の命令範囲チェック|PASS（tag付きREAD/WRITE 1222ケース）|
|既定構成のSPI / QSPIホスト統合|全PASS（物理プロトコル→PSRAM→表示画素、COPY/PCM競合を含む）|
|深さ8の `kagura_fb_host` 階層lint|終了コード0（幅拡張の警告あり）|

既定構成の回帰は以下で再現できる:

```sh
KAGURA_TEST_FILTER="tb_fb_command_bounds tb_fb_host_spi tb_fb_host_qspi" bash tools/test-fb-verilator.sh
verilator --lint-only --timing -Wno-fatal --top-module kagura_fb_host -GQUEUE_DEPTH=8 -f rtl/fb/sources.f
```

## 物理ホストと配置評価

```sh
bash tools/test-fb-queue-host.sh
# 部分実行例:
KAGURA_QUEUE_LANES=4 KAGURA_QUEUE_DEPTHS=8 bash tools/test-fb-queue-host.sh
```

SPI(1 lane)/QSPI(4 lanes)のそれぞれで深さ2/4/8を検証する。
先頭の全画面FILLを実行中に後続の小矩形FILLを先行受付し、満杯とoverflow拒否、
ACKでの順次再開、全画面の最終画素、READ/WRITE転送窓、PRESENT後のscanout画素を
確認する。2バーストでpointer wrapも通る。実PSRAMの代わりに独立したCAモデルを
使い、HDMI出力のserializerはstub。PCMループも同時に動かしている。
このホスト試験は `AUDIO_CSR=0` で、PCM設定はcoreへ直接与える。
拡張Queueと音声CSR COMMITの組合せ、COPYの拡張深さでの物理ホスト試験は未実施。
ログは `build/fb-queue-host/lanes-{1,4}-depth-{2,4,8}/`。

`accept` は最初の記述子送信開始から最後のSUBMIT送信終了まで、`drain` は
最後のACK送信終了までの54 MHzサイクル数。CSRアクセスを伴うテスト用ホストの
経過時間であり、CPU命令数、CPU負荷、実機FPSではない。深さごとに記述子数が
違うため、そのまま高速化率を計算できない。

Gowinの同一条件比較（QSPI、place=1、route=2、GW1NR-9C）:

```powershell
./tools/eval-fb-command-queue.ps1 -OutputBase build/fb-queue-eval-registered
# 通常ビルドからの指定も可能:
./tools/build-fb.ps1 -Transport qspi -QueueDepth 4 -ReportOnly
```

事前に `python3 tools/prepare-hdmi-stream.py` を実行する。
上の指定では評価ビルドを `build/fb-queue-eval-registered/qspi-depth-{1,2,4,8}/` に分離する。
通常ビルドも深さ>1では出力先に `-queueN` を付ける。
`result.json` は再生成時刻を満たすbitstreamだけを有効とし、STAは既存の
`check-fb-timing.ps1 -ReportOnly` で集計する。数値STAと実機適合は別判定。
入力のSHA-256一覧は出力ディレクトリ直下の `source-sha256.json`。

```sh
python3 tools/summarize-fb-command-queue.py --eval-dir build/fb-queue-eval-registered --output build/fb-queue-eval-registered/summary.json
```

集計器は合成XMLのLUT/ALU/Register/BSRAM/SSRAM、配置後のLogic/Register/CLS、
STA、物理ホスト試験ログをJSONへ収集する。未実行と失敗をPASS扱いしない。

### STAで見つかった直接読出し方式の問題

最初の方式は `descriptors[read_ptr]` を実行器へ直接接続していた。
同一のQSPI/配置1/配線2で、深さ1はSetup +0.747 ns、Hold +0.507 ns、違反0。
深さ2はSetup −10.427 ns、Setup違反453件、Hold違反0だった。
最悪経路は `host/registers/read_ptr_0_s1/Q` →
`host/commands/present_palette_144_s0/CE`。機能シミュレーションのPASSだけでは
この経路の問題を検出できなかった。

元方式の結果は `build/fb-queue-eval/qspi-depth-{1,2}/result.json` に残す。
元方式の深さ4は合成まで完了したが配置評価を中断、深さ8はGowin未実施。
元方式の物理ホスト6構成のログは `build/fb-queue-eval/host-direct/` に保存。
現在の実装は上記の先頭レジスタ段でこの経路を分割した修正版。

### 先頭保持段のみの評価結果（2026-11-06）

Gowin V1.9.12.04、QSPI、place=1、route=2。深さ1はレジスタ段追加前の基準測定で、
深さ1では追加段をバイパスする。生データ・各クリティカルパス・入力SHA-256は
[評価JSON](evidence/gpu-command-queue-evaluation.json)に保存した。

|深さ|合成LUT|合成Register|BSRAM|SSRAM|
|---|---:|---:|---:|---:|
|1（基準）|6714|5239|19|16|
|2|6737|5374|19|48|
|4|6688|5377|19|48|
|8|6705|5252|23|16|

深さ8は記述子RAMと先頭保持段が32-bit SDPB 4本の同期読出しへマップされた。
深さ2/4は分散RAMと保持FF。これはこのツール・ソース条件での実測であり、
論理保存bit数と配置資源を同一視しない。

|深さ|配置Logic / 8640|CLS / 4320|Setup最悪 ns|Hold最悪 ns|Setup違反件数|数値STA|
|---|---:|---:|---:|---:|---:|---|
|1（基準）|7820|4231|+0.747|+0.507|0|合格|
|2|8035|4249|−1.382|+0.527|15|不合格|
|4|7986|4247|−5.023|+0.530|98|不合格|
|8|7810|4220|−4.033|+0.484|693|不合格|

全構成Hold違反0、Recovery/Removalは正の余裕。Setup違反が残るため、
bitstream生成が完了していても深さ2/4/8を採用可能とは判定しない。
機能検証は、修正版のSPI/QSPI×深さ2/4/8の6構成すべてPASS。
先頭レジスタ付き単体・統合試験も3深さすべてPASS、深さ1の参照一致もPASS。
これらはシミュレーションであり、実機確認ではない。

深さ2の最悪経路は保持した記述子bit33→`commands/done`（8論理段、
データ遅延19.500 ns、うち配線12.502 ns）。深さ4はopcode bit6→PALETTE更新CE、
深さ8はSDPB出力→`commands/done` が最悪。RAM読出しからの一段分割だけでは
命令デコード・検証から制御出力までの経路が残る。

**採用判断: 深さ1を維持し、2/4/8は実験用候補として保留。**
次のRTL候補は既存DECODEサイクルでopcode分類、検証結果、PALETTEの選択・更新許可を
レジスタ化し、EXECUTEのdone/error/CEまでの組合せ段数を減らすこと。
音声・転送窓などの経路にも負の余裕があるため、対象経路の改善だけで全体STAが
合格すると仮定しない。同じ制約で全Setup/Hold/Recovery/Removalと
Setup余裕0.10 ns以上を再確認する。制約の緩和で今回の違反を除外していない。

実機SPI/QSPI受付・HDMI/PCM共存・実アプリ性能は未検証。
採用には数値STA合格に加え、同じ描画列に対する受付待ち時間／ACK待ち時間／
CPU占有率／画面結果の比較が必要。今回の配置比較は各構成1条件であり、
配置条件を変えた場合の余裕の再現性も未評価。
