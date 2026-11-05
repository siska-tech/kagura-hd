# 300060/8B境界診断：独立派生・実機Step 9 FAIL

後続の実機許可で1回投入し、[Step 7一致/Step 9不一致を観測、KAGURA-9復元済み](../../docs/psram-boundary-hardware-result.md)。
以下は生成・PC検証時点の履歴。Flash書込み・追加診断はない。

2026-11-04。32B境界300064を跨ぐ8B WRITE/READと、絶対位置の独立4B READを
組み合わせた**1つの固定実験**。解析・実装・PC検証・Standard Bitstream生成まで。
FPGA/RP2040アクセス・書込みなし。KAGURA-HD実機合格/正式Releaseではない。

実機PASS済み`diagnostics/psram/`はファイルhashで保存・無変更を確認。
既存controller/PHY、製品RTL/ABI、既存CST/SDC、品質ゲートは無変更。
専用Top/engine/build/check/decoderだけを本ディレクトリへ追加した。
UART送信器、pin制約、SDCは原版ファイルをそのまま参照する。

## 固定シーケンスとデータ

全addressはbyte単位、表のdataは送受信byte順。各READは別のCS transaction。
seedは3か所を全て書いた後に全て読み直すため、後のseed writeが先の場所へalias
する場合も本試験前に検出する。同一開始点の8B READだけでは合格しない。

| step | 操作 | address | bytes | 期待data | 目的 |
| --- | --- | --- | --- | --- | --- |
| 0 | WRITE | 300032 | 4 | ED 0F 21 43 | ラップ上書き候補のguard A |
| 1 | WRITE | 300060 | 4 | 21 43 65 87 | 境界前seed B |
| 2 | WRITE | 300064 | 4 | 65 87 A9 CB | 境界後seed C |
| 3 | READ | 300032 | 4 | ED 0F 21 43 | 絶対位置/guardの初期確認 |
| 4 | READ | 300060 | 4 | 21 43 65 87 | 境界前初期確認 |
| 5 | READ | 300064 | 4 | 65 87 A9 CB | 境界後初期確認 |
| 6 | WRITE | **300060** | **8** | **01 23 45 67 8A AC CE F0** | **境界cross WRITEは1回** |
| 7 | READ | 300060 | 8 | 01 23 45 67 8A AC CE F0 | same-start診断、これだけではPASS不可 |
| 8 | READ | 300060 | 4 | 01 23 45 67 | 境界前を独立確認 |
| 9 | READ | **300064** | **4** | **8A AC CE F0** | **境界後の絶対位置を独立確認** |
| 10 | READ | 300032 | 4 | ED 0F 21 43 | ラップ先guard保持を確認 |

最大11 command。これはseed/guardを含む単一実験で、複数の転送長や開始点のsweepではない。
最初の不一致、controller error、timeoutで**そのstepの全packetだけを出力しfreeze**。
後続stepを実行しないため、失敗時には後ろの確認READも意図的に未実施になる。
各commandでvalidは1回のacceptまで保持し、accept後は解除。完了不明を再送しない。
成功時もstep10でfreezeし、再triggerは無視。resetによる自動再試行はない。

## なぜ偽PASSを検出できるか

32B wrap仮説では、300060からの8B WRITEが300060..300063と
**300032..300035**へ保存される。same-start 8B READも同じwrap経路なら一致する。
しかし独立4B READの300064は初期seed Cのままであり、step9で不一致になる。
独立4B READの300060は境界を跨がないため、先頭4Bの保存も分離して確認できる。
step10は、境界後が正しく更新された場合でも、余分な書込みによるguard破壊を検出する。
step9で止まるwrapケースではstep10を送らず、guard上書きはPCモデル内部でのみ観測する。
実機で未実施READの値を推定して実測扱いしない。

さらに、絶対address bit5 aliasならseed A/Cが重なる。3 seed write後のstep3が失敗し、
境界実験に進まない。ラップと恒久的aliasの停止位置を区別できる。
実ダイ型番・CA45の仕様適用は未確定で、wrapモデルの結果は仮説の切り分け根拠。
電気的data eye/DDR位相/PVTを再現したものではない。

## UARTと停止条件

pin17、115200 8N1、元のUART送信器を再利用。triggerは元と同じpin42/GP7。
CR0=8F1F、LAT14/RDL6、54MHz、位相67.5°、die0のみ。die1非選択/reset/Hi-Z。
GP7 High保持と旧PIO所有権解放は、将来のSRAM投入前に改めて確認する。

各stepにつき149B **PBC1** packet:

| byte | 内容 |
| --- | --- |
| 0..3 | PBC1 |
| 4 | status: 0=完了/READ一致、1=READ不一致、2=controller error、3=timeout |
| 5..7 | step index、words、write flag (1=WRITE/0=READ) |
| 8..11 | byte address LE32 |
| 12..15 | CR0 BE16、LAT、RDL |
| 16..79 | expected data 64B（意味のある4/8B以外0） |
| 80..143 | actual data 64B |
| 144 | 先頭144BのXOR |
| 145..148 | END! |

