// SPDX-License-Identifier: Apache-2.0
// Controller-response replacement for host-path isolation. No PSRAM interface.
// Never echoes WRITE data into READ: independent address-derived ROM oracle.
module psram_host_stub(
    input wire clk,reset,host_valid,host_write,
    input wire [19:0] host_addr,
    input wire [4:0] host_words,
    input wire [511:0] host_wdata,
    input wire [63:0] host_mask,
    output wire mem_ready,
    output reg mem_done,mem_error,
    output reg [511:0] mem_rdata,
    output reg [511:0] accepted_data,
    output reg [63:0] accepted_mask,
    output reg [19:0] accepted_addr,
    output reg [4:0] accepted_words,
    output reg accepted_write
);
    reg pending;
    assign mem_ready=!reset && !pending && !mem_done;
    always @(posedge clk) begin
        if(reset) begin
            pending<=0;mem_done<=0;mem_error<=0;mem_rdata<=0;
            accepted_data<=0;accepted_mask<=0;accepted_addr<=0;accepted_words<=0;accepted_write<=0;
        end else begin
            mem_done<=pending;pending<=0;mem_error<=0;
            if(host_valid && mem_ready) begin
                accepted_data<=host_wdata;accepted_mask<=host_mask;
                accepted_addr<=host_addr;accepted_words<=host_words;accepted_write<=host_write;
                pending<=1;
                // Deliberately differs from the uploaded byte pattern.
                for(integer i=0;i<64;i++) mem_rdata[i*8+:8]<=8'((host_addr*4+i)*13+8'h5b);
            end
        end
    end
endmodule
