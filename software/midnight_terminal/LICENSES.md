# 出典・ライセンス

新規C/Python/PowerShell、シナリオ、幾何形状から作成したドット絵、合成PCMは、このリポジトリのApache-2.0で提供する。既存作品の画像、キャラクター、台詞、曲、ロゴを使用していない。配布フォントの権利は以下のとおり別扱いとする。

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

実機投入用USB版はPico SDK固定submoduleのTinyUSB（commit `86ad6e56c1700e85f1c5678607a762cfe3aa2f47`、MIT）を使用する。`vendor/TinyUSB-LICENSE`と`vendor/Pico-SDK-LICENSE`へ上流のライセンス文書を保存した。可逆LZの圧縮・展開コードはこの作品用の新規Apache-2.0ソース。
