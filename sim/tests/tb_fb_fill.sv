`timescale 1ns/1ps
module tb_fb_fill;
    reg clk=0, reset=1, valid=0, page=0;
    always #5 clk=~clk;
    reg [15:0] x=0,y=0,width=0,height=0;
    reg [3:0] color=0;
    wire ready,done,error,mem_valid,mem_write;
    wire [21:0] mem_addr;
    wire [7:0] mem_wdata;
    reg mem_ready=0,mem_done=0;
    reg [7:0] mem_rdata=0;
    reg [7:0] memory[0:230399];
    reg [7:0] reference_memory[0:230399];
    integer delay_left=0,cycle=0,i,j,k,px,py;
    reg pending=0;
    kagura_fb_fill dut(.*);
    always @(negedge clk) begin
        cycle=cycle+1;
        mem_done=0;
        mem_ready=!pending && cycle%3!=0;
        if (pending) begin
            if (delay_left==0) begin
                mem_done=1;
                pending=0;
            end else delay_left=delay_left-1;
        end
    end
    always @(posedge clk) begin
        if (!reset && mem_valid && mem_ready) begin
            if (mem_addr>=230400) $fatal(1,"address overflow");
            pending=1;
            delay_left=cycle%5+1;
            if(mem_write) memory[mem_addr]=mem_wdata;
            else mem_rdata=memory[mem_addr];
        end
    end
    task run_fill(input integer p,xx,yy,ww,hh,cc,invalid);
        integer a, ox, oy, observed_error;
        begin
            @(negedge clk);
            page=p; x=xx; y=yy; width=ww; height=hh; color=cc; valid=1;
            @(negedge clk); valid=0;
            wait(done);
            observed_error=error;
            if(observed_error!=invalid) $fatal(1,"error status");
            if(!invalid) begin
                for(oy=yy;oy<yy+hh;oy=oy+1)
                    for(ox=xx;ox<xx+ww;ox=ox+1) begin
                        a=p*115200+oy*320+ox/2;
                        if(ox%2==0) reference_memory[a][7:4]=cc;
                        else reference_memory[a][3:0]=cc;
                    end
            end
            @(negedge clk);
            for(a=0;a<230400;a=a+1)
                if(memory[a]!==reference_memory[a])
                    $fatal(1,"pixel mismatch at byte %0d for %0d,%0d %0dx%0d",a,xx,yy,ww,hh);
        end
    endtask
    initial begin
        for(i=0;i<230400;i=i+1) begin
            memory[i]=(i*37+19)%256;
            reference_memory[i]=memory[i];
        end
        repeat(3) @(negedge clk);
        reset=0;
        run_fill(0,0,0,640,360,3,0);
        run_fill(1,639,359,1,1,15,0);
        for(j=0;j<2;j=j+1)
            for(k=1;k<6;k=k+1) run_fill(j,10+j,13,k,3,k,0);
        run_fill(0,0,0,0,4,0,0);
        run_fill(0,639,359,2,1,0,1);
        run_fill(0,65535,0,2,1,0,1);
        for(j=0;j<80;j=j+1) begin
            px=$urandom_range(0,620); py=$urandom_range(0,350);
            run_fill(j%2,px,py,$urandom_range(1,20),$urandom_range(1,10),j%16,0);
        end
        $display("PASS fb_fill: full pages, boundaries, odd edges, invalid ranges, 80 randomized rectangles, memory stalls");
        $finish;
    end
    initial begin #100000000; $fatal(1,"watchdog"); end
endmodule
