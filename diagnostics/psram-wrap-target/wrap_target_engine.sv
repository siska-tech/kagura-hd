// SPDX-License-Identifier: Apache-2.0
// One wrap-destination observation, 8 commands maximum. First fault freezes
// after its full record. No retry, next experiment, or automatic reset.
module wrap_target_engine #(parameter integer TIMEOUT=100000)(
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
    localparam IDLE=0,LOAD=1,REQUEST=2,WAIT_RESULT=3,COMPARE=4,REPORT=5,FROZEN=6;
    reg [2:0] state;
    reg [3:0] step;
    reg [7:0] status,position,checksum;
    reg [21:0] byte_address;
    reg op_write;
    reg [4:0] op_words;
    reg [63:0] expected_data;
    reg [511:0] received,expected_shift;
    reg [63:0] compare_data,compare_expected;
    reg [3:0] compare_index;
    reg [$clog2(TIMEOUT+1)-1:0] watchdog;
    // All data uniquely identify address/role. A=alias guard, B/C=boundary.
    localparam [31:0] A=32'h43210fed,B=32'h87654321,C=32'hcba98765;
    localparam [63:0] TEST=64'hf0ceac8a67452301;
    reg [21:0] selected_address;
    reg selected_write;
    reg [4:0] selected_words;
    reg [63:0] selected_data;
    always @* begin
        selected_address=300032;selected_write=0;selected_words=1;selected_data={32'd0,A};
        case(step)
            0: selected_write=1;
            1:begin selected_write=1;selected_address=300060;selected_data={32'd0,B};end
            2:begin selected_write=1;selected_address=300064;selected_data={32'd0,C};end
            3:begin end
            4:begin selected_address=300060;selected_data={32'd0,B};end
            5:begin selected_address=300064;selected_data={32'd0,C};end
            6:begin selected_write=1;selected_address=300060;selected_words=2;selected_data=TEST;end
            7:begin selected_address=300032;selected_data={32'd0,TEST[63:32]};end
            default:begin end
        endcase
    end
    assign valid=state==REQUEST;
    assign write=op_write;
    assign addr=byte_address[21:2];
    assign words=op_words;
    assign wdata={448'd0,expected_data};
    assign mask=0;
    assign armed=state==IDLE && initialized;
    assign finished=state==FROZEN;
    assign failed=status==1 || status==2 || status==3;
    assign tx_valid=state==REPORT;
    // PRT1: status, step, words, write, LE address, CR0/LAT/RDL,
    // expected64, actual64, XOR(header+payload), END! = 149 bytes.
    always @* begin
        tx_data=0;
        case(position)
            0:tx_data="P";1:tx_data="R";2:tx_data="T";3:tx_data="1";
            4:tx_data=status;5:tx_data={4'd0,step};6:tx_data={3'd0,op_words};7:tx_data={7'd0,op_write};
            8:tx_data=byte_address[7:0];9:tx_data=byte_address[15:8];
            10:tx_data={2'd0,byte_address[21:16]};11:tx_data=0;
            12:tx_data=8'h8f;13:tx_data=8'h1f;14:tx_data=14;15:tx_data=6;
            144:tx_data=checksum;
            145:tx_data="E";146:tx_data="N";147:tx_data="D";148:tx_data="!";
            default:begin
                if(position>=16 && position<80) tx_data=expected_shift[7:0];
                else if(position>=80 && position<144) tx_data=received[7:0];
            end
        endcase
    end
    always @(posedge clk) begin
        if(reset) begin
            state<=IDLE;step<=0;status<=0;position<=0;checksum<=0;
            byte_address<=0;op_write<=0;op_words<=1;expected_data<=0;
            received<=0;expected_shift<=0;compare_data<=0;compare_expected<=0;
            compare_index<=0;watchdog<=0;
        end else begin
            if(state==REQUEST || state==WAIT_RESULT) watchdog<=watchdog+1'b1;
            case(state)
                IDLE:if(start && initialized) state<=LOAD;
                LOAD:begin
                    byte_address<=selected_address;op_write<=selected_write;op_words<=selected_words;
                    expected_data<=selected_data;expected_shift<={448'd0,selected_data};
                    received<=0;status<=0;position<=0;checksum<=0;watchdog<=0;state<=REQUEST;
                end
                REQUEST:if(ready) state<=WAIT_RESULT;
                WAIT_RESULT:if(done) begin
                    if(!op_write) received<=rdata;
                    if(error) begin status<=2;state<=REPORT;end
                    else if(op_write) state<=REPORT;
                    else begin
                        compare_data<=rdata[63:0];compare_expected<=expected_data;
                        compare_index<=0;state<=COMPARE;
                    end
                end
                COMPARE:begin
                    if(compare_data[7:0]!=compare_expected[7:0]) begin
                        status<=step==7 ? 8'd5 : 8'd1;state<=REPORT;
                    end else if(compare_index=={op_words[1:0],2'b00}-1'b1) begin
                        if(step==7) status<=4;
                        state<=REPORT;
                    end
                    else begin
                        compare_data<=compare_data>>8;compare_expected<=compare_expected>>8;
                        compare_index<=compare_index+1'b1;
                    end
                end
                REPORT:if(tx_ready) begin
                    if(position<144) checksum<=checksum ^ tx_data;
                    if(position>=16 && position<80) expected_shift<=expected_shift>>8;
                    if(position>=80 && position<144) received<=received>>8;
                    if(position==148) begin
                        if(status!=0 || step==7) state<=FROZEN;
                        else begin step<=step+1'b1;state<=LOAD;end
                    end else position<=position+1'b1;
                end
                default:begin end
            endcase
            if((state==REQUEST || state==WAIT_RESULT) && watchdog==$clog2(TIMEOUT+1)'(TIMEOUT-1)) begin
                status<=3;state<=REPORT;
            end
        end
    end
endmodule
