`timescale 1ns/1ps
module fb_tick_check #(parameter integer NUM=525,DEN=1,REGISTER_TICK=1)(input wire pixel,system_clk,reset,output reg done=0);
 kagura_audio_transport #(.TICK_NUM(NUM),.TICK_DEN(DEN),.REGISTER_TICK(REGISTER_TICK)) dut(
  .reset,.clk_system(system_clk),.clk_pixel(pixel),.sample_valid(1'b0),.sample_data(32'd0),
  .full(),.overflow(),.pixel_valid(),.pixel_data(),.pixel_ready(1'b1),.underflow(),.muted(),.underflow_toggle());
 integer phase=0,checked=0,ticks=0;
 always @(posedge pixel) begin
  if(reset) phase=0;
  else begin
   if(dut.tick!==1'(phase+DEN>=NUM)) $fatal(1,"audio clock %0d/%0d phase %0d",NUM,DEN,phase);
   if(dut.tick) ticks=ticks+1;
   phase=(phase+DEN)%NUM;checked=checked+1;
   if(checked==120000) done=1;
  end
 end
endmodule
module tb_fb_audio_clock;
 reg pixel=0,system_clk=0,reset=1;
 always #5 pixel=~pixel;
 always #7 system_clk=~system_clk;
 wire a,b,c,d,e,f;
 fb_tick_check #(.NUM(525),.DEN(1)) clock25(pixel,system_clk,reset,a);
 fb_tick_check #(.NUM(12375),.DEN(8)) clock74(pixel,system_clk,reset,b);
 fb_tick_check #(.NUM(5),.DEN(3)) fallback(pixel,system_clk,reset,c);
 fb_tick_check #(.NUM(7),.DEN(4)) short_fraction(pixel,system_clk,reset,d);
 fb_tick_check #(.NUM(12375),.DEN(8),.REGISTER_TICK(0)) clock74_plain(pixel,system_clk,reset,e);
 fb_tick_check #(.NUM(7),.DEN(4),.REGISTER_TICK(0)) short_plain(pixel,system_clk,reset,f);
 initial begin
  #100;@(negedge pixel);reset=0;
  wait(clock25.checked==60000);@(negedge pixel);reset=1;
  repeat(5) @(negedge pixel);reset=0;
  wait(a && b && c && d && e && f);
  $display("PASS: fb_audio_clock 720000 exact tick decisions, 525/1, 12375/8, 7/4, registered/combinational ticks, fast-ratio fallback, mid-phase reset");$finish;
 end
 initial begin #2000000;$fatal(1,"audio clock timeout");end
endmodule
