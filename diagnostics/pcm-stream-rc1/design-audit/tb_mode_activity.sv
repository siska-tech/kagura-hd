// Diagnostic only. Replays the exact hardware-host window payloads of the
// audit A/B modes (hardware-host/main.c audit_byte/sample) into archived CSR
// RTL and counts internal transitions per 25 s-equivalent batch pair.
// cmd_read_data is held at 0: its real value after b16_init is unobserved.
`timescale 1ns/1ps
module tb_mode_activity;
 localparam N=7; // 0:z 1:x 2:5 3:f 4:a 5:i 6:o
 reg clk=0, reset=1, valid=0;
 always #5 clk=~clk;
 reg [4:0] addr=0;
 reg [7:0] data[N];
 wire [N-1:0] ready;
 wire [511:0] upload[N], di[N];
 wire [31:0] wword[N];
 longint di_count[N], out_count[N], tx_count[N], ww_count[N];
 reg [511:0] old_di[N], old_out[N], old_tx[N];
 reg [31:0] old_ww[N];
 reg measuring=0;
 for(genvar p=0;p<N;p++) begin:g
  kagura_fb_registers #(.AUDIO_CSR(1),.QUEUE_DEPTH(8)) dut(
   .clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),.external_error(1'b0),
   .req_valid(valid),.req_write(1'b1),.req_addr(addr),.req_wdata(data[p]),.req_ready(ready[p]),
   .cmd_ready(1'b1),.cmd_done(1'b0),.cmd_read_result(1'b0),.cmd_tag(16'd0),.cmd_error(8'd0),.cmd_read_data(512'd0),
   .upload_data(upload[p]));
  for(genvar w=0;w<16;w++) begin:taps
   assign di[p][w*32+:32]=dut.upload_words[w].write_data;
  end
  assign wword[p]=dut.window_write_word;
  kagura_fb_burst_ctrl #(.INIT_CYCLES(8)) txdut(.clk,.reset,.valid(1'b0),.write(1'b0),.addr(20'd0),.words(5'd1),
   .wdata(upload[p]),.mask(64'd0),.phy_dq_i_rise(8'd0),.phy_dq_i_fall(8'd0));
  always @(negedge clk) begin
   if(measuring) begin
    di_count[p]+=$countones(di[p]^old_di[p]);
    out_count[p]+=$countones(upload[p]^old_out[p]);
    tx_count[p]+=$countones(txdut.tx^old_tx[p]);
    ww_count[p]+=$countones(wword[p]^old_ww[p]);
   end
   old_di[p]=di[p]; old_out[p]=upload[p]; old_tx[p]=txdut.tx; old_ww[p]=wword[p];
  end
 end
 function automatic [7:0] sample(input integer channel, input integer half, input integer offset);
  integer amplitude, period;
  amplitude = offset<64 ? 24+((half+37*channel)%64) : 72;
  period = channel ? 32 : 64;
  sample = (offset%period)<period/2 ? 8'(amplitude) : 8'(-amplitude);
 endfunction
 function automatic [7:0] payload(input integer p, input integer chunks, input integer i,
                                  input integer channel, input integer seq, input integer offset);
  reg [7:0] flip; flip = chunks[0] ? 8'haa : 8'h55;
  case(p)
   0: payload=0;
   1: payload=sample(channel,seq,offset+i);
   2: payload=flip;
   3: payload=chunks[0] ? 8'hf0 : 8'h0f;
   4: payload=i<2 ? flip : 0;
   5: payload=i<2 ? 0 : flip;
   default: payload=8'h55;
  endcase
 endfunction
 task automatic wr(input integer a);
  @(negedge clk); addr=5'(a); valid=1;
  @(posedge clk); assert(&ready) else $fatal(1,"CSR not ready");
  @(negedge clk); valid=0;
  repeat(30) @(negedge clk);
 endtask
 initial begin
  for(int p=0;p<N;p++) begin data[p]=0;di_count[p]=0;out_count[p]=0;tx_count[p]=0;ww_count[p]=0;end
  repeat(8) @(negedge clk); reset=0;
  repeat(200) @(negedge clk);
  // T8 diagnostic RTL only: CSR 31 bit1 restores all-word DI switching.
  if($test$plusargs("BROADCAST")) begin for(int p=0;p<N;p++) data[p]=8'h02; wr(31); end
  // Prime with one batch, then measure two batches (sequence 0 and 1),
  // the steady-state cycle of run_legacy()'s writes&1 alternation.
  for(int batch=0;batch<3;batch++) begin
   int chunks=0;
   if(batch==1) measuring=1;
   for(int channel=0;channel<2;channel++)
    for(int offset=0;offset<4096;offset+=64) begin
     for(int p=0;p<N;p++) data[p]=0;
     wr(25);
     for(int i=0;i<64;i++) begin
      for(int p=0;p<N;p++) data[p]=payload(p,chunks,i,channel,batch&1,offset);
      wr(24);
     end
     chunks++;
    end
  end
  measuring=0;
  for(int p=0;p<N;p++)
   $display("MODE %s per_2_batches DI512=%0d window_write_word=%0d upload512=%0d idleTX512=%0d",
            p==0?"z":p==1?"x":p==2?"5":p==3?"f":p==4?"a":p==5?"i":"o",
            di_count[p],ww_count[p],out_count[p],tx_count[p]);
  $display("PASS mode activity"); $finish;
 end
endmodule
