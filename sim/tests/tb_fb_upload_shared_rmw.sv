`timescale 1ns/1ps
// Reusing window_group must not mix descriptor reads with CPU data RMW.
module tb_fb_upload_shared_rmw;
    reg clk=0,reset=1,req_valid=0,req_write=0;
    always #5 clk=~clk;
    reg [4:0] req_addr=0;
    reg [7:0] req_wdata=0;
    wire req_ready,rsp_valid,rsp_error,busy,irq,cmd_valid;
    wire [7:0] rsp_rdata;
    wire [127:0] command;
    wire [511:0] upload_data;
    reg cmd_done=0;
    kagura_fb_registers dut(.clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),
        .req_valid,.req_write,.req_addr,.req_wdata,.req_ready,.rsp_valid,.rsp_error,.rsp_rdata,
        .busy,.irq,.cmd_valid,.cmd_ready(1'b1),.cmd_done,.cmd_read_result(1'b0),
        .cmd_tag(16'd1),.cmd_error(8'd0),.cmd_read_data(512'd0),.command,.upload_data);
    task access(input bit wr,input integer address,value,input bit error_expected,output reg [7:0] result);
        begin
            @(negedge clk);req_valid=1;req_write=wr;req_addr=5'(address);req_wdata=8'(value);
            do @(posedge clk);while(!req_ready);
            @(negedge clk);req_valid=0;
            while(!rsp_valid) @(negedge clk);
            if(rsp_error!==error_expected) $fatal(1,"CSR response error mismatch addr=%0d",address);
            result=rsp_rdata;
        end
    endtask
    reg [7:0] oracle[0:63],value;
    integer target;
    task verify_all;
        begin
            access(1,25,0,0,value);
            for(integer i=0;i<64;i++) begin
                access(0,24,0,0,value);
                if(value!==oracle[i]) $fatal(1,"independent window oracle byte=%0d expected=%h actual=%h",i,oracle[i],value);
            end
        end
    endtask
    initial begin
        repeat(3) @(negedge clk);reset=0;repeat(2) @(negedge clk);
        access(1,25,0,0,value);
        for(integer i=0;i<64;i++) begin oracle[i]=8'(13+i*29);access(1,24,oracle[i],0,value);end
        for(integer i=0;i<16;i++) access(1,8+i,8'hc0+i,0,value);
        for(integer i=0;i<64;i++) begin
            access(0,8+i%16,0,0,value);
            if(value!==8'(8'hc0+i%16)) $fatal(1,"descriptor readback");
            target=(i*17)%64;
            access(1,25,target,0,value);
            oracle[target]=8'(3+i*7);access(1,24,oracle[target],0,value);
            verify_all();
        end
        access(1,25,63,0,value);oracle[63]=8'h42;access(1,24,oracle[63],0,value);
        access(1,24,8'hee,1,value); // pointer64 must not alias byte zero
        verify_all();
        access(1,7,0,0,value);access(1,26,1,0,value);
        access(1,24,8'hff,1,value); // busy locks the shared staging buffer
        @(negedge clk);cmd_done=1;@(negedge clk);cmd_done=0;repeat(2) @(negedge clk);
        verify_all();
        // Reset before a pending CPU commit must clear every lane.
        access(1,25,0,0,value);
        @(negedge clk);req_valid=1;req_write=1;req_addr=24;req_wdata=8'haa;
        do @(posedge clk);while(!req_ready);
        @(negedge clk);req_valid=0;reset=1;
        repeat(3) @(negedge clk);reset=0;repeat(2) @(negedge clk);
        for(integer i=0;i<64;i++) oracle[i]=0;
        verify_all();
        $display("PASS: shared RMW 64 permuted updates with descriptor reads and full-window oracle; pointer64/busy/reset-in-commit");
        $finish;
    end
    initial begin #2000000;$fatal(1,"watchdog");end
endmodule
