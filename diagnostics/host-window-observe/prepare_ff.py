from pathlib import Path
root=Path(__file__).resolve().parents[2];diag=Path(__file__).resolve().parent
source=(diag/'build.tcl').read_text()
ff=source.replace('rtl/fb/kagura_fb_upload_word.sv','diagnostics/host-window-observe/kagura_fb_upload_word_ff.sv')
assert ff!=source
(diag/'build-ff.tcl').write_text(ff)
out=root/'build/host-window-observe/sim-ff';out.mkdir(exist_ok=True)
tb=(root/'build/host-window-observe/sim/tb_window_observe.sv').read_text()
tb=tb.replace('module tb_window_observe #','module tb_window_observe_ff #')
tb=tb.replace('build/host-window-observe/sim/uart','build/host-window-observe/sim-ff/uart')
(out/'tb_window_observe_ff.sv').write_text(tb)
