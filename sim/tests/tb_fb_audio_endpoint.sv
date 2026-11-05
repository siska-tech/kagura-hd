`timescale 1ns/1ps
module tb_fb_audio_endpoint;
 reg clk=0;always #5 clk=~clk;
 reg reset=1,enabled=1,req_valid=0,req_write=0;
 reg [3:0] req_addr=0;reg [7:0] req_wdata=0;
 wire req_ready,rsp_valid,rsp_error;wire [7:0] rsp_data;
 wire audio_apply,audio_capture,audio_commit_done,audio_settings_valid,audio_busy,audio_settle;
 reg audio_ready=0,audio_done=0,audio_apply_error=0;
 reg fifo_underflow=0,fifo_overflow=0,muted=0;reg [7:0] pcm_status0=0,pcm_status1=0;
 wire [143:0] cfg_step;wire [23:0] cfg_duty;wire [47:0] cfg_gain_l,cfg_gain_r;
 wire [5:0] cfg_enable,cfg_phase_reset;wire [7:0] cfg_wave_len,cfg_master;
 wire [15:0] cfg_noise_period,cfg_pcm_gain_l,cfg_pcm_gain_r;
 wire [1:0] cfg_pcm_enable,pcm_prepare,pcm_stop,pcm_clear,pcm_loop_enable;
 wire [43:0] pcm_start,pcm_end,pcm_loop;

 kagura_fb_audio_endpoint dut(.*);
 reg valid=0;reg [127:0] command=0;
 wire ready,done,host_valid;wire [7:0] error;wire [15:0] tag;
 kagura_fb_commands #(.AUDIO_CSR(1)) engine(
  .clk,.reset,.valid,.ready,.command,.upload_data(512'd0),.done,.error,.tag,
  .read_data(),.read_result(),.host_valid,.host_ready(1'b1),.host_write(),.host_addr(),.host_words(),.host_wdata(),.host_mask(),
  .host_done(1'b0),.host_error(1'b0),.host_rdata(512'd0),.present_valid(),.present_ready(1'b1),.present_done(1'b0),.present_page(),.present_palette(),
  .audio_capture,.audio_apply,.audio_commit_done,.audio_settings_valid,.audio_busy,.audio_settle,.audio_ready,.audio_done,.audio_apply_error);
 integer accesses=0,captures=0,applies=0,prepares=0,stops=0,clears=0;
 always @(posedge clk) if(!reset) begin
  if(audio_capture) captures++;
  if(audio_apply && audio_ready) applies++;
  if(pcm_prepare[0] || pcm_prepare[1]) prepares++;
  if(pcm_stop[0] || pcm_stop[1]) stops++;
  if(pcm_clear[0] || pcm_clear[1]) clears++;
  if(host_valid) $fatal(1,"audio command accessed memory");
 end
 task access(input bit wr,input [3:0] a,input [7:0] d,input bit bad,output [7:0] v);
  begin
   @(negedge clk);while(!req_ready) @(negedge clk);
   req_valid=1;req_write=wr;req_addr=a;req_wdata=d;
   @(negedge clk);req_valid=0;
   while(!rsp_valid) @(negedge clk);
   if(rsp_error!==bad) $fatal(1,"CSR error a=%h idx=%h expected=%b got=%b",a,dut.index,bad,rsp_error);
   v=rsp_data;accesses++;
  end
 endtask
 reg [7:0] v;
 task setting(input [7:0] i,input [7:0] d);
  begin access(1,6,i,0,v);access(1,7,d,0,v);end
 endtask
 task submit(input [7:0] op,input [15:0] t,input bit bad);
  begin
   @(negedge clk);while(!ready) @(negedge clk);
   command=0;command[7:0]=op;command[31:16]=t;command[32]=bad;valid=1;
   @(negedge clk);valid=0;
  end
 endtask
 task complete_audio(input bit bad);
  begin
   wait(audio_apply);repeat(3) @(negedge clk);
   if(done) $fatal(1,"completed before ready");
   audio_ready=1;@(negedge clk);audio_ready=0;
   repeat(3) @(negedge clk);
   if(done || !audio_busy) $fatal(1,"completed before apply");
   audio_done=!bad;audio_apply_error=bad;@(negedge clk);audio_done=0;audio_apply_error=0;
   if(!done || error!=(bad ? 4 : 0) || audio_busy) $fatal(1,"apply completion/error");
  end
 endtask
 initial begin
  repeat(4) @(negedge clk);reset=0;
  for(integer i=0;i<96;i++) begin
   access(1,6,8'(i),0,v);access(1,7,8'hff,1,v);access(0,7,0,1,v);
  end
  if(!audio_settings_valid || cfg_enable!=0 || cfg_step!=0) $fatal(1,"unsupported voices changed state");
  setting(8'he0,64);setting(8'h6c,4);setting(8'h6d,2);setting(8'h6e,3);
  setting(8'h8c,2);setting(8'h8d,4);setting(8'h8e,3);
  submit(7,16'h1234,0);wait(audio_apply);
  if(cfg_master!=64 || cfg_pcm_gain_l!=16'h0204 || cfg_pcm_gain_r!=16'h0402 || cfg_pcm_enable!=3) $fatal(1,"PCM snapshot content");
  setting(8'he0,32);setting(8'h6c,8);
  if(cfg_master!=64 || cfg_pcm_gain_l!=16'h0204) $fatal(1,"next PCM shadow leaked");
  complete_audio(0);if(tag!=16'h1234 || captures!=1 || applies!=1) $fatal(1,"PCM tag or duplicate apply");
  submit(0,16'h1235,0);wait(done);if(tag!=16'h1235 || error!=0) $fatal(1,"ordered fence");
  submit(7,16'h1236,0);wait(audio_apply);
  if(cfg_master!=32 || cfg_pcm_gain_l!=16'h0208) $fatal(1,"next PCM shadow");
  complete_audio(1);
  submit(7,16'h1237,1);wait(done);if(error!=2 || captures!=2) $fatal(1,"reserved bytes admitted capture");
  for(integer c=0;c<2;c++) begin
   setting(8'(96+c*32+2),64);
   access(1,6,8'(96+c*32+15),0,v);access(1,7,1,1,v);
   access(1,7,8,1,v);access(1,7,2,0,v);access(1,7,4,0,v);
   setting(8'(96+c*32+2),0);setting(8'(96+c*32+4),128);
   setting(8'(96+c*32+15),1);
  end
  repeat(5) @(negedge clk);
  if(prepares!=2 || stops!=2 || clears!=2) $fatal(1,"PCM command/width guard");
  for(integer a=8;a<16;a++) begin access(1,4'(a),1,1,v);access(0,4'(a),0,1,v);end
  submit(7,16'h1239,0);wait(audio_apply);@(negedge clk);reset=1;
  repeat(3) @(negedge clk);reset=0;repeat(4) @(negedge clk);
  if(!ready || audio_apply || audio_busy || cfg_pcm_enable!=0 || cfg_master!=32) $fatal(1,"reset pending PCM apply");
  if(captures!=3 || applies!=2) $fatal(1,"PCM capture counts");
  $display("PASS: PCM2 endpoint %0d CSR accesses; unsupported voices, PCM shadow/snapshot, tag, guards, reset",accesses);$finish;
 end
 initial begin #1000000;$fatal(1,"PCM2 endpoint timeout");end
endmodule
