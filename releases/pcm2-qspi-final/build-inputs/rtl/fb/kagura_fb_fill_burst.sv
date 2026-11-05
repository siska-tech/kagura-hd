// SPDX-License-Identifier: Apache-2.0
// Packed 4bpp rectangle fill and optional same-phase opaque copy, using
// up to 64-byte transactions. COPY source responses are captured externally
// into the shared upload window before the corresponding masked write.
// Odd nibble edges use a one-word RMW. Other writers must be serialized
// across the command; scanout and PCM may interleave between bursts.
module kagura_fb_fill_burst #(
    // Only for callers that validate the full rectangle before asserting valid.
    parameter bit VALIDATED_INPUT=0,
    parameter bit ENABLE_COPY=0,
    parameter bit NONEMPTY_INPUT=0
) (
    input wire clk,reset,valid,page,
    input wire copy,src_page,
    input wire [15:0] src_x,src_y,
    output wire capture_window,
    input wire [15:0] x,y,width,height,
    input wire [3:0] color,
    output wire ready,
    output reg done,error,
    output wire req_valid,
    input wire req_ready,
    output wire req_write,
    output reg [19:0] req_addr,
    output wire [4:0] req_words,
    output wire [511:0] req_wdata,
    output reg [63:0] req_mask,
    input wire rsp_done,rsp_error,
    input wire [511:0] rsp_data
);
    localparam IDLE=0,SETUP=1,READ_REQ=2,READ_WAIT=3,WRITE_REQ=4,WRITE_WAIT=5,ROW_BASE=6,COPY_CAPTURE=7,COPY_PLAN=8,COPY_Y=9,COPY_X=10,COPY_POSITION=11;
    reg [3:0] state;
    reg request_pending;
    reg [15:0] row_word,source_row_word;
    reg held_copy,backwards_x,backwards_y;
    reg [8:0] origin_y,origin_sy,last_row_offset;
    reg [7:0] source_delta;
    wire copying=ENABLE_COPY && copy;
    wire down=copying && page==src_page && y>src_y;
    wire rightwards=copying && page==src_page && y==src_y && x>src_x;
    reg held_page;
    reg [8:0] first_byte,end_byte,current_byte,rows_left;
    reg left_odd,right_odd,rmw;
    reg [3:0] fill_color;
    reg [4:0] chunk_words;
    reg [31:0] edge_data;
    wire [16:0] ex={1'b0,x}+{1'b0,width};
    wire [16:0] ey={1'b0,y}+{1'b0,height};
    wire [16:0] rounded_end=ex+17'd1;
    wire [8:0] last_byte=end_byte-9'd1;
    reg [6:0] last_word_index,end_word;
    wire [8:0] last_word={last_word_index,2'b00};
    wire need_rmw=!held_copy && ((left_odd && current_byte=={first_byte[8:2],2'b00}) ||
                  (right_odd && current_byte==last_word));
    // Work in word indices: avoid byte subtraction followed by rounding.
    wire [6:0] limit_word=right_odd && current_byte[8:2]<last_word_index ? last_word_index : end_word;
    wire [6:0] words_left=limit_word-current_byte[8:2];
    wire [6:0] reverse_distance=current_byte[8:2]-first_byte[8:2];
    wire reverse_full=reverse_distance>=7'd15;
    wire [4:0] copy_words=backwards_x ? (reverse_full ? 5'd16 : {1'b0,reverse_distance[3:0]}+5'd1) :
                        (words_left>16 ? 5'd16 : words_left[4:0]);
    wire [4:0] next_words=need_rmw ? 5'd1 : words_left>16 ? 5'd16 : words_left[4:0];
    wire [6:0] setup_word=backwards_x ? (reverse_full ? current_byte[8:2]-7'd15 : first_byte[8:2]) : current_byte[8:2];
    wire [8:0] setup_byte={setup_word,2'b00};
    wire [9:0] next_byte={1'b0,current_byte}+{3'b0,chunk_words,2'b00};
    reg [63:0] byte_mask;
    reg [3:0] first_mask,last_mask;
    wire [8:0] tail_distance=last_word-current_byte;
    reg [31:0] patched_data;
    reg row_finished;
    reg [7:0] patch_mask;
    reg [7:0] patch_mask_next;
    // Geometry and chunk fields settle before READ/WRITE response states.
    // Register control decisions without changing the FSM or bus latency.
    always @(posedge clk) begin
        if(reset) begin row_finished<=0;patch_mask<=0;end
        else begin
            row_finished<=backwards_x ? current_byte[8:2]==first_byte[8:2] : next_byte>={1'b0,end_byte};
            patch_mask<=patch_mask_next;
        end
    end
    always @* begin
        // Interior bytes need no mask. Only the first/last word can be
        // partial; mask bits beyond req_words are not transmitted.
        case(first_byte[1:0])
            0: first_mask=4'b0000;
            1: first_mask=4'b0001;
            2: first_mask=4'b0011;
            3: first_mask=4'b0111;
        endcase
        case(end_byte[1:0])
            0: last_mask=4'b0000;
            1: last_mask=4'b1110;
            2: last_mask=4'b1100;
            3: last_mask=4'b1000;
        endcase
        byte_mask=current_byte[8:2]==first_byte[8:2] ? {60'd0,first_mask} : 64'd0;
        if(tail_distance[8:6]==0) byte_mask=byte_mask | ({60'd0,last_mask} << tail_distance[5:0]);
        patch_mask_next=0;
        for(integer i=0;i<4;i=i+1) begin
            if(int'(current_byte)+i>=int'(first_byte) && int'(current_byte)+i<int'(end_byte)) begin
                patch_mask_next[i*2]=!(right_odd && int'(current_byte)+i==int'(last_byte));
                patch_mask_next[i*2+1]=!(left_odd && int'(current_byte)+i==int'(first_byte));
            end
            patched_data[i*8+:4]=patch_mask[i*2] ? fill_color : rsp_data[i*8+:4];
            patched_data[i*8+4+:4]=patch_mask[i*2+1] ? fill_color : rsp_data[i*8+4+:4];
        end
    end
`ifndef SYNTHESIS
// synthesis translate_off
    always @(posedge clk) if(!reset && valid && ready && VALIDATED_INPUT)
        if(x>=640 || y>=360 || ex>640 || ey>360 || (NONEMPTY_INPUT && (width==0 || height==0))) $fatal(1,"unvalidated fill caller");
    always @(posedge clk) if(!reset && valid && ready && copying) begin
        if(!VALIDATED_INPUT || src_x>=640 || src_y>=360 ||
           {1'b0,src_x}+{1'b0,width}>640 || {1'b0,src_y}+{1'b0,height}>360 ||
           src_x[0] || x[0] || width[0] || src_x[2:0]!=x[2:0])
            $fatal(1,"unvalidated copy caller");
    end
// synthesis translate_on
`endif
    assign capture_window=held_copy && state==READ_WAIT && rsp_done && !rsp_error;
    assign ready=!reset && state==IDLE;
    assign req_valid=!reset && request_pending;
    assign req_write=state==WRITE_REQ;
    assign req_words=chunk_words;
    assign req_wdata=rmw ? {480'd0,edge_data} : {128{fill_color}};
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;request_pending<=0; done<=0; error<=0; row_word<=0; first_byte<=0; end_byte<=0;
            current_byte<=0; rows_left<=0; source_row_word<=0; held_copy<=0; backwards_x<=0; backwards_y<=0;origin_y<=0;origin_sy<=0;last_row_offset<=0;source_delta<=0; left_odd<=0; right_odd<=0; rmw<=0;
            last_word_index<=0; end_word<=0; held_page<=0; fill_color<=0; req_addr<=0; chunk_words<=0; edge_data<=0; req_mask<=0;
        end else begin
            done<=0; error<=0;
            case(state)
                IDLE: if(valid) begin
                    // Capture the coordinate product independently of validation.
                    // The next stage adds the page offset before issuing memory.
                    row_word<=({7'd0,y[8:0]}<<6)+({7'd0,y[8:0]}<<4);
                    origin_y<=y[8:0];origin_sy<=src_y[8:0];last_row_offset<=height[8:0]-9'd1;
                    source_delta<={1'b0,src_x[9:3]}-{1'b0,x[9:3]};
                    held_copy<=copying; backwards_x<=rightwards; backwards_y<=down;
                    held_page<=page;
                    if(!VALIDATED_INPUT && (x>=640 || y>=360 || ex>640 || ey>360)) begin done<=1; error<=1; end
                    else if(!NONEMPTY_INPUT && (VALIDATED_INPUT ? (width[9:0]==0 || height[8:0]==0) : (width==0 || height==0))) done<=1;
                    else begin
                        first_byte<=x[9:1]; end_byte<=rounded_end[9:1];
                        current_byte<={x[9:3],2'b00}; rows_left<=height[8:0];
                        left_odd<=!copying && x[0]; right_odd<=!copying && ex[0]; fill_color<=color; state<=copying ? COPY_POSITION : ROW_BASE;
                    end
                end
                COPY_POSITION: begin
                    if(backwards_y) begin origin_y<=origin_y+last_row_offset;origin_sy<=origin_sy+last_row_offset;end
                    state<=COPY_Y;
                end
                COPY_Y: begin
                    row_word<=({7'd0,origin_y}<<6)+({7'd0,origin_y}<<4);
                    source_row_word<=({7'd0,origin_sy}<<6)+({7'd0,origin_sy}<<4);
                    current_byte<=backwards_x ? {last_byte[8:2],2'b00} : {first_byte[8:2],2'b00};
                    state<=ROW_BASE;
                end
                ROW_BASE: begin
                    row_word<=row_word+(held_page ? 16'd28800 : 16'd0);
                    source_row_word<=source_row_word+(src_page ? 16'd28800 : 16'd0);
                    last_word_index<=last_byte[8:2];
                    end_word<=end_byte[8:2]+{6'd0,(|end_byte[1:0])}; state<=held_copy ? COPY_X : SETUP;
                end
                COPY_X: begin
                    // A signed word delta is applied modulo 16 bits. Adding
                    // current_byte later restores the validated absolute address.
                    source_row_word<=source_row_word+{{8{source_delta[7]}},source_delta};
                    state<=COPY_PLAN;
                end
                COPY_PLAN: begin
                    // Break reverse chunk arithmetic from mask/address setup.
                    current_byte<=setup_byte;chunk_words<=copy_words;state<=SETUP;
                end
                SETUP: begin
                    req_addr<={4'd0,(held_copy ? source_row_word : row_word)+{9'd0,current_byte[8:2]}};
                    request_pending<=1;rmw<=need_rmw; if(!held_copy) chunk_words<=next_words; req_mask<=byte_mask;
                    state<=held_copy || need_rmw ? READ_REQ : WRITE_REQ;
                end
                READ_REQ: if(req_ready) begin request_pending<=0;state<=READ_WAIT;end
                READ_WAIT: if(rsp_done) begin
                    if(rsp_error) begin state<=IDLE; done<=1; error<=1; end
                    else if(held_copy) state<=COPY_CAPTURE;
                    else begin edge_data<=patched_data; request_pending<=1;state<=WRITE_REQ; end
                end
                COPY_CAPTURE: begin
                    // Registers capture the source window on this edge. Only
                    // then may the arbiter accept the corresponding write.
                    req_addr<={4'd0,row_word+{9'd0,current_byte[8:2]}};
                    request_pending<=1;state<=WRITE_REQ;
                end
                WRITE_REQ: if(req_ready) begin request_pending<=0;state<=WRITE_WAIT;end
                WRITE_WAIT: if(rsp_done) begin
                    if(rsp_error) begin state<=IDLE; done<=1; error<=1; end
                    else if(row_finished) begin
                        if(rows_left==1) begin state<=IDLE; done<=1; end
                        else begin
                            rows_left<=rows_left-1'b1; row_word<=backwards_y ? row_word-16'd80 : row_word+16'd80;
                            source_row_word<=backwards_y ? source_row_word-16'd80 : source_row_word+16'd80;
                            current_byte<=backwards_x ? last_word : {first_byte[8:2],2'b00}; state<=held_copy ? COPY_PLAN : SETUP;
                        end
                    end else begin current_byte<=backwards_x ? current_byte-9'd4 : next_byte[8:0]; state<=held_copy ? COPY_PLAN : SETUP; end
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
