from pathlib import Path
root=Path(__file__).resolve().parents[2];diag=Path(__file__).resolve().parent
source=(diag/'build.tcl').read_text()
(diag/'build-rmw.tcl').write_text(source.replace('rtl/fb/kagura_fb_upload_word.sv',
    'diagnostics/host-window-observe/fix-candidates/kagura_fb_upload_word_rmw.sv'))
out=root/'build/host-window-observe/sim-rmw';out.mkdir(exist_ok=True)
tb=(root/'build/host-window-observe/sim/tb_window_observe.sv').read_text()
tb=tb.replace('module tb_window_observe #','module tb_window_observe_rmw #')
tb=tb.replace('build/host-window-observe/sim/uart','build/host-window-observe/sim-rmw/uart')
(out/'tb_window_observe_rmw.sv').write_text(tb)
source=(root/'build/psram-isolation/board-sim/gowin_SP_sim.v').read_text()
guard='''
// Conservative capability gate: this test only permits complete word writes.
// It rejects byte-enable dependence, not a model of a particular silicon fault.
always @(posedge CLK) if(CE && WRE && AD[3:0]!=4'hf)
    $fatal(1,"native byte-enable dependence rejected by full-word-only gate");
'''
(out/'gowin_SP_fullword_guard.v').write_text(source.replace('endmodule',guard+'endmodule'))
