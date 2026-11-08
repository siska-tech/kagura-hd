# GPU命令デコードの段階化

続くpayload選択信号の分割は[専用レポート](gpu-payload-selection.md)を参照。
本書の測定は、分割前のデコード段階化のみの結果として保持する。

先頭記述子のレジスタ化後も、Setup最悪余裕は深さ2で−1.382 ns、4で−5.023 ns、
8で−4.033 nsだった。PALETTE更新CEやdone/errorの判定までに、opcode比較と
記述子の検証が重なっていた。前段階の測定は[Queue候補の評価](gpu-command-queue.md)に残す。

## 実装

`kagura_fb_commands.REGISTER_DECODE` を追加。既定は0で、
`kagura_fb_host` がQueue深さ>1のときだけ1を指定する。

|サイクル|REGISTER_DECODE=0（深さ1）|REGISTER_DECODE=1（拡張Queue）|
|---|---|---|
|IDLE受付|命令を受付|命令を受付|
|DECODE|既存の演算・検証準備|8-bit全幅opcodeのone-hot分類、個別条件、PALETTE選択・値を保持|
|VALIDATE|なし|実行先state、done/error、PALETTE更新one-hotを保持|
|EXECUTE|記述子を参照して判断|保持した実行方針を適用|

拡張時の命令開始に1システムクロックを追加する。実行は引き続きFIFO順の直列。
Queueの容量、完了ACK規則、転送窓のバリア規則は変更しない。

PALETTEは可変part-selectの更新許可をEXECUTEで計算せず、16本の保持した
更新許可で各12-bitエントリを更新する。色データもローカルの12-bitレジスタに保持する。
FILL/COPYは既存の座標終端・範囲計算の後、VALIDATEで実行方針を確定する。
BAD_COMMANDとRANGE_ERROR、空矩形・同位置COPYの判定優先順位を保持する。

音声の記述子検証は保持するが、`audio_busy` / `audio_settle` /
`audio_settings_valid` は従来通り実際のEXECUTEで確認する。
settle中は同じ静的デコード結果を保持して待機し、設定のcaptureを繰り返さない。
深さ1は従来のEXECUTE分岐を通る。

## 機能検証

Verilator 5.032で実行。

|試験|結果・範囲|
|---|---|
|従来デコードとの効果比較、AUDIO_CSR=0|587ケースPASS|
|従来デコードとの効果比較、AUDIO_CSR=1|588ケースPASS|
|READ/WRITE境界、REGISTER_DECODE=1|1222ケースPASS|
|先頭保持段＋段階化デコード＋CSR Queue|深さ2/4/8すべてPASS|
|深さ1のCSR参照モデルとのサイクル一致|PASS|
|SPI/QSPIのホスト→PSRAM→表示、深さ2/4/8|6構成すべてPASS|

効果比較は同じ命令をREGISTER_DECODE=0/1の実行器へ与え、完了時刻の一致ではなく、
メモリ要求列（read/write、アドレス、語数、512-bitデータ、64-bitマスク）、
完了tag/error、PALETTE全192-bit、READ結果capture回数、PRESENT回数、
音声capture/apply/commit_done回数を比較する。

全256 opcode、FILL/COPYの境界・空矩形・17-bit終端演算、PALETTE全16要素と
予約ビット、形式／範囲エラーの優先順位、メモリエラー、音声の無効設定・busy・
settle待機・applyエラーを含む。通常は外部応答条件を安定させて比較し、
settle試験は両実行器が待機した後に解除する。

Queue試験では満杯・overflow拒否・ACK待ち・pointer wrap・PALETTE値の保持・
READの窓確定・バリア・リセットを確認する。音声busy等が命令実行サイクル間で変化する
一般の場合のサイクル同値性を主張する試験ではない。

## 再現

```sh
bash tools/test-fb-decode.sh
bash tools/test-fb-command-queue.sh
KAGURA_QUEUE_HOST_DIR=build/fb-queue-host-decoded bash tools/test-fb-queue-host.sh
```

ログは `build/fb-decode/`、`build/fb-command-queue/depth-N-registered/`、
`build/fb-queue-host-decoded/lanes-L-depth-N/`。
CIにも `test-fb-decode.sh` を追加し、比較試験と境界試験のログを保存する。

Gowinの比較はQSPI、GW1NR-9C、place=1、route=2、既存のSDCで実施する。
先頭保持段のみのビルドを上書きしない出力先を指定する。

