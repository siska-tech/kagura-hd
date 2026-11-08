// SPDX-License-Identifier: Apache-2.0
// Minimal indexed bridge: only absolute CSR 36/37. COMMIT uses tagged opcode 7.
module kagura_fb_audio_endpoint(
 input wire clk,reset,enabled,
 input wire req_valid,req_write,input wire [3:0] req_addr,input wire [7:0] req_wdata,
 output wire req_ready,output reg rsp_valid,rsp_error,output reg [7:0] rsp_data,
 input wire audio_capture,audio_commit_done,
 output wire audio_settings_valid,audio_busy,audio_settle,
 input wire fifo_underflow,fifo_overflow,muted,input wire [7:0] pcm_status0,pcm_status1,
 output wire [143:0] cfg_step,output wire [23:0] cfg_duty,
 output wire [47:0] cfg_gain_l,cfg_gain_r,output wire [5:0] cfg_enable,cfg_phase_reset,
 output wire [7:0] cfg_wave_len,cfg_master,output wire [15:0] cfg_noise_period,
 output wire [15:0] cfg_pcm_gain_l,cfg_pcm_gain_r,output wire [1:0] cfg_pcm_enable,
 input wire [7:0] stream_token,stream_status,
 output reg stream_control_write,stream_publish,
 output reg [7:0] stream_data,
 output wire [43:0] pcm_start,pcm_end,pcm_loop,
 output wire [1:0] pcm_loop_enable,pcm_prepare,pcm_stop,pcm_clear
);

 wire [7:0] index,rdata,reg_status;
 wire read_legal,write_legal,settings_valid,apply_busy,settle;
 wire [47:0] start24,end24,loop24;
 assign pcm_start={start24[45:24],start24[21:0]};
 assign pcm_end={end24[45:24],end24[21:0]};
 assign pcm_loop={loop24[45:24],loop24[21:0]};
 assign audio_settings_valid=settings_valid;
 assign audio_busy=apply_busy;
 assign audio_settle=settle;
 // Capture cannot coincide with a new shadow write. Subsequent writes use
 // the original register pipeline and cannot alter the captured snapshot.
 assign req_ready=!reset && enabled && !settle && !audio_capture;
 wire accept=req_valid && req_ready;
 wire pcm_command=index>=8'h60 && index<8'ha0 && index[4:0]==15;
 wire range_valid=index[7] ?
  !(|start24[47:46] || |end24[47:46] || (pcm_loop_enable[1] && |loop24[47:46])) :
  !(|start24[23:22] || |end24[23:22] || (pcm_loop_enable[0] && |loop24[23:22]));
 wire data_legal=write_legal && !(pcm_command &&
   (req_wdata[7:3]!=0 || (req_wdata[0] && !range_valid)));
 (* ASYNC_REG="TRUE" *) reg [2:0] sync1,sync2;
 reg [1:0] old_fifo;
 wire [1:0] fifo_event=sync2[1:0]&~old_fifo;
 kagura_audio_registers #(.PCM(1),.PCM_ONLY(1)) registers(
  .clk,.reset,.index_write(accept && req_write && req_addr==6),
  .data_write(accept && req_write && req_addr==7 && data_legal),.wdata(req_wdata),
  .index,.rdata,.read_legal,.write_legal,.settings_valid,
  .capture(audio_capture),.commit_done(audio_commit_done),.apply_busy,
  .underflow_event(fifo_event[0]),.overflow_event(fifo_event[1]),.muted(sync2[2]),.status(reg_status),
  .snapshot_step(cfg_step),.snapshot_duty(cfg_duty),.snapshot_l(cfg_gain_l),.snapshot_r(cfg_gain_r),
  .snapshot_enable(cfg_enable),.snapshot_reset(cfg_phase_reset),.snapshot_len(cfg_wave_len),
  .snapshot_master(cfg_master),.snapshot_period(cfg_noise_period),
  .pcm_start(start24),.pcm_end(end24),.pcm_loop(loop24),.pcm_loop_enable,.pcm_prepare,.pcm_stop,.pcm_clear,
  .pcm_status({pcm_status1,pcm_status0}),.snapshot_pcm_l(cfg_pcm_gain_l),.snapshot_pcm_r(cfg_pcm_gain_r),
  .snapshot_pcm_enable(cfg_pcm_enable),.settle);
 always @(posedge clk) begin
  if(reset) begin
   stream_control_write<=0; stream_publish<=0; stream_data<=0;
   sync1<=0;sync2<=0;old_fifo<=0;rsp_valid<=0;rsp_error<=0;rsp_data<=0;
  end else begin
   sync1<={muted,fifo_overflow,fifo_underflow};sync2<=sync1;old_fifo<=sync2[1:0];
   stream_control_write<=0; stream_publish<=0;
   rsp_valid<=accept;rsp_error<=0;rsp_data<=0;
   if(accept) begin
    if(req_write) begin
     if(req_addr==7 && index==8'he3 && req_wdata<=1) begin
      stream_control_write<=1;
      stream_data<=req_wdata;
     end else if(req_addr==7 && index==8'he4) begin
      stream_publish<=1;
      stream_data<=req_wdata;
     end else if(req_addr!=6 && !(req_addr==7 && data_legal)) rsp_error<=1;
    end else case(req_addr)
     6:rsp_data<=index;
     7:case(index)
       8'he3: rsp_data<=8'h51;
       8'he4: rsp_data<=stream_token;
       8'he5: rsp_data<=stream_status;
       default: begin rsp_data<=rdata; rsp_error<=!read_legal; end
     endcase
     default:rsp_error<=1;
    endcase
   end
  end
 end
endmodule
