`timescale 1ns/1ps
module tb_boundary #(parameter integer WRAP=0,ALIAS=0,FAULT=0);
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
    wire inject=engine.step==6;
    wire controller_valid=valid && !(FAULT==2 && inject);
    kagura_fb_burst_ctrl #(.INIT_CYCLES(64)) controller(.valid(controller_valid),.*);
    // Test-only absolute byte-address bit5 alias. Existing models untouched.
    wire [7:0] model_f=ALIAS && controller.ca_phase && controller.tick==2 && !controller.ca[46] ?
                          (phy_dq_o_fall & 8'hfd) : phy_dq_o_fall;
    generate if(WRAP) begin
        kagura_psram_wrap_pair_model #(.BYTES(300160),.ALLOW_UNDOCUMENTED_CA45(1)) memory(
            .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
            .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
            .dq_f(model_f),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
            .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
        always @(posedge clk) if(finished && FAULT==0 && ALIAS==0)
            if(memory.memory[300032]!=8'h8a || memory.memory[300033]!=8'hac ||
               memory.memory[300034]!=8'hce || memory.memory[300035]!=8'hf0)
                $fatal(1,"wrapped write did not overwrite alias guard");
    end else begin
        kagura_hyperram_pair_model #(.BYTES(300160),.MAX_WORDS(16)) memory(
            .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
            .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),
            .dq_f(model_f),.mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),
            .read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    end endgenerate
    wire tx_valid,tx_ready,finished,failed,armed,uart_tx;
    wire [7:0] tx_data;
    wire engine_done=FAULT==3 && inject ? 1'b0 : done;
    wire engine_error=FAULT==1 && inject ? done : error;
    wire [511:0] engine_rdata=FAULT==4 && engine.step==8 ? rdata ^ 512'd1 : rdata;
    boundary_engine #(.TIMEOUT(300)) engine(
        .clk,.reset,.start,.initialized,.valid,.write,.addr,.words,.wdata,.mask,
        .ready(FAULT==2 && inject ? 1'b0 : ready),.done(engine_done),.error(engine_error),.rdata(engine_rdata),
        .tx_valid,.tx_ready,.tx_data,.finished,.failed,.armed);
    psram_probe_uart #(.DIV(4)) uart(.clk,.reset,.valid(tx_valid),.data(tx_data),.ready(tx_ready),.tx(uart_tx));
    reg [7:0] capture[0:1638];
    reg [7:0] byte_value;
    integer captured=0,requests=0;
    always @(posedge clk) if(controller_valid && ready) requests<=requests+1;
    initial forever begin
        @(negedge uart_tx);#60;
        for(integer bit_index=0;bit_index<8;bit_index++) begin byte_value[bit_index]=uart_tx;#40;end
        if(!uart_tx || captured>=1639) $fatal(1,"UART framing/extra data");
        capture[captured]=byte_value;captured++;
    end
    integer expected_step,expected_status,expected_requests,file_handle;
    reg [7:0] checksum;
    initial begin
        repeat(3) @(negedge clk);reset=0;wait(armed);
        repeat(20) @(negedge clk);
        if(requests || captured) $fatal(1,"untriggered execution");
        start=1;@(negedge clk);start=0;
        wait(finished);wait(tx_ready);repeat(20) @(negedge clk);
        expected_step=ALIAS ? 3 : FAULT==1 || FAULT==2 || FAULT==3 ? 6 : FAULT==4 ? 8 : WRAP ? 9 : 10;
        expected_status=FAULT==1 ? 2 : FAULT==2 || FAULT==3 ? 3 : ALIAS || FAULT==4 || WRAP ? 1 : 0;
        expected_requests=expected_step+1-(FAULT==2 ? 1 : 0);
        if(captured!=(expected_step+1)*149 || requests!=expected_requests) $fatal(1,"command/packet count");
        for(integer step_index=0;step_index<=expected_step;step_index++) begin
            checksum=0;
            for(integer b=0;b<144;b++) checksum=checksum ^ capture[step_index*149+b];
            if(capture[step_index*149+144]!=checksum || capture[step_index*149]!="P" ||
               capture[step_index*149+1]!="B" || capture[step_index*149+5]!=8'(step_index) ||
               capture[step_index*149+148]!="!") $fatal(1,"packet metadata/checksum");
            if(capture[step_index*149+4]!=8'(step_index==expected_step ? expected_status : 0)) $fatal(1,"status sequence");
        end
        if(WRAP && !FAULT && !ALIAS) begin
            // The 8B same-start roundtrip PASSED but absolute post-boundary
            // READ fails: expected trial tail, actual retained seed C.
            if(capture[7*149+4]!=0 || capture[9*149+4]!=1) $fatal(1,"false PASS not exposed");
            if({capture[9*149+83],capture[9*149+82],capture[9*149+81],capture[9*149+80]}!=32'hcba98765)
                $fatal(1,"unexpected post-boundary retained seed");
        end
        start=1;repeat(1000) @(negedge clk);start=0;
        if(captured!=(expected_step+1)*149 || requests!=expected_requests || valid || !finished) $fatal(1,"replay/retrigger");
        file_handle=$fopen($sformatf("build/psram-boundary/packet-r%0d-a%0d-f%0d.bin",WRAP,ALIAS,FAULT),"wb");
        if(!file_handle) $fatal(1,"capture file");
        for(integer i=0;i<captured;i++) $fwrite(file_handle,"%c",capture[i]);
        $fclose(file_handle);
        $display("PASS: boundary wrap=%0d alias=%0d fault=%0d last_step=%0d status=%0d requests=%0d UART=%0d",WRAP,ALIAS,FAULT,expected_step,expected_status,requests,captured);
        $finish;
    end
    initial begin #5000000;$fatal(1,"watchdog");end
endmodule
