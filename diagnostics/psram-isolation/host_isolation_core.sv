// SPDX-License-Identifier: Apache-2.0
// Reuses product host endpoint without a GPU, PSRAM Controller or PHY.
// Exactly one 4B WRITE then one independent 4B READ; frozen until reset.
module host_isolation_core #(parameter integer LANES=4,UART_DIV=469)(
    input wire clk,reset,host_sck,host_cs_n,
    inout wire [3:0] host_io,
    output wire host_busy,host_ready,host_irq_n,uart_tx,
    output wire [1:0] request_count,
    output wire frozen,fault,trace_busy
);
    wire host_valid,host_write,mem_ready,mem_done,mem_error;
    wire [19:0] host_addr;
    wire [4:0] host_words;
    wire [511:0] host_wdata,mem_rdata;
    wire [63:0] host_mask;
    wire present_valid;
    wire cursor_req_valid,cursor_req_write;
    wire [4:0] cursor_req_addr;
    wire [7:0] cursor_req_wdata;
    reg cursor_rsp_valid;
    reg [7:0] cursor_rsp_data;
    wire [511:0] accepted_data;
    wire [63:0] accepted_mask;
    wire [19:0] accepted_addr;
    wire [4:0] accepted_words;
    wire accepted_write,stub_ready,stub_done,stub_error;
    reg [1:0] count;
    reg log_pending,failed;
    wire take=host_valid && mem_ready;
    // Bytes outside this one-word request are never transferred. Device.write_bytes
    // masks these unused bytes, while the old ROM probe used an all-zero mask.
    wire unexpected=host_words!=1 || host_addr!=20'd75008 || host_write!=(count==0) || host_mask[3:0]!=0;
    assign request_count=count;
    assign frozen=count==2 || failed;
    assign fault=failed;
    assign mem_ready=stub_ready && !trace_busy && !log_pending && !frozen;
    assign mem_done=stub_done;
    assign mem_error=stub_error || failed;
    kagura_fb_host #(.LANES(LANES)) endpoint(
        .clk,.reset,.enabled(1'b1),.video_error(1'b0),.audio_error(1'b0),
        .host_sck,.host_cs_n,.host_io,.host_busy,.host_ready,.host_irq_n,
        .host_valid,.mem_ready,.host_write,.host_addr,.host_words,.host_wdata,.host_mask,
        .mem_done,.mem_error,.mem_rdata,.present_valid,.present_page(),.present_palette(),
        .present_ready(1'b1),.present_done(present_valid),
        .cursor_req_valid,.cursor_req_write,.cursor_req_addr,.cursor_req_wdata,
        .cursor_req_ready(1'b1),.cursor_rsp_valid,.cursor_rsp_error(1'b0),.cursor_rsp_data,.cursor_irq(1'b0));
    psram_host_stub stub(.clk,.reset,.host_valid(host_valid && !trace_busy && !log_pending && !frozen),
        .host_write,.host_addr,.host_words,.host_wdata,.host_mask,.mem_ready(stub_ready),
        .mem_done(stub_done),.mem_error(stub_error),.mem_rdata,
        .accepted_data,.accepted_mask,.accepted_addr,.accepted_words,.accepted_write);
    wire frame_done;
    pdt_snapshot #(.UART_DIV(UART_DIV)) trace(
        .clk,.reset,.start(log_pending),.writing(accepted_write),.address(accepted_addr),
        .words(accepted_words),.mask(accepted_mask),
        .payload(accepted_write ? accepted_data : mem_rdata),.fault(failed),
        .busy(trace_busy),.uart_tx,.frame_done);
    always @(posedge clk) begin
        if(reset) begin count<=0;log_pending<=0;failed<=0;cursor_rsp_valid<=0;cursor_rsp_data<=0;end
        else begin
            log_pending<=take;
            if(take) begin count<=count+1'b1;if(unexpected) failed<=1;end
            cursor_rsp_valid<=cursor_req_valid;
            // Diagnostic bank replaces cursor functionality only in this top.
            case(cursor_req_addr)
                0:cursor_rsp_data<="I";
                1:cursor_rsp_data<="S";
                2:cursor_rsp_data<="O";
                3:cursor_rsp_data<="1";
                4:cursor_rsp_data<={2'd0,trace_busy,log_pending,failed,frozen,count};
                5:cursor_rsp_data<=8'd1; // test ID
                6:cursor_rsp_data<=8'(LANES);
                default:cursor_rsp_data<=0;
            endcase
        end
    end
endmodule
