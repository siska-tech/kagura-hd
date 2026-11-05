> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD scanout RX32 — Standard単回評価結果

後続実機評価：最初の4B PSRAM試験で不一致を確認して停止し、既存KAGURA-9へ復元した。[実機結果](rx32-hardware-result-2026-11-04.md)。本書の内部STA数値PASSは変わらないが、実機合格・Releaseにはしない。

2026-11-04。独立branch `eval/rx32-scanout-01`、worktree `build/rx32-scanout-worktree`。

**判定：既存の数値STA品質ゲートPASS。フル機能、32B境界分割、音声Phase 1、192bitパレットCDCを維持したまま、scanout受信bufferの除去だけで、今回のTang Nano 9K実装は全配線・setup +0.898ns・setup/hold違反0に到達した。実機動作・外部PSRAM I/O・Releaseの合格ではない。**

## 1. 実行条件と回数

- Gowin Standard V1.9.12.04（64-bit）、GW1NR-LV9QN88PC6/I5、device GW1NR-9C。
- QSPI、System54/Pixel74、既存SDC/CST、Place1/Route2。`cmd.do`でも指定を確認。
- 対照は保存済み32B分割＋音声Phase 1。Phase 2のupload局所MUXは含めない。
- 合成/P&Rは新規空ディレクトリ `build/rx32-scanout-worktree/build/kagura-fb-qspi` で**1回**。retry、seed/配置/制約変更なし。実行時刻22:48:55〜22:50:42 JST、tool exit0。
- `full-input-hashes.json` と機能評価済み入力を照合してから開始し、実ビルド入力を `standard-input-manifest.json` へ固定。終了後も全入力hashを確認した。
- RTLの新規変更なし。実機接続/FPGA・RP2040操作/Flash変更/commit/Push/Merge/Releaseなし。

## 2. 実測比較

|項目|Phase 1対照|RX32|差分/判定|
|---|---:|---:|---|
|Logic|7717|7189|−528|
|LUT|6800|6271|−529|
|ALU|821|822|＋1|
|FF total|5370|4910|**−460**|
|fabric FF|5362|4902|−460|
|CLS|4217/4320|4144/4320|−73、97.62%→95.93%|
|BSRAM / DSP|19 / 1|19 / 1|増加なし|
|Worst Setup|−1.321ns|**＋0.898ns**|既存＋0.100nsゲートPASS|
|Worst Hold|＋0.530ns|**＋0.530ns**|PASS|
|Setup / Hold違反|16 / 0|**0 / 0**|PASS|
|Recovery / Removal最小|＋10.621 / ＋0.792ns|＋10.015 / ＋0.530ns|負解析なし|
|全配線|完了|**完了**|P&R完了、出力生成、ERRORなし|

FF差は事前のRTL保持bit見積り−460と一致した。一方、CLS削減は73であり、FF/LUT削減量からCLSを比例推定できないことも確認した。CLS90%以下という探索目標は未達だが、それを新ゲートにはせず、既存STAゲートを通過した。

## 3. 合成ネットリストで確認した構造

|階層|REG 対照→RX32|LUT 対照→RX32|確認事項|
|---|---|---|---|
|display/fetch|539→29|566→60|bufferの512FFが消失。count/overflowに伴う2FF増を含め−510REG|
|memory_ctrl|1219→1269|1491→1497|read_half16＋half_valid1＋word32＋valid1の50FFが残存|
|scheduler|12→12|33→33|仲裁状態のREG増なし|
|display|532→532|287→287|パレット保持・pixel表示側REG増なし|

対照の階層値は**Phase 1**の資源表から取得した。先行調査で引用したPhase 2のfetch LUT567/controller LUT1492とは1ずつ異なる。今回比較に使う正しい値は上表の566/1491である。

controllerのlegacy RX512とTX512、upload窓SP16個は残る。これらも消えたと拡大解釈しない。新規BSRAM/FIFOを増やさず、line RAMへ直接送る構造が合成後にも実現した。

## 4. STA・CDC・制約の確認

最悪setupはpixel74内のTMDS経路：

`core/hdmi/protocol/tmds_gen[0].tmds_channel/qm1_2_s0/Q`
→ `.../inverse_balance2_3_s0/D`、slack **＋0.898ns**。

保存上位25経路ではsystem54内最小は `executing→upload_words[12].ram/storage/DI[31]` の＋1.178ns。TX maskの例は＋1.478ns。Phase 1のsystem内部13違反とCDC3違反は全体違反0によって解消を確認できる。ただし同一始終点の全遅延差を取得したという意味ではない。

全10 clockのsetup/hold TNSは0、負endpoint0。clock27/serial371等はFmax算出対象pathなしと報告されており、これを独立した外部I/O保証とは扱わない。Fmaxの表示値はpixel74 79.552MHz、system54 57.668MHz、psram54 113.990MHz。逆数から未丸めWNSを捏造しない。

