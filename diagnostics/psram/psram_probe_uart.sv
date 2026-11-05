// SPDX-License-Identifier: Apache-2.0
module psram_probe_uart #(parameter integer DIV=469)(
    input wire clk,reset,valid,
    input wire [7:0] data,
    output wire ready,tx
);
    reg [9:0] shift=10'h3ff;
    reg [3:0] bits=0;
    reg [$clog2(DIV)-1:0] count=0;
    assign ready=bits==0;
    assign tx=shift[0];
    always @(posedge clk) begin
        if(reset) begin shift<=10'h3ff;bits<=0;count<=0;end
        else if(ready) begin
            if(valid) begin shift<={1'b1,data,1'b0};bits<=10;count<=$clog2(DIV)'(DIV-1);end
        end else if(count==0) begin
            shift<={1'b1,shift[9:1]};bits<=bits-1'b1;count<=$clog2(DIV)'(DIV-1);
        end else count<=count-1'b1;
    end
endmodule
