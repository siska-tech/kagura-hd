# KAGURA-HD XIAO keyboard bridge

Seeed XIAO RP2040でUSB HID boot keyboardを受信し、XLINK UART経由で
PicoのMicroPython REPLへ入力するHD専用FWです。
ユーザーの`kagura-6502/xiao/firmware`からUSB Host・キー差分処理・XLINKを再利用し、
元の6502版のソースやFWは変更していません。

## 接続と動作

| 信号 | XIAO | Pico / キャリア |
|---|---|---|
| UART TX | D6 / GP0 | Pico GP1 RX |
| UART RX | D7 / GP1 | Pico GP0 TX |
| USB Host D+ / D− | D4 / GP6、D5 / GP7 | キャリアのUSB-A |
| UART条件 | 115200 baud、8N1 | 3.3V UART、GND共通 |

キャリアRevAのUART配線と一致します。USB-AのVBUS保護回路とJP1等の給電経路を
設計どおり実装してください。キャリア給電中にXIAO本体のUSB-CをPCへ同時接続しないでください。

UART TXはPico側RX線が5 ms以上highになるまで入力状態を保ちます。
Pico側もRXが5 ms以上highになるまでUART受信を開始しません。未設定・未給電の
XIAOでRXがlowのままなら、USB REPLを残して待機します。
6502のRESET/NMI、K65 status監視、boot menu、イメージ転送、LittleFSは使いません。
アプリからFlashを書き込む処理もありません。

Picoへ`kagura_keyboard.py`と更新版`kagura_console.py`を配置します。
`kagura_console.start()`で標準有効、`keyboard=False`で無効化できます。
USB REPL入力も併用可能です。UARTそのものを`os.dupterm`へ渡さず、
CRC検証済みKEY eventを文字や制御sequenceへ変換して`Console.readinto()`から渡します。
Ctrl-Cはsoft timerから`os.dupterm_notify()`で実行中のPythonへ通知します。

対応: 日本語109キー配列のASCII、Shift、Caps Lock、キーリピート、Enter、Escape、
Backspace、Tab、矢印、Home/End、Insert/Delete、Page Up/Down、Ctrl-A〜Z、AltのESC prefix。
Ctrl-D soft resetやCtrl-E paste mode等の動作はMicroPythonの仕様に従います。
Caps LockのUSB LED更新、かな漢字IME、NKRO・独自レポート形式は未対応です。

状態は`kagura_console.console.keyboard`の`bridge_version`、`connected`、`events`、
`bad_frames`、`dropped`で確認できます。旧6502 FWもKBD_CFG後のKEY frameは受信できますが、
旧supervisorやboot処理は残り、HD statusを返さず、一部のShift記号も異なります。

## プロトコル

`7E type length payload CRC8`。CRCはtypeからpayloadまで、多項式07、初期値0、MSB-first。

- `01 KEY`: `[HID usage, modifiers, flags, code]`。down=1、repeat=2、Shift=4、Ctrl=8、Alt=16。
  up eventはREPLへ渡しません。
- `83 KBD_CFG`: `[enable, 1, delay_lo, delay_hi, period_lo, period_hi, 0]`。
  delay=250〜2000 ms、period=10〜500 ms。初期値は有効、500/33 ms。
- `85 HD_HELLO`: `KHD1`。
- `C5 HD_STATUS`: `KHDK version connected`、version=1、connected=0/1。
  TX有効化時、HELLO時、通常は1秒ごとに送信します。

Picoは64-byte超・CRC不一致のframeを破棄し、100 ms中断時に再同期します。
ring満杯時はESC sequence全体を破棄し、Ctrl-Cは別枠で優先します。

## ビルド・書込み

Pico SDK 2.2.0とPico-PIO-USB commit
`b186e36bea0f3bcc2ee94ca1fa81e7f71281443a`を使用します。

```sh
cmake -S software/xiao_keyboard -B build/xiao-keyboard/firmware \
  -DPICO_SDK_PATH=/path/to/pico-sdk-2.2.0 \
  -DPICO_BOARD=seeed_xiao_rp2040 -DCMAKE_BUILD_TYPE=Release
cmake --build build/xiao-keyboard/firmware -j4
```

出力は`kagura_hd_xiao.uf2`。Flashの最初の256 KiBだけへリンクし、既存保存領域は使用しません。
現物のFlash全体を退避してから、UF2の書込みアドレスを確認して配置してください。
`-DXIAO_BRIDGE_RAM=ON`でRAM専用ELFも作れます。

書込み時はキャリアとPico USBを両方切り、XIAOをキャリアから取り外して、
XIAOだけをPCへBOOTSEL接続する方法を推奨します。
USB CDCは`CAFE:4011`、製品名`KAGURA-HD XIAO keyboard`。
CDCへ`BOOTSEL\n`を送るとROM bootloaderへ入ります。

## 出典・テスト

`vendor/`の元ファイル・変更後hashは`vendor/provenance.json`に記録しています。
usb_hostのpointer includeと、USB製品名・PIDだけを調整しています。
Pico SDK、TinyUSB、Pico-PIO-USBは各原本のライセンスに従います。

```sh
PYTHONPATH=software/kagura_fb python software/kagura_fb/tests/test_keyboard.py
cc -std=c11 -Wall -Wextra -Werror -Isoftware/xiao_keyboard/vendor -Isoftware/xiao_keyboard \
  software/xiao_keyboard/test_bridge.c software/xiao_keyboard/bridge.c \
  software/xiao_keyboard/vendor/keymap.c software/xiao_keyboard/vendor/keyboard_edges.c -o /tmp/test_bridge
/tmp/test_bridge
```

CRC、分割受信、破損・中断からの復帰、キー解放／リピート、編集・Ctrlキー、
ring overflow、status、JIS記号・Caps Lock・差分イベントを検証します。
FWはSDK 2.2.0でビルド確認済みです。USB現物・給電・UARTの実機確認は別途必要です。

2026-11-23、XIAOへUF2を書込み、picotoolの読戻し照合と、USB CDCで
`KAGURA-HD XIAO keyboard bridge v1`の応答を確認しました。
ユーザー指定により書込み前のFlash退避は省略しています。
同日、キャリアへ戻した状態でUARTのbridge_version=1、USBキーボード接続、
KEY event受信、CRC error 0、入力破棄0を確認しました。
ユーザーによる`help()`と`2+3`→`5`の入力も確認済みです。
