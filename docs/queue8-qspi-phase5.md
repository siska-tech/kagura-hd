# KAGURA-HD QSPI CSデグリッチ Phase 5

## 設計監査と試作

Phase 4縮小backpressure診断構成を複製し、A/Bとも同じ診断レジスタを追加した。
比較するFPGA RTLの差はkagura_spi_adapter.svのCS_FILTER=0/1だけ。
Bを試験専用とし、製品RTLへは反映しない。

既存CS/SCKは54 MHzで2 FF同期、IOも2 FF同期。同期レジスタは
clk posedgeの同期resetを使う。生CSを非同期クリアや出力ゲートへ接続しない。
旧版は同期CS highを観測したposedgeでphase=HEADER、discard=1、
IO出力禁止へ進む。chunkは次の同期CS startで0。
CS終了、CS開始、SCK取得の優先順は分岐により分離され、
high時や最初のlowサイクルと重なったSCKは取り込まない。
発行済みreq_validやREAD応答待ちはCS終了で取り消さず独立に完了する。

Bはframe_activeを受信境界の1 bitとして追加。
同期CS highの飽和カウンタの更新前値が2のとき、3つ目のhighを処理する。
最初の1/2 highではphase、chunk、in_shift、offsetを保持する。
high中および最初のlowと重なるSCKを抑え、途中のSCK遷移を再生しない。
3つ目のhighでframe_active、drive_mask、chunkを消し、HEADER/discardへ戻す。
次のlowを新規startとして受理する。1/2 highからのlowではstartを作らず、
元のframe位置で次のSCKを受理する。
したがって短highと本来必要なSCKが重なれば、そのニブルは回収できない。
今回の対策はCS境界耐性を高めるもので、任意の物理ノイズ下の通信を保証しない。

BのIO出力許可は保持drive_maskと同期済みCS lowのAND。
受信の終了確定を待たず、同期済みhighが反映された時点でIO出力を解放する。
短highから戻れば以前のREAD drive_maskへ戻る。
合法な新規CSには十分なhighがあり、確定終了でマスクを消してからHostの出力を受ける。
250 nsは54 MHzで13.5クロック。同期による遅延と3サンプル判定を含めても
Hostの設計上の合法間隔には余裕がある。
生CSに直接依存する非同期パスは増やしていない。
外部のCS/SCK/IO波形、同期段に達するグリッチ、端子解放時間は内部STAだけでは保証しない。

Phase 4の40/56/32 bitトレースとraw CS start、短high、未完ヘッダ、
完成ヘッダ0x00のカウンタを保持。short/highのRAWは既存同期器後でフィルタ前。
追加の正式終了数はAが従来のCS end、Bが3回highで終了した回数。
擬似境界の抑制数はBでframe_active中のraw startを数える。16 bit飽和。
診断CSR32–49のREADにrawカウンタと抑制数、CSR19–22のREADに正式終了数を割り当てる。
実際の受付開始数はraw開始数から抑制数を引く。
末尾で2回の診断READを行うため、各カウンタには読出し自体の境界が含まれ、
サンプル時点も異なる。未完ヘッダ数はRAW側のCS終了候補で数える。
診断firmwareは同一バイナリ、開始キーgの250 ns設定を両方で使用する。

## 同一波形試験

5 MHz相当で同じCS/SCK/IOを旧・新アダプタに印加した。
DATA中の1/2 highの後で旧版は後続0x00/0x1EからCSR0 WRITEを2回生成し、
Bは元のアドレス8/9へ継続しCSR0 WRITEは0件。
HEADERの1/2 highでニブル位置を維持。3/4 highで途中DATAを破棄。
250 ns、1 µs、2 µsの合法境界、複数の位相、途中の高期間のSCK遷移、
連続短high、READ中の短high後の再開、合法なREAD終了での出力解放を確認。
CS highの同期出力と同時にIO無効であることを毎サイクル検査した。
Bで抑制数7を観測。VCDはbuild/queue8-phase5/cs-filter-ab.vcd、
試験ソースはtb_cs_filter.sv、実行ログはfilter.log。

## ゲートと実機比較

