# BLIT STORM 1時間耐久試験

2026-11-07。1時間を予定し、最初の異常で停止した。完走は未達。

診断firmware、Queue8、completion burst、merged letteringを使用。
STA改善候補DCB31A19D4AC754D9131EAD492A83A949C9328F236755A65A9EB0F6514DA8181をSRAM投入。
BLIT STORMだけを選び、描画パラメータの時刻を25秒周期とした。
スケジュール時間は単調増加、試験時間3600000 ms。
元の全8シーンを経由した状態と完全一致する負荷ではない。
試験用ソースはbuild/queue8-blit-hour/test-*、ビルド後に製品ソースを試験前内容へ復元。

約489.375秒（ホスト観測）でSTOP rc=-5。最後のPERFは485302 ms。
GPU_RET_ERROR expected=6064 received=6064 status=18 completion_error=0 sticky=2。
423233件投入、423225件回収、peak 8、pending 8、errors 1。
最後のPERFはtimeouts=0、audio_fault=0。

今回の停止分岐はタグ不一致ではなく、タグ一致後に読んだsticky error 2によるKFB_DEVICE。
当該完了のcompletion_errorは0。正常完了がsticky errorと同時に観測された。
初回停止も同じ原因だったとは断定できない。

sticky 2の発生源は、不正SUBMIT、不正CSR書込み、audio CSR応答エラー、
過去のコマンド完了エラーなど複数ある。
従ってRAM取込み変更やQSPI破損を今回のログだけで原因と確定できない。
次の調査はstickyの最初の設定要因と要求アドレス・データを保持するFPGA観測、
または承認済みFPGAで同じ耐久負荷を比較すること。
数値STA改善候補は採用保留を継続。

原ログ・録画・バックアップはbuild/queue8-blit-hour/hardware/candidate。
復旧記録はbuild/queue8-blit-hour/recovery/result.json。
FPGA Flash書込み0回。診断firmwareを元の全Flash像へ戻し全量照合、
承認済みQueue8 SRAMへ復元する。

## 承認済みFPGAでの比較

同一の1時間BLIT STORM専用診断firmwareを承認済みFPGA
5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77で実行。
ホスト観測28.203秒でSTOP rc=-5。最後のPERFは25200 ms。
GPU_RET_ERROR expected=54789 received=54789 status=18 completion_error=0 sticky=2。
22485件投入、22477件回収、pending 8、errors 1。
原証跡はbuild/queue8-blit-baseline/candidate。

STA改善候補だけに固有の障害という仮説はこの比較で支持されなくなった。
両画像で同じエラー分類が観測されたが、stickyの内部設定要因まで同一と断定できない。
ホスト側正常SUBMITと不正CSR、audio bank応答、過去のエラー完了を区別するには、
最初のsticky設定時の原因コード・CSR要求・cmd_tag/cmd_errorをFPGAに保持する必要がある。
BAD_COMMAND設定箇所を監査した結果、不正SUBMIT、未定義CSR書込み、
external_error（audio応答）、非ゼロ完了エラーが候補。
外部音声応答はCSR dispatch bankとaudio_rsp_valid/audio_rsp_errorで伝播する。
音声pollは毎秒実行されるが、時間的相関はまだ確認できない。
今回の比較はSTA候補採用の根拠にはしない。

復旧証跡はbuild/queue8-blit-baseline/recovery/result.json。
