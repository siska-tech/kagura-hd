`timescale 1ns/1ps
module tb_fb_host #(parameter integer LANES=1, QUEUE_DEPTH=1, parameter bit REGISTER_AUDIO_CREDITS=0, REPLICATE_PACKET_FIRST=0);
    reg clk=0,pix_clk=0,fast=0,reset=1;
    always #(500.0/54.0) clk=~clk;
    always #(500.0/74.25) pix_clk=~pix_clk;
    always #(100.0/74.25) fast=~fast;
    reg sck=0,cs_n=1;
    reg [3:0] drive=0,drive_enable=0;
    tri [3:0] host_io;
    genvar pin;
    generate for(pin=0;pin<4;pin=pin+1) begin: bus_pin
        assign host_io[pin]=drive_enable[pin] ? drive[pin] : 1'bz;
    end endgenerate
    wire busy,gpio_ready,irq_n;
    wire host_valid,host_write,mem_ready,mem_done,mem_error;
    wire [19:0] host_addr;
    wire [4:0] host_words;
    wire [511:0] host_wdata,mem_rdata;
    wire [63:0] host_mask;
    wire present_valid,present_page,present_ready,present_done;
    wire [191:0] present_palette;
    wire initialized,video_underrun,memory_error,audio_overflow,audio_underflow;
    wire [10:0] cx;
    wire [9:0] cy;
    wire [23:0] rgb;
    kagura_fb_host #(.LANES(LANES),.QUEUE_DEPTH(QUEUE_DEPTH)) endpoint(
        .clk,.reset,.enabled(initialized),.video_error(video_underrun || memory_error),
        .audio_error(audio_overflow || audio_underflow),.host_sck(sck),.host_cs_n(cs_n),.host_io,
        .host_busy(busy),.host_ready(gpio_ready),.host_irq_n(irq_n),.host_valid,.mem_ready,.host_write,
        .host_addr,.host_words,.host_wdata,.host_mask,.mem_done,.mem_error,.mem_rdata,
        .present_valid,.present_page,.present_palette,.present_ready,.present_done,
        .cursor_req_valid,.cursor_req_write,.cursor_req_addr,.cursor_req_wdata,.cursor_req_ready,.cursor_rsp_valid,.cursor_rsp_error,.cursor_rsp_data,.cursor_irq);
    wire cursor_req_valid,cursor_req_write,cursor_req_ready,cursor_rsp_valid,cursor_rsp_error,cursor_irq;
    wire [4:0] cursor_req_addr;
    wire [7:0] cursor_req_wdata,cursor_rsp_data;
    reg audio_apply=0;
    reg [1:0] pcm_prepare=0;
    wire audio_ready,audio_done;
    wire [7:0] pcm_status0,pcm_status1;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe,phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_core #(.INIT_CYCLES(64),.AUDIO_REGISTER_TICK(LANES==4),.CURSOR_PIPELINE_MAILBOX(QUEUE_DEPTH>1),.AUDIO_REGISTER_CREDITS(QUEUE_DEPTH>1 && REGISTER_AUDIO_CREDITS),.PACKET_REPLICATE_FIRST(QUEUE_DEPTH>1 && REPLICATE_PACKET_FIRST)) core(
        .clk_system(clk),.clk_pixel(pix_clk),.clk_pixel_x5(fast),.reset,
        .host_valid,.host_write,.host_addr,.host_words,.host_wdata,.host_mask,.host_ready(mem_ready),
        .host_done(mem_done),.host_error(mem_error),.host_rdata(mem_rdata),
        .present_valid,.present_page,.present_palette,.present_ready,.present_done,
        .cursor_req_valid,.cursor_req_write,.cursor_req_addr,.cursor_req_wdata,.cursor_req_ready,.cursor_rsp_valid,.cursor_rsp_error,.cursor_rsp_data,.cursor_irq,
        .audio_apply,.audio_ready,.audio_done,.audio_error(),.cfg_step({6{24'd153791}}),.cfg_duty(24'h808080),
        .cfg_gain_l({6{8'd4}}),.cfg_gain_r({6{8'd3}}),.cfg_enable(6'b111111),.cfg_phase_reset(6'b111111),.cfg_wave_len(8'h55),
        .cfg_master(8'd32),.cfg_noise_period(16'd3),.cfg_pcm_gain_l(16'h0408),.cfg_pcm_gain_r(16'h0804),.cfg_pcm_enable(2'b11),
        .pcm_prepare,.pcm_stop(2'd0),.pcm_clear(2'd0),.pcm_start({22'd240192,22'd240128}),.pcm_end({22'd240256,22'd240192}),.pcm_loop({22'd240192,22'd240128}),
        .pcm_loop_enable(2'b11),.pcm_status0,.pcm_status1,.wave_read(),.wave_addr(),.wave_data(8'sd7),
        .tmds(),.tmds_clock(),.initialized,.video_underrun,.memory_error,.audio_overflow,.audio_underflow,
        .cx,.cy,.rgb,.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,.phy_dq_o_rise,.phy_dq_o_fall,
        .phy_rwds_oe,.phy_rwds_o_rise,.phy_rwds_o_fall,.phy_dq_tx,.phy_rwds_tx,.phy_dq_i_rise,.phy_dq_i_fall);
    kagura_hyperram_pair_model #(.BYTES(262144),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),.dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),
        .dq_r(phy_dq_o_rise),.dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
        .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    always @* if((drive_enable & endpoint.io_oe)!=0) $fatal(1,"SPI IO contention");
    task byte_transfer(input [7:0] tx,output [7:0] rx);
        reg [3:0] sampled;
        begin
            rx=0;
            for(integer i=0;i<8/LANES;i=i+1) begin
                drive=LANES==1 ? {3'd0,tx[7-i]} : tx[7-i*4-:4];
                #500; sck=1; sampled=host_io;
                if(LANES==1) rx[7-i]=sampled[1]; else rx[7-i*4-:4]=sampled;
                #500; sck=0;
            end
        end
    endtask
    reg [7:0] txbuf[0:63],rxbuf[0:63];
    task write_registers(input [5:0] address,input bit increment,input integer length);
        reg [7:0] ignored;
        begin
            cs_n=0; drive_enable=LANES==1 ? 4'b0001 : 4'b1111; #300;
            byte_transfer({1'b0,increment,address},ignored);
            for(integer i=0;i<length;i=i+1) byte_transfer(txbuf[i],ignored);
            #100; cs_n=1; drive_enable=0; #300;
        end
    endtask
    task read_registers(input [5:0] address,input bit increment,input integer length);
        reg [7:0] ignored;
        begin
            cs_n=0; drive_enable=LANES==1 ? 4'b0001 : 4'b1111; #300;
            byte_transfer({1'b1,increment,address},ignored);
            byte_transfer(8'(length),ignored);
            if(LANES==4) drive_enable=0;
            byte_transfer(0,ignored);
            for(integer i=0;i<length;i=i+1) byte_transfer(0,rxbuf[i]);
            #100; cs_n=1; drive_enable=0; #300;
        end
    endtask
    task write_one(input [5:0] address,input [7:0] value);
        begin txbuf[0]=value; write_registers(address,0,1); end
    endtask
    task wait_tag(input [15:0] tag,input [7:0] expected_error);
        integer count;
        begin
            count=0;
            read_registers(27,0,1);
            while((QUEUE_DEPTH==1 && rxbuf[0][0]) || !rxbuf[0][4]) begin
                if(count>4000) $fatal(1,"command timeout tag=%h status=%h",tag,rxbuf[0]);
                read_registers(27,0,1); count=count+1;
            end
            read_registers(28,1,3);
            if({rxbuf[1],rxbuf[0]}!==tag || rxbuf[2]!==expected_error) $fatal(1,"completion tag/error");
        end
    endtask
    task stage_command(input [127:0] descriptor);
        begin
            for(integer i=0;i<16;i=i+1) txbuf[i]=descriptor[i*8+:8];
            write_registers(8,1,16); write_one(26,1);
        end
    endtask
    integer sys_cycles=0,line_start=0,max_blit_line=0,blit_lines=0,pcm_checked=0,blit_pcm=0,blit_start_cycle=0,blit_completion_cycles=0;
    reg testing_blit=0;
    always @(posedge clk) begin
        sys_cycles<=sys_cycles+1;
        if(!reset && endpoint.cmd_valid && endpoint.cmd_ready && endpoint.command[7:0]==6) blit_start_cycle<=sys_cycles;
        if(!reset && endpoint.cmd_done && endpoint.command[7:0]==6) blit_completion_cycles<=sys_cycles-blit_start_cycle;
        if(!reset && core.display.fetch_start) line_start<=sys_cycles;
        if(!reset && core.display.fetch_done && testing_blit) begin
            if(sys_cycles-line_start>1920 || core.display.fetch_error) $fatal(1,"BLIT missed line deadline");
            if(sys_cycles-line_start>max_blit_line) max_blit_line<=sys_cycles-line_start;
            blit_lines<=blit_lines+1;
        end
    end
    always @(posedge clk) if(!reset && core.sample_boundary && core.pf_active==2'b11) begin
        #1;
        if(core.pcm0!==8'((pcm_checked%64)*3+8) || core.pcm1!==8'(127-(pcm_checked%64)*5))
            $fatal(1,"BLIT PCM byte order/loop %0d",pcm_checked);
        pcm_checked=pcm_checked+1;
        if(testing_blit) blit_pcm=blit_pcm+1;
    end
    reg [127:0] descriptor;
    task queue_test;
        integer first_cycle,last_accept_cycle;
        begin
            for(integer round_id=0;round_id<2;round_id++) begin
                descriptor=0;descriptor[7:0]=1;descriptor[15:8]=1;
                descriptor[31:16]=16'(256+round_id*QUEUE_DEPTH);
                descriptor[79:64]=640;descriptor[95:80]=360;descriptor[103:96]=6;
                first_cycle=sys_cycles;stage_command(descriptor);
                for(integer i=1;i<QUEUE_DEPTH;i++) begin
                    descriptor[31:16]=16'(256+round_id*QUEUE_DEPTH+i);
                    descriptor[79:64]=8;descriptor[95:80]=1;descriptor[103:96]=8'(i);
                    stage_command(descriptor);
                end
                last_accept_cycle=sys_cycles;
                if(endpoint.registers.queue_count!=QUEUE_DEPTH || !busy)
                    $fatal(1,"physical transport did not fill queue before first completion");
                write_one(26,1);
                read_registers(7,0,1);if(rxbuf[0]!=1) $fatal(1,"queue overflow error");
                write_one(7,0);
                for(integer i=0;i<QUEUE_DEPTH;i++) begin
                    wait_tag(16'(256+round_id*QUEUE_DEPTH+i),0);
                    // Completion must survive several physical transactions until ACK.
                    read_registers(28,1,3);
                    if({rxbuf[1],rxbuf[0]}!==16'(256+round_id*QUEUE_DEPTH+i))
                        $fatal(1,"queued completion overwritten");
                    write_one(31,1);
                end
                for(integer i=115200;i<230400;i++) begin
                    if(model.memory[i] !== (i<115204 ? {2{4'(QUEUE_DEPTH-1)}} : 8'h66))
                        $fatal(1,"queued fill pixel/order address=%0d",i);
                end
                $display("QUEUE transport LANES=%0d depth=%0d round=%0d accept=%0d drain=%0d cycles",
                    LANES,QUEUE_DEPTH,round_id,last_accept_cycle-first_cycle,sys_cycles-first_cycle);
            end
            // Shared-window operations after drain, with explicit completion ACK.
            write_one(25,0);
            for(integer i=0;i<64;i++) txbuf[i]=8'(i*7+3);
            write_registers(24,0,64);
            descriptor=0;descriptor[7:0]=4;descriptor[15:8]=16;
            descriptor[31:16]=512;descriptor[63:32]=240000;
            stage_command(descriptor);wait_tag(512,0);write_one(31,1);
            descriptor[7:0]=5;descriptor[31:16]=513;
            stage_command(descriptor);wait_tag(513,0);
            read_registers(24,0,64);
            for(integer i=0;i<64;i++) if(rxbuf[i]!==8'(i*7+3)) $fatal(1,"queued READ byte=%0d",i);
            write_one(31,1);
            descriptor=0;descriptor[7:0]=3;descriptor[15:8]=1;descriptor[31:16]=514;
            stage_command(descriptor);wait_tag(514,0);write_one(31,1);
            wait(cy==0 && cx==100);
            if(rgb!==24'h666666) $fatal(1,"queued page did not reach scanout");
            // COPY consumes a fresh shared-window capture for every burst.
            // Copy the now-displayed page into the back page, then switch back
            // to FILL: stale per-lane selects must not leak either payload.
            descriptor=0;descriptor[7:0]=6;descriptor[15:8]=1;descriptor[31:16]=515;
            descriptor[111:96]=640;descriptor[127:112]=4;
            stage_command(descriptor);wait_tag(515,0);write_one(31,1);
            for(integer i=0;i<1280;i++)
                if(model.memory[i]!==model.memory[115200+i]) $fatal(1,"queued COPY window byte=%0d",i);
            descriptor=0;descriptor[7:0]=1;descriptor[31:16]=516;
            descriptor[79:64]=8;descriptor[95:80]=1;descriptor[103:96]=15;
            stage_command(descriptor);wait_tag(516,0);write_one(31,1);
            for(integer i=0;i<1280;i++)
                if(model.memory[i] !== (i<4 ? 8'hff : model.memory[115200+i]))
                    $fatal(1,"queued COPY to FILL payload byte=%0d",i);
            if(endpoint.late || memory_error || audio_overflow || audio_underflow)
                $fatal(1,"queued host/core error");
            $display("PASS: queued fb_host LANES=%0d depth=%0d physical transport, ordered pixels, READ, PRESENT, COPY and payload switching",LANES,QUEUE_DEPTH);
            $finish;
        end
    endtask
    initial begin
        @(negedge clk);
        for(integer i=0;i<64;i=i+1) begin
            model.memory[240128+i]=8'(i*3+8);model.memory[240192+i]=8'(127-i*5);
        end
        repeat(5) @(negedge clk); reset=0; wait(gpio_ready);
        if(QUEUE_DEPTH>1) queue_test();
        read_registers(0,1,7);
        if({rxbuf[3],rxbuf[2],rxbuf[1],rxbuf[0]}!==32'h3142464b || rxbuf[4]!=1 || rxbuf[5]!=2 || rxbuf[6]!=127)
            $fatal(1,"FB identity/capabilities");
        // Cursor RAM/metadata use a separate CSR window, outside GPU staging.
        write_one(46,0); write_one(47,1);
        write_one(37,0); write_one(38,0); write_one(39,8'hff); write_one(40,8'h0f);
        for(integer block_id=0;block_id<4;block_id=block_id+1) begin
            for(integer i=0;i<64;i=i+1) txbuf[i]=8'h55;
            write_registers(48,0,64);
        end
        // Full back-page fill. A second submit while executing must be rejected.
        descriptor=0; descriptor[7:0]=1; descriptor[15:8]=1; descriptor[31:16]=16'h1234;
        descriptor[79:64]=640; descriptor[95:80]=360; descriptor[103:96]=6;
        stage_command(descriptor); write_one(26,1);
        // A queued cursor position must be accepted while a full GPU fill is busy.
        write_one(32,3); write_one(33,10); write_one(34,0); write_one(35,10); write_one(36,0); write_one(49,1);
        read_registers(27,0,1); if(!rxbuf[0][0]) $fatal(1,"cursor test missed busy fill");
        read_registers(50,0,1); if(!rxbuf[0][0]) $fatal(1,"cursor commit blocked by GPU busy");
        read_registers(53,0,1); if(rxbuf[0]!=0) $fatal(1,"cursor upload/commit error");
        read_registers(8,1,16);
        for(integer i=0;i<16;i=i+1) if(rxbuf[i]!==descriptor[i*8+:8]) $fatal(1,"staging readback");
        wait_tag(16'h1234,0);
        read_registers(7,0,1); if(rxbuf[0]!=1) $fatal(1,"busy collision not reported");
        for(integer i=115200;i<230400;i=i+1) if(model.memory[i]!==8'h66) $fatal(1,"full fill pixel");
        if(!endpoint.irq) $fatal(1,"completion IRQ");
        write_one(7,0); write_one(31,1);
        // Odd nibble, word and row boundaries.
        descriptor=0; descriptor[7:0]=1; descriptor[15:8]=1; descriptor[31:16]=16'h1235;
        descriptor[47:32]=1; descriptor[63:48]=1; descriptor[79:64]=7; descriptor[95:80]=2; descriptor[103:96]=10;
        stage_command(descriptor); wait_tag(16'h1235,0);
        if(model.memory[115520]!==8'h6a || model.memory[115521]!==8'haa || model.memory[115523]!==8'haa || model.memory[115524]!==8'h66)
            $fatal(1,"odd rectangle");
        // Upload 64 bytes and transfer it back through the result window.
        write_one(25,0);
        for(integer i=0;i<64;i=i+1) txbuf[i]=8'(i*7+3);
        write_registers(24,0,64);
        descriptor=0; descriptor[7:0]=4; descriptor[15:8]=16; descriptor[31:16]=16'h1236; descriptor[63:32]=240000;
        stage_command(descriptor); wait_tag(16'h1236,0);
        descriptor[7:0]=5; descriptor[31:16]=16'h1237;
        stage_command(descriptor); wait_tag(16'h1237,0);
        read_registers(24,0,64);
        for(integer i=0;i<64;i=i+1) if(rxbuf[i]!==8'(i*7+3)) $fatal(1,"readback window %0d",i);
        // Invalid ranges leave memory unchanged and complete with an error tag.
        descriptor=0; descriptor[7:0]=1; descriptor[15:8]=1; descriptor[31:16]=16'h1238;
        descriptor[47:32]=639; descriptor[79:64]=2; descriptor[95:80]=1;
        stage_command(descriptor); wait_tag(16'h1238,3); write_one(7,0);
        // Palette shadow is invisible until page presentation reaches vblank.
        descriptor=0; descriptor[7:0]=2; descriptor[15:8]=6; descriptor[31:16]=16'h1239; descriptor[43:32]=12'hf20;
        stage_command(descriptor); wait_tag(16'h1239,0);
        descriptor=0; descriptor[7:0]=3; descriptor[15:8]=1; descriptor[31:16]=16'h123a;
        stage_command(descriptor); wait_tag(16'h123a,0);
        wait(cy==0 && cx==100);
        if(rgb!==24'hff2200) $fatal(1,"present did not reach scanout");
        wait(cy==22 && cx==23); @(negedge pix_clk);
        if(core.hdmi_rgb!==24'hffffff) $fatal(1,"cursor did not reach HDMI RGB");
        read_registers(50,0,1); if(rxbuf[0][0] || !rxbuf[0][1] || !rxbuf[0][2]) $fatal(1,"cursor completion state");
        // Masked write and readback while scanout is actively using memory.
        write_one(25,0);
        txbuf[0]=8'h11; txbuf[1]=8'h22; txbuf[2]=8'h33; txbuf[3]=8'h44;
        write_registers(24,0,4);
        descriptor=0; descriptor[7:0]=4; descriptor[15:8]=1; descriptor[31:16]=16'h123b;
        descriptor[63:32]=240000; descriptor[127:64]=64'hfffffffffffffff9;
        stage_command(descriptor); wait_tag(16'h123b,0);
        descriptor=0; descriptor[7:0]=5; descriptor[15:8]=16; descriptor[31:16]=16'h123c; descriptor[63:32]=240000;
        stage_command(descriptor); wait_tag(16'h123c,0);
        read_registers(24,0,64);
        for(integer i=0;i<64;i=i+1)
            if(rxbuf[i] !== (i==1 ? 8'h22 : i==2 ? 8'h33 : 8'(i*7+3))) $fatal(1,"masked readback during scanout");
        // Real CSR result-window reuse while scanout and both PCM loops run.
        testing_blit=1;
        descriptor=0;descriptor[7:0]=6;descriptor[15:8]=1;descriptor[31:16]=16'h123d;
        descriptor[111:96]=640;descriptor[127:112]=360;
        stage_command(descriptor);
        write_one(33,11);write_one(49,1);
        read_registers(27,0,1);if(!rxbuf[0][0]) $fatal(1,"cursor test missed busy BLIT");
        read_registers(53,0,1);if(rxbuf[0]!=0) $fatal(1,"cursor blocked by BLIT");
        wait_tag(16'h123d,0);testing_blit=0;
        for(integer i=0;i<115200;i=i+1)
            if(model.memory[i]!==model.memory[115200+i]) $fatal(1,"BLIT window reuse pixel %0d",i);
        if(blit_lines<50 || blit_pcm<100) $fatal(1,"insufficient BLIT/display/PCM overlap");
        $display("BLIT contention LANES=%0d: lines=%0d max=%0d sys cycles, ordered PCM=%0d, copy=%0d sys cycles",LANES,blit_lines,max_blit_line,blit_pcm,blit_completion_cycles);
        if(endpoint.late || memory_error || audio_overflow || audio_underflow || !pcm_status0[1] || !pcm_status1[1] || pcm_status0[5:2]!=0 || pcm_status1[5:2]!=0) $fatal(1,"host/core error");
        $display("PASS: fb_host LANES=%0d physical protocol -> tagged commands -> PSRAM -> displayed pixels",LANES);
        $finish;
    end
    initial begin
        wait(!reset && initialized);
        @(negedge clk); pcm_prepare=2'b11;
        @(negedge clk); pcm_prepare=0;
        wait(pcm_status0[0] && pcm_status1[0] && audio_ready);
        @(negedge clk); audio_apply=1;
        @(negedge clk); audio_apply=0;
    end
    initial begin #60000000; $fatal(1,"watchdog"); end
endmodule
module tb_fb_host_spi; tb_fb_host #(.LANES(1)) test(); endmodule
module tb_fb_host_qspi; tb_fb_host #(.LANES(4)) test(); endmodule
