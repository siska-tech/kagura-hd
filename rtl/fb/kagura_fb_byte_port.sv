// SPDX-License-Identifier: Apache-2.0
// Dedicated, single-outstanding bridge to kagura_hyperram_ctrl.
// ctrl_cmd_rdy must be the controller's actual idle indication, not an
// arbiter grant. Write completion waits for busy followed by idle.
// Reset must also reset the controller. No caching, so other readers remain
// coherent. Serialize other writers around the fill engine's edge RMW.
module kagura_fb_byte_port (
    input wire clk, reset, initialized,
    input wire mem_valid,
    output wire mem_ready,
    input wire mem_write,
    input wire [21:0] mem_addr,
    input wire [7:0] mem_wdata,
    output reg mem_done,
    output reg [7:0] mem_rdata,
    output wire ctrl_cmd, ctrl_cmd_en,
    input wire ctrl_cmd_rdy,
    output wire [19:0] ctrl_addr,
    output wire [31:0] ctrl_wr_data,
    output wire [3:0] ctrl_data_mask,
    input wire [31:0] ctrl_rd_data,
    input wire ctrl_rd_data_valid
);
    localparam IDLE=0, READ_WAIT=1, WRITE_BUSY=2, WRITE_IDLE=3;
    reg [1:0] state, lane;
    assign mem_ready = !reset && initialized && state==IDLE && ctrl_cmd_rdy;
    assign ctrl_cmd_en = mem_valid && mem_ready;
    assign ctrl_cmd = mem_write;
    assign ctrl_addr = mem_addr[21:2];
    assign ctrl_wr_data = {4{mem_wdata}};
    assign ctrl_data_mask = ~(4'b0001 << mem_addr[1:0]);
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;
            lane<=0;
            mem_done<=0;
            mem_rdata<=0;
        end else begin
            mem_done<=0;
            case(state)
                IDLE: if(ctrl_cmd_en) begin
                    lane<=mem_addr[1:0];
                    state<=mem_write ? WRITE_BUSY : READ_WAIT;
                end
                READ_WAIT: if(ctrl_rd_data_valid) begin
                    case(lane)
                        0: mem_rdata<=ctrl_rd_data[7:0];
                        1: mem_rdata<=ctrl_rd_data[15:8];
                        2: mem_rdata<=ctrl_rd_data[23:16];
                        3: mem_rdata<=ctrl_rd_data[31:24];
                    endcase
                    mem_done<=1;
                    state<=IDLE;
                end
                WRITE_BUSY: if(!ctrl_cmd_rdy) state<=WRITE_IDLE;
                WRITE_IDLE: if(ctrl_cmd_rdy) begin
                    mem_done<=1;
                    state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule

