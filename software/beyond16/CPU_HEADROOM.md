# CPU headroom：現在使える時間と非同期化候補

最新Host ON実機ログを再解析。実機追加操作なし。対象は描画main loopを実行するcore0。RP2040全体の2core合算CPU使用率ではない。

148.95秒の同一windowで、描画call105.430秒、call外43.520秒、Host callback87.357秒、call内かつHost外18.074秒。率はそれぞれ70.8%、29.2%、58.6%、12.1%。PERF.msはcall開始前、counterはcall後なので境界にframe長の誤差がある。

## 現状のCPU空き時間

core0上で現在そのまま他の処理を呼べる場所は、同期b16_tickが返ってから次frameを始めるまで。call外29.2%はその候補windowの大まかな上限で、保証された空き時間ではない。sleep_ms、USB入力確認、描画不要tick、PERF/BUS文字出力、計測、割込み処理を含み、それらの時間が未分離。全scene共通の29.2%余力でもない。

scene内部windowにおけるcall外率：BOOT40.1%、HYPERSPACE39.8%、RASTER3.1%、PLASMA48.3%、ROTO16.7%、BLIT47.2%、VECTOR4.4%、FINALE56.3%。scene境界を除いた各windowを使用。FINALEは静的表示区間を含む。平均の候補時間で、連続して確保できる最大時間は不明。

sleep中はcore0へ任意のmain処理を現在実行していない。他の仕事を入れるならsleep前の協調callbackなどが必要。CPUがWFEで停止している割合と、deadlineを守って他の処理へ割当可能な割合は別。IRQを使えば描画call中にも動けるが、実行時間次第で通信を遅らせるため、余裕の証明にはならない。

## 改善可能なCPU余力

Host callback58.6%は非同期化の検討対象であり、解放可能量ではない。begin/endのGPIO・方向切替・descriptor準備等はCPU実行が必要。transferはFIFO供給・回収・deadline確認のCPU仕事とPIO待ちが混在。DONE pollingのtransactionはCPU仕事で、GPU待ち自体と同じではない。PRESENT待ちも未分離。

DMAでFIFO供給・回収を任せて他の計算を進める、IRQや協調schedulerでGPU完了待ちをyieldする、次frameの座標/maskを空き時間に計算する候補がある。queue1を維持し、未完了中のdescriptor上書きや描画page誤使用をしない。短CSRではDMA設定費もあり58.6%全ては回収できない。専用mask workspaceの二重buffer／ownerも必要。

## 正確な追加測定

同じfirmware条件の計測variantで以下を記録する。

- main：描画call、描画不要tick、USB入力、ログ出力、sleep実経過時間を排他的に集計。sleepはIRQ実行時間も含むためCPU停止時間と呼ばない。
- render：座標計算／mask生成／矩形抽出、SDK投入、command完了待ち、PRESENT完了待ち。入れ子のHost時間は親区間から引くときだけ差分化し、単純加算しない。
- transport：FIFOに進捗のない待ちiteration、CPU供給／回収、終端停止待ちを分離。毎iteration時刻取得は測定負荷が大きく、サンプル計測とON/OFF比較を併用する。
- reclaim実証：期限付きの既知CPU仕事をmainの余白へ入れ、達成work量とframe miss、音声faultを測る。DMA/IRQ版でも同じ仕事を実行して増えたwork量を比較する。microsecond計測だけで非同期化による解放量を断定しない。

現状の厳密なCPU空き率と非同期回収可能率は未測定。数値を捏造せず、evidence/cpu-headroom-bounds.jsonではnullとした。解放CPU時間が増えてもGPU待ちや転送線上時間は残るため、fps向上と同義ではない。
