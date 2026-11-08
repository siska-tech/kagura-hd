# Queue8 STA改善候補の実機停止調査

2026-11-07。停止原因は未確定。

元firmwareで基準FPGAは150秒を完走。改善FPGAはBLIT STORMの約114秒で停止し、
198128件投入、198120件回収、pending 8、errors 1、STOP rc=-5。
最後のPERFはtimeouts=0、audio_fault=0。原ログは
build/queue8-sta-hardware/run1/candidate/demo-usb.log。

kfb_waitのrc=-5には、完了エラー、sticky error、完了タグ不一致の分岐がある。
現存ログは受信タグ・完了エラー・sticky値を保持していない。
errors 1とpending 8だけではenqueueとretireのどちらの失敗かも確定できない。
従ってPSRAMデータ破損やRAM選択変更を原因と断定できない。

B16_KFB_PROFILEの異常時だけ、GPU_RET_ERRORまたはGPU_RET_TAGを出力する診断を追加。
従来のACK・sticky確認・不一致停止の分岐は維持。
元と同じQueue8、metrics、merged lettering、completion burstで独立ビルドした。

| 診断firmware＋改善FPGA | 投入 | 回収 | pending | errors | 結果 |
|---|---:|---:|---:|---:|---|
| 1回目 | 324805 | 324805 | 0 | 0 | 150秒全8シーン完走 |
| 2回目 | 325087 | 325087 | 0 | 0 | 150秒全8シーン完走 |

両回ともGPU_RET異常ログなし。診断のprintfは異常時だけだが、
RP2040バイナリ配置や実行タイミングが変わるため、元firmwareの障害解消とは判定できない。
候補は引き続き採用保留。数値STA合格と実機安定性を別々に記録する。

証跡と全HDMI録画はbuild/queue8-diagnostic/hardware/candidate、
build/queue8-diagnostic/repeat/candidate。復旧記録はbuild/queue8-diagnostic/recovery。
Flashは書込み前二重バックアップ、firmware領域の書込み後照合、filesystem・末尾保持確認を実施。
診断後に元の全Flash像へ復旧し全量照合し、基準FPGAをSRAMへ再投入する。
FPGA Flash書込みは0回。

次の切分けには元firmwareでの再現頻度の測定と、受信値を残しつつ
ホットパスの配置変化を抑えた診断、QSPIサンプリングの検証が必要。
今回の2回正常を根拠にRTLの採用へ進めない。

## 元firmwareの再現試験

元firmwareの全Flash像が初回基準測定前の像と一致することを二重読出しで確認し、
同じSTA改善候補をSRAM投入して150秒・全8シーンを再実行した。
324967件投入・全件回収、peak 8、pending 0、errors 0、STOP rc=0。
前回の約114秒停止は再現しなかった。元firmware＋改善候補は現時点で2回中1回停止、
1回完走であり、この少数試験から故障率を推定しない。
診断版だけの配置変更を非再現の説明として確定する根拠も得られていない。
記録とHDMI録画はbuild/queue8-original-repeat/candidate。
終了後、承認済みQueue8のSRAM再投入でFinishedを確認。
今回のRP2040 Flash書込み・FPGA Flash書込みは0回。
