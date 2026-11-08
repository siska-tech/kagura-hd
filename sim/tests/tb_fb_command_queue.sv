`timescale 1ns/1ps
// CSR-to-executor integration: capacity includes the active descriptor.
module tb_fb_command_queue #(parameter integer DEPTH=2, REGISTER_HEAD=0, TEST_ACK_DELAY=0);
    reg clk=0,reset=1;
    always #5 clk=~clk;
    reg req_valid=0,req_write=0;
    reg [4:0] req_addr=0;
    reg [7:0] req_wdata=0;
    wire req_ready,rsp_valid,rsp_error,busy,irq,valid,ready,done,read_result;
    wire [7:0] rsp_rdata,error;
    wire [15:0] tag;
    wire [127:0] command;
    wire engine_valid,engine_ready;
    wire [127:0] engine_command;
    generate if(REGISTER_HEAD) begin: registered_head
        kagura_fb_command_head head(.clk,.reset,.in_valid(valid),.in_ready(ready),.in_command(command),
            .out_valid(engine_valid),.out_ready(engine_ready),.out_done(done),.out_command(engine_command));
    end else begin: direct_head
        assign engine_valid=valid;assign ready=engine_ready;assign engine_command=command;
    end endgenerate
    wire [511:0] upload_data,read_data;
    wire [191:0] present_palette;
    reg present_done=0;
    reg mem_ready=0,mem_done=0;
    reg [511:0] mem_data=0;
    wire present_valid,host_valid;
    kagura_fb_registers #(.QUEUE_DEPTH(DEPTH)) regs(
        .clk,.reset,.enabled(1'b1),.spi_late(1'b0),.video_error(1'b0),.audio_error(1'b0),.external_error(1'b0),
        .req_valid,.req_write,.req_addr,.req_wdata,.req_ready,.rsp_valid,.rsp_error,.rsp_rdata,.busy,.irq,
        .cmd_valid(valid),.cmd_ready(ready),.cmd_done(done),.cmd_read_result(read_result),
        .cmd_tag(tag),.cmd_error(error),.cmd_read_data(read_data),.command,.upload_data);
    kagura_fb_commands #(.REGISTER_DECODE(REGISTER_HEAD)) engine(
        .clk,.reset,.valid(engine_valid),.ready(engine_ready),.command(engine_command),.upload_data,.done,.error,.tag,.read_data,.read_result,
        .host_valid,.host_ready(mem_ready),.host_done(mem_done),.host_error(1'b0),.host_rdata(mem_data),
        .host_write(),.host_addr(),.host_words(),.host_wdata(),.host_mask(),
        .present_valid,.present_ready(1'b1),.present_done,.present_page(),.present_palette,
        .audio_capture(),.audio_apply(),.audio_commit_done(),
        .audio_settings_valid(1'b0),.audio_busy(1'b0),.audio_settle(1'b0),.audio_ready(1'b0),.audio_done(1'b0),.audio_apply_error(1'b0));
    task access(input bit wr,input integer addr,data,input bit fails,output reg [7:0] result);
        @(negedge clk);req_valid=1;req_write=wr;req_addr=5'(addr);req_wdata=8'(data);
        do @(posedge clk);while(!req_ready);
        @(negedge clk);req_valid=0;
        while(!rsp_valid) @(negedge clk);
        if(rsp_error!==fails) $fatal(1,"CSR addr=%0d error=%0d expected=%0d",addr,rsp_error,fails);
        result=rsp_rdata;
    endtask
    reg [7:0] value;
    task submit(input integer opcode,id);
        access(1,8,opcode,0,value);
        access(1,10,id&255,0,value);
        access(1,11,id>>8,0,value);
        access(1,26,1,0,value);
    endtask
    task completion(input integer id,err);
        wait(irq);repeat(2) @(negedge clk);
        access(0,28,0,0,value);if(value!==8'(id)) $fatal(1,"completion tag %d != %d",value,id);
        access(0,30,0,0,value);if(value!==8'(err)) $fatal(1,"completion error");
    endtask
    initial begin
        repeat(4) @(negedge clk);reset=0;
        // Repeated rounds wrap both pointers. PRESENT stalls the active head.
        for(integer round_id=0;round_id<4;round_id++) begin
            submit(3,round_id*DEPTH);
            wait(present_valid);repeat(4) @(negedge clk);
            for(integer i=1;i<DEPTH;i++) submit(0,round_id*DEPTH+i);
            if(!busy) $fatal(1,"full queue must assert busy");
            access(1,26,1,1,value); // full: no replacement
            access(1,7,0,0,value);
            @(negedge clk);present_done=1;
            @(negedge clk);present_done=0;
            for(integer i=0;i<DEPTH;i++) begin
                completion(round_id*DEPTH+i,0);
                repeat(8) @(negedge clk);
                access(0,28,0,0,value);
                if(value!==8'(round_id*DEPTH+i)) $fatal(1,"completion overwritten before ACK");
                repeat(TEST_ACK_DELAY) @(negedge clk);
                access(1,31,1,0,value);
            end
            repeat(8) @(negedge clk);
            if(busy || regs.queue_count!=0) $fatal(1,"queue did not drain");
        end
        // Memory-related opcode is a barrier; younger commands are rejected.
        access(1,9,1,0,value);
        submit(4,99);
        access(1,8,0,1,value);
        access(1,24,42,1,value);
        access(1,7,0,0,value);
        @(negedge clk);reset=1;repeat(3) @(negedge clk);reset=0;
        submit(4,99); // zero word count: RANGE_ERROR
        completion(99,3);
        access(1,31,1,0,value);access(1,7,0,0,value);
        // A valid READ retains the shared window lock through bulk settling.
        access(1,9,1,0,value);submit(5,103);
        wait(host_valid);
        access(1,25,0,1,value);access(1,7,0,0,value);
        @(negedge clk);mem_ready=1;
        @(negedge clk);mem_ready=0;
        repeat(3) @(negedge clk);
        mem_data={16{32'h12345678}};mem_done=1;
        @(negedge clk);mem_done=0;
        completion(103,0);
        if(upload_data!==mem_data) $fatal(1,"queued READ result did not settle");
        access(1,31,1,0,value);
        access(1,9,0,0,value);
        // Queue a palette payload while a different descriptor is executing.
        submit(3,104);wait(present_valid);
        access(1,9,6,0,value);access(1,12,8'h20,0,value);access(1,13,8'h0f,0,value);
        submit(2,105);
        if(present_palette[72+:12]!==12'h666) $fatal(1,"palette executed out of order");
        @(negedge clk);present_done=1;
        @(negedge clk);present_done=0;
        completion(104,0);access(1,31,1,0,value);
        completion(105,0);
        if(present_palette[72+:12]!==12'hf20) $fatal(1,"queued palette snapshot");
        access(1,31,1,0,value);
        access(1,9,0,0,value);access(1,12,0,0,value);access(1,13,0,0,value);
        // Reset flushes active, queued and unacknowledged completion state.
        submit(3,100);submit(0,101);
        @(negedge clk);reset=1;repeat(3) @(negedge clk);reset=0;
        repeat(6) @(negedge clk);
        if(busy || irq || valid || regs.queue_count!=0) $fatal(1,"reset flush");
        submit(0,102);completion(102,0);
        $display("PASS: command queue depth=%0d registered_head=%0d",DEPTH,REGISTER_HEAD);$finish;
    end
    initial begin #1000000;$fatal(1,"timeout");end
endmodule
