`timescale 1ns/1ps
module tb_fb_burst_bounds;
    wire rword_valid,scan_word_valid;
    wire [31:0] rword_data,scan_word_data;

    reg clk=0,reset=1,valid=0,write=1;
    always #5 clk=~clk;
    reg [19:0] addr=0;
    reg [4:0] words=1;
    reg [511:0] wdata=0;
    reg [63:0] mask=~64'd0;
    wire ready,done,error,initialized;
    wire [511:0] rdata;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall;
    wire [7:0] phy_dq_i_rise=0,phy_dq_i_fall=0;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(16)) dut(.*);
    integer windows=0,before_windows,expected_error,cases=0;
    reg cs_previous=1;
    always @(posedge clk) begin
        cs_previous<=phy_cs_n;
        if(cs_previous && !phy_cs_n) windows<=windows+1;
    end
    initial begin
        repeat(3) @(negedge clk); reset=0; wait(initialized);
        for(integer address=1048512;address<1048576;address=address+1)
            for(integer length=0;length<19;length=length+1) begin
                wait(ready); @(negedge clk);
                addr=20'(address); words=5'(length); valid=1;
                before_windows=windows;
                expected_error=length==0 || length>16 || address+length>1048576;
                @(negedge clk); valid=0; wait(done); #1;
                if(error!==1'(expected_error)) $fatal(1,"die bound %0d + %0d",address,length);
                if(windows-before_windows!=(expected_error!=0 ? 0 : ((address%8+length+7)/8)))
                    $fatal(1,"invalid request drove CS or split window count wrong");
                cases=cases+1;
            end
        $display("PASS: fb_burst_bounds %0d end-of-die lengths, rejected requests never assert CS",cases);
        $finish;
    end
    initial begin #2000000; $fatal(1,"watchdog"); end
endmodule
