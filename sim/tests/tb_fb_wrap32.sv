`timescale 1ns/1ps
// Independent linear byte oracle against a physical 32B-wrap memory model.
module tb_fb_wrap32;
    wire rword_valid,scan_word_valid;
    wire [31:0] rword_data,scan_word_data;

    reg clk=0,reset=1,valid=0,write=0;
    always #5 clk=~clk;
    reg [19:0] addr=0;
    reg [4:0] words=1;
    reg [511:0] wdata=0;
    reg [63:0] mask=0;
    wire ready,done,error,initialized;
    wire [511:0] rdata;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(64)) dut(.*);
    kagura_psram_wrap_pair_model #(.BYTES(4194304),.ALLOW_UNDOCUMENTED_CA45(1)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
        .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
        .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    reg [7:0] expected[0:4194303];
    integer windows=0,cycles=0,max_read=0,cases=0;
    reg previous_cs=1;
    always @(posedge clk) begin
        cycles<=cycles+1;
        previous_cs<=phy_cs_n;
        if(previous_cs && !phy_cs_n) windows<=windows+1;
    end
    task automatic transaction(input bit wr,input integer address,length,input bit bad);
        integer before_windows,start_cycle;
        begin
            wait(ready);@(negedge clk);
            addr=20'(address/4);words=5'(length);write=wr;valid=1;
            before_windows=windows;start_cycle=cycles;
            @(negedge clk);valid=0;wait(done);#1;
            if(error!==bad || !ready || !phy_cs_n) $fatal(1,"completion/bounds status");
            if(windows-before_windows!=(bad ? 0 : ((address%32+length*4+31)/32)))
                $fatal(1,"physical CS split count");
            if(!bad) begin
                for(integer b=0;b<length*4;b++) begin
                    if(wr) begin
                        if(!mask[b]) expected[address+b]=wdata[b*8+:8];
                    end else if(rdata[b*8+:8]!==expected[address+b])
                        $fatal(1,"linear oracle address=%0d offset=%0d",address,b);
                end
                // Independently inspect touched bytes and both guards, including
                // masked lanes. Detect write wrap hidden by same-start reads.
                for(integer b=(address/32)*32;b<address+length*4+32 && b<4194304;b++)
                    if(model.memory[b]!==expected[b]) $fatal(1,"unexpected physical write %0d",b);
                if(!wr && cycles-start_cycle>max_read) max_read=cycles-start_cycle;
            end
            cases++;@(negedge clk);
        end
    endtask
    initial begin
        for(integer b=0;b<4194304;b++) expected[b]=8'ha5;
        repeat(3) @(negedge clk);reset=0;wait(initialized);
        // Exact hardware trigger case, now required to be linear rather than
        // altering the independently addressed wrap target.
        wdata=64'hf0ceac8a67452301;mask=0;
        transaction(1,300060,2,0);
        transaction(0,300032,1,0);transaction(0,300060,1,0);transaction(0,300064,1,0);
        transaction(0,300060,2,0);
        for(integer offset=0;offset<8;offset++) begin
            for(integer length=1;length<=16;length++) begin
                for(integer b=0;b<64;b++) begin wdata[b*8+:8]=8'($urandom);mask[b]=1'($urandom);end
                transaction(1,1024+offset*4,length,0);
                transaction(0,1024+offset*4,length,0);
            end
        end
        // Aligned/unaligned 64B, fully masked write and final-die boundaries.
        mask=0;for(integer b=0;b<64;b++) wdata[b*8+:8]=8'(b*37+11);
        transaction(1,300000,16,0);transaction(0,300000,16,0);
        mask='1;transaction(1,300028,16,0);transaction(0,300028,16,0);
        mask=0;transaction(1,4194240,16,0);transaction(0,4194240,16,0);
        transaction(1,4194300,2,1);transaction(1,0,0,1);transaction(0,0,17,1);
        // Reset in first transfer, then during a continuation. Reinitialize;
        // only the interrupted write's memory contents are unspecified.
        for(integer pause_cycles=3;pause_cycles<=60;pause_cycles+=57) begin
            wait(ready);@(negedge clk);addr=512;words=16;write=0;valid=1;
            @(negedge clk);valid=0;repeat(pause_cycles) @(negedge clk);
            reset=1;repeat(3) @(negedge clk);reset=0;wait(initialized);
            transaction(0,300032,1,0);
        end
        if(max_read>111) $fatal(1,"split read latency bound");
        $display("PASS: wrap32 linear READ/WRITE, every word offset/1..16 words, masks, guards, die/reset: cases=%0d max_read=%0d",cases,max_read);
        $finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
