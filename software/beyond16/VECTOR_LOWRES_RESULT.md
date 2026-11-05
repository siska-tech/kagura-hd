# VECTOR 低解像度・最終画面差分方式

152x48 indexed RAM maskへBresenham連続線をpainter順に合成し、4x4表示セルへ拡大する。4bpp packed版より単純な1byte/cellを採用。現在mask7296B、back page別前回mask14592B、計21888B。前回maskはengine内に保持し、engine間で共有しない。

各pageの最終色との差分から色0（旧線消去）も含む横runを抽出し、同色かつ未更新の連続行へ矩形化する。GPUは既存FILLのみ。通常VECTORでは従来dirty消去を省略し、scene入口は前回maskを失効。scene出口の残像消去用dirty情報は維持する。17.5秒以降のロゴBLIT期間は従来dirty消去＋mask再生成へ戻し、BLITが上書きしたmask領域のcache不整合を防ぐ。

607時刻・20秒のVECTOR PC負荷：156770command、平均258.27/frame、最悪688/frame（scene入口文字等込み）。直前実機版相当の同じtimestamp列298131command比47.42%減。画素等価試作277987比43.60%減。これは実機fpsの予測ではない。

見た目は意図的に変更：点線を4pxセルの連続線へ変更。立体計算・色・時間制御を維持。PNG evidence/vector-lowres-120000.png等を生成し目視確認。旧画素との一致は要求しない。

既存の独立Python GPUモデル対C実装、全scene autoplay、fault非再送、timeout/tag wrap/boundsの4テストPASS。engineサイズ増に合わせてテストの固定8192B確保をb16_size()に修正し、正常exit0を確認。これはGPU描画命令の画素照合であり、Bresenham形状の独立数学oracleではない。

RP2040ビルドPASS：text315492B、bss210540B、stack8192B設定、Flash容量検査PASS。実機stack high-water未測定。実機書込みなし、前回firmwareを保持。実機fps／音声NOT RUN、release_ready=false。

残る改善余地：ロゴ期間のcache無効化、より少ない矩形への分割、縦横方向の選択、mask粗密比較、Host固定費。平均258命令では現在の通信条件で30fpsを保証できない。全画面uploadや未完了commandの上書きは導入していない。
