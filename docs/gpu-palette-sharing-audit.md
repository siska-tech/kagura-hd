# PALETTE保持共有化の設計監査

2026-11-07。対象はQSPI Queue8、packet-first分割ON、audio credits保持OFF。

## 監査判断

最終判断は**不採用**。機能監査ではボード接続に限り既存REQ/ACKと完了順序を維持できると判断し、既定OFFの評価試作とSTA比較へ進めた。
合成ではFFが5,397→5,205、192 FF（約3.6%）減少した。削減対象の`held_palette`は192 FF→0。
PIX側の表示中PALETTEとpage保持は残す。クロック、SDC、同期段数、vblank反映edge、完了edgeは変更しない。
しかし配置後のCLS削減は13個（約0.3%）にとどまり、Setupは−3.569 nsへ悪化した。
今回のSTA改善という目的には効果が不足するため、試作を本線から取り除き、共有化前の41入力のSHA-256へ復元した。
試作は[再適用可能なパッチ](evidence/gpu-palette-sharing/prototype.patch)とnative入力snapshotへ保存した。
[復元照合](evidence/gpu-palette-sharing/restoration.json)。

## 更新権限と保持期間

`rtl/fb/kagura_fb_commands.sv`の`present_palette`が唯一の実行時更新元である。
リセット時の初期化と、EXECUTE状態で検証を通ったPALETTEコマンドだけが書き込む。
CSRのstaging descriptorを書き換えても、この192-bit bankは変わらない。

PRESENTはPRESENT_REQ→PRESENT_WAITへ進み、`present_done`が返るまでEXECUTEへ戻らない。
Queue8は後続descriptorを受け付けるが、PRESENT中に後続PALETTEを実行しない。
その後もregister endpointは未ACKの完了を保持し、次のdescriptorの実行を止める。
したがって、PRESENT受理からPIX反映、2FFのACK同期、SYS完了まで、コマンド側bank自体が安定している。
共有化のための新しいロック、ACK待ち、完了transactionは追加しない。

ボード起動時は定数PALETTEが入力される。起動PRESENTの完了後にRUNへ移り、host側bankへ切り替わる。
hostはRUNになるまで有効化されず、初期PALETTEも同じ定数である。
共有化はこの接続関係を前提とし、任意の外部producerへ無条件には適用しない。

## CDC・リセット・表示の監査

- 元のSYS `held_palette`→PIX `palette`を、SYSコマンドbankと起動／RUN選択MUX→同じPIX `palette`へ置き換える。192本のbundled-data転送であることは変わらないが、旧snapshotが隔離していたMUXもCDC経路へ入る。
- REQの2FF同期後、vblankでpageとPALETTEを同時に反映し、そのedgeでACKを更新する。ACK同期と`present_done`生成はそのまま。
- 後続PALETTEはSYS側bankだけを更新し、表示中のPIX bankは次のPRESENTまで変わらない。
- 既存SDCのmax-delayはsystem54/pixel74のclock間に適用されるため、新しい発信FFも制約範囲に入る。制約値やfalse-pathは変更しない。
- scanout既存契約の「両domainのresetを同時assert」を維持する。ボードcoreは共通resetを非同期assertし、domain別に同期releaseする。
- reset中はPIX bank、REQ/ACK、pendingを消去する。共有化時の未使用`held_palette`は合成で除去される。入力bankのreset値が旧snapshotと異なっても、reset中に表示適用しない。

`SHARED_PRESENT_PALETTE`の既定値は0。既定のscanoutは受理edgeでsnapshotし、入力が直後に変化しても従来どおり動作する。
明示的に共有化したproducerだけに、受理から完了までの入力安定性を要求する。simulation assertionで契約違反を検出する。
これは既存のコマンド実行器が既に満たす条件であり、完了順序やソフトウェアABIの変更ではない。

## 実装と再現手順

