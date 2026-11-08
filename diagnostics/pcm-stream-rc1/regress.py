#!/usr/bin/env python3
"""Run in WSL/Linux with Verilator; no synthesis or hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
diag = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--present-rx-stage', action='store_true')
parser.add_argument('--fill-end-adder', action='store_true')
parser.add_argument('--generation-carry', action='store_true')
parser.add_argument('--window-commit-merge', action='store_true')
parser.add_argument('--palette-ram', action='store_true')
parser.add_argument('--window-word-select', action='store_true')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
release = root / 'releases/queue8-qspi-deglitch-rc1'
baseline = release / 'build-inputs'
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
for name, expected in json.loads((release / 'source-input-manifest.json').read_text()).items():
    if digest(baseline / name).lower() != expected.lower():
        raise RuntimeError(f'RC1 hash mismatch: {name}')
inputs = out / 'inputs'
shutil.copytree(baseline, inputs)
patches = ['stream.patch', 'tx-sta.patch', 'window-sta.patch', 'control-sta.patch']
if args.present_rx_stage:
    patches.append('present-rx-sta.patch')
if args.fill_end_adder:
    patches.append('fill-end-sta.patch')
if args.generation_carry:
    patches.append('generation-sta.patch')
if args.window_commit_merge:
    patches.append('window-merge-sta.patch')
if args.palette_ram:
    patches.append('palette-ram-sta.patch')
if args.window_word_select:
    patches.append('window-word-sta.patch')
for name in patches:
    subprocess.run(['git', 'apply', '--ignore-space-change', str(diag / name)], cwd=inputs, check=True)
if args.present_rx_stage:
    assert 'reg [192:0] present_rx' in (inputs / 'rtl/fb/kagura_fb_scanout.sv').read_text()
if args.fill_end_adder:
    assert 'wire [9:0] rounded_end' in (inputs / 'rtl/fb/kagura_fb_fill_burst.sv').read_text()
if args.generation_carry:
    assert 'reg generation_carry' in (inputs / 'rtl/fb/kagura_fb_scanout.sv').read_text()
if args.window_commit_merge:
    assert 'reg [7:0] window_write_byte' in (inputs / 'rtl/fb/kagura_fb_registers.sv').read_text()
if args.palette_ram:
    assert 'palette_write_addr' in (inputs / 'rtl/fb/kagura_fb_scanout.sv').read_text()
if args.window_word_select:
    assert "data_addr[5:2]==4'(word)" in (inputs / 'rtl/fb/kagura_fb_registers.sv').read_text()
assert 'cursor_upper_carry' in (inputs / 'rtl/fb/kagura_fb_burst_ctrl.sv').read_text()
assert 'local_window_select' in (inputs / 'rtl/fb/kagura_fb_registers.sv').read_text()
assert 'g_stream' in (inputs / 'rtl/audio/kagura_pcm_prefetch.sv').read_text()
support = [root / 'sim/support/kagura_hyperram_pair_model.sv',
           root / 'sim/support/kagura_fb_serializer_stub.sv',
           root / 'third_party/hdl-util-hdmi/src/packet_assembler.sv']
scanout_test = root / 'sim/tests/tb_fb_scanout.sv'
fill_test = root / 'sim/tests/tb_fb_fill_burst.sv'
blit_test = root / 'sim/tests/tb_fb_blit.sv'
window_test = root / 'sim/tests/tb_fb_register_window.sv'
window_reference = root / 'sim/support/kagura_fb_registers_reference.sv'
files = sorted(p for p in inputs.rglob('*') if p.is_file()) + sorted(diag.glob('*.*')) + support
manifest = {str(p): digest(p) for p in files if p.is_file()}
test_display = args.present_rx_stage or args.generation_carry or args.palette_ram
if test_display:
    manifest[str(scanout_test)] = digest(scanout_test)
if args.fill_end_adder:
    for fixture in (fill_test, blit_test):
        manifest[str(fixture)] = digest(fixture)
if args.window_commit_merge or args.window_word_select:
    for fixture in (window_test, window_reference):
        manifest[str(fixture)] = digest(fixture)
(out / 'input-sha256.json').write_text(json.dumps(manifest, indent=2))
(out / 'version.txt').write_text(subprocess.check_output(['verilator', '--version'], text=True))
commands = []
def run(cmd, log):
    commands.append(cmd)
    (out / 'commands.json').write_text(json.dumps(commands, indent=2))
    with (out / log).open('w') as stream:
        subprocess.run(cmd, cwd=inputs, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=600)
def test(name, top, sources, options=(), seeds=(1,)):
    obj = out / name
    run(['verilator', '--binary', '--assert', '--timing', '--timescale', '1ns/1ps',
         '-Wno-fatal', '--top-module', top, '--Mdir', str(obj), '-j', '4',
         *options, *map(str, sources)], name + '-build.log')
    for seed in seeds:
        log = f'{name}-{seed}.log'
        run([str(obj / ('V' + top)), f'+verilator+seed+{seed}'], log)
        if 'PASS' not in (out / log).read_text():
            raise RuntimeError(f'Missing PASS: {log}')
        print((out / log).read_text(), flush=True)
if args.window_commit_merge or args.window_word_select:
    test('window', 'tb_fb_register_window', ['rtl/fb/kagura_fb_registers.sv',
         'rtl/fb/kagura_fb_upload_word.sv', window_test, window_reference])
if test_display:
    display = ['rtl/fb/kagura_fb_scanout.sv', 'rtl/fb/kagura_fb_line_banks.sv',
               'rtl/fb/kagura_fb_line_fetch.sv', 'rtl/memory/kagura_ram_tdp.sv']
    options = [f'-GCHECK_GENERATION={int(args.generation_carry)}']
    if args.palette_ram:
        options.append('-DKAGURA_TEST_PALETTE_RAM')
    test('present-rx', 'tb_present_rx', [*display, diag / 'tb_present_rx.sv'], options)
    test('scanout', 'tb_fb_scanout', [*display, 'rtl/fb/kagura_fb_arbiter.sv',
         'rtl/fb/kagura_fb_burst_ctrl.sv', support[0], scanout_test])
if args.fill_end_adder:
    memory = ['rtl/fb/kagura_fb_fill_burst.sv', 'rtl/fb/kagura_fb_burst_ctrl.sv', support[0]]
    test('fill', 'tb_fb_fill_burst', [*memory, fill_test])
    test('blit', 'tb_fb_blit', [*memory, 'rtl/fb/kagura_fb_commands.sv',
         'rtl/fb/kagura_fb_arbiter.sv', blit_test])
test('burst', 'tb_fb_burst_ctrl', ['rtl/fb/kagura_fb_burst_ctrl.sv', support[0], diag / 'tb_burst_carry.sv'], seeds=(1,19,73))
for replica in (0, 1):
    test(f'packet-{replica}', 'tb_packet_assembler', [support[2], 'rtl/hdmi/kagura_packet_assembler.sv', diag / 'tb_packet_assembler.sv'], [f'-GREPLICATE_FIRST={replica}'], (1,19,73))
test('stream', 'tb_stream', ['rtl/audio/kagura_pcm_prefetch.sv', diag / 'tb_stream.sv'])
test('board', 'tb_fb_board_qspi', [support[1], support[0], diag / 'tb_fb_board_qspi.sv', 'boards/tang-nano-9k/kagura_fb_top.sv'], ['-f', 'rtl/fb/sources.f'])
for name, expected in manifest.items():
    if digest(Path(name)) != expected:
        raise RuntimeError(f'Input changed during regression: {name}')
runs = 11 + 2 * test_display + 2 * args.fill_end_adder + (args.window_commit_merge or args.window_word_select)
(out / 'result.json').write_text(json.dumps({'passed': True, 'runs': runs, 'assertions': True}, indent=2))
print(f'PASS: complete RC1 STA regression ({runs} runs)', flush=True)
