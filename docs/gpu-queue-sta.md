# 深さ8のSTA再評価

このページはPALETTE共有化前の調査記録。後続の[PALETTE保持共有化の設計監査](gpu-palette-sharing-audit.md)で、別途実装・比較を扱う。

2026-11-07。基準画像は実機A/B/A/Bまで検証したQSPI Queue8、packet first分割ON、audio credits保持OFF。
基準のSetupは+0.050 ns、Holdは+0.470 ns。数値ゲートはSetup +0.100 ns以上、Setup/Hold違反0、Recovery/Removalに負の余裕なし。
54 MHz system／74.25 MHz pixel、PLL、PSRAM LAT/RDL、既存SDCを維持して比較した。

今回の試験では数値ゲートを通過する新画像を得られず、STA未達の解消には至っていない。
基準のSetup +0.050 nsは正だが、必要な+0.100 nsに0.050 ns不足している。
試作画像への更新は行わず、承認済み基準画像を保持する。

## 基準と保持

基準bitstream SHA-256は`5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77`。
`build/fb-queue-eval-packet-first-p4-r2/qspi-depth-8`を上書きせず、各試験は新しいbuild directoryへ出力する。
新しい画像のFPGA SRAM／Flash投入、RP2040書込みは行っていない。

## RTL候補の切り分け

基準の最悪はmemory_ctrl state→512-bit tx保持FF、次点はheld_palette→paletteのCDC転送だった。
次の候補を実装し、機能比較とネイティブ合成・配置配線を行った。

- tx／maskを8群に分け、次cycleのload／shift制御を登録。転送edgeと完了cycleは凍結した旧RTLと一致。
- PRESENT payload 193 bitをPIXで先行sample。旧scanoutとのpage／palette／generation／ACKのcycle一致を3 seedで確認。
- 合成後に除去・吸収されるdescriptor保持段を128 bit保持、連続capture、48-bit geometry保持へ分けて比較。
- 64-byte upload windowを16個のBRAMからFF格納へ変更。CSR応答cycle、READ完了、COPY capture、warm resetを旧CSRと比較。
- SPI/QSPI Queue8、depth2/4/8のFIFO、既定depth1のboard・stereo oracleを検証。

これらは機能試験を通過しても、STA違反や配置／配線不足を生じ、基準画像より良い数値ゲート結果を得られなかった。
CLS使用率は多くの構成で約99%となり、局所的な保持段追加で最悪経路が別ブロックへ移る。
FF総数だけでは配置可能性を判断できず、byte単位enable版は総FFを減らしても未配置FFが増えた。

未達のRTL試作は本線から取り除き、元画像の入力41ファイルを保存済みSHA-256とbyte単位で照合して復元した。
その後、build入口へ合成方針の選択だけを追加した。現在の41入力のうち40は基準とbyte単位で一致し、
差分は既定autoを維持する`tools/build-fb.tcl`だけである。[照合記録](evidence/gpu-queue-sta/current-source-verification.json)。
試作本体は`build/queue-sta-rejected-prototypes/`、各native試験の正確な入力は各build下`source-snapshot/`に保持する。
[試作差分](evidence/gpu-queue-sta/rejected-rtl.patch)と[各候補の比較・失敗記録](evidence/gpu-queue-sta/comparison.json)も保存する。
既存のユーザー変更をgit版へ戻す操作は行っていない。

## P&R設定の分離評価

Gowin V1.9.12.04に付属する公式Tcl User Guide SUG1220-2.1Eを確認した。
place=2はtiming優先、place=3/4は配置改善を試みる設定。
route=2はrouting速度改善、route=1は時間をかけてrouting改善を試みる設定である。
またreplicate_resourcesの既定は0、route_maxfanのGW1NR-9C既定は23。

`tools/reroute-fb-netlist.ps1`は、承認済み画像と同じmapped netlist、CST、SDCをコピーしてhash照合し、
合成を省略してP&Rだけを行う。retimingはnone、timing_drivenは1。PLLや実クロックを変更しない。
入力と元bitstreamの試験後hashも照合し、既存出力directoryの上書きを拒否する。
`diagnostics/queue8-sta/frozen-inputs.json`にmapped logic・端子CST・SDCを固定する。
netlistの行頭`//`コメントだけを除いて比較するため、時刻コメントが異なる同一回路の再合成結果も使用できる。
回路や制約が異なる場合はP&Rを開始しない。

```powershell
./tools/reroute-fb-netlist.ps1 -OutputBuild build/<new-run> -PlaceOption 4 -RouteOption 1
```