評価試作では`SHARED_PRESENT_PALETTE`をscanout/coreへ、`GPU_SHARED_PALETTE`をボード設定へ追加した。
build/evaluationの`-SharePresentPalette`で明示的に有効化する。Queue深さの製品既定1、共有化OFFを維持する。
共有化OFFのmapped netlistは、行頭`//`コメントを除いて承認済み基準版と完全一致した。
[合成回路の照合記録](evidence/gpu-palette-sharing/mapped-proof.json)。

本線へは採用していないため、下記スイッチと試験スクリプトは本線に残していない。
再現する場合は隔離した作業コピーへ評価パッチを適用してから実行する。
復元後の本線に対する`git apply --check --ignore-space-change`は通過した。

```powershell
git apply --ignore-space-change docs/evidence/gpu-palette-sharing/prototype.patch
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -PlaceOption 4 -RouteOption 2 -OutputBase build/<off-run>
./tools/eval-fb-command-queue.ps1 -Depths 8 -ReplicatePacketFirst -SharePresentPalette -PlaceOption 4 -RouteOption 2 -OutputBase build/<on-run>
./tools/check-fb-timing.ps1 -BuildDir build/<on-run>/qspi-depth-8
```

## 機能検証

評価パッチ適用後の`wsl bash tools/test-fb-palette-sharing.sh`。

- 凍結した旧scanoutとcycle比較：3 seed × 512要求、各17回の途中reset。PIXのPALETTE/page/generation/ACK/line mailbox、SYSのready/done/要求アドレスが一致。
- 実際のregister endpoint＋registered head＋command executor＋新旧scanoutを接続：Queue8満杯、後続PALETTE/PRESENT、遅延CPU ACK、タグ・completion error・sticky errorの確認、途中reset。各seedで144件回収、80回の表示適用。
- 実メモリモデル付きscanout：共有化ONで1,843,200画素のpage/PALETTE切替、2倍拡大、背景飽和負荷を検証。
- 契約違反試験：受理後に入力PALETTEを変える不正producerをassertionが拒否。
- 共有化OFFの既存scanout試験も通過。

試験スクリプトの重複起動で一度実行ファイル競合が発生した。排他制御を追加し、最終版を単独再実行して全項目を通過させた。
これは試験実行系の競合であり、回路の不一致ではない。

## 回路規模・STA比較

同じRTL入力、Gowin V1.9.12.04、QSPI Queue8、place=4／route=2、同一CST・SDCでOFF／ONを比較した。

| 指標 | 共有化OFF | 共有化ON |
|---|---:|---:|
| Logic | 7,868 | 7,867 |
| Register | 5,397 | 5,205 |
| CLS | 4,246/4,320 | 4,233/4,320 |
| BSRAM | 23/26 | 23/26 |
| Setup | +0.050 ns | −3.569 ns |
| Setup違反endpoint | 0 | 68 |
| Hold | +0.470 ns | +0.533 ns |
| Hold違反endpoint | 0 | 0 |
| Recovery | +8.556 ns | +9.639 ns |
| Removal | +0.839 ns | +0.830 ns |

ONの最悪経路は`host_active_s0/Q`→起動／RUN選択MUX `n2337_s2`→`core/display/palette_92_s0/D`。
入力が機能上安定していても、snapshot除去でMUXと制御fanoutがPIX転送の遅延へ露出する。
FFの削減量に対して配置容量の改善が小さく、STA悪化が大きいため、追加の同期段や起動制御変更を重ねて採用を強行しない。
[比較とhash](evidence/gpu-palette-sharing/comparison.json)、[機能試験証跡](evidence/gpu-palette-sharing/functional-tests.json)。

## 適用判断の限界

FF削減をCLS削減やSTA合格と同一視しない。既存の数値ゲートはSetup +0.100 ns以上、Setup/Hold違反0、Recovery/Removalに負の余裕なし。
新画像の実機動作、外部PSRAM IOの完全なタイミング保証は別途必要。今回、FPGA SRAM/Flash・RP2040へは書き込まない。
