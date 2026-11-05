// SPDX-License-Identifier: Apache-2.0
// Diagnostic counterfactual ONLY. Same logical write/hold/read behavior as SP
// and its Verilator branch. Never add alongside the production leaf module.
module kagura_fb_upload_word(
    input wire clk,write,
    input wire [3:0] byte_enable,
    input wire [31:0] wdata,
    output wire [31:0] rdata
);
    reg [31:0] memory;
    reg [31:0] result;
    always @(posedge clk)
        if(write) begin
            for(integer lane=0;lane<4;lane++)
                if(byte_enable[lane]) memory[lane*8+:8]<=wdata[lane*8+:8];
        end else result<=memory;
    assign rdata=result;
endmodule
