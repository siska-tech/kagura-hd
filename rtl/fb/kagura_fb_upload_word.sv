// SPDX-License-Identifier: Apache-2.0
// A 32-bit lane of the 64-byte upload window. Explicit SP placement avoids
// Gowin converting the tiny working set into fabric FFs. Normal-mode writes
// hold rdata; a subsequent read edge exposes the newly stored word.
module kagura_fb_upload_word(
    input wire clk,write,
    input wire [3:0] byte_enable,
    input wire [31:0] wdata,
    output wire [31:0] rdata
);
`ifdef VERILATOR
`ifndef KAGURA_GOWIN_SIM
`define KAGURA_FB_UPLOAD_BEHAVIORAL
`endif
`endif
`ifdef KAGURA_FB_UPLOAD_BEHAVIORAL
    reg [31:0] memory;
    reg [31:0] result;
    always @(posedge clk)
        if(write) begin
            for(integer lane=0;lane<4;lane=lane+1)
                if(byte_enable[lane]) memory[lane*8+:8]<=wdata[lane*8+:8];
        end else result<=memory;
    assign rdata=result;
`undef KAGURA_FB_UPLOAD_BEHAVIORAL
`else
    // In 32-bit SP mode AD[3:0] are byte write enables, AD[4] is
    // unused, and AD[13:5] is the word address (zero for this lane).
    SP #(.BIT_WIDTH(32),.READ_MODE(1'b0),.WRITE_MODE(2'b00),.RESET_MODE("SYNC")) storage(
        .CLK(clk),.CE(1'b1),.OCE(1'b1),.RESET(1'b0),.WRE(write),
        .BLKSEL(3'd0),.AD({10'd0,byte_enable}),.DI(wdata),.DO(rdata));
`endif
endmodule
