`timescale 1ns/1ps
module tb_fb_contention;
    reg clk=0,reset=1;
    wire valid,write;
    always #5 clk=~clk;
    wire [19:0] addr;
    wire [4:0] words;
    wire [511:0] wdata;
    wire [63:0] mask;
    wire ready,done,error,initialized;
    wire [511:0] rdata;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(64)) dut(.*);
    kagura_hyperram_pair_model #(.BYTES(4096),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
        .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
        .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));

    reg [2:0] req_valid=0;
    wire [2:0] req_ready,rsp_done,rsp_error;
    reg [2:0] req_write=3'b100;
    reg [2:0][19:0] req_addr=0;
    reg [2:0][4:0] req_words={5'd16,5'd1,5'd16};
    reg [2:0][511:0] req_wdata=0;
    reg [2:0][63:0] req_mask=0;
    wire [511:0] rsp_data;
    kagura_fb_arbiter scheduler(.*);
    integer cycles=0,line_start=0,line_index=0,burst_index=0,max_line=0;
    integer pcm_count=0,gpu_count=0,pcm_start=0,max_pcm=0;
    reg [2:0] pending=0;
    always @(posedge clk) begin
        if(reset) begin
            cycles<=0; req_valid<=0; pending<=0;
        end else begin
            cycles<=cycles+1;
            for(integer port=0;port<3;port=port+1) begin
                if(req_valid[port] && req_ready[port]) begin
                    pending[port]<=1; req_valid[port]<=0;
                end
                if(rsp_done[port]) begin
                    if(!pending[port] || rsp_error[port]) $fatal(1,"incorrect response owner/error");
                    pending[port]<=0;
                    if(port!=2 && rsp_data[31:0]!==32'ha5a5a5a5) $fatal(1,"read response data");
                end
            end
            // Keep both background clients saturated (stronger than 48 kHz PCM).
            if(!pending[1] && !req_valid[1]) begin req_valid[1]<=1; pcm_start<=cycles; end
            if(!pending[2] && !req_valid[2]) req_valid[2]<=1;
            if(rsp_done[1]) begin
                pcm_count<=pcm_count+1;
                if(cycles-pcm_start>max_pcm) max_pcm<=cycles-pcm_start;
            end
            if(rsp_done[2]) gpu_count<=gpu_count+1;
            if(cycles%2400==0 && line_index<360) begin
                if(pending[0] || req_valid[0] || burst_index!=0) $fatal(1,"line missed");
                req_valid[0]<=1; req_addr[0]<=0; line_start<=cycles;
            end
            if(rsp_done[0]) begin
                for(integer b=0;b<64;b=b+1)
                    if(rsp_data[b*8+:8]!==8'ha5) $fatal(1,"scanout burst mismatch");
                if(burst_index==4) begin
                    if(cycles-line_start>1920) $fatal(1,"scanout deadline");
                    if(cycles-line_start>max_line) max_line<=cycles-line_start;
                    line_index<=line_index+1; burst_index<=0;
                end else begin
                    burst_index<=burst_index+1;
                    req_addr[0]<=req_addr[0]+20'd16; req_valid[0]<=1;
                end
            end
            if(line_index==360) begin
                if(pcm_count<1000 || gpu_count<1000 || max_pcm>4096) $fatal(1,"background starvation");
                $display("PASS: fb_contention 360 lines max=%0d cycles PCM max=%0d cycles PCM=%0d GPU=%0d",max_line,max_pcm,pcm_count,gpu_count);
                $finish;
            end
        end
    end
    initial begin
        req_addr[1]=256; req_addr[2]=512;
        req_wdata[2]={64{8'h69}};
        repeat(3) @(negedge clk); reset=0;
    end
    initial begin #20000000; $fatal(1,"watchdog"); end
endmodule
