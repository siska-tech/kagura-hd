// SPDX-License-Identifier: Apache-2.0
// One armed 4B window roundtrip; passive taps, independent UART snapshot.
module window_observe_core #(parameter integer LANES=4,UART_DIV=469,TIMEOUT=54000000)(
    input wire clk,reset,host_sck,host_cs_n,
    inout wire [3:0] host_io,
    output wire host_busy,host_ready,host_irq_n,uart_tx,
    output wire [1:0] request_count,
    output reg frozen,
    output wire fault,trace_busy
);
    wire cursor_req_valid,cursor_req_write;
    wire [4:0] cursor_req_addr;
    wire [7:0] cursor_req_wdata;
    reg cursor_rsp_valid;
    reg [7:0] cursor_rsp_data;
    wire present_valid;
    wire obs_rx_take,obs_rx_write,obs_csr_take,obs_csr_write,obs_csr_rsp,obs_tx_rsp;
    wire [5:0] obs_rx_addr;
    wire [4:0] obs_csr_addr;
    wire [7:0] obs_rx_data,obs_csr_data,obs_csr_rdata,obs_tx_rdata;
    wire [31:0] obs_upload;
    kagura_fb_host_observe #(.LANES(LANES)) endpoint(
        .clk,.reset,.enabled(1'b1),.video_error(1'b0),.audio_error(1'b0),
        .host_sck,.host_cs_n,.host_io,.host_busy,.host_ready,.host_irq_n,
        .host_valid(),.mem_ready(1'b0),.host_write(),.host_addr(),.host_words(),.host_wdata(),.host_mask(),
        .mem_done(1'b0),.mem_error(1'b0),.mem_rdata(512'd0),
        .present_valid,.present_page(),.present_palette(),.present_ready(1'b1),.present_done(present_valid),
        .cursor_req_valid,.cursor_req_write,.cursor_req_addr,.cursor_req_wdata,
        .cursor_req_ready(1'b1),.cursor_rsp_valid,.cursor_rsp_error(1'b0),.cursor_rsp_data,.cursor_irq(1'b0),
        .obs_rx_take,.obs_rx_write,.obs_rx_addr,.obs_rx_data,
        .obs_csr_take,.obs_csr_write,.obs_csr_addr,.obs_csr_data,
        .obs_csr_rsp,.obs_tx_rsp,.obs_csr_rdata,.obs_tx_rdata,.obs_upload);
    reg armed,used,csr_pending,tx_pending,start_trace;
    reg [7:0] flags,rx_count,write_count,read_count,csr_count,tx_count;
    reg [31:0] rx_bytes,csr_bytes,upload_settled,upload_at_read,csr_bytes_out,tx_bytes_out;
    reg [4:0] settle;
    reg [$clog2(TIMEOUT+1)-1:0] watchdog;
    // Payload slots 0..5: RX bytes, CSR bytes, settled SP, first-read SP,
    // CSR responses, host-dispatch responses. Slot6 tx count, slot7 counters,
    // slot8 read count. Upper slots are zero.
    wire [511:0] trace_payload={224'd0,24'd0,read_count,
        flags,rx_count,write_count,csr_count,24'd0,tx_count,
        tx_bytes_out,csr_bytes_out,upload_at_read,upload_settled,csr_bytes,rx_bytes};
    assign request_count=0;
    assign fault=flags!=0;
    wire frame_done;
    window_snapshot #(.UART_DIV(UART_DIV)) trace(.clk,.reset,.start(start_trace),
        .writing(1'b0),.address(20'd75008),.words(5'd9),.mask(64'd0),
        .payload(trace_payload),.fault,.busy(trace_busy),.uart_tx,.frame_done);
    always @(posedge clk) begin
        if(reset) begin
            armed<=0;used<=0;frozen<=0;flags<=0;start_trace<=0;
            rx_count<=0;write_count<=0;read_count<=0;csr_count<=0;tx_count<=0;
            rx_bytes<=0;csr_bytes<=0;upload_settled<=0;upload_at_read<=0;csr_bytes_out<=0;tx_bytes_out<=0;
            settle<=0;watchdog<=0;csr_pending<=0;tx_pending<=0;cursor_rsp_valid<=0;cursor_rsp_data<=0;
        end else begin
            start_trace<=0;
            cursor_rsp_valid<=cursor_req_valid;
            case(cursor_req_addr)
                0:cursor_rsp_data<="I";1:cursor_rsp_data<="S";2:cursor_rsp_data<="O";3:cursor_rsp_data<="2";
                4:cursor_rsp_data<={3'd0,used,fault,trace_busy,frozen,armed};
                5:cursor_rsp_data<=2;6:cursor_rsp_data<=8'(LANES);
                8:cursor_rsp_data<=flags;
                default:cursor_rsp_data<=0;
            endcase
            if(cursor_req_valid && cursor_req_write && cursor_req_addr==7 && cursor_req_wdata==1 && !used) begin
                armed<=1;used<=1;watchdog<=0;
            end
            if(armed && !frozen) begin
                watchdog<=watchdog+1'b1;
                if(settle!=0) begin
                    settle<=settle-1'b1;
                    if(settle==1) upload_settled<=obs_upload;
                end
                if(obs_rx_take && obs_rx_write && obs_rx_addr==24) begin
                    if(rx_count<4) begin rx_bytes[rx_count[1:0]*8+:8]<=obs_rx_data;rx_count<=rx_count+1'b1;end
                    else flags[0]<=1;
                end
                if(obs_csr_take) begin
                    if(obs_csr_write && obs_csr_addr==24) begin
                        if(write_count<4) begin
                            csr_bytes[write_count[1:0]*8+:8]<=obs_csr_data;write_count<=write_count+1'b1;
                            if(write_count==3) settle<=8;
                        end else flags[1]<=1;
                    end
                    if(!obs_csr_write && obs_csr_addr==24) begin
                        if(read_count==0) upload_at_read<=obs_upload;
                        read_count<=read_count+1'b1;csr_pending<=1;tx_pending<=1;
                        if(write_count!=4) flags[2]<=1;
                    end
                    if(obs_csr_write && obs_csr_addr==26) flags[3]<=1;
                end
                if(obs_csr_rsp && csr_pending) begin
                    csr_pending<=0;
                    if(csr_count<4) begin csr_bytes_out[csr_count[1:0]*8+:8]<=obs_csr_rdata;csr_count<=csr_count+1'b1;end
                    else flags[4]<=1;
                end
                if(obs_tx_rsp && tx_pending) begin
                    tx_pending<=0;
                    if(tx_count<4) begin
                        tx_bytes_out[tx_count[1:0]*8+:8]<=obs_tx_rdata;tx_count<=tx_count+1'b1;
                        if(tx_count==3) begin frozen<=1;armed<=0;start_trace<=1;end
                    end else flags[5]<=1;
                end
                if(watchdog==$clog2(TIMEOUT+1)'(TIMEOUT-1)) begin flags[7]<=1;frozen<=1;armed<=0;start_trace<=1;end
            end
        end
    end
endmodule
