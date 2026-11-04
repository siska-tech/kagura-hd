// SPDX-License-Identifier: Apache-2.0
// Fetch one logical 640-pixel packed-4bpp line into an inactive line bank.
// Five 64-byte memory reads become eighty 32-bit synchronous RAM writes.
// All ports are in the 54 MHz domain. The caller owns bank selection and
// must not display this bank until done. Reset is common with the arbiter.
module kagura_fb_line_fetch (
    input wire clk,reset,start,page,
    input wire [8:0] row,
    output wire ready,
    output reg done,error,
    output wire req_valid,
    input wire req_ready,
    output reg [19:0] req_addr,
    input wire rsp_done,rsp_error,
    input wire [511:0] rsp_data,
    output wire bank_we,
    output wire [6:0] bank_addr,
    output wire [31:0] bank_data
);
    localparam IDLE=0, ISSUE=1, WAIT=2, DRAIN=3;
    reg [1:0] state;
    reg [2:0] burst;
    reg [3:0] word_index;
    reg [511:0] buffer;
    assign ready=!reset && state==IDLE;
    assign req_valid=!reset && state==ISSUE;
    assign bank_we=!reset && state==DRAIN;
    assign bank_addr={burst,word_index};
    assign bank_data=buffer[31:0];
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE; done<=0; error<=0; req_addr<=0;
            burst<=0; word_index<=0; buffer<=0;
        end else begin
            done<=0; error<=0;
            case(state)
                IDLE: if(start) begin
                    if(row>=360) begin done<=1; error<=1; end
                    else begin
                        req_addr<=(page ? 20'd28800 : 20'd0)
                            + ({11'b0,row} << 6) + ({11'b0,row} << 4);
                        burst<=0; state<=ISSUE;
                    end
                end
                ISSUE: if(req_ready) state<=WAIT;
                WAIT: if(rsp_done) begin
                    if(rsp_error) begin done<=1; error<=1; state<=IDLE; end
                    else begin buffer<=rsp_data; word_index<=0; state<=DRAIN; end
                end
                DRAIN: begin
                    buffer<=buffer>>32;
                    if(word_index==15) begin
                        if(burst==4) begin done<=1; state<=IDLE; end
                        else begin burst<=burst+1'b1; req_addr<=req_addr+20'd16; state<=ISSUE; end
                    end else word_index<=word_index+1'b1;
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
