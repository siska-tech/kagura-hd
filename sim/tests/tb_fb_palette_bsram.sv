// SPDX-License-Identifier: Apache-2.0
// SPI scanout equivalence: the frozen scanout and the rtl/spi overlay (BSRAM
// palette, registered row flags)
// get the same line data and the same PRESENT sequence; RGB must match on
// every pixel clock. PRESENTs land at random points of the frame, including
// just before the vblank switch; the BSRAM copy adds 16 system cycles, so a
// request in the last microsecond before vblank may apply one frame later.
// Those frames are excluded and both must agree again on the following one.
`timescale 1ns/1ps
module tb_fb_palette_bsram #(parameter integer ROUNDS=20, parameter integer SEED=1);
    reg clk=0,pix_clk=0,reset=1;
    always #(500.0/54.0) clk=~clk;
    always #(500.0/74.25) pix_clk=~pix_clk;
    reg [10:0] cx=0;
    reg [9:0] cy=0;
    integer frames=0;
    always @(posedge pix_clk) begin
        if(reset) begin cx<=0; cy<=0; end
        else if(cx==1649) begin
            cx<=0;
            if(cy==749) begin cy<=0; frames<=frames+1; end else cy<=cy+1'b1;
        end else cx<=cx+1'b1;
    end
    reg present_page=0;
    reg [191:0] present_palette=192'hfff_eee_ddd_ccc_bbb_aaa_999_888_777_666_555_444_333_222_111_000;
    reg [1:0] present_valid=0;
    wire [1:0] present_ready,present_done,underrun,memory_error;
    wire [23:0] rgb[0:1];
    genvar d;
    generate for(d=0;d<2;d=d+1) begin: dut
        wire req_valid,scan_word_valid;
        wire [19:0] req_addr;
        wire [31:0] scan_word_data;
        reg busy=0,done_q=0;
        reg [19:0] addr_q;
        reg [4:0] count;
        // One 16-word read per request; data depends only on the address.
        always @(posedge clk) begin
            done_q<=0;
            if(reset) begin busy<=0; count<=0; end
            else if(!busy && req_valid) begin busy<=1; addr_q<=req_addr; count<=0; end
            else if(busy) begin
                if(count==16) begin busy<=0; done_q<=1; end
                else count<=count+1'b1;
            end
        end
        wire [31:0] mix=({12'd0,addr_q}+{27'd0,count})*32'h9e3779b1;
        assign scan_word_valid=busy && count<16;
        assign scan_word_data=mix^(mix>>15);
        // d=0: frozen rtl/fb scanout. d=1: rtl/spi overlay, which
        // tools/test-fb-spi.sh compiles as kagura_fb_scanout_spi.
        if(d==0) begin: frozen
            kagura_fb_scanout display(
                .sys_clk(clk),.sys_reset(reset),.pix_clk,.pix_reset(reset),.cx,.cy,
                .present_valid(present_valid[d]),.present_page,.present_palette,
                .present_ready(present_ready[d]),.present_done(present_done[d]),
                .req_valid,.req_ready(!busy),.req_addr,.rsp_done(done_q),.rsp_error(1'b0),
                .scan_word_valid,.scan_word_data,.rgb(rgb[d]),.underrun(underrun[d]),
                .memory_error(memory_error[d]),.generation_out());
        end else begin: overlay
            kagura_fb_scanout_spi display(
                .sys_clk(clk),.sys_reset(reset),.pix_clk,.pix_reset(reset),.cx,.cy,
                .present_valid(present_valid[d]),.present_page,.present_palette,
                .present_ready(present_ready[d]),.present_done(present_done[d]),
                .req_valid,.req_ready(!busy),.req_addr,.rsp_done(done_q),.rsp_error(1'b0),
                .scan_word_valid,.scan_word_data,.rgb(rgb[d]),.underrun(underrun[d]),
                .memory_error(memory_error[d]),.generation_out());
        end
    end endgenerate
    // The system side writes only the bank that is not on screen.
    always @(posedge clk)
        if(!reset && dut[1].overlay.display.pal_writing && dut[1].overlay.display.write_bank==dut[1].overlay.display.active_bank)
            $fatal(1,"palette write into the displayed bank");
    integer skip_until=-1, compared=0, lit=0, mismatches=0;
    always @(posedge pix_clk)
        if(!reset && frames>skip_until) begin
            compared<=compared+1;
            if(rgb[0]!=0) lit<=lit+1;
            if(rgb[0]!==rgb[1]) begin
                mismatches<=mismatches+1;
                if(mismatches<5) $display("MISMATCH frame=%0d cx=%0d cy=%0d reg=%h bsram=%h",frames,cx,cy,rgb[0],rgb[1]);
            end
        end
    integer done_frame[0:1];
    task automatic present(input bit near_vblank);
        integer target;
        begin
            if(near_vblank) begin
                // Last ~2 us before the switch at cx=1649, cy=719.
                target=1500+$urandom%140;
                wait(cy==719 && cx>=11'(target));
                skip_until=frames+1;
            end else begin
                target=40+$urandom%600;
                wait(cy==10'(target));
            end
            @(posedge clk);
            present_page<=$urandom%2;
            present_valid<=2'b11;
            fork
                begin wait(present_ready[0]); @(posedge clk); present_valid[0]<=0; end
                begin wait(present_ready[1]); @(posedge clk); present_valid[1]<=0; end
            join
            // Hold the palette until both PRESENTs complete (command contract).
            fork
                begin wait(present_done[0]); done_frame[0]=frames; end
                begin wait(present_done[1]); done_frame[1]=frames; end
            join
            if(!near_vblank && done_frame[0]!=done_frame[1])
                $fatal(1,"PRESENT completed in different frames %0d/%0d",done_frame[0],done_frame[1]);
            @(posedge clk);
            for(integer e=0;e<16;e++) present_palette[e*12+:12]<=12'($urandom);
        end
    endtask
    initial begin
        void'($urandom(SEED));
        repeat(20) @(posedge clk); reset=0;
        // First frames run on the boot palette contents: both must stay black.
        wait(frames==1);
        present(0);
        for(integer r=0;r<ROUNDS;r++) present(r%5==4);
        wait(frames>skip_until+1);
        if(mismatches!=0) $fatal(1,"%0d RGB mismatches",mismatches);
        if(lit<1000000) $fatal(1,"too few lit pixels compared: %0d",lit);
        if(underrun!=0 || memory_error!=0) $fatal(1,"underrun/memory error %b/%b",underrun,memory_error);
        $display("PASS: palette BSRAM equivalence rounds=%0d frames=%0d compared=%0d lit=%0d",ROUNDS,frames,compared,lit);
        $finish;
    end
endmodule