A/BでQueue8満杯、順序、READ・COPY・PRESENT、PCM/PSRAMボード回帰が通過。
QSPI試験は5 MHz、可変の合法CS境界で実施。FIFO単体はPhase 3と同一RTL。
最悪STAは以下。既存クロック、SDC、P4/R2を維持。Setup/Hold違反ともに0。

| 画像 | Setup ns | Hold ns | Recovery ns | Removal ns | CLS | BSRAM | 最悪Setup経路 |
|---|---:|---:|---:|---:|---:|---:|---|
| A 旧処理 | +1.552 | +0.484 | +10.295 | +0.542 | 3782/4320 | 20/26 | held_page → active_page |
| B フィルタ | +2.208 | +0.473 | +9.725 | +0.827 | 3842/4320 | 20/26 | bank tag_18 → pixel_tag_18 |

BはCLS 60増。最悪経路も配置配線も異なるため、余裕の増加をフィルタ固有の効果とはみなさない。
STAと回帰ログはbuild/queue8-phase5/a、bのtiming-status.json、
a-sim.log、b-sim.log、a-board.log、b-board.log。
bitstream、firmware、RTL入力、テストのSHA256はsha256.json。

両条件で同じ診断firmwareおよび書込み後RP2040全Flashハッシュを確認。
FPGA SRAMのUser CodeとStatus Code照合後に開始。
CS high 250 ns、5 MHz、Queue8、BLIT STORM 25秒周期。
Aは最初の異常で停止、Bは3600秒の描画を完了した。

| 指標 | A 旧処理 | B フィルタ |
|---|---:|---:|
| ホストSTOP観測 秒 | 955.187 | 3604.093 |
| CS開始 RAW | 27250309 | 102643596 |
| 正式終了 / 受付開始 | 27250309 / 27250309 | 102643596 / 102643596 |
| 短HIGH / 抑制 | 1 / 0 | 0 / 0 |
| 0x00ヘッダ / 捕捉BAD_COMMAND | 1 / 1 | 0 / 0 |
| 投入 / 回収 | 828015 / 828007 | 3137031 / 3137031 |
| peak / pending | 8 / 8 | 8 / 0 |
| Queue errors | 1 | 0 |
| timeout / PCM fault | 0 / 0 | 0 / 0 |
| STOP rc | -5 | 0 |

STOP観測時間には終了後の診断ログ出力を含む。
カウンタは初期化と終了時の診断通信を含む。
Aは従来どおりDATAで同期済みhighを1サンプル観測し、
その後の0x00ヘッダでCSR0 WRITE（data 0x02）を生成した。
期待タグ・受信タグ31163一致、完了エラー0、sticky 2。
Host履歴8192件に予定・PIO投入の差やCSR0 WRITEはなく、最終4区間は0x47、0x1A、0xDB、0x87。
RP2040パッド監視は両条件short_latched=0。外部端子の連続波形は取得していない。

Bは実機で短Highを観測せず、抑制も0件だった。
A/Bの配置配線が異なるため、Bの実機完走は短High抑制の実証に数えない。
注入波形での対策効果と、Bの正常な1時間運転までは確認。
実機で短Highが入った場合の効果および物理的発生源は未確定。
効果確認を条件としたフルHDMIの合成・実機評価は保留。
製品マージ、既存画像の置換、STA改善画像への正式採用は行っていない。

次はBで短Highの観測と抑制を同じ試験で得る。自然発生の反復か、
別の診断firmwareで既知の時点に短Highを注入し、正常なデータの欠落、
READのIO解放、再開後のコマンド結果を照合する。
物理的な発生源は、RP2040パッド側とFPGA同期後の連続サンプルを
既知のヘッダ列で対応づけて切り分ける。

原ログはbuild/queue8-phase5/hardware/aとbのdemo-usb.log。
comparison.jsonに計数、history-a.jsonにHost照合。
FPGA Flash書込み0。RP2040 Flashの事前二重バックアップ、
firmware/filesystem/消去末尾以降の照合、元の全Flash復旧を実施。
復旧後SHA256はc7052a32c9c4d83c0c4115c64b14d6bb18959301eda3ad3ecfb53fa50e1fc26a。
承認済みQueue8 SRAMへ復元した。recovery/result.jsonを参照。
一時差替えした製品firmwareソース、SDK、PIOをビルド前と照合済み。
