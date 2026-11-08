`timescale 1ns/1ps
// Exercise commits close to vblank/control-sync qualification, without waiting
// a frame between cases. Compare the application and acknowledgement edges.
module tb_fb_cursor_mailbox_pipeline;
    reg sys_clk=0,pix_clk=0,sys_reset=1,pix_reset=1;
    always #(500.0/54.0) sys_clk=~sys_clk;
    always #(500.0/74.25) pix_clk=~pix_clk;
    reg req_valid=0,req_write=1;
    reg [4:0] req_addr=0;
    reg [7:0] req_wdata=0;
    reg [10:0] cx=0;
    reg [9:0] cy=0;
    wire [23:0] background=24'h123456,rgb_out,ref_rgb;
    wire req_ready,rsp_valid,rsp_error,irq,ref_ready,ref_valid,ref_error,ref_irq;
    wire [7:0] rsp_data,ref_data;
    kagura_fb_cursor #(.PIPELINE_MAILBOX(1)) dut(.*);
    kagura_fb_cursor_reference reference_cursor(
        .sys_clk,.sys_reset,.pix_clk,.pix_reset,.req_valid,.req_write,.req_addr,.req_wdata,
        .req_ready(ref_ready),.rsp_valid(ref_valid),.rsp_error(ref_error),.rsp_data(ref_data),.irq(ref_irq),
        .cx,.cy,.background,.rgb_out(ref_rgb));
    always @(negedge sys_clk) if(!sys_reset)
        if({req_ready,rsp_valid,rsp_error,rsp_data,irq,dut.generation,dut.pending,dut.queued_valid} !==
           {ref_ready,ref_valid,ref_error,ref_data,ref_irq,reference_cursor.generation,reference_cursor.pending,reference_cursor.queued_valid})
            $fatal(1,"mailbox SYS cycle mismatch");
    always @(negedge pix_clk) if(!pix_reset)
        if({dut.position_x,dut.position_y,dut.active_bank,dut.visible,dut.pixel_colors,dut.ack,dut.seen,rgb_out} !==
           {reference_cursor.position_x,reference_cursor.position_y,reference_cursor.active_bank,reference_cursor.visible,
            reference_cursor.pixel_colors,reference_cursor.ack,reference_cursor.seen,ref_rgb})
            $fatal(1,"mailbox PIX application mismatch");
    task wr(input integer address,data);
        @(negedge sys_clk);req_valid=1;req_addr=5'(address);req_wdata=8'(data);
        do @(posedge sys_clk);while(!req_ready);
        @(negedge sys_clk);req_valid=0;
        while(!rsp_valid) @(negedge sys_clk);
        if(rsp_error) $fatal(1,"unexpected CSR error %0d",address);
    endtask
    task blank;
        @(negedge pix_clk);cx=1649;cy=719;
        @(negedge pix_clk);cx=0;cy=720;
    endtask
    integer x,y,delay_edges,bank,color;
    reg old_toggle;
    initial begin
        repeat(5) @(negedge sys_clk);sys_reset=0;pix_reset=0;
        for(integer i=0;i<100;i++) begin
            x=(i*73)%2048-1024;y=(i*37)%2048-1024;delay_edges=i%5;bank=(i+1)%2;
            old_toggle=dut.request_toggle;
            fork
                begin
                    wr(15,bank);wr(0,bank*2);
                    for(integer c=0;c<3;c++) begin
                        color=(i*137+c*911)&4095;wr(7+c*2,color&255);wr(8+c*2,color>>8);
                    end
                    wr(1,x&255);wr(2,(x>>8)&255);
                    wr(3,y&255);wr(4,(y>>8)&255);wr(17,1);
                end
                begin
                    wait(dut.request_toggle!=old_toggle);
                    repeat(delay_edges) @(posedge pix_clk);
                    blank(); // Can precede request_sync qualification.
                    repeat(5) @(posedge pix_clk);blank();
                end
            join
            wait(!dut.pending && !dut.queued_valid);
            @(negedge sys_clk);
            if(dut.generation!==16'(i+1) || dut.position_x!==12'(x) || dut.position_y!==12'(y))
                $fatal(1,"mailbox coordinate/generation case=%0d",i);
        end
        $display("PASS: cursor mailbox pipeline, 100 near-vblank commits, signed coordinates, colors/bank swaps, exact application/ack cycles");
        $finish;
    end
    initial begin #1000000;$fatal(1,"mailbox pipeline timeout");end
endmodule
