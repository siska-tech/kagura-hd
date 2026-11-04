`timescale 1ns/1ps
module tb_fb_core;
    reg clk=0,pix_clk=0,fast=0,reset=1;
    always #(100.0/74.25) fast=~fast;
    always #(500.0/54.0) clk=~clk;
    always #(500.0/74.25) pix_clk=~pix_clk;
    wire [10:0] cx;
    wire [9:0] cy;
    integer frames=0,pixels=0,encoded_pixels=0;
    always @(posedge pix_clk) begin
        if(reset) frames<=0;
        else if(cx==1649 && cy==749) frames<=frames+1;
    end
    reg present_valid=0,present_page=0;
    reg [191:0] present_palette=0;
    wire present_ready,present_done,underrun,memory_error;
    wire [23:0] rgb;
    reg host_valid=0;
    wire host_ready,host_done,host_error,initialized,audio_overflow,audio_underflow;
    wire [511:0] host_rdata;
    wire [2:0] tmds;
    wire tmds_clock,wave_read,audio_ready,audio_done,audio_error;
    wire [8:0] wave_addr;
    reg signed [7:0] wave_data=0;
    reg audio_apply=0;
    reg [1:0] pcm_prepare=0;
    wire [7:0] pcm_status0,pcm_status1;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_core #(.INIT_CYCLES(64)) dut(
        .clk_system(clk),.clk_pixel(pix_clk),.clk_pixel_x5(fast),.reset,
        .host_valid,.host_write(1'b1),.host_addr(20'd61000),.host_words(5'd16),
        .host_wdata({64{8'h69}}),.host_mask(64'd0),.host_ready,.host_done,.host_error,.host_rdata,
        .present_valid,.present_page,.present_palette,.present_ready,.present_done,
        .cursor_req_valid(1'b0),.cursor_req_write(1'b0),.cursor_req_addr(5'd0),.cursor_req_wdata(8'd0),
        .cursor_req_ready(),.cursor_rsp_valid(),.cursor_rsp_error(),.cursor_rsp_data(),.cursor_irq(),
        .audio_apply,.audio_ready,.audio_done,.audio_error,.cfg_step({6{24'd153791}}),.cfg_duty(24'h808080),
        .cfg_gain_l({6{8'd4}}),.cfg_gain_r({6{8'd3}}),.cfg_enable(6'b111111),.cfg_phase_reset(6'b111111),
        .cfg_wave_len(8'h55),.cfg_master(8'd32),.cfg_noise_period(16'd3),
        .cfg_pcm_gain_l(16'h0408),.cfg_pcm_gain_r(16'h0804),.cfg_pcm_enable(2'b11),
        .pcm_prepare,.pcm_stop(2'b0),.pcm_clear(2'b0),
        .pcm_start({22'd240064,22'd240000}),.pcm_end({22'd240128,22'd240064}),
        .pcm_loop({22'd240064,22'd240000}),.pcm_loop_enable(2'b11),.pcm_status0,.pcm_status1,
        .wave_read,.wave_addr,.wave_data,.tmds,.tmds_clock,.initialized,
        .video_underrun(underrun),.memory_error,.audio_overflow,.audio_underflow,.cx,.cy,.rgb,
        .phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,.phy_dq_o_rise,.phy_dq_o_fall,
        .phy_rwds_oe,.phy_rwds_o_rise,.phy_rwds_o_fall,.phy_dq_tx,.phy_rwds_tx,.phy_dq_i_rise,.phy_dq_i_fall);
    kagura_hyperram_pair_model #(.BYTES(262144),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),.dq_f(phy_dq_o_fall),
        .mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),.read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    reg host_pending=0;
    always @(posedge clk) begin
        if(reset) begin host_valid<=0; host_pending<=0; end
        else begin
            if(wave_read) wave_data<=8'(int'(wave_addr[7:0])-128);
            if(!host_pending && !host_valid) host_valid<=1;
            if(host_valid && host_ready) begin host_valid<=0; host_pending<=1; end
            if(host_done) begin
                if(!host_pending || host_error) $fatal(1,"host response");
                host_pending<=0;
            end
        end
    end
    function automatic [3:0] pattern(input integer page,x,y);
        pattern=4'(page==0 ? x+y : x^y);
    endfunction
    integer expected_index;
    always @(negedge pix_clk) begin
        if(!reset && frames>=1 && frames<=2 && cx<1280 && cy<720) begin
            expected_index=int'(pattern(frames-1,int'(cx)/2,int'(cy)/2));
            if(frames==2) expected_index=15-expected_index;
            if(rgb!=={3{8'(expected_index*17)}})
                $fatal(1,"pixel frame %0d (%0d,%0d) got %h expected %h",frames,cx,cy,rgb,{3{8'(expected_index*17)}});
            pixels=pixels+1;
        end
        if(!reset && frames==3) begin
            if(pixels!=2*1280*720 || underrun || memory_error) $fatal(1,"frame/underrun status %0d",pixels);
            if(audio_overflow || audio_underflow || pcm_status0[5:2]!=0 || pcm_status1[5:2]!=0 ||
               !pcm_status0[1] || !pcm_status1[1] || received<2000 || pcm_checked<2000 || avis<2 || acrs<30 || encoded_pixels<1800000)
                $fatal(1,"audio/HDMI status received=%0d AVI=%0d ACR=%0d encoded=%0d status=%h/%h",received,avis,acrs,encoded_pixels,pcm_status0,pcm_status1);
            $display("PASS: fb_core %0d RGB pixels, %0d TMDS pixels, %0d decoded stereo samples, %0d ACR, %0d AVI, PCM2+PSG6+host writes",pixels,encoded_pixels,received,acrs,avis);
            $finish;
        end
    end
    task present(input integer page);
        begin
            wait(present_ready); @(negedge clk);
            present_page=1'(page);
            for(integer c=0;c<16;c=c+1) present_palette[c*12+:12]=12'((page==0 ? c : 15-c)*273);
            present_valid=1; @(negedge clk); present_valid=0;
        end
    endtask
    initial begin
        @(negedge clk);
        for(integer page=0;page<2;page=page+1)
            for(integer y=0;y<360;y=y+1)
                for(integer x=0;x<640;x=x+2)
                    model.memory[page*115200+y*320+x/2]={pattern(page,x,y),pattern(page,x+1,y)};
        for(integer i=0;i<64;i=i+1) begin
            model.memory[240000+i]=8'(i*3+8);
            model.memory[240064+i]=8'(127-i*5);
        end
        repeat(5) @(negedge clk); reset=0;
        present(0);
        wait(frames==1 && cy==100); present(1);
    end
    initial begin
        wait(!reset && initialized && dut.prefetch.cfg_ready==2'b11);
        @(negedge clk); pcm_prepare=2'b11;
        @(negedge clk); pcm_prepare=0;
        wait(pcm_status0[0] && pcm_status1[0] && audio_ready);
        @(negedge clk); audio_apply=1;
        @(negedge clk); audio_apply=0;
        wait(audio_done);
        if(audio_error) $fatal(1,"audio config");
    end

    localparam integer VIC=4;
    localparam [19:0] CTS=20'd74250;
    integer received=0,bit_index=0,j,acrs=0,avis=0,acr_samples=0;
    reg [31:0] h;
    reg [63:0] b[0:3];
    reg [3:0] nib[0:2];
    reg [8:0] packet_bits;
    reg [2:0] mode_d1,mode_d2,mode_d3,emitted_mode;
    always @(posedge pix_clk) begin
        mode_d1<=dut.hdmi.protocol.mode; mode_d2<=mode_d1; mode_d3<=mode_d2; emitted_mode<=mode_d3;
    end
    reg [31:0] audio_queue[0:8191];
    integer audio_write=0,audio_read=0;
    reg audio_started=0;
    reg [31:0] decoded_sample;
    always @(negedge clk) if(!reset && dut.sample_valid) begin
        audio_queue[audio_write]={dut.sample_right,dut.sample_left}; audio_write=audio_write+1;
    end
    function automatic [7:0] video_byte(input [9:0] symbol);
        reg [7:0] qm;
        begin
            qm=symbol[9] ? ~symbol[7:0] : symbol[7:0];
            video_byte[0]=qm[0];
            for(integer k=1;k<8;k=k+1) video_byte[k]=symbol[8] ? qm[k]^qm[k-1] : ~(qm[k]^qm[k-1]);
        end
    endfunction
    reg [10:0] delayed_x[0:5];
    reg [9:0] delayed_y[0:5];
    integer delayed_frame[0:5];
    always @(posedge pix_clk) begin
        delayed_x[0]<=cx; delayed_y[0]<=cy; delayed_frame[0]<=frames;
        for(integer k=1;k<6;k=k+1) begin
            delayed_x[k]<=delayed_x[k-1]; delayed_y[k]<=delayed_y[k-1]; delayed_frame[k]<=delayed_frame[k-1];
        end
    end
    integer encoded_index;
    always @(negedge pix_clk) begin
        if(!reset && delayed_frame[5]>=1 && delayed_frame[5]<=2 && delayed_x[5]<1280 && delayed_y[5]<720) begin
            encoded_index=int'(pattern(delayed_frame[5]-1,int'(delayed_x[5])/2,int'(delayed_y[5])/2));
            if(delayed_frame[5]==2) encoded_index=15-encoded_index;
            if(emitted_mode!=1) $fatal(1,"encoded video mode");
            for(integer lane=0;lane<3;lane=lane+1)
                if(video_byte(dut.hdmi.protocol.tmds_internal[lane])!==8'(encoded_index*17))
                    $fatal(1,"encoded RGB at %0d,%0d",delayed_x[5],delayed_y[5]);
            encoded_pixels=encoded_pixels+1;
        end
    end
    function automatic [3:0] decode(input reg [9:0] symbol);
        begin
            case(symbol)
                10'b1010011100:decode=0; 10'b1001100011:decode=1;
                10'b1011100100:decode=2; 10'b1011100010:decode=3;
                10'b0101110001:decode=4; 10'b0100011110:decode=5;
                10'b0110001110:decode=6; 10'b0100111100:decode=7;
                10'b1011001100:decode=8; 10'b0100111001:decode=9;
                10'b0110011100:decode=10;10'b1011000110:decode=11;
                10'b1010001110:decode=12;10'b1001110001:decode=13;
                10'b0101100011:decode=14;10'b1011000011:decode=15;
                default:begin $fatal(1,"invalid TERC4 symbol");decode=0;end
            endcase
        end
    endfunction
    always @(negedge pix_clk) begin
        // Check the packet-start edge against the protocol coordinates,
        // independently of the registered look-ahead implementation. This
        // catches a one-pixel shift even if complete packets still decode.
        if(!reset && dut.hdmi.protocol.true_hdmi_output.packet_enable !==
            (dut.hdmi.protocol.cx >= dut.hdmi.protocol.screen_width+14 &&
             dut.hdmi.protocol.cx < dut.hdmi.protocol.screen_width+14+
                 dut.hdmi.protocol.true_hdmi_output.num_packets_alongside*32 &&
             ((int'(dut.hdmi.protocol.cx)-int'(dut.hdmi.protocol.screen_width)-14)%32)==0))
            $fatal(1,"packet start shifted at cx=%0d",dut.hdmi.protocol.cx);
        if(reset) bit_index=0;
        else if(emitted_mode==3) begin
            for(j=0;j<3;j=j+1) nib[j]=decode(dut.hdmi.protocol.tmds_internal[j]);
            packet_bits={nib[2],nib[1],nib[0][2]};
            h[bit_index]=packet_bits[0];
            for(j=0;j<4;j=j+1) begin
                b[j][2*bit_index]=packet_bits[1+j];
                b[j][2*bit_index+1]=packet_bits[5+j];
            end
            if(bit_index==31) begin
                // ACR: PB1..3 CTS, PB4..6 N=6144 (bits 7:0 = PB0).
                if(h[7:0]==1) begin
                    for(j=0;j<4;j=j+1) if(b[j][55:0]!=={8'h00,8'h18,8'h00,CTS[7:0],CTS[15:8],4'h0,CTS[19:16],8'h00})
                        $fatal(1,"ACR N/CTS %014h",b[j][55:0]);
                    if(received>0) begin acrs=acrs+1; acr_samples=received; end
                end
                // AVI: PB4 is the VIC; PB2 aspect 16:9 only for VIC4.
                if(h[7:0]==8'h82) begin
                    if(b[0][38:32]!==7'(VIC) || b[0][21:20]!==(VIC==4 ? 2'b10 : 2'b00)) $fatal(1,"AVI VIC/aspect");
                    avis=avis+1;
                end
                if(h[7:0]==2) for(j=0;j<4;j=j+1) begin
                    if(b[j][7:0]!=0 || b[j][31:24]!=0) $fatal(1,"audio precision padding");
                    decoded_sample={b[j][47:32],b[j][23:8]};
                    if(!audio_started && decoded_sample==0) begin end
                    else begin
                        if(!audio_started) begin
                            while(audio_read<audio_write && audio_queue[audio_read]==0) audio_read=audio_read+1;
                            audio_started=1;
                        end
                        if(audio_read>=audio_write || decoded_sample!==audio_queue[audio_read])
                            $fatal(1,"audio transport mismatch %0d got %h expected %h",audio_read,decoded_sample,audio_queue[audio_read]);
                        audio_read=audio_read+1; received=received+1;
                    end
                end
                bit_index=0;
            end else bit_index=bit_index+1;
        end else if(bit_index!=0) $fatal(1,"truncated island packet");
    end
    integer pcm_checked=0;
    always @(posedge clk) if(!reset && dut.sample_boundary && dut.pf_active==2'b11) begin
        #1;
        if(dut.pcm0!==8'((pcm_checked%64)*3+8) || dut.pcm1!==8'(127-(pcm_checked%64)*5))
            $fatal(1,"PCM byte order/loop %0d",pcm_checked);
        pcm_checked=pcm_checked+1;
    end
    initial begin #60000000; $fatal(1,"watchdog"); end
endmodule
