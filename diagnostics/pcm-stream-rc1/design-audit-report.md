# KAGURA-HD 設計監査：QSPI窓書込みとHDMI音声不連続

作成日：2026-11-08 / 範囲：read-onlyの監査、机上分析、独立テストベンチによる非侵襲シミュレーション

製品RTL、SDC、CST、Host SDK、既存bitstreamは変更していない。実機投入、Flash書込み、PR作成もしていない。新規ファイルは `diagnostics/pcm-stream-rc1/` 配下だけにある。

> **追記（同日、§14）：** 監査後、§11のT1–T3と2つの対照を実機で実施した。投入はFPGAとRP2040のSRAMだけで、Flash書込みは0回。結果は次の4点に集約される。
> - 再現には**窓の内部データ経路の活動**が必要で、QSPIパッドの活動だけでは再現しない。H2は反証。
> - パッドのエッジ数を最小にしたパターンでも強く再現する。
> - **白・黒の均一パレットでは再現しない。**
> - 最も強いパターンでも**RC1は再現しない**。
>
> これを受けて仮説の順位を更新した（§14.3）。

---

## 1. Executive Summary

**確定事項（ソース、ネットリスト、STA、シミュレーションで裏付けたもの）**

1. **A（+0.090 ns版）とB（RC1）は、合成・配置配線の設定が同じである。** 違うのはRTL 8ファイルだけ。SDC、CST、`build-fb.tcl`、`cmd.do` のオプション、`device.cfg`、`kagura_fb_config.sv` はハッシュまたは差分で一致を確認した（§2）。
2. **Q1：非ゼロの窓書込みで追加的に切り替わる回路は次の4つである。** ゼロ書込みでは、いずれも遷移数0だった。
   - QSPIパッドと入力同期FF
   - CSR書込み語 `window_write_word`（32 FF、各bitのfanoutは16）
   - **16個のSP BSRAMすべてのDI入力（512 bit）**。書込みenable（WRE）は対象の1語だけで、one-hotを確認済み。
   - `memory_ctrl.tx`（512 FF）。IDLE中は毎サイクル `upload_data` を取り込み、`tx[15:0]` はPSRAM DQのODDR入力へ直結している（OE=0）。

   この活動量はAとBで**完全に同じ**だった（§4、`window-{A,B}.log`）。
3. **Q2：音声への論理経路は見つからなかった。** PSRAM WRITEを伴わない条件では、窓データからHDMI Audio Sample Packet（ASP）／ACR／InfoFrameへ届く論理経路はない。RGBもパケットの選択や内容に入らない。
   - 2フレーム（2,475,000 pixelサイクル）のRTLシミュレーションで確認した。6種類のRGBパターンすべてで、ASPの内容と順序、Data IslandのTERC4シンボルが一致した。
   - **AとBは、パケット列（SHA-256一致）と全TMDSシンボル列（直列化前、サイクル単位のFNV-64一致）が同一だった**（§5、§6）。
4. **試験 `x`（従来PCM2＋窓書込み、ストリーム未arm）の条件では、AのRTL差分はすべてBと論理等価になる。** ストリーム機能は `streaming=0` で無効化され、レジスタ化の3変更は等価性アサーション付きのシミュレーションでPASSしている（§7）。したがって、**AとBで再現性が分かれた理由を、RTLの論理差で説明できる箇所は見つかっていない。**
5. **AとBの配置は大きく違う。** 報告経路上のセルを見る限り、AではHDMIのpacket/TMDSロジックと音声FIFOがTMDSピン側（上端、行2–13）へ寄っている。Bでは行15–23付近にある。また、Aの窓RAM `upload_words[4]` は `BSRAM_R10[8]` にあり、AのHDMIロジック群の近くに位置する。
6. **タイミング余裕も大きく違う。** AではHDMI pixel74ドメインの動作中の経路で余裕が小さい：
   - `tmds_gen[0]` は 0.272 ns（Bは0.659 ns）
   - InfoFrameスケジューラのCEは 0.622 ns / 1.019 ns

   なお、WNS +0.090 nsの経路はpalette CDCで、試験中は静的なため、今回の現象には関与しにくい（§8）。

**最ももっともらしい説明（未実証）**

FPGAの論理は正しいと考えられる。そのうえで、**A固有の配置・タイミング余裕**と、**データ依存のスイッチング活動**（窓RAM、`tx`、QSPIパッド、TMDSの直列エッジ密度）が物理的に重なっていると見るのが最も妥当である。その結果、HDMIリンクまたは受信器側でパケットが破損し、受信器が音声をミュートまたは補間している可能性が高い。

左右同時に10–80 msの低RMS区間が出る、という症状は、FPGA内部でのサンプル欠落よりも、受信器の誤り検出によるミュートとよく合う。FPGA内部で無音を出す経路（stop、underrun、FIFO underflow、mute）はどれもフラグを立てるが、そのフラグは0だった。

**ただし、物理原因（電源、GND、SSO、ジッタ、受信器）は一つも実測されていない。** 採用判定は保留とする（§13）。

**Q3（最も効率的な切り分け）**

Host側の変更だけで実施できる3つのA/B試験を先に行う（§11 T1–T3）：

- **T1：** QSPIパターン `0x55` と `0x0F` の比較。内部の遷移数をほぼ同じにしたまま、パッドのエッジ数だけを変える。
- **T2：** 白パレット。黒よりTMDSの直列エッジが少ない。
- **T3：** 非ゼロデータの書込み先を、窓ではなくstaging register（addr 8–23）に変える。

次に、**T4（別の受信器、またはHDMIプロトコルアナライザ）**で、FPGAの送出と受信側のどちらで乱れるかを分ける。

---

## 2. 監査対象のソース・bitstream・SHA-256対応

| 対象 | bitstream | SHA-256 | 照合 |
|---|---|---|---|
| A：PCMストリーミング試作 | `build/pcm-stream-rc1/sta-short-control/native/impl/pnr/kagura_fb.fs` | `de71d3fb2f45f2f119413659ef199ad72569bd8a74c6c1b68ad5ae44f119cbcb` | 指定ハッシュと一致 |
| B：デグリッチRC1 | `build/queue8-deglitch-release/native/impl/pnr/kagura_fb.fs` | `1f4aeec6f87cc6a8e795f8712047c335fe355045b74639454398a7acfd3ce46f` | `releases/queue8-qspi-deglitch-rc1/manifest.json:8` および `artifacts/experimental/queue8-qspi-deglitch-rc1/kagura-hd-qspi-queue8-cs-deglitch-rc1.fs` と一致 |

**ビルド入力の照合**（`design-audit/identity.json`、`collect.py`）：

- `releases/queue8-qspi-deglitch-rc1/build-inputs/` の41ファイルは、`source-input-manifest.json` と全件一致した。また、Bビルドの `inputs/` とも全件一致した。
- A（`build/pcm-stream-rc1/sta-short-control/inputs/`）は、41ファイルのうち33ファイルがRC1と同一だった。**相違は次の8ファイル**（差分は `design-audit/inputs-diff.patch`）：
  `boards/tang-nano-9k/kagura_fb_top.sv`、`rtl/audio/kagura_pcm_control.sv`、`rtl/audio/kagura_pcm_prefetch.sv`、`rtl/fb/kagura_fb_audio_endpoint.sv`、`rtl/fb/kagura_fb_burst_ctrl.sv`、`rtl/fb/kagura_fb_core.sv`、`rtl/fb/kagura_fb_registers.sv`、`rtl/hdmi/kagura_packet_assembler.sv`
- SDC（`169c6026…`）、`host.cst`、`phase1.cst`、`build-fb.tcl`、生成済みの `kagura_hdmi_stream.sv` は、AとBで同一。
- ネイティブの `kagura_fb.cst`（`77ef83cf…`）、`device.cfg`（`245d2339…`）、`kagura_fb_config.sv`（`4b904c7d…`：HOST_LANES=4、GPU_QUEUE_DEPTH=8、GPU_AUDIO_CREDITS=0、GPU_PACKET_FIRST=1）は、AとBで同一。
- `cmd.do`（PnR）と `kagura_fb.prj`（合成）は、パス文字列だけが異なる。どちらも `-place_option 4 -route_option 2 -route_maxfan 23 -correct_hold 1 -retiming_resource none -clock_route_order 0 -global_freq 50` である。Gowinのバージョンは V1.9.12.04。
- ネットリスト：A `kagura_fb.vg` は `81c66e4f…`、B は `06b927da…`。STA HTML：A `a13f3de8…`、B `8ce5280e…`。

**未確認として残すもの**

- 実機試験で使ったHost ELFの入力ソース。成果物のハッシュは `design-audit/evidence-hashes.json` に記録したが、そのELFをビルドしたソースのハッシュは記録されていない。
- `frame.hex` と `palette.hex` は現行の `software/beyond16/generated/assets.inc`（`18dfaff3…`）から作った。試験時の画面と同一かどうかは未証明（`fixture.json`）。
- 作業ツリーとmainは比較に使っていない。

---

## 3. 再現条件と実機で確定した事実

出典：`hardware-host/blit-audio-isolation.md`。証跡は `build/pcm-stream-rc1/stream-traffic-*`、`stream-match-*`、`stream-host-hardware-control-*`。ハッシュは `design-audit/evidence-hashes.json`。

| 25秒条件 | A 低RMS L/R | B 低RMS L/R |
|---|---:|---:|
| `c` 従来PCM2のみ | 0 / 0 | 0 / 0 |
| `u` ストリーム補充 | 6 / 6 | – |
| `v` 所有権の再公開のみ（データ書込みなし） | 0 / 0 | – |
| `w` 従来PCM2＋別のPSRAM領域へのWRITE | 6 / 6 | 0 / 0 |
| `x` 従来PCM2＋QSPI窓への非ゼロ書込み（PSRAM命令なし） | 10 / 8、再試験 10 / 10 | 0 / 0 |
| `z` 従来PCM2＋QSPI窓へのゼロ書込み | 0 / 0 | 未実施 |
| `n` 元配色・描画なし | 6 / 6、再試験 8 / 8 | – |
| `k` 同じ画面を黒パレットで表示 | 0 / 0 | – |

**実機で確定している事実**

- `x` と `z` は、書込み量、ペーシング（5 MHz、1チャンク237 µs、1バッチ最大30,352 µs）、Host ELFが同一である。
- 通信timeout、E1（underflow、overflow、mute）、PCM異常フラグは全回0だった。
- 低RMS区間は左右同時に発生する。
- 再現するのは「A」×「切り替わる書込みデータ」×「非黒の表示」の組合せだけである。

**監査で注意した点**

E1が0であることは、HDMI送出が正常であることの証明にならない。E1が観測するのは system54側のFIFO underflow/overflowとmuteだけである（`rtl/fb/kagura_fb_audio_endpoint.sv:60`）。パケットのBCH、TMDSの誤り、受信器のミュートは観測していない。

---

## 4. QSPI → Upload RAM のデータフロー

**1) パッドと同期**（`rtl/bus/kagura_spi_adapter.sv:51-52, 101-103`、AとB同一）

`host_sck`、`host_cs_n`、`host_io[3:0]` は、system54の2段FF（`sck_sync`、`cs_sync`、`io_sync0/1`、`ASYNC_REG`）でオーバーサンプリングしている。SCKはクロックとして使わず、`rise=active && !cs_q && sck_sync[1] && !sck_q`（`:74`）で検出する。

データは同期後の `io_sync1` を、SCKの立上り検出と同時に取り込む。5 MHzのSCKに対して、system54は約10.8倍のオーバーサンプリングになる。

**2) CSR要求** → `kagura_fb_host.sv:85-87`

`req_addr` でbase、cursor、audioへ振り分け、`base_addr`、`base_data`、`base_write` を登録する。

**3) 窓書込み**（`rtl/fb/kagura_fb_registers.sv`、Aの行番号）

- `req_addr==24` を受理すると（`:149-153`）、次の処理が行われる。
  - `cpu_write_word`（`:86-91`）を `window_write_word` へ登録する。これは、選択中の64 bitグループから旧値の32 bit語を取り出し、対象バイトだけを `req_wdata` に置き換えたもの。
  - `window_write_addr`、`window_pending=1`、`window_write=1`、`port_ready=0` を立て、`data_addr` を+1する。
  - 8バイトごとに `upload_group_select` を回転させる。
- `byte_commit=window_pending && window_write`（`:76`）。
- 書込みenable：`cpu_write=byte_commit && window_write_addr[5:2]==word_index`（`:118`）、`writing=reset||bulk_capture||cpu_write`（`:119`）。**16語のうち1語だけ**が書き込まれる。TBで `$onehot0(we)` を確認した。
- **データ選択（`:121`）：** A は `(reset || local_window_select[word_index/2]) ? reset_or_window_word : cmd_read_data[...]`、B は `select_window_word ? ... : ...`（`release …/kagura_fb_registers.sv:99, 106`）。
  - いずれの場合も、byte_commitの1サイクルだけ、**16語すべてのDIが `cmd_read_data` から `window_write_word` に切り替わり**、次のサイクルで戻る。
  - Aでは選択信号を8個のFF `window_select[g].select_cpu` に複製している（`:104-115`、syn_keep）。ネットリスト上のfanoutは各64（`design-audit/fanout.json`）。
- `window_write_word[n]` のfanoutは、AとBともに16（16個のSP DIマージ）。
- RAM本体は `kagura_fb_upload_word.sv:33-35`。SPの32 bit、`WRE=write`、`AD=14'h000f` 固定。

**4) 書込み対象外への伝播**

`upload_data`（512 bit、SPのDO）は、書き込まれた語だけが変わる。消費先は次の3つ：

- (a) `selected_upload_group`（`:80-85`、64 bitのAND-OR MUX）
- (b) `kagura_fb_commands.sv:182-189` の `host_wdata`。`select_fill=0` のとき `upload_data` をそのまま通す。
- (c) `kagura_fb_core.sv:75` の `req_wdata={3{host_wdata}}` → `kagura_fb_arbiter.sv:49` の `wdata=req_wdata[owner]` → `memory_ctrl`（burst_ctrl）の `wdata`。

**5) PSRAM WRITEを発行しなくても動く回路**

- A では `kagura_fb_burst_ctrl.sv:76-99`。`tx_load` は `state==IDLE && !valid` などを1サイクル前に登録したもので、`if(tx_load) tx<=wdata`。B では `release …/kagura_fb_burst_ctrl.sv:141` の IDLE 内で `tx<=wdata`。
  - **どちらも、IDLEの間は毎サイクル512 bitの `tx` が `upload_data` を追従する。** fanoutは A の `tx_load_s0.Q` が562、B の LUT `tx_495_s4.F` が576。
- `phy_dq_o_{rise,fall}={tx[7:0],tx[15:8]}`（ca_phaseでもconfiguringでもないとき、`:136-137`）。つまり窓の0–1バイト目は、PSRAM DQのODDR入力を直接切り替える。
  - `phy_dq_oe` は `ca_phase || (data_phase && writing)` のときだけ1（`:134`）なので、パッドは駆動しない。

**6) CPU窓書込みとREAD/COPY取込みの排他**

- 窓書込みの受理には `!busy && (!queued || queue_count==0)` が必要（`:101-102, 144`）。
- 書込み中は `port_ready=0` で次の要求を止める（`:132-133`）。
- `bulk_capture=cmd_read_result && executing` は、キューが空でないと発生しない。
- この排他はA/Bで同じで、Aのアサーション `select_cpu==byte_commit`（`:111-113`）でも確認している。

**7) 活動量の比較（独立TB `design-audit/tb_window_activity.sv`）**

条件：保存済みのA/B入力RTLを使い、1024回の書込みを各30サイクル間隔で実行。`cmd_read_data=0`。PSRAMへの要求はない。

| パターン | DI512 遷移 | upload_data 遷移 | idle `tx` 遷移 |
|---|---:|---:|---:|
| 0x00 | 0 | 0 | 0 |
| 0xFF | 1,024,000 | 512 | 512 |
| 0x55 | 512,000 | 256 | 256 |
| 0xAA | 512,000 | 256 | 256 |
| 0x00/0xFF交互 | 507,904 | 256 | 256 |
| 疑似乱数 | 508,064 | 4,125 | 4,125 |

- **AとBの結果は全行で同一**だった（`window-A.log` `97a26f5f…`、`window-B.log` `14d8079c…`）。
- 1回のcommitあたり、平均で約500–1000 bitのDIが一斉に遷移する。これは書込みデータそのものの変化（8 bit）に比べて非常に大きい。ただし、**この構造はBにも同じように存在し、Bは再現しない。** したがって、これだけで不連続の原因とは言えない。
- 実機では `cmd_read_data` は直前のREAD/COPYで取り込んだ値を保持している。試験 `x` ではREADを発行しないため、その内容は未確認。DIの遷移数は `cmd_read_data` と書込みデータのハミング距離で決まる。

---

## 5. PCM → HDMI Audio のデータフロー

**1) PSRAMからPCMサンプルまで**

- `kagura_pcm_prefetch`（`core.sv` の `prefetch`、STREAM=1）は、PSRAMのread応答 `mem_rsp_data` からサンプルFIFOへpushする。
- `sample_tick` でpopして `sample0/1` を作る。この経路は `upload_data` や `tx` と論理的に独立している。

**2) system54 → pixel74**（`kagura_audio_transport.sv:91-96` → `rtl/memory/kagura_async_fifo.sv`）

- 深さ16（ADDR_BITS=4、PTR=5）。
- Grayポインタ `wg` は登録値（`:45`）。2段同期 `wg_sync1/2`（`:24, 69`）を経て `visible_wb=gray_to_binary(wg_sync2)`（`:70`）。
- `underflow=fifo_underflow||starved`（`transport:96`）。underflow時は無音を出し、stickyフラグを立てる（`:5`、`:104`）。

**3) パケット生成**（`build/generated/kagura_hdmi_stream.sv`）

- Data Islandの期間は、画面座標 `cx`、`cy` と `num_packets_alongside` だけで決まる（`:282-309`）。
- モードは `mode <= data_island_guard ? 4 : data_island_period ? 3 : video_guard ? 2 : video_data_period ? 1 : 0`（`:339`）。
- `kagura_audio_packets` はACR、ASP、Audio InfoFrame（`audio_sent`）、AVI、SPDを優先順に選ぶ。`audio_sent`、`spd_sent` はフレーム終端でクリアする（`kagura_audio_packets.sv:57-83`）。
- `kagura_packet_assembler` がBCHを付加し、TERC4へ渡す。

**4) RGBの関与**

`rgb` は `kagura_hdmi_stream_eval.sv:40, 49` でTMDSエンコーダの映像入力に入るだけである。パケット選択、FIFOのready、サンプル取得のどれにも接続していない（コード上で確認）。

**5) 論理等価性の検証**（独立TB `design-audit/tb_hdmi_activity.sv`、`run-hdmi.sh`）

条件：A/Bそれぞれの保存入力。VIC 4、`PACKET_REPLICATE_FIRST=1`。共通の48 kHz分数tickと単調増加PCMで2フレーム。

- 6種類のRGB（黒、白、赤、緑、青、元配色）を並列に入力し、全サイクルで `header`、`sub[0..3]`、`packet_data`、`sample_ready` が一致した。
- Data Island中のTERC4シンボル（480,000 symbol）も全一致。
- ASPのサブパケットが、受理順のPCMと完全に一致することを確認した（accepted 1599 / consumed 1596 / ASP 399 / ACR 34。残り3サンプルは終了時点で送出待ち）。
- **A/Bの比較：** パケット転写 `packets-A.txt` と `packets-B.txt` は15,000行で、SHA-256 `8a816867…` が一致。パターンごとの全TMDSシンボル列のFNV-64も、6パターンすべてで一致した（例：元配色 `d83420c16eafb6eb`）。つまり、Aの `first_local` 変更（`kagura_packet_assembler.sv:39-44`）は、サイクル単位でBと等価である。

**6) FIFOフラグが0でも検出できない音声異常**

- 物理的な原因（タイミング違反、ノイズ）でpixel74のパケットレジスタが反転すると、BCHの不一致、InfoFrameの欠落、ASPの破損が起き得る。**これらはE1に現れない。**
- Grayバスのskewが同期周期を超えると、`visible_wb` が一時的に誤った値になり得る。その場合、超過や不足が連続しなければフラグは立たない。
- 受信器側でのBCH棄却やミュートも、FPGAからは観測できない。

**この監査で検証していないもの**

- 実装ネットリストのゲートレベルシミュレーション（SDF付き）。
- `kagura_audio_transport` とasync FIFOのCDC（TBではsampleを直接入力した）。
- `serializer`（スタブ化）と、OSER10からパッドまでの経路。

---

## 6. RGB → HDMI TMDS のデータフロー

経路は次のとおり：line fetch（PSRAM）→ line banks → `display` scanout → `palette`（pixel74、`held_palette` からのCDC）→ 4bit indexからRGB24 → `tmds_channel`（8b/10b、DCバランス）→ `serializer`（OSER10、serial371）→ `tmds_*` LVCMOS33D（DRIVE=8）。

**TMDS活動量**（同じTB、2フレーム）：

| RGB | RGB24 遷移 | 並列TMDS30 遷移 | 直列化後エッジ |
|---|---:|---:|---:|
| 黒 | 0 | 44,522,215 | 23,249,672 |
| 白 | 69,120 | 42,920,935 | **18,514,952** |
| 赤 | 23,040 | 43,986,535 | 21,671,432 |
| 緑 | 23,040 | 43,992,295 | 21,671,432 |
| 青 | 23,040 | 43,986,535 | 21,671,432 |
| 元配色 | 347,760 | **25,045,895** | **29,150,600** |

読み取れること：

- 元配色は黒と比べて、**直列エッジが+25%**、**並列レジスタの遷移が−44%**だった。FPGA内部のエンコーダレジスタの活動量だけで考えると、非黒の方がむしろ静かになる。
- 白は黒よりも直列エッジが少ない。**白パレットで再現しなければ、物理リンクのエッジ密度が効いていると考えられる。白でも再現すれば、エッジ密度以外の内容依存性が残る**（§11 T2）。
- 直列エッジ数はOSER10の入力ビット列から数えた論理値である。パッドでの実際の遷移、アイパターン、ジッタは未測定。

---

## 7. RC1との差分分析

**資源の差分**（`design-audit/resource-delta.txt`）：

- 全体：Register 5400→5435（+35）、LUT 6756→6925（+169）、ALU 882→945（+63）。CLSはユーザー記録で 4212→4265。BSRAMは23で不変。

