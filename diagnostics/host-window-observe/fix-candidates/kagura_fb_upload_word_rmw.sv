// SPDX-License-Identifier: Apache-2.0
// Diagnostic fix hypothesis only; never substitute into the product implicitly.
// Avoid native byte-enable: merge a settled read value, then write all 32 bits.
// Caller MUST provide a read edge between partial writes; the CSR port's
// existing write_recovery/read-settle cycles are tested separately.
module kagura_fb_upload_word(
    input wire clk,write,
    input wire [3:0] byte_enable,
    input wire [31:0] wdata,
    output wire [31:0] rdata
);
    wire [31:0] merged;
    for(genvar lane=0;lane<4;lane++) begin: merge
        assign merged[lane*8+:8]=byte_enable[lane] ? wdata[lane*8+:8] : rdata[lane*8+:8];
    end
    SP #(.BIT_WIDTH(32),.READ_MODE(1'b0),.WRITE_MODE(2'b00),.RESET_MODE("SYNC")) storage(
        .CLK(clk),.CE(1'b1),.OCE(1'b1),.RESET(1'b0),.WRE(write),
        .BLKSEL(3'd0),.AD(14'h000f),.DI(merged),.DO(rdata));
endmodule
