`timescale 1ns/1ps
// Stress back-to-back byte RMW, bulk captures and READ completion timing.
module tb_fb_register_window;
    reg clk=0,reset=1,req_valid=0,req_write=0;
    always #5 clk=~clk;
    reg [4:0] req_addr=0;
    reg [7:0] req_wdata=0;
    wire req_ready,rsp_valid,rsp_error,busy,irq,cmd_valid;
    wire [7:0] rsp_rdata;
    wire [127:0] command;
    wire [511:0] upload_data;
    reg cmd_done=0,cmd_read_result=0;
    reg [511:0] cmd_read_data=0;
    kagura_fb_registers dut(
        .clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),
        .req_valid,.req_write,.req_addr,.req_wdata,.req_ready,.rsp_valid,.rsp_error,.rsp_rdata,
        .busy,.irq,.cmd_valid,.cmd_ready(1'b1),.cmd_done,.cmd_read_result,
        .cmd_tag(16'habcd),.cmd_error(8'd0),.cmd_read_data,.command,.upload_data);
    wire ref_req_ready,ref_rsp_valid,ref_rsp_error,ref_busy,ref_irq,ref_cmd_valid;
    wire [7:0] ref_rsp_rdata;wire [127:0] ref_command;wire [511:0] ref_upload_data;
    kagura_fb_registers_reference reference_registers(
        .clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),.external_error(1'b0),
        .req_valid,.req_write,.req_addr,.req_wdata,.req_ready(ref_req_ready),.rsp_valid(ref_rsp_valid),.rsp_error(ref_rsp_error),.rsp_rdata(ref_rsp_rdata),
        .busy(ref_busy),.irq(ref_irq),.cmd_valid(ref_cmd_valid),.cmd_ready(1'b1),.cmd_done,.cmd_read_result,
        .cmd_tag(16'habcd),.cmd_error(8'd0),.cmd_read_data,.command(ref_command),.upload_data(ref_upload_data));
    always @(negedge clk) if(!reset)
        if({req_ready,rsp_valid,rsp_error,rsp_rdata,busy,irq,cmd_valid,command,upload_data} !==
           {ref_req_ready,ref_rsp_valid,ref_rsp_error,ref_rsp_rdata,ref_busy,ref_irq,ref_cmd_valid,ref_command,ref_upload_data})
            $fatal(1,"Host window cycle/reference mismatch");
    task access(input bit wr,input integer address,value,output reg [7:0] result);
        begin
            @(negedge clk);req_valid=1;req_write=wr;req_addr=5'(address);req_wdata=8'(value);
            do @(posedge clk);while(!req_ready);
            @(negedge clk);req_valid=0;
            while(!rsp_valid) @(negedge clk);
            if(rsp_error) $fatal(1,"unexpected CSR error address=%0d",address);
            result=rsp_rdata;
        end
    endtask
    reg [7:0] value;
    task verify_window(input integer base);
        begin
            access(1,25,0,value);
            for(integer i=0;i<64;i=i+1) begin
                access(0,24,0,value);
                if(value!==8'(base+i*17)) $fatal(1,"window byte=%0d got=%h",i,value);
            end
        end
    endtask
    initial begin
        repeat(3) @(negedge clk);reset=0;repeat(2) @(negedge clk);
        if(upload_data!==512'd0) $fatal(1,"window reset");
        for(integer iteration=0;iteration<6;iteration=iteration+1) begin
            access(1,25,0,value);
            for(integer i=0;i<64;i=i+1) access(1,24,iteration+i*17,value);
            verify_window(iteration);
            // READ completion must remain busy until BSRAM outputs settle.
            access(1,26,1,value);
            @(negedge clk);
            for(integer i=0;i<64;i=i+1) cmd_read_data[i*8+:8]=8'(91+iteration+i*17);
            cmd_read_result=1;cmd_done=1;
            @(negedge clk);cmd_read_result=0;cmd_done=0;
            if(!busy || dut.completed) $fatal(1,"READ completion before RAM output");
            @(negedge clk);
            if(busy || !dut.completed || upload_data!==cmd_read_data) $fatal(1,"READ result/completion ordering");
            verify_window(91+iteration);
            // Internal COPY captures must neither finish the command nor
            // depend on an initial zero contents.
            access(1,26,1,value);
            for(integer capture=0;capture<3;capture=capture+1) begin
                @(negedge clk);cmd_read_data=~cmd_read_data;cmd_read_result=1;
                @(negedge clk);cmd_read_result=0;
                @(negedge clk);
                if(!busy || dut.completed || upload_data!==cmd_read_data) $fatal(1,"COPY capture ordering");
            end
            @(negedge clk);cmd_done=1;
            @(negedge clk);cmd_done=0;
            if(busy || !dut.completed) $fatal(1,"COPY completion");
        end
        @(negedge clk);reset=1;repeat(3) @(negedge clk);reset=0;
        repeat(2) @(negedge clk);
        if(upload_data!==512'd0 || busy || irq) $fatal(1,"window warm reset");
        $display("PASS tb_fb_register_window: immediate masked byte writes/readback, 6 READ completions, 18 COPY captures, warm reset");
        $finish;
    end
    initial begin #200000;$fatal(1,"window timeout");end
endmodule
