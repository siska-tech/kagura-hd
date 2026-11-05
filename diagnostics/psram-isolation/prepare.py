"""Offline provenance snapshot and paired 4B stimulus preparation. No hardware I/O."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/psram-isolation'
OUT.mkdir(parents=True, exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

records = []
for label, base in [('pass', ROOT), ('fail', ROOT / 'build/rx32-scanout-worktree')]:
    for relative in ['rtl/fb/kagura_fb_burst_ctrl.sv', 'rtl/memory/kagura_hyperram_phy_gowin.sv']:
        source = base / relative
        target = OUT / 'baseline' / label / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha(target) != sha(source):
            raise SystemExit('Refusing to replace baseline: ' + str(target))
        shutil.copyfile(source, target)
        records.append(dict(label=label, source=str(source.relative_to(ROOT)), sha256=sha(source)))

# Keep the known-good PDR1 serializer/FSM, change stimulus only in this copy.
engine = (ROOT / 'diagnostics/psram/psram_probe_engine.sv').read_text()
engine = engine.replace('TIMEOUT=100000', 'TIMEOUT=100000, EXACT_FAIL_PATTERN=0')
engine = engine.replace('make_pattern=data;', "if(EXACT_FAIL_PATTERN) data=512'h43210fed;\n            make_pattern=data;")
(OUT / 'psram_probe_engine.sv').write_text(engine)
tb = (ROOT / 'diagnostics/psram/tb_psram_probe.sv').read_text()
tb = tb.replace('FAULT=0);', 'FAULT=0, EXACT_FAIL_PATTERN=0);')
# RX32 optional outputs are explicitly terminated for the new controller.
tb = tb.replace('.valid(controller_valid),.*', '.valid(controller_valid),.rword_valid(),.rword_data(),.*')
tb = tb.replace('.WORDS(WORDS),.TIMEOUT(300)', '.WORDS(WORDS),.TIMEOUT(300),.EXACT_FAIL_PATTERN(EXACT_FAIL_PATTERN)')
tb = tb.replace("8'((300032+i)*37+((300032+i)>>8)*17+29)", "(EXACT_FAIL_PATTERN ? 8'(32'h43210fed >> (i*8)) : 8'((300032+i)*37+((300032+i)>>8)*17+29))")
tb = tb.replace('packet-w%0d-r%0d-f%0d.bin",WORDS,WRAP,FAULT', 'isolation-p%0d-w%0d-r%0d-f%0d.bin",EXACT_FAIL_PATTERN,WORDS,WRAP,FAULT')
(OUT / 'tb_psram_probe.sv').write_text(tb)
(OUT / 'baseline-manifest.json').write_text(json.dumps(records, indent=2) + '\n')
print(json.dumps(records, indent=2))

# Reuse the pin-level SPI/QSPI driver tasks, exclude the GPU core entirely.
original = (ROOT / 'sim/tests/tb_fb_host.sv').read_text()
tasks = original[original.index('    task byte_transfer'):original.index('    integer sys_cycles')]
prefix = original[:original.index('    wire initialized,video_underrun')]
prefix = prefix.replace('module tb_fb_host', 'module tb_host_isolation')
endpoint = original[original.index('    kagura_fb_host #'):original.index('    wire cursor_req_valid')]
endpoint = endpoint.replace('.enabled(initialized)', ".enabled(1'b1)")
endpoint = endpoint.replace('.video_error(video_underrun || memory_error)', ".video_error(1'b0)")
endpoint = endpoint.replace('.audio_error(audio_overflow || audio_underflow)', ".audio_error(1'b0)")
endpoint = endpoint[:endpoint.index('        .cursor_req_valid')] + '''        .cursor_req_valid(),.cursor_req_write(),.cursor_req_addr(),.cursor_req_wdata(),
        .cursor_req_ready(1'b1),.cursor_rsp_valid(1'b0),.cursor_rsp_error(1'b0),.cursor_rsp_data(8'd0),.cursor_irq(1'b0));
'''
suffix = '''
    assign present_ready=1;assign present_done=present_valid;
    wire [511:0] accepted_data;wire [63:0] accepted_mask;
    wire [19:0] accepted_addr;wire [4:0] accepted_words;wire accepted_write;
    psram_host_stub stub(.*);
    integer requests=0;
    always @(posedge clk) if(host_valid && mem_ready) requests<=requests+1;
    reg [127:0] descriptor;
    integer size,address;
    initial begin
        repeat(5) @(negedge clk);reset=0;wait(gpio_ready);
        for(integer n=0;n<5;n++) begin
            size=4<<n;address=300060;
            write_one(25,0);
            for(integer i=0;i<size;i++) txbuf[i]=8'(i*37+17);
            write_registers(24,0,size);
            write_one(25,0);read_registers(24,0,size);
            for(integer i=0;i<size;i++) if(rxbuf[i]!==8'(i*37+17)) $fatal(1,"upload echo");
            descriptor=0;descriptor[7:0]=4;descriptor[15:8]=8'(size/4);
            descriptor[31:16]=16'(n*2+1);descriptor[63:32]=32'(address);descriptor[127:64]=64'h0123456789abcdef;
            stage_command(descriptor);wait_tag(16'(n*2+1),0);
            if(accepted_addr!=address/4 || accepted_words!=size/4 || !accepted_write || accepted_mask!=64'h0123456789abcdef) $fatal(1,"request metadata");
            for(integer i=0;i<size;i++) if(accepted_data[i*8+:8]!==8'(i*37+17)) $fatal(1,"TX boundary");
            descriptor[7:0]=5;descriptor[31:16]=16'(n*2+2);descriptor[127:64]=0;
            stage_command(descriptor);wait_tag(16'(n*2+2),0);
            write_one(25,0);read_registers(24,0,size);
            for(integer i=0;i<size;i++) if(rxbuf[i]!==8'((address+i)*13+91)) $fatal(1,"independent RX injection byte=%0d",i);
        end
        // Invalid length is rejected by the actual command decoder, no stub request.
        descriptor[7:0]=4;descriptor[15:8]=0;descriptor[31:16]=100;
        stage_command(descriptor);wait_tag(100,3);
        if(requests!=10) $fatal(1,"invalid request reached memory");
        // Pointer at the window end must report an error, never wrap to byte zero.
        write_one(7,0);write_one(25,64);write_one(24,255);read_registers(7,0,1);
        if(rxbuf[0]!=5) $fatal(1,"window end did not report buffer error");
        @(negedge clk);reset=1;repeat(4) @(negedge clk);
        if(host_valid) $fatal(1,"reset request");reset=0;wait(gpio_ready);
        write_one(25,0);read_registers(24,0,64);
        for(integer i=0;i<64;i++) if(rxbuf[i]!=0) $fatal(1,"reset window");
        $display("PASS: host isolation LANES=%0d 4/8/16/32/64B TX, independent RX, invalid length, window end, reset; no PSRAM instance",LANES);
        $finish;
    end
    initial begin #100000000;$fatal(1,"watchdog");end
endmodule
'''
(OUT / 'tb_host_isolation.sv').write_text(prefix + endpoint + tasks + suffix)
