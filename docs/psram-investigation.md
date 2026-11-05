> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# 初回実機PSRAM不一致の解析と次回試験準備

2026-11-04。KAGURA-HD実機評価は不合格、正式Releaseは禁止のまま。
今回の作業はPC上の解析・独立シミュレーション・診断準備のみ。
FPGA/RP2040アクセス、書込み、FW変更、製品RTL変更、Pushは行っていない。

## 1. 固定した証跡と差分

[元の例外記録](evaluation-exception.md)と
`build/hardware-eval-097/control-stage4/012-scratch.log`を照合した。
対象は基準commit `1d46c6db71eb48e486a8e038d41e5a44342fe699`、
Standard V1.9.12.04、QSPI、Bitstream SHA-256:
`ed5b1fbb19f136a5d9ec1a4fbe9b5036c2a8eec4eaad2b5eda6faba4ff87692a`。
Setup +0.097ns、Hold +0.527ns。+0.100nsゲートへの3ps不足は未解消。

アドレス300000 = `0x493E0`は32B境界に一致し、64B境界からは32Bの位置。
CR0=`0x8F1F`、LAT=14、RDL=6、PSRAM CK=54MHz DDR、位相67.5°。
ホストは`Device.write_bytes`で16 wordsのWRITEを1回、
`read_bytes`で16 wordsのREADを1回送る。ドライバは64B窓へ分割するが、
32B境界では分割しない。基準RTLも4MiB die終端を検査するだけである。

期待64B:
```
0b30557a9fc4e90e33587da2c7ec11365b80a5caef14395e83a8cdf2173c6186abd0f51a3f6489aed3f81d42678cb1d6fb20456a8fb4d9fe23486d92b7dc0126
```
実測64B:
```
d8d4f51a2f6489aed3f81d42668cb1d63120456a8eb4d9fe48486d92dcdc0126d8d4f51a2f6489aed3f81d42668cb1d63120456a8eb4d9fe48486d92dcdc0126
```

[64行のバイト差分CSV](evidence/psram-byte-diff.csv)に期待・実測・XOR・
ラップ予測との差を保存した。再現入力は`sim/diagnostics/psram-observation.json`。

| 比較 | 結果 |
| --- | --- |
| 元の線形期待値との不一致 | 40/64 bytes |
| 実測の最小完全周期 | 32 bytes、前後半が完全一致 |
| 32B内でWRITEもREADもラップする予測との一致 | 48/64 bytes |
| 上記予測との差 | 16 bytes、合計46 bits |
| 線形WRITE後にREADだけ32Bラップする予測との一致 | 0/64 bytes |
| 16/32/64bit内の単純バイト反転との一致 | 2/0/0 bytes |
| ラップ予測のバイト回転 | 最良0 byteずれで48一致、次点1 byteずれで4一致 |

ラップWRITEでは先頭32Bが後半32Bに上書きされる。その領域を再びラップREAD
すると期待値の後半が2回現れる。これは実測の大部分と整合する。
一方、追加の化けを無視して「原因確定」とはしない。
読み出し窓やコントローラの5bit相当のアドレスaliasでも似た結果は作れる。

ラップ予測との差分は各32B内のoffset `0,1,4,12,16,20,24,28`に同じ形で現れる。

| offset (もう一方は+32) | ラップ予測 | 実測 | XOR |
| --- | --- | --- | --- |
| 0 | AB | D8 | 73 |
| 1 | D0 | D4 | 04 |
| 4 | 3F | 2F | 10 |
| 12 | 67 | 66 | 01 |
| 16 | FB | 31 | CA |
| 20 | 8F | 8E | 01 |
| 24 | 23 | 48 | 6B |
| 28 | B7 | DC | 6B |

