`timescale 1ns/1ps
module tb_fb_line_banks;
    reg sys_clk=0,pix_clk=0,sys_reset=1,pix_reset=1;
    always #9 sys_clk=~sys_clk;
    always #7 pix_clk=~pix_clk;
    reg sys_write=0,sys_done=0,sys_page=0,pix_take=0,pix_enable=0,pix_page=0;
    reg [6:0] sys_addr=0,pix_addr=0;
    reg [31:0] sys_data=0;
    reg [8:0] sys_row=0,pix_row=0;
    reg [15:0] sys_generation=1,pix_generation=1;
    wire sys_can_write,pix_line_valid,pix_data_valid,pix_underrun;
    wire [31:0] pix_data;
    kagura_fb_line_banks dut(.*);
    task publish(input integer row,gen,value);
        begin
            wait(sys_can_write);
            for(integer i=0;i<80;i=i+1) begin
                @(negedge sys_clk); sys_write=1; sys_addr=7'(i); sys_data=32'(value+i);
            end
            @(negedge sys_clk); sys_write=0; sys_row=9'(row); sys_generation=16'(gen); sys_done=1;
            @(negedge sys_clk); sys_done=0;
            if(sys_can_write) $fatal(1,"reused published bank");
            repeat(5) @(negedge pix_clk);
        end
    endtask
    task take(input integer row,gen,good);
        begin
            @(negedge pix_clk); pix_row=9'(row); pix_generation=16'(gen); pix_take=1;
            @(negedge pix_clk); pix_take=0;
            if(pix_line_valid!==1'(good) || pix_data_valid) $fatal(1,"tag handover");
        end
    endtask
    task read_line(input integer value);
        begin
            for(integer i=0;i<80;i=i+1) begin
                @(negedge pix_clk); pix_enable=1; pix_addr=7'(i);
                @(negedge pix_clk);
                if(!pix_data_valid || pix_data!==32'(value+i)) $fatal(1,"line word %0d",i);
            end
            pix_enable=0;
        end
    endtask
    initial begin
        repeat(4) @(negedge sys_clk); sys_reset=0; pix_reset=0;
        publish(0,1,100); take(0,1,1); read_line(100);
        // A stale generation is acknowledged but does not transfer bank ownership.
        publish(1,1,200); take(1,2,0);
        publish(1,2,300); take(1,2,1); read_line(300);
        // Publish the back bank while repeatedly reading the current display.
        fork
            publish(2,2,400);
            read_line(300);
        join
        take(2,2,1); read_line(400);
        take(3,2,0);
        if(!pix_underrun) $fatal(1,"underrun flag");
        wait(sys_can_write);
        publish(0,3,500);
        sys_reset=1; pix_reset=1;
        repeat(4) @(negedge sys_clk); sys_reset=0; pix_reset=0;
        publish(0,4,600); take(0,4,1); read_line(600);
        $display("PASS: fb_line_banks async clocks, tags, stale discard, ownership, underrun, pending reset");
        $finish;
    end
    initial begin #1000000; $fatal(1,"watchdog"); end
endmodule
