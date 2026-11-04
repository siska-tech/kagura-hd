// SPDX-License-Identifier: Apache-2.0
// Single-command 640x360 packed-4bpp fill engine, 54 MHz domain.
// Byte addresses are relative to PSRAM die 0. Pages occupy 0..230399.
// Requests remain stable until mem_ready. Exactly one mem_done is required
// per accepted request (including writes), at least one cycle after acceptance.
// Odd edge pixels use a read/modify/write. The memory adapter must serialize
// other writers to the same page until done. Display and PCM reads may interleave.
// done/error pulse on completion/rejection. Reset cancels local work only.
module kagura_fb_fill (
    input wire clk, reset,
    input wire valid,
    output wire ready,
    input wire page,
    input wire [15:0] x, y, width, height,
    input wire [3:0] color,
    output reg done, error,
    output wire mem_valid,
    input wire mem_ready,
    output wire mem_write,
    output wire [21:0] mem_addr,
    output wire [7:0] mem_wdata,
    input wire mem_done,
    input wire [7:0] mem_rdata
);
    localparam IDLE=0, READ_REQ=1, READ_WAIT=2, WRITE_REQ=3, WRITE_WAIT=4;
    reg [2:0] state;
    reg [21:0] row_base;
    reg [8:0] first_byte, last_byte, current_byte;
    reg [8:0] rows_left;
    reg left_odd, right_even;
    reg [3:0] fill_color;
    reg [7:0] write_data;
    wire [16:0] final_x = end_x - 17'd1;
    wire edge_byte = (current_byte == first_byte && left_odd)
                  || (current_byte == last_byte && right_even);
    wire [16:0] end_x = {1'b0,x} + {1'b0,width};
    wire [16:0] end_y = {1'b0,y} + {1'b0,height};
    assign ready = state == IDLE && !reset;
    assign mem_valid = !reset && (state == READ_REQ || state == WRITE_REQ);
    assign mem_write = state == WRITE_REQ;
    assign mem_addr = row_base + {13'b0,current_byte};
    assign mem_wdata = write_data;

    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE;
            done <= 0;
            error <= 0;
            row_base <= 0;
            first_byte <= 0;
            last_byte <= 0;
            current_byte <= 0;
            rows_left <= 0;
            left_odd <= 0;
            right_even <= 0;
            fill_color <= 0;
            write_data <= 0;
        end else begin
            done <= 0;
            error <= 0;
            case (state)
                IDLE: if (valid) begin
                    if (x >= 640 || y >= 360 || end_x > 640 || end_y > 360) begin
                        done <= 1;
                        error <= 1;
                    end else if (width == 0 || height == 0) begin
                        done <= 1;
                    end else begin
                        row_base <= (page ? 22'd115200 : 22'd0)
                                  + ({13'b0,y[8:0]} << 8) + ({13'b0,y[8:0]} << 6);
                        first_byte <= x[9:1];
                        last_byte <= final_x[9:1];
                        current_byte <= x[9:1];
                        rows_left <= height[8:0];
                        left_odd <= x[0];
                        right_even <= end_x[0];
                        fill_color <= color;
                        write_data <= {color,color};
                        // Exclusive end odd means last pixel is even.
                        state <= (x[0] || (width == 1)) ? READ_REQ : WRITE_REQ;
                    end
                end
                READ_REQ: if (mem_ready) state <= READ_WAIT;
                READ_WAIT: if (mem_done) begin
                    write_data <= {
                        (current_byte == first_byte && left_odd) ? mem_rdata[7:4] : fill_color,
                        (current_byte == last_byte && right_even) ? mem_rdata[3:0] : fill_color
                    };
                    state <= WRITE_REQ;
                end
                WRITE_REQ: if (mem_ready) state <= WRITE_WAIT;
                WRITE_WAIT: if (mem_done) begin
                    write_data <= {fill_color,fill_color};
                    if (current_byte == last_byte) begin
                        if (rows_left == 1) begin
                            state <= IDLE;
                            done <= 1;
                        end else begin
                            row_base <= row_base + 22'd320;
                            rows_left <= rows_left - 9'd1;
                            current_byte <= first_byte;
                            state <= (left_odd || (first_byte == last_byte && right_even))
                                   ? READ_REQ : WRITE_REQ;
                        end
                    end else begin
                        current_byte <= current_byte + 9'd1;
                        state <= (current_byte + 9'd1 == last_byte && right_even)
                               ? READ_REQ : WRITE_REQ;
                    end
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule


