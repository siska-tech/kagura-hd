> 履歴資料：この文書の未検証・候補・公開保留などの記述は記録時点の状態です。最終版の選定と現行仕様は [リリース案内](release-validation.md) と [README](../README.md) を参照してください。

# KAGURA-HD ショーケース実機評価（2026-11-05）

判定：部分合格・最初のtimeoutで停止。全シーンの実機合格には至っていない。最終復旧は確認済み。`release_ready=false` を維持する。

## 実行条件と結果

使用FPGA SRAMイメージは `build/pcm2-timing-04/build/standard-timing-04/impl/pnr/kagura_fb.fs`、SHA-256は `642c7a3ce961685279c229dbe9b1577285bd7867353cfaf7de8f4db06b3683a7`。Gowin Standard 1.9.12.04の既存成果物を使用し、RTL・Controller・PHY・SDC/CSTの変更、新規Bitstream生成、FPGA Flash書込みは行っていない。

|段階|観測結果|判定範囲|
|---|---|---|
|v1 RAMモジュールロード|元のカスタムMicroPythonでMemoryError、FPGA SRAM投入0回|停止。デモ動作は未評価|
|標準FW切替|ユーザー承認により公式MicroPython 1.26.0へ切替、filesystem初期化|標準FWコードのハッシュ一致、起動確認|
|v2 Preflight/RAMロード|事前free heap 239840B、ロード後165072B、ABI 1.4/CAPS確認|PASS|
|Upload/echo|15ケース|PASS|
|32B境界跨ぎ|独立アドレス・guardを含む1ケース|PASS|
|転送長・配置|11ケース|PASS|
|offset・pattern・mask|40ケース|PASS|
|G1-09タイトル描画|描画job正常終了、status=2/error=0、free heap 150960B|命令実行と状態確認のみPASS|
|G1-09 page0 CRC|115200B読戻し中、120秒でraw REPL応答timeout|測定未完了。CRC不一致を観測したわけではない|
|以後の描画・音声・全ループ|停止条件に従い未実行|未確認|

v2はSRAM投入1回、約269.61秒で停止。PSRAM計67ケースは全てPASS。実行中の合格条件変更、失敗ケース再試行、別Bitstream投入は行っていない。凍結入力とBitstreamのハッシュ不変も確認した。

タイトルのHDMIキャプチャはCRC確認後の予定であり、到達していない。タイトル表示や独立Framebuffer oracle一致を実機PASSとは扱わない。後続のBLIT、パレット/PRESENT原子性、カーソルCRC、PCMバッファ、HDMI音声、連続競合動作は今回未確認。PC側Mock検証を実機検証へ読み替えない。

## 初発異常と原因の限界

初発異常は `crc-G1-09-0` のraw REPL受信timeout。CRC値の出力は取得できていない。長時間の64B単位読戻しに対してjob上限が不足した可能性と、処理途中の停滞の可能性は区別できていない。PSRAMデータ破損、PHY障害、GPU描画不一致の確定証拠ではない。

自動復旧ではraw REPL同期も崩れ、GPIO解放とFlash検証の応答取得が失敗した。FPGAは既存FlashからKAGURA-9へ再ロードできたが、これだけでは復旧完了としなかった。診断を再実行せず、別の復旧専用処理でシリアル同期を取り直した。

次回に必要なのは測定系の修正である。全ページ読戻しを有限サイズの独立jobへ分割し、各区間のoffset・byte数・CRC・所要時間を保存する。区間CRCはホストで結合または独立オラクルと比較し、進捗のない状態を識別する。timeout後は生存するworkerの処理を止め、REPL同期を確認してから復旧命令を送る。今回の凍結キャンペーンを変更して再試行せず、別キャンペーンとして条件を事前固定する。単にtimeoutを延長して合格扱いにはしない。

## 最終復旧

復旧専用処理でQSPI解放・GPIO安全状態を確認し、保護した元のRP2040全Flash復旧UF2を1回適用した。通常soft reset後、KAGURA-9 ABI `(0, 6)`、`last_error=None` を確認。HDMI最終キャプチャを目視し、KAGURA-9コンソールの表示を確認した。

|対象|SHA-256|
|---|---|
|元RP2040全Flashと最終復旧後の全Flash|`7134077f8bb0d5a1cc426235a8e3ee274dbc7a6f9718e1ee6b152036996a6da6`|
|保護した元RP2040全Flash復旧UF2|`4edd3bdcf17411049fe8ce58322c5bd0de2cbb5c41f1933ace1c440b7afaa44b`|
|試験時の標準MicroPython全Flash基準値|`78c84df7a0420275bafd90b82fce5ffa4b43e1a92ad990343f1bf9e741fed896`|
|公式標準MicroPython UF2|`3fb807524074c75694bd4b13a587dc8673e0815d393a5bdfc250c7cd561b34df`|

現在は標準FWを継続使用する状態ではなく、元のFW・filesystemを含むKAGURA-9環境へ復元済み。復旧の追加診断再実行は0回、追加FPGA SRAM投入も0回。

## 証跡

- v1：`build/showcase-hardware-2026-11-05-v1/`
- 標準FW切替：`build/showcase-stock-fw-2026-11-05-v1/switch-result.json`
- v2試験結果：`build/showcase-hardware-2026-11-05-v2/result.json`
- 各ケースのexpected/actual/XORとraw REPL：同ディレクトリの `control/`、`serial-worker.log`、`runner.log`
- 追加復旧結果：同ディレクトリの `recovery-supplement.json`
- 復旧Flash確認：`manual-restore-original-rp.log`
- 起動確認：`manual-recovery_resume.log`、`manual-recovery_state.log`
- 最終HDMI：`kagura9-final-recovered.png`

元の試験結果に残る自動復旧失敗は書き換えず、追加復旧結果を分離保存した。私有情報を含みうるRP2040全Flashバックアップは配布対象にしない。

内部STA合格と今回の有限PSRAM試験合格は、外部I/Oの全仕様・PVT保証、全デモ機能合格、Release承認を意味しない。Release不可。Git Push/Merge/Releaseは行っていない。
