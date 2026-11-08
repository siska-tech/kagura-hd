# 改善第1段階

背景dirty rectangleの横runを縦方向にも統合し、captionの1pixel FILLを文字行の連続spanへ変更した。

同じseed・33ms刻み・150秒の4,546時刻で旧DLLと新DLLを比較し、両Framebuffer全byteと表示paletteが毎回一致。GPU error／BUSY overwriteはいずれも0。

|PCモデル累積（startup込み）|旧|新|
|---|---:|---:|
|GPU commands|1,039,258|943,911|
|Host transactions|9,374,036|8,515,913|
|wire bytes|50,553,615|45,976,959|

transactionは9.15%減。実機fpsの改善率ではない。以前の報告とtimestamp列が異なるため、今回の旧新だけを比較する。

RP2040 ReleaseビルドPASS。text316432B、bss41188B、filesystem境界検査PASS。実機への書込み／測定は未実行。凍結した実機証跡は以前のbinaryを示し、新binaryを証明するものではない。

未実施：不要palette送信削減、PLASMA上書き前消去撤廃、tile cache、ROTO／VECTOR描画方式変更、ログ軽量化、実機Before/After。Release NOT READYを維持する。

再現：tools/verify_pass1.py（out/optimization-before/optimized.dllを参照）。比較結果：evidence/optimization-pass1.json。
