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
module tb_fb_board_qspi #(parameter integer LANES=4);
 reg reset_n=0,sck=0,cs_n=1;
 reg [3:0] drive=0,oe=0;tri [3:0] host_io;
 generate for(genvar i=0;i<4;i++) begin: pins
  assign host_io[i]=oe[i] ? drive[i] : 1'bz;
 end endgenerate
 wire ready,busy,irq_n;
 kagura_fb_top #(.HOST_LANES(LANES)) dut(.clk27(1'b0),.reset_n,.host_sck(sck),.host_cs_n(cs_n),.host_io,
  .host_busy(busy),.host_ready(ready),.host_irq_n(irq_n),.sd_hiz(),.tmds_clk_p(),.tmds_clk_n(),.tmds_d_p(),.tmds_d_n(),.led_n(),
  .O_psram_ck(),.O_psram_ck_n(),.O_psram_reset_n(),.O_psram_cs_n(),.IO_psram_rwds(),.IO_psram_dq());
 kagura_hyperram_pair_model #(.BYTES(262144),.MAX_WORDS(16)) model(
  .clk(dut.system_clk),.reset_n(dut.phy_reset_n),.cs_n(dut.phy_cs_n),.ck_en(dut.phy_ck_en),
  .dq_oe(dut.phy_dq_oe),.rwds_oe(dut.phy_rwds_oe),.dq_r(dut.phy_dq_o_rise),.dq_f(dut.phy_dq_o_fall),
  .mask_r(dut.phy_rwds_o_rise),.mask_f(dut.phy_rwds_o_fall),.read_r(fb_board_io::read_r),.read_f(fb_board_io::read_f));
 task transfer(input [7:0] tx,output [7:0] rx);
  begin
   for(integer b=0;b<8/LANES;b++) begin
    drive=LANES==1 ? {3'b0,tx[7-b]} : tx[7-b*4-:4];
    #500;sck=1;
    if(LANES==1) rx[7-b]=host_io[1];else rx[7-b*4-:4]=host_io;
    #500;sck=0;
   end
  end
 endtask
 reg [7:0] ignored,v,lo,hi,err,identity[0:6];integer tag=0;
 task csr_write(input [5:0] a,input [7:0] d);
  begin
   cs_n=0;oe=LANES==1 ? 4'b0001 : 4'b1111;#300;
   transfer({2'b00,a},ignored);transfer(d,ignored);#100;cs_n=1;oe=0;#300;
  end
 endtask
 task csr_read(input [5:0] a,output [7:0] d);
  begin
   cs_n=0;oe=LANES==1 ? 4'b0001 : 4'b1111;#300;
   transfer({2'b10,a},ignored);transfer(1,ignored);
   if(LANES==4) oe=0;
   transfer(0,ignored);transfer(0,d);#100;cs_n=1;oe=0;#300;
  end
 endtask
 task setting(input [7:0] i,input [7:0] d);
  begin
   cs_n=0;oe=LANES==1 ? 4'b0001 : 4'b1111;#300;
   transfer(8'h76,ignored);transfer(i,ignored);transfer(d,ignored);#100;cs_n=1;oe=0;#300;
  end
 endtask
 task command(input [7:0] op,input [7:0] arg,input [31:0] address);
  reg [7:0] d;
  begin
   tag++;
   for(integer i=0;i<16;i++) begin
    d=0;
    if(i==0) d=op;else if(i==1)d=arg;else if(i==2)d=8'(tag);else if(i==3)d=8'(tag>>8);
    else if(i>=4 && i<8)d=address[(i-4)*8+:8];
    csr_write(6'(8+i),d);
   end
   csr_write(26,1);
   do csr_read(27,v);while(!v[4] || v[0]);
   csr_read(28,lo);csr_read(29,hi);csr_read(30,err);
   if({hi,lo}!=16'(tag) || err!=0) $fatal(1,"Host tag/error op=%0d tag=%0d err=%h",op,tag,err);
   csr_write(31,1);
  end
 endtask
 task memory64(input [31:0] address,input [7:0] data);
  begin
   csr_write(25,0);for(integer i=0;i<64;i++)csr_write(24,data);
   command(4,16,address);command(0,0,0);command(5,16,address);
   csr_write(25,0);for(integer i=0;i<64;i++) begin csr_read(24,v);if(v!=data)$fatal(1,"Host PCM data oracle address=%0d byte=%0d",address,i);end
  end
 endtask
 task audio_check(input integer left,input integer right,input integer n);
  begin
   repeat(2) begin @(posedge dut.core.sample_valid);#1;end
   repeat(n) begin
    @(posedge dut.core.sample_valid);#1;
    if($signed(dut.core.sample_left)!=left || $signed(dut.core.sample_right)!=right)
     $fatal(1,"PCM sample oracle expected=%0d/%0d actual=%0d/%0d",left,right,$signed(dut.core.sample_left),$signed(dut.core.sample_right));
   end
  end
 endtask
 initial begin
  #500;reset_n=1;csr_write(24,8'hff);wait(ready && !busy);
  if(dut.host.registers.sticky_error!=1)$fatal(1,"early upload admission");
  csr_write(7,0);
  for(integer i=0;i<230400;i++) if(model.memory[i]!==0)$fatal(1,"boot framebuffer");
  for(integer i=0;i<7;i++)csr_read(6'(i),identity[i]);
  if({identity[0],identity[1],identity[2],identity[3]}!==32'h4b464231 || identity[4]!=1 || identity[5]!=4 || identity[6]!=255)$fatal(1,"PCM ABI identity");
  if(dut.pcm_status0[1] || dut.pcm_status1[1])$fatal(1,"PCM boot enabled");
  // Real unsupported operations must set the common error, not silently pass.
  for(integer k=0;k<3;k++) begin
   csr_write(54,k==0 ? 0 : k==1 ? 4 : 95);csr_write(55,255);csr_read(7,v);
   if(v!=2)$fatal(1,"unsupported synth write");csr_write(7,0);
   csr_read(55,v);csr_read(7,v);if(v!=2)$fatal(1,"unsupported synth read");csr_write(7,0);
  end
  setting(8'h60,100);setting(8'h64,50);setting(8'h6f,1);
  csr_write(54,8'h6f);csr_read(55,v);
  if(!v[4] || dut.core.prefetch.configured!=0 || dut.core.pf_req)$fatal(1,"invalid PCM configured memory");
  setting(8'h6f,4);
  memory64(240000,8'h40);memory64(240064,8'he0);
  setting(8'h60,8'h80);setting(8'h61,8'ha9);setting(8'h62,3);
  setting(8'h64,8'hc0);setting(8'h65,8'ha9);setting(8'h66,3);
  setting(8'h68,8'h80);setting(8'h69,8'ha9);setting(8'h6a,3);
  setting(8'h6c,4);setting(8'h6d,2);setting(8'h6e,3);setting(8'h6f,1);
  do begin csr_write(54,8'h6f);csr_read(55,v);if(v[5:2]!=0)$fatal(1,"PCM0 PREPARE fault");end while(!v[0]);
  command(7,0,0);if(!dut.pcm_status0[1] || dut.pcm_status1[1])$fatal(1,"PCM0 independent start");
  audio_check(32,16,8);
  setting(8'h80,8'hc0);setting(8'h81,8'ha9);setting(8'h82,3);
  setting(8'h84,0);setting(8'h85,8'haa);setting(8'h86,3);
  setting(8'h88,8'hc0);setting(8'h89,8'ha9);setting(8'h8a,3);
  setting(8'h8c,2);setting(8'h8d,4);setting(8'h8e,3);setting(8'h8f,1);
  do begin csr_write(54,8'h8f);csr_read(55,v);if(v[5:2]!=0)$fatal(1,"PCM1 PREPARE fault");end while(!v[0]);
  command(7,0,0);if(!dut.pcm_status0[1] || !dut.pcm_status1[1])$fatal(1,"dual PCM start");
  audio_check(24,0,16);
  setting(8'h6c,8);audio_check(24,0,4);command(7,0,0);audio_check(56,0,8);
  setting(8'h6e,2);command(7,0,0);audio_check(-8,-16,8);
  setting(8'h6e,3);command(7,0,0);audio_check(56,0,8);
  setting(8'h6f,2);setting(8'h8f,2);audio_check(0,0,4);
  if(dut.pcm_status0[1] || dut.pcm_status1[1])$fatal(1,"PCM stop");
  // Four-byte one-shot, DONE/CLEAR and no false global fault on DONE.
  setting(8'h84,8'hc4);setting(8'h85,8'ha9);setting(8'h86,3);setting(8'h8e,1);setting(8'h8f,4);setting(8'h8f,1);
  command(7,0,0);
  do begin csr_write(54,8'h8f);csr_read(55,v);end while(!v[2]);
  if(v[1] || v[5:3]!=0)$fatal(1,"one-shot status");
  audio_check(0,0,4);csr_read(27,v);if(v[3])$fatal(1,"DONE counted as audio fault");
  setting(8'h8f,4);csr_write(54,8'h8f);csr_read(55,v);if(v[5:2]!=0)$fatal(1,"PCM clear");
  csr_read(7,v);if(v!=0)$fatal(1,"shared sticky error");
  wait(dut.core.cx==2 && dut.core.cy==0);@(negedge dut.pixel);
  if(dut.core.rgb!==0 || dut.video_underrun || dut.memory_error || dut.audio_overflow || dut.audio_underflow)$fatal(1,"board final error");
  $display("PASS: PCM2 board LANES=%0d ABI1.4, Host upload/readback/FENCE, stereo sample oracle, gains, pause/resume, loop/one-shot, rejection, display",LANES);$finish;
 end
 initial begin #100000000;$fatal(1,"PCM2 board timeout");end
endmodule
