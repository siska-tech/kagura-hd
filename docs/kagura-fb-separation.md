# KAGURA-HD の継承元と Desktop 移管

KAGURA-HD は [Kagura-9 の基準コミット](https://github.com/siska-tech/kagura/tree/f562b2ec84605860fdb9f701f5b2e197b5ed4432) を基盤に開発しました。公開スナップショットは新規 main の単独初期コミットとして準備し、開発リポジトリとそのバックアップを保護しています。

CI は FB とその共通部品の回帰を実行します。Kagura-9 専用のレジスタ ABI・VDP・CPU・旧ホストソフトの CI は分離しました。共通 HDL と診断 Top、制約、Gowin 診断ツールは保持しています。

Desktop は将来 kagura-desktop へ移管する方針です。元の [software/desktop](https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/software/desktop/README.md) と [experiments/c-gem-desktop](https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/experiments/c-gem-desktop/README.md) が主対象です。C core / retained / text / binding / tests に加え、MicroPython の Desktop・UI・SDK・フォント、frozen module 設定、Pico の旧転送層、UI 計測・デバイス制御ツールが依存候補です。CMake は旧 MicroPython 配下の美咲フォントを参照し、実験実装は Pico の C 転送に依存します。

移管時は旧 SDK と KFB1 / ABI 1.2 の違いを精査し、CMake・MicroPython・Pico SDK の依存とフォント等の許諾を継承してください。元の [THIRD_PARTY.md](https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/THIRD_PARTY.md) に権利表示があります。移管先の作成とコードのリファクタリングは今回の範囲に含めていません。

公開候補 488 ファイルの選別記録、除外対象と開始時ハッシュの詳細は開発側の build/publication-audit に保存しました。Desktop・ゲームの旧ログと画像、開発用整理台帳は元の開発リポジトリに保存されています。