SDCのsystem54↔pixel74の**10.000ns max-delayが両方向ともActived**であることをSTA制約表で確認した。combined CSTはPhase 1とbyte一致、元SDCもhash一致。新しいfalse path、max-delay緩和、clock変更はない。

パレットの384FFについてprimitive、Q/D/CLK/CE/RESET接続を対照と全数比較し、**384個すべて一致**した。192bit paletteを狭幅化・追加pipeline・局所固定した成果ではない。

例外reportは各方向上位5pathを保存している。system→pixelの最悪はpalette bit156で＋1.620ns、route2.760ns、中間LUT0、C2Q0.458ns、fanout1：

- source R21C31[2][B] → capture R26C35[2][B]
- arrival=4.730＋2.642＋0.458＋2.760=10.590ns
- required=10.000＋2.640−0.030−0.400=12.210ns
- slack=12.210−10.590=＋1.620ns

reverse方向の保存最悪は＋10.149ns。全384FFの**配置座標**や全192対の個別STA一覧は今回も取得していない。全体STAのendpoint違反0と、保存された最悪例外pathを根拠に判定し、上位5/25を全個別経路一覧とは呼ばない。既存hold例外は維持されているため、global hold0がcross-domainの物理hold保証を意味するとも主張しない。

## 5. 仮説の採否と推奨の更新

**「line fetchの複製保持を除去すれば、追加tap費用を上回る資源削減と物理改善が得られる」という最初の仮説は、今回の1ビルドで支持された。** FF−460、Logic−528、CLS−73、全配線、数値STA合格が実測で揃った。

ただし、1回の対照比較から「slack改善の何nsがFF減、何nsが配置移動によるものか」を分離しない。パレットRTL無変更でも配線が成立したことは、広域配置との相互作用が大きかった証拠であり、192bit mailboxが常に問題ないことや、高CLSだけが唯一の根因であることを証明しない。

**次にパレットCDCやTX/CSRをさらに変更する必要性は、現時点では下がった。** この合格構成を固定した検証候補として保存し、追加アーキテクチャ変更を止める。全面32bit化やpalette事前転送を今すぐ重ねると、今回得た対照と余裕を失い得る。

従来の問いへの証拠は更新された：フル機能維持のTang Nano 9K設計について、**機能回帰と内部STA/配線を同時に成立させる具体的な候補を得た**。実機で動く設計の確立にはまだ未完了事項がある。

## 6. 残る受入条件と次の段階

機能評価のFB26、共通22、wrap統合12、controller272、追加tap381ケース/34,024edge、fetch776シナリオ、driver15＋QSPI oracle4は前段階でPASS。今回はRTL変更なしでその入力を確認してビルドしたため、無目的に再実行していない。[機能評価記録](rx32-scanout-functional-result-2026-11-04.md)

以下は未解決のまま：

1. 実ダイ型番/ID/CR、CA[45]の仕様整合、power-up/reset/LAT/RDL。
2. PSRAM外部CK/CA/DQ/RWDSのI/O timingとPVT保証。現SDCは外部仕様が未完成。
3. 元64Bでの32B wrap予測との差16B/46bit。32B split後の実機データ整合性。
4. 実機でのHDMI画素/音声、PRESENT/palette、cursor、overlap BLIT、PCM同時負荷。

次の技術段階は、保存候補を変えずに行うPSRAM独立診断と実機評価の具体化である。同開始READの偽PASSを避け、独立address/guard、全32B word offset、複数長/byte mask、READ/WRITEの切分けを含める。CR0/CA45を安全な修正と仮定しない。実機操作は今回実施していない。

合格bitstreamは評価成果物として保存したが、`release_ready=false` を維持し、`DO_NOT_PROGRAM.txt` を付けた。実機投入・製品への統合・Releaseへの自動昇格はしていない。

## 7. 証跡

評価worktreeの `build/analysis/`：

- `run-standard-once.ps1`：入力hash確認、空出力、一度だけの実行、既存品質ゲートを適用するdriver。
- `standard-run.json`：実行回数1、実行ファイル/hash、時刻、exit0、numeric_gate=PASS。
- `standard-input-manifest.json`：実ビルド入力hash。
- `analyze-standard-rx32.py`、`standard-comparison.json`：既存Phase 1と今回のreport/netlist比較。384FF全接続とclock TNSを含む。
- `physical-status.json`：機能・内部数値STA・配線PASSと外部I/O/実機未検証を分離した判定。

新ビルドの `build/kagura-fb-qspi/` にbuild.log、合成netlist/資源表、P&R/STA、`timing-status.json`、bitstreamを保存。元ビルドは上書きしていない。

bitstream SHA-256：`a99c5f8304aed79b8e0d148d6701f24bf5e282022c75c45ca3b0ab62b0d431cf`。

STA HTML report SHA-256：`85234531b777b1b8c7d560b113536fc754cad4ee66f5cae3b96892314a91d3f1`。
