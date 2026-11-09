#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Optional SPI (HOST_LANES=1) regressions with the rtl/spi/ overlay applied the
# same way tools/build-fb.tcl applies it. The QSPI selected build never uses it.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python3 tools/prepare-hdmi-stream.py
out="${KAGURA_SPI_TEST_DIR:-build/fb-spi}"
mkdir -p "$out"
exec 9>"$out/.lock"
flock -n 9 || { echo "SPI regression already running" >&2; exit 1; }
# sources.f with rtl/spi/ replacements.
while read -r path; do
    [ -z "$path" ] && continue
    overlay="rtl/spi/$(basename "$path")"
    if [ -f "$overlay" ]; then echo "$overlay"; else echo "$path"; fi
done < rtl/fb/sources.f > "$out/sources-spi.f"
common=(-f "$out/sources-spi.f" sim/support/kagura_fb_serializer_stub.sv sim/support/kagura_hyperram_pair_model.sv)
run() {
    local name=$1 top=$2 expect=$3; shift 3
    mkdir -p "$out/$name"
    verilator --binary --assert --timing --timescale 1ns/1ps -Wno-fatal --top-module "$top" \
        --Mdir "$root/$out/$name" -j 4 "$@" > "$out/$name/build.log" 2>&1
    timeout 900 "$out/$name/V$top" > "$out/$name/run.log" 2>&1 || true
    if grep -q "$expect" "$out/$name/run.log"; then echo "ok   $name"; else echo "FAIL $name"; tail -5 "$out/$name/run.log"; exit 1; fi
}
# The overlay scanout is compared with the frozen one under another name.
sed 's/^module kagura_fb_scanout /module kagura_fb_scanout_spi /' rtl/spi/kagura_fb_scanout.sv > "$out/kagura_fb_scanout_spi.sv"
grep -q '^module kagura_fb_scanout_spi ' "$out/kagura_fb_scanout_spi.sv"
scanout=(rtl/fb/kagura_fb_scanout.sv "$out/kagura_fb_scanout_spi.sv" rtl/fb/kagura_fb_line_banks.sv rtl/fb/kagura_fb_line_fetch.sv rtl/memory/kagura_ram_tdp.sv)
for seed in ${KAGURA_SPI_SEEDS:-1 2 3}; do
    run "palette-bsram-s$seed" tb_fb_palette_bsram 'PASS: palette BSRAM' -GSEED="$seed" "${scanout[@]}" sim/tests/tb_fb_palette_bsram.sv
done
for mailbox in 0 1; do
    run "cursor-mailbox$mailbox" tb_fb_cursor 'PASS: fb_cursor' -GPIPELINE_MAILBOX="$mailbox" sim/support/kagura_fb_cursor_reference.sv \
        rtl/spi/kagura_fb_cursor.sv rtl/memory/kagura_ram_tdp.sv sim/tests/tb_fb_cursor.sv
done
for glitch in 20 40; do
    run "cs-glitch-$glitch" tb_spi_cs_glitch 'PASS: SPI /CS' -GFILTER=1 -GGLITCH_NS="$glitch" rtl/spi/kagura_spi_adapter.sv sim/tests/tb_spi_cs_glitch.sv
done
# Sensitivity: without the qualification a 20 ns glitch must break the frame.
run cs-glitch-unfiltered tb_spi_cs_glitch 'RESULT FAIL' -GFILTER=0 -GGLITCH_NS=20 rtl/spi/kagura_spi_adapter.sv sim/tests/tb_spi_cs_glitch.sv
run host-l1-q8 tb_fb_host 'PASS: queued fb_host LANES=1 depth=8' -GLANES=1 -GQUEUE_DEPTH=8 -GREGISTER_AUDIO_CREDITS=0 \
    -GREPLICATE_PACKET_FIRST=1 "${common[@]}" sim/tests/tb_fb_host.sv
run board-l1-q8 tb_fb_board_qspi 'PASS: PCM2 board LANES=1' -GLANES=1 "${common[@]}" \
    diagnostics/pcm-stream-rc1/tb_fb_board_qspi.sv boards/tang-nano-9k/kagura_fb_top.sv
echo "PASS: SPI overlay regressions"
