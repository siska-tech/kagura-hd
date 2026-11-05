`timescale 1ns/1ps
module tb_psram_probe #(parameter integer WORDS=1,WRAP=0,FAULT=0);
    reg clk=0,reset=1,start=0;
    always #5 clk=~clk;
    wire valid,write,ready,done,error,initialized;
    wire [19:0] addr;
    wire [4:0] words;
    wire [511:0] wdata,rdata;
    wire [63:0] mask;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    wire controller_valid=FAULT==1 ? 1'b0 : valid;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(64)) controller(.valid(controller_valid),.*);
    generate if(WRAP) begin
        kagura_psram_wrap_pair_model #(.BYTES(300160),.ALLOW_UNDOCUMENTED_CA45(1)) memory(
            .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
            .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
            .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
            .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    end else begin
        kagura_hyperram_pair_model #(.BYTES(300160),.MAX_WORDS(16)) memory(
            .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
            .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
            .dq_f(phy_dq_o_fall),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
            .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    end endgenerate
    wire tx_valid,tx_ready,finished,failed,armed,uart_tx;
    wire [7:0] tx_data;
    // Fault 1 withholds ready, fault 2 returns a controller error on completion.
    psram_probe_engine #(.WORDS(WORDS),.TIMEOUT(300)) engine(
        .clk,.reset,.start,.initialized,.valid,.write,.addr,.words,.wdata,.mask,
        .ready(FAULT==1 ? 1'b0 : ready),.done,.error(FAULT==2 ? done : error),.rdata,
        .tx_valid,.tx_ready,.tx_data,.finished,.failed,.armed);
    psram_probe_uart #(.DIV(4)) uart(.clk,.reset,.valid(tx_valid),.data(tx_data),.ready(tx_ready),.tx(uart_tx));
    // Decode actual 8N1 wire, not the internal valid/ready bus.
    reg [7:0] packet[0:148];
    integer count=0,requests=0;
    reg [7:0] byte_value;
    always @(posedge clk) if(controller_valid && ready) requests<=requests+1;
    initial forever begin
        @(negedge uart_tx);#60;
        for(integer bit_index=0;bit_index<8;bit_index++) begin
            byte_value[bit_index]=uart_tx;#40;
        end
        if(!uart_tx) $fatal(1,"UART stop bit");
        if(count>=149) $fatal(1,"extra packet/retry");
        packet[count]=byte_value;count++;
    end
    reg [7:0] checksum=0;
    integer expected_result,capture_file;
    initial begin
        repeat(3) @(negedge clk);reset=0;wait(armed);
        repeat(20) @(negedge clk);
        if(requests!=0 || count!=0) $fatal(1,"memory test before trigger");
        start=1;@(negedge clk);start=0;
        wait(count==149);wait(tx_ready);repeat(10) @(negedge clk);
        if(!finished) $fatal(1,"not frozen");
        expected_result=FAULT==1 ? 3 : FAULT==2 ? 2 : WRAP && WORDS==16 ? 1 : 0;
        if(packet[0]!="P" || packet[1]!="D" || packet[2]!="R" || packet[3]!="1" ||
           packet[4]!=8'(expected_result) || packet[6]!=8'(WORDS)) $fatal(1,"packet header/status");
        for(integer i=0;i<144;i++) checksum=checksum ^ packet[i];
        if(packet[144]!=checksum || packet[145]!="E" || packet[148]!="!") $fatal(1,"packet checksum/footer");
        if(!FAULT) begin
            for(integer i=0;i<WORDS*4;i++) begin
                if(packet[16+i]!=8'((300032+i)*37+((300032+i)>>8)*17+29)) $fatal(1,"expected data");
                if(expected_result==0 && packet[80+i]!=packet[16+i]) $fatal(1,"actual data");
            end
        end
        start=1;repeat(500) @(negedge clk);start=0;
        if(count!=149 || !finished || valid) $fatal(1,"retrigger after result");
        if(FAULT==0 && requests!=2 || FAULT==2 && requests!=1 || FAULT==1 && requests!=0) $fatal(1,"unexpected command count");
        capture_file=$fopen($sformatf("build/psram-probe-sim/packet-w%0d-r%0d-f%0d.bin",WORDS,WRAP,FAULT),"wb");
        if(!capture_file) $fatal(1,"capture file");
        for(integer i=0;i<149;i++) $fwrite(capture_file,"%c",packet[i]);
        $fclose(capture_file);
        $display("PASS: probe WORDS=%0d WRAP=%0d FAULT=%0d status=%0d full UART packet, freeze/no retry",WORDS,WRAP,FAULT,expected_result);
        $finish;
    end
    initial begin #2000000;$fatal(1,"watchdog");end
endmodule
