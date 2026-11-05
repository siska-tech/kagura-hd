# KAGURA-HD 資料案内

現行版は実機Demoで使用した **PCM2 / ABI 1.4 / QSPI** です。

- [製品概要・実機確認範囲](../README.md)
- [通常Release添付一覧（QSPIのみ）](../releases/README.md)
- [validated / experimental成果物の区分](../artifacts/README.md)
- [最終Bitstream・SHA-256・元ビルド入力](../releases/pcm2-qspi-final/README.md)
- [公開準備状況・制限](release-validation.md)
- [Standard Editionのビルド手順](standard-build.md)
- [Host ABI 1.4・配線・C/MicroPython API](kagura-fb-host-api.md)
- [BLIT](kagura-fb-blit.md)、[カーソル](kagura-fb-cursor.md)
- [BEYOND 16 COLORS 実機結果](../software/beyond16/HARDWARE_RESULT.md)
- [MIDNIGHT TERMINAL 実機結果](../software/midnight_terminal/HARDWARE_RESULT.md)
- [公開準備でのファイル整理](cleanup.md)
- [統合後の回帰検証](release-preparation-validation.md)

## 開発履歴

以下は記録時点の結果です。未投入・Release保留などの記載は、その後の実機結果と分けて参照してください。

- [候補04までのタイミング改善とPC検証](pcm2-timing-improvement-2026-11-05.md)
- [PCM2専用構成とSDK](audio-pcm2-result-2026-11-05.md)
- [RMW統合キャンペーン](rmw-campaign-result-2026-11-05.md)
- [Showcase実機結果](showcase-hardware-result-2026-11-05.md)
- [旧Standardビルドのタイミング調査](standard-timing.md)
- [初期実機検証](hardware-validation.md)、[PSRAM調査](psram-investigation.md)
- [旧公開スナップショット監査](publication-audit.md)
- [継承元とDesktop移管](kagura-fb-separation.md)、[出典](sources.md)

診断Top、結果JSON、raw証拠は元の相対パスで保存しています。architecture / video / timing / audio等の継承資料は旧構成を含む設計履歴です。
