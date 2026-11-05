`timescale 1ns/1ps
// Diagnostic only; production RTL is instantiated unchanged.
module tb_psram_wrap_repro #(parameter bit STRICT_CA=0, LEGAL_CA_ADAPTER=0);
    reg clk=0,reset=1,valid=0,write=0;
    always #9.259259 clk=~clk;
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
    // Test-only adapter verifies that strict mode accepts reference-legal CA.
    // Not a production fix; CR0 and controller logic remain unchanged.
    wire [7:0] model_dq_r=LEGAL_CA_ADAPTER && dut.ca_phase && dut.tick==1 && !dut.ca[46] ?
                          (phy_dq_o_rise & 8'hdf) : phy_dq_o_rise;
    kagura_psram_wrap_pair_model #(.BYTES(300160),.ALLOW_UNDOCUMENTED_CA45(!STRICT_CA)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(model_dq_r),
        .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
        .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    task automatic transfer(input bit wr,input integer byte_address,n);
        begin
            wait(ready);@(negedge clk);
            write=wr;addr=20'(byte_address/4);words=5'(n);valid=1;
            @(negedge clk);valid=0;wait(done);
            if(error || !ready || !phy_cs_n) $fatal(1,"transaction/recovery failed");
            @(negedge clk);
        end
    endtask
    integer cases=0,mismatches;
    reg [7:0] predicted[0:31];
    task automatic check_case(input integer byte_address,n,seed);
        integer index;
        begin
            // Seed a complete 32B group using <=4B transactions, so untouched
            // bytes have independently known data. All starts are word aligned.
            for(integer offset=0;offset<32;offset+=4) begin
                for(integer b=0;b<4;b++) wdata[b*8+:8]=8'(offset+b+seed);
                transfer(1,(byte_address/32)*32+offset,1);
                for(integer b=0;b<4;b++) predicted[offset+b]=8'(offset+b+seed);
            end
            for(integer b=0;b<64;b++) wdata[b*8+:8]=8'(b*37+seed);
            for(integer b=0;b<n*4;b++) predicted[(byte_address+b)%32]=wdata[b*8+:8];
            transfer(1,byte_address,n);transfer(0,byte_address,n);
            mismatches=0;
            for(integer b=0;b<n*4;b++) begin
                index=(byte_address+b)%32;
                if(rdata[b*8+:8]!==predicted[index]) $fatal(1,"wrap prediction mismatch %0d",b);
                if(rdata[b*8+:8]!==wdata[b*8+:8]) mismatches++;
            end
            if((n<=8) && mismatches!=0) $fatal(1,"short same-start roundtrip unexpectedly failed");
            if(n==16 && mismatches!=32) $fatal(1,"64B roundtrip must overwrite first half");
            $display("WRAP_CASE address=%0d bytes=%0d linear_mismatches=%0d",byte_address,n*4,mismatches);
            cases++;
        end
    endtask
    initial begin
        repeat(3) @(negedge clk);reset=0;wait(initialized);
        // Exact hardware start/pattern: CR0=8f1f gives last 32B twice.
        for(integer b=0;b<64;b++) wdata[b*8+:8]=8'(b*37+11);
        transfer(1,300000,16);transfer(0,300000,16);
        for(integer b=0;b<64;b++)
            if(rdata[b*8+:8]!==8'((32+b%32)*37+11)) $fatal(1,"64B minimal reproduction");
        $display("REPRO_PREDICTED %h",rdata);
        // Shows WRITE damage separately: a short linear-location read sees the
        // second-half payload at the original first-half address.
        transfer(0,300000,1);
        if(rdata[31:0]!==32'h1af5d0ab) $fatal(1,"wrapped write localization");
        // +0,+28,+32,+60 cover aligned and crossing absolute 32/64B edges.
        for(integer n=1;n<=16;n*=2) begin
            check_case(300032,n,17+n);
            check_case(300060,n,41+n);
            check_case(300064,n,67+n);
            check_case(300092,n,89+n);
        end
        if(!LEGAL_CA_ADAPTER && model.unsupported_ca_count==0) $fatal(1,"CA incompatibility not observed");
        if(LEGAL_CA_ADAPTER && model.unsupported_ca_count!=0) $fatal(1,"legal CA adapter failed");
        $display("PASS: 32B wrap hypothesis reproduced; %0d length/boundary cases; CA45 violations=%0d",cases,model.unsupported_ca_count);
        $finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
