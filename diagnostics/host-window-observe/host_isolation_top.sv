// SPDX-License-Identifier: Apache-2.0
module host_isolation_top(
    input wire clk27,reset_n,host_sck,host_cs_n,
    inout wire [3:0] host_io,
    output wire host_busy,host_ready,host_irq_n,uart_tx,
    output wire [3:0] sd_hiz,
    output wire [5:0] led_n,
    output wire [1:0] O_psram_ck,O_psram_ck_n,O_psram_reset_n,O_psram_cs_n,
    inout wire [1:0] IO_psram_rwds,
    inout wire [15:0] IO_psram_dq
);
    wire clk,lock;
    rPLL #(.FCLKIN("27"),.IDIV_SEL(0),.FBDIV_SEL(1),.ODIV_SEL(8),.DEVICE("GW1NR-9C")) pll(
        .CLKOUT(clk),.CLKOUTP(),.LOCK(lock),.CLKIN(clk27),.CLKFB(1'b0),
        .RESET(~reset_n),.RESET_P(1'b0),.FBDSEL(6'b0),.IDSEL(6'b0),.ODSEL(6'b0),
        .PSDA(4'b0),.DUTYDA(4'b0),.FDLY(4'b0));
    reg [2:0] rst_pipe=0;
    always @(posedge clk or negedge reset_n)
        if(!reset_n) rst_pipe<=0;
        else rst_pipe<={rst_pipe[1:0],lock};
    wire reset=!rst_pipe[2];
    wire [1:0] request_count;
    wire frozen,fault,trace_busy;
    window_observe_core core(.*);
    assign O_psram_cs_n=2'b11;
    assign O_psram_ck=2'b00;
    assign O_psram_ck_n=2'b11;
    assign O_psram_reset_n=2'b00;
    assign IO_psram_rwds=2'bzz;
    assign IO_psram_dq=16'hzzzz;
    assign sd_hiz=4'bzzzz;
    assign led_n=~{fault,frozen,trace_busy,request_count,lock};
endmodule
