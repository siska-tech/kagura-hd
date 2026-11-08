# GPU payload選択信号の分割

次の[音声credits判定候補](gpu-credit-predicate.md)は機能比較を通過したが、
全体STAが悪化したため標準では無効とした。

前候補の深さ8はSetup −0.101 ns / −0.077 nsの2終点だけが未達だった。
起点はいずれも `host/commands/use_fill_payload_s0/Q`。
最悪経路ではファンアウト516、配線区間7.355 nsおよび6.319 nsが支配的だった。
前段階の記録は[デコード段階化](gpu-command-decode.md)に残す。

## 変更

拡張Queueで使う `REGISTER_DECODE=1` のpayload選択を、64-bit × 8区画へ分割した。
各区画は独立した `select_fill` FFで、FILLデータと共有転送窓の64-bit部分を選択する。
8個のFFに `syn_preserve` / `syn_keep` を指定し、単一FFへの再統合を防ぐ。
同じVALIDATEエッジで同じopcode判定を保持し、命令の受付・実行サイクルは増やさない。

データの512-bitバッファは追加しない。COPYは各READ結果を共有転送窓へ反映し、
続くWRITEがその時点の転送窓を参照する必要があるため、命令受付時のデータを
スナップショットする方式を避けた。FILL後もCPUの転送窓内容を保持する。
深さ1は従来の単一選択信号とmuxを使う。

## 機能確認

`test-fb-decode.sh` の従来実行器との効果比較は、AUDIO_CSR=0で587件、
AUDIO_CSR=1で588件、計1175件PASS。512-bitデータを含むメモリ要求列、
マスク、完了tag/error、PALETTE、音声制御効果が一致した。
段階化経路のREAD/WRITE境界1222件もPASS。

SPI/QSPIホスト試験に次を追加した。

1. FILL済みページをPRESENTし、表示画素を確認する。
2. 表示ページから裏ページへ640×4画素をCOPYする。
3. COPY対象1280 byteを全比較し、複数バーストで転送窓が更新されることを確認する。
4. 裏ページへ別の色でFILLし、更新対象とCOPYで残す領域を全比較する。

先頭バーストと後続バーストでデータが異なるため、古いCOPY窓を再利用する不具合も
検出できる。表示中のページを書き換えず、PCMループも並行稼働する。
これはRTLシミュレーションであり、実機試験ではない。

## 再現

```sh
KAGURA_DECODE_DIR=build/fb-decode-mailbox-final bash tools/test-fb-decode.sh
KAGURA_QUEUE_HOST_DIR=build/fb-queue-host-payload64-mailbox bash tools/test-fb-queue-host.sh
KAGURA_CURSOR_TEST_DIR=build/fb-cursor-mailbox bash tools/test-fb-cursor-pipeline.sh
```

```powershell
./tools/eval-fb-command-queue.ps1 -Depths 8 -PlaceOption 3 -RouteOption 2 -OutputBase build/fb-queue-eval-mailbox-p3-r2
```

```sh
python3 tools/summarize-fb-command-queue.py \
  --eval-dir build/fb-queue-eval-mailbox-p3-r2 --host-dir build/fb-queue-host-payload64-mailbox \
  --baseline-dir build/fb-queue-eval \
  --output docs/evidence/gpu-payload-selection-evaluation.json
```

数値STAの条件は従来と同じ。Setup/Hold違反0、Recovery/Removalに負の余裕なし、
最悪Setup余裕+0.10 ns以上。クロック、SDC、PSRAMのCA/PHY/LAT/RDLは変更しない。

## 先行実験: 16分割

先に32-bit × 16区画で合成・配置した。ネットリストで16個の独立FFを確認し、
機能比較1175件、境界1222件、COPY切替を含むSPI/QSPI×深さ2/4/8の6構成はPASS。
深さ8のSTAはSetup −1.516 ns、違反26件、Hold +0.536 ns、Hold違反0で、
全体として前候補の−0.101 ns / 2件から悪化した。
最悪経路は転送窓RAM出力→CPU書込み用wordレジスタへ移った。
対象制御の分割だけで全体STAが改善するとは言えない。

合成LUT6794、Register5333、BSRAM23、SSRAM16、配置Logic7901/8640、CLS4246/4320。
入力RTLと測定は `build/fb-queue-eval-payload-lanes/`、
機能ログは `build/fb-queue-host-payload/` に保持した。
配置への影響と追加FFを抑えるため、8分割64-bitへ絞って再評価した。

## 分割数の比較

同じQSPI深さ8、Gowin V1.9.12.04、place=1 / route=2で比較した。
各候補は機能比較1175件、境界1222件、SPI/QSPI×深さ2/4/8の6構成でPASSした。
数値は全設計の最悪値で、対象muxだけの遅延ではない。

| 選択FF | 区画幅 | 最悪Setup ns | Setup違反終点 | 合成LUT | 合成Register |
|---:|---:|---:|---:|---:|---:|
| 16 | 32 | −1.516 | 26 | 6794 | 5333 |
| **8** | **64** | **−0.333** | **1** | **6728** | **5325** |
| 4 | 128 | −1.367 | 30 | 6761 | 5321 |

