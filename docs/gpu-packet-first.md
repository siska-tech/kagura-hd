# HDMI packet first制御の分割

この深さ8・place=4候補は、その後ユーザーの暫定承認で
[メガデモ実機負荷比較](gpu-queue-demo-hardware.md)を実施した。以下はRTL／STA評価時点の記録。

[音声credits候補](gpu-credit-predicate.md)を無効にし、8分割payload／62-bitカーソル
mailboxを持つ深さ8を基準に、packet assemblerのロード制御だけを分割する。
基準のplace=3 / route=2では `first`→rest RAMがSetup −0.015 nsの最悪経路だった。

## 変更

`kagura_packet_assembler.REPLICATE_FIRST=1` で、4個のsubpacket（各54-bit）と
header（23-bit）のロードmuxに独立した5個の `first_local` FFを置く。
各FFは既存firstと同じ初期値1、同じ `counter_next==0` を同じPIXエッジで保持する。
`syn_preserve` / `syn_keep` で統合を防ぐ。元のfirstは出力ビット選択に引き続き使う。
新しいサイクルは追加せず、カウンタ、ECC、packet_data、resetの仕様は変えない。

ボードの `GPU_PACKET_FIRST`、core／HDMI wrapperの `PACKET_REPLICATE_FIRST`、
生成HDMI coreを通じて選択する。既定値は0で、Queue深さ>1のときだけ有効にできる。
通常ビルドは無効、評価は `-ReplicatePacketFirst` で明示的に有効にする。
音声credits保持は無効のまま、クロック・SDC・PSRAM条件も変更しない。
vendorファイルは編集せず、ハッシュ確認付き生成スクリプトにパラメータ接続を追加した。

## 機能比較

未変更のhdl-util packet_assemblerと、counterを全サイクル、packet_dataを全data-island
画素で比較する既存試験を、REPLICATE_FIRST=0/1とseed=1/19/73の6構成で実行した。
1〜18個の連続packet、ランダムな空き期間、途中resetを含め全構成PASS。
有効側だけで85,522 packets、2,735,030 island画素、93回の途中resetを比較し、
無効側でも同じ刺激・件数がPASSした。
合成ネットリストでは5系統が分離され、各系統にDFFと初期値1のDFFSが生成された。
合成Registerは基準5387から5397へ10増、LUTは6728から6762へ34増、
BSRAM23／SSRAM16は同数だった。ソース上の5 FFだけでコストを見積もらない。
候補有効のSPI/QSPI×深さ2/4/8も6構成すべてPASSした。
候補無効・深さ1のSPI/QSPIボード試験は、ステレオsample oracle、gain、
pause/resume、loop/one-shot、拒否応答、画面結果を含めてPASSした。
これらはRTLシミュレーションで、実機試験ではない。
[統合ログと入力ハッシュ](evidence/gpu-packet-first-integration.json)を保存した。

```sh
bash tools/test-packet-first.sh
KAGURA_PACKET_FIRST=1 KAGURA_QUEUE_HOST_DIR=build/fb-queue-host-packet-first bash tools/test-fb-queue-host.sh
```

```powershell
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -PlaceOption 1 -RouteOption 2 -OutputBase build/fb-queue-eval-packet-first-p1-r2
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -PlaceOption 3 -RouteOption 2 -OutputBase build/fb-queue-eval-packet-first-p3-r2
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -PlaceOption 4 -RouteOption 2 -OutputBase build/fb-queue-eval-packet-first-p4-r2
```

合格条件はSetup/Hold違反0件、Recovery/Removalに負の余裕なし、Setup余裕+0.10 ns以上。
深さ2/4のネイティブSTAと実機動作は今回の評価に含めない。製品既定の深さ1を維持する。

## 配置配線結果

Gowin V1.9.12.04、QSPI深さ8、route=2、54 MHz／74.25 MHz、同一SDCで測定した。

| place | 最悪Setup ns | Setup違反終点 | 最悪Hold ns | Hold違反終点 | Recovery ns | Removal ns |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | −1.428 | 21 | +0.506 | 0 | +7.954 | +1.033 |
| 3 | +0.042 | 0 | +0.539 | 0 | +8.811 | +0.827 |
| 4 | +0.050 | 0 | +0.470 | 0 | +8.556 | +0.839 |

place=3では変更前の−0.015 ns／1件から、Setup/Hold違反0件へ改善した。
ただし最悪Setup +0.042 nsは基準+0.10 nsに0.058 ns不足するため、数値ゲートは未達。
最悪経路は記述子RAM DO[5]→FILL end_byte bit7へ移った。
第2経路はmemory_ctrl state→tx_maskで+0.179 ns。
place=1の最悪はaudio_packets asp_selected→sub[2] bit10であり、
全配置で安定した改善が得られるとは扱わない。

機械可読記録は[packet比較](evidence/gpu-packet-first-functional.json)、
[place1](evidence/gpu-packet-first-p1-r2.json)、
[place3](evidence/gpu-packet-first-p3-r2.json)、
[place4](evidence/gpu-packet-first-p4-r2.json)を参照。

place=4もSetup/Hold違反0件で、今回の最良Setupは+0.050 ns。
最悪経路はmemory_ctrl state→tx bit270へ移り、基準には0.050 ns不足した。
place=3/4で違反0件になったことは改善だが、数値ゲートの合格とは扱わない。
**候補は次の検討用として保持し、通常ビルドのGPU_PACKET_FIRST=0と製品既定深さ1を維持する。**
実機への書込みやリリース変更は行っていない。

次の改善対象は、place=4のmemory_ctrl送信データ制御、およびplace=3の
記述子→FILL終端計算である。既存の+0.10 ns基準を緩めず、メモリ要求・マスク・
完了サイクルの等価性を保ちながら、残る制御ファンアウトと計算経路を評価する。
