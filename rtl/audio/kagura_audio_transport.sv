// SPDX-License-Identifier: Apache-2.0
// Pixel-paced audio delivery: one stereo sample per 48kHz tick, every
// TICK_NUM/TICK_DEN pixel clocks (525/1 at 25.2MHz, 12375/8 at 74.25MHz).
// Starts muted and unmutes once PREFILL samples are buffered. A tick that
// cannot be served while unmuted emits silence, sets sticky underflow and
// re-enters mute until the FIFO is prefilled again. Muted ticks emit silence
// without flagging an error.
module kagura_audio_transport #(
    parameter integer TICK_NUM=525,
    parameter integer TICK_DEN=1,
    parameter integer PREFILL=4,
    parameter bit REGISTER_TICK=0
) (
    input wire reset, clk_system, clk_pixel,
    input wire sample_valid,
    input wire [31:0] sample_data,
    output wire full, overflow,
    output reg pixel_valid,
    output reg [31:0] pixel_data,
    input wire pixel_ready,
    output wire underflow,
    output reg muted,
    output reg underflow_toggle
);
    wire empty;
    wire response_valid;
    wire [31:0] response_data;
    wire [4:0] level;
    wire fifo_underflow;
    reg pending,starved;
    // Due samples not yet placed in the output slot.
    reg [2:0] credits;
    wire tick;
    generate
        if(TICK_DEN>0 && TICK_NUM>=TICK_DEN && TICK_NUM%TICK_DEN==0) begin: integer_clock
            localparam integer PERIOD=TICK_NUM/TICK_DEN;
            localparam integer CW=$clog2(PERIOD)>0 ? $clog2(PERIOD) : 1;
            reg [CW-1:0] remaining;
            assign tick=remaining==0;
            always @(posedge clk_pixel or posedge reset)
                if(reset) remaining<=CW'(PERIOD-1);
                else remaining<=tick ? CW'(PERIOD-1) : remaining-1'b1;
        end else if(TICK_NUM>TICK_DEN && TICK_DEN>1 &&
                    (TICK_DEN & (TICK_DEN-1))==0 && TICK_NUM%TICK_DEN==TICK_DEN-1) begin: fractional_clock
            // 12375/8 is seven 1547-clock intervals then one 1546-clock
            // interval. This is the exact accumulator sequence, with shorter
            // carry chains. The general form also covers 7/4, 11/4, etc.
            localparam integer Q=TICK_NUM/TICK_DEN;
            localparam integer CW=$clog2(Q+1)>0 ? $clog2(Q+1) : 1;
            localparam integer PW=$clog2(TICK_DEN);
            reg [CW-1:0] remaining;
            reg [PW-1:0] phase;
            reg tick_zero;
            assign tick=REGISTER_TICK ? tick_zero : remaining==0;
            always @(posedge clk_pixel or posedge reset)
                if(reset) begin remaining<=CW'(Q);phase<=0;tick_zero<=0;end
                else if(tick) begin
                    phase<=phase+1'b1;
                    remaining<=phase==PW'(TICK_DEN-2) ? CW'(Q-1) : CW'(Q);
                    tick_zero<=Q==1 && phase==PW'(TICK_DEN-2);
                end else begin
                    remaining<=remaining-1'b1;tick_zero<=remaining==1;
                end
        end else begin: generic_clock
            reg [13:0] accumulator;
            assign tick=accumulator>=14'(TICK_NUM-TICK_DEN);
            always @(posedge clk_pixel or posedge reset)
                if(reset) accumulator<=0;
                else accumulator<=tick ? accumulator+14'(TICK_DEN-TICK_NUM) : accumulator+14'(TICK_DEN);
        end
    endgenerate
    // Prepare the output independently of ready; a valid word is held until
    // accepted. This removes packetizer-ready from the FIFO request path.
    wire issue=!pending && !pixel_valid && credits!=0;
    wire pop=!reset && issue && !muted && !empty;
    wire fill=issue && (muted || empty);
    kagura_async_fifo fifo(.reset(reset),.write_clk(clk_system),
        .write_enable(sample_valid),.write_data(sample_data),.full(full),.overflow(overflow),
        .read_clk(clk_pixel),.read_enable(pop),.read_data(response_data),
        .read_valid(response_valid),.empty(empty),.underflow(fifo_underflow),
        .read_level(level));
    assign underflow=fifo_underflow || starved;
    always @(posedge clk_pixel or posedge reset)
        if(reset) begin
            pending<=0; pixel_valid<=0; pixel_data<=0; muted<=1; starved<=0;
            credits<=0; underflow_toggle<=0;
        end else begin
            // Each new loss toggles independently of legacy sticky flags so
            // software can clear/re-arm its system-domain AUDIO_STATUS bits.
            if((tick && !issue && credits==3'd7) || (fill && !muted)) underflow_toggle<=~underflow_toggle;
            // A saturated credit counter means a deadline was lost.
            if(tick && !issue && credits==3'd7) starved<=1;
            else credits<=credits+{2'b0,tick}-{2'b0,issue};
            if(pixel_valid && pixel_ready) pixel_valid<=0;
            if(pop) pending<=1;
            if(response_valid) begin
                pending<=0; pixel_valid<=1; pixel_data<=response_data;
            end
            if(fill) begin pixel_valid<=1; pixel_data<=0; end
            if(muted) begin
                if(level>=PREFILL) muted<=0;
            end else if(fill) begin
                muted<=1; starved<=1;
            end
        end
endmodule
