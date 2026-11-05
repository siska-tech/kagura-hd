"""Generate pin-level integration bench from the already reviewed host driver tasks."""
from pathlib import Path
root = Path(__file__).resolve().parents[2]
out = root/'build/psram-isolation/board-sim'
out.mkdir(parents=True,exist_ok=True)
original = (root/'sim/tests/tb_fb_host.sv').read_text()
tasks = original[original.index('    task byte_transfer'):original.index('    integer sys_cycles')]
prefix = '''`timescale 1ns/1ps
module tb_host_isolation_board #(parameter integer LANES=4, BAD_REQUEST=0);
    reg clk=0,reset=1,sck=0,cs_n=1;
    always #(500.0/54.0) clk=~clk;
    reg [3:0] drive=0,drive_enable=0;
    tri [3:0] host_io;
    for(genvar pin=0;pin<4;pin++) assign host_io[pin]=drive_enable[pin] ? drive[pin] : 1'bz;
    wire busy,gpio_ready,irq_n,uart_tx,frozen,fault,trace_busy;
    wire [1:0] request_count;
    host_isolation_core #(.LANES(LANES),.UART_DIV(4)) dut(
        .clk,.reset,.host_sck(sck),.host_cs_n(cs_n),.host_io,
        .host_busy(busy),.host_ready(gpio_ready),.host_irq_n(irq_n),.uart_tx,
        .request_count,.frozen,.fault,.trace_busy);
    always @* if((drive_enable & dut.endpoint.io_oe)!=0) $fatal(1,"host contention");
    reg [7:0] packet[0:271];
    reg [7:0] uart_byte;
    integer bytes_received=0;
    initial forever begin
        @(negedge uart_tx);#(1000.0/54.0*6);
        for(integer i=0;i<8;i++) begin uart_byte[i]=uart_tx;#(1000.0/54.0*4);end
        if(!uart_tx || bytes_received>=272) $fatal(1,"UART framing/overflow");
        packet[bytes_received]=uart_byte;bytes_received++;
    end
'''
suffix = '''
    reg [127:0] descriptor;
    integer fd;
    initial begin
        repeat(5) @(negedge clk);reset=0;wait(gpio_ready);
        read_registers(32,1,7);
        if({rxbuf[3],rxbuf[2],rxbuf[1],rxbuf[0]}!==32'h314f5349 || rxbuf[5]!=1 || rxbuf[6]!=LANES)
            $fatal(1,"diagnostic identity");
        if(request_count!=0 || bytes_received!=0) $fatal(1,"precommand activity");
        write_one(25,0);
        txbuf[0]=8'hed;txbuf[1]=8'h0f;txbuf[2]=8'h21;txbuf[3]=8'h43;
        write_registers(24,0,4);
        write_one(25,0);read_registers(24,0,4);
        if({rxbuf[3],rxbuf[2],rxbuf[1],rxbuf[0]}!==32'h43210fed) $fatal(1,"upload echo");
        descriptor=0;descriptor[7:0]=4;descriptor[15:8]=1;descriptor[31:16]=1;
        descriptor[63:32]=BAD_REQUEST ? 300036 : 300032;
        descriptor[127:64]=64'hfffffffffffffff0;
        stage_command(descriptor);wait_tag(1,BAD_REQUEST ? 4 : 0);
        wait(bytes_received==136);wait(!trace_busy);repeat(10) @(negedge clk);
        if(BAD_REQUEST) begin
            if(!frozen || !fault || request_count!=1) $fatal(1,"fault did not freeze");
        end else begin
            if(fault || frozen || request_count!=1) $fatal(1,"WRITE state");
            descriptor[7:0]=5;descriptor[31:16]=2;descriptor[127:64]=0;
            stage_command(descriptor);wait_tag(2,0);
            write_one(25,0);read_registers(24,0,4);
            for(integer i=0;i<4;i++) if(rxbuf[i]!==8'((300032+i)*13+91)) $fatal(1,"download injection");
            wait(bytes_received==272);wait(!trace_busy);repeat(10) @(negedge clk);
            if(!frozen || fault || request_count!=2) $fatal(1,"completion freeze");
        end
        // Extra mem command cannot generate a third request/frame. CSR remains accessible.
        descriptor[7:0]=4;descriptor[31:16]=3;stage_command(descriptor);
        repeat(1000) @(negedge clk);
        if(request_count!=(BAD_REQUEST ? 1 : 2) || bytes_received!=(BAD_REQUEST ? 136 : 272)) $fatal(1,"postfreeze request");
        fd=$fopen($sformatf("build/psram-isolation/board-sim/uart-l%0d-b%0d.bin",LANES,BAD_REQUEST),"wb");
        for(integer i=0;i<bytes_received;i++) $fwrite(fd,"%c",packet[i]);
        $fclose(fd);
        $display("PASS: board core LANES=%0d BAD_REQUEST=%0d, identity/echo/request/injection/UART/freeze",LANES,BAD_REQUEST);
        $finish;
    end
    initial begin #20000000;$fatal(1,"watchdog");end
endmodule
'''
(out/'tb_host_isolation_board.sv').write_text(prefix+tasks+suffix)
