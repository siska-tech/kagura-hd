# 音声credits判定の保持

続く独立候補は[HDMI packet first制御の分割](gpu-packet-first.md)を参照。

[payload／カーソル改善](gpu-payload-selection.md)後の深さ8では、place=1 / route=2の
最悪Setupが−0.028 nsで、音声credits bit2→FIFO emptyの1終点が未達だった。
place=3 / route=2ではHDMI packet assemblerのfirst→rest RAMへ移り、−0.015 nsだった。
この段階は、まず音声の制御経路を1箇所だけ変更して評価する。

## 変更と等価性

`kagura_audio_transport.REGISTER_CREDITS=1` で、credits非ゼロの判定を1-bit FFに保持する。
credits自身、tick、出力valid、FIFO、mute／underflow制御は従来どおり。
issueを遅延させず、3-bitのゼロ判定をFIFO pop経路から外す。

issueはcreditsが非ゼロのときだけ成立する。次サイクルの非ゼロは次式で表せる。

```text
next_nonzero = (credits[2:1] != 0) || tick || (credits[0] && !issue)
```

credits>=2なら1減っても非ゼロ。credits=1ならtickがあるかissueしない場合だけ非ゼロ。
credits=0ではissueせず、tickがある場合だけ非ゼロになる。
7でtickかつ非issueの飽和も非ゼロを保つ。リセットはcreditsと同時に0へ戻す。
これにより `have_credits == (credits != 0)` を各PIXサイクルで保つ。

core→HDMI wrapper→transportへ既定0のパラメータを追加した。
ボードは `GPU_AUDIO_CREDITS`、ホスト試験は `REGISTER_AUDIO_CREDITS` で明示的に選び、
Queue深さ2/4/8のときだけ有効にできる。深さ1は従来経路を使う。
前段の8分割payloadと62-bitカーソルmailboxを維持し、SDCやクロックは変更しない。
HDMI packet assemblerには、この単独評価中の変更を加えていない。

## 検証

`tb_audio_credit_predicate` は同じ刺激をREGISTER_CREDITS=0/1に送り、SYS出力と
PIX出力、credits、pending、issue、非ゼロ不変条件を各サイクルで比較する。
12375/8（registered tick有無）、525/1、7/4、5/3の5構成で155万サイクルPASS。
飽和、実サンプル、無音、出力ストール、枯渇を各構成で必須カバレッジにし、
長時間の無入力・バースト供給・途中リセットを与えた。
最初の刺激は実音声周期で枯渇に届かなかったため、無入力期間を延ばして再実行した。
比較不一致ではなく、カバレッジ不足を検出して修正したもの。

```sh
bash tools/test-audio-credit-predicate.sh
KAGURA_AUDIO_CREDITS=1 KAGURA_QUEUE_HOST_DIR=build/fb-queue-host-credit bash tools/test-fb-queue-host.sh
```

```powershell
./tools/eval-fb-command-queue.ps1 -Depths 8 -RegisterAudioCredits -PlaceOption 1 -RouteOption 2 -OutputBase build/fb-queue-eval-credit-p1-r2
./tools/eval-fb-command-queue.ps1 -Depths 8 -RegisterAudioCredits -PlaceOption 3 -RouteOption 2 -OutputBase build/fb-queue-eval-credit-p3-r2
```

深さ2/4のネイティブSTAと実機動作はこの評価に含めない。既定深さ1を維持する。

## 結果と採否

| 深さ8 / route=2 | 変更前Setup ns / 違反 | credits保持Setup ns / 違反 | Hold ns / 違反 |
|---|---:|---:|---:|
| place=1 | −0.028 / 1 | −0.275 / 2 | +0.501 / 0 |
| place=3 | −0.015 / 1 | −3.959 / 186 | +0.388 / 0 |

place=1では音声起点の違反が消え、表示パレットheld→PIXパレットが−0.275 ns、
TMDS positive2→tmdsが−0.060 nsになった。place=3では記述子RAM出力→fill_end_xが最悪。
全体の改善とは判定できないため、**標準の拡張Queueでの有効化は不採用**。
機能比較・実験再現用のオプションと回帰試験だけを残し、ボードの既定値は0にした。
合成ネットリストには独立した `cached_credits.nonzero` FFが存在することを確認した。
Recovery/Removalはplace=1で+8.724/+0.736 ns、place=3で+7.093/+0.836 ns。

明示的なオプションを追加する前の測定では、ボードとホスト試験がQueue>1で
直接REGISTER_CREDITS=1を接続していた。記録の入力ハッシュはその測定時点のもの。
上記コマンドは同じ機能構成を新しいオプションで選ぶ手順であり、オプション追加後の
配置配線を再測定したという意味ではない。配置結果やbitstreamの一致は保証しない。

SPI/QSPI×深さ2/4/8は6構成すべてPASS。機械可読記録は
[機能比較](evidence/gpu-credit-predicate-functional.json)、
[place1](evidence/gpu-credit-predicate-p1-r2.json)、
[place3](evidence/gpu-credit-predicate-p3-r2.json)を参照。
次は本候補を標準から外した状態で、HDMI packet assemblerのfirst信号の
ファンアウト分割を独立した候補として評価する。

オプション分離後の最終ソースでも、既定0のSPI/QSPIボード統合試験、
72万件の音声tick比較、有効1のQSPI深さ8を再実行してすべてPASSした。
ボード試験はHDMI/PCM・ステレオsample oracle・gain・pause/resume・loop/one-shot・
拒否応答・画面結果を含むRTLシミュレーションで、実機試験ではない。
[最終回帰ログとソースハッシュ](evidence/gpu-credit-option-regression.json)を保存した。
