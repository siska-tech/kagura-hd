// SPDX-License-Identifier: Apache-2.0
// SPI (LANES=1) /CS short-high injection at 5 MHz SCK against kagura_spi_adapter.
// FILTER=1 must PASS; FILTER=0 is expected to FAIL (shows the test is sensitive).
`timescale 1ns/1ps
module tb_spi_cs_glitch #(parameter bit FILTER=1, parameter integer GLITCH_NS=40);
    reg clk=0; always #9.259 clk=!clk;   // 54 MHz
    reg reset=1, sck=0, cs_n=1, mosi=0;
    wire [3:0] io_out, io_oe;
    wire busy, irq_drive, req_valid, req_write, rsp_ready, late;
    wire [5:0] req_addr; wire [7:0] req_wdata;
    reg rsp_valid=0; reg [7:0] rsp_rdata=0;
    kagura_spi_adapter #(.LANES(1),.REG_ADDR_BITS(6),.STATUS_ADDR(6'd27),.FILTER_CS_HIGH(FILTER)) dut(
        .clk,.reset,.spi_sck(sck),.spi_cs_n(cs_n),.spi_io_in({3'b0,mosi}),.spi_io_out(io_out),.spi_io_oe(io_oe),
        .busy,.irq_drive,.irq_level(1'b0),.queue_free(6'd32),.req_valid,.req_ready(1'b1),.req_write,.req_addr,
        .req_wdata,.rsp_valid,.rsp_ready,.rsp_rdata,.rsp_error(1'b0),.late);
    function automatic [7:0] model(input [5:0] a); model={2'b10,a}^8'h3c; endfunction
    integer writes=0, status_reads=0, errors=0;
    reg [5:0] waddr[0:15]; reg [7:0] wdata[0:15];
    always @(posedge clk) begin
        rsp_valid<=0;
        if(req_valid) begin
            if(req_write) begin waddr[writes]<=req_addr; wdata[writes]<=req_wdata; writes<=writes+1; end
            else begin rsp_valid<=1; rsp_rdata<=model(req_addr); if(req_addr==27) status_reads<=status_reads+1; end
        end
    end
    wire miso=io_oe[1] ? io_out[1] : 1'bz;
    task automatic xfer(input [7:0] tx, output [7:0] rx);
        for(integer b=7;b>=0;b--) begin
            mosi=tx[b]; #100; sck=1; rx[b]=miso; #100; sck=0;
        end
    endtask
    task automatic glitch; begin #20; cs_n=1; #(GLITCH_NS); cs_n=0; #20; end endtask
    task automatic check(input bit cond, input string what); if(!cond) begin errors++; $display("FAIL: %s", what); end endtask
    reg [7:0] rx, st, d0, d1;
    initial begin
        #200 reset=0; #200;
        // Write frame: header(inc, addr 0x10), 0x11, glitch, 0x22, glitch, 0x33.
        cs_n=0; #100;
        xfer({2'b01,6'h10},st); xfer(8'h11,rx); glitch(); xfer(8'h22,rx); glitch(); xfer(8'h33,rx);
        #100 cs_n=1; #400;
        check(st==model(27), $sformatf("status on MISO during header %h", st));
        check(writes==3, $sformatf("write count %0d", writes));
        check(writes>0 && waddr[0]==6'h10 && wdata[0]==8'h11, "write0");
        check(writes>1 && waddr[1]==6'h11 && wdata[1]==8'h22, "write1");
        check(writes>2 && waddr[2]==6'h12 && wdata[2]==8'h33, "write2");
        // Read frame: header(read, inc, 0x20), count 2, glitch, dummy, glitch, 2 data.
        cs_n=0; #100;
        xfer({2'b11,6'h20},st); xfer(8'd2,rx); glitch(); xfer(8'h00,rx); glitch(); xfer(8'h00,d0); xfer(8'h00,d1);
        #100 cs_n=1; #400;
        check(d0==model(6'h20) && d1==model(6'h21), $sformatf("read data %h %h", d0, d1));
        check(status_reads==2, $sformatf("status fetches %0d (one per frame)", status_reads));
        check(!late, "sticky late");
        // Normal inter-frame CS high (300 ns) still ends a frame.
        cs_n=0; #100; xfer({2'b00,6'h05},st); xfer(8'h55,rx); #100 cs_n=1; #300;
        cs_n=0; #100; xfer({2'b00,6'h06},st); xfer(8'h66,rx); #100 cs_n=1; #400;
        check(writes==5 && waddr[3]==6'h05 && wdata[3]==8'h55 && waddr[4]==6'h06 && wdata[4]==8'h66, "back-to-back frames");
        check(!late, "sticky late after back-to-back");
        if(errors==0) $display("PASS: SPI /CS %0d ns glitch FILTER=%0d", GLITCH_NS, FILTER);
        else $display("RESULT FAIL: %0d errors FILTER=%0d", errors, FILTER);
        $finish;
    end
endmodule
