# Third-party policy and investigation

hdl-util/hdmiの原版RTLを`third_party/hdl-util-hdmi/`に保存している。10 RTLファイルとLICENSE-APACHE/LICENSE-MITの計12ファイルは原版のまま、manifestでSHA256を固定。Apache-2.0側を選択し、著者表記と両ライセンス本文を保持。別NOTICEは調査treeに存在しなかった。Gowin/tn_vdp/SVOソースは取り込んでいない。

| Candidate | 調査した許諾 | 方針 |
|---|---|---|
| hdl-util/hdmi | READMEでMIT OR Apache-2.0、LICENSE-MIT/ LICENSE-APACHEを確認 | 採用済み。Apache-2.0を選択し、原版ファイル一覧・hashをmanifestに固定。ローカル置換実装は下記と[出典](../../../docs/sources.md)を参照 |
| lfantoniosi/tn_vdp | root BSD-3-Clause | 9K v2を参考。F18A/HDMI/Gowin等の個別由来を再確認してから必要箇所だけ採用 |
| Sipeed SVO | 調査したsvo_tmds.vにISC相当の許諾文 | 同じ許諾が全ファイルにあるとは仮定しない |
| Gowin generated IP | 生成wrapperにGowin copyright/all rights reserved | EDAで再生成、同梱/再配布条件を確認。独自成果物として再ライセンスしない |

revisionとURLは[出典](../../../docs/sources.md)。今後の導入時には原著作権、ライセンス本文、変更内容、必要なNOTICEを保持し、トップレベルLICENSEだけで上書きしない。

`tools/prepare-hdmi-stream.py`が原版`hdmi.sv`から派生ソースをbuild内へ生成する。原版のハッシュを検証し、変更箇所をコード上のanchorで限定、由来とApache-2.0選択を生成物に記載する。原版は不変。stream構成で再利用するpacket formatters/assembler/TMDS encoderも同じライセンス条件で使用する。

`rtl/hdmi/kagura_tmds_channel.sv`は固定した上流`src/tmds_channel.sv`（著者Sameer Puri）を基にしたローカル置換実装として管理する。74.25MHz向けにprefix XORと3段パイプラインへ構成を変更し、上流より2 pixel clocks遅い同一出力列を生成する。Apache-2.0を適用し、由来・変更内容をソース先頭にも記載する。原版は比較試験とDVI構成で使用する。

`rtl/hdmi/kagura_packet_assembler.sv`も同様に、上流`src/packet_assembler.sv`を基にしたローカル置換実装である。counterで選ぶbit muxをshift registerに置き換え、上流と毎cycle同じ出力を生成する（`tb_packet_assembler`で検査）。Apache-2.0を適用し、由来・変更内容をソース先頭に記載する。

## 分離した旧製品資産のライセンス記録

旧 Pico SDK import（BSD-3-Clause）、Meta Piano由来のCC0音声、美咲フォントとその許諾表示を含む旧ソフトウェアは、Kagura-9 の固定コミット f562b2ec84605860fdb9f701f5b2e197b5ed4432 に保存されています。移管先では元の表記とライセンスを継承してください。詳細は[分離台帳](../../../docs/kagura-fb-separation.md)と[元の権利表示](https://github.com/siska-tech/kagura/blob/f562b2ec84605860fdb9f701f5b2e197b5ed4432/THIRD_PARTY.md)を参照してください。
