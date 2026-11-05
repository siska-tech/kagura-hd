`timescale 1ns/1ps
// Contract-level producer deliberately varies gaps and completion phase.
// Expected RAM addresses/data depend only on the requested line, not the FSM.
module tb_fb_rx32_fetch;
    reg clk=0,reset=1,start=0,page=0,req_ready=0,rsp_done=0,rsp_error=0;
    always #5 clk=~clk;
    reg [8:0] row=0;
    reg scan_word_valid=0;
    reg [31:0] scan_word_data=0;
    wire ready,done,error,req_valid,bank_we;
    wire [19:0] req_addr;
    wire [6:0] bank_addr;
    wire [31:0] bank_data;
    kagura_fb_line_fetch dut(.*);
    integer written=0,cases=0;
    reg check_writes=0;
    function automatic [31:0] pattern(input integer index);
        pattern=32'(index*32'h1020305)^32'hc001d00d;
    endfunction
    always @(posedge clk) begin
        if(reset) written=0;
        else if(bank_we) begin
            if(check_writes && (int'(bank_addr)!=written || bank_data!==pattern(written)))
                $fatal(1,"write oracle addr=%0d expected=%0d data=%h",bank_addr,written,bank_data);
            written=written+1;
        end
    end
    task launch(input integer y,input bit p);
        @(negedge clk); row=9'(y);page=p;start=1;written=0;
        @(negedge clk);start=0;
    endtask
    task accept(input integer address);
        wait(req_valid);
        repeat(3) begin
            @(negedge clk);
            if(!req_valid || int'(req_addr)!=address || bank_we || done)
                $fatal(1,"held request/address");
        end
        req_ready=1;@(negedge clk);req_ready=0;
    endtask
    task beat(input integer index,input bit finish,input bit fail);
        scan_word_data=pattern(index);scan_word_valid=1;
        rsp_done=finish;rsp_error=fail;
        @(negedge clk);
        scan_word_valid=0;rsp_done=0;rsp_error=0;
    endtask
    task completion(input bit fail);
        rsp_done=1;rsp_error=fail;
        @(negedge clk);rsp_done=0;rsp_error=0;
    endtask
    task reset_now;
        reset=1;#1;if(bank_we || req_valid) $fatal(1,"reset gate");
        repeat(3) @(negedge clk);
        reset=0;scan_word_valid=0;rsp_done=0;rsp_error=0;req_ready=0;start=0;
        #1;if(!ready || done || bank_we) $fatal(1,"reset did not cancel fetch");
    endtask
    task good_line(input integer y,input bit p,input bit same_edge);
        check_writes=1;launch(y,p);
        for(integer b=0;b<5;b++) begin
            accept((p ? 28800 : 0)+y*80+b*16);
            for(integer w=0;w<16;w++) begin
                repeat((w+b)%3) @(negedge clk);
                beat(b*16+w,same_edge && w==15,0);
            end
            if(!same_edge) begin repeat(4) @(negedge clk);completion(0);end
            if(b<4 && done) $fatal(1,"premature line publication");
        end
        if(!done || error || !ready || written!=80) $fatal(1,"good line completion");
        cases++;@(negedge clk);
    endtask
    initial begin
        repeat(3) @(negedge clk);reset=0;
        // Every row and page, with both final-word completion phases.
        for(integer p=0;p<2;p++)
            for(integer y=0;y<360;y++) good_line(y,1'(p),1'(y));
        check_writes=0;
        // Short response, excess response and memory errors after any prefix.
        for(integer count=0;count<=17;count++) begin
            if(count==16) continue;
            launch(1,0);accept(80);
            for(integer i=0;i<count;i++) beat(i,0,0);
            completion(0);
            if(!done || !error || !ready || written>16) $fatal(1,"malformed count accepted");
            cases++;@(negedge clk);
        end
        for(integer prefix=0;prefix<=16;prefix++) begin
            launch(2,1);accept(28960);
            for(integer i=0;i<prefix;i++) beat(i,0,0);
            completion(1);
            if(!done || !error || !ready) $fatal(1,"memory error accepted");
            cases++;@(negedge clk);
            launch(2,1);accept(28960);
            for(integer i=0;i<prefix;i++) beat(i,0,0);
            reset_now();cases++;
        end
        // Excess word coincident with done must not wrap into RAM address 0.
        launch(0,0);accept(0);
        for(integer i=0;i<16;i++) beat(i,0,0);
        beat(16,1,0);
        if(!done || !error || written!=16) $fatal(1,"simultaneous overflow");
        cases++;@(negedge clk);
        // Error on final word suppresses that write and aborts publication.
        launch(0,0);accept(0);
        for(integer i=0;i<15;i++) beat(i,0,0);
        beat(15,1,1);
        if(!done || !error || written!=15) $fatal(1,"simultaneous final error");
        cases++;@(negedge clk);
        launch(360,0);if(!done || !error || req_valid) $fatal(1,"invalid row");
        cases++;@(negedge clk);
        launch(0,0);reset_now();cases++;
        good_line(359,1,0);
        $display("PASS: rx32 fetch %0d scenarios: 720 rows/pages, gaps, final beat phases, count faults, errors/reset/recovery",cases);
        $finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
