// SPDX-License-Identifier: Apache-2.0
// Fetch one logical 640-pixel packed-4bpp line into an inactive line bank.
// Five 64-byte memory reads stream into eighty reserved line RAM words.
// The tap cannot stall. Partial writes must never be published on error.
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
    input wire scan_word_valid,
    input wire [31:0] scan_word_data,
    output wire bank_we,
    output wire [6:0] bank_addr,
    output wire [31:0] bank_data
);
    localparam IDLE=0, ISSUE=1, WAIT=2;
    reg [1:0] state;
    reg [2:0] burst;
    reg [4:0] word_count;
    reg overflow;
    wire receiving=state==WAIT && scan_word_valid;
    wire final_count_ok=word_count==16 || (word_count==15 && receiving);
    assign ready=!reset && state==IDLE;
    assign req_valid=!reset && state==ISSUE;
    assign bank_we=!reset && receiving && word_count<16 && !(rsp_done && rsp_error);
    assign bank_addr={burst,word_count[3:0]};
    assign bank_data=scan_word_data;
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE; done<=0; error<=0; req_addr<=0;
            burst<=0; word_count<=0; overflow<=0;
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
                ISSUE: if(req_ready) begin
                    word_count<=0; overflow<=0; state<=WAIT;
                end
                WAIT: begin
                    if(receiving) begin
                        if(word_count<16) word_count<=word_count+1'b1;
                        else overflow<=1;
                    end
                    if(rsp_done) begin
                        if(rsp_error || overflow || !final_count_ok ||
                           (receiving && word_count==16)) begin
                            done<=1; error<=1; state<=IDLE;
                        end else if(burst==4) begin done<=1; state<=IDLE; end
                        else begin
                            burst<=burst+1'b1; req_addr<=req_addr+20'd16; state<=ISSUE;
                        end
                    end
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
