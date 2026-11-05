// SPDX-License-Identifier: Apache-2.0
// Diagnostic-only bounded recorder. Tap data is observational, never drives PHY.
// Configure source before arm. Samples include a cycle offset; no live UART mux.
module psram_boundary_capture # (parameter integer DEPTH=64)(
    input wire clk,reset,arm,trigger,
    input wire [1:0] source,
    input wire [31:0] tx_sample,rx_sample,request_sample,window_sample,
    input wire sample_valid,
    output reg frozen,overflow,
    output reg [$clog2(DEPTH+1)-1:0] count,
    input wire [$clog2(DEPTH)-1:0] read_index,
    output reg [47:0] read_data
);
    reg active,armed;
    reg [1:0] selected;
    reg [15:0] cycle;
    reg [47:0] samples[0:DEPTH-1];
    wire [31:0] selected_data=selected==0 ? tx_sample : selected==1 ? rx_sample :
                                    selected==2 ? request_sample : window_sample;
    always @(posedge clk) begin
        read_data<=samples[read_index];
        if(reset) begin active<=0;armed<=0;frozen<=0;overflow<=0;count<=0;cycle<=0;selected<=0;end
        else begin
            if(arm && !armed && !active && !frozen) begin armed<=1;selected<=source;end
            if(trigger && armed) begin active<=1;armed<=0;cycle<=0;end
            if(active) begin
                cycle<=cycle+1'b1;
                if(sample_valid) begin
                    samples[count[$clog2(DEPTH)-1:0]]<={cycle,selected_data};
                    count<=count+1'b1;
                    if(count==DEPTH-1) begin active<=0;frozen<=1;end
                end
                if(cycle==16'hffff) begin active<=0;frozen<=1;overflow<=1;end
            end
        end
    end
endmodule
