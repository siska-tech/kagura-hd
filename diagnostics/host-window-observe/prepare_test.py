from pathlib import Path
root=Path(__file__).resolve().parents[2];out=root/'build/host-window-observe/sim'
out.mkdir(parents=True,exist_ok=True)
orig=(root/'sim/tests/tb_fb_host.sv').read_text()
tasks=orig[orig.index('    task byte_transfer'):orig.index('    integer sys_cycles')]
prefix='''`timescale 1ns/1ps
module tb_window_observe #(parameter integer LANES=4,NEGATIVE=0);
 reg clk=0,reset=1,sck=0,cs_n=1;
 always #(500.0/54.0) clk=~clk;
 reg [3:0] drive=0,drive_enable=0;
 tri [3:0] host_io;
 for(genvar p=0;p<4;p++) assign host_io[p]=drive_enable[p] ? drive[p] : 1'bz;
 wire busy,gpio_ready,irq_n,uart_tx,frozen,fault,trace_busy;
 wire [1:0] request_count;
 window_observe_core #(.LANES(LANES),.UART_DIV(4),.TIMEOUT(100000)) dut(
 .clk,.reset,.host_sck(sck),.host_cs_n(cs_n),.host_io,
 .host_busy(busy),.host_ready(gpio_ready),.host_irq_n(irq_n),.uart_tx,.frozen,.fault,.trace_busy,.request_count);
 reg [7:0] packet[0:135],uart_byte;
 integer bytes_received=0,fd;
 initial forever begin
  @(negedge uart_tx);#(1000.0/54.0*6);
  for(integer b=0;b<8;b++) begin uart_byte[b]=uart_tx;#(1000.0/54.0*4);end
  if(!uart_tx || bytes_received>=136) $fatal(1,"UART framing or repeat");
  packet[bytes_received]=uart_byte;bytes_received++;
 end
'''
suffix='''
 initial begin
  repeat(5) @(negedge clk);reset=0;wait(gpio_ready);
  read_registers(32,1,7);
  if({rxbuf[3],rxbuf[2],rxbuf[1],rxbuf[0]}!==32'h324f5349) $fatal(1,"ISO2 identity");
  if(bytes_received!=0) $fatal(1,"before arm UART");
  write_one(39,1);
  if(!NEGATIVE) begin
   write_one(25,0);
   txbuf[0]=8'hed;txbuf[1]=8'h0f;txbuf[2]=8'h21;txbuf[3]=8'h43;
   write_registers(24,0,4);
   write_one(25,0);read_registers(24,0,4);
   if({rxbuf[3],rxbuf[2],rxbuf[1],rxbuf[0]}!==32'h43210fed) $fatal(1,"Host echo");
  end
  wait(bytes_received==136);wait(!trace_busy);
  if(!frozen || fault!=(NEGATIVE!=0)) $fatal(1,"freeze/timeout");
  if(!NEGATIVE) begin
   if(dut.rx_bytes!==32'h43210fed || dut.csr_bytes!==32'h43210fed ||
      dut.upload_settled!==32'h43210fed || dut.upload_at_read!==32'h43210fed ||
      dut.csr_bytes_out!==32'h43210fed || dut.tx_bytes_out!==32'h43210fed) $fatal(1,"boundary snapshot");
  end
  write_one(39,1);repeat(1000) @(negedge clk);
  if(bytes_received!=136 || !frozen) $fatal(1,"rearm/repeat");
  fd=$fopen($sformatf("build/host-window-observe/sim/uart-l%0d-n%0d.bin",LANES,NEGATIVE),"wb");
  for(integer i=0;i<136;i++) $fwrite(fd,"%c",packet[i]);$fclose(fd);
  $display("PASS: ISO2 LANES=%0d NEGATIVE=%0d six boundaries/UART/freeze",LANES,NEGATIVE);$finish;
 end
 initial begin #10000000;$fatal(1,"watchdog");end
endmodule
'''
(out/'tb_window_observe.sv').write_text(prefix+tasks+suffix)