```powershell
./tools/eval-fb-command-queue.ps1 -Depths 2,4,8 -OutputBase build/fb-queue-eval-decoded
# 同じRTLで配置条件だけを変える追加比較:
./tools/eval-fb-command-queue.ps1 -Depths 2 -PlaceOption 2 -RouteOption 2 -OutputBase build/fb-queue-eval-decoded-p2-r2
```

```sh
python3 tools/summarize-fb-command-queue.py \
  --eval-dir build/fb-queue-eval-decoded --host-dir build/fb-queue-host-decoded \
  --baseline-dir build/fb-queue-eval --output docs/evidence/gpu-command-decode-evaluation.json
```

深さ1の配置結果は前段階の基準測定を参照する。数値STAはSetup/Hold違反0、
Recovery/Removalの負の余裕なし、Setup最悪余裕0.10 ns以上を合格条件とする。
bitstream生成と数値STA合格は別判定。実機SPI/QSPI、HDMI、PCMの確認は未実施。

## 配置・STA結果（2026-11-06）

Gowin V1.9.12.04、QSPI、place=1 / route=2で比較した。
[測定JSON](evidence/gpu-command-decode-evaluation.json)に、各最悪経路、
STAレポートとbitstreamのSHA-256、入力ソースのSHA-256、ホスト試験結果を保存した。

|深さ|前候補Setup ns|段階化後Setup ns|Setup違反 前→後|段階化後Hold ns|Hold違反|
|---|---:|---:|---:|---:|---:|
|2|−1.382|−4.350|15→663|+0.527|0|
|4|−5.023|−4.011|98→201|+0.470|0|
|8|−4.033|−0.101|693→2|+0.506|0|

Recovery/Removalは全構成とも正の余裕。全体STAの改善は深さで異なり、
深さ2は悪化、深さ4は最悪余裕が改善しても違反件数は増加した。
段階化すれば全配置で改善するという結果ではない。

|深さ|合成LUT|Register|BSRAM|SSRAM|配置Logic / 8640|CLS / 4320|
|---|---:|---:|---:|---:|---:|---:|
|2|6740|5440|19|48|8039|4258|
|4|6830|5443|19|48|8128|4260|
|8|6766|5318|23|16|7873|4248|

Register増分は前候補比で全構成+66。LUT増分は深さ2/4/8でそれぞれ+3/+142/+61。
深さ8の記述子RAMは引き続きSDPB 4本を使用し、BSRAM総数23を維持した。
CLS使用率は約98–99%で、配置・配線への余裕は小さい。

### 残った経路

深さ8のSetup違反は以下の2終点だけとなった。

|起点|終点|Setup余裕 ns|
|---|---|---:|
|`host/commands/use_fill_payload_s0/Q`|`core/memory_ctrl/tx_194_s0/D`|−0.101|
|同上|`core/memory_ctrl/tx_420_s0/D`|−0.077|

done/error/PALETTE更新CEを終点とする違反は深さ8では残っていない。
最悪経路は4論理段、データ遅延18.219 ns。`use_fill_payload` のファンアウトは516で、
最初の配線区間だけで7.355 ns、次の大きな配線区間も6.319 nsを占める。
次の具体的な改善対象は、512-bit payload選択と送信側制御の高ファンアウト・配線距離。
制御の局所化／分割保持などを検討する場合も、COPYの共有転送窓の寿命を維持する必要がある。

深さ2の全体最悪は `display/held_palette` → `display/palette`、
深さ4は `memory_ctrl/state` → `memory_ctrl/tx` に移った。
これらの全体結果も含めて未達と判断し、デコード以外の違反を除外していない。

### 配置条件の追加比較

同じ深さ2 RTLをplace=2 / route=2で1回追加評価した。
Setup −4.350 ns、違反663件、Hold +0.527 nsで、place=1の最悪値・件数と一致した。
要求オプションは生成された `impl/pnr/cmd.do` でも確認した。
bitstream SHA-256は異なるため、同一成果物とは扱わない。
[追加配置のJSON](evidence/gpu-command-decode-placement-evaluation.json)に別測定として残す。
この1回で配置条件全般の有効性や無効性を判定するものではない。

## 判断

深さ8では命令デコード・検証からの直接の違反を取り除き、全体の違反も693件から2件に
減らせた。一方、最悪Setup −0.101 nsは合格条件+0.10 nsに対して0.201 ns不足する。
**数値STA未達のため採用は保留し、製品既定の深さ1を維持する。**
深さ2/4の全体結果も未達であり、今回の変更を全面的なSTA改善とは扱わない。
追加のRTL改善・配置検証、続いて実機検証が必要。制約は今回も緩和していない。
