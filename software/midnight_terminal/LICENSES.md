# 出典・ライセンス

FM版（2026-11-09に全面再作成）の新規ソースと素材は、このリポジトリのApache-2.0で提供する。対象は、C・Python・シェル・PowerShell、台本（`tools/story.py`）、FM音源の曲と効果音、絵を加工するコード（`tools/paint.py`、`bar_reference.py`、`ai_art.py`）である。既存作品の画像、キャラクター、台詞、曲、ロゴは使っていない。異常ログの文面は旧版（同じリポジトリのオリジナル）から引き継いだ。配布フォントの権利は、以下のとおり別に扱う。

|項目|M+ BITMAP FONTS|美咲フォント|
|---|---|---|
|配布版|2.2.4|BDF 2021-05-05|
|著作権|2002–2005 COZ（配布LICENSE）|2002–2021 Num Kadoma|
|採用|mplus_j12r、mplus_f12r＋公式JIS0201差分|misaki_gothic.bdf|
|保存ライセンス|`vendor/LICENSE_E`、`LICENSE_J`|`vendor/misaki.txt`、`misaki-license-page.html`|
|原配布案内|[M+ BITMAP](https://mplus-fonts.osdn.jp/mplus-bitmap-fonts/)|[美咲公式](https://littlelimit.net/misaki.htm)、[公式ライセンス](https://littlelimit.net/font.htm)|
|取得元|[Debian original-source mirror](https://deb.debian.org/debian/pool/main/x/xfonts-mplus/xfonts-mplus_2.2.4.orig.tar.xz)|[公式BDF ZIP](https://littlelimit.net/arc/misaki/misaki_bdf_2021-05-05.zip)|

M+は上流版2.2.4の内容をDebian original-source mirrorから取得したもので、上流サーバーから直接取得したアーカイブではない。保存したアーカイブ内のライセンスと字形を確認した。現在のアウトライン版M PLUSのSIL OFLを、この旧bitmap版へ適用していない。

それぞれの保存配布物を**別々に確認**し、利用・複製・変更の有無を問わない再配布・商用／非商用利用の許諾と無保証を確認した。著作権表示とライセンス全文を上記ファイルに保存し、subsetにも同行させる。偶然似た許諾文であることを、同一ライセンスの推測に置き換えていない。フォントを含むPNGにもこの出典を付随させる。

SHA-256と正確な取得URLは[`vendor/provenance.json`](vendor/provenance.json)。元アーカイブも同ディレクトリに保存した。BDF内の字形をBBX・baselineに従って配置し、Unicode索引、1bpp行配列と可視化atlasへ変換する。平滑化・OSフォントによる置換・字形のAI生成は行わない。

Pico SDK 2.1.1はBSD-3-Clause等の上流ライセンスに従う。SDKとArm GNUビルドツールは`toolchain/`の開発依存で、このショーケースのGit成果物には含めない。既存KAGURA C SDKは元リポジトリのApache-2.0のまま再利用する。

`vendor/kagura_host.pio`と`vendor/kagura_pio_timing.py`は、ローカルKAGURA-9のC Hostドライバ／PIOタイミング試験から無変更で複製したApache-2.0のソース。出典パスとSHA-256は`vendor/qspi-provenance.json`。Cの転送管理はHDの6bitプロトコル用に適合し、KAGURA-9固有のレジスタ操作は複製していない。

実機投入用USB版はPico SDK固定submoduleのTinyUSB（commit `86ad6e56c1700e85f1c5678607a762cfe3aa2f47`、MIT）を使用する。`vendor/TinyUSB-LICENSE`と`vendor/Pico-SDK-LICENSE`へ上流のライセンス文書を保存した。可逆LZの圧縮・展開コード（`src/mt_lz.*`、`tools/pack_bgm.py`）は、BEYOND 16 COLORSなどと共有する新規Apache-2.0ソース。FM版の画像はDEFLATE（`zlib`で圧縮）で格納し、展開器`src/mt_inflate.c`はRFC 1951に基づいて新規に書いた。5×7のASCIIフォントは[FOUR OPERATORS](../fm_megademo/src/font.c)のものを共有している。

## 絵の出典

タイトル、バー、端末の絵は、プロジェクトの所有者が画像生成AIで作成し、2026-11-09にこの作品のために提供したイラストです。

- **配布の前提：** 生成に使ったサービスの規約が、これらの画像の再配布を認めていること。
- **扱い：** コードによる手続き生成ではない素材として、ほかの成果物とは区別して記録します。
- **リポジトリに置くもの：** 640×360に縮小した版だけです。

|絵|元画像|SHA-256（元画像）|
|---|---|---|
|タイトル（店の外観）|1672×941|`5517552ff815873e19f5160858e48adc4ff19797d25f8f254a949f122804394e`|
|端末|1672×941|`87d7b3078b73a94fd070ecbd2c0305a08e6bd2f6b76527739653f423906a9230`|
|バー（ミオ）|1672×941|`bc5c0b6e51b4fec5b69287e6ed23c14ca5b79ceb3a2d10a654ad72722853c1db`|
|まばたき（目を閉じたミオ）|1671×941。目の周りだけを保存|`0147c91b2977d209dde6997aa2881a93e97e2c4806dc76f54c566e453984aa5b`|

### バーの絵（ミオ）

バー店内の絵（`art/bar-reference-640x360.png`）について。

- **元画像：** 1672×941、SHA-256 `bc5c0b6e51b4fec5b69287e6ed23c14ca5b79ceb3a2d10a654ad72722853c1db`。リポジトリには、640×360に縮小した版だけを保存しています。
- **加工：** `tools/bar_reference.py` で、16色（RGB444）に量子化しています。
- **まばたきの差分：** 所有者が同じく画像生成AIで作成して提供した、目を閉じたミオの絵（1671×941、SHA-256 `0147c91b2977d209dde6997aa2881a93e97e2c4806dc76f54c566e453984aa5b`）から作っています。
  - リポジトリには、目の周りだけを切り出した `art/blink-reference-eyes.png`（元画像の(480,300)から360×140）を保存しています。
  - 両目の位置に合わせて拡大縮小・回転して合成し、色を合わせています。
- **赤い目の差分：** 瞳の色だけをコードで置き換えています。
