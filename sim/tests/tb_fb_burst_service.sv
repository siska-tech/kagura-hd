// SPDX-License-Identifier: Apache-2.0
// Measure saturated transaction service, independently of the BLIT proposal.
// This deliberately has no memory data model: only command/response timing is
// tested. End-to-end data checks remain in tb_fb_burst and the GPU regressions.
module tb_fb_burst_service;
    wire rword_valid,scan_word_valid;
    wire [31:0] rword_data,scan_word_data;

    reg clk=0;
    always #5 clk=~clk;
    reg reset=1,request=0,writing=0;
    reg [4:0] words=1;
    wire [2:0] req_ready,rsp_done,rsp_error;
    wire [2:0][4:0] req_words;
    assign req_words[0]=5'd1;
    assign req_words[1]=5'd1;
    assign req_words[2]=words;
    wire valid,ready,write,done,error,initialized;
    wire [19:0] addr;
    wire [4:0] count;
    wire [511:0] wdata,rdata;
    wire [63:0] mask;
    kagura_fb_arbiter arbiter(
        .clk,.reset,.req_valid({request,2'b00}),.req_ready,
        .req_write({writing,2'b00}),.req_addr(60'd0),.req_words,
        .req_wdata(1536'd0),.req_mask(192'd0),.rsp_done,.rsp_error,
        .rsp_data(),.valid,.ready,.write,.addr,.words(count),.wdata,.mask,
        .done,.error,.rdata,.rword_valid,.rword_data,.scan_word_valid,.scan_word_data);
    kagura_fb_burst_ctrl #(.INIT_CYCLES(4)) controller(
        .clk,.reset,.valid,.ready,.write,.addr,.words(count),.wdata,.mask,
        .done,.error,.rdata,.rword_valid,.rword_data,.initialized,
        .phy_reset_n(),.phy_cs_n(),.phy_ck_en(),.phy_dq_oe(),
        .phy_dq_o_rise(),.phy_dq_o_fall(),.phy_rwds_oe(),
        .phy_rwds_o_rise(),.phy_rwds_o_fall(),.phy_dq_tx(),.phy_rwds_tx(),
        .phy_dq_i_rise(8'd0),.phy_dq_i_fall(8'd0));
    integer cycle=0,checked=0;
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(!reset && (|rsp_error)) $fatal(1,"unexpected memory error");
    end
    task automatic measure(input bit wr,input integer n);
        integer last_start,starts,expected;
        begin
            @(negedge clk);reset=1;request=0;writing=wr;words=5'(n);
            repeat(3) @(negedge clk);
            reset=0;
            wait(initialized);
            @(negedge clk);request=1;
            last_start=-1;starts=0;
            expected=(wr ? 22 : 28)+2*n+((n+7)/8-1)*(wr ? 18 : 24);
            while(starts<4) begin
                @(posedge clk);
                if(req_ready[2]) begin
                    if(last_start>=0) begin
                        if(cycle-last_start!=expected)
                            $fatal(1,"wr=%0d words=%0d period=%0d expected=%0d",
                                   wr,n,cycle-last_start,expected);
                        checked=checked+1;
                    end
                    last_start=cycle;starts=starts+1;
                end
            end
        end
    endtask
    initial begin
        for(integer n=1;n<=16;n=n+1) begin measure(0,n);measure(1,n);end
        $display("PASS tb_fb_burst_service: %0d intervals, aligned split read=28+2N+24(K-1) write=22+2N+18(K-1)",checked);
        $finish;
    end
    initial begin #1000000;$fatal(1,"timeout");end
endmodule