| 分類 | 変更（Aのファイル:行） | FF/LUT | fanoutと主要MUX | 試験 `x` での論理 | HDMI音声への直接依存 | 物理的な可能性 |
|---|---|---|---|---|---|---|
| 所有権管理（E3–E5） | `kagura_fb_audio_endpoint.sv`、`kagura_fb_top.sv`、`core.sv` | endpoint +10 FF、+27 LUT | 8 bit `stream_data` | E3/E4を書かなければ不活性 | なし | 小 |
| PSRAM prefetch / PCM制御 | `kagura_pcm_prefetch.sv:86-160ほか`、`kagura_pcm_control.sv` | prefetch +19 FF、+58 ALU、+125 LUT。pcm_control +4 LUT | `need*`、`pop*`、`push*`、`mem_req_valid` へゲートを追加 | `streaming=0`、`stream_clear=0` で元の式に縮退。範囲チェック用の比較器（22 bit×3×2）は毎サイクル動く | system54側でサンプル供給を変え得る（streaming時のみ） | 配置が大きく変わった主因の可能性（ロジック増加） |
| TXロード/シフトの登録化 | `kagura_fb_burst_ctrl.sv:74-99` | +2 FF | `tx_load` 1本で fanout 562 | 等価。`tx_load==(state==IDLE)` をアサート（`:219-221`） | なし | 512 FFのクロックイネーブル分配が変わった。活動量はB（IDLEデコード、fanout 576）と同じ |
| 512 bit窓の選択 | `kagura_fb_registers.sv:101-121` | +8 FF（syn_keep） | 8×64 | 等価（`:111-113`） | なし | DI選択が8つのローカルFFに分散。DIの遷移量はA/B同一（§4） |
| HDMIパケット開始判定の短縮 | `kagura_packet_assembler.sv:39-44` | packet_assembler −5 FF | 5 lane | A/Bでパケット列とTMDS列がサイクル単位で一致（§5） | 論理影響なし（検証済み） | pixel74ロジックの配置が変わった |
| PSRAMアドレス加算の短縮 | `kagura_fb_burst_ctrl.sv:49-54, 190-191` | +1 FF、+6 ALU | `cursor_upper_carry` | 等価（`:216-218`） | なし | 小 |

**PCM2回帰と等価性の既存記録**

`build/pcm-stream-rc1/sta-short-control/` の各ログで次のPASSを確認した。いずれもAの入力によるもの。

- `board.log`：PCM2 board LANES=4、Host upload/readback、ステレオオラクル。
- `burst.log`：burst_ctrlのランダムmasked write。
- `packet-{1,19,73}.log`：hdl-util参照との一致。各約28,000パケット。

**意図しない機能差の候補**：試験 `x` の条件では見つからなかった。ストリーム時の `stereo_starved`（`prefetch:146`）は両chを同時に停止し、underrunフラグを立てる。これは無音を作り得るが、フラグに現れるため、今回の観測（PCM異常0）と矛盾する。

**論理と物理の切り分け**

- 試験 `x` でA/Bを分ける**論理的な因果は見つからない**。
- 残る差は、配置配線、タイミング余裕、局所的な電源分布という**物理的な可能性**だけである。

---

## 8. クロック・CDC・STA制約の監査

**クロック**（SDC、AとB同一）

- `clk27`（37.037 ns）
- `serial371`（×55/4 = 371.25 MHz）
- `pixel74`（serial371の÷5）
- `system54`（×2）
- `psram54`（×2、+67.5°）

| 項目 | 結果 | 根拠 |
|---|---|---|
| QSPI入力の同期 | 2FFでオーバーサンプリング。入出力は `set_false_path` | `spi_adapter.sv:51-52`、SDCの最終2行 |
| PCM FIFOのGray同期 | 登録したGrayを2段同期。MSBはGrayとbinaryが同値のため、合成で `wb_4` と `wg_4` が統合されている。これは正常（STA endpoint `fifo/wb_4_s1/Q → wg_sync1_4_s0/D`） | `async_fifo.sv:34-46, 67-72` |
| system54 ↔ pixel74 | 双方向に `set_max_delay 10.000` と hold false path。クラス別の制約はない | SDC |
| Grayバスのskew制約 | なし。10 nsのmax_delayで各bitの上限だけを抑えている。報告経路のdata delayは3.4–4.3 ns | A-timing #5、B #21 |
| palette、PRESENT、cursor | 保持データとトグル/ACKで受け渡す。palette CDCは試験中は静的 | A #1、#2、#4 |
| 非同期入力からクロック/reset/enable | `reset_n` はfalse path。`host_sck` はGCLKT_4ピンにあるが、データとしてサンプルしており、クロックには使っていない | rpt `host_sck 35/2 GCLKT_4` |
| 外部I/O | `set_input_delay` / `set_output_delay` はない。PSRAM DDR、HDMI出力、QSPIのパッドタイミングはSTAの対象外 | SDC |

**STAで保証されている範囲**

- 内部のreg-to-reg経路。setupは Slow 1.14 V / 85 °C、holdは Fast 1.26 V / 0 °C で評価。35,869経路、16,318 endpoint。
- CDCは10 nsの上限についてだけ保証している。

**STAで保証されていない範囲**

- 外部I/Oのタイミング。
- CDCの構造的な正しさ。専用CDCツールでの網羅検証は未実施。
- PLLとOSERのジッタ。
- SSO、IR drop、クロストーク。
- 実際の電圧と温度。

**A/Bの余裕の比較（setup）**：

| endpoint | A | B | 試験中に動くか |
|---|---:|---:|---|
| `display/held_palette_181 → palette_181`（CDC） | **0.090** | 上位25外 | 静的（PALETTEなし） |
| `tmds_gen[0]/mode2_0 → tmds_2` | **0.272** | 0.659 | 毎ピクセル |
| `audio_link/fifo/wb_4 → wg_sync1_4`（CDC） | 0.502 | 上位25外（`wg_1` で1.464） | 毎サンプル |
| `protocol/cx_3 → display/scan_addr_1/2` | 0.541 | 上位25外 | 毎ライン |
| `protocol/cx_6 → audio_packets/spd_sent CE` | **0.622** | 上位25外 | 毎フレーム |
| `protocol/cx_6 → audio_packets/audio_sent CE` | 1.019 | 1.128（cx_5） | 毎フレーム |
| `memory_ctrl/tx_load → tx_423` | 1.001 | 上位25外 | IDLE中は毎サイクル |
| `upload_words[4].ram/DO[22] → window_write_word_22` | 1.057 | 上位25外 | 窓書込み時 |

- Setup WNS +0.090 nsの経路は、試験中に値が変わらない。したがって、**+0.090 nsそのものが今回の直接原因である可能性は低い**。
- 問題になるとすれば、**動作中の pixel74 経路**の余裕である。AではTMDS ch0とInfoFrameスケジューラが0.3–1.0 nsで、Bより小さい。
- Audio InfoFrame（`audio_sent`）の欠落や破損は、受信器によっては一時的な音声ミュートを引き起こし得る（未検証の仮説）。
- STAの値はslow cornerで正の値である。データ依存の電源降下でこの余裕を超えるかどうかは、実測しない限り分からない。

---

## 9. 物理配置・I/Oバンク・スイッチング活動の評価

**I/Oバンク**（`kagura_fb.rpt.txt` §4、§7。AとB同一）：

| バンク | 信号 | VCCIO |
|---|---|---|
| bank 1（IOT/IOR） | `tmds_d_p/n[0..2]` = IOT41/39/38、`tmds_clk_p/n` = IOT42（ピン68–75、LVCMOS33D、DRIVE=8）、**`clk27` 入力 = ピン52 IOR17（GCLKT_3、PLLの基準）**、`host_irq_n` = ピン49 | 3.3 V |
| bank 2（IOB） | `host_sck` 35、`host_cs_n` 42、`host_io[0..3]` 28/29/30/33、`host_busy` 26、`host_ready` 27 | 3.3 V |
| bank 3（IOL、パッケージ内） | PSRAM 2ダイ分の DQ[15:0]、RWDS、CK、CS、RESET | 1.8 V |

- QSPIとHDMIは**別のI/Oバンク**にある。HDMIの8本の擬似差動出力は、**27 MHzのPLL基準入力と同じバンク1**にある。この点はAとBで共通。
- 基板の回路図、VCCIOとコア電源の共有関係、デカップリングは、リポジトリ内に資料がなく**未照合**。公式資料（Tang Nano 9K回路図、GW1NR-9のデータシート UG/DS）との照合は今後の作業として残す。

**配置**（`design-audit/placement-from-sta.json`、`placement.py`）

- `.db` はバイナリで、全セルの配置はない。STA詳細に出たセルの座標だけを抽出した。標本数が少ないので、傾向の参考に留める。

| 群 | A 行範囲 / 重心（行,列） | B 行範囲 / 重心 |
|---|---|---|
| TMDS ch0 | 5–20 / (13.5, 39.7) | 2–25 / (14.9, 36.2) |
| TMDS ch1/ch2 | 6–16 / (9.7–9.8, 41) | 15–27 / (21.7–22, 41) |
| audio_packets | 5–7 / (6.0, 35.3) | 20–21 / (20.2, 31.5) |
| packet_assembler | 13 / (13, 33) | 23 / (23, 30) |
| audio FIFO | 2–18 / (4.7, 43.1) | 4–23 / (18.6, 41.9) |
| palette / held_palette | 11–27 / 列17–29 | 13–23 / 列3–11 |
| 窓RAM | `upload_words[4]` = `BSRAM_R10[8]` | 不明 |

- Aでは、HDMI pixel74のロジックと音声FIFOが、上端のTMDS出力ピン（IOT38–42）と右上のPLL基準（IOR17）の近くに集まっている。また、BSRAM行R10に置かれた窓RAMの少なくとも1個と、同じ領域を共有している。Bではこの群が下に約10行ずれている。
- これは物理的に近いという事実であり、結合したことの証拠ではない。

**同時スイッチングの大きい群（論理的な遷移数）**

- 窓commit時の512 bit DI（各commit 1サイクル）。
- `tx` の512 FFと、その上位レジスタ。
- 窓の0–1バイト目に連動するPSRAM ODDRのD入力（OE=0、パッドは駆動しない）。
- QSPIの4本のデータ線（5 MHz、nibble単位）。
- TMDSの8本（371.25 Mbps×3ch＋クロック）。

電源ノイズ、GNDバウンス、クロストーク、アイ品質、ジッタは**どれも実測していない**。すべて仮説として扱う。

---

## 10. 仮説ごとの証拠と反証

| 仮説 | 支持する証拠 | 反証・矛盾 | 未観測 | 区別できる最小の試験 | 修正の対象範囲 |
|---|---|---|---|---|---|
| **H1** QSPI窓RAMの内部切替え | 非ゼロ時だけDI512、`tx`512、ODDR Dが動く（ゼロでは0）。窓RAMがAのHDMIロジックに近い | 同じ活動がBにもあり、Bは再現しない。単独では説明できない | 実機の電源波形 | **T3**（非窓レジスタへの非ゼロ書込み）、**T1** | `kagura_fb_registers.sv:121`、`burst_ctrl.sv:85-92` |
| **H2** QSPI入力の電気的影響 | パッドのトグルはデータ値に依存し、ゼロでは静か | HDMIとは別バンク。BとCSTは同一 | 基板の共通インピーダンス、Host側の波形 | **T1**（`0x55` 対 `0x0F`）、T3 | 基板、ドライブ設定、Host PIO |
| **H3** クロック/CDCの異常 | Aの音声FIFO Gray経路は余裕0.502 ns（10 nsの上限に対して） | Gray＋2FFの構造は正しい。上限はskew要件より厳しい。症状が左右同時の長い無音で、CDCの誤りと合いにくい | ゲートレベルのCDC検証 | T4の結果で受信側を除外した後、内部監視（D-3） | SDCのクラス別制約、FIFO |
| **H4** パケット生成の論理異常 | なし | RTLでA=B、RGB非依存、ASPの順序一致をサイクル単位で確認（§5）。**論理としては反証済み**。物理的な誤動作（タイミング超過）は残る | 実装ネットリストのSDFシミュレーション | D-3の内部監視、T5（再配置） | `kagura_audio_packets`、`packet_assembler` の配置とタイミング |
| **H5** TMDS信号品質の悪化 | 黒では再現せず元配色で再現（直列エッジ+25%）。PLL基準がTMDSと同じバンク。Aの配置がTMDSピン側に寄っている | RC1は同じピン、同じTMDS列（論理同一）で再現しない。単独では説明できない | アイパターン、ジッタ、パケット誤り数 | **T2**（白）、**T4**（アナライザ、別受信器） | IO設定、配置制約、基板 |
| **H6** 受信・キャプチャ側 | 左右同時のミュート状の区間は、受信器の誤り隠蔽と合う | B×同じHost×同じ受信器では0。受信器だけの問題なら画像に依存しない | 受信器の誤りカウンタ | **T4** | なし（受信器の限界とH5の組合せ） |

