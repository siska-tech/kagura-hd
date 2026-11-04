`timescale 1ns/1ps
module tb_fb_command_bounds;
 reg clk=0,reset=1,valid=0;always #5 clk=~clk;
 reg [127:0] command=0;
 wire ready,done,host_valid,host_write,read_result;wire [7:0] error;wire [15:0] tag;
 wire [19:0] host_addr;wire [4:0] host_words;
 reg host_done=0;integer requests=0,cases=0;
 kagura_fb_commands dut(.clk,.reset,.valid,.ready,.command,.upload_data(512'd0),.done,.error,.tag,
  .read_data(),.read_result,.host_valid,.host_ready(1'b1),.host_write,.host_addr,.host_words,.host_wdata(),.host_mask(),
  .host_done,.host_error(1'b0),.host_rdata(512'd0),.present_valid(),.present_ready(1'b1),.present_done(1'b0),.present_page(),.present_palette());
 always @(posedge clk) begin
  host_done<=!reset && host_valid;
  if(!reset && host_valid) requests=requests+1;
 end
 task check(input [31:0] address,input integer words,input bit allowed);
  integer before_count;
  begin
   @(negedge clk);wait(ready);before_count=requests;
   command=0;command[7:0]=8'(4+(cases%2));command[15:8]=8'(words);command[31:16]=16'(cases);command[63:32]=address;valid=1;
   @(negedge clk);valid=0;wait(done);
   if(tag!==16'(cases) || error!==(allowed ? 8'd0 : 8'd3) || requests-before_count!=(allowed ? 1 : 0))
    $fatal(1,"command bounds addr=%h words=%0d allowed=%0d error=%0d requests=%0d",address,words,allowed,error,requests-before_count);
   @(negedge clk);cases=cases+1;
  end
 endtask
 initial begin
  repeat(3) @(negedge clk);reset=0;
  for(integer a=1048512;a<1048576;a=a+1)
   for(integer n=0;n<=18;n=n+1) check(32'(a*4),n,n>=1 && n<=16 && a+n<=1048576);
  check(32'h400000,1,0);check(32'hfffffffc,1,0);check(32'd1,1,0);check(32'd2,1,0);check(32'd3,1,0);
  check(32'd0,16,1);
  $display("PASS: fb_command_bounds %0d tagged read/write ranges; rejected commands never reach memory",cases);$finish;
 end
 initial begin #2000000;$fatal(1,"command bounds timeout");end
endmodule
