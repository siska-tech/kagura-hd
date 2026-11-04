`timescale 1ns/1ps
// Board-top functional integration only: clocks, DDR PHY and LVDS pins are
// stubbed. The real boot/host/core RTL talks to the independent CA model.
package kagura_fb_config; localparam integer HOST_LANES=1; endpackage
package fb_board_io; logic [7:0] read_r,read_f; endpackage
module kagura_nano9k_clocks #(parameter integer VIDEO_ID_CODE=4,PSRAM_CK_ENABLE=1)(
 input wire clk27,reset_n,output reg pixel=0,serial=0,system_clk=0,
 output wire pixel_lock,system_lock,psram_ck);
 always #(500.0/74.25) pixel=~pixel;
 always #(100.0/74.25) serial=~serial;
 always #(500.0/54.0) system_clk=~system_clk;
 assign pixel_lock=reset_n; assign system_lock=reset_n; assign psram_ck=system_clk;
endmodule
module ELVDS_OBUF(input wire I,output wire O,OB); assign O=I; assign OB=~I; endmodule
module kagura_hyperram_phy_gowin(
 input wire clk,clk_ck,phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,
 input wire [7:0] phy_dq_o_rise,phy_dq_o_fall,
 input wire phy_rwds_oe,phy_rwds_o_rise,phy_rwds_o_fall,
 output wire [7:0] phy_dq_i_rise,phy_dq_i_fall,
 output wire phy_rwds_i_rise,phy_rwds_i_fall,
 output wire O_psram_ck,O_psram_ck_n,O_psram_reset_n,O_psram_cs_n,
 inout wire IO_psram_rwds,inout wire [7:0] IO_psram_dq);
 assign phy_dq_i_rise=fb_board_io::read_r; assign phy_dq_i_fall=fb_board_io::read_f;
 assign phy_rwds_i_rise=0; assign phy_rwds_i_fall=0;
 assign O_psram_ck=0; assign O_psram_ck_n=1;
 assign O_psram_reset_n=phy_reset_n; assign O_psram_cs_n=phy_cs_n;
endmodule
module tb_fb_board;
 reg reset_n=0,sck=0,cs_n=1,mosi=0;
 wire ready,busy,irq_n;
 tri [3:0] host_io;
 assign host_io[0]=!cs_n ? mosi : 1'bz;
 kagura_fb_top dut(.clk27(1'b0),.reset_n,.host_sck(sck),.host_cs_n(cs_n),.host_io,
  .host_busy(busy),.host_ready(ready),.host_irq_n(irq_n),.sd_hiz(),
  .tmds_clk_p(),.tmds_clk_n(),.tmds_d_p(),.tmds_d_n(),.led_n(),
  .O_psram_ck(),.O_psram_ck_n(),.O_psram_reset_n(),.O_psram_cs_n(),.IO_psram_rwds(),.IO_psram_dq());
 kagura_hyperram_pair_model #(.BYTES(262144),.MAX_WORDS(16)) model(
  .clk(dut.system_clk),.reset_n(dut.phy_reset_n),.cs_n(dut.phy_cs_n),.ck_en(dut.phy_ck_en),
  .dq_oe(dut.phy_dq_oe),.rwds_oe(dut.phy_rwds_oe),.dq_r(dut.phy_dq_o_rise),.dq_f(dut.phy_dq_o_fall),
  .mask_r(dut.phy_rwds_o_rise),.mask_f(dut.phy_rwds_o_fall),.read_r(fb_board_io::read_r),.read_f(fb_board_io::read_f));
 task transfer(input [7:0] tx,output [7:0] rx);
  begin
   for(integer b=7;b>=0;b=b-1) begin
    mosi=tx[b]; #500; sck=1; rx[b]=host_io[1]; #500; sck=0;
   end
  end
 endtask
 reg [7:0] ignored,identity[0:6];
 initial begin
  #500; reset_n=1;
  // A premature host upload must be rejected and cannot contaminate the
  // diagnostic payload, even while the memory initialization is in flight.
  cs_n=0;#300;transfer(8'h18,ignored);transfer(8'hff,ignored);#100;cs_n=1;
  wait(ready && !busy);
  if(dut.host.registers.sticky_error!=1) $fatal(1,"early host upload was not rejected");
  cs_n=0;#300;transfer(8'h07,ignored);transfer(0,ignored);#100;cs_n=1;#300;
  for(integer n=0;n<230400;n=n+1) begin
   if(model.memory[n]!==8'd0) $fatal(1,"boot page byte %0d",n);
  end
  for(integer n=0;n<64;n=n+1) begin
   if(model.memory[240000+n]!==8'd0 || model.memory[240064+n]!==8'd0)
    $fatal(1,"boot PCM byte %0d",n);
  end
  if(dut.failed) $fatal(1,"boot failure");
  cs_n=0; #300; transfer(8'hc0,ignored); transfer(7,ignored); transfer(0,ignored);
  for(integer n=0;n<7;n=n+1) transfer(0,identity[n]);
  #100; cs_n=1;
  if({identity[0],identity[1],identity[2],identity[3]}!==32'h4b464231 || identity[4]!=1 || identity[5]!=2 || identity[6]!=127)
   $fatal(1,"host unavailable after boot");
  wait(dut.core.cx==2 && dut.core.cy==0); @(negedge dut.pixel);
  // AUDIO_APPLY takes effect at the next 48 kHz sample boundary, after
  // host READY. It must be active by this first displayed-frame check.
  if(!dut.pcm_status0[1] || !dut.pcm_status1[1]) $fatal(1,"boot did not start PCM");
  if(dut.core.rgb!==24'd0) $fatal(1,"diagnostic display pixel");
  if(dut.video_underrun || dut.memory_error || dut.audio_overflow || dut.audio_underflow) $fatal(1,"board diagnostic error");
  $display("PASS: fb_board real top boot, both pages/PCM data, audio start, SPI identity and displayed pixel");
  $finish;
 end
 initial begin #25000000; $fatal(1,"board boot timeout"); end
endmodule
