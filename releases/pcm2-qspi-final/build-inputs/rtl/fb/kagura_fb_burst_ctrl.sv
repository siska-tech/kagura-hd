// SPDX-License-Identifier: Apache-2.0
// Bounded linear HyperBus transactions for Kagura-FB. Derived from the
// timing/CA/PHY contract of rtl/memory/kagura_hyperram_ctrl.sv.
// One command moves 1..16 32-bit words. Byte 0 is data[7:0], mask=1 inhibits
// a byte write. Address is a die-relative word index (4 MiB die).
// valid/data are held until ready. done follows the CS-high recovery gap for
// reads AND writes. error accompanies done on an invalid command, with no IO.
// Fixed CR0, 54 MHz CK, LAT=14/RDL=6 follow the existing board configuration.
// Requests are split at every absolute 32-byte boundary. TX/mask shift state
// and the RX one-hot slot continue across CS-separated chunks; no second
// payload buffer or change to the client interface is required.
// CA45, CR0, LAT/RDL and PHY remain unchanged pending separate review.
module kagura_fb_burst_ctrl #(
    parameter integer INIT_CYCLES=4096,
    parameter integer LAT=14,
    parameter integer RDL=6,
    parameter integer CS_HIGH_CYCLES=2
) (
    input wire clk, reset,
    input wire valid,
    output wire ready,
    input wire write,
    input wire [19:0] addr,
    input wire [4:0] words,
    input wire [511:0] wdata,
    input wire [63:0] mask,
    output reg done, error,
    output wire [511:0] rdata,
    // Unstallable tap; reserve a request before acceptance. Legacy rdata and
    // physical transfer/completion timing are unaffected.
    output reg rword_valid,
    output reg [31:0] rword_data,
    output wire initialized,
    output wire phy_reset_n, phy_cs_n, phy_ck_en, phy_dq_oe,
    output wire [7:0] phy_dq_o_rise, phy_dq_o_fall,
    output wire phy_rwds_oe, phy_rwds_o_rise, phy_rwds_o_fall,
    output wire phy_dq_tx, phy_rwds_tx,
    input wire [7:0] phy_dq_i_rise, phy_dq_i_fall
);
    localparam integer CW=$clog2(INIT_CYCLES+2)>7 ? $clog2(INIT_CYCLES+2) : 7;
    localparam INIT=0, CONFIG=1, IDLE=2, TRANSFER=3, GAP=4, CHECK=5, PREPARE=6;
    reg [2:0] state;
    reg [CW-1:0] init_tick;
    reg [6:0] tick,last_tick,clock_end;
    reg calibrated, configuring, writing, last_region;
    reg [4:0] address_tail;
    reg [5:0] pairs;
    reg [19:0] cursor;
    reg [4:0] remaining;
    wire [4:0] capacity=5'd8-{2'b00,cursor[2:0]};
    wire [4:0] chunk_words=remaining<capacity ? remaining : capacity;
    reg [47:0] ca;
    reg [511:0] tx;
    reg capture_enable,clear_receive;
    reg [31:0] capture_slot;
    // One-hot capture avoids both a 512-bit alignment barrel shifter and
    // a counter/subtractor on every receive register's clock enable.
    genvar slot;
    generate for(slot=0;slot<32;slot=slot+1) begin: receive
        reg [15:0] pair_data;
        always @(posedge clk) begin
            if(reset || clear_receive) pair_data<=0;
            else if(capture_enable && capture_slot[slot]) pair_data<={phy_dq_i_fall,phy_dq_i_rise};
        end
        assign rdata[slot*16+:16]=pair_data;
    end endgenerate
    reg [63:0] tx_mask;
    reg [15:0] read_half;
    reg read_half_valid;
    always @(posedge clk) begin
        if(reset) begin
            read_half<=0; read_half_valid<=0; rword_valid<=0; rword_data<=0;
        end else begin
            rword_valid<=0;
            if(clear_receive) read_half_valid<=0;
            else if(capture_enable) begin
                read_half_valid<=!read_half_valid;
                if(!read_half_valid) read_half<={phy_dq_i_fall,phy_dq_i_rise};
                else begin
                    rword_data<={phy_dq_i_fall,phy_dq_i_rise,read_half};
                    rword_valid<=1;
                end
            end
        end
    end
    // A <=16-word transaction can cross the 4 MiB limit only in the
    // final 32-word region. Keep a long address carry chain off the FSM.
    wire [5:0] tail_sum={1'b0,address_tail}+{1'b0,pairs[5:1]};
    wire beyond_die=last_region && tail_sum>6'd32;
    wire [6:0] latency=configuring ? 7'd3 : 7'(LAT);
    wire [6:0] data_start=latency+7'd1;
    wire transferring=state==TRANSFER;
    wire ca_phase=transferring && tick>=1 && tick<=3;
    wire data_phase=transferring && tick>=data_start && tick<=clock_end;
    wire [15:0] ca_pair=ca_phase ? 16'(ca >> ((3-int'(tick))*16)) : 16'd0;
    assign ready=!reset && state==IDLE;
    assign initialized=calibrated;
    assign phy_reset_n=!(reset || (state==INIT && init_tick<CW'(INIT_CYCLES/2)));
    assign phy_cs_n=reset || !transferring;
    assign phy_ck_en=!reset && transferring && tick>=1 && tick<=clock_end;
    assign phy_dq_oe=!reset && (ca_phase || (data_phase && writing));
    assign phy_rwds_oe=!reset && data_phase && writing && !configuring;
    assign {phy_dq_o_rise,phy_dq_o_fall}=ca_phase ? ca_pair :
        configuring ? 16'h8f1f : {tx[7:0],tx[15:8]};
    assign phy_rwds_o_rise=tx_mask[0];
    assign phy_rwds_o_fall=tx_mask[1];
    wire after_write=state==GAP && tick==0;
    assign phy_dq_tx=!reset && ((transferring && tick<=4) ||
        (transferring && writing && tick>=data_start-1'b1) || (after_write && writing));
    assign phy_rwds_tx=!reset && ((transferring && writing && !configuring && tick>=data_start-1'b1) ||
        (after_write && writing && !configuring));
    function automatic [47:0] make_ca(input rd, input registers, input [31:0] halfword_addr);
        make_ca={rd,registers,1'b1,halfword_addr[31:3],13'b0,halfword_addr[2:0]};
    endfunction
    always @(posedge clk) begin
        if(reset) begin
            state<=INIT; init_tick<=0; tick<=0; last_tick<=0; clock_end<=0; calibrated<=0; configuring<=0; writing<=0;
            last_region<=0; address_tail<=0; pairs<=0; cursor<=0; remaining<=0; ca<=0; tx<=0; tx_mask<=0; capture_slot<=0; clear_receive<=0; capture_enable<=0; done<=0; error<=0;
        end else begin
            done<=0;
            error<=0;
            clear_receive<=state==IDLE && valid;
            case(state)
                INIT: if(init_tick==CW'(INIT_CYCLES)) begin
                    tick<=0; state<=CONFIG;
                end else init_tick<=init_tick+1'b1;
                CONFIG: begin
                    configuring<=1; writing<=1; last_tick<=7'd4; clock_end<=7'd4;
                    ca<=make_ca(0,1,32'h800);
                    tick<=0; state<=TRANSFER;
                end
                IDLE: begin
                    // Capture while idle, independently of valid and bounds.
                    // Source mux/control depth must not drive 512-bit enables.
                    // Invalid requests never enter TRANSFER or assert CS.
                    configuring<=0; writing<=write; pairs<={words,1'b0};
                    cursor<=addr; capture_slot<=32'd1;
                    // Bound the active transfer counter independently of the
                    // long power-up delay; precompute terminal counts once.
                    ca<=make_ca(!write,0,{11'b0,addr,1'b0});
                    tx<=wdata; tx_mask<=mask; capture_enable<=0;
                    last_region<=&addr[19:5]; address_tail<=addr[4:0];
                    tick<=0; if(valid) state<=CHECK;
                end
                CHECK: begin
                    remaining<=pairs[5:1];
                    if(pairs[5:1]==0 || pairs[5:1]>16 || beyond_die) begin done<=1; error<=1; state<=IDLE; end
                    else state<=PREPARE;
                end
                PREPARE: begin
                    // At most 8 words and never across an absolute 32B edge.
                    pairs<={chunk_words,1'b0};
                    remaining<=remaining-chunk_words;
                    clock_end<=7'(LAT)+{1'b0,chunk_words,1'b0};
                    last_tick<=7'(LAT)+{1'b0,chunk_words,1'b0}+(writing ? 7'd0 : 7'(RDL));
                    ca<=make_ca(!writing,0,{11'b0,cursor,1'b0});
                    cursor<={cursor[19:3]+1'b1,3'b000};
                    tick<=0;state<=TRANSFER;
                end
                TRANSFER: begin
                    if(data_phase && writing && !configuring) begin
                        tx<=tx>>16; tx_mask<=tx_mask>>2;
                    end
                    // Registered one-hot slots select the receiving pair without
                    // a wide alignment mux or variable write decoder.
                    if(!writing && tick==7'(LAT+RDL)) capture_enable<=1;
                    if(capture_enable) capture_slot<=capture_slot<<1;
                    if(tick==last_tick) begin capture_enable<=0; tick<=0; state<=GAP; end
                    else tick<=tick+1'b1;
                end
                GAP: if(tick==7'(CS_HIGH_CYCLES-1)) begin
                    tick<=0; calibrated<=1;
                    if(configuring) state<=IDLE;
                    else if(remaining!=0) state<=PREPARE;
                    else begin done<=1;state<=IDLE;end
                    configuring<=0;
                end else tick<=tick+1'b1;
                default: begin state<=INIT; init_tick<=0; tick<=0; end
            endcase
        end
    end
endmodule
