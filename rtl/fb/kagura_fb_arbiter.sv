// SPDX-License-Identifier: Apache-2.0
// Three bounded transaction clients: 0 scanout, 1 PCM, 2 host/GPU.
// Only one operation is outstanding. The chosen owner is held until done.
// While scanout requests, alternate its grants with at most one PCM grant.
// With no scanout request, alternate PCM and GPU to avoid GPU starvation.
// Sources hold valid and relevant payload until req_ready (write data/mask
// are ignored for reads); rsp_done pulses after memory
// completion. The controller holds rdata until accepting its next command.
// Reset must be common with the downstream memory controller.
module kagura_fb_arbiter (
    input wire clk, reset,
    input wire [2:0] req_valid,
    output wire [2:0] req_ready,
    input wire [2:0] req_write,
    input wire [2:0][19:0] req_addr,
    input wire [2:0][4:0] req_words,
    input wire [2:0][511:0] req_wdata,
    input wire [2:0][63:0] req_mask,
    output reg [2:0] rsp_done,
    output reg [2:0] rsp_error,
    output wire [511:0] rsp_data,
    output wire valid,
    input wire ready,
    output wire write,
    output wire [19:0] addr,
    output wire [4:0] words,
    output wire [511:0] wdata,
    output wire [63:0] mask,
    input wire done,error,
    input wire [511:0] rdata,
    input wire rword_valid,
    input wire [31:0] rword_data,
    output wire scan_word_valid,
    output wire [31:0] scan_word_data
);
    localparam IDLE=0, ISSUE=1, WAIT=2;
    reg [1:0] state,owner,last_owner;
    reg [1:0] selected;
    always @* begin
        if(req_valid[0]) selected=(req_valid[1] && last_owner==0) ? 2'd1 : 2'd0;
        else if(req_valid[1] && !(last_owner==1 && req_valid[2])) selected=1;
        else selected=2;
    end
    assign req_ready=(!reset && state==ISSUE && ready) ? (3'b001 << owner) : 3'b0;
    assign valid=!reset && state==ISSUE && req_valid[owner];
    assign write=req_write[owner];
    assign addr=req_addr[owner];
    assign words=req_words[owner];
    assign wdata=req_wdata[owner];
    assign mask=req_mask[owner];
    assign rsp_data=rdata;
    // Only the scanout owner consumes the unstallable read tap.
    assign scan_word_valid=!reset && state==WAIT && owner==0 && rword_valid;
    assign scan_word_data=rword_data;
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE; owner<=0; last_owner<=2;
            rsp_done<=0; rsp_error<=0;
        end else begin
            rsp_done<=0; rsp_error<=0;
            case(state)
                IDLE: if(req_valid[selected]) begin
                    owner<=selected;
                    state<=ISSUE;
                end
                ISSUE: if(ready && req_valid[owner]) begin last_owner<=owner; state<=WAIT; end
                WAIT: if(done) begin
                    rsp_done[owner]<=1; rsp_error[owner]<=error;
                    state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
