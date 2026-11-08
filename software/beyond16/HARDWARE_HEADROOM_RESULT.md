# 8構成 実機比較結果

同じ描画・seed 0xb1616・RP2040 120MHz・既存QSPI設定・FPGA・配線で、固定hashの8構成を各1周150秒、PCM OFF/ON有限ベンチで比較した。FPGA投入0、FPGA Flash書込み0、release_ready=false。

## 全体結果

|構成|実PRESENT fps|間隔中央値 ms|p95 ms|最悪間隔 ms|33.333ms超過 %|最悪call ms|記録deadline miss|
|---|---:|---:|---:|---:|---:|---:|---:|
|A-off|29.373|33.334|49.996|150.008|51.453|149.002|220|
|A-summary|28.469|33.334|50.005|216.685|52.648|215.638|394|
|A-detailed|19.339|49.987|99.982|533.358|77.226|532.514|1694|
|B-summary|28.436|33.335|50.005|216.664|53.554|215.627|376|
|C-test128|28.449|33.334|50.005|216.669|53.060|215.639|389|
|absolute30|28.389|33.335|50.005|216.677|53.783|215.642|337|
|cooperative|28.442|33.334|50.005|216.672|52.439|215.643|363|
|work64|28.462|33.335|50.004|216.667|53.925|215.635|377|

実PRESENT fpsは連続完了区間から(N-1)/経過時間で算出。名目scene秒数あたりframe数とは異なる。PRESENT完了はCPU観測のDONE/tag/error/ACK後で、HDMI edgeそのものではない。absolute30とrelative33のdeadline定義も異なるためmiss数だけで順位を付けない。

## Scene別 実更新fps

|Scene|A-off|A-summary|A-detailed|B-summary|C-test128|absolute30|cooperative|work64|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|BOOT|30.353|30.151|20.000|30.151|30.151|30.050|30.151|30.151|
|HYPERSPACE|30.326|30.025|19.866|30.000|30.000|30.000|30.025|30.000|
|RASTER WAVES|29.975|29.975|14.962|29.975|29.975|29.975|29.975|29.975|
|PLASMA ENGINE|30.100|29.975|22.060|29.975|29.975|30.000|29.975|29.975|
|ROTOZOOM|30.120|30.020|17.269|29.960|29.980|29.980|30.020|30.020|
|BLIT STORM|30.320|30.301|29.960|30.280|30.320|30.020|30.240|30.301|
|VECTOR WORLD|24.582|18.678|7.970|18.558|18.593|18.628|18.558|18.678|
|FINALE|29.548|29.094|23.053|29.094|29.094|28.993|29.094|29.094|

## 長時間停止の位置

最悪callはいずれも約143秒、FINALE開始から3秒後の静的文字展開にある。A-offは143.167sで149.002ms。src/b16.cのcase7 / t>=3000で両pageへ初回letteringを展開する時刻と一致する。scene境界captionだけを最適化しても、この停止は残る。次の優先候補は画素等価なlettering矩形結合／展開手順の分割で、今回の8構成のソースとhashは変更しない。

## 計測負荷

OFF/SUMMARY/DETAILEDのfps差は、詳細計測が再生を乱すことを示す。regionはIRQ・計測自身を含む排他的wall-timeであり、CPU実行率／idle率へ換算しない。短いBENCH transactionはUSBログIRQ位相にも影響され、16反復の中央値でも一般的な定数補正とは扱わない。DETAILEDは診断専用とし通常再生には採用しない。

## DMA finite benchmark

以下はPCM ON、raw non-increment reg25 pointer WRITEの総時間中央値（16反復、us）。SDK PSRAM command全体とは区別する。

|B|A-summary CPU|B-summary DMA eligible >=64|C-test128 DMA eligible >=128|
|---:|---:|---:|---:|
|1|85.5|90.0|82.5|
|2|89.5|92.0|89.0|
|4|88.5|88.0|86.5|
|8|94.5|94.0|99.0|
|16|111.5|96.0|95.5|
|32|121.5|116.5|116.0|
|64|152.5|130.5|143.0|
|128|200.5|154.5|159.5|
|256|305.5|232.5|232.0|
|512|507.5|383.0|383.0|