**順位（もっともらしさ。実証ではない）**

1. **H5＋H6の複合**：A固有の物理条件でリンク品質が下がり、受信器がミュートする。
2. **H4の物理版**：Aの小さい余裕と、データ依存のノイズによるpixel74経路の誤動作。
3. **H1**（ノイズ源として）。
4. **H2**。
5. **H3**。
6. **H4の論理版**（RTLとしては反証済み）。

H1とH2は「何がノイズ源か」、H4の物理版、H5、H6は「どこで壊れるか」の候補であり、互いに排他ではない。

---

## 11. 次に実施すべき最小A/B試験

いずれも既存のSRAM投入手順と25秒条件で行う。T1–T3はFPGA画像をA（`DE71…`）のまま、**Hostのデータだけ**を変える。FPGA/RP2040のFlash書込みは不要。

| # | 内容 | 判定 |
|---|---|---|
| **T1** | `x` と同じ量、ペーシング、書込み先で、データを `0x55` 固定にした場合と `0x0F` 固定にした場合を比べる。adapterはMSB先頭のnibble転送（`spi_adapter.sv:4`）なので、`0x55` は各laneが一定でパッドのエッジがほぼ0、`0x0F` は毎nibbleで4 laneがトグルする。内部DIの1の数は同じ（4/byte） | `0x0F` だけで再現：H2が優勢。両方で再現：H1が優勢。両方で再現しない：データ遷移の内容依存性を再検討 |
| **T2** | `n` / `x` 条件で、パレットを**白**（必要なら赤も）にする | 白（直列エッジは黒より少ない）で再現しない：エッジ密度（H5）。白で再現：エッジ密度以外 |
| **T3** | 非ゼロの同じバイト列を、窓（addr 24）ではなくstaging register（addr 8–23、submitなし）へ書く。パッドの活動は同じで、窓RAM、DI512、`tx` は動かない | 再現しない：H1。再現する：H2またはパッド起点 |
| **T4** | A×`x`（再現条件）とB×`x` を、**別の受信器**、または**HDMIプロトコルアナライザ**（BCHとTERC4の誤り数、ASPの連続性）で記録する | 送出側でパケット列が正しく、誤りもない：H6。誤りがありAだけ：H5またはH4物理版 |
| T5 | A RTLのまま、P&Rのseedやplace_optionを変えて**STA違反0**の別配置を作り、`x` を試す。既存の変種（`sta-p3`、`sta-p4-r0`、palette系）は全て違反あり、`f24` は同一配置相当のため使えない | 配置で結果が変われば物理原因が確定に近づく |

推奨する順序は T1 → T3 → T2 → T4。T1–T3は機材を追加せずに1日以内で実施できる。T4は機材の手配が必要になる。

---

## 12. 最小修正候補と副作用（実装していない、仮説段階）

| 候補 | 内容 | 期待される効果 | 副作用・リスク |
|---|---|---|---|
| D-1 | 窓commit時のDI選択を、対象語だけに局所化する（`registers.sv:121` で `local_window_select` を語単位の `cpu_write` に置き換える）か、非書込みサイクルでDIを前値に保持する | DI512の遷移が約1/16になる | 選択信号のデコードがタイミング経路に戻る。RC1で広域選択にした理由（STA）と衝突する |
| D-2 | `tx` を要求の受理時だけロードする（IDLEでの追従をやめる） | 512 FFの遷移が窓書込みと連動しなくなる | COPYが「ライブの窓」を参照する仕様（`commands.sv:180-181`）との整合、`tx_load` の経路 |
| D-3 | 診断ビルド：pixel74側に、ASPのサンプル連番、BCHの再計算、InfoFrameの送出数を数えるカウンタを置き、CSRで読む | FPGA内部の誤動作とリンク・受信側の問題を分けられる | 資源とタイミングを圧迫し、配置が変わって現象が消える恐れがある |
| D-4 | `phy_dq_o` を `phy_dq_oe=0` のとき0に固定する | ODDR D入力の無駄なトグルがなくなる | PSRAM PHYのタイミングを再確認する必要がある |
| D-5 | HDMI pixel74群の配置をBに近づける制約を加える、またはpixel74経路の余裕を増やす | H4物理版、H5への対処 | 他の経路の余裕を失うおそれ |
| D-6 | HDMIのIO設定（DRIVE）を見直す | H5 | 実測なしでは評価できない。リンクマージンを悪化させる可能性 |

D-1、D-2、D-4は「ノイズ源を減らす」、D-3、D-5は「壊れる場所を確かめる・強くする」ための候補である。T1–T4の結果より前に、どれかを有効な修正と決めないこと。

---

## 13. 未解決事項と採用判定への影響

**未解決事項**

- 物理層（電源、GND、SSO、ジッタ、TMDSアイ品質）の実測。
- 受信器の誤り情報。
- ゲートレベル（SDF）での等価性。
- async FIFOとserializerのシミュレーション。
- 全セルの配置。
- 基板回路図との照合。
- 試験に使ったHost ELFのソースとの対応。
- 試験時の画面データが `assets.inc` と同一であること。
- `cmd_read_data` の実機での値。

**採用判定**

**原因は確定していない。** PCMストリーミング（A）の採用は**保留**とする。

- FIFOフラグ0、STA違反0、RTLの等価性、いずれも音声の連続性を保証しない。
- T1–T4で、物理原因が「A固有の配置」なのか「設計構造」なのかを区別したうえで判断する。
- 区別の結果がA固有の配置であれば、RTLは維持し、配置またはタイミングを是正してから再試験する。区別の結果が設計構造（D-1、D-2の対象）であれば、RC1にも潜在するリスクとして扱う。

---

## 付録：本監査で作成・更新した診断ファイル

| ファイル | SHA-256 | 内容 |
|---|---|---|
| `design-audit/collect.py` | – | 入力ハッシュの照合、STAのテキスト化、ネットリスト抽出（read-only） |
| `design-audit/summarize.py` | – | 資源差分、fanout、証跡ハッシュ |
| `design-audit/placement.py` | – | STA詳細からの部分配置（本監査で追加） |
| `design-audit/tb_window_activity.sv` / `run-sim.sh` | `3ced00bf…` | 窓の活動量TB |
| `design-audit/tb_hdmi_activity.sv` / `run-hdmi.sh` | `3f635d92…` | RGB独立性とA/B TMDS等価性のTB。本監査でFNV-64を追加 |
| `window-{A,B}.log` | `97a26f5f…` / `14d8079c…` | 窓TBの結果 |
| `hdmi-{A,B}.log` | `2a8a5ffc…` / `8f95313e…` | HDMI TBの結果（再実行済み） |
| `packets-{A,B}.txt` | 両方 `8a816867…` | パケット転写 |
| `identity.json` / `inputs-diff.patch` | `fd72cc6f…` / `774d72a3…` | 照合と差分 |
| `placement-from-sta.json` | `b3c573da…` | 部分配置 |

前回のセッションで保存されていた `hdmi-{A,B}.log` は、TBを修正する前の出力（書式が不一致、`packets-*.txt` なし）だった。本監査でWSLのVerilator 5.032により再実行し、上記の値で置き換えた。

---

## 14. 実機A/B試験の結果（2026-11-08、§11 T1–T3と対照）

### 14.1 実施条件

- **FPGA：** A（`de71d3fb…`、User Code `0x00009B86`）。#08のみB（RC1 `1f4aeec6…`、`0x00007F87`）。Programmerの操作2でSRAMにだけ投入した。
- **Host：** RAM実行専用のELF `build/pcm-stream-rc1/hardware-host-audit-ab/pcm_stream_hw.elf`（`82e73846…`、LOADセグメントはSRAM内）。ソースは `hardware-host/main.c`（`f5b4c0f9…`）で、既存の `x`/`z` と同じ `run_legacy()` に、データと書込み先だけが違う5モードを追加した。
- **手順：** 前回の `stream-traffic-x/run.py` を一般化したドライバ `hardware-host/run-audit-ab.py`（`c7a5626a…`）を使った。各回の流れは次のとおり。
  1. JTAG `0x1100481B` を照合
  2. RP2040 Flash 2 MiBを読み出す
  3. SRAMへ投入し、UGREEN 15390で48 kHzステレオを録音
  4. 25秒間実行
  5. 承認済みQueue8（`0x00004068`）を復旧
  6. Flashの前後一致を照合し、常設Host（COM5）へ復帰
- **共通条件：** 従来PCM2の固定2半面ループ。292バッチ×128チャンク×64 byte、1チャンク237 µsのペーシングで `x` と同量。5 MHz QSPI。
- **解析：** `analyze-phase.py`（291半面、`--marker-cycle 2`）。前回の `stream-traffic-x` の録音を再解析すると10 / 8で、記録値と一致した。

### 14.2 結果

| # | 画像 | モード | 書込み先・データ | パッド活動 | 窓の内部活動 | 表示 | 低RMS L/R | マーカー不一致 L/R |
|---|---|---|---|---|---|---|---:|---:|
| 01 | A | `x` | 窓・PCMパターン | 中 | 中 | 元配色 | **12 / 10** | 236 / 236 |
| 02 | A | `5` (T1) | 窓・0x55/0xAAをチャンクごとに交互 | **ほぼ0**（各laneがチャンク内で一定） | **最大**（チャンクごとに全bit反転） | 元配色 | **32 / 29** | 274 / 282 |
| 03 | A | `f` (T1) | 窓・0x0F/0xF0をチャンクごとに交互 | **最大**（毎nibbleで全laneがトグル） | 最大 | 元配色 | **26 / 26** | 274 / 284 |
| 04 | A | `r` (T3) | **staging reg 8**・PCMパターン（`x` と同じバイト列） | `x` と同じ | **なし** | 元配色 | **0 / 0** | 0 / 0 |
| 05 | A | `y` (T2) | 窓・PCMパターン | `x` と同じ | `x` と同じ | **白** | **0 / 0** | 0 / 0 |
| 06 | A | `e` | 窓・PCMパターン | `x` と同じ | `x` と同じ | **黒** | **0 / 0** | 0 / 0 |
| 07 | A | `x` | 窓・PCMパターン（終盤の再確認） | 中 | 中 | 元配色 | **10 / 12** | 248 / 250 |
| 08 | **B** | `5` | 窓・0x55/0xAAをチャンクごとに交互 | ほぼ0 | 最大 | 元配色 | **0 / 0** | 0 / 0 |

- 全8回とも `STOP rc=0`、timeout 0、device_error 0、292バッチ。E1とPCM異常フラグは全サンプルで0だった（`run_legacy()` の判定）。
- Queue8の復旧とRP2040 Flashの前後一致（`c7052a32…`）も全回で確認した。
- 正常だった回は、位相ステップが最大1–2サンプルだった。
- 「窓の内部活動」はHostの送信データから見た定性的な区分である（§4のTBに基づく）。実機での遷移数は測っていない。
- 証跡は `build/pcm-stream-rc1/audit-ab/0[1-8]-*/`（`result.json`、`stream-usb.log`、`stream-audio.mka`/`.wav`、`phase-analysis.json`、各種ログ）。ハッシュは `design-audit/hardware-ab-results.json`（`ca9f9705…`）。

