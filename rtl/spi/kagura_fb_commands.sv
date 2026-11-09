// SPDX-License-Identifier: Apache-2.0
// One outstanding, tagged FB command. The register endpoint locks both
// command and CPU writes to upload_data from acceptance through done. The
// descriptor stays stable; COPY updates upload_data via read_result internally. Completion tag/error is paired with done.
// Opcode 0 fence, 1 fill, 2 palette, 3 present, 4 write, 5 read, 6 aligned copy, 7 optional audio commit.
module kagura_fb_commands #(parameter bit AUDIO_CSR=0, parameter bit REGISTER_DECODE=0) (
    input wire clk,reset,valid,
    output wire ready,
    input wire [127:0] command,
    input wire [511:0] upload_data,
    output reg done,
    output reg [7:0] error,
    output wire [15:0] tag,
    output wire [511:0] read_data,
    output reg read_result,
    output wire host_valid,
    input wire host_ready,
    output wire host_write,
    output wire [19:0] host_addr,
    output wire [4:0] host_words,
    output wire [511:0] host_wdata,
    output wire [63:0] host_mask,
    input wire host_done,host_error,
    input wire [511:0] host_rdata,
    output wire present_valid,
    input wire present_ready,present_done,
    output wire present_page,
    output wire audio_capture,audio_apply,audio_commit_done,
    input wire audio_settings_valid,audio_busy,audio_settle,audio_ready,audio_done,audio_apply_error,
    output reg [191:0] present_palette
);
    localparam IDLE=0,EXECUTE=1,FILL_START=2,FILL_WAIT=3,MEM_REQ=4,MEM_WAIT=5,PRESENT_REQ=6,PRESENT_WAIT=7,DECODE=8,AUDIO_SNAPSHOT=9,AUDIO_SEND=10,AUDIO_WAIT=11,VALIDATE=12;
    localparam BAD_COMMAND=2,RANGE_ERROR=3,MEMORY_ERROR=4;
    reg [3:0] state;
    wire [127:0] desc=command;
    wire [7:0] opcode=desc[7:0],argument=desc[15:8];
    wire [31:0] byte_addr=desc[63:32];
    wire [5:0] end_tail={1'b0,byte_addr[6:2]}+{1'b0,argument[4:0]};
    wire beyond_die=(&byte_addr[21:7]) && end_tail>6'd32;
    assign tag=desc[31:16];
    // The memory controller holds its result until the next memory command.
    assign read_data=host_rdata;
    // The arbiter inserts IDLE/ISSUE before another controller acceptance.
    // Capture the read window one edge after host_done. rdata must remain
    // stable through that edge (the core guarantees it). The register endpoint
    // delays successful READ completion until the SP outputs have settled.
    reg copy_command;
    always @(posedge clk) begin
        if(reset) copy_command<=0;
        else if(state==IDLE && valid) copy_command<=opcode==6;
    end
    wire copy_capture;
    reg reading_command;
    always @(posedge clk) begin
        if(reset) reading_command<=0;
        else if(state==EXECUTE) reading_command<=REGISTER_DECODE ? opcode_q[5] : opcode==5;
    end
    always @(posedge clk) begin
        if(reset) read_result<=0;
        else read_result<=(state==MEM_WAIT && host_done && !host_error && reading_command) || (copy_capture && fill_active);
    end
    reg [16:0] fill_end_x,fill_end_y;
    reg palette_command_ok,copy_range_ok,engine_empty;
    wire [15:0] engine_x=copy_command ? desc[79:64] : desc[47:32];
    wire [15:0] engine_y=copy_command ? desc[95:80] : desc[63:48];
    // DECODE/EXECUTE settle this mux before FILL_START. Keep validation
    // on the original full-width descriptor; only stage the engine operand.
    reg [15:0] engine_y_q;
    always @(posedge clk) if(reset) engine_y_q<=0; else engine_y_q<=engine_y;
    wire [15:0] engine_width=copy_command ? desc[111:96] : desc[79:64];
    wire [15:0] engine_height=copy_command ? desc[127:112] : desc[95:80];
    wire [16:0] copy_sx_end={1'b0,desc[47:32]}+{1'b0,desc[111:96]};
    wire [16:0] copy_sy_end={1'b0,desc[63:48]}+{1'b0,desc[127:112]};
    always @(posedge clk) begin
        engine_empty<=engine_width==0 || engine_height==0;
        palette_command_ok<=argument<=15 && desc[47:44]==0 && desc[127:48]==0;
        fill_end_x<={1'b0,engine_x}+{1'b0,engine_width};
        fill_end_y<={1'b0,engine_y}+{1'b0,engine_height};
        copy_range_ok<=desc[47:32]<640 && desc[63:48]<360 && desc[79:64]<640 && desc[95:80]<360 && copy_sx_end<=640 && copy_sy_end<=360;
    end
    // Optional queued path: raw descriptor -> local checks/one-hot opcode ->
    // final execution decision -> EXECUTE. No timing exceptions are needed.
    reg [7:0] opcode_q;
    reg fence_ok_q,fill_format_q,fill_origin_q,palette_ok_q,present_ok_q;
    reg memory_range_q,memory_read_q,copy_format_q,copy_same_q,audio_format_q;
    reg [15:0] palette_select_q,palette_update_q;
    reg [11:0] palette_data_q;
    reg [3:0] decoded_state;
    reg [7:0] decoded_error;
    reg decoded_done,decoded_audio;
    always @(posedge clk) begin
        if(reset) begin
            opcode_q<=0;fence_ok_q<=0;fill_format_q<=0;fill_origin_q<=0;palette_ok_q<=0;present_ok_q<=0;
            memory_range_q<=0;memory_read_q<=0;copy_format_q<=0;copy_same_q<=0;audio_format_q<=0;
            palette_select_q<=0;palette_update_q<=0;palette_data_q<=0;
            decoded_state<=IDLE;decoded_error<=BAD_COMMAND;decoded_done<=1;decoded_audio<=0;
        end else if(REGISTER_DECODE) begin
            if(state==DECODE) begin
                for(integer op=0;op<8;op=op+1) opcode_q[op]<=opcode==8'(op);
                fence_ok_q<=argument==0 && desc[127:32]==0;
                fill_format_q<=argument<=1 && desc[103:96]<=15 && desc[127:104]==0;
                fill_origin_q<=desc[47:32]<640 && desc[63:48]<360;
                palette_ok_q<=argument<=15 && desc[47:44]==0 && desc[127:48]==0;
                present_ok_q<=argument<=1 && desc[127:32]==0;
                memory_range_q<=argument!=0 && argument<=16 && byte_addr[31:22]==0 && byte_addr[1:0]==0 && !beyond_die;
                memory_read_q<=desc[127:64]==0;
                copy_format_q<=argument<=3 && !desc[32] && !desc[64] && !desc[96] && desc[34:32]==desc[66:64];
                copy_same_q<=argument[0]==argument[1] && desc[47:32]==desc[79:64] && desc[63:48]==desc[95:80];
                audio_format_q<=argument==0 && desc[127:32]==0;
                palette_select_q<=16'b1 << argument[3:0];
                palette_data_q<=desc[43:32];
            end
            if(state==VALIDATE) begin
                decoded_state<=IDLE;decoded_done<=1;decoded_error<=BAD_COMMAND;decoded_audio<=0;
                palette_update_q<=0;
                // opcode_q is one-hot (or zero for an unknown full-width opcode).
                unique case(1'b1)
                    opcode_q[0]: decoded_error<=fence_ok_q ? 8'd0 : BAD_COMMAND;
                    opcode_q[1]: begin
                        if(!fill_format_q) decoded_error<=BAD_COMMAND;
                        else if(!fill_origin_q || fill_end_x>640 || fill_end_y>360) decoded_error<=RANGE_ERROR;
                        else begin
                            decoded_error<=0;
                            if(!engine_empty) begin decoded_done<=0;decoded_state<=FILL_START;end
                        end
                    end
                    opcode_q[2]: begin
                        decoded_error<=palette_ok_q ? 8'd0 : BAD_COMMAND;
                        if(palette_ok_q) palette_update_q<=palette_select_q;
                    end
                    opcode_q[3]: if(present_ok_q) begin decoded_done<=0;decoded_error<=0;decoded_state<=PRESENT_REQ;end
                    opcode_q[4],opcode_q[5]: begin
                        if(!memory_range_q) decoded_error<=RANGE_ERROR;
                        else if(opcode_q[5] && !memory_read_q) decoded_error<=BAD_COMMAND;
                        else begin decoded_done<=0;decoded_error<=0;decoded_state<=MEM_REQ;end
                    end
                    opcode_q[6]: begin
                        if(!copy_format_q) decoded_error<=BAD_COMMAND;
                        else if(!copy_range_ok || fill_end_x>640 || fill_end_y>360) decoded_error<=RANGE_ERROR;
                        else begin
                            decoded_error<=0;
                            if(!copy_same_q && !engine_empty) begin decoded_done<=0;decoded_state<=FILL_START;end
                        end
                    end
                    opcode_q[7]: if(AUDIO_CSR && audio_format_q) begin
                        decoded_audio<=1;decoded_done<=0;decoded_error<=0;decoded_state<=EXECUTE;
                    end
                    default: ;
                endcase
            end
        end
    end
    wire audio_descriptor_ok=REGISTER_DECODE ? audio_format_q : argument==0 && desc[127:32]==0;
    wire audio_opcode=REGISTER_DECODE ? opcode_q[7] : opcode==7;
    assign audio_capture=!reset && AUDIO_CSR && state==EXECUTE && audio_opcode &&
        audio_descriptor_ok && !audio_settle && !audio_busy && audio_settings_valid;
    assign audio_apply=!reset && AUDIO_CSR && state==AUDIO_SEND;
    assign audio_commit_done=!reset && AUDIO_CSR && state==AUDIO_WAIT && (audio_done || audio_apply_error);
    assign ready=!reset && state==IDLE;
    assign present_valid=!reset && state==PRESENT_REQ;
    assign present_page=argument[0];
    wire fill_ready,fill_done,fill_error,fill_valid,fill_write;
    wire [19:0] fill_addr;
    wire [4:0] fill_words;
    wire [511:0] fill_wdata;
    wire [63:0] fill_mask;
    wire fill_active=state==FILL_START || state==FILL_WAIT;
    reg use_fill_payload,use_engine;
    always @(posedge clk) begin
        if(reset) begin use_fill_payload<=0; use_engine<=0; end
        else if(REGISTER_DECODE && state==VALIDATE) begin use_fill_payload<=opcode_q[1];use_engine<=opcode_q[1] || opcode_q[6];end
        else if(!REGISTER_DECODE && state==IDLE && valid) begin use_fill_payload<=opcode==1; use_engine<=opcode==1 || opcode==6; end
    end
    assign host_valid=use_engine ? fill_valid : (!reset && state==MEM_REQ);
    assign host_write=use_engine ? fill_write : (REGISTER_DECODE ? opcode_q[4] : opcode==4);
    // SPI overlay (rtl/spi/README.md): MEM_REQ is at least two cycles after
    // the held descriptor is valid, so READ/WRITE address and length come
    // from flops instead of the descriptor RAM output.
    reg [19:0] mem_addr_q;
    reg [4:0] mem_words_q;
    always @(posedge clk) begin mem_addr_q<=byte_addr[21:2]; mem_words_q<=argument[4:0]; end
    assign host_addr=use_engine ? fill_addr : mem_addr_q;
    assign host_words=use_engine ? fill_words : mem_words_q;
    // Queued mode: each 64-bit payload lane has its own control flop. Preserve
    // the replicas so synthesis cannot recreate a single 512-load select net.
    // Only the selection is held; COPY must see the live upload window after
    // every read capture, rather than a command-time snapshot of its contents.
    generate if(REGISTER_DECODE) begin: payload_lanes
        for(genvar lane=0;lane<8;lane=lane+1) begin: word_lane
            (* syn_preserve=1, syn_keep=1 *) reg select_fill;
            always @(posedge clk)
                if(reset) select_fill<=0;
                else if(state==VALIDATE) select_fill<=opcode_q[1];
            assign host_wdata[lane*64+:64]=select_fill ? fill_wdata[lane*64+:64] : upload_data[lane*64+:64];
        end
    end else begin: legacy_payload
        assign host_wdata=use_fill_payload ? fill_wdata : upload_data;
    end endgenerate
    assign host_mask=use_engine ? fill_mask : desc[127:64];
    kagura_fb_fill_burst #(.VALIDATED_INPUT(1),.ENABLE_COPY(1),.NONEMPTY_INPUT(1)) fill(
        .clk,.reset,.valid(state==FILL_START),.page(copy_command ? argument[1] : argument[0]),
        .copy(copy_command),.src_page(argument[0]),.src_x(desc[47:32]),.src_y(desc[63:48]),.capture_window(copy_capture),
        .x(engine_x),.y(engine_y_q),.width(engine_width),.height(engine_height),.color(desc[99:96]),
        .ready(fill_ready),.done(fill_done),.error(fill_error),
        .req_valid(fill_valid),.req_ready(host_ready && fill_active),.req_write(fill_write),
        .req_addr(fill_addr),.req_words(fill_words),.req_wdata(fill_wdata),.req_mask(fill_mask),
        .rsp_done(host_done && fill_active),.rsp_error(host_error),.rsp_data(host_rdata));
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE; done<=0; error<=0;
            present_palette<=192'hfff_eee_ddd_ccc_bbb_aaa_999_888_777_666_555_444_333_222_111_000;
        end else begin
            done<=0; error<=0;
            case(state)
                IDLE: if(valid) state<=DECODE;
                DECODE: state<=REGISTER_DECODE ? VALIDATE : EXECUTE;
                VALIDATE: state<=EXECUTE;
                EXECUTE: if(REGISTER_DECODE) begin
                    done<=decoded_done;error<=decoded_error;state<=decoded_state;
                    for(integer pal=0;pal<16;pal=pal+1)
                        if(palette_update_q[pal]) present_palette[pal*12+:12]<=palette_data_q;
                    if(decoded_audio) begin
                        if(audio_busy) begin done<=1;error<=1;state<=IDLE;end
                        else if(audio_settle) state<=EXECUTE;
                        else if(!audio_settings_valid) begin done<=1;error<=RANGE_ERROR;state<=IDLE;end
                        else state<=AUDIO_SNAPSHOT;
                    end
                end else case(opcode)
                    0: begin
                        done<=1; state<=IDLE;
                        if(argument!=0 || desc[127:32]!=0) error<=BAD_COMMAND;
                    end
                    1: begin
                        if(argument>1 || desc[103:96]>15 || desc[127:104]!=0) begin
                            done<=1; error<=BAD_COMMAND; state<=IDLE;
                        end else if(desc[47:32]>=640 || desc[63:48]>=360 || fill_end_x>640 || fill_end_y>360) begin
                            done<=1; error<=RANGE_ERROR; state<=IDLE;
                        end else if(engine_empty) begin done<=1;state<=IDLE;end
                        else state<=FILL_START;
                    end
                    2: begin
                        done<=1; state<=IDLE;
                        if(!palette_command_ok) error<=BAD_COMMAND;
                        else present_palette[argument[3:0]*12+:12]<=desc[43:32];
                    end
                    3: begin
                        if(argument>1 || desc[127:32]!=0) begin done<=1; error<=BAD_COMMAND; state<=IDLE; end
                        else state<=PRESENT_REQ;
                    end
                    4,5: begin
                        if(argument==0 || argument>16 || byte_addr[31:22]!=0 || byte_addr[1:0]!=0 || beyond_die) begin
                            done<=1; error<=RANGE_ERROR; state<=IDLE;
                        end else if(opcode==5 && desc[127:64]!=0) begin
                            done<=1; error<=BAD_COMMAND; state<=IDLE;
                        end else state<=MEM_REQ;
                    end
                    6: begin
                        if(argument>3 || desc[32] || desc[64] || desc[96] || desc[34:32]!=desc[66:64]) begin
                            done<=1; error<=BAD_COMMAND; state<=IDLE;
                        end else if(!copy_range_ok || fill_end_x>640 || fill_end_y>360) begin
                            done<=1; error<=RANGE_ERROR; state<=IDLE;
                        end else if(argument[0]==argument[1] && desc[47:32]==desc[79:64] && desc[63:48]==desc[95:80]) begin
                            done<=1; state<=IDLE;
                        end else if(engine_empty) begin done<=1;state<=IDLE;end
                        else state<=FILL_START;
                    end
                    7: begin
                        if(!AUDIO_CSR || !audio_descriptor_ok) begin done<=1;error<=BAD_COMMAND;state<=IDLE;end
                        else if(audio_busy) begin done<=1;error<=1;state<=IDLE;end
                        else if(audio_settle) state<=EXECUTE;
                        else if(!audio_settings_valid) begin done<=1;error<=RANGE_ERROR;state<=IDLE;end
                        else state<=AUDIO_SNAPSHOT;
                    end
                    default: begin done<=1; error<=BAD_COMMAND; state<=IDLE; end
                endcase
                AUDIO_SNAPSHOT: state<=AUDIO_SEND;
                AUDIO_SEND: if(audio_ready) state<=AUDIO_WAIT;
                AUDIO_WAIT: if(audio_done || audio_apply_error) begin
                    done<=1;error<=audio_apply_error ? MEMORY_ERROR : 8'd0;state<=IDLE;
                end
                FILL_START: if(fill_ready) state<=FILL_WAIT;
                FILL_WAIT: if(fill_done) begin
                    done<=1; error<=fill_error ? MEMORY_ERROR : 8'd0; state<=IDLE;
                end
                MEM_REQ: if(host_ready) state<=MEM_WAIT;
                MEM_WAIT: if(host_done) begin
                    done<=1; error<=host_error ? MEMORY_ERROR : 8'd0; state<=IDLE;
                end
                PRESENT_REQ: if(present_ready) state<=PRESENT_WAIT;
                PRESENT_WAIT: if(present_done) begin done<=1; state<=IDLE; end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
