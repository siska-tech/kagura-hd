`timescale 1ns/1ps
// Compare observable effects, not cycle numbers, against the released decoder.
module tb_fb_decode_equivalence #(parameter bit AUDIO_CSR=1);
    reg clk=0,reset=1,valid=0;
    always #5 clk=~clk;
    reg [127:0] command=0;
    reg memory_error=0,audio_busy=0,audio_settle=0,audio_settings_valid=1,audio_apply_error=0;
    wire [1:0] ready,done,host_valid,host_write,read_result,present_valid,present_page;
    wire [1:0] audio_capture,audio_apply,audio_commit_done;
    wire [1:0][7:0] error;
    wire [1:0][15:0] tag;
    wire [1:0][19:0] host_addr;
    wire [1:0][4:0] host_words;
    wire [1:0][511:0] host_wdata;
    wire [1:0][63:0] host_mask;
    wire [1:0][191:0] palette;
    reg [1:0] host_done=0,present_done=0,audio_done=0,seen=0;
    reg [601:0] trace [0:1][0:255];
    integer length[0:1],reads[0:1],presents[0:1],captures[0:1],applies[0:1],commits[0:1];
    reg [7:0] result_error[0:1];
    reg [15:0] result_tag[0:1];
    for(genvar mode=0;mode<2;mode++) begin: engines
        kagura_fb_commands #(.AUDIO_CSR(AUDIO_CSR),.REGISTER_DECODE(mode==1)) dut(
            .clk,.reset,.valid,.ready(ready[mode]),.command,.upload_data({16{32'h2468ace0}}),
            .done(done[mode]),.error(error[mode]),.tag(tag[mode]),.read_data(),.read_result(read_result[mode]),
            .host_valid(host_valid[mode]),.host_ready(1'b1),.host_write(host_write[mode]),
            .host_addr(host_addr[mode]),.host_words(host_words[mode]),.host_wdata(host_wdata[mode]),.host_mask(host_mask[mode]),
            .host_done(host_done[mode]),.host_error(memory_error),.host_rdata({16{32'h12345678}}),
            .present_valid(present_valid[mode]),.present_ready(1'b1),.present_done(present_done[mode]),
            .present_page(present_page[mode]),.present_palette(palette[mode]),
            .audio_capture(audio_capture[mode]),.audio_apply(audio_apply[mode]),.audio_commit_done(audio_commit_done[mode]),
            .audio_settings_valid,.audio_busy,.audio_settle,.audio_ready(1'b1),.audio_done(audio_done[mode]),.audio_apply_error);
        always @(posedge clk) begin
            host_done[mode]<=!reset && host_valid[mode];
            present_done[mode]<=!reset && present_valid[mode];
            audio_done[mode]<=!reset && audio_apply[mode];
            if(!reset) begin
                if(host_valid[mode]) begin
                    if(length[mode]>=256) $fatal(1,"trace capacity");
                    trace[mode][length[mode]]={host_write[mode],host_addr[mode],host_words[mode],host_wdata[mode],host_mask[mode]};
                    length[mode]=length[mode]+1;
                end
                if(read_result[mode]) reads[mode]=reads[mode]+1;
                if(present_valid[mode]) presents[mode]=presents[mode]+1;
                if(audio_capture[mode]) captures[mode]=captures[mode]+1;
                if(audio_apply[mode]) applies[mode]=applies[mode]+1;
                if(audio_commit_done[mode]) commits[mode]=commits[mode]+1;
                if(done[mode]) begin
                    seen[mode]=1;result_error[mode]=error[mode];result_tag[mode]=tag[mode];
                end
            end
        end
    end
    integer cases=0;
    task check(input [127:0] descriptor);
        wait(&ready);@(negedge clk);
        seen=0;
        for(integer mode=0;mode<2;mode++) begin
            length[mode]=0;reads[mode]=0;presents[mode]=0;captures[mode]=0;applies[mode]=0;commits[mode]=0;
        end
        command=descriptor;command[31:16]=16'(cases);valid=1;
        @(negedge clk);valid=0;
        while(seen!=2'b11) @(negedge clk);
        if(result_error[0]!==result_error[1] || result_tag[0]!==result_tag[1] ||
           result_tag[1]!==16'(cases) || palette[0]!==palette[1] || length[0]!=length[1] ||
           reads[0]!=reads[1] || presents[0]!=presents[1] || captures[0]!=captures[1] ||
           applies[0]!=applies[1] || commits[0]!=commits[1])
            $fatal(1,"decode mismatch case=%0d desc=%h errors=%0d/%0d traces=%0d/%0d",cases,descriptor,result_error[0],result_error[1],length[0],length[1]);
        for(integer i=0;i<length[0];i++)
            if(trace[0][i]!==trace[1][i]) $fatal(1,"memory trace case=%0d item=%0d",cases,i);
        cases=cases+1;repeat(2) @(negedge clk);
    endtask
    reg [127:0] desc;
    initial begin
        repeat(4) @(negedge clk);reset=0;
        // All 256 full-width opcodes, including unknown codes with low bits 0..7.
        for(integer op=0;op<256;op++) check(128'(op));
        for(integer i=0;i<128;i++) begin
            desc=0;desc[7:0]=1;desc[15:8]=8'(i%3);
            desc[47:32]=16'((i*17)%648);desc[63:48]=16'((i*13)%365);
            desc[79:64]=16'(i%17);desc[95:80]=16'(i%4);desc[103:96]=8'(i%19);check(desc);
            desc=0;desc[7:0]=6;desc[15:8]=8'(i%5);
            desc[47:32]=16'((i*8)%648);desc[63:48]=16'(i%363);
            desc[79:64]=16'((i*16)%648);desc[95:80]=16'((i+1)%363);
            desc[111:96]=16'((i%3)*8);desc[127:112]=16'(i%4);check(desc);
        end
        for(integer i=0;i<18;i++) begin
            desc=0;desc[7:0]=2;desc[15:8]=8'(i);desc[43:32]=12'(i*137);check(desc);
            desc[44]=1;check(desc);desc[127]=1;check(desc);
        end
        // Explicit format-vs-range, no-op-vs-range and 17-bit end-sum priorities.
        desc=0;desc[7:0]=1;desc[47:32]=640;check(desc);desc[15:8]=2;check(desc);
        desc[15:8]=0;desc[47:32]=8;desc[79:64]=65535;desc[95:80]=1;check(desc);
        desc=0;desc[7:0]=6;desc[47:32]=640;check(desc);desc[32]=1;check(desc);
        for(integer op=4;op<=5;op++) begin
            desc=0;desc[7:0]=8'(op);desc[15:8]=16;desc[63:32]=240000;check(desc);
            desc[127]=1;check(desc);desc[15:8]=0;check(desc);
            desc[15:8]=16;desc[63:32]=32'h3ffffc;check(desc);
        end
        desc=0;desc[7:0]=3;desc[15:8]=2;check(desc);desc[15:8]=1;desc[32]=1;check(desc);
        desc=0;desc[7:0]=4;desc[15:8]=1;memory_error=1;check(desc);memory_error=0;
        desc=0;desc[7:0]=7;audio_busy=1;audio_settle=1;audio_settings_valid=0;check(desc);
        desc[32]=1;check(desc);audio_busy=0;audio_settle=0;check(desc);
        desc[32]=0;check(desc);audio_settings_valid=1;audio_apply_error=1;check(desc);audio_apply_error=0;
        if(AUDIO_CSR) begin
            audio_settle=1;
            fork
                check(desc);
                begin
                    wait(engines[0].dut.state==1 && engines[1].dut.state==1);
                    repeat(5) @(negedge clk);audio_settle=0;
                end
            join
        end
        $display("PASS: decode equivalence AUDIO_CSR=%0d cases=%0d, exact memory traces, palette, errors and audio effects",AUDIO_CSR,cases);
        $finish;
    end
    initial begin #2000000;$fatal(1,"decode equivalence timeout");end
endmodule