WRITEには読出し実測値がないためactualは0/data_valid=false。
controller error/timeoutのactualも有効値と見なさない。READ不一致時は最初の不一致で
比較を打ち切るが、既に捕捉した全rdataをUARTへ出す。別のerror register fieldはない。
メモリcommandのtimeoutは各100000 cycle（約1.85ms）。UART待機中は次commandを送らない。
外部受信側の欠損・timeoutはFAILとし、失敗後にreset/retriggerして取り直さない。
簡易XORは強いCRCではないためrawを保全し、metadata/sequence/dataも照合する。

成功は11 packet/1639B全てを検証した場合だけ。途中終了、重複・余分なpacket、
fault後のpacket、statusとdataの矛盾、誤address/data/lengthをdecoderがrejectする。
decoderは保存済みファイルだけを読み、COMやProgrammerを開かない。

## PC検証結果

Verilator **5.032**、元controllerをインスタンス化し、UARTの実8N1波形から全byteを復元。

| model/fault | 最後のstep | status | command数 | UART bytes |
| --- | --- | --- | --- | --- |
| 線形 | 10 | 0 | 11 | 1639 |
| 32B wrap（same-start偽PASS） | 9 | 1 | 10 | 1490 |
| address bit5 alias | 3 | 1 | 4 | 596 |
| step6 controller error | 6 | 2 | 7 | 1043 |
| step6受理前timeout | 6 | 3 | 6 | 1043 |
| step6受理後の完了不明timeout | 6 | 3 | 7 | 1043 |
| step8のREAD bit化け | 8 | 1 | 9 | 1341 |

**7/7 PASS**。trigger前にメモリ試験なし、最初のfault後に後続commandなし、
結果後に再triggerしても追加command/packetなし、UART framing/XORを検証。
wrapケースはstep7のstatus0を確認した上でstep9が
期待`8A AC CE F0`、実測`65 87 A9 CB`となることを検証。
モデル内部の300032..300035が`8A AC CE F0`へ上書きされることも確認した。
元の4B実機値に見られなかった他の電気的faultの網羅テストではない。

decoder **4/4 PASS**: 上記7本の実UART simulation capture、偽PASS検出、欠損/余分/破損、
fault後のpacket拒否。全raw/decoded JSONは`build/psram-boundary/`。
[simulation一覧](../../docs/evidence/psram-boundary-simulation.json)にも記録。
これはPC上の合格で、実機結果ではない。
元の4B診断・model・製品RTLが無変更のため、既存全回帰は再実行していない。

## Standard生成結果

出力: `build/psram-boundary/candidate/impl/pnr/psram_boundary.fs`

SHA-256:
`6c52669e3965d2d18ce993944a0e05d6af16f44caece545f328f3cb87afca657`

| 項目 | 値 |
| --- | --- |
| tool/device | Gowin Standard V1.9.12.04 / GW1NR-LV9QN88PC6/I5 |
| Place/Route | 1 / 2 |
| Logic / CLS | 1099 / 918 |
| FF | 1414 total = fabric 1411 + I/O 3 |
| BSRAM | 0 / 26 |
| Setup | **+5.514ns** |
| Hold | **+0.708ns** |
| Setup/Hold違反 | **0 / 0** |
| 配線 | PnR完了・Bitstream生成成功、error/unroutedメッセージなし |
| 数値ゲート | **PASS**、Setup>=+0.100nsを維持 |
| 実機/Release | **未投入 / 禁止** |

最悪Setup: `engine/position_6_s1/Q → engine/state_2_s1/CE`。
未使用PLL CLKOUTDのwarningのみ。SDCは原版を直接参照し、一切変更していない。
外部PSRAM min/max I/O遅延、ODDR TX全端子経路、PVTの保証を意味しない。
[gate JSON](../../docs/evidence/psram-boundary-gate.json)を保存。
新規ビルド1回でゲートPASS。SDCや品質ゲートを緩和しての再試行はない。

元4B診断ソース全ファイルと実機PASS済みBitstreamのSHA-256を開始時と終了時で照合し一致。
controller/PHY、原版UART/CST/SDCも一致。manifestは`build/psram-boundary/preserved-inputs.json`、
今回の入力は`candidate/source-manifest.json`。基準ビルドと復旧イメージは保持。

## 再現手順（PCのみ）

```bash
bash diagnostics/psram-boundary/test.sh
```

```powershell
uv run --offline --no-project python diagnostics/psram-boundary/test_decode.py
uv run --offline --no-project python diagnostics/psram-boundary/decode.py build/psram-boundary/packet-r0-a0-f0.bin
```

`build/psram-boundary/<新しい空dir>`からStandardのgw_sh.exeへ
`diagnostics/psram-boundary/build.tcl`の絶対pathを渡す。root直下での実行は拒否する。
生成後、repository rootで以下を実行する:

```powershell
& diagnostics/psram-boundary/check.ps1 -BuildDir 'build/psram-boundary/<新しい空dir>'
```

今回は実機投入の許可に進まず、ここで完了。将来の試験では正確なhash・復旧・GPIO所有権・
UART待機を再確認し、SRAMのみの投入を別途判断する。FW/Flash変更、Push、Releaseはしない。
