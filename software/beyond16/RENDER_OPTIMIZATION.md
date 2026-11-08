> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# Render optimization

新エフェクト／画質変更なし。既存152×48 VECTOR maskとページ別最終色差分を維持。物理fps改善は未測定。

## 採用候補

隣接ロゴsliceのdyが一致するときだけ8px単位のBLITを結合する。sxとdxの差80、幅は8の倍数でBLIT alignmentを維持する。source header y22..69とdestination y120以降は重ならない。dirty領域／VECTORロゴinvalidは結合後の幅を覆う。同じdyの連続sliceだけなので画素等価。B16_MERGE_LOGO=0で切り戻せる。

scene captionは8×8glyphの同色runを縦に延ばし、8byte visited bitmapで重複描画を除く。source glyphに全bitが立っている矩形だけをFILLする。追加atlas／PSRAM／大規模workspaceなし。caption文字、位置、色、音声trigger時刻は維持。scene境界の事前音声処理や分割は音楽同期へ作用するため未採用。

## 既にある最適化

paletteは変化時だけ送信。VECTORの横final-color run、縦矩形統合、旧線消去と新線の最終mask統合、page別cache、ロゴBLIT領域だけのinvalidは着手前から存在。これを新規成果として数えない。過剰描画rectangle heuristic、mask二重化、次sceneの大量page更新は効果と所有権の証明なしに追加しない。

RASTER scratch帯の最終restoreは画面に見える領域の画素復元で、不要と判断して除去できない。背景復元もpage再利用契約が必要。今回そのまま維持。VECTOR30fpsを保証しない。

## Before / After

同一seed0xb1616、33ms論理tick、150秒4546frame、同じpacked SDK/CAPS cache条件。

|項目|Before|After|
|---|---:|---:|
|GPU commands|486788|476117|
|Host transactions|4381892|4285853|
|wire bytes|23368224|22856016|
|BLIT pixels|86019264|86019264|
|GPU error / BUSY overwrite|0 / 0|0 / 0|
|両page全byte、palette、表示page|基準|全frame一致|
|実機fps / CPU Headroom|既存実機記録|NOT RUN / NOT MEASURED|

削減率約2.19%。PCモデルの命令数結果であり実機速度の推定値ではない。固定seed再実行も全frame digest一致。evidence/headroom-render.json参照。

PROFILE OFF/SUMMARY/DETAILED、cooperativeを同じ4546frameで旧版と全byte照合。absolute30Hzは同じ受理時刻で画素を比較するため34ms入力4412frameを使う。schedulerの受理frame数／deadlineの物理検証をこれで代替しない。独立BlitModel oracle、fault、tag wrap、PCM0/1契約は既存test.pyでも回帰する。
