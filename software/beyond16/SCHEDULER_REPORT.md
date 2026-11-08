> 実機8構成比較を実施：[最新結果](HARDWARE_HEADROOM_RESULT.md)。以下の実機未実行表記は投入前の記録。実仕事量は測定済み、期限準拠Headroom上限は未確立。release_ready=false。

# Scheduler and PRESENT

既定は現行relative33msを維持。B16_SCHEDULER=1でepoch起点のabsolute30Hzを比較できる。次slotはceil((floor(ms×30/1000)+1)×1000/30)。33ms固定の30.303Hzに対し、33/34msを配分し累積phase driftを避ける。遅延時は現在時刻から次slotへ飛び、古いframeを連続再生しない。音楽／scene時間は実時刻epoch基準で、frame数で進めない。

|方針|今回の状態|制約|
|---|---|---|
|33ms relative|実装・既定・PC回帰|実機比較NOT RUN|
|absolute30Hz|独立firmware／PC回帰|実機比較NOT RUN|
|HDMI vblankの2周期|設計比較のみ、未採用|ABIには独立したvblank timestampがない。DONE観測を真のvblank edgeと同一視しない|
|PRESENT完了基準|設計比較のみ、未採用|完了+33.333msではその後の描画時間も積算し、30Hzを下回る可能性|

2周期方式の実験はPRESENT DONE観測を位相のproxyとして、2/60sの絶対slotへ提出する設計。ただしpoll/Host遅延と描画時間予測の影響をcaptureで較正する必要がある。GPUのclock／ABI変更でtimestampを追加することはしない。比較前の採用はしない。

## 記録の意味

FRAME: ms（timeline）、draw_start_us、present_before_us、present_after_us、deadline_us、call us。present_beforeはSDK呼出前、present_afterはDONE/tag/error確認とACK成功後。frame終了にはその後のPCM poll等も含む。翌FRAMEのdraw_startも別時刻。下位32bit時刻は差分をmod2^32で扱う。

deadlineはrelative版ではdraw start+33333usのcall budget、absolute版では音楽epoch基準の次30Hz slot。relative版のmissをabsolute位相期限遵守と呼ばない。skipped counterは既存34ms近似なので合否の主指標に使わない。

tools/analyze_headroom_log.pyで同scene連続PRESENT間隔の中央値、nearest-rank p95、最悪、33.333ms超過率、実更新fps=(N-1)/最初から最後の完了間隔、記録deadline超過率、scene境界gap、次draw開始gapを計算する。最初／最後が欠ける窓のfpsと150秒平均を混同しない。33.333ms超過率は60Hz HDMI実周期の微差も受けるため単独合否にしない。

物理値は全てNOT RUN。既存host-ab-timing.jsonはFRAME開始+call時間の近似で、新しいPRESENT完了記録へ読み替えない。

原因分類: geometry/mask/rect/descriptor増加ならCPU、transaction begin/transfer/end増加ならHost、DONE待ち増加ならGPU/PSRAM候補、wire/DONE不変で提出位相・sleep/logが増加ならscheduler候補。wall-time分類だけで因果を確定せず、1要因ずつvariantとHDMI captureで確認する。
