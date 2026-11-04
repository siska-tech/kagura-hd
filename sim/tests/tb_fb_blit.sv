`timescale 1ns/1ps
// COPY command -> shared fill/copy walker -> real arbiter/controller -> CA model.
// upload_data has the same one-edge-later capture as the register endpoint.
module tb_fb_blit;
    reg clk=0,reset=1,valid=0;
    always #5 clk=~clk;
    reg [127:0] command=0;
    reg [511:0] upload_data=0;
    wire ready,done,read_result,host_valid,host_write;
    wire [7:0] error;
    wire [15:0] tag;
    wire [19:0] host_addr;
    wire [4:0] host_words;
    wire [511:0] host_wdata,host_rdata,read_data;
    wire [63:0] host_mask;
    wire [2:0] req_ready,rsp_done,rsp_error;
    integer cycle=0,requests=0,cases=0,interleaves=0,full_cycles=0;
    reg competing=0,other0=0,other1=0,inject_read_error=0,inject_write_error=0,window_held=0,inflight_write=0;
    kagura_fb_commands commands(
        .clk,.reset,.valid,.ready,.command,.upload_data,.done,.error,.tag,
        .read_data,.read_result,.host_valid,.host_ready(req_ready[2]),
        .host_write,.host_addr,.host_words,.host_wdata,.host_mask,
        .host_done(rsp_done[2]),
        .host_error(rsp_error[2] || (inject_read_error && !inflight_write) || (inject_write_error && inflight_write)),
        .host_rdata,.present_valid(),.present_ready(1'b1),.present_done(1'b0),.present_page(),.present_palette());
    wire ctrl_valid,ctrl_ready,ctrl_write,ctrl_done,ctrl_error,initialized;
    wire [19:0] ctrl_addr;
    wire [4:0] ctrl_words;
    wire [511:0] ctrl_wdata;
    wire [63:0] ctrl_mask;
    kagura_fb_arbiter arbiter(
        .clk,.reset,.req_valid({host_valid,other1,other0}),
        .req_ready,.req_write({host_write,2'b00}),
        .req_addr({host_addr,20'd60016,20'd60000}),.req_words({host_words,5'd1,5'd16}),
        .req_wdata({host_wdata,1024'd0}),.req_mask({host_mask,128'd0}),
        .rsp_done,.rsp_error,.rsp_data(host_rdata),
        .valid(ctrl_valid),.ready(ctrl_ready),.write(ctrl_write),.addr(ctrl_addr),
        .words(ctrl_words),.wdata(ctrl_wdata),.mask(ctrl_mask),
        .done(ctrl_done),.error(ctrl_error),.rdata(ctrl_rdata));
    wire [511:0] ctrl_rdata;
    wire phy_reset_n,phy_cs_n,phy_ck_en,phy_dq_oe,phy_rwds_oe;
    wire phy_rwds_o_rise,phy_rwds_o_fall,phy_dq_tx,phy_rwds_tx;
    wire [7:0] phy_dq_o_rise,phy_dq_o_fall,phy_dq_i_rise,phy_dq_i_fall;
    kagura_fb_burst_ctrl #(.INIT_CYCLES(16)) controller(
        .clk,.reset,.valid(ctrl_valid),.ready(ctrl_ready),.write(ctrl_write),.addr(ctrl_addr),
        .words(ctrl_words),.wdata(ctrl_wdata),.mask(ctrl_mask),.done(ctrl_done),.error(ctrl_error),.rdata(ctrl_rdata),
        .initialized,.phy_reset_n,.phy_cs_n,.phy_ck_en,.phy_dq_oe,.phy_dq_o_rise,.phy_dq_o_fall,
        .phy_rwds_oe,.phy_rwds_o_rise,.phy_rwds_o_fall,.phy_dq_tx,.phy_rwds_tx,.phy_dq_i_rise,.phy_dq_i_fall);
    kagura_hyperram_pair_model #(.BYTES(262144),.MAX_WORDS(16)) model(
        .clk,.reset_n(phy_reset_n),.cs_n(phy_cs_n),.ck_en(phy_ck_en),
        .dq_oe(phy_dq_oe),.rwds_oe(phy_rwds_oe),.dq_r(phy_dq_o_rise),.dq_f(phy_dq_o_fall),
        .mask_r(phy_rwds_o_rise),.mask_f(phy_rwds_o_fall),.read_r(phy_dq_i_rise),.read_f(phy_dq_i_fall));
    always @(posedge clk) begin
        cycle<=cycle+1;
        if(reset) begin other0<=0;other1<=0;end
        else begin
            if(req_ready[0]) other0<=0;
            else if(!other0 && competing && cycle%211<37) other0<=1;
            if(req_ready[1]) other1<=0;
            else if(!other1 && competing && cycle%173<11) other1<=1;
        end
        if(reset) begin upload_data<=0;window_held<=0;end
        else begin
            if(read_result) begin
                if(read_data!==saved_response) $fatal(1,"response changed before upload capture");
                upload_data<=read_data;window_held<=1;
            end
            if(rsp_done[2] && !inflight_write) saved_response<=host_rdata;
            if(window_held && (req_ready[0] || req_ready[1])) interleaves<=interleaves+1;
            if(host_valid && req_ready[2]) begin
                requests<=requests+1;inflight_write<=host_write;
                if(host_addr*4+host_words*4>230400) $fatal(1,"BLIT outside pages");
                if(host_write) begin
                    if(!window_held) $fatal(1,"write before window capture");
                    window_held<=0;
                end
            end
        end
    end
    reg [511:0] saved_response;
    reg [7:0] expected[0:230399],snapshot[0:230399];
    task run_copy(input integer sp,dp,sx,sy,dx,dy,w,h,expected_error);
        integer before_count,start_cycle,sa,da,value;
        begin
            @(negedge clk);wait(ready);before_count=requests;start_cycle=cycle;
            for(integer i=0;i<230400;i=i+1) snapshot[i]=model.memory[i];
            command=0;command[7:0]=6;command[15:8]=8'(sp+2*dp);command[31:16]=16'(cases);
            command[47:32]=16'(sx);command[63:48]=16'(sy);command[79:64]=16'(dx);command[95:80]=16'(dy);
            command[111:96]=16'(w);command[127:112]=16'(h);valid=1;
            @(negedge clk);valid=0;
            wait(done);
            if(error!=8'(expected_error) || tag!=16'(cases))
                $fatal(1,"BLIT error case=%0d got=%0d expected=%0d",cases,error,expected_error);
            if(w==640 && h==360) full_cycles=cycle-start_cycle;
            if(expected_error==0) begin
                for(integer yy=0;yy<h;yy=yy+1) for(integer xx=0;xx<w;xx=xx+1) begin
                    sa=sp*115200+(sy+yy)*320+(sx+xx)/2;
                    da=dp*115200+(dy+yy)*320+(dx+xx)/2;
                    value=((sx+xx)%2==0) ? int'(snapshot[sa][7:4]) : int'(snapshot[sa][3:0]);
                    if((dx+xx)%2==0) expected[da][7:4]=4'(value);else expected[da][3:0]=4'(value);
                end
            end else if(expected_error!=4 && requests!=before_count) $fatal(1,"invalid command reached memory");
            @(negedge clk);
            if(expected_error!=4) for(integer i=0;i<230400;i=i+1)
                if(model.memory[i]!==expected[i])
                    $fatal(1,"BLIT case=%0d at byte %0d got=%h expected=%h sx=%0d dx=%0d w=%0d",cases,i,model.memory[i],expected[i],sx,dx,w);
            cases=cases+1;
        end
    endtask
    task synchronize_reference;
        for(integer i=0;i<230400;i=i+1) expected[i]=model.memory[i];
    endtask
    initial begin
        repeat(3) @(negedge clk);reset=0;wait(initialized);
        @(negedge clk);
        for(integer i=0;i<262144;i=i+1) model.memory[i]=8'($urandom);
        synchronize_reference();
        competing=0;run_copy(0,1,0,0,0,0,640,360,0);competing=1;
        run_copy(0,0,0,0,0,16,640,344,0);run_copy(0,0,0,16,0,0,640,344,0);
        for(integer phase=0;phase<4;phase=phase+1)
            for(integer w=2;w<=258;w=w+2) begin
                run_copy(0,0,phase*2,12,phase*2+8,12,w,2,0);
                run_copy(0,0,phase*2+8,12,phase*2,12,w,2,0);
            end
        for(integer i=0;i<100;i=i+1) begin
            automatic integer sx=$urandom_range(0,35)*8+2*(i%4);
            automatic integer dx=$urandom_range(0,35)*8+2*(i%4);
            run_copy(i%2,(i/2)%2,sx,$urandom_range(0,320),dx,$urandom_range(0,320),$urandom_range(1,160)*2,$urandom_range(1,40),0);
        end
        run_copy(1,1,638,359,638,359,2,1,0);run_copy(0,1,638,359,638,359,0,0,0);
        run_copy(0,1,0,0,2,0,2,1,2);run_copy(0,1,1,0,1,0,2,1,2);
        run_copy(0,1,0,0,0,0,3,1,2);run_copy(0,1,638,0,638,0,4,1,3);
        run_copy(0,1,0,359,0,0,2,2,3);run_copy(0,1,0,0,0,359,2,2,3);
        run_copy(0,1,0,0,0,0,65528,1,3);run_copy(0,1,0,0,0,0,2,65535,3);
        run_copy(0,2,0,0,0,0,2,1,2);run_copy(0,1,640,0,0,0,0,1,3);
        inject_read_error=1;run_copy(0,1,0,0,0,0,128,2,4);inject_read_error=0;
        synchronize_reference();
        inject_write_error=1;run_copy(0,1,0,0,0,0,128,2,4);inject_write_error=0;
        synchronize_reference();
        // Cancel an actual pending read, then prove clean command recovery.
        @(negedge clk);command=128'h0002_0080_0000_0000_0000_0000_ffff_0206;valid=1;
        @(negedge clk);valid=0;wait(host_valid && req_ready[2]);
        @(negedge clk);reset=1;repeat(3) @(negedge clk);reset=0;wait(initialized);
        run_copy(0,1,0,0,0,0,128,2,0);
        if(interleaves==0) $fatal(1,"no reads interleaved between copy read/write");
        $display("PASS tb_fb_blit: %0d cases; pixel oracle, all byte phases, overlaps, range/alignment, errors/reset, %0d interleaves; isolated full=%0d cycles",cases,interleaves,full_cycles);
        $finish;
    end
    initial begin #200000000;$fatal(1,"BLIT watchdog cases=%0d cmd_state=%0d engine_state=%0d arb_state=%0d ctrl_state=%0d ctrl_tick=%0d ctrl_valid=%0d ready=%0d req=%b owner=%0d",cases,commands.state,commands.fill.state,arbiter.state,controller.state,controller.tick,ctrl_valid,ctrl_ready,arbiter.req_valid,arbiter.owner);end
endmodule
