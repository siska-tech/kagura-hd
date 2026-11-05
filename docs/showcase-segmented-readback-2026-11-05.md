> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# ショーケース区間読戻し：PC検証と次回実機条件案

2026-11-05。前回の実機停止結果と復旧証跡は変更していない。今回の作業はPCのみで、COM/JTAG操作、RP2040書込み、FPGA投入は実施していない。

## 実装済み

- `tools/showcase_segmented_readback.py`：512B単位の診断job生成、64Bずつの既存Device API読戻し、ホスト独立オラクルによる全byte比較。expected/actual/XOR・絶対byte位置・区間CRC・所要時間を記録する。欠落・重複・順序違い・不一致は失敗として保持し、後続結果を受理しない。
- `tools/showcase_raw_session.py`：raw REPL取引の失敗時に一度interruptし、serial portを閉じ、同じセッションでの後続命令を拒否する。timeoutまでに受信済みの部分stdoutも保存する。復旧は新しい接続でのみ行う設計。既存の凍結workerには未組込みであり、既存試験結果を書き換えていない。
- `tools/prepare_showcase_readback_plan.py`：前回と同じタイトル描画をPC Mockで再生し、独立Framebuffer oracleから期待byte列と450個の有限読戻しjobを生成する。デバイス操作は含まない。

## PC検証結果

`test_showcase_segmented_readback.py` の5テストと `test_showcase_raw_session.py` の4テスト、計9テストPASS。

両ページの欠落なし全byte比較とCRC、生成したMicroPythonコードの64B×8回の読戻し、破損証跡と失敗保持、不完全な記録・重複・順序違い・不正範囲の拒否、正常raw応答、timeout時の部分ログ保持とclose、同一セッションでの復旧拒否、デバイス例外・不正ACK時の停止を確認した。serialのテストにはFake portを使用し、実USBの切断・停止を保証するものではない。

タイトル期待値を再生成し、凍結済みv2の期待CRCと両ページで一致した。

|page|byte数|区間数|CRC32（十進）|
|---|---:|---:|---:|
|0|115200|225|3079446894|
|1|115200|225|1432089894|

出力は `build/showcase-readback-plan-2026-11-05/`。`plan.json`、`page0.bin`、`page1.bin`、各ページのjob・期待値manifest、`sha256.json`を保存した。RP2040には全画面期待値を保持させず、各jobの受信バッファは64B、hex証跡は最大512B分とする。PC側のoracle保持とRP2040上の使用メモリは別物であり、実機heap最小値は未測定。

## 次回キャンペーン案（未実行）

同じSHA `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7` の既存Bitstream、同じG1-09タイトル条件を使う。各区間は120秒上限を維持し、2ページ全体の読戻しは900秒上限、最大450区間、再試行0回、SRAM投入最大1回とする。1区間のデータを取得した時点でホスト比較し、最初の異常で次のjobを送らない。900秒で完了しなくても条件は実行中に変更しない。

前回の120秒timeoutの原因が単純な所要時間か停滞かは未確定。区間所要時間と最後に完了したアドレスによって識別する。区間化でPASSしても元の全ページjob停止原因を確定したとは扱わない。

これは実行可能キャンペーン全体の完成宣言ではない。新workerへの組込み、進捗ログの逐次保存、ホスト全体deadlineの適用、独立復旧経路、標準FW再導入と事前・事後ハッシュ確認を含むrunnerの組立てとPC故障注入確認が残る。以前の失敗ケース再試行禁止に従い、実機再開は新キャンペーンの条件・復旧処理を固定して別途承認を受けてからとする。音声や全デモの長時間再実行をこのタイトル単独案へ混在させない。

既存GPU RTL、Controller/PHY、SDC/CST、STA合格成果物は保護する。KAGURA-9復旧状態を維持し、`release_ready=false`。新規Bitstream生成、実機投入、Push/Merge/Releaseは行っていない。