64B以上でDMAの総時間短縮が観測された。測定範囲の評価候補閾値は64B。ただし採用閾値は変更しない。DMA waitはpollingのままでCPU仕事を同時実行しておらず、CPU解放量は未測定。本編描画のdescriptor/CSRは短く、長いuploadは素材展開時だけなので、DMAによる本編fps改善の根拠は得られていない。

凍結済み有限ベンチのscratchデータは全zeroであり、値を交互に変える実機DMAデータ完全性試験を代替しない。PC fakeはnonzero patternを検証した。PIO/READ方向/CSの独立logic analyzer波形、実機Framebuffer全byte oracleはNOT RUN。DMAの一般採用は保留する。

## CPU workと協調処理

work64: 19258 batches × 64 rounds = 1232512 rounds、定義した算術演算9860096回。演算区間wall-time 0.117891s、checksum=3484907162、再計算照合valid=1。

同条件A-summaryのdeadline miss 394、work64のmiss 377。元からVECTOR／境界で期限超過があるため、全frame期限を守れるCPU Headroom上限を証明したとは扱わない。1idle tickに1batchという試験量であり最大負荷sweepではない。実仕事量はMEASURED、deadline準拠の割当可能能力はNOT ESTABLISHED。

GPU待機協調処理の計測window内seed生成は236回、排他的wall-time 362us。CPU専用seed cacheのみで、DMAとの同時有効化なし。次frame VECTOR mask二重化やcore1は未実装。cooperative結果は1周の有限観測であり、わずかなfps差を有意な改善としない。

## 音声・保護・残る条件

|構成|音声span s|10ms低RMS欠落blocks|BGM相関 最低|全Flash試験後一致|
|---|---:|---:|---:|---|
|A-off|150.01|0|0.994783|PASS|
|A-summary|150.00|0|0.994861|PASS|
|A-detailed|150.01|0|0.993790|PASS|
|B-summary|150.01|0|0.994328|PASS|
|C-test128|150.01|0|0.994408|PASS|
|absolute30|150.00|0|0.994289|PASS|
|cooperative|150.01|0|0.994110|PASS|
|work64|150.00|0|0.994684|PASS|

8構成ともtimeout=0、PCM STATUS fault=0、STOP rc=0。音声は物理HDMI 48kHz/2ch capture、低RMS閾値20、10ms窓。各sceneのstinger後2秒を既知BGMへ相関照合。独立underrun counterはなく、全sampleの正常性保証ではない。BUSY overwriteの独立実機counterもなく、SDK直列化契約とPC回帰の範囲を区別する。

各書込み前に新しい2MiB backupを2回保存して一致確認。書込み後と試験後の全量一致、erase終端以降の保持、filesystem 0x100a0000以降の全構成同一を検証。既存backupと保護対象248ファイルのhash不変。元のFlashへ戻す場合は今回A-off/before.binを第一復旧像とし、既存backupを上書きしない。

最初のA-off demoはUSB再列挙raceで開始前に停止。開始markerもg送信もなく、完了済みbenchを繰り返さず、全Flash一致を再確認して未開始demoのみ継続した。再開時のログ上書き防止によるPC停止も記録。GPU timeout／不確定commandの再送は0。

単発・固定順序比較であり、反復周回／順序無作為化／温度PVT／物理波形の証明はない。VECTOR平均30fps、全sceneの安定30fps、長時間停止削減は未達。CPU＋PIOを既定に保ち、DMA／cooperative／schedulerの採用変更とGit releaseは行わない。実機は最後のwork64 firmwareを保持し、PCM停止、g/b明示開始gateで待機。

## 証跡

- [比較JSON](evidence/headroom-hardware/comparison.json)：全scene、PRESENT間隔、transition、profile、work、有限ベンチ、audio。
- [Flash ledger](evidence/headroom-hardware/flash-ledger.json)：各firmware・新backup・試験後全量hash。
- [Campaign](evidence/headroom-hardware/campaign.json)：段階と開始前停止の履歴。
- 原HDMI動画・WAV・復旧像：build/beyond16-headroom-20261106-120732（既存記録を上書きせず保管）。
