# 公開準備の検証

## 2026-11-09：PCMストリーミング選定版

作業ツリーの `rtl/` と `boards/` を、選定版（[releases/pcm-stream-qspi](../releases/pcm-stream-qspi/README.md)）の入力に揃えたうえで、[CI](../.github/workflows/kagura-fb.yml) と同じ試験を WSL（Verilator 5.032、seed 1）で実行しました。すべて合格です。

|区分|試験|
|---|---|
|RTL|FB 全回帰、QSPI PCM2 board、32B wrap、wrap 統合、共通 HDMI・音声・メモリ、カーソル pipeline、音声 credit、packet-first、GPU queue（decode、command queue、ACK 観測、queue host ×3 構成）|
|ソフトウェア|C/Python ドライバ、BLIT 解析、BEYOND 16 の PC 回帰と lettering、FOUR OPERATORS と MIDNIGHT TERMINAL の PC ビルド・全編実行|
|成果物|`tools/check-release.py`（選定版 bitstream、パッケージのチェックサム、固定入力 41 件、作業ツリーとの一致）、`tools/check-dependencies.ps1`（固定第三者ソース 12 件）|

注記：

- MicroPython の実ランタイム試験は、ローカルに環境がないため実行していません。
- 作業ツリーの `software/beyond16/tools/ci.sh` は改行が CRLF なので、LF に変換して実行しました。git はコミット時に LF へ変換します。
- 実機での確認は各デモの README にあります。選定版の上で、BEYOND 16 COLORS、FOUR OPERATORS、MIDNIGHT TERMINAL がそれぞれ完走しています。

## 2026-11-06：PCM2 候補04（履歴）

実機Demoが使用したPCM2 QSPI候補04をルートへ統合し、独立したビルド領域で回帰を実行しました。実行結果は[JSON](evidence/release-preparation-2026-11-06.json)、生ログは同じevidence配下に保存しています。

|検証|結果|
|---|---|
|C/Python既存ドライバ|15件 PASS|
|RP2040 QSPI transport|4件 PASS|
|C/Python音声CSR|10件 PASS|
|全FB回帰|26件 PASS|
|実board top QSPI PCM2|PASS：ABI1.4、upload/readback、stereo oracle、制御・拒否系・表示|
|32B wrap controller|PASS|
|32B wrapモデルでのFB統合|12件 PASS|
|共通HDMI・音声・メモリ|22構成 PASS|
|BEYOND PC：通常／descriptor packing|4件 PASS|
|Showcase PC：wire Mock／独立pixel oracle|16件 PASS|
|採用Bitstream・元入力・package inventory|PASS：元入力40ファイル、SHA-256一致|
|固定第三者ソース|12ファイル PASS|
|PowerShell build入口の構文、git diff --check|PASS|

Verilator 5.032、seed 1、WSL/Linuxを使用しました。元入力と現在のFPGAソースはテキストのLF/CRLFだけを正規化して照合します。配布用の元入力とBitstreamはバイト列を変更せず保存しています。

QSPI音声試験の入口にHDMI派生ソース生成を追加し、過去のbuildディレクトリなしでも単独実行できるよう修正しました。既存のC SDKの任意option `KFB_PACK_DESCRIPTOR`は保持し、通常版と有効版をDemoのPC回帰で比較しています。

今回Gowin再ビルドと実機再投入は行っていません。採用ファイルは既存の実機確認済みBitstreamです。Unix MicroPythonは今回のWSL環境に未導入のため再実行していません。既存の実機・STA記録は記録時点の結果として保持し、今回のPC回帰を新しい実機確認とは扱いません。
