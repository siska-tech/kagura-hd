# KAGURA-HD ハードウェアカーソル（ABI 1.2、1.1 で導入）

> 描画・カーソルのAPI契約はABI 1.4へ継承しています。本文の資源・STA・検証計画は開発時点の記録で、現行のPCM2構成・実機結果は [README](../README.md) を参照してください。


論理32×32・2bpp、色0透明・色1～3は専用RGB444のカーソルを実装します。映像では整数2倍の64×64画素です。画面側16色パレットから独立し、フレームバッファとPSRAMには書き込みません。形状は256 B×2バンク、追加BSRAMは1個です。

描画命令とは別のCSR窓なので、FILLやPRESENTのBUSY中にも位置を投入できます。HOST_BUSYピンは描画命令用です。カーソルの待機判定にはCSR50を使います。カーソル形状・色・ホットスポットは非表示バンクへ転送し、位置・選択バンク・表示状態を垂直帰線で一括反映します。

位置はホットスポットの論理座標で、x/yは符号付き -1024～1023、ホットスポットは各0～31です。画面外はクリップします。形状内の画素は各バイトの上位2bitから左→右、1行8 B、32行です。

## C／MicroPython API

Cは `kfb_cursor_shape`、`kfb_cursor_move`、`kfb_cursor_status`、`kfb_cursor_wait` を使います。形状データは256 B、色は3個のuint16_t RGB444です。moveは非同期の投入、waitは反映待ちです。エラー時に不確かな転送を自動再送しません。既存のkfb_device構造体は変更していません。

MicroPythonの例です。呼出しは同じデバイスについて直列化します。

```python
from kagura_fb import connect_rp2040

gpu = connect_rp2040()
status, generation = gpu.cursor_status()
if status & 1:
    gpu.cursor_wait()
    status, generation = gpu.cursor_status()
bank = 1 - ((status >> 1) & 1)
shape = bytearray(256)
for y in range(24):
    for x in range(y // 2 + 1):
        color = 2 if x == 0 or x == y // 2 else 1
        shape[y * 8 + x // 4] |= color << ((3 - x % 4) * 2)
gpu.cursor_shape(bank, shape, (0xfff, 0x000, 0x09f), (0, 0))
gpu.cursor_move(120, 80, bank)  # 描画命令の完了を待たずに投入
# 他のCPU処理を行える
generation = gpu.cursor_wait()
gpu.cursor_move(121, 81, bank)
gpu.cursor_move(122, 82, bank)  # 待機中の更新は最新位置へ集約
# 非表示も垂直帰線で反映
gpu.cursor_wait()
gpu.cursor_move(122, 82, bank, visible=False)
gpu.cursor_wait()
```

描画側も非同期にする場合は `gpu.submit(command)` / `gpu.wait(tag)`、Cは `kfb_submit` / `kfb_wait` を使えます。待機中にcursor_moveを投入し、GPUとカーソルの完了を別々に確認します。

形状の転送先は必ず非表示バンクを選び、カーソル反映が保留中なら先にwaitします。形状転送はGPU BUSYから独立していますが、選択中・反映保留中のバンクは書けません。転送失敗したバンクを表示せず、offset 0から256 Bを再転送して成功を確認してください。

## レジスタとワイヤ形式

KFB1 major=1、minor=1、CSR6のbit5がcursor capabilityです。SPIヘッダは `bit7=read, bit6=increment, bit5:0=address` になり、増分は64アドレスで折り返します。旧0～31への通常アクセスは同じです。Cのレジスタ転送コールバックも6bitアドレスをマスクせず送る必要があります。PythonのSPITransportは対応済みです。旧Kagura-9用adapterは既定5bitのままです。

|絶対CSR|機能|
|---|---|
|32|書込み：staging control：bit0 visible、bit1 bank。ほか0|
|33–34|書込み：staging x、signed16 LE（有効範囲 -1024～1023）|
|35–36|書込み：staging y、signed16 LE（同上）|
|37 / 38|書込み：編集バンクのhotspot x/y、0～31|
|39–44|書込み：編集バンクの色1、2、3、RGB444各16bit LE。上位4bitは0|
|46|書込み：画像バイトoffset、0～255。書込みで終端フラグを解除|
|47|書込み：編集バンク、0/1|
|48|画像DATA書込み。offset自動増分。256 B到達後の追加書込みは拒否|
|49|書込み1：staging位置・bank・visibleをcommit|
|50|読出しstatus。書込みbit6=1：cursor completion IRQを解除|
|51–52|反映済み世代番号16bit LE。51読出しで上位byteをスナップショット|
|53|cursor sticky error。任意値の書込みで解除|

