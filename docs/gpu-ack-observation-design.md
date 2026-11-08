# 完了回収とACK待機の観測・次候補

対象は暫定承認の深さ8画像（SHA-256 `5592ae2cb18e4aa0bd70417b168a2d63d098bd3d14a5d19560636de7e6c97a77`）。
本書のABI拡張は設計候補であり、実装・実機投入していない。FPGA Flash変更はない。

## 現行プロトコルでsticky読出しとACKをまとめられるか

`rtl/bus/kagura_spi_adapter.sv` はheaderのrwでtransaction全体の方向を決める。
readはcount／dummy／data、writeはdata列で、同一CS内のread→write切替えや二つ目のheaderはない。
reg7のsticky読出しとreg31のACK書込みをそのまま一つにすることはできない。
ホスト関数を一つにまとめても、CSが二回ならtransaction削減にはならない。

reg7は`spi_late ? TRANSPORT_ERROR : sticky_error`を返す。完了errorだけでは代用できず、
statusのDONE／transport bitだけでもstickyの内容は代用できない。
reg31の現在のreadはIRQ値で、stickyではない。

次の案は採用しない。

- 完了情報のreadで自動ACK：ホストが誤tagやpartial-read IO失敗を検出する前にslotを消す。
- stickyを読まずACK、error確認の間引き：元のエラー確認契約を失う。
- reg7..31を広くreadして節約：data windowなど副作用のあるregisterを通る。
- read方向のままACK値を送る：現在のadapterはwriteとして解釈しない。

### 優先候補：stickyを完了snapshotへ隣接させる

将来の**別ABI・別bitstream**として、reg31のreadをreg7と同じsticky表示へ変更し、
reg31のwriteは従来のACKのままとする候補がある。
27..31の5-byte readでstatus／tag／completion error／stickyを取得し、
ホストがread成功、DONE、transport、tag、completion error、stickyを確認してから独立ACKする。
readにACK副作用を持たせない。

最初のDONEが0ならsnapshot全体を破棄しstatus-only pollへ戻る。
後からDONEを確認した場合は28..31の4-byte readでtag／error／stickyを取得する。
誤tag・IO・timeout・transportでACKせず停止、正tagのdevice errorは現行と同様に記録・ACK後fault latch、再送なし。
sticky clearを回収経路へ追加しない。

これは「stickyとACKを同一transaction化」ではなく、stickyを既存snapshotへ含めて
独立sticky readを一回減らす案である。ACK前の検証をホスト側に残せる。
現行のIRQ読出しABIを変えるため、明示的な実験ABI識別が必須。
例として専用minor値を割り当て、ホストがその値と構成を厳密に認識した場合だけ使う。
未認識・現在の画像では必ず現行経路へ戻す。既存capability byteは全bit使用済みなので流用しない。

成立条件の検証は、snapshot途中のDONE成立、tag周回／不一致、partial read、sticky error、
completion error、SPI late、reset、ACK失敗で行う。read時の副作用0も検証する。
errorがsticky取得後からACKまでに発生する窓は現行にもある。この案で閉じたとは主張しない。

### 条件付きACKを使う案

FPGAがACK受付時点でexpected tag・sticky・transportを検査し、異常ならslotを保持する設計は可能。
ただし現在のwriteにはホストへ「ACKを拒否した」ことを確定通知する応答契約がない。
拒否を黙って行うとホストだけがretiredを進めるため不可。
二相の要求／応答と一意なsequence、拒否理由、reset epoch、応答の保持、IO失敗時の照合を設計し、
追加確認readを含むtransaction数で比較する必要がある。現行write APIへの小変更では実現しない。

## 既存画像で観測できるACK待機の範囲

現行RTLのdispatch条件は次のとおり。

```text
cmd_valid = !reset && queue_count != 0 && !active && !completed
```

`completed && queue_count != 0 && !active`の各cycleは、後続descriptorがあるのに
未ACKの完了slotがdispatchを止めている。completedだけを数えると、後続がない正常な末尾保持も混ざる。
この区別が必要である。dispatch停止はHDMI／PCM停止を意味しない。

既存実機QRET reason=0は、software pending=8で最古を回収する経路に限定される。
1所有者・resetなし・エラーなしでは、DONE確認時点に完了slotのほか後続7件が残り、
次のACKはこの回収関数だけが発行する。
`q_done`（DONE read成功後）から`q_ack`（ACK呼出し直前）までは確実に完了を保持している。
既存の`metadata_us`はこの区間のtimestamp差であり、CPU処理・IOを含むが、その間dispatchが止まるという意味を持つ。

ただし完了の実際の成立はq_done以前、ACK受理はq_ack以後なので、これは保持全体の一部だけ。
snapshotではmetadata転送がpoll区間へ移るため、metadataの差をそのまま総停止時間の短縮としない。
poll＋metadata＋ACKも純GPU時間ではない。
1/64の周期sampleを全回数へ単純外挿せず、sample区間の合計と平均を報告する。
満杯回収以外にはこの「後続7件」の根拠を適用しない。

## RTL観測試験

`tools/test-fb-ack-observe.sh`は現行CSR→registered head→executor統合試験を外から観測する。
製品RTL・ports・CSRは変更しない。試験fixtureに既定0のACK遅延parameterだけを追加した。
reset区間を除き累積し、完了保持を「後続ありdispatch停止」と「後続なし」に分類する。
前者でcmd_validが立たないこともassertする。

深さ8×4周回の32完了についてACK遅延を0／100 cycleで比較した。

| カウンタ（simulation cycle） | 遅延0 | 遅延100 | 差 |
|---|---:|---:|---:|
| completed保持 | 577 | 3,777 | 3,200 |
| 後続ありdispatch停止 | 483 | 3,283 | 2,800 |
| 後続なし保持 | 94 | 494 | 400 |

末尾4件を除く28件だけで100 cycle分が実行再開を遅らせることを確認した。
これはcounterの意味とRTLの因果関係の検証であり、実機QSPI時間の再現や実測FPGA cycleではない。
[試験結果](evidence/gpu-completion-abab/ack-observer.json)。

## 実機内部cycleを直接取得する次の設計

必要なcounterは、総cycle、completed保持cycle、上記dispatch停止cycle、active cycle、
dispatch数、完了数、ACK受付数。clear／reset epochとoverflow状態も取得する。
複数byteを読む間の桁上がりを防ぐため、一度の明示要求で全counterをsnapshotし、
sequence付きの読出し窓へ固定する。読出しでACKやcounter clearを起こさない。
cursor／audioの既存addressへ無条件に重ねず、実験ABIの窓を設計する。

54 MHzでのcycle数を取得してはじめて、停止率とA/Bの差を直接比較できる。
観測回路もfanout・面積・タイミングを変えるため、新画像の機能試験・STA・hashを取り、
観測ONの同じ画像同士で比較する。現在の承認画像のSetup +0.050 nsを、新画像の保証へ流用しない。
今回のA/B/A/Bにはこの回路を投入せず、ホスト上の区間観測とsimulationまでを完了範囲とする。
