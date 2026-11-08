// SPDX-License-Identifier: Apache-2.0
// Break the asynchronous descriptor-RAM -> opcode/operand decode path.
// Keep the captured descriptor (including tag) stable through completion and
// READ's delayed retirement. The register endpoint controls retirement/ACK.
module kagura_fb_command_head (
    input wire clk,reset,
    input wire in_valid,
    output wire in_ready,
    input wire [127:0] in_command,
    output wire out_valid,
    input wire out_ready,out_done,
    output reg [127:0] out_command
);
    reg pending,issued;
    assign in_ready=!reset && !pending;
    assign out_valid=!reset && pending && !issued;
    always @(posedge clk) begin
        if(reset) begin pending<=0;issued<=0;out_command<=0;end
        else begin
            if(in_valid && in_ready) begin
                out_command<=in_command;pending<=1;issued<=0;
            end
            if(out_valid && out_ready) issued<=1;
            if(out_done) begin pending<=0;issued<=0;end
        end
    end
endmodule
