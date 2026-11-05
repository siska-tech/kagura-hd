// SPDX-License-Identifier: Apache-2.0
// Independent diagnostic model: W955D8MBYA A01-001 wrap/CA contract.
// Pair boundary ONLY: LAT/RDL emulate the existing controller/PHY pipeline,
// not the datasheet's pin latency, analog eye, RWDS stalls or tri-state delays.
// ALLOW_UNDOCUMENTED_CA45 models a hypothesis, NOT specified silicon behavior.
module kagura_psram_wrap_pair_model #(
    parameter integer LAT=14, RDL=6, BYTES=4096, CS_HIGH_CYCLES=2,
    parameter bit ALLOW_UNDOCUMENTED_CA45=0
) (
    input wire clk, reset_n, cs_n, ck_en, dq_oe, rwds_oe,
    input wire [7:0] dq_r,dq_f,
    input wire mask_r,mask_f,
    output wire [7:0] read_r,read_f
);
    reg [7:0] memory[0:BYTES-1];
    reg [7:0] pipe_r[0:RDL-1],pipe_f[0:RDL-1];
    reg [47:0] ca=0;
    reg [15:0] cr0=16'h8f1f;
    reg reading=0,registers=0,selected=0;
    integer cycle=0,base=0,high_cycles=100,wrap_bytes=32,index_r,index_f;
    integer unsupported_ca_count=0,transactions=0;
    assign read_r=pipe_r[RDL-1];
    assign read_f=pipe_f[RDL-1];
    function automatic integer location(input integer offset);
        location=(base/wrap_bytes)*wrap_bytes+(base+offset)%wrap_bytes;
    endfunction
    initial begin
        for(integer n=0;n<BYTES;n++) memory[n]=8'ha5;
        for(integer n=0;n<RDL;n++) begin pipe_r[n]=0;pipe_f[n]=0;end
    end
    always @(posedge clk) begin
        for(integer n=RDL-1;n>0;n--) begin pipe_r[n]<=pipe_r[n-1];pipe_f[n]<=pipe_f[n-1];end
        pipe_r[0]<=0;pipe_f[0]<=0;
        if(!reset_n) begin
            cycle=0;selected=0;high_cycles=100;cr0=16'h8f1f;
        end else if(cs_n) begin
            if(ck_en || dq_oe || rwds_oe) $fatal(1,"WRAP_MODEL: activity with CS high");
            cycle=0;selected=0;high_cycles=high_cycles+1;
        end else begin
            if(!selected) begin
                if(high_cycles<CS_HIGH_CYCLES) $fatal(1,"WRAP_MODEL: CS recovery gap");
                selected=1;high_cycles=0;transactions=transactions+1;
            end
            if(ck_en) begin
                if(cycle<3) begin
                    if(!dq_oe || rwds_oe) $fatal(1,"WRAP_MODEL: CA bus ownership");
                    ca={ca[31:0],dq_r,dq_f};
                    if(cycle==2) begin
                        reading=ca[47];registers=ca[46];
                        if(ca[44:34]!=0 || ca[15:3]!=0) $fatal(1,"WRAP_MODEL: reserved address bits");
                        base=int'({ca[33:16],ca[2:0]})*2;
                        if(registers) begin
                            if(reading || base!=4096 || !ca[45]) $fatal(1,"WRAP_MODEL: unsupported register command");
                        end else begin
                            if(ca[45]) begin
                                unsupported_ca_count=unsupported_ca_count+1;
                                if(!ALLOW_UNDOCUMENTED_CA45) $fatal(1,"WRAP_MODEL: memory CA45=1 undocumented by reference die");
                            end
                            if(base<0 || base>=BYTES) $fatal(1,"WRAP_MODEL: die range");
                            case(cr0[1:0])
                                0:wrap_bytes=128;1:wrap_bytes=64;2:wrap_bytes=16;3:wrap_bytes=32;
                            endcase
                        end
                    end
                end else if(registers) begin
                    if(cycle!=3 || !dq_oe || rwds_oe) $fatal(1,"WRAP_MODEL: CR0 write ownership");
                    cr0={dq_r,dq_f};
                    if(cr0[15:2]!=14'h23c7) $fatal(1,"WRAP_MODEL: unsupported CR0 fields");
                end else if(cycle>=LAT) begin
                    index_r=location(2*(cycle-LAT));index_f=location(2*(cycle-LAT)+1);
                    if(index_r>=BYTES || index_f>=BYTES) $fatal(1,"WRAP_MODEL: wrap range");
                    if(reading) begin
                        if(dq_oe || rwds_oe) $fatal(1,"WRAP_MODEL: read contention");
                        pipe_r[0]<=memory[index_r];pipe_f[0]<=memory[index_f];
                    end else begin
                        if(!dq_oe || !rwds_oe) $fatal(1,"WRAP_MODEL: missing write drive");
                        if(!mask_r) memory[index_r]<=dq_r;
                        if(!mask_f) memory[index_f]<=dq_f;
                    end
                end else if(dq_oe || rwds_oe) $fatal(1,"WRAP_MODEL: host drive during latency");
                cycle=cycle+1;
            end
        end
    end
endmodule
