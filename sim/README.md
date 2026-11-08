# Simulation

現行PCM2 ABI 1.4の回帰入口です。WSL/Linux、Verilator 5.032、Python 3、C11、g++、make、flock、timeoutを使用します。

```sh
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-fb-verilator.sh
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-common-verilator.sh
bash tools/test-fb-audio-qspi.sh
bash tools/test-fb-wrap32.sh
bash tools/test-fb-wrap32-integration.sh
bash tools/test-fb-drivers.sh
bash tools/test-fb-command-queue.sh
bash tools/test-fb-ack-observe.sh
bash tools/test-fb-decode.sh
bash tools/test-fb-cursor-pipeline.sh
bash tools/test-audio-credit-predicate.sh
bash tools/test-packet-first.sh
bash tools/test-fb-queue-host.sh
```

`tests/`が単体・統合試験、`support/`が参照モデル・Host・HDMI・PSRAMモデルです。`sim/diagnostics/`は調査専用です。生成物とログは`build/`へ保存します。旧Kagura-9の試験も一部保持していますが、現行の入口は上記です。

採用Bitstreamの元PC/STA結果と再検証結果は[公開成果物](../releases/pcm2-qspi-final/README.md)を参照してください。シミュレーション結果と実機HDMI録画は区別します。

受付Queue深さ2/4/8の実験用候補とプロトコル制約は
[GPU command queue](../docs/gpu-command-queue.md)を参照してください。製品既定は深さ1です。

`test-fb-ack-observe.sh`は未ACKによるdispatch停止と、後続がない完了保持を区別し、
制御したACK遅延の差を検証します。実機cycle測定ではありません。
[観測範囲と将来の実機counter設計](../docs/gpu-ack-observation-design.md)を参照してください。
