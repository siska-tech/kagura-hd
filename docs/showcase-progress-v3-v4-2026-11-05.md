> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# ショーケース実機継続結果：v3と未実行v4

## v3の実行結果

指定済みPCM2 STA成果物 `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7` をSRAMへ1回投入した。FPGA Flashの書込み、製品RTL/Controller/PHY/SDC/CSTの変更、新規Bitstream生成は行っていない。

- PSRAM 67ケース：全PASS。
- G1-09タイトル：両ページ計230400B全byte比較・CRCとHDMI色/画素プローブ照合PASS。実機キャプチャを目視し、ロゴ・仕様・色帯表示も確認。
- G2-23、G2-47 FILL：途中HDMI照合と最終両ページ全byte比較・CRC・HDMI照合PASS。
- G3-11、G3-23 BLIT：途中HDMI照合PASS。
- G3-47 BLIT最終：page0の区間0～174はホスト比較PASS。区間175の結果ファイルを開く際にPC側PermissionErrorが発生し、キャンペーン停止。データ不一致を理由にした停止ではない。
- 区間175のworker結果は `ok=true`。停止後、保存済み512BをPC上で独立オラクルと比較して全byte一致を確認した。実機への再送はしていない。page0残り、page1、最終HDMIは未確認であり、G3-47全体はPASSとしない。
- パレット、カーソル、PCM、BGM、6シーン通し再生：未実行。

512B読戻しは代表値約0.72秒で進行した。単純換算で1ページの読戻しだけで約162秒となり、前回の全ページjob上限120秒を上回る。これは所要時間不足と整合する観測であり、前回の停滞を完全に否定するものではない。今回のタイトルとFILLは区間化により全byte一致まで到達した。

v3は約1425.25秒で停止。GPIO安全状態確認、既存FPGA FlashからKAGURA-9を再ロード、元のRP2040全Flash復元、通常soft reset、ABI `(0,6)`・last_error=None・HDMI表示確認まで完了した。最終全Flash SHAは `7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`。凍結入力とBitstreamのハッシュ不変を確認。

## 測定系修正とv4準備

結果ファイルの一時的なアクセス拒否に対し、最大5秒間、生成済みの同じファイルを開き直す処理を追加した。デバイス要求の再送・失敗データの再測定とは別のPC内処理。persistent PermissionError、不正JSON、期限超過は従来どおり停止する。原因がWindowsの一時共有競合かセキュリティソフト等かは未同定。

`tools/test_showcase_*.py` 計12テストPASS。区間比較、raw session停止/close、外部中断、同一sessionでの後続命令拒否、PC内ファイルアクセス猶予と期限超過をFakeで確認した。

v4は `build/showcase-hardware-2026-11-05-v4/` に準備・凍結した。タイトル/FILLのv3合格結果を引き継ぎ、PSRAM事前確認の後、未完了のBLIT以降を進める構成。各読戻し確認900秒、各区間120秒、全体10800秒、通し再生1800秒、SRAM投入最大1回、実機再試行0回。Bitstream・判定閾値は同じ。RP2040は試験中だけ公式MicroPython1.26.0、終了時は元の全Flashに復元する。

## v4の実行承認レビュー

v4起動コマンドは自動承認レビューに拒否された。理由は、以前の固定キャンペーンの「失敗ケース再試行禁止」に対し、後の継続指示が明確な上書きになっていないとの判断。拒否後に別経路で起動していない。v4のstarted.markerは存在せず、v4のRP2040書込み・SRAM投入は0回。

再開には、このPC側測定エラーを修正した別キャンペーンによる再投入・未完了項目の再測定を明示的に許可する必要がある。実データ不一致、timeout、識別異常が発生した場合の即停止・証拠保存・復旧条件は維持する。

## 証跡

- `build/showcase-hardware-2026-11-05-v3/result.json`
- 同 `readback-comparisons.jsonl`、`control/`、`runner.log`
- 同 `G1-09.png`、`G2-23.png`、`G2-47.png`、`G3-11.png`、`G3-23.png`
- 同 `recovery-supplement.json`、`manual-restore-original-rp.log`、`kagura9-final-recovered.png`
- `build/showcase-hardware-2026-11-05-v4/prior-handoff-evidence.json`、`plan.json`、`frozen-inputs.json`

現時点は未完走。内部STA、有限のPSRAM/描画試験合格、外部I/O/PVT保証、Release承認は分離する。`release_ready=false`、Release不可。Git Push/Mergeは行っていない。
