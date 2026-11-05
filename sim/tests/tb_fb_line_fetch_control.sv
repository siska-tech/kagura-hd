`timescale 1ns/1ps
module tb_fb_line_fetch_control;
    reg clk=0,reset=1,start=0,page=1,req_ready=0,rsp_done=0,rsp_error=0;
    always #5 clk=~clk;
    reg [8:0] row=0;
    reg scan_word_valid=0;
    reg [31:0] scan_word_data=0;
    wire ready,done,error,req_valid,bank_we;
    wire [19:0] req_addr;
    wire [6:0] bank_addr;
    wire [31:0] bank_data;
    kagura_fb_line_fetch dut(.*);
    task launch(input integer y);
        begin
            @(negedge clk); row=9'(y); start=1;
            @(negedge clk); start=0;
        end
    endtask
    initial begin
        repeat(3) @(negedge clk); reset=0;
        launch(360);
        if(!done || !error || req_valid || bank_we) $fatal(1,"invalid row");
        launch(359);
        repeat(5) begin
            @(negedge clk);
            if(!req_valid || req_addr!=57520 || bank_we) $fatal(1,"held request");
        end
        req_ready=1; @(negedge clk); req_ready=0;
        repeat(3) @(negedge clk);
        rsp_done=1; rsp_error=1; @(negedge clk); rsp_done=0; rsp_error=0;
        if(!done || !error || bank_we || !ready) $fatal(1,"memory error");
        launch(0); req_ready=1; @(negedge clk); req_ready=0;
        scan_word_valid=1; #1;
        if(!bank_we || bank_addr!=0) $fatal(1,"stream start");
        reset=1;
        if(bank_we) begin #1; if(bank_we) $fatal(1,"reset write gate"); end
        repeat(3) @(negedge clk); scan_word_valid=0; reset=0; #1;
        if(!ready || req_valid || bank_we || done) $fatal(1,"reset cancellation");
        $display("PASS: fb_line_fetch_control invalid row, backpressure, response error, reset during stream");
        $finish;
    end
    initial begin #100000; $fatal(1,"watchdog"); end
endmodule
