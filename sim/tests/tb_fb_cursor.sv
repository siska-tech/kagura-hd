`timescale 1ns/1ps
module tb_fb_cursor;
 reg sys_clk=0,pix_clk=0,sys_reset=1,pix_reset=1;
 always #(500.0/54) sys_clk=~sys_clk;
 always #(500.0/74.25) pix_clk=~pix_clk;
 reg [10:0] cx=0;reg [9:0] cy=0;
 integer frame=0,checked=0;
 always @(posedge pix_clk) begin
  if(pix_reset) begin cx<=0;cy<=0;frame<=0;end
  else if(cx==1649) begin cx<=0;if(cy==749) begin cy<=0;frame<=frame+1;end else cy<=cy+1'b1;end
  else cx<=cx+1'b1;
 end
 function automatic [23:0] backdrop(input integer x,y);backdrop=24'(((x&255)<<16)|((y&255)<<8)|((x^y)&255));endfunction
 wire [23:0] background=backdrop(int'(cx),int'(cy)),rgb_out;
 reg req_valid=0,req_write=0;reg [4:0] req_addr=0;reg [7:0] req_wdata=0;
 wire req_ready,rsp_valid,rsp_error,irq;wire [7:0] rsp_data;
 kagura_fb_cursor dut(.*);
 wire ref_ready,ref_valid,ref_error,ref_irq;wire [7:0] ref_data;wire [23:0] ref_rgb;
 kagura_fb_cursor_reference reference_cursor(
  .sys_clk,.sys_reset,.pix_clk,.pix_reset,.req_valid,.req_write,.req_addr,.req_wdata,
  .req_ready(ref_ready),.rsp_valid(ref_valid),.rsp_error(ref_error),.rsp_data(ref_data),.irq(ref_irq),
  .cx,.cy,.background,.rgb_out(ref_rgb));
 always @(negedge sys_clk) if(!sys_reset) begin
  if({req_ready,rsp_valid,rsp_error,rsp_data,irq} !== {ref_ready,ref_valid,ref_error,ref_data,ref_irq})
   $fatal(1,"cursor CSR cycle mismatch");
 end
 always @(negedge pix_clk) if(!pix_reset) begin
  if(rgb_out!==ref_rgb) $fatal(1,"cursor RGB cycle mismatch cx=%0d cy=%0d",cx,cy);
  if({dut.position_x,dut.position_y,dut.active_bank,dut.visible,dut.ack} !==
     {reference_cursor.position_x,reference_cursor.position_y,reference_cursor.active_bank,reference_cursor.visible,reference_cursor.ack})
   $fatal(1,"cursor mailbox application edge mismatch");
 end
 task access(input bit wr,input integer address,data,expected_error,output integer result);
  begin
   @(negedge sys_clk);req_valid=1;req_write=wr;req_addr=5'(address);req_wdata=8'(data);
   do @(posedge sys_clk);while(!req_ready);
   @(negedge sys_clk);req_valid=0;
   while(!rsp_valid) @(negedge sys_clk);
   if(!rsp_valid || rsp_error!==1'(expected_error)) $fatal(1,"cursor CSR %0d error %0d expected %0d",address,rsp_error,expected_error);
   result=int'(rsp_data);
  end
 endtask
 task wr(input integer a,d);integer ignored;begin access(1,a,d,0,ignored);end endtask
 task bad(input integer a,d,err);integer ignored;begin access(1,a,d,1,ignored);access(0,21,0,0,ignored);if(ignored!=err) $fatal(1,"cursor sticky error");wr(21,0);end endtask
 task pose(input integer x,y,bank,show);
  begin wr(0,bank*2+show);wr(1,x&255);wr(2,(x>>8)&255);wr(3,y&255);wr(4,(y>>8)&255);wr(17,1);end
 endtask
 function automatic integer texel(input integer bank,x,y);
  texel=bank!=0 ? ((x^y)&3) : 1+((x+y)%3);
 endfunction
 function automatic integer palette(input integer bank,index);
  if(bank!=0) case(index) 1:palette=32'hf00;2:palette=32'h0f0;default:palette=32'h00f;endcase
  else case(index) 1:palette=32'hf80;2:palette=32'h08f;default:palette=32'hf0f;endcase
 endfunction
 task asset(input integer bank);
  integer value,col;
  begin
   wr(14,0);wr(15,bank);wr(5,bank!=0 ? 3 : 31);wr(6,bank!=0 ? 4 : 31);
   for(integer c=1;c<=3;c=c+1) begin col=palette(bank,c);wr(5+c*2,col&255);wr(6+c*2,col>>8);end
   for(integer b=0;b<256;b=b+1) begin
    value=0;
    for(integer p=0;p<4;p=p+1) value=(value<<2)|texel(bank,(b%8)*4+p,b/8);
    wr(16,value);
    if(bank==1 && b==15) begin wr(0,3);bad(17,1,7);end
   end
  end
 endtask
 task wait_generation(input integer target);
  integer lo,hi;
  begin
   lo=0;
   while(lo!=target) begin access(0,19,0,0,lo);access(0,20,0,0,hi);lo=lo|(hi<<8);if(lo!=target) #100000;end
  end
 endtask
 // Independent frame reference: A, negative clipping B, coalesced D, bank
 // switch E (one visible corner pixel), hidden. Position C must never appear.
 integer rx=0,ry=0,rb=0,rshow=0,hx,hy,sx,sy,index,col;
 reg [23:0] expected;
 always @(posedge pix_clk) begin
  if(!pix_reset) begin
   expected=backdrop(int'(cx),int'(cy));hx=rb!=0 ? 3 : 31;hy=rb!=0 ? 4 : 31;
   sx=int'(cx)/2-rx+hx;sy=int'(cy)/2-ry+hy;
   if(rshow!=0 && cx<1280 && cy<720 && sx>=0 && sx<32 && sy>=0 && sy<32) begin
    index=texel(rb,sx,sy);
    if(index!=0) begin col=palette(rb,index);expected=24'((((col>>8)&15)*17<<16)|(((col>>4)&15)*17<<8)|((col&15)*17));end
   end
   if(cx==1649 && cy==719) case(frame)
    0:begin rx=10;ry=20;rb=1;rshow=1;end
    1:begin rx=-3;ry=2;rb=1;rshow=1;end
    2:begin rx=630;ry=350;rb=1;rshow=1;end
    3:begin rx=0;ry=0;rb=0;rshow=1;end
    4:rshow=0;
    default:begin end
   endcase
   #1;if(rgb_out!==expected) $fatal(1,"cursor pixel frame=%0d cx=%0d cy=%0d got=%h expected=%h",frame,cx,cy,rgb_out,expected);
   checked=checked+1;
  end
 end
 integer result;
 initial begin
  repeat(5) @(negedge sys_clk);sys_reset=0;pix_reset=0;
  // Initial bank 0 is protected, incomplete banks cannot be displayed.
  wr(15,0);bad(16,255,1);wr(15,1);wr(14,9);bad(16,255,2);wr(14,0);
  asset(1);pose(10,20,1,1);wait_generation(1);if(!irq) $fatal(1,"cursor completion IRQ");
  // Both active shape and metadata are immutable. Invalid commits cannot
  // replace the pending/latest position or advance its applied generation.
  bad(16,255,1);bad(5,4,1);
  pose(-3,2,1,1);pose(100,80,1,1);pose(630,350,1,1);
  wr(1,0);wr(2,4);bad(17,1,3);
  asset(0);
  wait_generation(3);pose(0,0,0,1);wait_generation(4);pose(0,0,0,0);wait_generation(5);
  wait(frame==6);
  if(dut.bitmap.collisions!=0 || checked<7000000) $fatal(1,"cursor coverage/collision");
  wr(18,64);if(irq) $fatal(1,"cursor IRQ clear");
  // Reset during a pending update cancels the mailbox and invalidates old RAM.
  pose(-1,-1,1,1);
  @(negedge sys_clk);sys_reset=1;pix_reset=1;
  repeat(4) @(negedge sys_clk);sys_reset=0;pix_reset=0;
  access(0,18,0,0,result);if(result!=0) $fatal(1,"cursor reset status");
  wr(0,3);bad(17,1,7);
  #5000;access(0,19,0,0,result);if(result!=0) $fatal(1,"stale cursor ack after reset");
  $display("PASS: fb_cursor %0d pixels, 2x scale, transparency/colors/hotspot, clipping, bank swap, latest coalescing, busy/range/partial-shape errors, no RAM collision",checked);
  $finish;
 end
 initial begin #110000000;$fatal(1,"cursor timeout");end
endmodule
