// SPDX-License-Identifier: Apache-2.0
// A 32-bit lane of the 64-byte upload window. Avoid native partial-byte SP
// writes on GW1NR-9C: merge settled rdata and always write a complete word.
// A read edge must separate partial writes; the CSR port's recovery cycles
// provide this. Full-word bulk captures need no previous read value.
// The integrated CSR now shares its CPU merge and supplies byte_enable=1111,
// allowing the per-lane merge below to collapse to a complete-word input.
module kagura_fb_upload_word(
    input wire clk,write,
    input wire [3:0] byte_enable,
    input wire [31:0] wdata,
    output wire [31:0] rdata
);
    wire [31:0] merged;
    generate for(genvar lane=0;lane<4;lane++) begin: merge
        assign merged[lane*8+:8]=byte_enable[lane] ? wdata[lane*8+:8] : rdata[lane*8+:8];
    end endgenerate
`ifdef VERILATOR
`ifndef KAGURA_GOWIN_SIM
`define KAGURA_FB_UPLOAD_BEHAVIORAL
`endif
`endif
`ifdef KAGURA_FB_UPLOAD_BEHAVIORAL
    reg [31:0] memory;
    reg [31:0] result;
    always @(posedge clk)
        if(write) memory<=merged;
        else result<=memory;
    assign rdata=result;
`undef KAGURA_FB_UPLOAD_BEHAVIORAL
`else
    // Constant low address bits enable the complete word in the generic SP
    // model. No dynamic native byte-enable dependency remains.
    SP #(.BIT_WIDTH(32),.READ_MODE(1'b0),.WRITE_MODE(2'b00),.RESET_MODE("SYNC")) storage(
        .CLK(clk),.CE(1'b1),.OCE(1'b1),.RESET(1'b0),.WRE(write),
        .BLKSEL(3'd0),.AD(14'h000f),.DI(merged),.DO(rdata));
`endif
endmodule
