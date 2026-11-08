# Queue8 FPGA縮小診断

HDMIパケット生成・TMDS・serializerを除き、画素カウンタ1650×750、
scanout、PRESENT mailbox、QSPI、Queue8、GPU、PSRAM、
PCM合成・prefetch・audio transport FIFOを保持。
audio transportのpixel_readyを1に固定。音声パケット化のbackpressureが変わる。
映像・音声出力はない。製品画像と同等と扱わない。
FPGAで同じ障害が出る最小構成は探索中。

sticky error 2の最初の設定経路を8 bit保持。
cause=1は不正CSR書込み（addr=26は不正SUBMIT）、
cause=2はaudio external_error、cause=3はエラー完了。
既存のsticky設定優先順を維持。sticky非ゼロ時のCSR0のみを診断値へ切替。
診断firmwareが異常時にGPU_TRACEとして取得する。

元の映像タイミングのリセット座標0,0、1650×750周期を確認。
QSPI Queue8の満杯受付・順序・READ・COPY・PRESENTの回帰試験PASS。
STA Setup +1.943 ns、Hold +0.456 ns、Setup/Hold違反0。
Recovery +9.625 ns、Removal +0.536 ns。
CLS3698/4320、BSRAM20/26。
既存SDCのCDC・外部PSRAM IO制約の限界を引き継ぐ。

ビットストリームSHA256
D415199BD0B236F2A5497BF048986C70DCB23CACD56DA38E286B56296420C486

診断RTLはdiagnostics/queue8-reduced、
全入力と合成・P&R証跡はbuild/queue8-reduced/inputsとnative、
回帰試験はbuild/queue8-reduced/sim.log。
実機原ログはbuild/queue8-reduced/hardware/candidate。
製品RTLには反映していない。

## 実機耐久結果

BLIT STORMを25秒周期で回す診断firmwareで、3600秒の描画を完了。
ホストでの停止観測は3603.906秒、STOP rc=0。
投入3136341、回収3136341、peak 8、pending 0、errors 0。
全PERF記録でtimeouts=0、audio_fault=0。GPU_TRACE出力なし。
縮小構成では問題が再現せず、再現可能な最小構成は未確定。
HDMI送出回路除去、音声FIFO出力即時回収、配置配線の変化を含むため、
どの差分が再現性を変えたかは未確定。

ビルドは入力snapshot内のtools/build-fb.tclに qspi 4 2 8 0 1 auto を指定。
実機runnerはbuild/queue8-reduced/run.py。HDMI録画を外しUSBで監視。
firmwareはbuild/queue8-sticky-trace/fw-compact/beyond16.bin。
試験前Flash二重読出しと書込み後の全量照合を実施。
復旧はbuild/queue8-reduced/recovery/result.jsonに記録。
FPGA Flash書込み0回。

## 音声FIFO backpressureの復元比較

前回の縮小版に、製品と同じ `kagura_audio_packets` と
VIC4の水平ブランキング中のパケット受付タイミングを追加した。
音声サンプルを受け付けられるタイミングを元へ戻し、
パケット組立、TMDS、serializerを除いた状態で比較する。

FPGA入力の差分は `rtl/hdmi/kagura_hdmi_stream_eval.sv` の1ファイル。
復元版のRTLは `diagnostics/queue8-reduced/kagura_hdmi_stream_backpressure.sv`。
同じ診断firmwareを使い、投入後のRP2040全Flashハッシュが
前回の縮小版試験と一致することを確認した。

元HDMIと260万画素クロックを比較し、画素座標、sample_ready、
FIFO出力valid、full、overflow、underflowが一致した。
sample_readyが低いクロックを283720回観測した。
STAはSetup +0.929 ns、Hold +0.528 ns、Setup/Hold違反0。
CLS3740/4320、BSRAM20/26。
ビットストリームSHA256
075d7f38a099d26f1016a69b0ded3ee2dcb0340964afc17cecc0e467cef89f88。

入力、回帰ログ、STA、実機原ログは `build/queue8-backpressure`。

BLIT STORMはホスト観測2215.171秒（36分55秒）でSTOP rc=-5。
1926244件投入、1926236件回収、peak 8、pending 8、errors 1。
最後のPERFは2210552 ms、timeouts=0、audio_fault=0。
GPU_RET_ERRORはexpected=received=4537、status=18、completion_error=0、sticky=2。
GPU_TRACEのcause=1、addr=0は、ベースCSRの識別レジスタ0への不正書込みを示す。
この8 bit形式で取得した値は設定元とアドレス。
ログに併記されたdata/tag/cmd_errorのゼロはfirmwareが出力した固定値。

即時回収版は1時間完走し、backpressure復元版は1回の試行で再現した。
今回の差はパケットスケジューラと、その追加に伴う配置配線。
不正書込み要求が生成された場所や、backpressureとの因果関係は未確定。
今回使用した診断RTLはsticky設定済みの場合に限り、
CSR0への書込みにも診断応答を返す分岐を含む。
今回の設定元記録はsticky=0での最初の書込みに対応する。

承認済みQueue8 SRAMと元のRP2040全Flash像へ復旧済み。
全量一致の証跡はbuild/queue8-backpressure/recovery/result.json。
