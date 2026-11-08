`timescale 1ns/1ps
module tb_fb_burst_ctrl;
    localparam integer MEMORY_BYTES=32768;
    integer carry_reads=0,carry_writes=0;
    reg [2:0] carry_boundaries=0;
    always @(posedge clk) if(!reset && dut.state==dut.PREPARE && dut.cursor_upper_carry) begin
        if(dut.writing) carry_writes<=carry_writes+1;
        else carry_reads<=carry_reads+1;
        case(dut.cursor[19:11])
            0: carry_boundaries[0]<=1;
            1: carry_boundaries[1]<=1;
            2: carry_boundaries[2]<=1;
        endcase
    end
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
    kagura_hyperram_pair_model #(.BYTES(MEMORY_BYTES),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
        .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
        .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    reg [7:0] expected_memory[0:MEMORY_BYTES-1];
    integer i,j,trial,a,n,cycles=0,start_cycle,max_read=0;
    always @(posedge clk) cycles<=cycles+1;
    task transaction(input integer wr,base,length,bad);
        integer b;
        begin
            wait(ready);
            @(negedge clk);
            write=1'(wr); addr=20'(base); words=5'(length);
            for(b=0;b<64;b=b+1) begin
                wdata[b*8+:8]=8'($urandom);
                mask[b]=1'($urandom);
            end
            valid=1; start_cycle=cycles;
            @(negedge clk); valid=0;
            wait(done);
            if(error!==1'(bad)) $fatal(1,"invalid command status");
            if(!phy_cs_n || !ready) $fatal(1,"completion before bus recovery");
            if(bad==0) begin
                for(b=0;b<length*4;b=b+1) begin
                    if(wr!=0) begin
                        if(!mask[b]) expected_memory[base*4+b]=wdata[b*8+:8];
                    end else if(rdata[b*8+:8]!==expected_memory[base*4+b])
                        $fatal(1,"read mismatch word %0d byte %0d",base,b);
                end
                if(wr==0 && cycles-start_cycle>max_read) max_read=cycles-start_cycle;
            end
            for(b=0;b<MEMORY_BYTES;b=b+1)
                if(model.memory[b]!==expected_memory[b]) $fatal(1,"memory corruption %0d",b);
            @(negedge clk);
        end
    endtask
    initial begin
        for(i=0;i<MEMORY_BYTES;i=i+1) expected_memory[i]=8'ha5;
        repeat(3) @(negedge clk);
        reset=0;
        wait(initialized);
        for(trial=0;trial<100;trial=trial+1) begin
            a=$urandom_range(0,1008); n=$urandom_range(1,16);
            transaction(1,a,n,0);
            transaction(0,a,n,0);
        end
        transaction(1,252,16,0); transaction(0,252,16,0); transaction(1,508,16,0); transaction(0,508,16,0);
        transaction(0,1023,1,0);
        for(j=2048;j<=6144;j=j+2048) begin
            transaction(1,j-4,16,0); transaction(0,j-4,16,0);
            transaction(1,j-1,16,0); transaction(0,j-1,16,0);
            // A new request must not reuse the preceding carry.
            transaction(1,32,16,0); transaction(0,32,16,0);
        end
        transaction(1,0,0,1); transaction(1,0,17,1);
        transaction(0,1048575,2,1);
        // Abort a command in the CA phase, reset controller/model protocol state,
        // then ensure initialization and a fresh request complete.
        wait(ready); @(negedge clk); valid=1; write=1; addr=0; words=16;
        @(negedge clk); valid=0;
        repeat(2) @(negedge clk);
        reset=1; repeat(3) @(negedge clk); reset=0;
        wait(initialized); transaction(0,0,1,0);
        // Up to three CS windows for an unaligned 16-word request. This is
        // a controller latency bound, not a relaxed scanout deadline.
        if(max_read>3*(14+6+2+3)+32+4) $fatal(1,"split burst latency bound exceeded");
        if(carry_reads<6 || carry_writes<6 || carry_boundaries!==3'b111)
            $fatal(1,"missing carry=1 coverage");
        $display("COVER: carry=1 reads=%0d writes=%0d boundaries=%b",carry_reads,carry_writes,carry_boundaries);
        $display("PASS: fb_burst_ctrl random masked writes, 1..16 words, boundaries, reset; max read %0d cycles",max_read);
        $finish;
    end
    initial begin #10000000; $fatal(1,"watchdog"); end
endmodule
