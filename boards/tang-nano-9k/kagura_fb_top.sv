// SPDX-License-Identifier: Apache-2.0
// Kagura-FB host target. Clears both pages to black and initializes two
// silent PCM storage before accepting host commands. ABI1.4 PCM-only audio settings
// are Host-controlled and boot muted. No flash IO.
module kagura_fb_top #(parameter integer HOST_LANES=kagura_fb_config::HOST_LANES) (
    input wire clk27,reset_n,host_sck,host_cs_n,
    inout wire [3:0] host_io,
    output wire host_busy,host_ready,host_irq_n,
    output wire [3:0] sd_hiz,
    output wire tmds_clk_p,tmds_clk_n,
    output wire [2:0] tmds_d_p,tmds_d_n,
    output wire [5:0] led_n,
    output wire [1:0] O_psram_ck,O_psram_ck_n,O_psram_reset_n,O_psram_cs_n,
    inout wire [1:0] IO_psram_rwds,
    inout wire [15:0] IO_psram_dq
);
    wire pixel,serial,system_clk,pixel_lock,system_lock,psram_ck;
    kagura_nano9k_clocks #(.VIDEO_ID_CODE(4),.PSRAM_CK_ENABLE(1)) clocks(
        .clk27,.reset_n,.pixel,.serial,.system_clk,.pixel_lock,.system_lock,.psram_ck);
    wire reset=!(reset_n && pixel_lock && system_lock);
    localparam BOOT=0,SEND=1,WAIT_WRITE=2,PRESENT=3,WAIT_PRESENT=4,PREPARE=5,WAIT_PCM=6,APPLY=7,RUN=8;
    reg [3:0] stage;
    reg [19:0] host_addr;
    reg failed;
    wire mem_ready,host_done,host_error,initialized,present_ready,present_done;
    wire audio_ready,audio_done,audio_error,video_underrun,memory_error,audio_overflow,audio_underflow;
    wire [7:0] pcm_status0,pcm_status1;
    reg host_active;
    wire audio_muted;
    wire audio_req_valid,audio_req_write,audio_req_ready,audio_rsp_valid,audio_rsp_error;
    wire [3:0] audio_req_addr;wire [7:0] audio_req_wdata,audio_rsp_data;
    wire audio_apply,audio_capture,audio_commit_done,audio_settings_valid,audio_busy,audio_settle;
    wire [143:0] cfg_step;wire [23:0] cfg_duty;wire [47:0] cfg_gain_l,cfg_gain_r;
    wire [5:0] cfg_enable,cfg_phase_reset;wire [7:0] cfg_wave_len,cfg_master;
    wire [15:0] cfg_noise_period,cfg_pcm_gain_l,cfg_pcm_gain_r;
    wire [1:0] cfg_pcm_enable,pcm_prepare,pcm_stop,pcm_clear,pcm_loop_enable;
    wire [43:0] pcm_start,pcm_end,pcm_loop;
    kagura_fb_audio_endpoint audio_endpoint(
        .clk(system_clk),.reset,.enabled(host_active && !failed),
        .req_valid(audio_req_valid),.req_write(audio_req_write),.req_addr(audio_req_addr),.req_wdata(audio_req_wdata),
        .req_ready(audio_req_ready),.rsp_valid(audio_rsp_valid),.rsp_error(audio_rsp_error),.rsp_data(audio_rsp_data),
        .audio_capture,.audio_commit_done,.audio_settings_valid,.audio_busy,.audio_settle,.fifo_underflow(audio_underflow),.fifo_overflow(audio_overflow),
        .muted(audio_muted),.pcm_status0,.pcm_status1,.cfg_step,.cfg_duty,.cfg_gain_l,.cfg_gain_r,.cfg_enable,
        .cfg_phase_reset,.cfg_wave_len,.cfg_master,.cfg_noise_period,.cfg_pcm_gain_l,.cfg_pcm_gain_r,.cfg_pcm_enable,
        .pcm_start,.pcm_end,.pcm_loop,.pcm_loop_enable,.pcm_prepare,.pcm_stop,.pcm_clear);
    wire wave_read;
    wire [8:0] wave_addr;
    wire signed [7:0] wave_data=8'sd0;
    always @(posedge system_clk) begin
        if(reset) begin stage<=BOOT; host_addr<=0; failed<=0; end
        else begin
            if(stage!=RUN && (host_error || audio_error)) failed<=1;
            case(stage)
                BOOT: if(initialized) stage<=SEND;
                SEND: if(mem_ready) stage<=WAIT_WRITE;
                WAIT_WRITE: if(host_done) begin
                    if(host_error) begin failed<=1; stage<=RUN; end
                    else if(host_addr==60016) stage<=PRESENT;
                    else begin
                        host_addr<=host_addr==57584 ? 20'd60000 : host_addr+20'd16;
                        stage<=SEND;
                    end
                end
                PRESENT: if(present_ready) stage<=WAIT_PRESENT;
                WAIT_PRESENT: if(present_done) stage<=RUN;
                PREPARE: stage<=WAIT_PCM;
                WAIT_PCM: if(pcm_status0[0] && pcm_status1[0]) stage<=APPLY;
                APPLY: if(audio_ready) begin
                    stage<=RUN;
                end
                default: stage<=RUN;
            endcase
        end
    end
    wire tc;
    wire [2:0] tx;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe,phy_dq_tx,phy_rwds_tx;
    wire phy_rwds_o_rise,phy_rwds_o_fall;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    wire command_valid,command_write,command_present_valid,command_present_page;
    wire [19:0] command_addr;
    wire [4:0] command_words;
    wire [511:0] command_data,host_rdata;
    wire [63:0] command_mask;
    wire [191:0] command_palette;
    wire cursor_req_valid,cursor_req_write,cursor_req_ready,cursor_rsp_valid,cursor_rsp_error,cursor_irq;
    wire [4:0] cursor_req_addr;
    wire [7:0] cursor_req_wdata,cursor_rsp_data;
    always @(posedge system_clk) host_active<=!reset && stage==RUN;
    kagura_fb_host #(.LANES(HOST_LANES),.AUDIO_CSR(1)) host(
        .clk(system_clk),.reset,.enabled(host_active && !failed),
        .video_error(video_underrun || memory_error),
        .audio_error(audio_overflow || audio_underflow || |(pcm_status0&8'h38) || |(pcm_status1&8'h38)),
        .host_sck,.host_cs_n,.host_io,.host_busy,.host_ready,.host_irq_n,
        .host_valid(command_valid),.mem_ready(mem_ready),.host_write(command_write),
        .host_addr(command_addr),.host_words(command_words),.host_wdata(command_data),.host_mask(command_mask),
        .mem_done(host_done),.mem_error(host_error),.mem_rdata(host_rdata),
        .present_valid(command_present_valid),.present_page(command_present_page),.present_palette(command_palette),
        .present_ready(present_ready),.present_done(present_done),
        .cursor_req_valid,.cursor_req_write,.cursor_req_addr,.cursor_req_wdata,.cursor_req_ready,.cursor_rsp_valid,.cursor_rsp_error,.cursor_rsp_data,.cursor_irq,
        .audio_req_valid,.audio_req_write,.audio_req_addr,.audio_req_wdata,.audio_req_ready,.audio_rsp_valid,.audio_rsp_error,.audio_rsp_data,
        .audio_capture,.audio_apply,.audio_commit_done,.audio_settings_valid,.audio_busy,.audio_settle,
        .audio_ready,.audio_done,.audio_apply_error(audio_error));