高fanout resource複製、routing fanout 10／60も、同じmapped designで比較した。
replicate_resources=1、place=4／route=2はSetup +0.050 ns／Hold +0.470 nsで数値改善なし。
fanout=60、place=4／route=2も同じ最悪余裕だった。異なるbitstream hashを、性能改善の根拠にはしない。
route=1はplace=4で1,492本、place=2で1,111本が未配線。fanout=10は2,538本が未配線だった。

## 合成方針の評価

公式の`opt_goal`はauto／area／timingで、既定はauto。
build／evaluation入口へ`-OptimizationGoal`を追加した。既定autoと製品既定のQueue1を維持する。
modeを変える出力は別directoryへ分け、入力ソースを全量退避してhashを記録する。
元のRTL・CST・SDCでtiming優先合成も比較する。global_freq表示50 MHzを実クロックの変更とは扱わない。
基準の合成reportもsystem54／pixel74.25を認識している。
timing／place=4ではSetup −1.308 ns、place=2では186本が未配線だった。
area／place=4は基準と同じmapped logicとSetup +0.050 ns、place=2はSetup −1.428 nsだった。
onehot明示指定もplace=4で234本、place=2で835本が未配線となり、取り除いた。

```powershell
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -OptimizationGoal timing -PlaceOption 4 -RouteOption 2 -OutputBase build/<new-eval>
```

## 内部セル配置の評価

基準の詳細STAでは、`memory_ctrl/n2777_s2`はR8C9、fanout 498。
最悪TX側のR2C41への配線だけで12.031 nsを占める。上流state FFのfanoutは619だった。
基準の次点はpalette bit 71の転送でSetup +0.098 ns。
`diagnostics/queue8-sta/*.cst`は、この凍結netlistの内部セルだけを指定する候補であり、製品CSTには組み込まない。
helperはmemory_ctrl／display／cursor内部のINS_LOCだけを受け付け、I/O・PLL・clock制約の追加を拒否する。

control-centerはLUTをR8C25へ移し、palette bit 71の受信FFも近接させた。
結果はSetup −0.223 ns、4違反で、最悪はpalette bit 137へ移った。
state-control-centerは上流state FFも移したが、Setup −0.641 ns、2違反で、最悪はpalette bit 156だった。
nearはSetup −1.243 ns、1違反。midはSetup −0.013 ns、1違反となった。
midの次点はpalette bit 135の+0.298 nsで、残る違反はcursor held bit 1→sample mailbox bit 1の配線4.393 nsだった。
midを起点にcursor受信FFを近接させる2候補と、制御LUTを左右1列動かす2候補を別buildで比較する。
cursor-aはSetup −0.602 ns、1違反、cursor-bは−0.554 ns、12違反。
leftはSetup −0.379 ns、1違反となり、いずれも不採用。
rightもSetup −1.508 ns、8違反で不採用。全配置候補の評価は完了し、採用候補はない。
局所配置の改善を全体STAの改善とは扱わない。
初回のcenter系2 buildはhelperのTcl書出し失敗でP&R開始前に停止したため、回路の失敗件数には含めない。

```powershell
./tools/reroute-fb-netlist.ps1 -OutputBuild build/<new-placement-run> -ExtraCst diagnostics/queue8-sta/control-near.cst
./tools/check-fb-timing.ps1 -BuildDir build/<new-placement-run>
```

## 証跡と限界

[比較JSON](evidence/gpu-queue-sta/comparison.json)、[機能試験](evidence/gpu-queue-sta/functional-tests.json)。
bitstream、原netlist、全ソースsnapshotとnative reportはbuild下へ保持し、evidenceにはhashとreportを保存する。
新画像の実機互換性・映像・音声は未検証。既存SDCに残る外部PSRAM IOの未完仕様とCDC制約範囲も維持する。
数値STAの合否を、実機確認済みやrelease-readyと混同しない。

## 残る改善対象

基準のCLSは4,246/4,320（99%）、Registerは5,397/6,771（80%）、BSRAMは23/26（89%）。
配線・制御の局所改善が別のCDC経路へ違反を移すため、配置変更だけを採用する根拠は得られなかった。
次の設計対象は、追加の保持段よりも既存の重複保持・組合せ選択の削減である。
特にPRESENT paletteのコマンド側保持とmailbox側保持を共有できるかは、
PRESENT完了までのデータ安定性、リセット時の挙動、CDCの制約対象を含めた別の設計・検証を要する。
この共有化は未実装であり、今回の達成事項には含めない。