読戻しはCSR50～53のみです。位置・形状・色・編集ポインタの設定値はアプリ側で保持し、それ以外の読出しは0です。未使用CSRへの書込みはエラーです。画像はoffset 0から順番に256 B書いて有効化します。途中・順番違い・未転送の形状を表示するcommitは拒否します。

CSR50：bit0 pending、bit1 active bank、bit2 active visible、bit3 latest slot使用中、bit4 bank0形状有効、bit5 bank1形状有効、bit6反映完了、bit7=0。エラーは1 busy、2不正設定／順番、3範囲、5画像窓終端、7未完成形状です。カーソル完了／エラーもIRQ_nへ接続し、GPU側のCSR31とは独立して解除します。

## 所有権と反映

有効バンクと、mailboxまたはlatest slotが参照するバンクは、画像・色・ホットスポットの変更を拒否します。画像をCPUが書くsystem portと映像が読むpixel portを別クロックで使います。bank解放はpixel側の反映ackをsystem側で同期してから行います。

mailbox内の位置はackまで保持します。その間のcommitは1個のlatest slotを置き換えます。ackと新commitが同時なら新しい位置を優先します。これにより描画キューを塞がず、途中の位置を集約できます。最初の保留位置は次の垂直帰線、latest slotは続く垂直帰線で反映されます。

世代番号は実際の反映ごとに増え、65535の次は0です。commitの発行数とは異なります。waitはlatest slotまで空になった時点の世代を返します。位置ごとのCPU実測遅延・p95は未測定です。

system/pixel resetは同時にassertします。リセットで両バンクの形状有効フラグ、mailbox、IRQ、世代を無効化し、カーソルを非表示にします。BRAMの古い内容は再転送なしには表示できません。

画素側は4画素先読みで座標、BRAM、2bit抽出をパイプライン化します。カーソルCSR要求は独立したレジスタ付きディスパッチで処理します。最後の合成レジスタを既存HDMI入力レジスタと置き換え、背景と映像タイミングの遅延を維持します。ホットスポットを引いた左上座標はcommit時に計算し、画素ごとの加算を減らしています。

## 検証

単体試験は全画面を独立の画像式と照合し、透明色、専用色、2倍拡大、負座標、四辺のクリップ、ホットスポット、bank切替、最新位置の集約、無効／部分形状、active bank書込み拒否、IRQ、保留中reset、RAM衝突を確認します。SPI/QSPI結合試験は実ピンのパケットから、GPU BUSY中の位置commitとHDMI入力への合成までを検査します。

C/Pythonのモデル試験と実MicroPython Unixでは、GPU処理と独立した形状転送・移動、世代の折返し、timeout、旧firmwareの拒否、不確かなsubmitの非再送を検査します。物理DDR、CDCの最終signoff、実機のレイテンシは別途確認が必要です。

カーソル単独追加時点の履歴（2026-11-04）：RTL全23試験、C/Python共通13試験、実MicroPython Unix試験が通過。単体画素照合は7,425,407画素です。カーソル込みの数値STAはSPI setup +0.170 ns / hold +0.552 ns、QSPI setup +0.274 ns / hold +0.405 ns、setup/hold違反はいずれも0。実機・外部PSRAMタイミング・最終CDC signoffは未検証です。[詳細な資源・検証記録](kagura-fb-implementation.md)を参照してください。


BLIT統合後の現在値：RTL全26試験、C/Python15試験、実MicroPythonが通過。
単体画素照合は7,425,424画素。CSRは入力を保持・検証して2 sys edgeで応答し、
COMMITの値判定を先に登録する。色もSYS側のheld mailboxへ同時保存し、画素側の
bank選択muxを除いた。所有権・最新位置集約・vblank反映・6bitレジスタ仕様は維持する。
SPI setup +1.122 ns / hold +0.558 ns、QSPI setup +0.660 ns / hold +0.552 nsで
違反0。[最新のBLIT統合記録](kagura-fb-implementation.md)を参照。
