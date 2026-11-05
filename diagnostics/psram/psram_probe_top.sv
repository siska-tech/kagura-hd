// SPDX-License-Identifier: Apache-2.0
module psram_probe_top(
    input wire clk27,reset_n,trigger_n,
    output wire uart_tx,
    output wire [5:0] led_n,
    output wire [1:0] O_psram_ck,O_psram_ck_n,O_psram_reset_n,O_psram_cs_n,
    inout wire [1:0] IO_psram_rwds,
    inout wire [15:0] IO_psram_dq
);
    wire clk,clk_ck,lock;
    rPLL #(.FCLKIN("27"),.IDIV_SEL(0),.FBDIV_SEL(1),.ODIV_SEL(8),
        .PSDA_SEL("0011"),.DUTYDA_SEL("1000"),.DEVICE("GW1NR-9C")) pll(
        .CLKOUT(clk),.CLKOUTP(clk_ck),.LOCK(lock),.CLKIN(clk27),.CLKFB(1'b0),
        .RESET(~reset_n),.RESET_P(1'b0),.FBDSEL(6'b0),.IDSEL(6'b0),.ODSEL(6'b0),
        .PSDA(4'b0),.DUTYDA(4'b0),.FDLY(4'b0));
    reg [2:0] rst_pipe=0;
    always @(posedge clk or negedge reset_n)
        if(!reset_n) rst_pipe<=0;
        else rst_pipe<={rst_pipe[1:0],lock};
    wire reset=!rst_pipe[2];
    (* async_reg="true" *) reg [1:0] trigger_sync=2'b11;
    reg seen_high=0,previous=1;
    always @(posedge clk) begin
        if(reset) begin trigger_sync<=2'b11;seen_high<=0;previous<=1;end
        else begin
            trigger_sync<={trigger_sync[0],trigger_n};previous<=trigger_sync[1];
            if(initialized && trigger_sync[1]) seen_high<=1;
        end
    end
    wire start=seen_high && previous && !trigger_sync[1];
    wire valid,write,ready,done,error,initialized;
    wire [19:0] addr;
    wire [4:0] words;
    wire [511:0] wdata,rdata;
    wire [63:0] mask;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_burst_ctrl controller(.*);
    wire tx_valid,tx_ready,finished,failed,armed;
    wire [7:0] tx_data;
    psram_probe_engine engine(.*);
    psram_probe_uart uart(.clk,.reset,.valid(tx_valid),.data(tx_data),.ready(tx_ready),.tx(uart_tx));
    kagura_hyperram_phy_gowin phy(
        .clk,.clk_ck,.phy_reset_n,.phy_cs_n,.phy_ck_en,
        .phy_dq_oe(phy_dq_tx),.phy_rwds_oe(phy_rwds_tx),
        .phy_dq_o_rise,.phy_dq_o_fall,.phy_rwds_o_rise,.phy_rwds_o_fall,
        .phy_dq_i_rise,.phy_dq_i_fall,.phy_rwds_i_rise(),.phy_rwds_i_fall(),
        .O_psram_ck(O_psram_ck[0]),.O_psram_ck_n(O_psram_ck_n[0]),
        .O_psram_reset_n(O_psram_reset_n[0]),.O_psram_cs_n(O_psram_cs_n[0]),
        .IO_psram_rwds(IO_psram_rwds[0]),.IO_psram_dq(IO_psram_dq[7:0]));
    assign O_psram_ck[1]=0;
    assign O_psram_ck_n[1]=1;
    assign O_psram_reset_n[1]=0;
    assign O_psram_cs_n[1]=1;
    assign IO_psram_rwds[1]=1'bz;
    assign IO_psram_dq[15:8]=8'bz;
    assign led_n=~{1'b0,finished,failed,armed,lock,initialized};
endmodule