8分割ではpayload選択起点の違反が消え、残りはカーソルのheld→position_yの
クロック間転送1件になった。4分割では転送窓側へ違反が移り、8分割を採用した。
候補別の機械可読記録は `evidence/gpu-payload-selection-{16,8,4}.json` に保存した。
これらは次節のカーソル変更前の測定である。

## カーソルmailboxの段階化

拡張Queue構成だけで `CURSOR_PIPELINE_MAILBOX=1` を有効にし、座標・可視状態・
bank・3色の62-bit mailboxをPIX側で連続サンプルする段を加えた。
適用先はそのサンプルをvblank条件で取り込む。深さ1と単体モジュールの既定値は0。
QueueのGPU命令やカーソルのCSR形式は変更しない。

SYS側はheldとheld_colorsをrequest_toggleと同時に公開し、ackが戻るまで保持する。
PIX側のrequest_syncは2段で、適用条件が新toggleを観測するのは最速で3番目の
PIXエッジになる。この時点で参照するサンプルは2番目のエッジの値であり、
公開から少なくとも1 PIX周期後の値である。既存のbundled-data上限10 nsは
PIX周期約13.468 nsより短い。従来と同じ適用／ackエッジのまま全62-bitを保持できる。
リセットの同時assert条件も従来どおり。SDCの緩和や新たなfalse pathは追加していない。

Y座標12-bitだけの先行実験ではSetup −0.542 ns / 1件となり、残りが色mailboxへ
移ったため採用しなかった。62-bit全体ではカーソル違反がなくなった。
place=1 / route=2の結果はSetup −0.028 ns / 1件、Hold +0.533 ns / 0件、
Recovery +6.029 ns、Removal +0.836 ns。残る起点は音声FIFOのcredits→empty判定。
合成LUT6728、Register5387、BSRAM23、SSRAM16。
この条件では数値STA基準に未達であり、実機採用可とは判定しない。

固定した従来カーソルとの比較は7,425,424画素でPASSし、CSR応答、座標、bank、
色、RGB、generation、pending/queued、適用／ackサイクルを比較した。
追加の100件はrequest同期とvblankの境界を0〜4 PIXエッジずらし、符号付き座標・
色・bankを更新して同じエッジで反映されることを確認した。
最終RTLのSPI/QSPI×深さ2/4/8も6構成すべてPASS。
深さ2/4の最終RTLのネイティブSTAと実機動作は未検証で、既定深さ1を維持する。

## 同じRTLでの配置配線比較

| place | route | ビルド | 最悪Setup ns | 違反終点 | 最悪経路 |
|---:|---:|---|---:|---:|---|
| 1 | 2 | 完了 | −0.028 | 1 | 音声credits→FIFO empty |
| 2 | 2 | 完了 | −0.028 | 1 | 音声credits→FIFO empty |
| 3 | 2 | 完了 | −0.015 | 1 | HDMI packet assembler first→rest RAM |
| 4 | 2 | 完了 | −0.674 | 16 | READ結果→共有窓RAM入力 |
| 1 | 1 | 失敗 | — | — | PR0004、475本が未配線 |

place=3 / route=2はHold +0.426 ns、Recovery +8.354 ns、Removal +0.800 ns。
音声の経路は改善したが、HDMIの別経路が残り数値STAは未達だった。
route=1は1512秒で失敗し、新しいbitstreamも得られなかった。
失敗を違反0件として扱わない。個別記録は
[place3/route2](evidence/gpu-mailbox-placement-p3-r2.json)、
[place1/route1](evidence/gpu-mailbox-placement-p1-r1.json)を参照。
ソース・制約は変更せず、ビルドオプションだけを比較した。
追加比較は[place2/route2](evidence/gpu-mailbox-placement-p2-r2.json)、
[place4/route2](evidence/gpu-mailbox-placement-p4-r2.json)に保存した。
基準条件の[place1/route2](evidence/gpu-mailbox-placement-p1-r2.json)も別記録とした。

最良のplace=3 / route=2でも基準+0.10 nsに対し0.115 ns不足する。
配置条件の変更だけでは合格せず、拡張Queueは引き続き実験用候補とする。
次のRTL改善対象は、音声のcredits非ゼロ判定からFIFO emptyまでの制御と、
HDMI packet assemblerのfirst信号からrest RAM書込みまでの経路である。
それぞれのサイクル・音声出力・パケット内容の等価性を保つ変更が必要で、
今回のpayload／カーソル変更に含めて未検証の変更を追加していない。

カーソル機能比較のログハッシュと入力ハッシュは
[mailbox検証記録](evidence/gpu-cursor-mailbox-pipeline.json)に残す。
命令比較・境界・Queue単体・SPI/QSPI統合のPASS行とログハッシュは
[機能回帰記録](evidence/gpu-payload-functional-regressions.json)を参照。
