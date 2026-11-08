`timescale 1ns/1ps
// Passive observation of the unchanged CSR/executor integration fixture.
// No CSR, FPGA netlist, production port, or hardware timing is changed.
module tb_fb_ack_observe #(parameter integer ACK_DELAY=0);
    tb_fb_command_queue #(.DEPTH(8),.REGISTER_HEAD(1),.TEST_ACK_DELAY(ACK_DELAY)) fixture();
    longint unsigned cycles=0,hold_cycles=0,blocked_cycles=0;
    longint unsigned blocked_runs=0,held_without_younger=0;
    bit was_blocked=0;
    wire blocked=fixture.regs.completed && fixture.regs.queue_count!=0 && !fixture.regs.active;
    always @(posedge fixture.clk) begin
        if(!fixture.reset) begin
            cycles<=cycles+1;
            if(fixture.regs.completed) hold_cycles<=hold_cycles+1;
            if(fixture.regs.completed && fixture.regs.queue_count==0)
                held_without_younger<=held_without_younger+1;
            if(blocked) begin
                blocked_cycles<=blocked_cycles+1;
                if(!was_blocked) blocked_runs<=blocked_runs+1;
                if(fixture.valid) $fatal(1,"dispatch while completion awaits ACK");
            end
            was_blocked<=blocked;
        end else was_blocked<=0;
    end
    final begin
        if(blocked_cycles==0 || held_without_younger==0 || blocked_runs<7)
            $fatal(1,"observer did not exercise both queued and empty completion holds");
        if(hold_cycles!=blocked_cycles+held_without_younger)
            $fatal(1,"completion hold classification mismatch");
        $display("ACK_OBSERVE cycles=%0d completion_hold=%0d blocked_dispatch=%0d no_younger=%0d blocked_runs=%0d",
            cycles,hold_cycles,blocked_cycles,held_without_younger,blocked_runs);
        $display("PASS: passive ACK dispatch observer; simulation cycles, not hardware cycles");
    end
endmodule
