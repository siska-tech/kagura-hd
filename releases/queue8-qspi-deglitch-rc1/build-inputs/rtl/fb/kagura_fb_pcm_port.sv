// SPDX-License-Identifier: Apache-2.0
// Byte PCM requests -> one-word burst client, with a coherent one-word cache.
// Both interfaces use independent valid/ready (no combinational valid/ready
// loop through the arbiter). Flush on sample reconfiguration and GPU writes.
module kagura_fb_pcm_port (
    input wire clk,reset,initialized,flush,
    input wire mem_req_valid,
    output wire mem_req_ready,
    input wire [21:0] mem_req_addr,
    output reg mem_rsp_valid,mem_rsp_error,
    output reg [7:0] mem_rsp_data,
    output wire req_valid,
    input wire req_ready,
    output reg [19:0] req_addr,
    input wire rsp_done,rsp_error,
    input wire [31:0] rsp_data
);
    localparam IDLE=0, ISSUE=1, WAIT=2, LOOKUP=3;
    reg [1:0] state,lane;
    reg cache_valid,invalidated;
    reg [19:0] cache_tag;
    reg [31:0] cache_data;
    wire cache_hit=cache_valid && !flush && cache_tag==req_addr;
    assign mem_req_ready=!reset && initialized && state==IDLE;
    assign req_valid=!reset && state==ISSUE;
    function automatic [7:0] byte_at(input [31:0] data,input [1:0] byte_lane);
        byte_at=8'(data>>(byte_lane*8));
    endfunction
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE; lane<=0; req_addr<=0; cache_valid<=0; invalidated<=0; cache_tag<=0; cache_data<=0;
            mem_rsp_valid<=0; mem_rsp_error<=0; mem_rsp_data<=0;
        end else begin
            mem_rsp_valid<=0; mem_rsp_error<=0;
            if(flush) begin cache_valid<=0; invalidated<=1; end
            case(state)
                IDLE: if(mem_req_valid && mem_req_ready) begin
                    req_addr<=mem_req_addr[21:2]; lane<=mem_req_addr[1:0]; invalidated<=flush; state<=LOOKUP;
                end
                LOOKUP: begin
                    if(cache_hit && !invalidated) begin
                        mem_rsp_data<=byte_at(cache_data,lane); mem_rsp_valid<=1; state<=IDLE;
                    end else state<=ISSUE;
                end
                ISSUE: if(req_ready) state<=WAIT;
                WAIT: if(rsp_done) begin
                    mem_rsp_valid<=1; mem_rsp_error<=rsp_error;
                    mem_rsp_data<=byte_at(rsp_data,lane);
                    cache_valid<=!rsp_error && !flush && !invalidated; cache_tag<=req_addr; cache_data<=rsp_data;
                    state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
