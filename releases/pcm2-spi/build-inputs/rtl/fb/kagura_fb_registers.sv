// SPDX-License-Identifier: Apache-2.0
// Byte register endpoint for the existing SPI/QSPI transport. Data-window
// accesses and staging reads take two system edges; other responses take one. Command/data windows are
// locked while busy; SUBMIT cannot drop or replace an executing operation.
module kagura_fb_registers #(parameter bit AUDIO_CSR=0) (
    input wire clk,reset,enabled,spi_late,video_error,audio_error,external_error,
    input wire req_valid,req_write,
    input wire [4:0] req_addr,
    input wire [7:0] req_wdata,
    output wire req_ready,
    output reg rsp_valid,rsp_error,
    output reg [7:0] rsp_rdata,
    output wire busy,irq,
    output reg cmd_valid,
    input wire cmd_ready,cmd_done,cmd_read_result,
    input wire [15:0] cmd_tag,
    input wire [7:0] cmd_error,
    input wire [511:0] cmd_read_data,
    output reg [127:0] command,
    output wire [511:0] upload_data
);
    localparam BUSY_ERROR=1,BAD_COMMAND=2,BUFFER_ERROR=5,TRANSPORT_ERROR=6;
    reg executing,completed,finish_read;
    reg [6:0] data_addr;
    // Decode on the same edge as every address update, never one cycle late.
    reg [7:0] upload_group_select;
    reg [15:0] completed_tag;
    reg [7:0] completed_error,sticky_error;
    reg window_pending,window_write,write_recovery,port_ready;
    reg [5:0] window_write_addr;
    reg [31:0] window_write_word;
    reg [63:0] window_group;
    reg [2:0] window_lane;
    assign req_ready=!reset && port_ready;
    assign busy=!enabled || executing;
    assign irq=completed || sticky_error!=0 || spi_late;
    wire [7:0] status={spi_late,2'b00,completed,audio_error,video_error,enabled,busy};
    wire bulk_capture=cmd_read_result && executing;
    wire byte_commit=window_pending && window_write;
    // Merge once at CSR acceptance and hold the completed word through the
    // existing commit edge. Read-group storage remains dedicated to reads.
    reg [63:0] selected_upload_group;
    always @* begin
        selected_upload_group=0;
        for(integer group_index=0;group_index<8;group_index=group_index+1)
            selected_upload_group=selected_upload_group |
                (upload_data[group_index*64+:64] & {64{upload_group_select[group_index]}});
    end
    wire [31:0] cpu_old_word=data_addr[2] ? selected_upload_group[63:32] : selected_upload_group[31:0];
    wire [31:0] cpu_write_word;
    generate for(genvar byte_lane=0;byte_lane<4;byte_lane++) begin: cpu_merge
        assign cpu_write_word[byte_lane*8+:8]=data_addr[1:0]==2'(byte_lane) ?
            req_wdata : cpu_old_word[byte_lane*8+:8];
    end endgenerate
    // Sixteen SP blocks retain the parallel 512-bit upload interface.
    // Output settles one edge after capture; COPY's arbiter handoff leaves
    // that edge before write acceptance. READ completion waits for it too.
    genvar word_index;
    generate for(word_index=0;word_index<16;word_index=word_index+1) begin: upload_words
        wire cpu_write=byte_commit && window_write_addr[5:2]==4'(word_index);
        wire writing=reset || bulk_capture || cpu_write;
        wire [3:0] byte_enable=4'b1111;
        wire [31:0] write_data=reset ? 32'd0 : bulk_capture ? cmd_read_data[word_index*32+:32] : window_write_word;
        kagura_fb_upload_word ram(.clk,.write(writing),.byte_enable,.wdata(write_data),.rdata(upload_data[word_index*32+:32]));
    end endgenerate
    always @(posedge clk) begin
        if(reset) begin
            rsp_valid<=0; rsp_error<=0; rsp_rdata<=0; cmd_valid<=0;
            window_pending<=0; window_write<=0;write_recovery<=0;port_ready<=1; window_write_addr<=0; window_write_word<=0; window_group<=0; window_lane<=0;
            command<=0; executing<=0; completed<=0;finish_read<=0;
            completed_tag<=0; completed_error<=0; sticky_error<=0; data_addr<=0;upload_group_select<=1;
        end else begin
            write_recovery<=byte_commit;
            if(window_pending) port_ready<=!window_write;
            if(write_recovery) port_ready<=1;
            rsp_valid<=window_pending; rsp_error<=0;
            window_pending<=0;
            if(window_pending) begin
                if(!window_write) rsp_rdata<=window_group[window_lane*8+:8];
            end
            finish_read<=cmd_done && cmd_read_result && executing;
            if(cmd_valid && cmd_ready) cmd_valid<=0;
            if(req_valid && req_ready) begin
                rsp_valid<=1; rsp_rdata<=0;
                if(req_write) begin
                    if((req_addr>=8 && req_addr<=26) && busy) begin
                        rsp_error<=1; if(sticky_error==0) sticky_error<=BUSY_ERROR;
                    end else if(req_addr>=8 && req_addr<=23) command[(req_addr-8)*8+:8]<=req_wdata;
                    else case(req_addr)
                        7: sticky_error<=0;
                        24: if(data_addr<64) begin
                                window_write_word<=cpu_write_word;
                                window_write_addr<=data_addr[5:0];
                                window_pending<=1;port_ready<=0; window_write<=1; rsp_valid<=0; data_addr<=data_addr+1'b1;
                                if(data_addr[2:0]==7) upload_group_select<={upload_group_select[6:0],upload_group_select[7]};
                            end
                            else begin rsp_error<=1; if(sticky_error==0) sticky_error<=BUFFER_ERROR; end
                        25: if(req_wdata<=64) begin data_addr<=req_wdata[6:0];upload_group_select<=8'b1 << req_wdata[5:3];end
                            else begin rsp_error<=1; if(sticky_error==0) sticky_error<=BUFFER_ERROR; end
                        26: if(req_wdata==1 && cmd_ready) begin
                                cmd_valid<=1; executing<=1; completed<=0;
                            end else begin rsp_error<=1; if(sticky_error==0) sticky_error<=BAD_COMMAND; end
                        31: if(req_wdata[0]) completed<=0;
                        default: begin rsp_error<=1; if(sticky_error==0) sticky_error<=BAD_COMMAND; end
                    endcase
                end else begin
                    if(req_addr>=8 && req_addr<=23) begin
                        window_group<=req_addr[4] ? command[127:64] : command[63:0];
                        window_lane<=req_addr[2:0];window_pending<=1;port_ready<=0;window_write<=0;rsp_valid<=0;
                    end
                    else case(req_addr)
                        0: rsp_rdata<=8'h4b;
                        1: rsp_rdata<=8'h46;
                        2: rsp_rdata<=8'h42;
                        3: rsp_rdata<=8'h31;
                        4: rsp_rdata<=1;
                        5: rsp_rdata<=AUDIO_CSR ? 4 : 2;
                        6: rsp_rdata<=AUDIO_CSR ? 8'hff : 8'h7f;
                        7: rsp_rdata<=spi_late ? TRANSPORT_ERROR : sticky_error;
                        24: if(!executing && data_addr<64) begin
                                window_group<=selected_upload_group; window_lane<=data_addr[2:0];
                                window_pending<=1;port_ready<=0; window_write<=0; rsp_valid<=0; data_addr<=data_addr+1'b1;
                                if(data_addr[2:0]==7) upload_group_select<={upload_group_select[6:0],upload_group_select[7]};
                            end
                            else begin rsp_error<=1; if(sticky_error==0) sticky_error<=BUFFER_ERROR; end
                        25: rsp_rdata<={1'b0,data_addr};
                        26: rsp_rdata<=busy ? 8'd0 : 8'd1;
                        27: rsp_rdata<=status;
                        28: rsp_rdata<=completed_tag[7:0];
                        29: rsp_rdata<=completed_tag[15:8];
                        30: rsp_rdata<=completed_error;
                        31: rsp_rdata<={7'd0,irq};
                        default: rsp_rdata<=0;
                    endcase
                end
            end
            if(AUDIO_CSR && external_error && sticky_error==0) sticky_error<=BAD_COMMAND;
            if(bulk_capture) begin data_addr<=0;upload_group_select<=1;end
            // A completion takes priority over an IRQ/error clear in this cycle.
            if(((cmd_done && !cmd_read_result) || finish_read) && executing) begin
                executing<=0; completed<=1; completed_tag<=cmd_tag; completed_error<=cmd_error;
                if(cmd_error!=0 && sticky_error==0) sticky_error<=cmd_error;
            end
        end
    end
endmodule
