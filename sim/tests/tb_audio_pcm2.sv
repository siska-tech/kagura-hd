`timescale 1ns/1ps
module tb_audio_pcm2;
 reg clk=0,reset=1,apply_valid=0;always #5 clk=~clk;
 reg [15:0] cfg_pcm_gain_l=0,cfg_pcm_gain_r=0;
 reg [1:0] cfg_pcm_enable=0;reg [7:0] cfg_master=32;
 reg signed [7:0] pcm_sample0=0,pcm_sample1=0;
wire [0:0] ref_apply_ready;
wire [0:0] ref_apply_done;
wire [0:0] ref_apply_error;
wire [0:0] ref_apply_busy;
wire [0:0] ref_sample_valid;
wire [15:0] ref_sample_left;
wire [15:0] ref_sample_right;
wire [6:0] ref_last_cycles;
wire [0:0] ref_apply_boundary;
wire [0:0] ref_sample_boundary;
kagura_audio_synth_reference #(.EXTERNAL_SNAPSHOT(1),.PCM_ENABLE(1)) ref_inst(
 .clk,.reset,.apply_valid,.cfg_pcm_gain_l,.cfg_pcm_gain_r,.cfg_pcm_enable,.cfg_master,.pcm_sample0,.pcm_sample1,
 .cfg_step(144'd0),.cfg_duty(24'd0),.cfg_gain_l(48'd0),.cfg_gain_r(48'd0),.cfg_enable(6'd0),.cfg_phase_reset(6'd0),
 .cfg_wave_len(8'h55),.cfg_noise_period(16'd0),.wave_data(8'sd0),.wave_read(),.wave_addr(),
.apply_ready(ref_apply_ready),.apply_done(ref_apply_done),.apply_error(ref_apply_error),.apply_busy(ref_apply_busy),.sample_valid(ref_sample_valid),.sample_left(ref_sample_left),.sample_right(ref_sample_right),.last_cycles(ref_last_cycles),.apply_boundary(ref_apply_boundary),.sample_boundary(ref_sample_boundary));
wire [0:0] dut_apply_ready;
wire [0:0] dut_apply_done;
wire [0:0] dut_apply_error;
wire [0:0] dut_apply_busy;
wire [0:0] dut_sample_valid;
wire [15:0] dut_sample_left;
wire [15:0] dut_sample_right;
wire [6:0] dut_last_cycles;
wire [0:0] dut_apply_boundary;
wire [0:0] dut_sample_boundary;
kagura_audio_synth #(.EXTERNAL_SNAPSHOT(1),.PCM_ENABLE(1),.PCM_ONLY(1)) dut_inst(
 .clk,.reset,.apply_valid,.cfg_pcm_gain_l,.cfg_pcm_gain_r,.cfg_pcm_enable,.cfg_master,.pcm_sample0,.pcm_sample1,
 .cfg_step(144'd0),.cfg_duty(24'd0),.cfg_gain_l(48'd0),.cfg_gain_r(48'd0),.cfg_enable(6'd0),.cfg_phase_reset(6'd0),
 .cfg_wave_len(8'h55),.cfg_noise_period(16'd0),.wave_data(8'sd0),.wave_read(),.wave_addr(),
.apply_ready(dut_apply_ready),.apply_done(dut_apply_done),.apply_error(dut_apply_error),.apply_busy(dut_apply_busy),.sample_valid(dut_sample_valid),.sample_left(dut_sample_left),.sample_right(dut_sample_right),.last_cycles(dut_last_cycles),.apply_boundary(dut_apply_boundary),.sample_boundary(dut_sample_boundary));

 integer cycles=0,checked=0,samples=0,profile=0,offset=-1;
 integer p0l=0,p0r=0,p1l=0,p1r=0,scaled_l,scaled_r,master_int;
 integer positive_clip=0,negative_clip=0,last_boundary=-1;
 reg [15:0] active_l=0,active_r=0;reg [7:0] active_master=32;reg [1:0] active_enable=0;
 reg [255:0] seen0=0,seen1=0;
 function automatic signed [15:0] clamp(input integer v);
  if(v>32767) return 16'sd32767;else if(v< -32768) return -16'sd32768;else return 16'(v);
 endfunction
 always @(posedge clk) begin
  cycles++;
  if(reset) begin
   offset=-1;last_boundary=-1;active_l=0;active_r=0;active_master=32;active_enable=0;
   p0l=0;p0r=0;p1l=0;p1r=0;
  end else begin
   if(ref_apply_boundary) begin active_l=cfg_pcm_gain_l;active_r=cfg_pcm_gain_r;active_master=cfg_master;active_enable=cfg_pcm_enable;end
   if(ref_sample_boundary) begin
    if(last_boundary>=0 && cycles-last_boundary!=1125) $fatal(1,"48k sample cadence");
    last_boundary=cycles;offset=0;
   end else if(offset>=0) offset++;
   if(offset==22) begin
    seen0[$unsigned(pcm_sample0)]=1;
    p0l=active_enable[0] ? int'(pcm_sample0)*int'(active_l[7:0]) : 0;
    p0r=active_enable[0] ? int'(pcm_sample0)*int'(active_r[7:0]) : 0;
   end
   if(offset==25) begin
    seen1[$unsigned(pcm_sample1)]=1;
    p1l=active_enable[1] ? int'(pcm_sample1)*int'(active_l[15:8]) : 0;
    p1r=active_enable[1] ? int'(pcm_sample1)*int'(active_r[15:8]) : 0;
   end
  end
 end
 always @(negedge clk) begin
  if(ref_apply_ready!==dut_apply_ready) $fatal(1,"PCM2 cycle mismatch apply_ready cycle=%0d ref=%h new=%h",cycles,ref_apply_ready,dut_apply_ready);
  if(ref_apply_done!==dut_apply_done) $fatal(1,"PCM2 cycle mismatch apply_done cycle=%0d ref=%h new=%h",cycles,ref_apply_done,dut_apply_done);
  if(ref_apply_error!==dut_apply_error) $fatal(1,"PCM2 cycle mismatch apply_error cycle=%0d ref=%h new=%h",cycles,ref_apply_error,dut_apply_error);
  if(ref_apply_busy!==dut_apply_busy) $fatal(1,"PCM2 cycle mismatch apply_busy cycle=%0d ref=%h new=%h",cycles,ref_apply_busy,dut_apply_busy);
  if(ref_sample_valid!==dut_sample_valid) $fatal(1,"PCM2 cycle mismatch sample_valid cycle=%0d ref=%h new=%h",cycles,ref_sample_valid,dut_sample_valid);
  if(ref_sample_left!==dut_sample_left) $fatal(1,"PCM2 cycle mismatch sample_left cycle=%0d ref=%h new=%h",cycles,ref_sample_left,dut_sample_left);
  if(ref_sample_right!==dut_sample_right) $fatal(1,"PCM2 cycle mismatch sample_right cycle=%0d ref=%h new=%h",cycles,ref_sample_right,dut_sample_right);
  if(ref_last_cycles!==dut_last_cycles) $fatal(1,"PCM2 cycle mismatch last_cycles cycle=%0d ref=%h new=%h",cycles,ref_last_cycles,dut_last_cycles);
  if(ref_apply_boundary!==dut_apply_boundary) $fatal(1,"PCM2 cycle mismatch apply_boundary cycle=%0d ref=%h new=%h",cycles,ref_apply_boundary,dut_apply_boundary);
  if(ref_sample_boundary!==dut_sample_boundary) $fatal(1,"PCM2 cycle mismatch sample_boundary cycle=%0d ref=%h new=%h",cycles,ref_sample_boundary,dut_sample_boundary);

  checked++;
  if(dut_sample_valid) begin
   if(offset!=31 || dut_last_cycles!=31) $fatal(1,"PCM sample acquisition/emit offset %0d cycles=%0d",offset,dut_last_cycles);
   master_int=int'(active_master);
   scaled_l=((p0l+p1l)*master_int)>>>8;scaled_r=((p0r+p1r)*master_int)>>>8;
   if(dut_sample_left!==clamp(scaled_l) || dut_sample_right!==clamp(scaled_r))
     $fatal(1,"independent PCM mix oracle sample=%0d exp=%0d/%0d got=%0d/%0d",samples,clamp(scaled_l),clamp(scaled_r),$signed(dut_sample_left),$signed(dut_sample_right));
   if(scaled_l>32767 || scaled_r>32767) positive_clip++;
   if(scaled_l< -32768 || scaled_r< -32768) negative_clip++;
   samples++;
  end
  // Change sources every system cycle, catching any acquisition-edge drift.
  if(profile==0) begin pcm_sample0=-128;pcm_sample1=-128;end
  else if(profile==1) begin pcm_sample0=127;pcm_sample1=127;end
  else begin pcm_sample0=8'(cycles);pcm_sample1=8'(~cycles);end
 end
 task idle(input integer n);repeat(n) @(negedge clk);endtask
 integer target;
 initial begin
  idle(4);reset=0;
  for(integer k=0;k<9;k++) begin
   @(negedge clk);profile=k;
   case(k)
    0,1:begin cfg_pcm_gain_l=16'hffff;cfg_pcm_gain_r=16'hffff;cfg_master=255;cfg_pcm_enable=3;end
    2:begin cfg_pcm_gain_l=0;cfg_pcm_gain_r=0;cfg_master=255;cfg_pcm_enable=3;end
    3:begin cfg_pcm_gain_l=16'h00ff;cfg_pcm_gain_r=16'hff00;cfg_master=32;cfg_pcm_enable=3;end
    4:begin cfg_pcm_gain_l=16'hff01;cfg_pcm_gain_r=16'h01ff;cfg_master=0;cfg_pcm_enable=3;end
    5:begin cfg_pcm_gain_l=16'hffff;cfg_pcm_gain_r=16'hffff;cfg_master=255;cfg_pcm_enable=1;end
    6:begin cfg_pcm_gain_l=16'h80ff;cfg_pcm_gain_r=16'hff80;cfg_master=128;cfg_pcm_enable=2;end
    7:begin cfg_pcm_gain_l=16'hffff;cfg_pcm_gain_r=16'hffff;cfg_master=255;cfg_pcm_enable=0;end
    8:begin cfg_pcm_gain_l=16'h80ff;cfg_pcm_gain_r=16'hff01;cfg_master=32;cfg_pcm_enable=3;end
   endcase
   while(!ref_apply_ready) @(negedge clk);
   apply_valid=1;@(negedge clk);apply_valid=0;
   if(k==3) begin reset=1;@(negedge clk);reset=0;end
   else begin
    while(!ref_apply_done) @(negedge clk);
    if(k==5) begin
     while(!(dut_inst.state==10 && dut_inst.cycles==7)) @(negedge clk);
     reset=1;@(negedge clk);reset=0;
    end
   end
   target=samples+(k==8 ? 512 : 64);
   while(samples<target) @(negedge clk);
  end
  if(seen0!={256{1'b1}} || seen1!={256{1'b1}} || positive_clip==0 || negative_clip==0)
    $fatal(1,"PCM oracle coverage incomplete");
  $display("PASS: PCM2 mixer %0d samples, all signed8 values, gain/master extremes, pan, clipping, reset; %0d cycle comparisons; acquisition22/25 emit31",samples,checked);$finish;
 end
 initial begin #20000000;$fatal(1,"PCM2 mixer timeout");end
endmodule
