# Simulation

現行PCM2 ABI 1.4の回帰入口です。WSL/Linux、Verilator 5.032、Python 3、C11、g++、make、flock、timeoutを使用します。

```sh
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-fb-verilator.sh
KAGURA_STRICT_VERSION=1 KAGURA_SEED=1 bash tools/test-common-verilator.sh
bash tools/test-fb-audio-qspi.sh
bash tools/test-fb-wrap32.sh
bash tools/test-fb-wrap32-integration.sh
bash tools/test-fb-drivers.sh
```

`tests/`が単体・統合試験、`support/`が参照モデル・Host・HDMI・PSRAMモデルです。`sim/diagnostics/`は調査専用です。生成物とログは`build/`へ保存します。旧Kagura-9の試験も一部保持していますが、現行の入口は上記です。

採用Bitstreamの元PC/STA結果と再検証結果は[公開成果物](../releases/pcm2-qspi-final/README.md)を参照してください。シミュレーション結果と実機HDMI録画は区別します。
