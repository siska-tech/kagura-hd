// SPDX-License-Identifier: Apache-2.0
// External-clock evaluation top; no PLL/pin/PHY/STA completeness implied.
// EXTERNAL_RGB=0 draws kagura_video_source; 1 takes rgb_in, which must be
// aligned to cx_out/cy_out of the same cycle.
// VIDEO_ID_CODE 1 (640x480, 25.2MHz) or 4 (1280x720, 74.25MHz); the 48kHz
// tick is pixel*8/12375 for VIC4 and the coordinates widen to 11 bits.
module kagura_hdmi_stream_eval #(
    parameter bit EXTERNAL_RGB=0,
    parameter integer VIDEO_ID_CODE=1,
    parameter bit AUDIO_REGISTER_TICK=0,
    parameter bit AUDIO_REGISTER_CREDITS=0,
    parameter bit PACKET_REPLICATE_FIRST=0,
    localparam integer XW=VIDEO_ID_CODE==4 ? 11 : 10
) (
    input wire clk_system,clk_pixel,clk_pixel_x5,reset,
    input wire sample_valid,
    input wire [31:0] sample_data,
    output wire full,overflow,underflow,
    output wire [2:0] tmds,
    output wire tmds_clock,
    output wire muted,
    input wire [23:0] rgb_in,
    output wire [XW-1:0] cx_out,
    output wire [9:0] cy_out,
    output wire underflow_toggle
);
    localparam integer TICK_NUM=VIDEO_ID_CODE==4 ? 12375 : 525;
    localparam integer TICK_DEN=VIDEO_ID_CODE==4 ? 8 : 1;
    wire valid,ready;
    wire [31:0] pcm;
    wire [XW-1:0] x,fw,sw;
    wire [9:0] y,fh,sh;
    wire [23:0] rgb, pattern_rgb;
    generate if(!EXTERNAL_RGB) begin: internal
        kagura_video_source #(.XW(XW),.H_ACTIVE(VIDEO_ID_CODE==4 ? 1280 : 640),.V_ACTIVE(VIDEO_ID_CODE==4 ? 720 : 480))
            video(x,y,pattern_rgb);
    end else begin: external
        assign pattern_rgb=24'h000000;
    end endgenerate
    assign rgb=EXTERNAL_RGB ? rgb_in : pattern_rgb;
    assign cx_out=x;
    assign cy_out=y;
    kagura_audio_transport #(.TICK_NUM(TICK_NUM),.TICK_DEN(TICK_DEN),.REGISTER_TICK(AUDIO_REGISTER_TICK),.REGISTER_CREDITS(AUDIO_REGISTER_CREDITS)) audio_link(reset,clk_system,clk_pixel,
        sample_valid,sample_data,full,overflow,valid,pcm,ready,underflow,muted,underflow_toggle);
    // Diagnostic sink removes HDMI packet generation/TMDS/serializer.
    // Scanout keeps the original VIC4 coordinate period and reset phase.
    reg [XW-1:0] scan_x;
    reg [9:0] scan_y;
    assign x=scan_x;
    assign y=scan_y;
    always @(posedge clk_pixel) begin
        if(reset) begin scan_x<=0;scan_y<=0;end
        else begin
            scan_x<=scan_x==1649 ? 0 : scan_x+1'b1;
            if(scan_x==1649) scan_y<=scan_y==749 ? 0 : scan_y+1'b1;
        end
    end
    // VIC4 has ten audio packet slots in the horizontal blanking period.
    // Use the production scheduler for the original sample_ready handshake.
    reg packet_enable = 0;
    always @(posedge clk_pixel) begin
        if(reset) packet_enable<=0;
        else packet_enable<=x>=1293 && x<1613 && x[4:0]==5'd13;
    end
    kagura_audio_packets #(.VIDEO_ID_CODE(4),.CTS(74250)) audio_packets(
        .clk_pixel,.reset,.video_field_end(x==1279 && y==719),
        .packet_enable,.sample_valid(valid),.sample_data(pcm),
        .sample_ready(ready),.header(),.sub());
    assign tmds=0;
    assign tmds_clock=0;
endmodule