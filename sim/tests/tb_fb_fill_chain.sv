`timescale 1ns/1ps
module tb_fb_fill_chain;
    reg clk=0, reset=1, valid=0, page=0;
    always #5 clk=~clk;
    reg [15:0] x=0,y=0,width=0,height=0;
    reg [3:0] color=0;
    wire ready,done,error,mem_valid,mem_write;
    wire [21:0] mem_addr;
    wire [7:0] mem_wdata;
    wire mem_ready,mem_done;
    wire [7:0] mem_rdata;
    reg [7:0] reference_memory[0:230399];
    integer delay_left=0,cycle=0,i,j,k,px,py;
    reg pending=0;
    kagura_fb_fill dut(.*);

    wire cmd,cmd_en,cmd_rdy,rd_valid,initialized;
    wire [19:0] addr;
    wire [31:0] wr_data,rd_data;
    wire [3:0] mask;
    wire phy_reset_n,cs_n,ck_en,dq_oe,rwds_oe,mask_r,mask_f;
    wire [7:0] dq_r,dq_f,read_r,read_f;
    kagura_fb_byte_port port(
        .clk,.reset,.initialized,.mem_valid,.mem_ready,.mem_write,.mem_addr,
        .mem_wdata,.mem_done,.mem_rdata,.ctrl_cmd(cmd),.ctrl_cmd_en(cmd_en),
        .ctrl_cmd_rdy(cmd_rdy),.ctrl_addr(addr),.ctrl_wr_data(wr_data),
        .ctrl_data_mask(mask),.ctrl_rd_data(rd_data),.ctrl_rd_data_valid(rd_valid));
    kagura_hyperram_ctrl #(.INIT_CYCLES(64)) ctrl(
        .clk,.rst_n(!reset),.lat_cycles(5'd14),.rd_latency(3'd6),
        .cmd,.cmd_reg(1'b0),.cmd_en,.cmd_rdy,.addr,.wr_data,.data_mask(mask),
        .rd_data,.rd_data_valid(rd_valid),.init_calib(initialized),
        .phy_reset_n,.phy_cs_n(cs_n),.phy_ck_en(ck_en),.phy_dq_oe(dq_oe),
        .phy_dq_o_rise(dq_r),.phy_dq_o_fall(dq_f),.phy_rwds_oe(rwds_oe),
        .phy_rwds_o_rise(mask_r),.phy_rwds_o_fall(mask_f),
        .phy_dq_tx(),.phy_rwds_tx(),.phy_dq_i_rise(read_r),.phy_dq_i_fall(read_f));
    kagura_hyperram_pair_model #(.BYTES(230400)) memory_model(
        .clk,.reset_n(phy_reset_n),.cs_n,.ck_en,.dq_oe,.rwds_oe,.dq_r,.dq_f,
        .mask_r,.mask_f,.read_r,.read_f);
    task run_fill(input integer p,xx,yy,ww,hh,cc,invalid);
        integer a, ox, oy, observed_error;
        begin
            @(negedge clk);
            page=p; x=xx; y=yy; width=ww; height=hh; color=cc; valid=1;
            @(negedge clk); valid=0;
            wait(done);
            observed_error=error;
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
                if(memory_model.memory[a]!==reference_memory[a])
                    $fatal(1,"pixel mismatch at byte %0d for %0d,%0d %0dx%0d",a,xx,yy,ww,hh);
        end
    endtask
    initial begin
        for(i=0;i<230400;i=i+1) begin
            reference_memory[i]=8'ha5;
        end
        repeat(3) @(negedge clk);
        reset=0;
        run_fill(0,0,0,640,360,3,0);
        run_fill(1,639,359,1,1,15,0);
        for(j=0;j<2;j=j+1)
            for(k=1;k<6;k=k+1) run_fill(j,10+j,13,k,3,k,0);
        run_fill(0,0,0,0,4,0,0);
        run_fill(0,639,359,2,1,0,1);
        run_fill(0,65535,0,2,1,0,1);
        for(j=0;j<80;j=j+1) begin
            px=$urandom_range(0,620); py=$urandom_range(0,350);
            run_fill(j%2,px,py,$urandom_range(1,20),$urandom_range(1,10),j%16,0);
        end
        $display("PASS: fb_fill_chain: full pages, boundaries, odd edges, invalid ranges, 80 randomized rectangles, memory stalls");
        $finish;
    end
    initial begin #100000000; $fatal(1,"watchdog"); end
endmodule
