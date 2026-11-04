// SPDX-License-Identifier: Apache-2.0
// 640x360 indexed framebuffer -> 1280x720, nearest-neighbour 2x scanout.
// Coordinates are the current HDMI pixel-domain coordinates (1650x750 total).
// A five-pixel lookahead includes controls, RAM, index, selection and RGB.
// System/pixel resets must be asserted together. Mailbox payloads are held
// until ack; the board implementation must constrain these CDC paths.
module kagura_fb_scanout (
    input wire sys_clk,sys_reset,pix_clk,pix_reset,
    input wire [10:0] cx,
    input wire [9:0] cy,
    input wire present_valid,present_page,
    input wire [191:0] present_palette,
    output wire present_ready,
    output reg present_done,
    output wire req_valid,
    input wire req_ready,
    output wire [19:0] req_addr,
    input wire rsp_done,rsp_error,
    input wire [511:0] rsp_data,
    output reg [23:0] rgb,
    output wire underrun,
    output reg memory_error,
    output wire [15:0] generation_out
);
    reg present_toggle,present_pending;
    reg held_page;
    reg [191:0] held_palette;
    reg present_ack,present_seen;
    (* ASYNC_REG="TRUE" *) reg [1:0] present_sync,present_ack_sync;
    assign present_ready=!sys_reset && !present_pending;
    always @(posedge sys_clk) begin
        if(sys_reset) begin
            present_toggle<=0; present_pending<=0; held_page<=0;
            held_palette<=0; present_ack_sync<=0; present_done<=0;
        end else begin
            present_ack_sync<={present_ack_sync[0],present_ack};
            present_done<=0;
            if(present_valid && present_ready) begin
                held_page<=present_page; held_palette<=present_palette;
                present_toggle<=~present_toggle; present_pending<=1;
            end else if(present_pending && present_ack_sync[1]==present_toggle) begin
                present_pending<=0; present_done<=1;
            end
        end
    end
    reg active_page,started;
    reg [191:0] palette;
    reg [15:0] generation;
    assign generation_out=generation;
    reg vblank,take;
    reg [8:0] next_row;
    always @(posedge pix_clk) begin
        next_row<=cy==749 ? 9'd0 : 9'((cy+10'd1)>>1);
        if(pix_reset) begin vblank<=0; take<=0; end
        else begin
            vblank<=cx==1649 && cy==719;
            take<=started && cx==1644 && (cy==749 || (cy<719 && cy[0]));
        end
    end
    reg line_toggle,line_page;
    reg [8:0] line_row;
    reg [15:0] line_generation;
    reg line_ack;
    (* ASYNC_REG="TRUE" *) reg [1:0] line_ack_sync,line_sync;
    wire line_slot_free=line_toggle==line_ack_sync[1];
    always @(posedge pix_clk) begin
        if(pix_reset) begin
            present_sync<=0; present_ack<=0; present_seen<=0;
            active_page<=0; palette<=0; generation<=0; started<=0;
            line_toggle<=0; line_page<=0; line_row<=0; line_generation<=0; line_ack_sync<=0;
        end else begin
            present_sync<={present_sync[0],present_toggle};
            line_ack_sync<={line_ack_sync[0],line_ack};
            if(vblank) begin
                started<=1; generation<=generation+1'b1;
                if(present_sync[1]!=present_seen) begin
                    active_page<=held_page; palette<=held_palette;
                    present_ack<=present_sync[1]; present_seen<=present_sync[1];
                end
                if(line_slot_free) begin
                    line_page<=present_sync[1]!=present_seen ? held_page : active_page;
                    line_generation<=generation+1'b1; line_row<=0; line_toggle<=~line_toggle;
                end
            end else if(take && next_row<359 && line_slot_free) begin
                line_page<=active_page; line_row<=next_row+1'b1;
                line_generation<=generation; line_toggle<=~line_toggle;
            end
        end
    end
    reg fetching,fetch_start,line_seen,fetch_page;
    reg [8:0] fetch_row;
    reg [15:0] fetch_generation;
    wire fetch_ready,fetch_done,fetch_error,can_write,bank_we;
    wire [6:0] bank_addr;
    wire [31:0] bank_data;
    always @(posedge sys_clk) begin
        if(sys_reset) begin
            line_sync<=0; line_seen<=0; line_ack<=0; fetching<=0;
            fetch_start<=0; fetch_page<=0; fetch_row<=0; fetch_generation<=0; memory_error<=0;
        end else begin
            line_sync<={line_sync[0],line_toggle};
            fetch_start<=0;
            if(!fetching && fetch_ready && can_write && line_sync[1]!=line_seen) begin
                fetch_page<=line_page; fetch_row<=line_row; fetch_generation<=line_generation;
                line_seen<=line_sync[1]; fetching<=1; fetch_start<=1;
            end
            if(fetch_done) begin
                fetching<=0; line_ack<=line_seen;
                if(fetch_error) memory_error<=1;
            end
        end
    end
    kagura_fb_line_fetch fetch(
        .clk(sys_clk),.reset(sys_reset),.start(fetch_start),.page(fetch_page),.row(fetch_row),
        .ready(fetch_ready),.done(fetch_done),.error(fetch_error),.req_valid,.req_ready,.req_addr,
        .rsp_done,.rsp_error,.rsp_data,.bank_we,.bank_addr,.bank_data);
    // Register controls ahead of the RAM, index and palette pipeline.
    wire [10:0] ax5=cx>=1645 ? cx-11'd1645 : cx+11'd5;
    reg scan;
    reg [6:0] scan_addr;
    reg [4:0] scan_shift;
    always @(posedge pix_clk) begin
        scan<=!pix_reset && started && ((cx<1275 && cy<720) || (cx>=1645 && (cy==749 || cy<719)));
        scan_addr<=ax5[10:4];
        scan_shift<={ax5[3:2],~ax5[1],2'b00};
    end
    wire [31:0] pixel_word;
    wire pixel_valid,line_valid;
    kagura_fb_line_banks banks(
        .sys_clk,.sys_reset,.sys_can_write(can_write),.sys_write(bank_we),
        .sys_addr(bank_addr),.sys_data(bank_data),.sys_done(fetch_done && !fetch_error),
        .sys_row(fetch_row),.sys_page(fetch_page),.sys_generation(fetch_generation),
        .pix_clk,.pix_reset,.pix_take(take),.pix_enable(scan),.pix_addr(scan_addr),
        .pix_row(next_row),.pix_page(active_page),.pix_generation(generation),
        .pix_data(pixel_word),.pix_data_valid(pixel_valid),.pix_line_valid(line_valid),.pix_underrun(underrun));
    reg [4:0] nibble_shift;
    reg [15:0] color_select;
    reg index_valid,color_valid;
    reg [3:0] index;
    wire [3:0] pixel_index=4'(pixel_word>>nibble_shift);
    wire [11:0] color_group[0:3];
    wire [11:0] color=color_group[0]|color_group[1]|color_group[2]|color_group[3];
    // One-hot registered selection and a balanced OR tree replace the long
    // 16-color variable mux. The extra selection stage is compensated by
    // the five-pixel lookahead; line ownership is taken one pixel earlier.
    genvar group_id;
    generate for(group_id=0;group_id<4;group_id=group_id+1) begin: palette_group
        assign color_group[group_id]=
            (palette[(group_id*4+0)*12+:12]&{12{color_select[group_id*4+0]}})|
            (palette[(group_id*4+1)*12+:12]&{12{color_select[group_id*4+1]}})|
            (palette[(group_id*4+2)*12+:12]&{12{color_select[group_id*4+2]}})|
            (palette[(group_id*4+3)*12+:12]&{12{color_select[group_id*4+3]}});
    end endgenerate
    always @(posedge pix_clk) begin
        nibble_shift<=scan_shift;
        index<=pixel_index;
        color_select<=16'd1<<index;
        index_valid<=!pix_reset && pixel_valid;
        color_valid<=!pix_reset && index_valid;
        if(pix_reset || !color_valid) rgb<=0;
        else rgb<={color[11:8],color[11:8],color[7:4],color[7:4],color[3:0],color[3:0]};
    end
endmodule