### 14.3 判定

**実機で確定したこと**（A、この機器構成、25秒×各1回。#01と#07は2回）：

1. **QSPIパッドの活動だけでは再現しない（H2を反証）。** #04は `x` と同じバイト列、同じペーシング、同じパッド活動で、書込み先がstaging registerだけ違う。結果は0 / 0。さらに、パッドのエッジがほぼ0の#02で、最も強く再現した。
2. **窓のデータ経路の活動が必要条件である（H1を支持）。** 内部で全bitが反転するパターン（#02、#03：26–32）は、PCMパターン（#01、#07：10–12）より明らかに悪化した。活動量と症状の強さに単調な関係が見える。このとき活動する経路は、窓RAMのDI、`upload_data`、`memory_ctrl.tx` の512 FF、PSRAM DQのODDR入力である（§4）。どれが寄与しているかは区別できていない。
3. **表示内容が必要条件である。** 内部活動が同じ `x` 条件でも、白と黒の均一パレットでは0 / 0だった。白は黒よりTMDSの直列エッジが少なく、元配色は黒より多い（§6）。これは「直列エッジ密度にしきい値がある」という解釈と矛盾しない。ただし、均一な画面と非均一な画面の違いが効いている可能性もあり、エッジ密度が原因とまでは**言えない**。
4. **A固有である。** 最も強いパターン（#02で32 / 29）でも、RC1（#08）は0 / 0だった。§5、§7のとおりAとBのRTLは論理等価で、窓の活動量も同じであることから、**AとBの違いは配置・配線・タイミング余裕の側にある**という見方が強まった。

**更新後の仮説の順位**（実証ではない）：

1. **H1（ノイズ源）× A固有の物理的感受性 × H5（TMDS内容への依存）の複合。** 窓の内部経路のスイッチングと、非均一な映像のTMDS出力が重なったときにだけ、Aの配置で音声が乱れる。§9のとおり、AではHDMI pixel74群と窓RAMが近く、pixel74の余裕も小さい。乱れる場所は、FPGA内部（pixel74経路の誤動作、H4物理版）か、リンク・受信側（H5/H6）かのどちらかで、まだ区別できていない。
2. **H6** 単独：RC1が同じ受信器で正常なので、受信器だけの問題である可能性は低い。ただし、受信側の誤り隠蔽が最終的な症状を作っている可能性は残る。
3. **H3**：変化なし（低い）。
4. **H2**：**反証**（#04、#02）。
5. **H4 論理版**：RTLとして反証済み（§5）。

### 14.4 次の最小試験（更新）

| # | 内容 | 目的 |
|---|---|---|
| T4 | #02（A、最も強い条件）と#08（B）を、**HDMIプロトコルアナライザ**か**別の受信器**で記録する。BCH/TERC4の誤り、ASPの連続性、Audio InfoFrameの欠落を見る | FPGAの送出で壊れているのか、リンク・受信側で壊れているのかを分ける |
| T6 | A、`5` パターンで、**窓の0–1バイト目だけ**を書き換える場合と、**2–63バイト目だけ**を書き換える場合を比べる。`tx[15:0]` からPSRAM ODDRに届くのは0–1バイト目だけ | ODDR/IOL3バンクの寄与と、窓RAM・`tx` のFFの寄与を分ける（Hostの変更だけで実施可能） |
| T7 | A、`x`、表示を「縦縞（2色交互）」と「元配色の半分の面積」にする | TMDSの内容依存性を、エッジ密度と非均一性に分ける（Hostの変更だけで実施可能） |
| T5 | A RTLのまま、STA違反0の別配置で#02を実施する | 配置への依存を確定させる |
| D-3 | pixel74の内部監視（診断RTL） | T4で送出側の誤りが見つかった場合に実施 |

### 14.5 採用判定への影響

再現条件は「A × 窓の内部データ活動 × 非均一な表示」まで絞り込めた。**原因の物理的な機構はまだ実証できていない**ため、採用は**保留のまま**とする。

RC1は、内部活動を最大にした今回の条件でも正常だった。ただし、窓のDI 512 bitを一斉に切り替える構造と、`tx` がIDLE中に追従する構造（D-1、D-2の対象）はRC1にも同じように存在する。配置が変われば同じ現象が起き得る潜在的なリスクとして記録する。

---

## 15. 追加の実機試験：T6、T7、一色表示のスイープ（2026-11-08）

### 15.1 条件

§14.1と同じ手順、同じドライバで実施した。投入はSRAMだけで、Flash書込みは0回。全回で、Queue8 `0x00004068` の復旧とRP2040 Flashの一致を確認した。

Host ELFはモードを追加するたびに再ビルドした。

| 実行 | ELF |
|---|---|
| #09–14 | `d7e013d0…`（`build/pcm-stream-rc1/hardware-host-audit-ab2/`） |
| #15–18 | `b4e61dd4…`（`…-audit-ab3/`） |

- 既存のモードのコードは変えていない。
- 現在の `hardware-host/main.c`（`ea8e5240…`）は全モードを含む最終版である。
- 途中のELFの元になった版のソースは、バイト単位では保存していない。差分はモードの追加だけである。

証跡は `build/pcm-stream-rc1/audit-ab/09-*`〜`18-*`、ハッシュは `design-audit/hardware-ab-results.json`（`42c709c2…`、全18回分）。

### 15.2 T6：窓のどの部分の活動が効くか

#### 実機の結果

表示は全回で元配色、画像はA。

| # | モード | Hostの窓データ | 低RMS L/R |
|---|---|---|---:|
| 09 | `x` | PCMパターン（基準） | 14 / 15 |
| 10 | `a` | 0–1バイト目だけ0x55/0xAAを交互、残りは0（`tx[15:0]` からPSRAM DQのODDRへ届く部分だけ） | **0 / 0** |
| 11 | `i` | 2–63バイト目だけ0x55/0xAAを交互、0–1バイト目は0 | **38 / 32** |
| 12 | `o` | 全バイト0x55で固定（窓の内容は1回目以降変わらない） | **25 / 25** |

#### 同じデータ列による内部遷移数

`design-audit/tb_mode_activity.sv` と `run-mode-sim.sh` で、Hostの `audit_byte()` と `sample()` が作るバイト列をそのまま保存済みRTLに入力した。2バッチ（`writes&1` の1周期）分を数え、`cmd_read_data=0` と仮定した。結果はAとBで同一である（`mode-A.log` `3812d85d…`、`mode-B.log` `1ebee280…`）。

| モード | DI512 | `window_write_word` | `upload_data` | idle `tx` | 実機 |
|---|---:|---:|---:|---:|---|
| `z` | 0 | 0 | 0 | 0 | 0 / 0 |
| `a` | 262,144 | 6,144 | 4,096 | 4,096 | 0 / 0 |
| `x` | 6,324,224 | 15,078 | 2,048 | 2,048 | 10–15 |
| `o` | 8,388,608 | **0** | **0** | **0** | 25 / 25 |
| `5` / `f` | 8,388,608 | 192,512 | 131,072 | 131,072 | 32 / 29、26 / 26 |
| `i` | 8,126,464 | 190,464 | 126,976 | 126,976 | 38 / 32 |

#### 判定（実機とシミュレーションの両方で裏付けたもの）

1. **PSRAM DQのODDRに届く経路（窓の0–1バイト目、`tx[15:0]`）の活動は不要である**（#10）。
2. **窓の内容、`upload_data`、`tx`、`window_write_word` の変化も不要である**（#12）。`o` ではこれらの遷移は0だが、強く再現した。
3. 再現の有無と一貫して対応する内部の活動は、**byte_commitごとに16個のSP BSRAMすべてのDI（512 bit）が `cmd_read_data` と `window_write_word` の間で切り替わる部分だけ**である（`kagura_fb_registers.sv:121`、Aの `window_select[g].select_cpu` は各fanout 64）。0か0.26 Mでは再現せず、6.3 M以上で再現する。
4. 書込みenableの活動（1語へのWRE）は `z` でも同じだけあり、`z` は再現しない。したがって、それだけでは十分条件にならない。

**前提**：実機での `cmd_read_data` の値は観測していない。`z` と `a` が0 / 0であることは、`cmd_read_data≈0` という仮定と矛盾しない。

**結論**：ノイズ源の候補はH1の中でも**窓RAMのDIの一斉切替え**に絞り込めた。これは§12 D-1（DIの選択を対象語だけに局所化する、または非書込み時にDIを保持する）が直接狙う箇所である。この構造はRC1にも同じように存在するが、RC1は再現しない（#08）。

### 15.3 T7と一色表示のスイープ：表示のどの性質が効くか

画像A、窓データは `x` のPCMパターン。TMDSの指標は、標準の8b/10bモデル（`design-audit/tmds-model/`、結果は `metrics.txt`）で有効表示区間について計算した。このモデルはTBの直列エッジの差分と一致することを確認している（元配色−黒：TB 3.20、モデル 3.25 edges/pixel。黒−白：両方2.57）。

| # | 表示 | 各チャネルの値 | 直列エッジ/char | 並列トグル/char | 低RMS L/R |
|---|---|---|---:|---:|---:|
| 05、18 | 白 `0xFFF` | 0xFF一定 | 1.14 | 7.71 | **0 / 0**、**0 / 0** |
| 06 | 黒 `0x000` | 0x00一定 | 2.00 | 8.00 | **0 / 0** |
| 15 | 赤 `0xF00` | R=0xFF、G=B=0x00 一定 | – | – | **0 / 0** |
| 16 | `0x111` | 0x11一定 | – | – | 8 / 9 |
| 17 | `0xEEE` | 0xEE一定 | – | – | 11 / 10 |
| 13 | 灰 `0x555` | 0x55一定 | 6.00 | 0.00 | 13 / 10 |
| 14 | 黒白の縦縞（FB 1 pixelピッチ） | 0x00と0xFFが2 pixelごとに交互 | 1.50 | 8.99 | **38 / 38** |
| 01、07、09 | 元配色 | 22種のchar | 3.08 | 4.41 | 10–15 |

#### 判定

- **TMDSの直列エッジ密度という仮説（H5の単純な形）は反証された。** 縦縞は黒よりエッジが少ないのに最も強く再現し、灰は黒の3倍のエッジでも再現の強さは中程度だった。
- **画面の均一性という仮説も反証された。** 灰、`0x111`、`0xEEE` は均一な一色表示だが再現した。
- 並列トグル数、最大ラン長、異なるcharの数のいずれも、再現する表示としない表示を分けられない。
- 今回の試験で一貫している経験則は、「**全チャネルが0x00か0xFFのどちらかで一定**の表示（黒、白、赤）だけが再現しない」というものである。0x00と0xFFが交互になる縦縞は再現する。この規則を説明する機構は**特定できていない**。

#### 考察（仮説）

- 灰 `0x555` は並列トグルが0（エンコーダの出力レジスタが変化しない）なのに再現した。したがって、TMDSエンコーダのデータ依存の内部タイミング（Aで余裕0.272 nsの `tmds_gen[0]` 経路）だけでは説明しにくい。
- 0x00と0xFFが一定のとき、TMDSは2種類の最大不均衡charを交互に出し、それ以外の一色表示は均衡charか別の系列を出す。リンクや受信器でのcharの扱い（CDR、DC、誤り検出のしやすさ）に依存する可能性があるが、実測はない。

### 15.4 更新した結論

**実機で確定**（画像A、この機器構成。各条件1–4回）：

- 再現には、(1) 窓RAM 16個へのDIの一斉切替えと、(2) 「全チャネル0x00/0xFF一定」以外の表示の、**両方**が必要である。
- QSPIパッド、PSRAMのODDR、窓の内容と `tx` の変化は、いずれも不要である。
- RC1は最も強いデータ条件でも再現しない。
- 基準条件 `x` の再現性：4回で10–15（左右とも）。0 / 0の条件は全回でマーカー不一致が0だった。

**未確定**：

- DIの切替えが音声の乱れに至る物理的な経路。候補は、電源・GNDを通じたpixel74経路の誤動作、またはTMDS出力やPLLへの結合。
- 表示内容への依存の機構。
- 乱れる場所が、FPGA内部なのか、リンク・受信器なのか。

### 15.5 次の最小試験（更新）

| # | 内容 | 目的・判定 |
|---|---|---|
| **T8** | **診断ビルド**：Aの入力のコピーに対してD-1（例：`write_data` の選択を対象語の `cpu_write` だけにする、または非書込みサイクルでDIを前値に保持する）を適用し、STA違反0を確認してから#11、#12、#14を再試験する。製品RTLは変更しない | 再現が消えれば、DIの一斉切替えが原因であることがほぼ確定し、修正候補にもなる。消えなければ、DIの配線や配置そのものではなく、より広い結合を疑う。配置が変わる副作用があるため、B側へ同じ変更を入れた場合との比較も検討する |
| T4 | #11、#14（A）と#08（B）を、HDMIプロトコルアナライザか別の受信器で記録する | 送出側か受信側かを分ける |
| T9 | 0x00/0xFF一定の別の組合せ（シアン `0x0FF`、黄 `0xFF0`）、および `0x00`/`0x11` の縦縞 | 表示への依存の規則を確かめる（Hostの変更だけで実施可能） |
| T10 | `cmd_read_data` を既知の値にしてから `o` を実施する（例：開始前に窓へのREADを1回行い、`cmd_read_data` を `0x55` のパターンにしてDIの切替えを0にする） | DIの切替え量だけを変えた対照（Hostの変更だけで実施可能） |

T8は、診断領域でのRTLのコピー、合成、P&R、STAが必要になる。製品RTLとSDCは変更せず、SRAMへの投入だけで行う。

### 15.6 採用判定への影響

保留を継続する。ノイズ源の候補を窓RAMのDIの一斉切替えまで具体化できたので、T8の結果によってD-1を修正として採用するかどうかを判断できる見通しになった。

---

## 16. T8：診断ビルドによるDI切替え量の切り分け（2026-11-08）

### 16.1 診断画像

- **ソース：** Aの保存入力41ファイルをコピーした（`build/pcm-stream-rc1/t8-di-local/inputs/`。コピーがAと一致することは `design-audit/t8-base-inputs.sha256` で照合済み）。変更したのは `rtl/fb/kagura_fb_registers.sv` だけである（パッチは `t8-di-local.patch`、`c48b6494…`）。製品RTL、SDC、CSTは変更していない。
- **変更内容：**
  - 8個のグループ選択FFを、**16個の語単位の選択FF**（`window_select[w].select_cpu`、syn_keep）に置き換えた。
  - `diag_broadcast=0`（リセット後の既定）では、byte_commit時に**対象の1語だけ**DIを切り替える。
  - CSR 31 にbit1を書くと `diag_broadcast=1`（stickyで、bit2で解除）になり、**Aと同じ全語のDI切替え**に戻る。
  - DIのMUXと選択FFは両モードで共通で、FFの入力条件だけが異なる。つまり**同じ配置のまま、Hostから切替えられる**。HostのSDKはaddr 31に値1しか書かないため、既存の動作とは衝突しない。
- **シミュレーション**（`design-audit/run-t8-sim.sh`）：
  - 窓TBで、全バイトの内容照合とパッチ内のアサーションがPASSした。
  - モード別のDI遷移数は、既定では1/16になった（例：`o` 8,388,608 → 524,288）。`+BROADCAST` ではAと完全に一致した（`t8-tb_*-{local,broadcast}.log`）。
- **合成とP&R：** Aと同じ `build-fb.tcl qspi 4 2 8 0 1 auto` で合成した（netlist `38ecc4ba…`）。
  - place 4 / route 2 ではSTA不合格（setup違反112、WNS −2.795 ns。ワースト経路は無関係のcursor）だったため、投入しなかった。
  - 同じnetlistとSDCで `reroute.ps1` によりP&R条件を9通り試した。結果は次のとおり。

| P&R条件 | 結果 |
|---|---|
| p4/r2/f22、p4/r2/f16、p4/r1、p2、p1、p0 | unrouted nets で失敗 |
| p4/r2/f24 | setup違反112 |
| p4/r0 | setup違反64 |
| **p3/r2/f23** | **違反0、WNS +0.177 ns、WHS +0.527 ns。数値ゲート（≥0.10 ns）を通過** |

- **採用した画像：** `build/pcm-stream-rc1/t8-di-local/sta-p3-r2-f23/impl/pnr/kagura_fb.fs`（`fad15376…`、User Code `0x00008039`）。STA HTMLは `f23e7793…`、テキスト化したものは `design-audit/T8-timing.txt`。
- **Host ELF：** `5e08a679…`。大文字のモード `I`/`O`/`T`/`X` は、開始前にCSR 31へ0x02を書き（USBログに `DIAG_BROADCAST set` を記録）、その後は小文字の `i`/`o`/`S`/`x` と同じ処理をする。

### 16.2 結果

手順は§14.1と同じ。投入はSRAMだけで、全回で復旧とFlashの一致を確認した。

| # | 画像 | モード | DI切替え | 窓データ / 表示 | 低RMS L/R |
|---|---|---|---|---|---:|
| 19 | T8 | `O` | 全語（Aと同じ） | 0x55固定 / 元配色 | **0 / 0** |
| 20 | T8 | `o` | 対象語だけ | 0x55固定 / 元配色 | 0 / 0 |
| 21 | T8 | `I` | 全語 | 2–63バイト目反転 / 元配色 | **0 / 0** |
| 22 | T8 | `T` | 全語 | PCM / 黒白の縦縞 | **0 / 0** |
| 23 | **A** | `i` | 全語 | 2–63バイト目反転 / 元配色（陽性対照） | **29 / 30** |

全回で `rc=0`、timeout 0、E1とPCM異常フラグは0。0 / 0の回はマーカー不一致も0だった。

### 16.3 判定

**確定したこと**

- **T8画像では、DIの全語切替えを有効にしても、Aで最も強く再現した3条件（Aでは25–38）が再現しなかった。** 同じセッションの陽性対照（A、#23）は29 / 30で再現しており、機器構成側が再現しない状態に変わったわけではない。
- したがって、**DIの全語切替えは、それだけでは十分条件にならない。** 再現には「Aの配置配線」が必要である。§15で特定した「窓RAMのDIの一斉切替え」は、**A固有の物理条件のもとで効くノイズ源（または引き金）**と位置づけるのが正しい。
- 当初のT8の狙い（同じ配置でのDI切替え量の比較）は、T8画像が両モードとも0 / 0だったため、**判定できなかった**。D-1（DIの局所化）が修正として必要かどうかは、この試験からは言えない。

**この試験の限界**

- 実機で `diag_broadcast=1` が実際に有効になったかは、直接は観測できない。DIの切替えは機能上見えないためである。根拠は、RTLシミュレーションと、Hostが書込みを完了したログ（sticky errorなし）だけである。
- T8画像の配置はAと大きく異なる（全面的な再配置）。何が「Aに固有の物理条件」なのかは、まだ特定できていない。

**示唆（仮説）**

T8画像のSTAでは、Aで余裕の小さかったpixel74のHDMI経路が、上位25経路から外れた。

| 経路 | A | T8 |
|---|---:|---:|
| `tmds_gen[0]/mode2_0→tmds_2` | 0.272 ns | >1.42 ns |
| `cx_6→spd_sent CE` | 0.622 ns | >1.42 ns |
| `audio_fifo wb_4→wg_sync1_4` | 0.502 ns | >1.42 ns |
| HDMI系で最も余裕が小さい経路 | – | `audio_packets/acr_pending→sub[0]` 0.785 ns、`tmds_gen[1]/qm1_3→balanced2` 1.234 ns |

これは、**H4物理版**（Aで余裕の小さいpixel74経路が、DIの一斉切替えによる電源・GNDノイズで誤動作する）と矛盾しない。ただし、配置が変われば、結合経路（距離、配線、電源領域）も同時に変わるため、余裕の差が原因だとは断定できない。

### 16.4 結論の更新と採用判定

1. 再現には、(a) **Aの配置配線**、(b) 窓RAMのDIの一斉切替え、(c) 「全チャネル0x00/0xFF一定」以外の表示、の**3つすべて**が必要である（実機で確認）。
2. RC1（B）とT8（Aの機能＋DI選択の変更、別配置）は、最も強い条件でも再現しない。
3. **最も実用的な結論：** 現象は**特定の配置配線結果（Aのbitstream `DE71…`）に結び付いている**。STAを通過していても、同じRTLから別の配置で作ったbitstreamで再現しない、という事実がある。したがって、PCMストリーミングを採用する際には、次の2点が必要になる。
   - bitstreamごとに、今回の**再現条件セット**（`i`、`5`、`o`、`S` ＋ `x`、各25秒）を実機での合否ゲートにすること。
   - 原因の物理的な仕組みは未特定のため、このゲートは「この機器構成で再現しない」ことしか保証しないと明記すること。
4. **T8画像の扱い：** T8画像（`fad15376…`）は、Aの全機能を含み、STA余裕も大きく（+0.177 ns）、今回の再現条件セットで0 / 0だった。ただし、この画像はDI選択の診断変更を含む**診断ビルド**である。採用候補にするには、変更をSTA対策として正式なパッチにし、通常の回帰試験（PCM2ボードTB、ストリーミングのプロトコル試験 `g`、150秒の `b`、1時間の `l`、BLIT STORMの `s`）を通す必要がある。**現時点では採用候補として宣言しない。**

### 16.5 次の候補

| # | 内容 | 目的 |
|---|---|---|
| T11 | A RTLのまま（DIの変更なし）、place 3 / route 2 などでSTA違反0の別配置を作り、`i`/`5`/`S` を実施する | 「DI選択の変更」と「配置の変更」のどちらが再現を消したのかを分ける。以前のスイープでは、A netlistのSTA合格配置は元の1つ（と、それと同一配置相当の `f24`）だけだった。place 3 / route 2 / maxfan 23 は、A netlistでは違反84で不合格、T8 netlistでは合格である。別のseed、またはpalette配置制約を与えたP&Rが必要になる |
| T4 | A×`i`/`S` と、T8×`I`/`T` を、HDMIアナライザか別の受信器で記録する | 乱れる場所（FPGA内部か、リンク・受信器か）を特定する |
| T12 | T8画像で、Aのpixel74経路の余裕に近づける配置制約を与える（逆方向の試験） | 余裕と結合のどちらが効くかを調べる |

---

## 17. T11：A RTLのまま別の配置を作る試み（2026-11-08）

### 17.1 実施内容

A RTL（DI選択の変更なし）のまま、STA違反0でAと配置の異なる画像を作ることを目指した。製品RTL、SDC、CSTは変更していない。

- **P&R条件のみの変更**（Aのnetlist、CST、SDCをハッシュ照合したうえで `reroute.ps1` を使用）：
  - place 4 / route 2 で maxfan 18、20、26、28、30、35
  - place 3 / route 2 で maxfan 20、26、30
  - place 0 / route 2
- **P&Rの別オプション**（`diagnostics/pcm-stream-rc1/t11-variants.ps1`）：`replicate_resources 1`、`clock_route_order 1`
- **同じRTLの再合成**：入力41ファイルがAと一致することを照合し、`opt_goal timing` と `opt_goal area` で合成した。area版は place 3 / route 2 も試した。
  - 1回目の試行は、照合書式の不一致で照合段階で停止した。合成は実行していない。その残りが `build/pcm-stream-rc1/t11-a/syn-timing/` にある（削除はセーフティチェックで止められたため、残してある）。

### 17.2 結果

| 区分 | 条件 | 結果 |
|---|---|---|
| STA合格 | p4/r2/f24、f26、f28、f30、f35、`replicate_resources 1`、`clock_route_order 1`、`opt_goal area`（p4/r2） | 違反0、WNS +0.090、WHS +0.53、ワースト経路も同一。**bitstreamは先頭の `//Created Time:` 行以外、Aとバイト単位で同一**（f24、f26、f35、replicate、clockorder、areaの6種で `cmp` により確認）。STA詳細の座標列と経路表のハッシュも同一 |
| STA不合格 | p3/r2/f26、f30、area＋p3/r2 | 違反84（WNS −2.766）。以前の p3/r2/f23（違反84）と p4/r0（違反2）も同様 |
| 配置・配線の失敗 | p4/r2/f18、f20、p3/r2/f20、p0/r2、`opt_goal timing`（48 LUTが配置不能） | 以前の p4/r2/f22、f16、p4/r1、p2、p1 も同様 |

### 17.3 判定

- **確定：** Gowin V1.9.12.04のこのフローは決定的に動作する。A RTLから得られるSTA合格の実装は、試した範囲では**A自身（`DE71…` と本体が同一）だけ**だった。seedに当たるオプションはなく、配置を変える条件はすべてSTA不合格か配線失敗だった。したがって、**「A RTLのままSTAを通る別の配置」は、ツールオプションだけでは作れない。** 本体が同一の画像を実機で試しても新しい情報は得られないため、T11の実機試験は行わなかった。
- **代わりになる根拠：** T8画像を旧動作（`diag_broadcast=1`）で動かした試験（#19、#21、#22）が、得られる中で最もT11に近い。
  - 旧動作では、窓のDIとRAMの振る舞いがAとサイクル単位で同一である（`t8-tb_*-broadcast.log` の遷移数がAと完全に一致）。それでも再現しなかった。
  - よって、再現が消えた主因は**実装（配置配線）の変化**と考えるのが妥当である。
  - **残る交絡：** T8のnetlistは、選択FFの数（8→16）とその入力のデコードがAと異なる。また、実機で `diag_broadcast=1` が有効になったことは直接観測できない。
- **採用判定への示唆：**
  - 現象は特定の実装に結び付いた物理的な問題である。同じRTLでも配置が変われば消えるが、Gowinでは配置を自由に選べない。
  - そのため、修正や採用の判断はbitstream単位の**実機再現ゲート**（§16.4）に依存せざるを得ない。
  - 根本原因（どの経路が、どの物理的な仕組みで誤動作するか）の特定には、T4（HDMIアナライザか別の受信器）か、Aへの内部監視の追加（D-3。ただし配置が変わって現象が消える可能性が高い）が必要になる。

### 17.4 次の候補

| # | 内容 | 備考 |
|---|---|---|
| T4 | A×`i`/`S` とT8×`I`/`T`、B×`5` を、HDMIアナライザか別の受信器で記録する | 機材が必要。A画像を変えずに乱れる場所を特定できる唯一の手段 |
| T13 | A netlistに、窓RAM（16 BSRAM）またはHDMI pixel74群の位置を固定する制約（INS_LOC）を与えて再配置する | 以前のpalette制約の試行（5種）はすべてSTA不合格だった。制約の選び方によってはSTAを通る可能性がある |
| G1 | 採用ゲートの整備：候補bitstreamごとに `x`、`5`、`i`、`o`、`S`（各25秒）とRC1対照を自動実行し、低RMSとマーカーで判定する | `run-audit-ab.py` と `hardware-ab-results.json` の仕組みをそのまま使える |

## 18. G1採用ゲートと、T8から診断CSRを除いた製品相当版（2026-11-08）

### 18.1 G1採用ゲート

- **スクリプト：** `hardware-host/adoption-gate.py`（SHA-256 `7319da79…f6a4f1`）
- **手順：**
  - 数値STAゲート：候補の `timing-status.json` を読み、setup/hold違反0かつsetup WNS ≥ 0.10 nsでなければ `REFUSED` で終了する（実機に投入しない）。
  - 陽性対照：A×`i`。低RMSブロックの合計が10以上でなければ、ベンチが不感とみなして `INVALID` とする。
  - 陰性対照：RC1×`5`。クリーンでなければ `INVALID` とする。
  - 候補：`x`、`5`、`i`、`o`、`S` を各25秒実行する。すべてクリーン（rc=0、低RMS [0,0]、マーカー不一致 [0,0]）なら `PASS` とする。
  - 各実行はSRAMのみに書き込み、approved Queue8（UserCode 0x00004068）の復元とRP2040 Flashの一致を確認する。
- **自己試験：**

| 試験 | 候補 | 結果 |
|---|---|---|
| STA拒否 | T8の初回P&R（WNS −2.795 ns） | `REFUSED`。実機投入なし |
| 実機 | T8 sta-p3-r2-f23（`fad15376…`、WNS +0.177 ns） | 陽性対照 [28,29]／マーカー[275,278]、陰性対照 [0,0]、候補5条件すべて [0,0]。`PASS` |

- `PASS` が意味するのは「このベンチ、この条件、各25秒で再現しなかった」ことだけで、物理的な原因が無いことは示さない。

### 18.2 製品相当版のRTL

- **パッチ：** `window-word-sta.patch`（SHA-256 `60053241…f947ae`）。入力はA（41ファイル、`t8-base-inputs.sha256` で照合）にこのパッチだけを当てたもの。
- **T8との違い：** CSR 31（`diag_broadcast`）とその経路を削除した。窓RAMのワードごとの選択FF（16個、`syn_preserve`）は残し、該当ワードのBSRAMにだけ書込みデータを渡す。
- **回帰：** `regress.py --window-word-select` は12件すべてPASSした（`build/pcm-stream-rc1/word-select-regression`）。パッチ後のテキストの検査と、`tb_fb_register_window` の参照比較を含む。
- 回帰側の `kagura_fb_registers.sv` のコピーはCRLFとLFが混在している。ビルド側のコピーとの違いは改行コードだけであることを確認した。

### 18.3 STAの結果：合格する実装は見つからなかった

`sta-sweep.ps1 -Trial build/pcm-stream-rc1/word-select` と、それ以前の個別試行の結果を以下に示す。RTL、SDC（RC1と同一ハッシュ）、CSTはどれも変えていない。

| 実装 | setup違反 | WNS (ns) | 最悪経路の終点 |
|---|---|---|---|
| native p4/r2（標準） | 26 | −1.765 | core/memory_ctrl/tx_325（始点 tx_load） |
| p4/r2 f26・f28・f30、replicate1、clockorder1 | 26 | −1.765 | 同上（すべて同じ結果） |
| p3/r2 f23・f26・f30、replicate1 | 30 | −1.619 | host/registers/sticky_error_0 CE |
| p4/r0 | 67 | −2.123 | memory_ctrl tx_325 |
| p3/r0 | 36 | −2.004 | commands/fill/end_byte_7 |
| p3/r1、p4/r2 f18・f20・f22、p3/r2 f18・f20 | — | — | 配線失敗（PR0004、未配線ネットあり） |
| 再合成 area：p4/r2、p3/r2/f23 | 26、30 | −1.765、−1.619 | nativeと同じ結果（netlistが実質同一） |
| 再合成 timing：p4/r2 | 38 | −3.926 | registers/window_write_word_13 |
| 再合成 timing：p3/r2/f23 | — | — | 配線失敗 |

- 違反はすべてsystem54ドメインで起きている。主な経路は、tx_loadから512個のtxレジスタへのファンアウトと、host/registersのCE経路である。
- T8（同じ構造に診断CSRを加えたもの）は、p3/r2/f23で +0.177 ns を出して合格した。CSRを外しただけで合否が逆転したことになる。これはGowin P&Rの結果がnetlistの小さな違いに大きく左右されることを示しており、§17の「配置は自由に選べない」という結論と一致する。
- **方針：** STA未達の画像は実機に投入しない。G1は数値ゲートで拒否する設計なので、製品相当版はG1の実機段階に進めていない。

### 18.4 判断に必要な選択肢

| # | 内容 | 留意点 |
|---|---|---|
| P1 | 製品相当版のnetlistに、T8の合格実装の位置を制約として与える（窓BSRAM、選択FF、tx群のINS_LOC）。または、tx_load系とsticky_error系の配置を固定する | CSTの追加は製品の実装制約の変更にあたる。SDCは変えない |
| P2 | T8のnetlist構造を保ったまま、diag_broadcastを定数0に縛る。たとえばCSR書込みの経路だけを残してゲートする | T8と配置が近くなる保証はない。「製品相当」の定義を確認する必要がある |
| P3 | T8の画像（診断CSRつき、既定値は製品と同じ動作）を、そのまま候補としてG1で評価済みのものと扱う | 製品に診断CSRが残る。CSR 31への誤った書込みで旧動作に戻るリスクがある |
| P4 | tx_loadのファンアウトとsticky_errorのCE経路を、RTLで分割または複製する | 製品RTLの変更が増え、新しい回帰と実機ゲートが必要になる |

- PCMストリーミングの採用は宣言しない。原因は特定の配置に結び付いた物理現象であり、根本的な仕組みはまだ確定していない。
- 残置物：`build/pcm-stream-rc1/t11-a/syn-timing`（部分的な生成物）。安全確認により削除が拒否されたため、そのまま残している。

## 19. P1：T8合格実装の配置を製品相当版に与える試み（2026-11-08）

### 19.1 方法

- **T8の配置抽出：**
  - T8 sta-p3-r2-f23を `-gen_posp 1` 付きで再P&Rした。出力先は `build/pcm-stream-rc1/p1-placement/t8-posp`。
  - `.bin` は元のT8画像と完全に一致した。`.fs` の差は作成時刻のコメント1行だけである。
  - `.posp` に記録されるのはハードブロック25個（BSRAM 23個、DSP 2個）だけで、ロジックセルの位置は含まれない。インスタンス名はすべて製品相当版のnetlistにも存在する。
- **制約の付け方：** 製品相当版のnetlist（RTLとSDCは不変。SDCはRC1と同じハッシュ）に、`INS_LOC` を追記したCSTを与えた。
- **スクリプト：** `p1-placement.ps1`。生成したCSTは `hard-block-loc.cst`。

### 19.2 結果

| 実装 | 固定したもの | 結果 |
|---|---|---|
| 製品相当版 p3/r2 f23・f26・f30 | ハードブロック25個 | 配線失敗（未配線218本） |
| 製品相当版 p4/r2 f23・f26 | ハードブロック25個 | 配線失敗（未配線408本） |
| 製品相当版 p3/r2/f23 | 窓RAMのBSRAM 16個 | 配線失敗（未配線168本） |
| 製品相当版 p4/r2/f23 | 窓RAMのBSRAM 16個 | setup違反96件、WNS −3.109 ns（tx_468） |
| 製品相当版 p3/r2/f23 | 窓RAM＋記述子のBSRAM 20個 | 配線失敗（未配線380本） |
| 製品相当版 p4/r2/f23 | 窓RAM＋記述子のBSRAM 20個 | 配線失敗（未配線48本） |
| **対照：T8自身のnetlist** p3/r2/f23 | T8自身のハードブロック25個 | **配線失敗（未配線180本）** |
| **対照：T8自身のnetlist** p3/r2/f23 | T8自身のBSRAM 23個 | **配線失敗（未配線454本）** |

### 19.3 解釈

