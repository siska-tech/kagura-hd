// SPDX-License-Identifier: Apache-2.0
// External-clock Kagura-FB integration core. 54 MHz system/PSRAM clock,
// 74.25 MHz pixel clock, 371.25 MHz serializer clock. One PSRAM die, 4 MiB.
// Host/GPU transactions complete at host_done. Wait for previous writes to
// complete before presenting a page, and never mutate the displayed page.
// Audio configuration and PCM ranges must remain stable through apply_done
// and PREPARE completion respectively. Wave data is a synchronous one-cycle
// read response. Addresses here are die-relative bytes/words, not the old ABI.
module kagura_fb_core #(
    parameter integer INIT_CYCLES=4096,
    parameter bit AUDIO_REGISTER_TICK=1,
    parameter bit PCM_ONLY=0,
    parameter bit CURSOR_PIPELINE_MAILBOX=0,
    parameter bit AUDIO_REGISTER_CREDITS=0,
    parameter bit PACKET_REPLICATE_FIRST=0
) (
    input wire clk_system,clk_pixel,clk_pixel_x5,reset,
    input wire host_valid,host_write,
    input wire [19:0] host_addr,
    input wire [4:0] host_words,
    input wire [511:0] host_wdata,
    input wire [63:0] host_mask,
    output wire host_ready,host_done,host_error,
    output wire [511:0] host_rdata,
    input wire present_valid,present_page,
    input wire [191:0] present_palette,
    output wire present_ready,present_done,
    input wire cursor_req_valid,cursor_req_write,
    input wire [4:0] cursor_req_addr,
    input wire [7:0] cursor_req_wdata,
    output wire cursor_req_ready,cursor_rsp_valid,cursor_rsp_error,cursor_irq,
    output wire [7:0] cursor_rsp_data,
    input wire audio_apply,
    output wire audio_ready,audio_done,audio_error,
    input wire [143:0] cfg_step,
    input wire [23:0] cfg_duty,
    input wire [47:0] cfg_gain_l,cfg_gain_r,
    input wire [5:0] cfg_enable,cfg_phase_reset,
    input wire [7:0] cfg_wave_len,cfg_master,
    input wire [15:0] cfg_noise_period,cfg_pcm_gain_l,cfg_pcm_gain_r,
    input wire [1:0] cfg_pcm_enable,pcm_prepare,pcm_stop,pcm_clear,
    input wire [43:0] pcm_start,pcm_end,pcm_loop,
    input wire [1:0] pcm_loop_enable,
    output wire [7:0] pcm_status0,pcm_status1,
    output wire wave_read,
    output wire [8:0] wave_addr,
    input wire signed [7:0] wave_data,
    output wire [2:0] tmds,
    output wire tmds_clock,
    output wire initialized,video_underrun,memory_error,audio_overflow,audio_underflow,audio_muted,
    output wire [10:0] cx,
    output wire [9:0] cy,
    output wire [23:0] rgb,
    output wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,
    output wire [7:0] phy_dq_o_rise,phy_dq_o_fall,
    output wire phy_rwds_oe,phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx,
    input wire [7:0] phy_dq_i_rise,phy_dq_i_fall
);
    (* ASYNC_REG="TRUE" *) reg [2:0] sys_release,pix_release;
    always @(posedge clk_system or posedge reset)
        if(reset) sys_release<=0; else sys_release<={sys_release[1:0],1'b1};
    always @(posedge clk_pixel or posedge reset)
        if(reset) pix_release<=0; else pix_release<={pix_release[1:0],1'b1};
    wire system_reset=!sys_release[2];
    wire pixel_reset=!pix_release[2];
    wire [2:0] req_valid,req_ready,rsp_done,rsp_error;
    wire [2:0] req_write={host_write,2'b00};
    wire [2:0][19:0] req_addr;
    wire [2:0][4:0] req_words={host_words,5'd1,5'd16};
    // Scanout/PCM never write. Broadcast unused write fields so arbitration
    // does not insert a redundant 512-bit data mux in the host write path.
    wire [2:0][511:0] req_wdata={3{host_wdata}};
    wire [2:0][63:0] req_mask={3{host_mask}};
    wire [511:0] rsp_data;
    wire scan_word_valid,rword_valid;
    wire [31:0] scan_word_data,rword_data;
    assign req_valid[2]=host_valid;
    assign req_addr[2]=host_addr;
    assign host_ready=req_ready[2];
    assign host_done=rsp_done[2];
    assign host_error=rsp_error[2];
    assign host_rdata=rsp_data;
    kagura_fb_scanout display(
        .sys_clk(clk_system),.sys_reset(system_reset),.pix_clk(clk_pixel),.pix_reset(pixel_reset),.cx,.cy,
        .present_valid,.present_page,.present_palette,.present_ready,.present_done,
        .req_valid(req_valid[0]),.req_ready(req_ready[0]),.req_addr(req_addr[0]),
        .rsp_done(rsp_done[0]),.rsp_error(rsp_error[0]),.scan_word_valid,.scan_word_data,.rgb,
        .underrun(video_underrun),.memory_error,.generation_out());
    wire pf_req,pf_req_ready,pf_rsp,pf_rsp_error;
    wire [21:0] pf_addr;
    wire [7:0] pf_data;
    wire cache_flush;
    reg host_transaction_write;
    always @(posedge clk_system) begin
        if(system_reset) host_transaction_write<=0;
        else if(host_valid && host_ready) host_transaction_write<=host_write;
    end
    wire host_write_completed=host_done && host_transaction_write && !host_error;
    kagura_fb_pcm_port pcm_port(
        .clk(clk_system),.reset(system_reset),.initialized,
        .flush(cache_flush || host_write_completed),
        .mem_req_valid(pf_req),.mem_req_ready(pf_req_ready),.mem_req_addr(pf_addr),
        .mem_rsp_valid(pf_rsp),.mem_rsp_error(pf_rsp_error),.mem_rsp_data(pf_data),
        .req_valid(req_valid[1]),.req_ready(req_ready[1]),.req_addr(req_addr[1]),
        .rsp_done(rsp_done[1]),.rsp_error(rsp_error[1]),.rsp_data(rsp_data[31:0]));
    wire [1:0] cfg_valid,cfg_ready,start_play,stop_play,pf_ready,pf_active;
    wire [1:0] pf_done,pf_underrun,pf_config_error,pf_memory_error;
    wire signed [7:0] pcm0,pcm1;
    wire apply_boundary,sample_boundary;
    kagura_pcm_prefetch #(.ADDR_WIDTH(22),.BUFFER_ADDR_BITS(5),.MEMORY_BYTES(23'h400000),.RESPONSE_TIMEOUT(4096)) prefetch(
        .clk(clk_system),.reset(system_reset),.sample_tick(sample_boundary),.cfg_valid,.cfg_ready,
        .cfg_start(pcm_start),.cfg_end(pcm_end),.cfg_loop(pcm_loop),.cfg_loop_enable(pcm_loop_enable),
        .start_play,.stop_play,.ready(pf_ready),.active(pf_active),.done(pf_done),
        .underrun(pf_underrun),.config_error(pf_config_error),.memory_error(pf_memory_error),
        .sample0(pcm0),.sample1(pcm1),.mem_req_valid(pf_req),.mem_req_ready(pf_req_ready),
        .mem_req_addr(pf_addr),.mem_rsp_valid(pf_rsp),.mem_rsp_data(pf_data),.mem_rsp_error(pf_rsp_error));
    kagura_pcm_control pcm_control(
        .clk(clk_system),.reset(system_reset),.prepare(pcm_prepare),.stop(pcm_stop),.clear(pcm_clear),
        .apply_boundary,.commit_enable(cfg_pcm_enable),.cfg_valid,.cfg_ready,.start_play,.stop_play,.cache_flush,
        .pf_ready,.pf_active,.pf_done,.pf_underrun,.pf_config_error,.pf_memory_error,
        .status0(pcm_status0),.status1(pcm_status1));
    wire sample_valid,audio_apply_ready;
    assign audio_ready=!system_reset && audio_apply_ready;
    wire signed [15:0] sample_left,sample_right;
    kagura_audio_synth #(.EXTERNAL_SNAPSHOT(1),.PCM_ENABLE(1),.PCM_ONLY(PCM_ONLY)) synth(
        .clk(clk_system),.reset(system_reset),.apply_valid(audio_apply),.apply_ready(audio_apply_ready),
        .cfg_step,.cfg_duty,.cfg_gain_l,.cfg_gain_r,.cfg_enable,.cfg_phase_reset,.cfg_wave_len,.cfg_master,.cfg_noise_period,
        .apply_done(audio_done),.apply_error(audio_error),.apply_busy(),.wave_read,.wave_addr,.wave_data,
        .sample_valid,.sample_left,.sample_right,.last_cycles(),.apply_boundary,.sample_boundary,
        .pcm_sample0(pcm0),.pcm_sample1(pcm1),.cfg_pcm_gain_l,.cfg_pcm_gain_r,.cfg_pcm_enable);
    // The inherited protocol registers video_data_period one cycle before
    // mode. Delay RGB to keep first/last encoded pixels aligned with that DE.
    wire [23:0] hdmi_rgb;
    kagura_fb_cursor #(.PIPELINE_MAILBOX(CURSOR_PIPELINE_MAILBOX)) cursor(
        .sys_clk(clk_system),.sys_reset(system_reset),.pix_clk(clk_pixel),.pix_reset(pixel_reset),
        .req_valid(cursor_req_valid),.req_write(cursor_req_write),.req_addr(cursor_req_addr),.req_wdata(cursor_req_wdata),
        .req_ready(cursor_req_ready),.rsp_valid(cursor_rsp_valid),.rsp_error(cursor_rsp_error),.rsp_data(cursor_rsp_data),.irq(cursor_irq),
        .cx,.cy,.background(rgb),.rgb_out(hdmi_rgb));
    kagura_hdmi_stream_eval #(.EXTERNAL_RGB(1),.VIDEO_ID_CODE(4),.AUDIO_REGISTER_TICK(AUDIO_REGISTER_TICK),.AUDIO_REGISTER_CREDITS(AUDIO_REGISTER_CREDITS),.PACKET_REPLICATE_FIRST(PACKET_REPLICATE_FIRST)) hdmi(
        .clk_system,.clk_pixel,.clk_pixel_x5,.reset(pixel_reset),.sample_valid,.sample_data({sample_right,sample_left}),
        .full(),.overflow(audio_overflow),.underflow(audio_underflow),.tmds,.tmds_clock,.muted(audio_muted),
        .rgb_in(hdmi_rgb),.cx_out(cx),.cy_out(cy),.underflow_toggle());
    wire ctrl_valid,ctrl_ready,ctrl_write,ctrl_done,ctrl_error;
    wire [19:0] ctrl_addr;
    wire [4:0] ctrl_words;
    wire [511:0] ctrl_wdata,ctrl_rdata;
    wire [63:0] ctrl_mask;
    kagura_fb_arbiter scheduler(
        .clk(clk_system),.reset(system_reset),.req_valid,.req_ready,.req_write,.req_addr,.req_words,.req_wdata,.req_mask,
        .rsp_done,.rsp_error,.rsp_data,.valid(ctrl_valid),.ready(ctrl_ready),.write(ctrl_write),.addr(ctrl_addr),
        .words(ctrl_words),.wdata(ctrl_wdata),.mask(ctrl_mask),.done(ctrl_done),.error(ctrl_error),.rdata(ctrl_rdata),
        .rword_valid,.rword_data,.scan_word_valid,.scan_word_data);
    kagura_fb_burst_ctrl #(.INIT_CYCLES(INIT_CYCLES)) memory_ctrl(
        .clk(clk_system),.reset(system_reset),.valid(ctrl_valid),.ready(ctrl_ready),.write(ctrl_write),.addr(ctrl_addr),
        .words(ctrl_words),.wdata(ctrl_wdata),.mask(ctrl_mask),.done(ctrl_done),.error(ctrl_error),.rdata(ctrl_rdata),
        .rword_valid,.rword_data,
        .initialized,.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,.phy_dq_o_rise,.phy_dq_o_fall,
        .phy_rwds_oe,.phy_rwds_o_rise,.phy_rwds_o_fall,.phy_dq_tx,.phy_rwds_tx,.phy_dq_i_rise,.phy_dq_i_fall);
endmodule
