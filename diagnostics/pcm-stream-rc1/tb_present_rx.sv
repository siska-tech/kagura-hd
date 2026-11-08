// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_present_rx #(parameter bit CHECK_GENERATION=0);
    reg sys_clk=0, pix_clk=0;
    always #9.259 sys_clk=~sys_clk;
    always #6.734 pix_clk=~pix_clk;
    reg sys_reset=1, pix_reset=1;
    reg [10:0] cx=0;
    reg [9:0] cy=0;
    reg present_valid=0, present_page=0;
    reg [191:0] present_palette=0;
    wire present_ready, present_done;
    kagura_fb_scanout dut(
        .sys_clk,.sys_reset,.pix_clk,.pix_reset,.cx,.cy,
        .present_valid,.present_page,.present_palette,.present_ready,.present_done,
        .req_valid(),.req_ready(1'b0),.req_addr(),.rsp_done(1'b0),.rsp_error(1'b0),
        .scan_word_valid(1'b0),.scan_word_data(32'd0),
        .rgb(),.underrun(),.memory_error(),.generation_out());

    wire [191:0] visible_palette;
`ifdef KAGURA_TEST_PALETTE_RAM
    for(genvar color=0;color<16;color++) begin: palette_oracle
        assign visible_palette[color*12+:12]=dut.palette_valid ?
            dut.palette_memory[{dut.present_seen,4'(color)}] : 12'd0;
    end
    always @(posedge sys_clk)
        if(!sys_reset && dut.palette_loading && dut.palette_valid &&
           dut.palette_write_addr[4]==dut.present_seen)
            $fatal(1,"palette write overlaps displayed bank");
`else
    assign visible_palette=dut.palette;
`endif

    task automatic submit(input bit page, input logic [191:0] colors);
        wait(present_ready);
        @(negedge sys_clk);
        present_page=page;
        present_palette=colors;
        present_valid=1;
        @(posedge sys_clk);
        #1ps;
        if(present_ready || present_done) $fatal(1,"PRESENT did not enter pending");
        present_valid=0;
        present_palette=~colors;
        present_page=~page;
    endtask

    task automatic flip_at_first_eligible_edge(
        input bit page, input logic [191:0] colors,
        input bit old_page, input logic [191:0] old_colors,
        input bit expect_line
    );
        wait(dut.present_sync[0]!=dut.present_seen);
        @(negedge pix_clk);
        if(dut.present_sync[1]!=dut.present_seen) $fatal(1,"missed REQ boundary");
        cx=1649; cy=719;
        @(negedge pix_clk);
        cx=0; cy=0;
        if(dut.active_page!==old_page || visible_palette!==old_colors || present_done)
            $fatal(1,"PRESENT applied before vblank");
        @(negedge pix_clk);
        if(expect_line && dut.line_generation!==dut.generation)
            $fatal(1,"first line uses wrong generation");
        if(dut.active_page!==page || visible_palette!==colors ||
           dut.present_ack!==dut.present_seen)
            $fatal(1,"PRESENT did not apply atomically at first eligible vblank");
        if(expect_line && dut.line_page!==page)
            $fatal(1,"first line uses wrong page");
        wait(present_done);
        if(!present_ready) $fatal(1,"ACK did not reopen mailbox");
    endtask

    localparam logic [191:0] COLORS=192'h123456789abcdef_fedcba9876543210_aa5500ffdeadbeef;
    task automatic check_generation_wrap;
        logic [15:0] expected;
        expected=dut.generation;
        @(negedge pix_clk);
        // Stress consecutive increments as well as gaps around byte carries.
        for(int n=0;n<66000;n++) begin
            cx=(n%257==255) ? 0 : 1649;
            cy=719;
            @(posedge pix_clk);
            if(dut.vblank) expected=expected+16'd1;
            @(negedge pix_clk);
            if(dut.generation!==expected)
                $fatal(1,"generation mismatch at step %0d",n);
        end
        $display("PASS: generation low-byte carries and 16-bit wrap");
    endtask
    initial begin
        repeat(4) @(negedge sys_clk);
        sys_reset=0; pix_reset=0;
        submit(1,COLORS);
        flip_at_first_eligible_edge(1,COLORS,0,0,1);
        submit(0,~COLORS);
        flip_at_first_eligible_edge(0,~COLORS,1,COLORS,0);
        submit(1,COLORS);
        @(negedge sys_clk);
        sys_reset=1; pix_reset=1;
        repeat(4) @(negedge sys_clk);
        if(visible_palette!==192'd0 || dut.active_page!==1'b0 || present_done)
            $fatal(1,"reset did not discard pending PRESENT");
        sys_reset=0; pix_reset=0;
        submit(1,~COLORS);
        flip_at_first_eligible_edge(1,~COLORS,0,0,1);
        if(CHECK_GENERATION) check_generation_wrap();
        $display("PASS: first eligible vblank, held payload, page/palette atomicity, first line and reset");
        $finish;
    end
    initial begin #(CHECK_GENERATION ? 1000000 : 10000); $fatal(1,"PRESENT watchdog"); end
endmodule
