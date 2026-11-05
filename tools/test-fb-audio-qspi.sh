#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/prepare-hdmi-stream.py
mkdir -p build/audio-qspi
verilator --binary --assert --timing --timescale 1ns/1ps -Wno-fatal --top-module tb_fb_board_qspi --Mdir "$PWD/build/audio-qspi/obj" -j 4 -f rtl/fb/sources.f sim/support/kagura_fb_serializer_stub.sv sim/support/kagura_hyperram_pair_model.sv sim/tests/tb_fb_board_qspi.sv boards/tang-nano-9k/kagura_fb_top.sv > build/audio-qspi/build.log 2>&1
timeout 180 build/audio-qspi/obj/Vtb_fb_board_qspi | tee build/audio-qspi/run.log