`ifndef SYNTHESIS
// synthesis translate_off
    always @(posedge system_clk) if(!reset) begin
        if(initialized && !host_active && command_data!==512'd0) $fatal(1,"host payload before boot completion");
    end
// synthesis translate_on
`endif
    assign sd_hiz=4'bzzzz;
    // Equivalent fractional-tick representations give the two transport
    // placements different packing choices, with identical 48 kHz decisions.
    kagura_fb_core #(.AUDIO_REGISTER_TICK(HOST_LANES==4),.PCM_ONLY(1)) core(
        .clk_system(system_clk),.clk_pixel(pixel),.clk_pixel_x5(serial),.reset,
        .host_valid(host_active ? command_valid : stage==SEND),.host_write(host_active ? command_write : 1'b1),
        .host_addr(host_active ? command_addr : host_addr),.host_words(host_active ? command_words : 5'd16),
        // Upload/command payload is locked at zero until host enable. Reuse
        // those zeros for startup clears, avoiding a second 512-bit data path.
        .host_wdata(command_data),.host_mask(host_active ? command_mask : 64'd0),
        .host_ready(mem_ready),.host_done,.host_error,.host_rdata,
        .present_valid(host_active ? command_present_valid : stage==PRESENT),.present_page(host_active && command_present_page),
        .present_palette(host_active ? command_palette : 192'hfff_eee_ddd_ccc_bbb_aaa_999_888_777_666_555_444_333_222_111_000),
        .present_ready,.present_done,
        .cursor_req_valid,.cursor_req_write,.cursor_req_addr,.cursor_req_wdata,.cursor_req_ready,.cursor_rsp_valid,.cursor_rsp_error,.cursor_rsp_data,.cursor_irq,
        .audio_apply,.audio_ready,.audio_done,.audio_error,
        .cfg_step,.cfg_duty,.cfg_gain_l,.cfg_gain_r,.cfg_enable,.cfg_phase_reset,.cfg_wave_len,.cfg_master,
        .cfg_noise_period,.cfg_pcm_gain_l,.cfg_pcm_gain_r,.cfg_pcm_enable,
        .pcm_prepare,.pcm_stop,.pcm_clear,.pcm_start,.pcm_end,.pcm_loop,.pcm_loop_enable,.pcm_status0,.pcm_status1,
        .wave_read,.wave_addr,.wave_data,.tmds(tx),.tmds_clock(tc),.initialized,.video_underrun,
        .memory_error,.audio_overflow,.audio_underflow,.audio_muted,.cx(),.cy(),.rgb(),
        .phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,.phy_dq_o_rise,.phy_dq_o_fall,
        .phy_rwds_oe,.phy_rwds_o_rise,.phy_rwds_o_fall,.phy_dq_tx,.phy_rwds_tx,.phy_dq_i_rise,.phy_dq_i_fall);
    kagura_hyperram_phy_gowin phy(
        .clk(system_clk),.clk_ck(psram_ck),.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe(phy_dq_tx),
        .phy_dq_o_rise,.phy_dq_o_fall,.phy_rwds_oe(phy_rwds_tx),.phy_rwds_o_rise,.phy_rwds_o_fall,
        .phy_dq_i_rise,.phy_dq_i_fall,.phy_rwds_i_rise(),.phy_rwds_i_fall(),
        .O_psram_ck(O_psram_ck[0]),.O_psram_ck_n(O_psram_ck_n[0]),
        .O_psram_reset_n(O_psram_reset_n[0]),.O_psram_cs_n(O_psram_cs_n[0]),
        .IO_psram_rwds(IO_psram_rwds[0]),.IO_psram_dq(IO_psram_dq[7:0]));
    assign O_psram_ck[1]=0;
    assign O_psram_ck_n[1]=1;
    assign O_psram_reset_n[1]=0;
    assign O_psram_cs_n[1]=1;
    assign IO_psram_rwds[1]=1'bz;
    assign IO_psram_dq[15:8]=8'bz;
    ELVDS_OBUF clock_buffer(.I(tc),.O(tmds_clk_p),.OB(tmds_clk_n));
    genvar i;
    generate for(i=0;i<3;i=i+1) begin: output_lane
        ELVDS_OBUF buffer_lane(.I(tx[i]),.O(tmds_d_p[i]),.OB(tmds_d_n[i]));
    end endgenerate
    wire pcm_error=|(pcm_status0&8'h38) || |(pcm_status1&8'h38);
    assign led_n=~{stage==RUN,failed || pcm_error,video_underrun || memory_error,audio_overflow || audio_underflow,initialized,pixel_lock && system_lock};
endmodule
