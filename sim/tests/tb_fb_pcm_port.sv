`timescale 1ns/1ps
module tb_fb_pcm_port;
    reg clk=0,reset=1,initialized=0,flush=0,mem_req_valid=0;
    always #5 clk=~clk;
    reg [21:0] mem_req_addr=0;
    wire mem_req_ready,mem_rsp_valid,mem_rsp_error,req_valid;
    wire [7:0] mem_rsp_data;
    wire [19:0] req_addr;
    reg req_ready=0,rsp_done=0,rsp_error=0;
    reg [31:0] rsp_data=0,value=32'h12345678;
    reg fault=0,pending=0;
    integer cycle=0,delay_left=0,commands=0;
    kagura_fb_pcm_port dut(.*);
    always @(negedge clk) begin
        cycle=cycle+1;
        req_ready=!pending && cycle%3!=0;
        rsp_done=0;
        if(pending) begin
            if(delay_left==0) begin
                rsp_done=1; rsp_data=value; rsp_error=fault; pending=0;
            end else delay_left=delay_left-1;
        end
    end
    always @(posedge clk) if(!reset && req_valid && req_ready) begin
        pending=1; delay_left=3; commands=commands+1;
    end
    task read_byte(input integer address,expected,expected_error);
        begin
            @(negedge clk); mem_req_addr=22'(address); mem_req_valid=1;
            wait(mem_req_ready); @(posedge clk); @(negedge clk); mem_req_valid=0;
            wait(mem_rsp_valid);
            if(mem_rsp_error!==1'(expected_error) || (expected_error==0 && mem_rsp_data!==8'(expected)))
                $fatal(1,"PCM byte response");
            @(negedge clk);
        end
    endtask
    task invalidate;
        begin @(negedge clk); flush=1; @(negedge clk); flush=0; end
    endtask
    initial begin
        repeat(3) @(negedge clk); reset=0;
        if(mem_req_ready) $fatal(1,"request before initialization");
        initialized=1;
        read_byte(0,8'h78,0); read_byte(1,8'h56,0);
        if(commands!=1) $fatal(1,"cache miss on adjacent byte");
        value=32'haabbccdd; invalidate();
        read_byte(1,8'hcc,0); read_byte(2,8'hbb,0);
        if(commands!=2) $fatal(1,"flush or cache failed");
        fault=1; read_byte(8,0,1);
        fault=0; read_byte(8,8'hdd,0);
        if(commands!=4) $fatal(1,"error response cached");
        fork
            read_byte(12,8'hdd,0);
            begin wait(req_valid); invalidate(); end
        join
        read_byte(12,8'hdd,0);
        if(commands!=6) $fatal(1,"flush during read revalidated cache");
        $display("PASS: fb_pcm_port init gating, byte lanes, cache, flush during read, errors, stalls");
        $finish;
    end
    initial begin #100000; $fatal(1,"watchdog"); end
endmodule
