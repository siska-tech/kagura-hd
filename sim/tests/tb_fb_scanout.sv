`timescale 1ns/1ps
module tb_fb_scanout #(parameter bit INJECT_STALL=0);
    reg stalled=0;
    integer missing_lines=0;
    reg clk=0,pix_clk=0,reset=1;
    always #(500.0/54.0) clk=~clk;
    always #(500.0/74.25) pix_clk=~pix_clk;
    reg [10:0] cx=0;
    reg [9:0] cy=0;
    integer frames=0,pixels=0;
    always @(posedge pix_clk) begin
        if(reset) begin cx<=0; cy<=0; frames<=0; end
        else if(cx==1649) begin
            cx<=0;
            if(cy==749) begin cy<=0; frames<=frames+1; end else cy<=cy+1'b1;
        end else cx<=cx+1'b1;
    end
    reg present_valid=0,present_page=0;
    reg [191:0] present_palette=0;
    wire present_ready,present_done,underrun,memory_error;
    wire [23:0] rgb;
    wire [15:0] generation_out;
    wire [2:0] req_ready,rsp_done,rsp_error;
    wire [511:0] rsp_data;
    wire display_valid;
    wire [19:0] display_addr;
    kagura_fb_scanout display(
        .sys_clk(clk),.sys_reset(reset),.pix_clk,.pix_reset(reset),.cx,.cy,
        .present_valid,.present_page,.present_palette,.present_ready,.present_done,
        .req_valid(display_valid),.req_ready(req_ready[0] && !stalled),.req_addr(display_addr),
        .rsp_done(rsp_done[0]),.rsp_error(rsp_error[0]),.rsp_data,.rgb,.underrun,.memory_error,.generation_out);
    reg [2:0] background=0;
    reg [2:0] pending=0;
    wire [2:0] req_valid={background[2:1],display_valid && !stalled};
    wire [2:0] req_write=3'b100;
    wire [2:0][19:0] req_addr={20'd61000,20'd60000,display_addr};
    wire [2:0][4:0] req_words={5'd16,5'd1,5'd16};
    wire [2:0][511:0] req_wdata={512'h12345678,512'd0,512'd0};
    wire [2:0][63:0] req_mask=0;
    wire valid,ready,write,done,error,initialized;
    wire [19:0] addr;
    wire [4:0] words;
    wire [511:0] wdata,rdata;
    wire [63:0] mask;
    kagura_fb_arbiter scheduler(.*);
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(64)) memory_ctrl(.*);
    kagura_hyperram_pair_model #(.BYTES(262144),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
        .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
        .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    always @(posedge clk) begin
        if(reset) begin background<=0; pending<=0; end
        else for(integer p=1;p<3;p=p+1) begin
            if(!background[p] && !pending[p]) background[p]<=1;
            if(background[p] && req_ready[p]) begin pending[p]<=1; background[p]<=0; end
            if(rsp_done[p]) begin
                if(!pending[p] || rsp_error[p]) $fatal(1,"background response");
                pending[p]<=0;
            end
        end
    end
    function automatic [3:0] pattern(input integer page,x,y);
        pattern=4'(page==0 ? x+y : x^y);
    endfunction
    integer expected_index;
    always @(negedge pix_clk) begin
        if(!reset && frames>=1 && frames<=2 && cx<1280 && cy<720) begin
            expected_index=int'(pattern(frames-1,int'(cx)/2,int'(cy)/2));
            if(frames==2) expected_index=15-expected_index;
            if(INJECT_STALL && frames==1 && !display.banks.pix_line_valid) begin
                expected_index=0;
                if(cx==0 && !cy[0]) missing_lines=missing_lines+1;
            end
            if(rgb!=={3{8'(expected_index*17)}})
                $fatal(1,"pixel frame %0d (%0d,%0d) got %h expected %h",frames,cx,cy,rgb,{3{8'(expected_index*17)}});
            pixels=pixels+1;
        end
        if(!reset && frames==3) begin
            if(pixels!=2*1280*720 || underrun!==INJECT_STALL || memory_error || (INJECT_STALL && missing_lines==0)) $fatal(1,"frame/underrun status %0d",pixels);
            $display("PASS: fb_scanout %0d pixels, 2x scaling, palette+page atomic flip, saturated background, missing lines=%0d",pixels,missing_lines);
            $finish;
        end
    end
    task present(input integer page);
        begin
            wait(present_ready); @(negedge clk);
            present_page=1'(page);
            for(integer c=0;c<16;c=c+1) present_palette[c*12+:12]=12'((page==0 ? c : 15-c)*273);
            present_valid=1; @(negedge clk); present_valid=0;
        end
    endtask
    initial begin
        @(negedge clk);
        for(integer page=0;page<2;page=page+1)
            for(integer y=0;y<360;y=y+1)
                for(integer x=0;x<640;x=x+2)
                    model.memory[page*115200+y*320+x/2]={pattern(page,x,y),pattern(page,x+1,y)};
        repeat(5) @(negedge clk); reset=0;
        present(0);
        wait(frames==1 && cy==100); present(1);
    end
    initial if(INJECT_STALL) begin
        wait(frames==1 && cy==197 && cx==1646);
        stalled=1;
        repeat(6000) @(negedge clk);
        stalled=0;
    end
    initial begin #60000000; $fatal(1,"watchdog"); end
endmodule

module tb_fb_scanout_faults; tb_fb_scanout #(.INJECT_STALL(1)) test(); endmodule
