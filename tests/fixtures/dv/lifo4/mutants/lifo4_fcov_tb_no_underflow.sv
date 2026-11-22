// Mutant stimulus of lifo4_fcov_tb.sv: the call of scn_underflow is taken out, so the run never
// reaches a pop with the stack empty.
// The held-out stimulus of the eval case dv/fcov-lifo4 (RX-E4): it drives lifo4 through
// the scenarios the requirement matrix names and judges the seat's coverage model
// lifo4_fcov by what the model reports after the last cycle. It checks nothing else, so a
// run that fails fails because the model reports a hole, or plans too few bins.
//
// Every input changes 1 ns after a rising edge, so the model samples settled values.
// Each scenario is one line of the main sequence, so a mutant of this file takes one
// line out and leaves a stimulus that never reaches that scenario.
`timescale 1ns / 1ps
module lifo4_fcov_tb;
    logic       clk = 1'b0;
    logic       rst_n = 1'b0;
    logic       push = 1'b0;
    logic       pop = 1'b0;
    logic [7:0] din = 8'd0;
    wire  [7:0] dout;
    wire  [2:0] count;
    wire        empty, full, err;
    int         planned, holes;
    int         checks, errors;
    logic [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line

    lifo4 dut (.clk(clk), .rst_n(rst_n), .push(push), .pop(pop), .din(din), .dout(dout), .count(count),
               .empty(empty), .full(full), .err(err));
    lifo4_fcov fcov (.clk(clk), .rst_n(rst_n), .push(push), .pop(pop), .din(din), .dout(dout), .count(count),
                     .empty(empty), .full(full), .err(err), .planned(planned), .holes(holes));

    always #5 clk = ~clk;

    // One rising edge with the given request, then 1 ns: the registers it wrote are visible.
    task automatic cycle(input logic p, input logic q, input logic [7:0] d);
        push = p;
        pop = q;
        din = d;
        @(posedge clk);
        #1;
        push = 1'b0;
        pop = 1'b0;
    endtask

    task automatic reset_dut;
        rst_n = 1'b0;
        repeat (2) @(posedge clk);
        #1;
        rst_n = 1'b1;
        repeat (2) @(posedge clk);
        #1;
    endtask

    task automatic scn_underflow;    // a pop with the stack empty
        cycle(1'b0, 1'b1, 8'h00);
    endtask
    task automatic scn_both_empty;   // a push and a pop with the stack empty
        cycle(1'b1, 1'b1, 8'hA1);
    endtask
    task automatic scn_pop_last;     // a pop that empties the stack
        cycle(1'b0, 1'b1, 8'h00);
    endtask
    task automatic scn_fill;         // four pushes: every occupancy from 0 to 4
        cycle(1'b1, 1'b0, 8'h11);
        cycle(1'b1, 1'b0, 8'h22);
        cycle(1'b1, 1'b0, 8'h33);
        cycle(1'b1, 1'b0, 8'h44);
    endtask
    task automatic scn_overflow;     // a push with the stack full
        cycle(1'b1, 1'b0, 8'h55);
    endtask
    task automatic scn_both_full;    // a push and a pop with the stack full
        cycle(1'b1, 1'b1, 8'h66);
    endtask
    task automatic scn_pop_two;      // two pops from a full stack
        cycle(1'b0, 1'b1, 8'h00);
        cycle(1'b0, 1'b1, 8'h00);
    endtask
    task automatic scn_both_mid;     // a push and a pop with the stack neither empty nor full
        cycle(1'b1, 1'b1, 8'h77);
    endtask
    task automatic scn_reset_busy;   // a reset while the stack holds a word
        rst_n = 1'b0;
        repeat (2) @(posedge clk);
        #1;
        rst_n = 1'b1;
    endtask

    initial begin
        reset_dut;
        scn_both_empty;
        scn_pop_last;
        scn_fill;
        scn_overflow;
        scn_both_full;
        scn_pop_two;
        scn_both_mid;
        scn_reset_busy;
        repeat (3) @(posedge clk);
        #1;

        checks = 2;
        errors = 0;
        if (planned < 15) begin
            $error("the model plans %0d bins; the requirement matrix names 15", planned);
            errors++;
        end
        if (holes != 0) begin
            $error("the model reports %0d planned bins not hit", holes);
            errors++;
        end
        if (errors == 0)
            $display("lifo4_fcov_tb: PASS (%0d bins planned, none left)", planned);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, checks - errors, errors);
        $finish;
    end
endmodule
