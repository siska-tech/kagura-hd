# Kagura-FB 技術調査・実現性評価・基本設計

> 設計・実装・診断構成の開発記録です。過去の製品名・資源値・ビルド構成が含まれます。現行 KAGURA-HD の仕様と最新の検証値は [README](README.md) を参照してください。

2026-11-03 ／ 対象 Tang Nano 9K、RP2040・RP2350。調査基準は Kagura-9 の [f562b2e](https://github.com/siska-tech/kagura/tree/f562b2ec84605860fdb9f701f5b2e197b5ed4432)。本書の既存機の測定値は上流の記録、FB の数値は明記した条件での計算または試験目標である。初期調査時点の成果は設計まで。以後のRTL実装・シミュレーション・合成結果は [実装記録](docs/kagura-fb-implementation.md) を参照。

## 採否

**640×360・4bpp を条件付きで採用する。** 画面は FPGA の内蔵 PSRAM の die 0 に置き、表示器が自律走査する。RP2040 は変更矩形を送る。画面が静止していればホスト転送はゼロで、HDMI と音声は進み続ける。初版で優先するのは文字入力、カーソル、ウィンドウ再描画であり、全画面動画の毎秒60枚転送は要求から切り分ける。採用を確定する条件は、共有メモリの行取得期限、720p のタイミング収束、PCM 同時負荷の三つである。

## 何を継承できるか

| 系統 | 上流で確認した事項 | FB での扱い |
|---|---|---|
| 映像 | 既存720pの論理画面は320×180。TileFramebuffer は480p専用で、1,200枚のタイルに38,400 Bを保持する | 専用 bitstream とし、タイル・スプライト・スクロール・従来 VRAM を外す。HDMI 座標、色展開、packetizer、serializer、基板制約を継承 |
| 外部メモリ | パッケージ内64 Mbitのうち、制御済みのdie 0は4 MiB。既存VDPは直接走査しない。8-bit DDR、54 MHz、1命令4 B、ホスト書込みはbyte mask方式 | PHY・初期化とPCMの既存word操作を残し、表示用の線形burst readと連続host writeを追加 |
| 音源 | pulse×3、noise×1、wavetable×2、signed 8-bit・48 kHz固定のPCM×2。左右gainを適用し、16-bit stereoへ混合 | 音源レジスタ、PCM prepare/loop、32 B/ch先読み、ミキサ、audio FIFO、HDMI audioを継承 |
| ホスト | SPI/QSPI、キュー、FENCE、Pico用ソフト、MicroPythonのdirty更新に実装実績 | transportと音源APIを再利用。新しいFB capabilityで識別し、旧tile SDKからの誤書込みを初期化時に防ぐ |

上流では qspipsram720 で PSG 6ch＋PCM 2ch の1時間試験がある。公表された配置例は Logic 6,666、FF 5,152、BSRAM 25/26。FB版の資源見積りには、撤去した回路と新しい仲裁器を含めて再合成が要る。機材総量は LUT4 8,640、FF 6,480、18 Kib BSRAM 26個、PLL 2個。[検証状況][validation]・[長時間試験][stage3]・[疑似FB仕様][tile]・[ボード仕様][board]

## メモリ配置と表示経路

1面は 640×360÷2 = **115,200 B（112.5 KiB）**、stride 320 B。オンチップBSRAMはビット総量でも59,904 Bなので単面を収容できない。PSRAMでは2面で230,400 B、die 0の約5.5%。次表は提案するホスト可視のバイトアドレス（両端を含む）。制御器にはdie相対のword番号を渡す。[PSRAM仕様][ram]

| 範囲 | 用途 |
|---|---|
| 0x400000–0x41C1FF | ページ0 |
| 0x41C200–0x4383FF | ページ1 |
| 0x438400–0x7FFFFF | PCM・アセット。SDKのallocatorが予約し、音声再生中の再割当を防ぐ |

画素アドレスは base + 320y + floor(x/2)。偶数xは上位4 bit、奇数xは下位4 bit。全16 indexを不透明色として使用。16個のRGB444パレットをshadow/activeに分け、垂直帰線で反映する。RGB888出力には各4 bitを複製する。端の奇数画素を書き換える場合はホストのshadowで隣接画素を保存し、バイト境界へ拡張して送る。

    PSRAM die 0 → burst reader (54 MHz) → 320 B × 2 行バンク → index → palette → HDMI
             ↑                               書込54 MHz／読出74.25 MHz
    RP → SPI/QSPI → 書込FIFO → 仲裁器 ← PCM prefetch → mixer → audio FIFO → HDMI

HDMIは VIC 4、横1280+110+40+220=1650、縦720+5+5+20=750。74.25 MHzで60 Hz、OSER10の5倍クロックは371.25 MHz。表示座標(X,Y)に対し (X>>1,Y>>1) を参照し、同じ320 Bを2物理行で使う。BSRAM同期読出し・パレットの遅延分だけ座標先読みを行い、HDMIのDEと最初・最後の画素を揃える。HDMI packet送出は既存のblanking schedulerで継続。48 kHzの基準は54 MHz÷1125、ACRはN=6144、CTS=74250とする。[HDMI実装][hdmi]・[音源仕様][audio]

行バンクは一方を表示中に他方へ次行を先読みする。dual-clock RAMに加え、bank・行番号・ページ世代付きのready/releaseをack付きtoggleで渡す。送信側はackまでタグを保持し、読出し中のbankを上書きしない。リセット時は双方の所有権を初期化し、PSRAM初期化と行0の準備が済むまで黒表示。vblank冒頭で次ページを確定し、行0を先読みする。期限超過時はその論理行を背景色で2行出し、sticky underrunと累積数を記録する。古い世代の行を破棄して行番号で再同期する。行バンクの実データは640 Bで、個別にBSRAMへ割り当てるなら2ブロックを仮予約する。

## 帯域と仲裁の成立条件

以下の MB/s は 10⁶ B/s。ポートの物理上限とアプリが送れる量は別々に扱う。

| 通信 | 計算 | 意味 |
|---|---:|---|
| 画面走査のフレーム平均 | 115,200×60 = 6.912 MB/s | 2倍拡大後の画素をPSRAMから再読しない |
| 表示期間の行取得 | 320 B / (2×1650 / 74.25 MHz) = 7.200 MB/s | 44.44 µs、54 MHzで2,400 cycleごとに1行 |
| PCM 2ch連続再生 | 2×48,000×1 = 0.096 MB/s | sample実データ。短いloop、cache miss、バス切替による追加費用は別途 |
| 全面更新60回/s | 書込6.912、走査・PCM込み計13.920 MB/s | ページ複製やコマンド負荷は含まない |
| 既存PHYのデータ相上限 | 54 MHz×2 B = 108 MB/s | CA・初期latency・CS high・方向切替・仲裁を除いた値 |

既存word方式は1行80命令。期限2,400 cycleを80で割ると、他の利用者も含め平均30 cycle/wordまでしか使えない。上流のPSRAM→従来VRAM COPY実測4.7–5.3 MB/sはbyte engine経由の値であり、表示専用ポートの上限とも保証値ともみなせない。[制御器RTL][ctrl]・[既存測定][ram]

**試作は64 Bの連続読出しを1行5回**とする。54 MHz DDRのデータ相は32 cycle/burst。仮に命令・待ち・終了に32 cycle/burstなら1行320 cycle（5.93 µs）。残余は2,080 cycleだが、この32 cycleは設計仮定である。実チップのlinear/wrapped設定、行・境界をまたぐ挙動、最大CS low時間、固定latencyとread capture窓を照合し、必要箇所で分割する。単語モードのmemtest結果をそのままburstの合否に使わない。

仲裁の単位は最大64 B、1件ずつ完了させる。表示行要求中は表示burstをhostより優先し、PCM要求があれば各表示burst間にPCMを最大1word挿入する。表示のない期間はPCMとhostを交互に許可し、長いhost書込みも分割する。PCMは先読み残量の低下で要求を早める。実装時は開始済みhost 1件、PCM挿入5件、CDC、バンク公開までを含む最悪時間を数える。合格目標は1行 **1,920 system cycle以下（35.56 µs、期限に20%余裕）**。32 BのPCM在庫は満杯で667 µsだが、既存PCM timeoutは4,096 cycle（75.85 µs）。各chの最大応答と残量の双方を記録する。

## ホストと画面更新契約

RP2040は264 KiB SRAM。単面shadow後の物理残量は151.5 KiB、二面では39 KiB。RP2350は520 KiBで、それぞれ407.5 KiB、295 KiB。いずれもスタック・ヒープ・DMA・ランタイムを差し引く前の値。RP2040/Cは単面shadow＋dirty矩形＋PIO/DMAを基準とし、MicroPythonでは連続115,200 Bを起動時に確保できるか測る。不足時はGUI状態から16行帯（5,120 B）を再描画する。RP2350はフォントcache、複雑な合成、GC余裕に有利。共通のFPGA側SCK受入条件ではCPU交換だけで転送上限は上がらない。[Raspberry Pi仕様][rp]

QSPI 5 MHz SDRの純データ相は2.5 MB/s、全面転送の理想最短46.08 ms（21.7回/s）。1-bit SPI同周波数なら0.625 MB/s、184.32 ms。上流の既存queued経路は約2.00 MB/sの算出上限で、MicroPythonの連続1024タイルのflush実効例は約0.345 MB/s。これを仮にFBでも得られると全面約334 ms、32×32矩形は512 Bでpayload相当約1.48 ms。後者に行設定・小転送の固定費が加わるためGUI応答時間の保証には使えない。全面60回/sにはQSPIでプロトコル費用ゼロでも13.824 MHz以上が必要。高速SCKの可否は独立に評価する。[上流transport解析][transport]

**提案ABI** は既存音源・エラー・キュー順序を維持し、FB専用ABI ID、CAPS、寸法・stride・ページ数を公開する。レジスタ番号は既存予約域を照合して実装時に割り当てる。

- WRITE_RECT(page,xByte,y,widthBytes,height,payload) で詰めた行を一括送信し、FPGA側でstrideを加算。範囲・積・payload長を検査する。FIFOのcredit分だけ受け取り、中断時は未完了を報告して同一領域を再送可能とする。
- FENCE(tag) は先行書込みのメモリ反映後に完了。PRESENT(page,palette,tag) は同じキューで書込み完了を待ち、vblankで一括反映。受付と表示世代のackを分け、保留中の2件目はbusy。読出し診断、frame番号、行遅延最大、PCM underrun、FIFO errorを公開する。
- 初版SDKは両ページを同色で初期化。ホストの正本を更新したら両ページのdirty集合に加え、背面の未反映集合を送り、FENCE後にその面だけcleanにする。表示ack後に旧前面を再利用する。差分だけを交互に送って古いウィンドウが再出現する問題を避ける。帯描画モードでも各面に必要な矩形を現在のGUI状態から再生成する。DMA完了まで送信元を保持し、失敗時はdirtyを残す。
- Cは初期化、矩形入力、palette、present/wait、音源操作を提供。MicroPythonはbuffer protocol対応の描画面と同じflush/present契約を使い、DMA・矩形転送はC bindingへ集約。dirty矩形が多いときは近接領域を結合し、送信時間と余分なbyte数を実測比較する。矩形塗りつぶしを最初のアクセラレータ候補とし、採否は後述の比較試験で決める。

## 代替案の選択条件

| 観測した制約 | 代替 | 効果と代償 |
|---|---|---|
| ホスト更新だけが遅い | 640×360・4bppを維持し、帯描画・矩形結合・FPGA fillを順に評価 | 静止画の細字と16色を保てる。帯描画はRAMを節約するが全面転送量は同じ |
| PSRAMの行期限が不足、16色が優先 | 320×180・4bpp、整数4倍 | 28,800 B、走査1.728 MB/s。文字の横・縦解像度は半分。単面をBSRAMへ移す案も再合成で評価 |
| 細字が優先で減色可能 | 640×360・2bpp、整数2倍 | 57,600 B、走査3.456 MB/s。4色。PSRAMを継続使用し、BSRAMには行とFIFOの余裕を確保 |
| linear burst PHYの検証が不成立 | 320×180・4bppのBSRAM単面＋PSRAMはPCM専用 | 共有メモリの映像期限を除去。単面への表示中書込みはtearし得る。vblank中の更新量を制限する |

## 実装判断のための試験順序

1. **既存系の再現**。対象commitのqspipsram720を同一ツール版で再ビルド。資源、PLL、setup/hold、720p表示、6音源＋PCM左右を記録。派生版ではApache-2.0のLICENSE、THIRD_PARTY、HDMIソース生成時のhash確認を引き継ぐ。[上流第三者表記][third]
2. **メモリ単体**。4 B/64 B read/write、境界・方向切替・マスク・短いPCMループをモデルと実機で照合。64 Bごとのアドレスパターンでwrapを検出する。最大burst時間とCK位相余裕を測る。従来word・PCM試験も再実行。
3. **映像と競合**。座標別パターン、奇偶nibble、四隅、フレーム世代を独立参照画像と全画素比較。host連続書込み、PCM 2chの異なるループ、PSG全chを同時に動かし、行公開が全て1,920 cycle以内か確認。遅延注入・リセット・vblank直前直後のpresentで誤ページ表示と音声停止がないことを検査。TMDS復号でVIC、音声sample、CTSを照合。
4. **配置と実機耐久**。54/74.25/371.25 MHzと位相付きCKに既存制約を適用し、CDCを個別レビュー。配置後setup WNS ≥ +0.10 ns、hold違反0、デバイス容量内を要求する。実機は複数sinkで1時間の同時負荷、ライン・PCM・HDMI audio FIFO異常0、表示60 Hz、左右音声連続、読戻しCRC一致を確認する。
5. **GUI評価**。RP2040/C、RP2040/MicroPython、RP2350/C・MicroPythonで同じ文字入力、カーソル移動、ウィンドウ移動、全面画像を実行。描画・転送・FENCE・表示ackを別々に計時し、p50/p95/最大、画面反映回数、送信bytes、空きheapを記録する。暫定UX目標は32×32カーソル更新の入力から表示ackまでp95 33 ms以内。超過箇所に応じて上表から選ぶ。

## 固定機能2D GPUとしての評価

**最初の試作に矩形塗りつぶしを含める。** RP2040は入力処理・レイアウト・可視領域の決定を担い、FPGAは指定された背面ページへの画素生成を担う。上流のRP2040/Cデスクトップ試験では、文字ラベル1個の変更に0.53 ms、ウィンドウ輪郭の8 px移動に4.58 msを要した。これは旧画面での操作・合成・タイル化・SRAMコピーを合わせた値で、FPGA転送は含まない。GPUに移してもレイアウト等はCPUに残るので、これらの時間全体を削減量として計上しない。[上流RP2040ベンチマーク](https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/experiments/c-gem-desktop/BENCHMARKS.md)

### 命令別の費用

下表は1ページに描く1回分。座標と幅はバイト整列、命令記述子は比較用に16 B固定、転送ヘッダ・待ち・境界処理は除外した。FPGA内で生成した画素もPSRAMへの書込み帯域を消費する。

| 操作例 | CPU描画後に送る画素 | GPUへ送る量の例 | FPGAでの実データ移動 | 判断 |
|---|---:|---:|---|---|
| 200×100のウィンドウ背景 | 10,000 B | FILL_RECT 16 B | 書込10,000 B | 最優先。単色生成と矩形アドレスカウンタで実現。枠線も細い矩形で描ける |
| 8×16の不透明文字40個を1行に描画 | 2,560 B | GLYPH_RUN 16 B＋16-bit字形ID×40＝96 B | 字形の読出し最大640 B、画素書込2,560 B（キャッシュヒット時は字形読出し減） | BLIT後の候補。1bpp常駐字形を前景・背景indexに展開。未登録字形は16 B/字＋登録費用 |
| 640×360の端末を16行上へスクロールし、下端を単色消去 | 115,200 B | COPY_RECT＋FILL_RECT＝32 B | 344行分の読出し110,080 B＋画面書込115,200 B | FILL・カーソルに続く優先対象。内部帯域も大きいため文字行の再生成とも比較する |
| 一回だけ使う多色ビットマップ | 画像の4bppサイズ | WRITE_RECT＋同サイズの画素 | 画像サイズ分を書込 | 既存の矩形転送を使う。反復するアイコンのみPSRAMへの初回登録を償却できる |

たとえばスクロールを毎秒60回行うと、1ページ分の描画で13.517 MB/s、走査・PCMを合わせて約20.525 MB/sの有効帯域を要する。下記の差分再生で両ページを追従させれば描画分は定常時に約2倍、合計約34.04 MB/sになる。これらは転送データの下限で、実効値は仲裁、方向切替、短い行末、字形読出しで変わる。CPUとの通信量だけではスクロールの採否を決められない。

### 回路・ソフトウェアの境界

- **共通描画器**。既存の順序付きキューとFENCEを土台に、54 MHzで動く1個の矩形走査FSM、行先アドレス加算器、最大64 Bの作業バッファを追加する。FILLは色indexを複製したbyteを出力。上流のFILLは連続byte、COPYはPSRAMから旧VRAMへの転送なので、stride付き矩形やPSRAM内コピーの実行部を追加する。[上流レジスタ仕様](https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/register-map.md)
- **4bppとコピーの正しさ**。SDKがクリップし、RTLはページ内、座標、幅・高さを加算桁あふれ込みで検証する。奇数端は端byteだけread-modify-writeし、同じbyte内の1画素も処理する。COPYは同一面で重なる場合、下移動は下から、同一行の右移動は右から進め、各分割片を読み切ってから書く。初期COPYは送受x・幅が偶数のものに限定し、未対応は能力フラグで判別してGUI状態から該当矩形を再描画する。
- **リアルタイム性**。GPUをホストと同じ低優先度帯に入れ、各burst後に走査とPCMへ仲裁を戻す。長い描画の途中にもPCM先読みを通す。音源制御命令がキュー先頭で長く待つ問題は別に測り、必要ならSDKが大矩形を帯に分けて発行する。追加PLL・乗算器は要求しない。FIFOと字形cacheは表示行RAMと別に計上し、機能ごとに配置配線差分を取る。
- **ページの正本**。GPUモードはFPGAページを画素の正本とし、ホストはGUIモデルと未反映命令列を保持する。世代kが表示されたら、旧前面（世代k−1）へkの命令列を順番に一度だけ再生し、その後k+1の差分を実行する。相対スクロールの二重実行を防ぐため、ページ世代と完了tagを照合する。字形・画像・WRITE_RECTの元データは両面反映まで保持。タイムアウトで実行済み範囲が不明なら背面をモデルから全再描画する。CPU shadowモードと切り替える際も全面同期する。
- **APIと優先順位**。C／MicroPython共通で fill_rect、glyph_run、copy_rect、write_rect をバッチ投入し、presentで一括確定する。MicroPythonは固定長bytearrayへの追記と一括送信で、文字ごとのSPI往復を避ける。クリップ、文字列の解釈、折返しはCPUで行う。斜線・円はCPUのspan列で開始し、透過blitはアイコン再利用率を測って選ぶ。α合成は宛先読出しと16色への再量子化が増えるため初期候補から外す。

### ハードウェアカーソル（独立した試作候補）

GUIのポインタ1個を走査時に最前面へ重ねる。FILL_RECTと別の機能フラグを設け、塗りつぶし試作と同じ段階で有無を比較する。背景の保存・復元、移動跡の再描画、両ページへの差分再生が不要になる。例えばバイト整列した32×32ポインタが重ならない位置へ移る場合、ソフトウェアが旧・新矩形を全転送すると計1,024 B。ハードウェア方式は定常移動1回につきx/y各16 bitの計4 B＋通信ヘッダで済み、カーソル用のPSRAMアクセスはゼロになる。小さな移動は矩形が重なるので、実効差はdirty領域を結合したソフトウェア版と比較する。

| 項目 | 試作仕様 |
|---|---|
| 形状 | 論理32×32、2bppで256 B。値0は透明、1～3はカーソル専用RGB444の3色。矢印・Iビーム・リサイズ形状をSDKから設定できる。ホットスポットを形状ごとに0～31で指定 |
| 合成 | 既存の論理座標 (X>>1,Y>>1) からポインタ左上（位置−ホットスポット）を引き、符号付きで範囲判定。透明・範囲外なら背景、それ以外はカーソル色を選択する。両者のRGBとDEを同じ段数だけ遅延させ、HDMIの映像入力で合成。論理1画素は物理2×2画素になる |
| 記憶 | FPGA内に256 B×2バンク（生データ512 B）。非表示バンクへ形状を書き、完了後に切り替える。物理BSRAM消費はRAM推論とポート幅に依存するため配置後に確認 |
| 更新 | C／MicroPythonに形状登録、表示／非表示、位置設定を提供。位置はx/yを一組として投入し、描画キューと独立したmailboxでpixel domainへ渡す。垂直帰線で座標・形状bank・色・ホットスポット・表示状態を一括反映。連続移動は最新位置に集約し、反映済み世代番号を返す。形状bankの再利用は反映ack後。ページ切替の有無によらず更新できる |

**判定試験。** 同一入力列で小移動、画面を横断する移動、四隅での部分表示、形状変更、非表示復帰を比較する。長いCOPYとページ反転中も移動させ、入力から反映ackまでp95 33 ms以内、移動に伴うFB書込み0、走査・音声異常0を確認する。FB読戻しCRCは移動前後で不変となるため、ポインタの色・位置・残像は合成後の画素列を参照画像と照合する。CPU実働時間、実転送量、LUT/FF/BSRAM増分と74.25 MHzのタイミング余裕を記録して採否を決める。

### 採用ゲート

同一のGUI操作列を「CPU描画＋WRITE_RECT」「＋FILL」「＋字形」「＋COPY」の順に再生する。RP2040のCとMicroPythonを主比較、RP2350を副比較とし、画面CRC・クリップ位置・両ページの世代を一致させる。重なりの四方向、1 px幅、奇数端、連続スクロール、キュー満杯、PCM 2chと最大長コピーの競合を含める。CPU実働時間（DMA待ち・vblank待ちを分離）、バス上のbytes、GPU busy時間、presentのp95、LUT/FF/BSRAM増分を記録する。暫定採用条件は対象操作でCPU実働時間が半減し、表示反映p95が基準より悪化せず、前節の行取得1,920 cycle・音声異常0・STA条件を満たすこと。実機値が得られるまで、CPU負荷削減率と描画fpsは未確定とする。

[validation]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/validation-status.md
[stage3]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/tile-1200-stage3.md
[tile]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/framebuffer.md
[board]: https://wiki.sipeed.com/hardware/en/tang/Tang-Nano-9K/Nano-9K
[ram]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/psram.md
[ctrl]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/rtl/memory/kagura_hyperram_ctrl.sv
[hdmi]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/hdmi.md
[audio]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/audio-spec.md
[rp]: https://www.raspberrypi.com/documentation/microcontrollers/microcontroller-chips.html
[transport]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/docs/framebuffer-transport-analysis.md
[third]: https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/THIRD_PARTY.md


## 実装スコープの確定（2026-11-03）

Kagura-FBは独立プロジェクトとし、W65C02S対応と旧ROMブート読込みを対象外とする。FPGA内の旧CPUバス・旧ブートローダーをFB専用ビルドへ含めない。SPI／QSPIの合成時選択は維持する。起動時の診断用PSRAMデータ初期化は旧ROMブート読込みとは別の処理であり、現段階の結合検証用に保持する。

## ハードウェアカーソルの実装結果（2026-11-04）

32×32・2bpp・透明色＋専用3色、2バンク、ホットスポット、負座標クリップ、vblankでの一括反映と最新位置集約を実装した。描画BUSYと独立したCSR窓を使う。C/MicroPythonの非同期投入・待機APIも追加した。反映済み世代は実際の反映回数を16bitで返し、集約されたcommit発行数とは区別する。画面外を含む画素照合とSPI/QSPI結合試験、両構成の数値STAが通過した。

現構成はLogic約87%、CLS 96～97%、BSRAM 3/26、DSP 1/10であり、後続のBLIT・字形・音声制御には資源削減と再配置配線を併行する。CPU実働時間とp95反映遅延の実機採用ゲートは未評価。[カーソル仕様](docs/kagura-fb-cursor.md)と[実装・検証記録](docs/kagura-fb-implementation.md)を参照。

## BLIT優先の具体化（2026-11-04）

次は不透明COPY_RECTを字形描画・公開音源制御APIより優先する。現行の1 outstanding命令方式を保ち、転送窓64 Bを作業領域として再利用する。初期実装は送受X・幅を偶数、`src_x % 8 == dst_x % 8`に限定し、縦スクロール、ページ間コピー、重なりに対応する。任意のbyte/nibble位置合わせは資源差分を測って追加する。opcode6、ABI minor2、能力bit6としてRTLとC／MicroPython APIを追加した。

転送計画の画素参照モデル884ケースと不正入力8ケースを検証した。既存メモリRTLの96区間の周期計測に基づく全面コピーのtransaction処理時間は3.733 ms（54 MHz、GPU内部待ち・走査/PCM競合・ホスト通信を除外）。平均帯域上は640×360・4bppを維持する案とし、採用にはBLIT RTLの表示・音声競合試験とSPI/QSPI両方の配置配線が必要。[BLIT評価・命令案・採用ゲート](docs/kagura-fb-blit.md)に詳細を記す。


初期BLITのRTLは1,150ケースの画素参照照合を通過し、SPI/QSPI実CSR経路でも全面コピー・カーソル更新・走査・6音源＋PCM 2chの競合試験を通過した。全面コピーは単独で3.900 ms、結合試験で約4.68 ms、行取得は最大595 sys cycleだった。いずれもシミュレーション値で、実機fpsやCPU負荷削減率ではない。FILLと行走査を共有し、転送窓は512 FFから16個のSP BSRAMへ置換した。起動時は黒画面・無音PCMデータを初期化し、起動パターン用の広い合流回路を除いた。最新の資源・STA結果は[実装記録](docs/kagura-fb-implementation.md)を参照。


BLIT統合版のSPI/QSPIはともにplace 1／route 2で数値STAに合格した。setup +1.122/+0.660 ns、hold +0.558/+0.552 ns、setup/hold違反0。CLSは4,245/4,320（SPI）・4,223/4,320（QSPI）、BSRAM19/26、DSP1/10。論理解像度・色深度・クロックは維持する。残りCLSは少なく、段階B以降の任意位置・透過・字形には別の資源評価が必要。720pの48kHz音声tickはSPI/QSPIで等価なカウンタ表現を使い分け、両者の720,000回のtick判断を独立の整数モデルと照合した。全26 RTL試験・C/Python15試験・実MicroPythonが通過し、実機検証は未完了。
