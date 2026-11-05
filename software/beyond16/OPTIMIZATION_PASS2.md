# 改善第2段階

画素等価を維持して以下を実装した。

- PLASMA：page別tile ID cache、変化tileのみBLIT、定常時の消去撤廃。scene遷移時はcache失効・残像消去。
- ROTOZOOM：横方向の同色セルを1 FILLに統合。
- VECTOR：同じ高さで重なる線分ドットを矩形に統合。
- Palette：実際のshadow値を保持し、値が変わる場合のみ送信。
- 第1段階のdirty矩形縦統合とcaption span化を維持。
- 通常RP2040ビルドはUSBのみ。毎frame FRAME文字ログを抑止し、1秒PERF集計とerror/STOPを維持。B16_VERBOSE_FRAMES定義で詳細ログ復帰可能。

旧版との同一seed・33ms刻み150秒、4,546時刻の両Framebuffer全byteと表示palette比較PASS。GPU error／BUSY overwrite=0。独立oracle／異常系を含む既存4テストはVECTOR最終統合前にPASS、最終統合後は全時刻旧新版比較PASS。

|PCモデル累積・startup込み|旧版|改善版|
|---|---:|---:|
|commands|1,039,258|714,804|
|transactions|9,374,036|6,453,950|
|wire bytes|50,553,615|34,979,823|
|BLIT pixels|113,097,856|76,420,224|

transactions31.15%減、commands31.22%減。これはfps向上率ではない。比較の生値はevidence/optimization-pass1.json（第2段階までを含む累計、script名は初期名を維持）。

RP2040 ReleaseビルドPASS。text313684B、bss41420B。filesystem開始0x100a0000の容量検査PASS。実機投入は未実行、既存Flash内容は保持。既存hardware証跡とSTATUSは以前の実機版に対する記録で、新版の実機性能証明ではない。release_ready=false。

残る課題：RASTERの162帯FILL＋55ロゴsliceなどの再設計、VECTORのさらなるspan化、Host区間計測と通信経路改修。これらは今回の等価最適化の範囲では未実施。30fps達成は未確認。次の実機評価では描画区間・PRESENT・更新完了間隔を測定し、FRAMEログの抑止に対応して収集scriptも更新する必要がある。
