# 実機検証計画 — 承認後に別作業として実施

初回の実機投入・1周録画を実施した。[実施結果](HARDWARE_RESULT.md)を参照。以下は当初の検証項目で、全分岐・全画面CRC・性能等の未完了項目も含む。後続の明示承認でRP2040 firmware Flashの変更を許可され、元Flashを退避し、既存filesystemを保持して書いた。`release_ready=false`を維持する。

1. 対象ボード・配線・Host所有者、既存候補04の保存hash、現在のFWと復帰手段を確認する。未解決Host／PSRAM試験結果を読み、合格に置き換えない。投入方式・Flashを変更する範囲は別途明示して承認を得る。
2. ABI 1.4、CAPS、メモリ排他を確認する。更新した5MHz PIOを実行する前に、SCK・CS・IOのターンアラウンドを測定できる試験構成を用意する。最初は音声停止、小さいmask WRITE／readbackから比較する。既存の低速診断transportは比較対照としてリポジトリに残るが、作品の既定経路には使わない。RMW・window境界・RX32の既知問題が再現したら作品試験へ進めず記録する。
3. 小さいFILL・奇数／偶数X・重なりBLIT・両ページ・PALETTE/PRESENT・cursorを試し、PCの期待画素と実機readbackを比較する。READ／FENCEの待ち時間を個別測定する。映像はHDMI captureでも確認する。
4. 背景・警告素材を小チャンクで転送し、配置表の範囲外へ書かないことを確認する。転送byte、コマンド数、各処理のwall time、最長main-loop停止、PRESENT ACK、場面切替準備時間を測定する。目標33.3msの予算に入らなければ未達として残す。
5. PCM0のみSTOP/CLEAR→転送・FENCE→PREPARE/READY→COMMIT、次にPCM1の決定音。PCM0を継続したままPCM1を切り替え、COMMIT snapshot保持、GAIN L/R、MASTER、loop端、STOP／再開、ERROR／UNDERRUNを検査する。
6. HDMI音声を48kHz signed16 stereoでcaptureし、無圧縮PCMの長さ、左右gain、無音・飽和・途切れを検査する。PC生成WAVを実機captureと称しない。エラー表示と映像fallbackも確認する。
7. 88秒autoplay、3分岐、点滅抑制、全シーンの復旧、複数周、resetを試す。Host速度とHDMI 60Hz scanoutを別々に報告する。初期ロード時間は作品内の88秒に黙って含めない。
8. 比較画像、CRC、転送ログ、音声、実測FPS、温度／電源条件、失敗したケースも保存する。計画の合格だけではReleaseにしない。FPGA RTL・Controller/PHY・PLL・SDC/CSTの変更が必要なら、このショーケースの範囲から分離する。

現在のRP2040 QSPIは、KAGURA-9の実績値を再利用した5MHz PIO（RP2040 120MHz、分周2）。組み立てたPIOのPCモデルと、候補04の実RTLを使う5MHz board-top機能試験に合格した。実用速度と非ブロッキング化の達成には、HD実機でのHost信号・実効転送速度の検証と、予算付きのロード／転送スケジューリングの確認が必要。初回ロードは論理再生時計より前に実行するが、場面切替の同期ロード時間はまだ実機計測していない。