残差16B中14Bがword内lane0、2Bがlane1、lane2/3にはない。
offset24と28は次のバイトと同じ値だが、全体に一定の1byteずれはない。
全8bitに差分があり、単一DQ固定故障とも断定できない。
一様なbyte内±1..7bit shift、全512bit列の±1..15bit shift（両byte order）
のいずれも完全一致しない。位相不良による個別bit/edge誤りはこの結果では否定できない。
READとWRITEのどちらで化けたかも現ログだけでは分離できない。

## 2. 仕様とCR0の照合：確定事項と適用限界

一次資料は以下。Winbond資料はメーカー発行PDFのMouser配布コピーを参照した。
メーカー直URLは取得できなかった。資料の版とページを固定し、一般的なHyperRAM
仕様をそのまま実ダイの仕様と見なさない。

- [Sipeed Tang Nano 9K公式](https://en.wiki.sipeed.com/hardware/en/tang/Tang-Nano-9K/Nano-9K.html)
- [Gowin DS117-2.9.3E、2021-10-26](https://dl.sipeed.com/fileList/TANG/Nano%209K/6_Chip_Manual/EN/DS117-2.9.3E_GW1NR%20series%20of%20%20FPGA%20Products%20DataSheet.pdf)、§2.3/§3.2.2
- [Gowin PSRAM IP公式](https://www.gowinsemi.com/en/support/ip_detail/35/)
- [Winbond W955D8MBYA A01-001、2019-06-05](https://www.mouser.com/datasheet/2/949/W955D8MBYA_85C_PKG_datasheet_A01-001_20190605-1760391.pdf)、印刷pp.12,22–24,32,34–39

Gowin/Sipeed資料からQN88Pの内蔵PSRAMは合計64Mbit、各32Mbitと確認できる。
製品RTLは独立x8のdie0のみ4MiBとして使い、die1を非選択・resetに保持する。
**この個体内のメーカー・ダイ型番・revisionは未確認**。Gowin IPはWinbond品を
サポートするが、実装個体がW955D8MBYAである証明にはならない。ID/CR実読出しも
初回評価にはない。以下の照合はW955D8MBYAを参照ダイとする条件付き評価。

CR0=8F1Fの分解:

| bits | 値 | 参照ダイでの意味 |
| --- | --- | --- |
| 15 | 1 | 通常動作 |
| 14:12 | 000 | 出力drive 50Ω |
| 11:8 | 1111 | 予約bitの指定値 |
| 7:4 | 0001 | 初期latency count 6 |
| 3 | 1 | 固定2倍、count 12 |
| 2 | 1 | legacy wrap。0は予約、Hybrid Wrap選択ではない |
| 1:0 | 11 | wrap長32B。00/01/10は128/64/16B |

この参照仕様はmemory CA[45]=0、register CA[45]=1と規定する。
現行`make_ca`は両方で1を設定し、元モデルも1を要求する。
従って「CA45=1なら線形に動く」という汎用HyperBusの解釈は、この資料では保証されない。
実ダイが1を無視する、wrapに扱う、その他の挙動をするかは未確定。
**CR0=8F1Fで64Bの任意開始線形連続転送が保証される根拠はない。**
Hybrid SleepはCR1の省電力機能で、Hybrid Wrap/Linear Burstとは別。
この資料にHybrid Wrapの有効設定はなく、未確認の別ダイ仕様を混ぜない。

ラップの参照式は`floor(start/B)*B + ((start+offset) mod B)`（byte単位）。
境界は絶対アドレスで、CSごとの開始点を基準に32Bを数える方式とは異なる。
300000付近にdie境界はなく、4MiB越えとは無関係。
長さを32B以下にするだけでは不十分で、例えば+28開始の8B転送も境界をまたぐ。
CR0を64B wrapへ変えるだけでも、元アドレス300000は64B境界の中間なので解決保証がない。

DDRではCA/WRITEはCKに対しcenter aligned、READ DQはRWDSとedge aligned。
RWDSはCA中の追加latency通知、READ中のstrobe、WRITE中のbyte maskとして働く。
固定latencyはREAD strobeの不要を保証しない。参照仕様では境界でのRWDS停止も記述される。
実PHYはRWDSを診断用に捕捉するだけで、RDL=6のsystem-clock IDDRで読む。
CR0の12 count、RTL LAT=14、RDL=6はそれぞれ起点・pipelineが違うため単純比較で
正否を決められない。物理CA/CK/RWDS/DQの時間軸での確認が必要。

参照タイミングにはtCSHI>=6ns、tRWR>=36ns、tCSS>=2ns、input setup/hold各0.9ns、
DQ/RWDS解放<=6nsがある。54MHzの2 cycleは約37.04nsだが、controller GAPだけで
pad上の保証とはしない。READ終端ではCSを最後のcaptureまで保つ必要がある。
controllerはCK終了後もRDL分CSを保持するが、実ODDR/IDDR経路は別途観測対象。
最大CS Lowは4µs、64Bのnominal transferは約1µsで範囲内の見込み。
reset pulse/recoveryは200/200/400ns、power-upは150µs。warm resetの待ちと電源投入待ち
を区別する。今回、これらを波形で実測・保証したとはしない。

## 3. 既存モデルの問題と独立再現

元の`sim/support/kagura_hyperram_pair_model.sv`は変更していない。

| 観点 | 元モデル | 今回の独立モデル／残課題 |
| --- | --- | --- |
| アドレス | CA45=1必須、常時線形 | CR0からwrap長をdecode、絶対境界でwrap |
| CA45 | memoryにも1を要求 | 参照仕様ならreject。仮説modeのみ1を許容し違反数を記録 |
| latency/RDL | controllerと同じ固定値 | 同じpair抽象を維持。独立したpin latency検証ではない |
| DQ/RWDS | abstract OEを検査 | CA/read/write ownershipとCS-high recovery cycleを検査 |
| turnaround | アナログ解放時間なし | padのtOZ/tDSZ、TX窓、preambleは未モデル化 |
| 位相 | なし | CK位相・IDDR/ODDR・data eyeは未モデル化 |
| CS終端 | abstract CS/CK | CK停止中もCSを追跡、物理終端holdは未検証 |
| refresh | なし | RWDS stalls/PVT/retentionも未モデル化 |

追加モデル`sim/support/kagura_psram_wrap_pair_model.sv`は**より厳格なprotocol診断モデル**。
実チップ完全モデルやタイミングsign-offモデルではない。
未確認CAの挙動は`ALLOW_UNDOCUMENTED_CA45=1`で明示的な仮説として扱う。

`tb_psram_wrap_repro`は製品burst controllerを変更せずインスタンス化する。

1. 仮説modeで300000/64Bの後半32B上書き・2回反復を再現。
2. 独立4B READで、WRITEが先頭領域へ後半を保存したことを確認。
3. 1/2/4/8/16 words × 4開始位置の20ケースでwrap予測と一致。
4. strict modeでは現行CA45を拒否することを負テストで確認。
5. testbenchだけでmemory CA45を0へ変えた正テストも同じ20ケースを通過。

**再現したのは32B周期の理想的なaliasのみ。実測の残差16B/46bitは再現していない。**
実測値をハードコードして出力する故障モデルは作っていない。
短いsame-start WRITE/READはwrap経路が共通で偽PASSになる点もテストしている。

## 4. 保存と次回の診断準備

`tools/prepare-psram-diagnostics.py`はOFFLINEでmanifestと20個の個別ケースを生成する。
COM/JTAGは開かず、raw REPL requestも作らず、自動実行・自動sweepはない。
失敗BitstreamのSHA、実RP2040の2MiB backup、recovery UF2のSHAを再照合した。
既存KAGURA-9のFPGA Flash・RP2040・復旧イメージはそのまま保持している。
全Flashイメージは個人データを含み得るため公開証跡に含めない。

`software/kagura_fb/diagnostics/psram_case.py`はRAM実行用の**未投入**診断部品。
import時のI/Oはなく、呼出側から既存Deviceと同期ログ関数を渡す。
新FWは不要。現時点でこれを実機へ転送・実行する許可はない。

- `window_only`: PSRAM命令なしで64B staging窓のupload/echoを照合。host aliasを先に分離。
- `run_one`: 指定1ケースだけ。1-word単位で周辺をseed/verifyし、試験WRITE/READ、
  続いて独立1-word READとguardを照合。scratchは300000..300159のみ。
- 全readの期待・実測hex、開始address、長さ、case IDを比較前にemitする。
  write直前にもintentを残す。host側emitは永続化完了後にreturnする必要がある。
- 最初の不一致／転送例外で例外を上げる。再送・後続case・自動復旧writeをしない。
  pin releaseだけは外側の`finally`で行う。部分出力やtimeoutを成功扱いにしない。
- scratchは破壊試験領域。失敗後のrestoreは行わず、不確定命令を再投入しない。

| 開始address | mod32 | mod64 | 目的 |
| --- | --- | --- | --- |
| 300032 | 0 | 0 | 両境界aligned |
| 300060 | 28 | 28 | 32B境界直前、8B以上でcross |
| 300064 | 0 | 32 | 32B aligned/64B中間 |
| 300092 | 28 | 60 | 32B/64B両境界直前 |

各開始位置について4/8/16/32/64Bを用意した。毎回absolute addressとcase IDを含む
非32B周期のデータを使う。全20ケースを一括実行することは推奨しない。
まずwindow echo 1件、その後aligned 4B 1件。不一致ならそこで止める。
通過した場合だけ次の1件を選ぶ。

read/writeの分離用に`isolated_read`も準備した。1-word seed/verifyで絶対位置を確定した後、
長いREADを1回だけ行う。長いWRITE後の短いREADと
比較すればcategory2/3/4を分離しやすい。現64Bログを取り直すだけの試験は避ける。

## 5. 最小診断Topの検討と投入ゲート

既存`kagura_fb_memtest_top`/`kagura_hyperram_diag_top`は旧1-word controllerを使うため、
HDの16-word burst不具合をそのまま再現するTopではない。単なる再実行は優先しない。

今回は新たな診断Top/Bitstreamを生成していない。従って新合成・P&R・STA結果もない。
今後必要なら`build/psram-diagnostic-top/`等の独立作業ディレクトリで、
**既存burst controllerとPHYを無改変で再利用**し、HDMI/scanout/audio/host窓を除き、
固定ROMケースをUART triggerで1回だけ実行するTopを第一候補とする。
UARTにはcase/address/length、送信data、全受信data、CA、RWDSを含む短いscopeを出し、
最初の不一致でfreezeする。現行配線は変更せず、die1は非選択、出力は不要時Hi-Z。
CR0/ID読み出しが必要なら診断専用の制御を独立実装し、本体へ混ぜない。
未知ダイに対する未確認CR書換えや位相sweepを同時に入れない。

Gowin Standard V1.9.12.04、同じdevice/PLL/PHY/制約を用い、Logic/CLS/FF/BSRAM、
Setup/Hold、全配線、未制約path、interface timingの限界を記録する。
新候補はSetup>=+0.100ns、Hold違反0、Setup違反0、全配線完了を確認してから
別途SRAM投入を判断する。元候補の3ps例外を新候補へ自動流用しない。
FPGA Flash/RP2040 Flashは禁止、RP2040 FWは保持、SRAM投入自体も今回は行わない。

## 6. 原因分類・修正候補とリスク

| category | 現時点の判断 | 最小の分離方法 |
| --- | --- | --- |
| 1 PSRAM設定/バースト仕様 | **主仮説**。CR0参照仕様と32B周期、後半上書き予測48B一致 | ID/CR確認、aligned短転送→境界cross、独立絶対位置READ |
| 2 READ timing/DDR位相 | 未排除。固定RDL、残差はlaneに偏る | 既知1-word seed→長READ、RWDS/DQ scope |
| 3 WRITE timing | 未排除。window/first-byte境界も候補 | 長WRITE→独立4B READ、送信DQ/mask scope |
| 4 controller address | CA45に参照仕様との不一致。アドレス下位aliasも未排除 | CA全48bitと実アクセス絶対位置を比較 |
| 5 host QSPI/window | 未排除。現stagingは7bit pointer/64B、静的に32B aliasは見当たらない | PSRAMを介さない64B窓echo。既存window回帰はsimulation証拠のみ |
| 6 未特定 | **全体として未特定**。主仮説だけで全実測を説明しない | 複数要因を同時変更せず上記で分離 |

仕様に基づく修正候補は次の順で評価する。本体RTL修正は今回実施しない。

1. 実ダイのwrapが確認できた場合、CSごとのburstをwrap境界で分割する。
   32B以下への単純capではcrossを防げない。全clientのarbiter/line fetch/fill/BLIT/
   PCMの再組立て・帯域・deadline・mask処理へ影響するので回帰とSTAが必要。
   host driverだけの分割ではscanout等は直らない。
2. 実ダイ仕様が確認できた場合、CA45をmemory/registerで区別する候補を検討。
   旧1-word controllerの実績だけで長burstを保証しない。単独変更でwrapは消えない。
3. CR0 burst length変更は境界問題を移すだけ。linear/hybrid対応が確認できない現状で
   CR0 bit2を0へ落とす案は予約設定となる恐れがあり採用しない。
4. 残差がtimingと分離された場合のみRDL/CK位相・RWDS捕捉を検討。
   データeye/turnaround/CS終端を含む検証が必要で、無根拠な位相変更はしない。

## 7. PC上での再現手順と検証記録

```powershell
uv run --offline --no-project python tools/analyze-psram-observation.py
uv run --offline --no-project python tools/prepare-psram-diagnostics.py
uv run --offline --no-project python sim/diagnostics/test_psram_diagnostics.py
```

WSLの既存Verilator 5.032で`bash tools/test-psram-diagnostics.sh`を実行。
負テストのabortは想定結果で、exit codeとCAエラー文の両方を検査する。
追加Pythonテスト7件PASS：証跡解析、実Device+既存線形Modelの20ケース、
PSRAM命令なしwindow echo、64B不一致の全ログと停止、cross短転送の偽PASS検出、
不確定転送例外の非再送、長READと長WRITEの分離。診断モデル3 modeもPASS。
ログと生成planは`build/psram-investigation/`、private recovery manifestは同所に保持。

既存回帰は元モデル・元RTLのまま、Verilator 5.032/seed 1/strict version指定で実行。
FB **26/26 PASS**、共有部品 **22/22 PASS**。C/Python driver **15/15 PASS**、
slow QSPI pin oracle **4/4 PASS**。ログはそれぞれ`fb-regression.log`、
`common-regression.log`、`driver-regression.log`に保存した。
これらはシミュレーション/PCテストの合格であり、実機PSRAMの不合格を覆さない。
準備したRAM診断関数も既存Unix MicroPython上で20ケース、isolated READ、
host-window echoを通過した（`prepared-micropython.log`）。RP2040上では未実行。

## 次段階：独立診断候補の作成（2026-11-04）

上記解析・準備後の継続指示で、[独立4B診断Top](../diagnostics/psram/README.md)を追加した。
製品RTL/PHYは無改変。Standard合成・P&R・STAを実施し、最終候補はSetup +6.276ns、
Hold +0.708ns、違反0、配線完了で数値ゲートPASS。UART実波形の5ケースとdecoder
3テストもPASS。**FPGA/RP2040へは未投入**で、元の実機不合格/Release禁止は継続。
生成履歴・ハッシュ・最小4B試験・復旧手順はリンク先を参照。

その後の実機投入の明示許可で、[4B1回の実機試験](psram-4b-hardware-result.md)を実施しPASS。
KAGURA-9へ復元済み。64B不一致の解消や本体実機合格、Releaseを意味しない。
