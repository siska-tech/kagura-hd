// Diagnostic only. Archived CSR RTL, identical accepted transactions in six lanes.
`timescale 1ns/1ps
module tb_window_activity;
 reg clk=0, reset=1, valid=0;
 always #5 clk=~clk;
 reg [4:0] addr=0;
 reg [7:0] data[6];
 wire [5:0] ready;
 wire [511:0] upload[6];
 wire [511:0] di[6];
 wire [15:0] we[6];
 integer di_count[6], out_count[6], tx_count[6], commits[6];
 reg [511:0] old_di[6],old_out[6],old_tx[6];
 reg measuring=0;
 for(genvar p=0;p<6;p++) begin:g
  kagura_fb_registers #(.AUDIO_CSR(1),.QUEUE_DEPTH(8)) dut(
   .clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),.external_error(1'b0),
   .req_valid(valid),.req_write(1'b1),.req_addr(addr),.req_wdata(data[p]),.req_ready(ready[p]),
   .cmd_ready(1'b1),.cmd_done(1'b0),.cmd_read_result(1'b0),.cmd_tag(16'd0),.cmd_error(8'd0),.cmd_read_data(512'd0),
   .upload_data(upload[p]));
  for(genvar w=0;w<16;w++) begin:taps
   assign di[p][w*32+:32]=dut.upload_words[w].write_data;
   assign we[p][w]=dut.upload_words[w].writing;
  end
  // Isolate the idle TX tracking documented in core: no PSRAM requests.
  kagura_fb_burst_ctrl #(.INIT_CYCLES(8)) txdut(.clk,.reset,.valid(1'b0),.write(1'b0),.addr(20'd0),.words(5'd1),
   .wdata(upload[p]),.mask(64'd0),.phy_dq_i_rise(8'd0),.phy_dq_i_fall(8'd0));
  always @(negedge clk) begin
   if(measuring) begin
    di_count[p]+=$countones(di[p]^old_di[p]);
    out_count[p]+=$countones(upload[p]^old_out[p]);
    tx_count[p]+=$countones(txdut.tx^old_tx[p]);
    assert($onehot0(we[p])) else $fatal(1,"non-target write");
    commits[p]+=$countones(we[p]);
   end
   old_di[p]=di[p]; old_out[p]=upload[p]; old_tx[p]=txdut.tx;
  end
 end
 task automatic wr(input integer a);
  @(negedge clk); addr=5'(a); valid=1;
  @(posedge clk); assert(&ready) else $fatal(1,"CSR not ready");
  @(negedge clk); valid=0;
  repeat(30) @(negedge clk);
 endtask
 reg [31:0] rng=32'h12345678;
 reg [511:0] expected[6];
 initial begin
  for(int p=0;p<6;p++) begin data[p]=0;di_count[p]=0;out_count[p]=0;tx_count[p]=0;commits[p]=0;expected[p]=0;end
  repeat(8) @(negedge clk); reset=0;
  repeat(200) @(negedge clk);
  // T8 diagnostic RTL only: CSR 31 bit1 restores all-word DI switching.
  if($test$plusargs("BROADCAST")) begin for(int p=0;p<6;p++) data[p]=8'h02; wr(31); end
  measuring=1;
  for(int batch=0;batch<16;batch++) begin
   for(int p=0;p<6;p++) data[p]=0;
   wr(25);
   for(int b=0;b<64;b++) begin
    rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
    data[0]=0;data[1]=8'hff;data[2]=8'h55;data[3]=8'haa;data[4]=b[0]?8'hff:0;data[5]=rng[7:0];
    for(int p=0;p<6;p++) expected[p][b*8+:8]=data[p];
    wr(24);
    for(int p=0;p<6;p++) assert(upload[p]===expected[p]) else $fatal(1,"window data mismatch p=%0d byte=%0d",p,b);
   end
  end
  repeat(10) @(negedge clk); measuring=0;
  for(int p=0;p<6;p++) begin
   assert(commits[p]==1024) else $fatal(1,"commit count");
   $display("WINDOW pattern=%0d writes=%0d DI512=%0d upload512=%0d idleTX512=%0d",p,commits[p],di_count[p],out_count[p],tx_count[p]);
  end
  $display("PASS window activity and per-byte contents"); $finish;
 end
endmodule
