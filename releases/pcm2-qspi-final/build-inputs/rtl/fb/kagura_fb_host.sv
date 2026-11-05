// SPDX-License-Identifier: Apache-2.0
// Kagura-FB ABI 1.1 SPI/QSPI host endpoint. Mode 0, MSB first.
// BUSY covers command submission; status reads remain available while busy.
module kagura_fb_host #(parameter integer LANES=1, parameter bit AUDIO_CSR=0) (
    input wire clk,reset,enabled,video_error,audio_error,
    input wire host_sck,host_cs_n,
    inout wire [3:0] host_io,
    output wire host_busy,host_ready,host_irq_n,
    output wire host_valid,
    input wire mem_ready,
    output wire host_write,
    output wire [19:0] host_addr,
    output wire [4:0] host_words,
    output wire [511:0] host_wdata,
    output wire [63:0] host_mask,
    input wire mem_done,mem_error,
    input wire [511:0] mem_rdata,
    output wire present_valid,present_page,
    output wire [191:0] present_palette,
    input wire present_ready,present_done,
    output wire cursor_req_valid,cursor_req_write,
    output wire [4:0] cursor_req_addr,
    output wire [7:0] cursor_req_wdata,
    input wire cursor_req_ready,cursor_rsp_valid,cursor_rsp_error,cursor_irq,
    input wire [7:0] cursor_rsp_data,
    output wire audio_req_valid,audio_req_write,output wire [3:0] audio_req_addr,
    output wire [7:0] audio_req_wdata,
    input wire audio_req_ready,audio_rsp_valid,audio_rsp_error,
    output wire audio_capture,audio_apply,audio_commit_done,
    input wire audio_settings_valid,audio_busy,audio_settle,audio_ready,audio_done,audio_apply_error,
    input wire [7:0] audio_rsp_data
);
    wire [3:0] io_out,io_oe;
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1) begin: io
        assign host_io[lane]=io_oe[lane] ? io_out[lane] : 1'bz;
    end endgenerate
    wire req_valid,req_ready,req_write,rsp_valid,rsp_error,irq,irq_drive,late,busy;
    wire [5:0] req_addr;
    wire [7:0] req_wdata,rsp_rdata;
    reg enabled_sys;
    always @(posedge clk) enabled_sys<=!reset && enabled;
    assign host_ready=enabled_sys && !reset;
    assign host_irq_n=irq_drive ? 1'b0 : 1'bz;
    kagura_spi_adapter #(.LANES(LANES),.REG_ADDR_BITS(6),.STATUS_ADDR(6'd27)) transport(
        .clk,.reset,.spi_sck(host_sck),.spi_cs_n(host_cs_n),.spi_io_in(host_io),
        .spi_io_out(io_out),.spi_io_oe(io_oe),.busy(host_busy),.irq_drive,.irq_level(irq || cursor_irq),
        .queue_free(busy ? 6'd0 : 6'd32),.req_valid,.req_ready,.req_write,.req_addr,.req_wdata,
        .rsp_valid,.rsp_ready(),.rsp_rdata,.rsp_error,.late);
    // Both status inputs may originate in the pixel domain. They are sticky
    // levels; synchronize before CSR decoding in the system domain.
    (* ASYNC_REG="TRUE" *) reg [1:0] video_sync,audio_sync;
    always @(posedge clk) begin
        if(reset) begin video_sync<=0; audio_sync<=0; end
        else begin video_sync<={video_sync[0],video_error}; audio_sync<={audio_sync[0],audio_error}; end
    end
    wire base_ready,base_rsp_valid,base_rsp_error;
    wire [7:0] base_rsp_data;
    // One registered dispatch slot. Each CSR bank gets local payload
    // registers so the transport address does not fan out across both banks.
    localparam BUS_IDLE=0,BUS_ISSUE=1,BUS_WAIT=2;
    reg [1:0] bus_state;
    reg bus_cursor,bus_audio,base_write,cursor_write,audio_write;
    reg [3:0] audio_addr;reg [7:0] audio_data;
    assign audio_req_valid=bus_state==BUS_ISSUE && bus_audio;
    assign audio_req_write=audio_write;assign audio_req_addr=audio_addr;assign audio_req_wdata=audio_data;
    reg [4:0] base_addr,cursor_addr;
    reg [7:0] base_data,cursor_data;
    wire base_valid=bus_state==BUS_ISSUE && !bus_cursor && !bus_audio;
    assign cursor_req_valid=bus_state==BUS_ISSUE && bus_cursor;
    assign cursor_req_write=cursor_write;
    assign cursor_req_addr=cursor_addr;
    assign cursor_req_wdata=cursor_data;
    assign req_ready=!reset && bus_state==BUS_IDLE;
    assign rsp_valid=bus_state==BUS_WAIT && (bus_audio ? audio_rsp_valid : bus_cursor ? cursor_rsp_valid : base_rsp_valid);
    assign rsp_error=bus_audio ? audio_rsp_error : bus_cursor ? cursor_rsp_error : base_rsp_error;
    assign rsp_rdata=bus_audio ? audio_rsp_data : bus_cursor ? cursor_rsp_data : base_rsp_data;
    always @(posedge clk) begin
        if(reset) begin
            bus_state<=BUS_IDLE;bus_audio<=0;audio_write<=0;audio_addr<=0;audio_data<=0;bus_cursor<=0;base_write<=0;cursor_write<=0;
            base_addr<=0;cursor_addr<=0;base_data<=0;cursor_data<=0;
        end else case(bus_state)
            BUS_IDLE: if(req_valid) begin
                bus_audio<=AUDIO_CSR && req_addr>=54;bus_cursor<=req_addr[5] && !(AUDIO_CSR && req_addr>=54);bus_state<=BUS_ISSUE;
                if(AUDIO_CSR && req_addr>=54) begin audio_addr<=req_addr[3:0];audio_data<=req_wdata;audio_write<=req_write;end
                else if(req_addr[5]) begin cursor_addr<=req_addr[4:0];cursor_data<=req_wdata;cursor_write<=req_write;end
                else begin base_addr<=req_addr[4:0];base_data<=req_wdata;base_write<=req_write;end
            end
            BUS_ISSUE: if(bus_audio ? audio_req_ready : bus_cursor ? cursor_req_ready : base_ready) bus_state<=BUS_WAIT;
            BUS_WAIT: if(rsp_valid) bus_state<=BUS_IDLE;
            default: bus_state<=BUS_IDLE;
        endcase
    end
    wire cmd_valid,cmd_ready,cmd_done,cmd_read_result;
    wire [15:0] cmd_tag;
    wire [7:0] cmd_error;
    wire [127:0] command;
    wire [511:0] upload_data,cmd_read_data;
    kagura_fb_registers #(.AUDIO_CSR(AUDIO_CSR)) registers(
        .clk,.reset,.enabled(enabled_sys),.spi_late(late),.video_error(video_sync[1]),.audio_error(audio_sync[1]),
        .external_error(AUDIO_CSR && bus_audio && audio_rsp_valid && audio_rsp_error),
        .req_valid(base_valid),.req_write(base_write),.req_addr(base_addr),.req_wdata(base_data),
        .req_ready(base_ready),.rsp_valid(base_rsp_valid),.rsp_error(base_rsp_error),.rsp_rdata(base_rsp_data),
        .busy,.irq,.cmd_valid,.cmd_ready,.cmd_done,.cmd_read_result,.cmd_tag,.cmd_error,.cmd_read_data,
        .command,.upload_data);
    kagura_fb_commands #(.AUDIO_CSR(AUDIO_CSR)) commands(
        .clk,.reset,.valid(cmd_valid),.ready(cmd_ready),.command,.upload_data,
        .done(cmd_done),.error(cmd_error),.tag(cmd_tag),.read_data(cmd_read_data),.read_result(cmd_read_result),
        .host_valid,.host_ready(mem_ready),.host_write,.host_addr,.host_words,.host_wdata,.host_mask,
        .host_done(mem_done),.host_error(mem_error),.host_rdata(mem_rdata),
        .audio_capture,.audio_apply,.audio_commit_done,.audio_settings_valid,.audio_busy,.audio_settle,.audio_ready,.audio_done,.audio_apply_error,
        .present_valid,.present_ready,.present_done,.present_page,.present_palette);
endmodule
