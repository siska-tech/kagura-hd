`timescale 1ns/1ps
module tb_fb_byte_port;
    reg clk=0,reset=1,initialized=0,mem_valid=0,mem_write=0;
    always #5 clk=~clk;
    reg [21:0] mem_addr=0;
    reg [7:0] mem_wdata=0;
    wire mem_ready,mem_done,ctrl_cmd,ctrl_cmd_en;
    wire [7:0] mem_rdata;
    wire [19:0] ctrl_addr;
    wire [31:0] ctrl_wr_data;
    wire [3:0] ctrl_data_mask;
    reg ctrl_cmd_rdy=1,ctrl_rd_data_valid=0;
    reg [31:0] ctrl_rd_data=0;
    reg [31:0] memory[0:7];
    integer remaining=0,i,j;
    reg pending_read=0;
    reg [19:0] saved_addr;
    kagura_fb_byte_port dut(.*);
    always @(posedge clk) begin
        ctrl_rd_data_valid<=0;
        if(reset) begin
            ctrl_cmd_rdy<=1; remaining<=0;
        end else if(ctrl_cmd_en) begin
            if(!ctrl_cmd_rdy) $fatal(1,"accepted while busy");
            ctrl_cmd_rdy<=0;
            remaining<=7;
            pending_read<=!ctrl_cmd;
            saved_addr<=ctrl_addr;
            if(ctrl_cmd)
                for(i=0;i<4;i=i+1)
                    if(!ctrl_data_mask[i]) memory[ctrl_addr][i*8+:8]<=ctrl_wr_data[i*8+:8];
        end else if(!ctrl_cmd_rdy) begin
            if(remaining==0) begin
                ctrl_cmd_rdy<=1;
                if(pending_read) begin
                    ctrl_rd_data_valid<=1;
                    ctrl_rd_data<=memory[saved_addr];
                end
            end else remaining<=remaining-1;
        end
        if(mem_done && !ctrl_cmd_rdy) $fatal(1,"early completion");
    end
    task transact(input integer wr,a,d);
        begin
            @(negedge clk);
            mem_valid=1; mem_write=wr; mem_addr=a; mem_wdata=d;
            wait(mem_ready); @(posedge clk); @(negedge clk);
            mem_valid=0;
            wait(mem_done);
            if(!wr && mem_rdata!==d[7:0]) $fatal(1,"read lane mismatch");
            @(negedge clk);
        end
    endtask
    initial begin
        for(j=0;j<8;j=j+1) memory[j]=32'h12345678;
        repeat(3) @(negedge clk);
        reset=0;
        repeat(3) @(negedge clk);
        if(mem_ready) $fatal(1,"ready before init");
        initialized=1;
        for(j=0;j<4;j=j+1) transact(1,4+j,160+j);
        if(memory[1]!==32'ha3a2a1a0) $fatal(1,"write lanes");
        if(memory[0]!==32'h12345678 || memory[2]!==32'h12345678) $fatal(1,"neighbor corruption");
        for(j=0;j<4;j=j+1) transact(0,4+j,160+j);
        $display("PASS fb_byte_port: init gating, all byte lanes, write completion, read routing");
        $finish;
    end
    initial begin #100000; $fatal(1,"watchdog"); end
endmodule
