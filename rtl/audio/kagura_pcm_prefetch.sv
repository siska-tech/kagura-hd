// SPDX-License-Identifier: Apache-2.0
// Two-channel signed-8-bit PCM reader with a private prefetch buffer.
//
// The memory interface permits one outstanding read. A board-specific PSRAM
// wrapper supplies the variable-latency response. Configuration is accepted
// only while that channel is stopped and no read is outstanding; software
// waits for ready before asserting start so playback never depends on the
// first PSRAM access latency. Optional response timeout invalidates the owner
// but drains the late response before accepting a fresh configuration.
module kagura_pcm_prefetch #(
    parameter integer ADDR_WIDTH=24,
    parameter integer BUFFER_ADDR_BITS=8,
    parameter [ADDR_WIDTH:0] MEMORY_BYTES={1'b1,{ADDR_WIDTH{1'b0}}},
    parameter integer RESPONSE_TIMEOUT=0,
    parameter bit STREAM=0
) (
    input  wire clk,
    input  wire reset,
    input  wire sample_tick,
    input  wire stream_control_write,stream_publish,
    input  wire [7:0] stream_data,
    input  wire [1:0] explicit_stop,
    output wire [7:0] stream_token,stream_status,
    output wire stream_cancel_control,

    input  wire [1:0] cfg_valid,
    output wire [1:0] cfg_ready,
    input  wire [2*ADDR_WIDTH-1:0] cfg_start,
    input  wire [2*ADDR_WIDTH-1:0] cfg_end,
    input  wire [2*ADDR_WIDTH-1:0] cfg_loop,
    input  wire [1:0] cfg_loop_enable,
    input  wire [1:0] start_play,
    input  wire [1:0] stop_play,

    output wire [1:0] ready,
    output reg  [1:0] active,
    output reg  [1:0] done,
    output reg  [1:0] underrun,
    output reg  [1:0] config_error,
    output reg  [1:0] memory_error,
    output reg  signed [7:0] sample0,
    output reg  signed [7:0] sample1,

    output reg  mem_req_valid,
    input  wire mem_req_ready,
    output reg  [ADDR_WIDTH-1:0] mem_req_addr,
    input  wire mem_rsp_valid,
    input  wire [7:0] mem_rsp_data,
    input  wire mem_rsp_error
);
    localparam integer BUFFER_DEPTH=1<<BUFFER_ADDR_BITS;
    localparam integer COUNT_WIDTH=BUFFER_ADDR_BITS+1;
    localparam integer TIMEOUT_WIDTH=RESPONSE_TIMEOUT>0 ? $clog2(RESPONSE_TIMEOUT+1) : 1;
    localparam [COUNT_WIDTH-1:0] BUFFER_DEPTH_COUNT=COUNT_WIDTH'(BUFFER_DEPTH);

    reg [7:0] buffer0 [0:BUFFER_DEPTH-1];
    reg [7:0] buffer1 [0:BUFFER_DEPTH-1];
    reg [BUFFER_ADDR_BITS-1:0] rd_ptr [0:1];
    reg [BUFFER_ADDR_BITS-1:0] wr_ptr [0:1];
    reg [COUNT_WIDTH-1:0] count [0:1];
    reg [ADDR_WIDTH-1:0] end_addr [0:1];   // last byte (END-1)
    reg [ADDR_WIDTH-1:0] loop_addr [0:1];
    reg [ADDR_WIDTH-1:0] fetch_addr [0:1];
    // Next fetch address and END flag, registered from fetch_addr. A channel
    // issues at most one request per response, so after each address change
    // (configure or issue) the copy is one cycle stale and next_ok blocks it.
    reg [ADDR_WIDTH-1:0] fetch_next [0:1];
    reg [1:0] fetch_last,next_ok;
    reg [1:0] loop_enable;
    reg [1:0] configured;
    reg [1:0] fetch_done;
    reg outstanding;
    reg outstanding_ch;
    reg discard_response;
    reg [TIMEOUT_WIDTH-1:0] timeout_count;
    reg rr;
    reg selected_valid;
    reg selected_ch;

    // Bit 12 identifies the half of an 8 KiB aligned stereo plane.
    reg stream_armed,stream_half;
    reg [6:0] stream_generation;
    reg [1:0] owed_a,owed_b;
    reg outstanding_half,outstanding_last;
    reg [1:0] stream_gate;
    wire streaming=STREAM && stream_armed;
    wire stream_arm=STREAM && stream_control_write && stream_data==1 &&
                    !stream_armed && active==0;
    wire stream_abort=streaming && ((stream_control_write && stream_data==0) ||
                      (|explicit_stop) || (|underrun) ||
                      (|config_error) || (|memory_error));
    wire stream_clear=stream_arm || stream_abort;
    wire half_free=stream_half ? owed_b==0 : owed_a==0;
    assign stream_token={stream_generation,stream_half};
    assign stream_status={5'b0,outstanding,streaming,streaming && half_free};
    assign stream_cancel_control=stream_clear;
    wire publish=streaming && stream_publish && half_free &&
                 stream_data==stream_token;

    if(STREAM) begin : g_stream
        always @(posedge clk) begin
            // next_ok already masks the one cycle after configure or issue.
            for(int c=0;c<2;c=c+1)
                stream_gate[c]<=fetch_addr[c][12] ? owed_b[c] : owed_a[c];
            if(reset) begin
                stream_armed<=0; stream_half<=0; stream_generation<=0;
                owed_a<=0; owed_b<=0;
                outstanding_half<=0; outstanding_last<=0;
            end else if(stream_clear) begin
                stream_armed<=stream_arm;
                stream_half<=0;
                stream_generation<=stream_generation+1'b1;
                // Both halves must be filled and fenced before arming.
                owed_a<=2'b11; owed_b<=2'b11;
            end else if(streaming) begin
                if(mem_req_valid && mem_req_ready) begin
                    outstanding_half<=fetch_addr[selected_ch][12];
                    outstanding_last<=(&fetch_addr[selected_ch][11:0]);
                end
                if(mem_rsp_valid && outstanding && !discard_response &&
                   !mem_rsp_error && outstanding_last) begin
                    if(outstanding_half) owed_b[outstanding_ch]<=0;
                    else owed_a[outstanding_ch]<=0;
                end
                if(publish) begin
                    if(stream_half) begin
                        owed_b<=2'b11;
                        stream_generation<=stream_generation+1'b1;
                    end else owed_a<=2'b11;
                    stream_half<=~stream_half;
                end
            end
        end
    end else begin : g_no_stream
        assign stream_armed=0;
        assign stream_half=0;
        assign stream_generation=0;
        assign owed_a=0;
        assign owed_b=0;
        assign outstanding_half=0;
        assign outstanding_last=0;
        assign stream_gate=0;
    end

    wire [1:0] playback_stop=stop_play | {2{streaming && (|stop_play)}};
    wire stereo_starved=streaming && sample_tick && (&active) &&
                         !(|playback_stop) && (count[0]==0 || count[1]==0);
    // A channel stopped on a sample tick does not consume that sample, so a
    // pause on the AUDIO_COMMIT boundary resumes without a gap.
    wire pop0=sample_tick && active[0] && !playback_stop[0] && !stereo_starved;
    wire pop1=sample_tick && active[1] && !playback_stop[1] && !stereo_starved;
    wire push0=mem_rsp_valid && outstanding && !discard_response && !mem_rsp_error && !outstanding_ch && !stream_clear;
    wire push1=mem_rsp_valid && outstanding && !discard_response && !mem_rsp_error && outstanding_ch && !stream_clear;
    // A request is issued only with no read outstanding, so the space a channel
    // needs is simply count < depth: the MSB of count (count <= depth).
    wire need0=(!streaming || (stream_gate[0] && (&configured))) && configured[0] && next_ok[0] && !fetch_done[0] && !count[0][COUNT_WIDTH-1];
    wire need1=(!streaming || (stream_gate[1] && (&configured))) && configured[1] && next_ok[1] && !fetch_done[1] && !count[1][COUNT_WIDTH-1];

    assign cfg_ready={2{!outstanding}} & ~active;
    assign ready[0]=configured[0] && (count[0]==BUFFER_DEPTH_COUNT || fetch_done[0]);
    assign ready[1]=configured[1] && (count[1]==BUFFER_DEPTH_COUNT || fetch_done[1]);

    always @* begin
        selected_valid=0;
        selected_ch=0;
        if(need0 && need1) begin selected_valid=1; selected_ch=rr; end
        else if(need0) begin selected_valid=1; selected_ch=0; end
        else if(need1) begin selected_valid=1; selected_ch=1; end
        mem_req_valid=!outstanding && selected_valid && !stream_clear;
        mem_req_addr=selected_ch ? fetch_addr[1] : fetch_addr[0];
    end

    always @(posedge clk) begin
        for(int c=0;c<2;c=c+1) begin
            fetch_last[c]<=fetch_addr[c]==end_addr[c];
            fetch_next[c]<=fetch_addr[c]==end_addr[c] ? loop_addr[c] : fetch_addr[c]+1'b1;
        end
        next_ok[0]<=!reset && !(cfg_valid[0] && cfg_ready[0]) && !(mem_req_valid && mem_req_ready && !selected_ch);
        next_ok[1]<=!reset && !(cfg_valid[1] && cfg_ready[1]) && !(mem_req_valid && mem_req_ready && selected_ch);
    end

    // Range check of the configuration inputs, registered every cycle: the
    // caller holds them for at least two cycles before cfg_valid (the public
    // registers settle for three), so the comparators stay out of the accept path.
    reg [1:0] cfg_bad;
    reg [1:0] stream_range_bad;
    if(STREAM) begin : g_range
        for(genvar c=0;c<2;c=c+1) begin : g_channel
            wire [21:0] start_byte=cfg_start[c*ADDR_WIDTH +: ADDR_WIDTH];
            wire [21:0] end_byte=cfg_end[c*ADDR_WIDTH +: ADDR_WIDTH];
            wire [21:0] loop_byte=cfg_loop[c*ADDR_WIDTH +: ADDR_WIDTH];
            always @(posedge clk)
                stream_range_bad[c]<= !cfg_loop_enable[c] ||
                    (|start_byte[12:0]) || (|end_byte[12:0]) ||
                    end_byte[21:13]!=start_byte[21:13]+9'd1 || loop_byte!=start_byte;
        end
    end else begin : g_no_range
        assign stream_range_bad=0;
    end
    always @(posedge clk)
        for(int c=0;c<2;c=c+1)
            cfg_bad[c]<=cfg_start[c*ADDR_WIDTH +: ADDR_WIDTH]>=cfg_end[c*ADDR_WIDTH +: ADDR_WIDTH] ||
                {1'b0,cfg_end[c*ADDR_WIDTH +: ADDR_WIDTH]}>MEMORY_BYTES ||
                (cfg_loop_enable[c] &&
                 (cfg_loop[c*ADDR_WIDTH +: ADDR_WIDTH]<cfg_start[c*ADDR_WIDTH +: ADDR_WIDTH] ||
                  cfg_loop[c*ADDR_WIDTH +: ADDR_WIDTH]>=cfg_end[c*ADDR_WIDTH +: ADDR_WIDTH]));

    integer i;
    always @(posedge clk) begin
        if(reset) begin
            active<=0; done<=0; underrun<=0; config_error<=0; memory_error<=0;
            sample0<=0; sample1<=0; loop_enable<=0; configured<=0; fetch_done<=0;
            outstanding<=0; outstanding_ch<=0; discard_response<=0; timeout_count<=0; rr<=0;
            for(i=0;i<2;i=i+1) begin
                rd_ptr[i]<=0; wr_ptr[i]<=0; count[i]<=0;
                end_addr[i]<=0; loop_addr[i]<=0; fetch_addr[i]<=0;
            end
        end else begin
            done<=0; underrun<=0; config_error<=0; memory_error<=0;

            for(i=0;i<2;i=i+1) begin
                if(cfg_valid[i] && cfg_ready[i]) begin
                    rd_ptr[i]<=0; wr_ptr[i]<=0; count[i]<=0; fetch_done[i]<=0;
                    if(cfg_bad[i] || (streaming && (stream_range_bad[i] || configured[i]))) begin
                        configured[i]<=0;
                        config_error[i]<=1;
                    end else begin
                        end_addr[i]<=cfg_end[i*ADDR_WIDTH +: ADDR_WIDTH]-1'b1;
                        loop_addr[i]<=cfg_loop[i*ADDR_WIDTH +: ADDR_WIDTH];
                        fetch_addr[i]<=cfg_start[i*ADDR_WIDTH +: ADDR_WIDTH];
                        loop_enable[i]<=cfg_loop_enable[i];
                        configured[i]<=1;
                    end
                end else if(cfg_valid[i] && !cfg_ready[i]) config_error[i]<=1;

                if(playback_stop[i]) begin
                    active[i]<=0;
                    if(i==0) sample0<=0; else sample1<=0;
                end
                if(start_play[i]) begin
                    if(ready[i] && !active[i] && (!streaming || (&start_play))) active[i]<=1;
                    else config_error[i]<=1;
                end
            end

            if(mem_req_valid && mem_req_ready) begin
                outstanding<=1;
                outstanding_ch<=selected_ch;
                discard_response<=0;
                timeout_count<=0;
                rr<=~selected_ch;
                if(fetch_last[selected_ch]) begin
                    if(loop_enable[selected_ch]) fetch_addr[selected_ch]<=fetch_next[selected_ch];
                    else fetch_done[selected_ch]<=1;
                end else fetch_addr[selected_ch]<=fetch_next[selected_ch];
            end

            if(mem_rsp_valid && outstanding) begin
                outstanding<=0;
                timeout_count<=0;
                if(discard_response) begin
                    discard_response<=0;
                end else if(mem_rsp_error) begin
                    memory_error[outstanding_ch]<=1;
                    fetch_done[outstanding_ch]<=1;
                    configured[outstanding_ch]<=0;
                    active[outstanding_ch]<=0;
                    if(outstanding_ch) sample1<=0; else sample0<=0;
                end else if(outstanding_ch) begin
                    buffer1[wr_ptr[1]]<=mem_rsp_data;
                    wr_ptr[1]<=wr_ptr[1]+1'b1;
                end else begin
                    buffer0[wr_ptr[0]]<=mem_rsp_data;
                    wr_ptr[0]<=wr_ptr[0]+1'b1;
                end
            end else if(outstanding && RESPONSE_TIMEOUT>0 && !discard_response) begin
                if(timeout_count==TIMEOUT_WIDTH'(RESPONSE_TIMEOUT-1)) begin
                    discard_response<=1;
                    memory_error[outstanding_ch]<=1;
                    fetch_done[outstanding_ch]<=1;
                    configured[outstanding_ch]<=0;
                    active[outstanding_ch]<=0;
                    if(outstanding_ch) sample1<=0; else sample0<=0;
                end else timeout_count<=timeout_count+1'b1;
            end

            if(pop0) begin
                if(count[0]!=0) begin sample0<=$signed(buffer0[rd_ptr[0]]); rd_ptr[0]<=rd_ptr[0]+1'b1; end
                else begin sample0<=0; active[0]<=0; underrun[0]<=1; end
            end else if(sample_tick && !active[0]) sample0<=0;
            if(pop1) begin
                if(count[1]!=0) begin sample1<=$signed(buffer1[rd_ptr[1]]); rd_ptr[1]<=rd_ptr[1]+1'b1; end
                else begin sample1<=0; active[1]<=0; underrun[1]<=1; end
            end else if(sample_tick && !active[1]) sample1<=0;

            case({push0,pop0 && count[0]!=0})
                2'b10: count[0]<=count[0]+1'b1;
                2'b01: count[0]<=count[0]-1'b1;
                default: ;
            endcase
            case({push1,pop1 && count[1]!=0})
                2'b10: count[1]<=count[1]+1'b1;
                2'b01: count[1]<=count[1]-1'b1;
                default: ;
            endcase

            if(pop0 && count[0]==1 && fetch_done[0] && !push0) begin active[0]<=0; done[0]<=1; end
            if(pop1 && count[1]==1 && fetch_done[1] && !push1) begin active[1]<=0; done[1]<=1; end

            if(stereo_starved) begin
                active<=0;
                underrun<=2'b11;
                sample0<=0; sample1<=0;
            end
            if(stream_clear) begin
                configured<=0;
                active<=0;
                sample0<=0; sample1<=0;
                // Keep the outstanding slot occupied until its late response drains.
                if(outstanding && !mem_rsp_valid) discard_response<=1;
            end
        end
    end

// synthesis translate_off
    always @(posedge clk) begin
        if(!reset && mem_rsp_valid && !outstanding) $fatal(1,"PCM memory response without request");
        if(!reset && count[0]>BUFFER_DEPTH_COUNT) $fatal(1,"PCM channel 0 buffer overflow");
        if(!reset && count[1]>BUFFER_DEPTH_COUNT) $fatal(1,"PCM channel 1 buffer overflow");
    end
// synthesis translate_on
endmodule
