`timescale 1ns/1ps
// Compare cached and direct credit predicates on every cycle, including FIFO
// starvation/recovery, prolonged output stalls, saturation and warm reset.
module audio_credit_check #(parameter integer NUM=7,DEN=4,RT=1)
 (input wire sys_clk,pix_clk,reset,output reg done=0);
 reg sample_valid=0,pixel_ready=0;
 reg [31:0] sample_data=0,rng=32'h983a52c1;
 wire full0,full1,overflow0,overflow1,valid0,valid1,under0,under1,mute0,mute1,toggle0,toggle1;
 wire [31:0] data0,data1;
 kagura_audio_transport #(.TICK_NUM(NUM),.TICK_DEN(DEN),.REGISTER_TICK(RT)) reference_audio(
  .reset,.clk_system(sys_clk),.clk_pixel(pix_clk),.sample_valid,.sample_data,
  .full(full0),.overflow(overflow0),.pixel_valid(valid0),.pixel_data(data0),
  .pixel_ready,.underflow(under0),.muted(mute0),.underflow_toggle(toggle0));
 kagura_audio_transport #(.TICK_NUM(NUM),.TICK_DEN(DEN),.REGISTER_TICK(RT),.REGISTER_CREDITS(1)) dut(
  .reset,.clk_system(sys_clk),.clk_pixel(pix_clk),.sample_valid,.sample_data,
  .full(full1),.overflow(overflow1),.pixel_valid(valid1),.pixel_data(data1),
  .pixel_ready,.underflow(under1),.muted(mute1),.underflow_toggle(toggle1));
 integer cycles=0,system_cycles=0;
 integer saturated=0,real_samples=0,silence=0,stalls=0,starved=0;
 always @(negedge sys_clk) begin
  if(reset) begin sample_valid=0;sample_data=0;system_cycles=0;end
  else begin
   system_cycles=system_cycles+1;
   rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
   // Long no-input intervals drain the FIFO; bursts refill and overflow it.
   sample_valid=system_cycles>=30000 && system_cycles<90000 && rng[0];
   sample_data=sample_data+32'h00010003;
   if({full0,overflow0} !== {full1,overflow1}) $fatal(1,"credit SYS mismatch");
  end
 end
 always @(negedge pix_clk) begin
  if(reset) begin pixel_ready=0;cycles=0;done=0;end
  else begin
   cycles=cycles+1;
   pixel_ready=cycles%40000>=16000 && cycles%11!=0;
   if({valid0,data0,under0,mute0,toggle0,reference_audio.credits,reference_audio.pending,reference_audio.issue} !==
      {valid1,data1,under1,mute1,toggle1,dut.credits,dut.pending,dut.issue})
    $fatal(1,"credit PIX mismatch ratio=%0d/%0d cycle=%0d",NUM,DEN,cycles);
   if(dut.have_credits !== (dut.credits!=0)) $fatal(1,"credit predicate invariant");
   if(dut.credits==7) saturated=saturated+1;
   if(valid1 && pixel_ready) if(data1!=0) real_samples=real_samples+1;else silence=silence+1;
   if(valid1 && !pixel_ready) stalls=stalls+1;
   if(dut.fill && !mute1) starved=starved+1;
   if(cycles==250000) begin
    if(!saturated || !real_samples || !silence || !stalls || !starved)
     $fatal(1,"credit coverage ratio=%0d/%0d sat=%0d real=%0d silence=%0d stalls=%0d starved=%0d",
      NUM,DEN,saturated,real_samples,silence,stalls,starved);
    $display("COVER: ratio=%0d/%0d registered_tick=%0d saturated=%0d samples=%0d silence=%0d stalled=%0d starved=%0d",
     NUM,DEN,RT,saturated,real_samples,silence,stalls,starved);
    done=1;
   end
  end
 end
endmodule
module tb_audio_credit_predicate;
 reg sys_clk=0,pix_clk=0,reset=1;
 always #(500.0/54.0) sys_clk=~sys_clk;
 always #(500.0/74.25) pix_clk=~pix_clk;
 wire [4:0] done;
 audio_credit_check #(.NUM(12375),.DEN(8)) real_clock(sys_clk,pix_clk,reset,done[0]);
 audio_credit_check #(.NUM(525),.DEN(1)) integer_clock(sys_clk,pix_clk,reset,done[1]);
 audio_credit_check #(.NUM(7),.DEN(4)) fast_clock(sys_clk,pix_clk,reset,done[2]);
 audio_credit_check #(.NUM(5),.DEN(3)) generic_clock(sys_clk,pix_clk,reset,done[3]);
 audio_credit_check #(.NUM(12375),.DEN(8),.RT(0)) plain_clock(sys_clk,pix_clk,reset,done[4]);
 initial begin
  repeat(5) @(negedge pix_clk);reset=0;
  repeat(60000) @(negedge pix_clk);reset=1;
  repeat(5) @(negedge pix_clk);reset=0;
  wait(&done);$display("PASS: audio credit predicate, 5 clock variants, 1550000 cycle comparisons, saturation/stalls/starvation/recovery and warm reset");$finish;
 end
 initial begin #5000000;$fatal(1,"credit predicate timeout");end
endmodule
