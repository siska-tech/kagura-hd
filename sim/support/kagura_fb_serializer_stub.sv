// Serializer is replaced only at the physical-pin boundary.
module serializer #(parameter int NUM_CHANNELS=3,parameter real VIDEO_RATE=74.25e6)(
    input wire clk_pixel,clk_pixel_x5,reset,
    input wire [9:0] tmds_internal[NUM_CHANNELS-1:0],
    output wire [2:0] tmds,output wire tmds_clock);
    assign tmds=0; assign tmds_clock=clk_pixel;
endmodule
