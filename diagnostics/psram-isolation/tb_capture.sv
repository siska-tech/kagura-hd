`timescale 1ns/1ps
module tb_capture;
    reg clk=0,reset=1,arm=0,trigger=0,sample_valid=1;
    always #5 clk=~clk;
    reg [1:0] source=1;
    reg [31:0] tx_sample=32'hdeadbeef,rx_sample=32'h43210fed,request_sample=0,window_sample=0;
    wire frozen,overflow;
    wire [2:0] count;
    reg [1:0] read_index=0;
    wire [47:0] read_data;
    psram_boundary_capture #(.DEPTH(4)) dut(.*);
    initial begin
        repeat(2) @(negedge clk);reset=0;
        repeat(3) @(negedge clk);if(count!=0) $fatal(1,"pretrigger capture");
        arm=1;@(negedge clk);arm=0;source=0;trigger=1;
        @(negedge clk);trigger=0;
        wait(frozen);@(negedge clk);
        if(count!=4 || overflow) $fatal(1,"bounded capture");
        for(integer i=0;i<4;i++) begin
            read_index=2'(i);repeat(2) @(negedge clk);
            if(read_data!=={16'(i),32'h43210fed}) $fatal(1,"source/cycle mismatch");
        end
        arm=1;trigger=1;repeat(10) @(negedge clk);
        if(count!=4 || !frozen) $fatal(1,"retrigger");
        $display("PASS: selected boundary capture, bounded freeze, no retrigger");$finish;
    end
    initial begin #10000;$fatal(1,"watchdog");end
endmodule