- 合格実装と同じハードブロック位置を、そのnetlist自身に制約として与えても、元の実装は再現されず、配線にも失敗した。
- Gowin V1.9.12.04では、ハードブロックに `INS_LOC` を与えると、配置の過程そのものが無制約の場合と変わると考えられる。したがって「合格した配置を制約で写し取る」という方法は、このツールでは成り立たない。
- ロジックセルを固定するには、その位置をT8から取り出す必要がある。しかし、T8のタイミングレポートには、製品相当版で違反している経路のセル（tx_load、sticky_error）が載っていない（T8ではこれらが臨界経路ではないため）。加えて、上の対照結果から、少数の制約でも配置全体が大きく変わると予想される。
- STAに合格した画像はなかった。そのため実機への投入もG1の実行もしていない。

### 19.4 残る選択肢

| # | 内容 |
|---|---|
| P2 | T8の構造を保ったまま、`diag_broadcast` を常に0に固定する |
| P3 | T8の画像そのものを候補とする（G1合格済み。診断CSRが残る） |
| P4 | tx_loadのファンアウトとsticky_errorのCE経路を、RTLで分割または複製してタイミング余裕を作る |

- 結果がnetlistの小さな差で大きく変わることから、P4のようにタイミング余裕そのものを増やす方法が、実装ごとのばらつきに対して最も頑健と考えられる。
- PCMストリーミングの採用は引き続き宣言しない。

## 20. T8画像の製品候補化：CSR 31監査、G1正式認定、bitstream固定（2026-11-08）

対象はT8画像 `fad15376…`（STA WNS +0.177 ns／WHS +0.527 ns、違反0）である。

### 20.1 CSR 31の安全性監査

**RTL**（`t8-di-local.patch`）

| 項目 | 結果 |
|---|---|
| bit0 | 従来どおりACK（DONEのクリア）。T8で変更していない。 |
| bit1 | `diag_broadcast` をセットする（stickyで保持）。 |
| bit2 | `diag_broadcast` をクリアする。bit1と同時に書いた場合はbit2が優先される。 |
| リセット | 0に戻る。 |
| 読み出し | `{7'd0,irq}` のまま変わらない。`diag_broadcast` は読み出せない。 |
| busy中の受付 | 制限されない（従来と同じ）。 |

**ソフトウェア**

- C版SDK（`kagura_fb.c`）とPython版SDK（`kagura_fb.py`）がCSR 31に書く値は1だけである。
- BEYOND 16、MIDNIGHT TERMINAL、RP2040ファームウェアは、CSR 31を直接書かない。
- 自動インクリメント書込みの開始レジスタは7、8、32、37、39、46、54である。どれもCSR 31には到達しない。
- 27〜30への書込みはBAD_COMMANDになる。そのため、インクリメント書込みが気付かれずに31へ達することはない。
- アドレスは6ビットで、63の次は0に戻る。この折り返しでも31には達しない。

**シミュレーション**（`design-audit/tb_csr31_safety.sv`、`run-csr31-sim.sh`）：2,282項目で**PASS**。

- リセット直後の値
- 書込み前の状態0と1のそれぞれから、全256値を書き込んだときの遷移と、応答エラーが出ないこと
- 読み出し値が変わらないこと
- 0〜30へ0xFFを書いても `diag_broadcast` がセットされないこと
- 27〜30への書込みが拒否されること
- SDKのACK値（1）を64回書いても `diag_broadcast` がセットされないこと
- リセットでクリアされること
- 両モードで窓へ書き込んだときに、RTL内のアサーションが成立すること

**残るリスク**

- QSPIのフレームが壊れた場合の誤書込みは、他のCSRと同じ扱いになる。
- 誤って `diag_broadcast=1` になった場合でも、T8の配置では再現しなかった。根拠は§16の#19・#21・#22と、§20.2の誤設定試験である。
- 防御を強める場合は、SDKの初期化時にCSR 31へ0x04を書けばよい。RC1やAでは0x04はACKを伴わず無害である。この変更は実施していない。

### 20.2 G1正式認定試験

- **実行：** `adoption-gate.py t8-cert … --modes xz5fryeaioGSR1E --rounds 3 --closing-controls --fault-modes IOTX`
- **結果の保存先：** `build/pcm-stream-rc1/gate/t8-cert-20261108-212533/gate.json`。写しを `candidate-t8/validation/g1-certification-gate.json` に置いた。

| 区分 | 回数 | 結果 |
|---|---|---|
| 開始時の陽性対照（A×`i`） | 1 | 低RMS [31,29]、マーカー [269,277]：ベンチは再現を検出できる |
| 開始時の陰性対照（RC1×`5`） | 1 | [0,0] / [0,0] |
| 候補：15モード×3周 | 45 | すべて [0,0] / [0,0] |
| 候補：CSR 31誤設定（`I`、`O`、`T`、`X`） | 4 | すべて [0,0] / [0,0] |
| 終了時の陽性対照（A×`i`） | 1 | [24,25]、マーカー [272,277]：最後までベンチは再現を検出できた |
| 終了時の陰性対照（RC1×`5`） | 1 | [0,0] / [0,0] |

- **判定：** `PASS (no reproduction under the audit set)`
- **インフラ：** 全53回で異常なし。approved Queue8（`0x00004068`）への復元と、RP2040 Flashの一致を毎回確認した。
- **初回起動の中断：** 最初の起動（`t8-cert-20261108-212511`）は、PowerShellから引き継いだ環境変数のためにprogrammer_cliの内蔵Pythonが起動できず、JTAGスキャンで止まった。書込みは発生していない。Bashから起動し直して実行した。

### 20.3 bitstreamの固定

固定パッケージは `candidate-t8/` に置いた。`SHA256SUMS` には自身を除く66ファイルを収め、そのハッシュは `b76ea70c…` である。

**内容**

- `.fs` と `.bin`
- 合成入力41ファイルと、そのハッシュ一覧（manifest）
- 1段目のnetlist、CST、SDC、2段目の `reroute.tcl`
- STA結果
- 検証記録
- ライセンス
- `manifest.json`
- `reproduce.ps1`

**再現ビルド**（`reproduce.ps1 -Output build/pcm-stream-rc1/candidate-t8-repro2`）：`reproduced: true`

| 比較対象 | 結果 |
|---|---|
| netlist | 一致（`//` で始まるヘッダコメントを除く） |
| CST | 一致 |
| `.bin` | 完全に一致 |
| `.fs` | 一致（`//Created Time` の1行を除く） |
| STA | 違反0/0、WNS +0.177 ns |

初回の再現（`candidate-t8-repro`）では、netlistの比較が不一致になった。差分は、ヘッダコメントに含まれる合成時刻と絶対パスだけだった。そこで比較からコメント行を除くよう修正した。`.bin` は初回の時点ですでに一致していた。

### 20.4 判定と限界

- 3項目（CSR 31監査、G1正式認定、bitstream固定）はいずれも問題なく完了した。T8画像を正式版へ昇格するための技術的な前提はそろっている。
- 昇格（`releases/` や `artifacts/` への配置、known-goodの扱い、Flashへの書込み）は所有者の判断に委ねる。本作業ではいずれも行っていない。
- **限界：**
  - G1 PASSが意味するのは、「このベンチ、この条件、各25秒で再現しなかった」ことだけである。Aでの物理的な根本原因は特定していない。
  - 修正の効果はこの配置に依存している。netlistやP&Rの設定が変わる再ビルドでは、STAとG1を取り直す必要がある。
  - setupの余裕は0.177 nsで、RC1の0.659 nsより小さい。PVT（電圧・温度・製造ばらつき）と外部I/Oのタイミングは評価していない。
  - 試験は基板1枚、HDMIキャプチャ経路1つで行った。

## 21. 正式版への昇格とFM音源メガデモ（2026-11-08）

### 21.1 昇格

所有者の判断により、T8を通常Releaseの添付対象（selected）に昇格し、PCM2版と置き換えた。FPGAとRP2040のFlashには書き込んでいない。

**昇格前の回帰試験**

- **方法：** RC1の検証と同じ手順で、常駐のBEYOND 16 COLORS Queue8 firmware（Flash `c7052a32…`）をT8上で150秒動かした。スクリプトは `promotion/run-megademo.py`、結果は `build/pcm-stream-rc1/promotion-megademo-2` にある。
- **結果：** RC1と同等だった。

| 項目 | 結果 |
|---|---|
| フレーム数 | 4452（全8シーン） |
| 最悪描画時間 | 82.296 ms |
| timeout／audio fault | 0／0 |
| HDMI音声の10 ms欠落 | 左右とも0 |
| RP2040 Flash | 実行前後で一致 |

- **初回の中断：** 最初の実行（`promotion-megademo`）は、再起動直後に起動メッセージを受信できず、メガデモの開始前に止まった。USBの準備が整うまで待つ処理を加えて再実行した。

**配置と更新したファイル**

- `artifacts/validated/kagura-hd-qspi-pcm-stream.fs`（`fad15376…`）
- `releases/pcm-stream-qspi/`：41個の入力、P&R入力、STA、検証記録、`reproduce.ps1`、`SHA256SUMS` で計71ファイル
- 更新：`releases/candidates.json`（`qspi_pcm2` は superseded）、`releases/SHA256SUMS`、`releases/README.md`、`releases/RELEASE_NOTES.md`、`artifacts/README.md`、`artifacts/validated/SHA256SUMS`、ルートの `README.md`、`docs/README.md`、`docs/kagura-fb-host-api.md`（ストリーミングCSRの節を追加）、`tools/check-release.py`（参照先を新パッケージに変更）

**`tools/check-release.py` の状態**

- 作業ツリーのRTL（`rtl/`、`boards/`）は、未コミットのQueue8開発中の状態である。選定版の入力とは9ファイルが異なる。
- この不一致は昇格前からあり、旧PCM2との照合でも不合格だった。
- 照合部分を除けば、選定版のbitstream、パッケージのチェックサム、固定入力41件はPASSする。
- 作業ツリーのRTLは変更していない。

### 21.2 FOUR OPERATORS

`software/fm_megademo/` に新しく作成した。

- **音源：** core 1で動く整数演算の4オペレータFM（6声）と、ドラム3種、エコー。
- **曲：** オリジナル、65小節。
- **映像：** 8シーン。
- **ストリーミング：** 補充を描画コマンドの合間に分割して進める。

**実機での実行**（SRAMのみ。選定版の画像とRAM ELF `87a142fc…`、結果は `build/fm-megademo/hw-03`）

| 項目 | 結果 |
|---|---|
| 終了 | `rc=0` |
| 補充 | 1546半面、最悪の公開遅延54.6 ms |
| ch STATUS／HDMI STATUS | 0x03／0x00 |
| timeout | 0 |
| HDMI録音の欠落 | 基準に音がある区間で左右とも0 |
| PC基準との相関 | 1秒ごとの中央値0.994 |

この実行は、PCMストリーミングと高い描画負荷（VECTORとSCOPEはFILLを多用する）を同時にかけた試験として、T8で初めて行ったものになる。

### 21.3 公開準備での扱い

- **候補一式（`candidate-t8/`）：** `.gitignore` に追加し、ローカル保管とした。公開する形は `releases/pcm-stream-qspi/` で、§20に書いた `candidate-t8/` の内容は、ここに同等のものがある。
- **netlist（2.6 MB）：** 配布パッケージには同梱しない。代わりに本体のSHA-256 `79434504…` を `manifest.json` に記録し、`reproduce.ps1` がこのハッシュで照合する。
- **個人の絶対パス：** ツールのログやレポートに含まれていたリポジトリの絶対パスを、`<repo>` に置き換えた（112ファイル、5,110か所）。
- **作業ツリーの同期：** 作業ツリーの `rtl/` と `boards/` を、選定版の入力に揃えた（9ファイル）。同期前の状態は `build/publication-prep/worktree-backup-20261108-232736/` に退避してある。
