# 公開準備時の整理（2026-11-06）

> 履歴資料：2026-11-06時点の整理記録です。2026-11-08に、選定版はPCMストリーミング版（[releases/pcm-stream-qspi](../releases/pcm-stream-qspi/README.md)）に置き換わりました。

実機Demoで使用したPCM2 QSPI候補04を最終版として選定しました。RTL・board top・SDK・回帰試験をルートへ統合し、既存C SDKの`KFB_PACK_DESCRIPTOR`も保持しています。

一回限りの候補生成・freeze・集計スクリプトは、未追跡ファイルだけを対象としてローカルの`build/development-archive-2026-11-06/tools/`へ退避しました。ファイル一覧は同ディレクトリの`manifest.json`にあります。公開用の再ビルドや回帰試験には使用しません。削除はしていません。

既存の`build/`には不採用候補、実機録画、退避Flash、ライセンス関連情報を含む可能性があるため、公開パッケージへ一括コピーしません。`.gitignore`で引き続き除外しています。採用Bitstreamと正確な入力40ファイルだけを`releases/pcm2-qspi-final/`へ取り出しました。

`diagnostics/`、`sim/diagnostics/`、結果JSONと履歴文書は再現性と不具合調査の根拠として保持します。履歴文書には現行案内への注記を付け、相対リンクを維持しました。ローカルIDE設定`.vscode/`は公開対象から除外しました。

統合前の変更対象ソースは`build/release-preparation-backup/`へ保存しています。既存の実機録画や作業ツリー、Flashバックアップには手を加えていません。

ローカル退避した一回限りのスクリプトは合計65本です。

- `tools/add-audio-readback-ram.py`
- `tools/compact-audio-snapshot.py`
- `tools/finalize-pcm2-timing.py`
- `tools/finalize-stock-campaign.py`
- `tools/finalize_showcase_campaign_v3.py`
- `tools/freeze-audio-csr-build.py`
- `tools/freeze-audio-minimal-pnr.py`
- `tools/freeze-audio-minimal-synthesis.py`
- `tools/freeze-audio-pcm2.py`
- `tools/freeze-audio-snapshot192.py`
- `tools/freeze-pcm2-timing.py`
- `tools/freeze-rmw-campaign.py`
- `tools/freeze-showcase-hardware.py`
- `tools/freeze-upload-rmw-build.py`
- `tools/implement-audio-minimal-bridge.py`
- `tools/integrate-audio-host-csr.py`
- `tools/prepare-audio-board-test.py`
- `tools/prepare-audio-calibration.py`
- `tools/prepare-audio-default-equivalence.py`
- `tools/prepare-audio-minimal-bridge.py`
- `tools/prepare-audio-minimal-qspi.py`
- `tools/prepare-audio-minimal-sdk.py`
- `tools/prepare-audio-minimal-tests.py`
- `tools/prepare-audio-pcm2-host-tests.py`
- `tools/prepare-audio-pcm2-unit-tests.py`
- `tools/prepare-audio-pcm2.py`
- `tools/prepare-audio-snapshot192-tests.py`
- `tools/prepare-audio-snapshot192.py`
- `tools/prepare-pcm2-timing.py`
- `tools/prepare-pcm2-timing02.py`
- `tools/prepare-pcm2-timing03.py`
- `tools/prepare-pcm2-timing04.py`
- `tools/prepare-psram-diagnostics.py`
- `tools/prepare-rmw-campaign.py`
- `tools/prepare-upload-rmw-hardware.py`
- `tools/prepare-upload-rmw-worktree.py`
- `tools/prepare_showcase_campaign_v3.py`
- `tools/prepare_showcase_campaign_v4.py`
- `tools/prepare_showcase_readback_plan.py`
- `tools/share-audio-shadow-read.py`
- `tools/summarize-audio-csr-implementation.py`
- `tools/summarize-audio-minimal-pnr.py`
- `tools/summarize-audio-minimal-synthesis.py`
- `tools/summarize-audio-pcm2.py`
- `tools/summarize-audio-snapshot192.py`
- `tools/summarize-pcm2-timing.py`
- `tools/summarize-rmw-campaign.py`
- `tools/summarize-upload-rmw-regressions.py`
- `tools/analyze-a0-difference.py`
- `tools/analyze-audio-calibration.py`
- `tools/analyze-audio-pcm2-scope.py`
- `tools/analyze-audio-pcm2-sta.py`
- `tools/analyze-audio-register-storage.py`
- `tools/analyze-psram-observation.py`
- `tools/analyze-rmw-campaign-audio.py`
- `tools/audit-audio-csr-implementation.py`
- `tools/audit-audio-minimal-bridge.py`
- `tools/audit-audio-pcm2.py`
- `tools/audit-audio-snapshot192.py`
- `tools/audit-upload-rmw-integration.py`
- `tools/check-pcm2-timing-raster.py`
- `tools/check-rmw-campaign-pc.py`
- `tools/complete-rmw-campaign.py`
- `tools/run-pcm2-timing03-pc.py`
- `tools/save-upload-rmw-hardware-result.py`

## 公開時の成果物配置

QSPI本体は`artifacts/validated/kagura-hd-qspi-pcm2.fs`、STA不合格SPI本体は`artifacts/experimental/spi-sta-fail/kagura-hd-spi.fs`へ移動しました。SPIにはDO_NOT_PROGRAMとタイミングレポートを同梱し、通常のRelease対象から外しました。`releases/`には元入力・メタデータ・履歴ログを保持し、Bitstream本体を重複配置しません。

公開用の実機記録では個体固有のRP2040 UIDを伏せています。元記録は`build/publication-private-backup/`へ保持しました。個体を選別する実機スクリプトは`KAGURA_RP2040_UID`環境変数を明示的に要求し、未指定時には接続を開始しません。数値測定値とBitstream本体は変更していません。
