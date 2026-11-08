// Diagnostic only (design-audit-report.md section 20). Exhaustive CSR 31
// safety check of the T8 register RTL (t8-di-local.patch):
//  S1 reset value of diag_broadcast is 0
//  S2 all 256 write values from both prior states: next = bit2 ? 0 : bit1 ? 1 : prev
//     (bit2 wins when both are set), never a response error. The bit0 ACK
//     path is the unchanged pre-T8 line (not exercised here: no completion)
//  S3 CSR 31 read data is unchanged ({7'd0,irq}); diag_broadcast is not readable
//  S4 0xFF written to every other base-bank address (0..30) never sets it
//  S5 addresses 27..30 reject writes, so an incrementing burst from <=26
//     cannot reach 31 without first reporting BAD_COMMAND
//  S6 the SDK ACK value (1) never sets it
//  S7 reset clears it from 1
//  S8 window writes in both states pass the RTL select assertions
`timescale 1ns/1ps
module tb_csr31_safety;
 reg clk=0, reset=1, valid=0, write=1;
 always #5 clk=~clk;
 reg [4:0] addr=0;
 reg [7:0] wdata=0;
 wire ready, rsp_valid, rsp_error, irq, busy;
 wire [7:0] rdata;
 kagura_fb_registers #(.AUDIO_CSR(1),.QUEUE_DEPTH(8)) dut(
  .clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),.external_error(1'b0),
  .req_valid(valid),.req_write(write),.req_addr(addr),.req_wdata(wdata),.req_ready(ready),
  .rsp_valid,.rsp_error,.rsp_rdata(rdata),.busy,.irq,
  .cmd_ready(1'b1),.cmd_done(1'b0),.cmd_read_result(1'b0),.cmd_tag(16'd0),.cmd_error(8'd0),.cmd_read_data(512'd0),
  .command(),.upload_data());
 integer checks=0;
 reg got_error; reg [7:0] got_data;
 task automatic access(input integer a, input bit w, input [7:0] d);
  @(negedge clk); addr=5'(a); write=w; wdata=d; valid=1;
  do @(posedge clk); while(!ready);
  @(negedge clk); valid=0;
  while(!rsp_valid) @(negedge clk);
  got_error=rsp_error; got_data=rdata;
  repeat(30) @(negedge clk);
 endtask
 task automatic expect_diag(input bit v, input string what);
  checks++;
  assert(dut.diag_broadcast==v) else $fatal(1,"%s: diag_broadcast=%0d expected %0d",what,dut.diag_broadcast,v);
 endtask
 task automatic window_traffic();
  access(25,1,0);
  for(int i=0;i<64;i++) begin access(24,1,8'(i*37+5)); checks++; assert(!got_error) else $fatal(1,"window write error"); end
 endtask
 initial begin
  repeat(8) @(negedge clk); reset=0; repeat(50) @(negedge clk);
  expect_diag(0,"S1 reset");
  // S2: exhaustive values from both prior states.
  for(int prev=0;prev<2;prev++)
   for(int v=0;v<256;v++) begin
    access(31,1,prev ? 8'h02 : 8'h04); expect_diag(prev[0],"S2 setup");
    access(31,1,8'(v));
    checks++; assert(!got_error) else $fatal(1,"S2 response error for 0x%02x",v);
    expect_diag(v[2] ? 1'b0 : v[1] ? 1'b1 : prev[0], $sformatf("S2 prev=%0d value=0x%02x",prev,v));
    access(31,0,0);
    checks++; assert(got_data[7:1]==0 && got_data[0]==irq) else $fatal(1,"S3 readback 0x%02x",got_data);
   end
  access(31,1,8'h04); expect_diag(0,"clear");
  // S4/S5: every other base-bank address with 0xFF.
  for(int a=0;a<31;a++) begin
   access(a,1,8'hff); expect_diag(0,$sformatf("S4 addr %0d",a));
   if(a>=27) begin checks++; assert(got_error) else $fatal(1,"S5 addr %0d accepted a write",a); end
   access(7,1,0); // clear sticky error
  end
  // S6: SDK ACK value repeatedly.
  for(int i=0;i<64;i++) access(31,1,8'h01);
  expect_diag(0,"S6 SDK ACK");
  // S8: window traffic in both states (RTL assertions active), S7 reset.
  window_traffic(); expect_diag(0,"S8 local");
  access(31,1,8'h02); expect_diag(1,"S8 set");
  window_traffic(); expect_diag(1,"S8 broadcast");
  @(negedge clk); reset=1; repeat(4) @(negedge clk); reset=0; repeat(50) @(negedge clk);
  expect_diag(0,"S7 reset clears");
  window_traffic();
  $display("PASS tb_csr31_safety checks=%0d", checks);
  $finish;
 end
endmodule
