// SPDX-License-Identifier: Apache-2.0
module tb_stream;
    bit clk=0;
    always #5 clk=~clk;
    bit reset=1,sample_tick,stream_control_write,stream_publish;
    bit [7:0] stream_data;
    bit [1:0] cfg_valid,start_play,explicit_stop;
    wire [1:0] cfg_ready,ready,active,underrun;
    wire [7:0] stream_token,stream_status;
    wire mem_req_valid;
    wire [21:0] mem_req_addr;
    bit response_pending,hold_response;
    wire mem_rsp_valid=response_pending && !hold_response;
    bit [7:0] mem_rsp_data;
    wire signed [7:0] sample0,sample1;
    localparam [21:0] L=22'h040000,R=22'h042000;
    wire mem_req_ready=!response_pending;
    byte generation[2];
    integer requests;

    kagura_pcm_prefetch #(.ADDR_WIDTH(22),.BUFFER_ADDR_BITS(5),.STREAM(1)) dut(
        .clk,.reset,.sample_tick,.stream_control_write,.stream_publish,.stream_data,
        .explicit_stop,.stream_token,.stream_status,.stream_cancel_control(),
        .cfg_valid,.cfg_ready,.cfg_start({R,L}),.cfg_end({R+22'd8192,L+22'd8192}),
        .cfg_loop({R,L}),.cfg_loop_enable(2'b11),.start_play,.stop_play(explicit_stop),
        .ready,.active,.done(),.underrun,.config_error(),.memory_error(),.sample0,.sample1,
        .mem_req_valid,.mem_req_ready,.mem_req_addr,.mem_rsp_valid,.mem_rsp_data,
        .mem_rsp_error(1'b0));

    always @(posedge clk) begin
        if(mem_rsp_valid) response_pending<=0;
        if(mem_req_valid && mem_req_ready) begin
            response_pending<=1;
            requests<=requests+1;
            mem_rsp_data<=mem_req_addr[7:0] + generation[mem_req_addr[12]] +
                          (mem_req_addr[13] ? 8'd31 : 8'd0);
        end
    end

    always @(negedge clk)
        if(stream_status[1] && dut.outstanding && dut.outstanding_last &&
           dut.outstanding_half==stream_token[0] && stream_status[0])
            $fatal(1,"half returned before final response was consumed");

    task automatic control(input byte data);
        @(negedge clk); stream_control_write=1; stream_data=data;
        @(negedge clk); stream_control_write=0;
    endtask
    task automatic publish(input byte token);
        @(negedge clk); stream_publish=1; stream_data=token;
        @(negedge clk); stream_publish=0;
    endtask
    task automatic start;
        control(1);
        wait(!stream_status[2]);
        repeat(3) @(negedge clk);
        cfg_valid=3;
        @(negedge clk); cfg_valid=0;
        wait(ready==3);
        @(negedge clk); start_play=3;
        @(negedge clk); start_play=0;
    endtask
    task automatic sample;
        repeat(10) @(negedge clk);
        sample_tick=1;
        @(negedge clk); sample_tick=0;
    endtask

    initial begin
        byte token;
        byte expected;
        integer last_requests;
        repeat(3) @(negedge clk); reset=0;
        start();
        for(int n=0;n<16384;n++) begin
            if(n%4096==4096-16) begin
                if(!stream_status[0]) $fatal(1,"half did not return before playback boundary");
                token=stream_token;
                publish(token^8'h02);
                if(stream_token!=token) $fatal(1,"stale publication accepted");
                generation[token[0]]+=8'd7;
                publish(token);
                if(stream_token==token) $fatal(1,"publication ignored");
                publish(token);
            end
            sample();
            expected=8'(n)+8'((n/8192)*7);
            if(sample0!==expected || sample1!==expected+8'd31 || active!=3)
                $fatal(1,"sample mismatch at %0d: %0d/%0d expected %0d",n,sample0,sample1,expected);
        end
        // Consume both ready halves without returning either. No old A data
        // may be requested after the two halves have drained.
        repeat(8192) sample();
        last_requests=requests;
        sample();
        if(underrun!=3 || active!=0 || sample0!=0 || sample1!=0)
            $fatal(1,"underrun did not stop both channels");
        repeat(10) @(negedge clk);
        if(stream_status[1] || requests!=last_requests)
            $fatal(1,"aborted stream issued another read");
        control(1);
        @(negedge clk); cfg_valid=3; hold_response=1;
        @(negedge clk); cfg_valid=0;
        wait(response_pending);
        control(0);
        if(!stream_status[2] || stream_status[1]) $fatal(1,"stop released outstanding read early");
        hold_response=0;
        repeat(10) @(negedge clk);
        if(stream_status[2:0]!=0 || active!=0) $fatal(1,"stop did not drain");
        start();
        if(active!=3) $fatal(1,"restart after drain failed");
        $display("PASS: stereo half reuse, sample sequence, stale token, starvation and restart");
        $finish;
    end
    initial begin #4000000; $fatal(1,"stream timeout"); end
endmodule
