// SPDX-License-Identifier: Apache-2.0
module kagura_fb_memtest_top #(
    parameter integer WORDS=256
) (
    input  wire clk27,
    input  wire reset_n,
    output wire [5:0] led_n,
    output wire [1:0] O_psram_ck,
    output wire [1:0] O_psram_ck_n,
    inout  wire [1:0] IO_psram_rwds,
    output wire [1:0] O_psram_reset_n,
    inout  wire [15:0] IO_psram_dq,
    output wire [1:0] O_psram_cs_n
);
    wire clk,clk_ck,lock;
    // 54 MHz; CLKOUTP is the same clock shifted by 67.5 degrees (PSDA 3 x 22.5).
    rPLL #(.FCLKIN("27"),.IDIV_SEL(0),.FBDIV_SEL(1),.ODIV_SEL(8),
        .PSDA_SEL("0011"),.DUTYDA_SEL("1000"),.DEVICE("GW1NR-9C")) pll(
        .CLKOUT(clk),.CLKOUTP(clk_ck),.LOCK(lock),.CLKIN(clk27),.CLKFB(1'b0),
        .RESET(~reset_n),.RESET_P(1'b0),.FBDSEL(6'b0),.IDSEL(6'b0),.ODSEL(6'b0),
        .PSDA(4'b0),.DUTYDA(4'b0),.FDLY(4'b0));

    reg [3:0] rst_pipe=0;
    always @(posedge clk) rst_pipe<={rst_pipe[2:0],lock&reset_n};
    wire rst_n=rst_pipe[3];

    logic cmd,cmd_en,cmd_rdy,rd_data_valid,init_calib;
    logic [19:0] addr;
    logic [31:0] wr_data,rd_data;
    logic phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe,phy_rwds_o_rise,phy_rwds_o_fall;
    logic [7:0] o_rise,o_fall,i_rise,i_fall;

    wire [3:0] data_mask;
    kagura_hyperram_ctrl #(.ADDR_WIDTH(20)) ctrl(
        .clk,.rst_n,.lat_cycles(5'd14),.rd_latency(3'd6),.cmd,.cmd_reg(1'b0),.cmd_en,.cmd_rdy,.addr,.wr_data,.data_mask(data_mask),.rd_data,
        .rd_data_valid,.init_calib,.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,
        .phy_dq_o_rise(o_rise),.phy_dq_o_fall(o_fall),.phy_rwds_oe,.phy_rwds_o_rise,
        .phy_rwds_o_fall,.phy_dq_i_rise(i_rise),.phy_dq_i_fall(i_fall));

    kagura_hyperram_phy_gowin phy(
        .clk,.clk_ck,.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,
        .phy_dq_o_rise(o_rise),.phy_dq_o_fall(o_fall),.phy_rwds_oe,.phy_rwds_o_rise,
        .phy_rwds_o_fall,.phy_dq_i_rise(i_rise),.phy_dq_i_fall(i_fall),
        .O_psram_ck(O_psram_ck[0]),.O_psram_ck_n(O_psram_ck_n[0]),
        .O_psram_reset_n(O_psram_reset_n[0]),.O_psram_cs_n(O_psram_cs_n[0]),
        .IO_psram_rwds(IO_psram_rwds[0]),.IO_psram_dq(IO_psram_dq[7:0]));

    assign O_psram_ck[1]=1'b0;
    assign O_psram_ck_n[1]=1'b1;
    assign O_psram_reset_n[1]=1'b0;
    assign O_psram_cs_n[1]=1'b1;
    assign IO_psram_rwds[1]=1'bz;
    assign IO_psram_dq[15:8]=8'bz;

    wire fill_ready, fill_done, fill_error;
    wire f_valid,f_write,b_ready,b_done;
    wire [21:0] f_addr;
    wire [7:0] f_data,b_data;
    reg [2:0] stage;
    reg [21:0] check_addr;
    reg failure, passed;
    reg [25:0] heartbeat;
    wire fill_active=stage<4;
    wire launch=stage==0 || stage==2;
    wire [7:0] expected_byte =
        ((check_addr==320 || check_addr==640) ? 8'h3a :
         (check_addr==321 || check_addr==641) ? 8'haa : 8'h33);
    kagura_fb_fill fill(
        .clk,.reset(!rst_n),.valid(launch),.ready(fill_ready),
        .page(1'b0),.x(stage<2 ? 16'd0 : 16'd1),
        .y(stage<2 ? 16'd0 : 16'd1),
        .width(stage<2 ? 16'd640 : 16'd3),
        .height(stage<2 ? 16'd360 : 16'd2),
        .color(stage<2 ? 4'd3 : 4'd10),.done(fill_done),.error(fill_error),
        .mem_valid(f_valid),.mem_ready(b_ready && fill_active),
        .mem_write(f_write),.mem_addr(f_addr),.mem_wdata(f_data),
        .mem_done(b_done && fill_active),.mem_rdata(b_data));
    kagura_fb_byte_port port(
        .clk,.reset(!rst_n),.initialized(init_calib),
        .mem_valid(fill_active ? f_valid : stage==4),
        .mem_ready(b_ready),.mem_write(fill_active && f_write),
        .mem_addr(fill_active ? f_addr : check_addr),.mem_wdata(f_data),
        .mem_done(b_done),.mem_rdata(b_data),
        .ctrl_cmd(cmd),.ctrl_cmd_en(cmd_en),.ctrl_cmd_rdy(cmd_rdy),
        .ctrl_addr(addr),.ctrl_wr_data(wr_data),.ctrl_data_mask(data_mask),
        .ctrl_rd_data(rd_data),.ctrl_rd_data_valid(rd_data_valid));
    always @(posedge clk) begin
        if(!rst_n) begin
            stage<=0; check_addr<=0; failure<=0; passed<=0; heartbeat<=0;
        end else begin
            heartbeat<=heartbeat+1'b1;
            case(stage)
                0,2: if(fill_ready) stage<=stage+1'b1;
                1,3: if(fill_done) begin
                    if(fill_error) failure<=1;
                    stage<=stage+1'b1;
                end
                4: if(b_ready) stage<=5;
                5: if(b_done) begin
                    if(b_data!=expected_byte) failure<=1;
                    if(check_addr==115199) begin
                        passed<=!failure && b_data==expected_byte;
                        stage<=6;
                    end else begin check_addr<=check_addr+1'b1; stage<=4; end
                end
                default: stage<=6;
            endcase
        end
    end
    // Lit LEDs: 0 initialized, 1 passed, 2 mismatch, 3 finished, 5 heartbeat.
    assign led_n=~{heartbeat[25],1'b0,stage==6,failure,passed,init_calib};
endmodule
