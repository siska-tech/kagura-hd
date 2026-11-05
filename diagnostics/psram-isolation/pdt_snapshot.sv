// SPDX-License-Identifier: Apache-2.0
// One immutable boundary snapshot per PDT1 frame. No live wide data mux.
module pdt_snapshot # (parameter integer UART_DIV=469)(
    input wire clk,reset,start,
    input wire writing,
    input wire [19:0] address,
    input wire [4:0] words,
    input wire [63:0] mask,
    input wire [511:0] payload,
    input wire fault,
    output wire busy,
    output wire uart_tx,
    output reg frame_done
);
    localparam IDLE=0,HEADER=1,RECORDS=2,CRC=3,DRAIN=4;
    reg [2:0] state;
    reg [95:0] header;
    reg [959:0] records;
    reg [31:0] crc;
    reg [7:0] remaining;
    wire [7:0] byte_data=state==HEADER ? header[7:0] : state==RECORDS ? records[7:0] : ~crc[7:0];
    wire tx_ready;
    wire tx_valid=state==HEADER || state==RECORDS || state==CRC;
    assign busy=state!=IDLE;
    psram_probe_uart #(.DIV(UART_DIV)) uart(.clk,.reset,.valid(tx_valid),.data(byte_data),.ready(tx_ready),.tx(uart_tx));
    function automatic [31:0] crc_byte(input [31:0] c,input [7:0] d);
        reg [31:0] v;
        begin
            v=c^{24'd0,d};
            for(integer i=0;i<8;i++) v=v[0] ? (v>>1)^32'hedb88320 : v>>1;
            crc_byte=v;
        end
    endfunction
    always @(posedge clk) begin
        if(reset) begin state<=IDLE;header<=0;records<=0;crc<=32'hffffffff;remaining<=0;frame_done<=0;end
        else begin
            frame_done<=0;
            case(state)
                IDLE: if(start) begin
                    // bytes PDT1, version1, source2=request/3=response, test ID1,
                    // count20, flags bit0 fault. Every record is same-edge snapshot.
                    header<={8'd0,7'd0,fault,16'd20,16'd1,(writing ? 8'd2 : 8'd3),8'd1,32'h31544450};
                    records[0*48+:48]<={16'd0,10'd0,address,2'b00};
                    records[1*48+:48]<={16'd0,26'd0,writing,words};
                    records[2*48+:48]<={16'd0,mask[31:0]};
                    records[3*48+:48]<={16'd0,mask[63:32]};
                    for(integer i=0;i<16;i++) records[(i+4)*48+:48]<={16'd0,payload[i*32+:32]};
                    crc<=32'hffffffff;remaining<=12;state<=HEADER;
                end
                HEADER: if(tx_ready) begin
                    crc<=crc_byte(crc,byte_data);header<=header>>8;remaining<=remaining-1'b1;
                    if(remaining==1) begin remaining<=120;state<=RECORDS;end
                end
                RECORDS: if(tx_ready) begin
                    crc<=crc_byte(crc,byte_data);records<=records>>8;remaining<=remaining-1'b1;
                    if(remaining==1) begin remaining<=4;state<=CRC;end
                end
                CRC: if(tx_ready) begin
                    crc<=crc>>8;remaining<=remaining-1'b1;
                    if(remaining==1) state<=DRAIN;
                end
                DRAIN: if(tx_ready) begin state<=IDLE;frame_done<=1;end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
