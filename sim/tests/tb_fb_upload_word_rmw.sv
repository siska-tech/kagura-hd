`timescale 1ns/1ps
module tb_fb_upload_word_rmw;
    reg clk=0,write=0;
    reg [3:0] byte_enable=0;
    reg [31:0] wdata=0;
    wire [31:0] rdata;
    reg [31:0] oracle=0,seed=32'h13579bdf;
    integer cases=0;
    always #5 clk=~clk;
    kagura_fb_upload_word dut(.*);
    task put(input [3:0] be,input [31:0] data);
        begin
            @(negedge clk);write=1;byte_enable=be;wdata=data;
            @(posedge clk);
            for(integer lane=0;lane<4;lane++)
                if(be[lane]) oracle[lane*8+:8]=data[lane*8+:8];
        end
    endtask
    task settle_and_check;
        begin
            @(negedge clk);write=0;
            @(posedge clk);#1;
            if(rdata!==oracle) $fatal(1,"independent oracle mismatch expected=%h actual=%h",oracle,rdata);
        end
    endtask
    initial begin
        put(4'hf,32'hfedcba98);settle_and_check();
        for(integer iteration=0;iteration<8;iteration++) begin
            for(integer mask=0;mask<16;mask++) begin
                seed={seed[30:0],seed[31]^seed[21]^seed[1]^seed[0]};
                put(4'(mask),seed);settle_and_check();cases++;
            end
        end
        // Full-word bulk captures need no read edge between writes.
        put(4'hf,32'h12345678);put(4'hf,32'habcdef01);put(4'hf,32'h43210fed);
        settle_and_check();
        // Following partial write must preserve the settled full-word result.
        put(4'b0101,32'h76543210);settle_and_check();
        $display("PASS: RMW 128 mask/pattern cases + consecutive full-word captures + partial after settle");
        $finish;
    end
    initial begin #100000;$fatal(1,"watchdog");end
endmodule

