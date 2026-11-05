// SPDX-License-Identifier: Apache-2.0
// One trigger, one bounded WRITE/READ, one complete UART report, then freeze.
// No retry, sweep, host window, display, audio, or Flash interface.
module psram_probe_engine #(
    parameter integer ADDRESS=300032, WORDS=1, CASE_ID=1, TIMEOUT=100000
) (
    input wire clk,reset,start,initialized,
    output wire valid,write,
    output wire [19:0] addr,
    output wire [4:0] words,
    output wire [511:0] wdata,
    output wire [63:0] mask,
    input wire ready,done,error,
    input wire [511:0] rdata,
    output wire tx_valid,
    output reg [7:0] tx_data,
    input wire tx_ready,
    output wire finished,failed,armed
);
    localparam IDLE=0,WRITE_REQ=1,WRITE_WAIT=2,READ_REQ=3,READ_WAIT=4,
               COMPARE=5,REPORT=6,FROZEN=7;
    reg [2:0] state;
    reg [7:0] result,position,checksum;
    reg [6:0] compare_index;
    reg [$clog2(TIMEOUT+1)-1:0] watchdog;
    reg [511:0] received;
    reg [WORDS*32-1:0] compare_data,compare_expected;
    function automatic [511:0] make_pattern;
        reg [511:0] data;
        begin
            data=0;
            for(integer i=0;i<WORDS*4;i++)
                data[i*8+:8]=8'((ADDRESS+i)*37+((ADDRESS+i)>>8)*17+CASE_ID*29);
            make_pattern=data;
        end
    endfunction
    localparam [511:0] EXPECTED=make_pattern();
    assign wdata=EXPECTED;
    assign mask=0;
    assign addr=20'(ADDRESS/4);
    assign words=5'(WORDS);
    assign valid=state==WRITE_REQ || state==READ_REQ;
    assign write=state==WRITE_REQ;
    assign armed=state==IDLE && initialized;
    assign finished=state==FROZEN;
    assign failed=result!=0;
    assign tx_valid=state==REPORT;
    // Fixed 149-byte PDR1 packet; XOR of bytes 0..143 then END! footer.
    always @* begin
        tx_data=0;
        case(position)
            0:tx_data="P";1:tx_data="D";2:tx_data="R";3:tx_data="1";
            4:tx_data=result;5:tx_data=8'(CASE_ID);6:tx_data=8'(WORDS);7:tx_data=0;
            8:tx_data=8'(ADDRESS);9:tx_data=8'(ADDRESS>>8);
            10:tx_data=8'(ADDRESS>>16);11:tx_data=8'(ADDRESS>>24);
            12:tx_data=8'h8f;13:tx_data=8'h1f;14:tx_data=14;15:tx_data=6;
            144:tx_data=checksum;
            145:tx_data="E";146:tx_data="N";147:tx_data="D";148:tx_data="!";
            default:begin
                if(position>=16 && position<80) tx_data=EXPECTED[(position-16)*8+:8];
                // Shift only after each accepted payload byte. Avoid a wide
                // position/subtractor/512-bit mux on the UART input path.
                else if(position>=80 && position<144) tx_data=received[7:0];
            end
        endcase
    end
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;result<=0;position<=0;checksum<=0;received<=0;
            watchdog<=0;compare_index<=0;
            compare_data<=0;compare_expected<=0;
        end else begin
            if(state==WRITE_REQ || state==WRITE_WAIT || state==READ_REQ || state==READ_WAIT) begin
                if(watchdog==$clog2(TIMEOUT+1)'(TIMEOUT-1)) begin
                    result<=3;state<=REPORT;
                end else watchdog<=watchdog+1'b1;
            end
            case(state)
                IDLE:if(start && initialized) begin state<=WRITE_REQ;watchdog<=0;end
                WRITE_REQ:if(ready) state<=WRITE_WAIT;
                WRITE_WAIT:if(done) begin
                    if(error) begin result<=2;state<=REPORT;end
                    else begin state<=READ_REQ;watchdog<=0;end
                end
                READ_REQ:if(ready) state<=READ_WAIT;
                READ_WAIT:if(done) begin
                    received<=rdata;compare_index<=0;
                    compare_data<=rdata[WORDS*32-1:0];compare_expected<=EXPECTED[WORDS*32-1:0];
                    if(error) begin result<=2;state<=REPORT;end
                    else state<=COMPARE;
                end
                COMPARE:begin
                    if(compare_data[7:0]!=compare_expected[7:0]) result<=1;
                    compare_data<=compare_data>>8;compare_expected<=compare_expected>>8;
                    if(compare_index==7'(WORDS*4-1)) state<=REPORT;
                    else compare_index<=compare_index+1'b1;
                end
                REPORT:if(tx_ready) begin
                    if(position>=80 && position<144) received<=received>>8;
                    if(position<144) checksum<=checksum ^ tx_data;
                    if(position==148) state<=FROZEN;
                    else position<=position+1'b1;
                end
                default:begin end
            endcase
            // Timeout has final priority: never issue a new request afterward.
            if((state==WRITE_REQ || state==WRITE_WAIT || state==READ_REQ || state==READ_WAIT) &&
               watchdog==$clog2(TIMEOUT+1)'(TIMEOUT-1)) begin result<=3;state<=REPORT;end
        end
    end
endmodule
