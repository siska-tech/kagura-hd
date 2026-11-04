// SPDX-License-Identifier: Apache-2.0
// Two 80x32 line banks with a tagged, acknowledged toggle mailbox.
// Both resets are asserted together, released in their respective domains.
// sys_done publishes the inactive bank and a stable row/page/generation tag.
// The pixel side consumes or discards it only at pix_take. A discarded stale
// tag never changes the displayed bank. The system reuses a bank only after
// the acknowledgement crosses back. Mailbox payloads stay stable until ack.
// pix_take precedes the first pixel read; reads on pix_take are invalidated.
module kagura_fb_line_banks (
    input wire sys_clk,sys_reset,
    output wire sys_can_write,
    input wire sys_write,
    input wire [6:0] sys_addr,
    input wire [31:0] sys_data,
    input wire sys_done,
    input wire [8:0] sys_row,
    input wire sys_page,
    input wire [15:0] sys_generation,
    input wire pix_clk,pix_reset,pix_take,pix_enable,
    input wire [6:0] pix_addr,
    input wire [8:0] pix_row,
    input wire pix_page,
    input wire [15:0] pix_generation,
    output wire [31:0] pix_data,
    output reg pix_data_valid,pix_line_valid,pix_underrun
);
    reg back_bank,published,request;
    reg [25:0] tag;
    // Held mailbox payload, captured locally before the two-stage request
    // synchronizer permits consumption. This isolates tag comparison from CDC.
    reg [25:0] pixel_tag;
    reg acknowledge,accepted,display_bank,seen;
    (* ASYNC_REG="TRUE" *) reg [1:0] request_sync,ack_sync;
    assign sys_can_write=!sys_reset && !published;
    always @(posedge sys_clk) begin
        if(sys_reset) begin
            back_bank<=1; published<=0; request<=0; tag<=0; ack_sync<=0;
        end else begin
            ack_sync<={ack_sync[0],acknowledge};
            if(sys_done && !published) begin
                tag<={sys_generation,sys_page,sys_row};
                request<=~request; published<=1;
            end else if(published && ack_sync[1]==request) begin
                if(accepted) back_bank<=~back_bank;
                published<=0;
            end
        end
    end
    always @(posedge pix_clk) begin
        if(pix_reset) begin
            request_sync<=0; acknowledge<=0; accepted<=0; display_bank<=0;
            seen<=0;pixel_tag<=0; pix_line_valid<=0; pix_data_valid<=0; pix_underrun<=0;
        end else begin
            request_sync<={request_sync[0],request};
            pixel_tag<=tag;
            pix_data_valid<=pix_enable && pix_line_valid && !pix_take && pix_addr<80;
            if(pix_take) begin
                if(request_sync[1]!=seen) begin
                    seen<=request_sync[1]; acknowledge<=request_sync[1];
                    if(pixel_tag=={pix_generation,pix_page,pix_row}) begin
                        accepted<=1; display_bank<=~display_bank; pix_line_valid<=1;
                    end else begin
                        accepted<=0; pix_line_valid<=0; pix_underrun<=1;
                    end
                end else begin pix_line_valid<=0; pix_underrun<=1; end
            end
        end
    end
    wire [31:0] unused_a[0:1],bank_data[0:1];
    genvar bank;
    generate for(bank=0;bank<2;bank=bank+1) begin: banks
        kagura_ram_tdp #(.DEPTH(80),.WIDTH(32)) ram(
            .clk_a(sys_clk),.enable_a(sys_can_write && sys_write && back_bank==1'(bank) && sys_addr<80),
            .write_a(1'b1),.addr_a(sys_addr),.wdata_a(sys_data),.rdata_a(unused_a[bank]),
            .clk_b(pix_clk),.enable_b(pix_enable && pix_line_valid && !pix_take && display_bank==1'(bank) && pix_addr<80),
            .addr_b(pix_addr),.rdata_b(bank_data[bank]));
    end endgenerate
    reg read_bank;
    always @(posedge pix_clk) read_bank<=display_bank;
    assign pix_data=bank_data[read_bank];
endmodule
