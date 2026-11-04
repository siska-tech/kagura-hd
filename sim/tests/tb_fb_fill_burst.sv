`timescale 1ns/1ps
module tb_fb_fill_burst;
    reg clk=0, reset=1, valid=0, page=0;
    always #5 clk=~clk;
    reg [15:0] x=0,y=0,width=0,height=0;
    reg [3:0] color=0;
    wire ready,done,error,req_valid,req_ready,req_write;
    wire [19:0] req_addr;
    wire [4:0] req_words;
    wire [511:0] req_wdata,rsp_data;
    wire [63:0] req_mask;
    wire rsp_done,rsp_error,ctrl_ready,initialized;
    reg [7:0] reference_memory[0:230399];
    integer i,j,k,px,py,cycles=0,start_cycle,full_cycles=0;
    always @(posedge clk) cycles<=cycles+1;
    wire allow_request=cycles%7!=0;
    assign req_ready=ctrl_ready && allow_request;
    kagura_fb_fill_burst dut(.copy(1'b0),.src_page(1'b0),.src_x(16'd0),.src_y(16'd0),.capture_window(),.*);
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(64)) controller(
        .clk,.reset,.valid(req_valid && allow_request),.ready(ctrl_ready),.write(req_write),.addr(req_addr),
        .words(req_words),.wdata(req_wdata),.mask(req_mask),.done(rsp_done),.error(rsp_error),.rdata(rsp_data),
        .initialized,.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,.phy_dq_o_rise,.phy_dq_o_fall,
        .phy_rwds_oe,.phy_rwds_o_rise,.phy_rwds_o_fall,.phy_dq_tx,.phy_rwds_tx,.phy_dq_i_rise,.phy_dq_i_fall);
    kagura_hyperram_pair_model #(.BYTES(230400),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),.dq_f(phy_dq_o_fall),
        .mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),.read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    task run_fill(input integer p,xx,yy,ww,hh,cc,invalid);
        integer a, ox, oy, observed_error;
        begin
            @(negedge clk);
            page=p; x=xx; y=yy; width=ww; height=hh; color=4'(cc); valid=1; start_cycle=cycles;
            @(negedge clk); valid=0;
            wait(done);
            observed_error=error;
            if(ww==640 && hh==360) full_cycles=cycles-start_cycle;
            if(observed_error!=invalid) $fatal(1,"error status");
            if(!invalid) begin
                for(oy=yy;oy<yy+hh;oy=oy+1)
                    for(ox=xx;ox<xx+ww;ox=ox+1) begin
                        a=p*115200+oy*320+ox/2;
                        if(ox%2==0) reference_memory[a][7:4]=cc;
                        else reference_memory[a][3:0]=cc;
                    end
            end
            @(negedge clk);
            for(a=0;a<230400;a=a+1)
                if(model.memory[a]!==reference_memory[a])
                    $fatal(1,"pixel mismatch at byte %0d for %0d,%0d %0dx%0d",a,xx,yy,ww,hh);
        end
    endtask
    initial begin
        for(i=0;i<230400;i=i+1) begin
            reference_memory[i]=8'ha5;
        end
        repeat(3) @(negedge clk);
        reset=0; wait(initialized);
        run_fill(0,0,0,640,360,3,0);
        run_fill(1,639,359,1,1,15,0);
        for(j=0;j<2;j=j+1)
            for(k=1;k<6;k=k+1) run_fill(j,10+j,13,k,3,k,0);
        run_fill(0,0,0,0,4,0,0);
        run_fill(0,639,359,2,1,0,1);
        run_fill(0,65535,0,2,1,0,1);
        for(j=0;j<100;j=j+1) begin
            px=$urandom_range(0,300); py=$urandom_range(0,300);
            run_fill(j%2,px,py,$urandom_range(1,340),$urandom_range(1,60),j%16,0);
        end
        $display("PASS: fb_fill_burst full pages, odd nibble/byte/word edges, invalid ranges, 100 random rectangles, stalls; full=%0d cycles",full_cycles);
        $finish;
    end
    initial begin #100000000; $fatal(1,"watchdog"); end
endmodule
