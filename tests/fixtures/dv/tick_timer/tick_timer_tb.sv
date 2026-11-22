// Self-checking SystemVerilog testbench for tick_timer.v (RX-E2), the reference
// answer of the eval case dv/coverage-tick-timer.
//
// Two lanes run the same directed checks, one with a 16-bit count and one with
// a 5-bit count (a width that is not a byte). Each lane covers reset values;
// write and read back of CTRL and LOAD, with the bits a register does not store
// reading zero and a write to COUNT changing nothing; the start, which loads
// the count; the count falling one per edge; a one-shot expiry, which sets the
// flag, clears EN and leaves the count at zero; a periodic expiry, which sets
// the flag, reloads the count and keeps EN; the interrupt, masked by IE in
// one-shot and in periodic mode alike; write-1-to-clear that never sets the
// flag; a stop that holds the count; a LOAD write that leaves the count alone;
// a CTRL write that takes the place of an expiry; an expiry at the very edge
// of a clear, which must keep the flag set; reads that change nothing; and
// reset again.
//
// Every input changes 1 ns after a rising edge and every check samples 1 ns
// after one, so a check sees the registers the last edge wrote.
`timescale 1ns / 1ps
module tick_timer_tb_lane #(
    parameter int W = 16
) ();
    localparam logic [1:0] CTRL = 2'd0, LOAD = 2'd1, COUNT = 2'd2, STATUS = 2'd3;
    localparam logic [31:0] M = (W == 32) ? 32'hFFFF_FFFF : ((32'd1 << W) - 32'd1);

    logic        clk = 1'b0;
    logic        rst_n = 1'b0;
    logic        we = 1'b0;
    logic [1:0]  addr = 2'd0;
    logic [31:0] wdata = 32'd0;
    logic [31:0] rdata;
    logic        irq;

    int  errors = 0;
    int  checks = 0;
    bit  done = 1'b0;
    logic [31:0] data;

    tick_timer #(.W(W)) dut (
        .clk(clk), .rst_n(rst_n), .we(we), .addr(addr), .wdata(wdata), .rdata(rdata), .irq(irq)
    );

    always #5 clk = ~clk;

    task automatic check(input string what, input logic [31:0] got, input logic [31:0] expected);
        checks++;
        if (got !== expected) begin
            $error("lane W=%0d: %s: got 0x%08h, expected 0x%08h", W, what, got, expected);
            errors++;
        end
    endtask

    // One rising edge, then 1 ns: the registers it wrote are visible.
    task automatic step(input int cycles = 1);
        repeat (cycles) @(posedge clk);
        #1;
    endtask

    task automatic write(input logic [1:0] a, input logic [31:0] d);
        we = 1'b1;
        addr = a;
        wdata = d;
        step();
        we = 1'b0;
        wdata = 32'd0;
    endtask

    // A read is combinational: no edge.
    task automatic read(input logic [1:0] a, output logic [31:0] d);
        addr = a;
        #1;
        d = rdata;
    endtask

    task automatic expect_reg(input string what, input logic [1:0] a, input logic [31:0] expected);
        read(a, data);
        check(what, data, expected);
    endtask

    task automatic reset_dut();
        rst_n = 1'b0;
        we = 1'b0;
        step(2);
        rst_n = 1'b1;
        step();
    endtask

    // The whole register state in one line: CTRL, COUNT, STATUS and the interrupt.
    task automatic expect_state(input string what, input logic [2:0] ctrl, input logic [31:0] count,
                                input logic expired, input logic irq_v);
        expect_reg({what, ": CTRL"}, CTRL, {29'd0, ctrl});
        expect_reg({what, ": COUNT"}, COUNT, count);
        expect_reg({what, ": STATUS"}, STATUS, {31'd0, expired});
        check({what, ": irq"}, {31'd0, irq}, {31'd0, irq_v});
    endtask

    initial begin
        // --- Reset values -------------------------------------------------------------------------
        repeat (3) @(posedge clk);
        #1;
        rst_n = 1'b1;
        step();
        expect_state("after reset", 3'd0, 32'd0, 1'b0, 1'b0);
        expect_reg("LOAD after reset", LOAD, 32'd0);

        // --- Registers: write and read back, bits a register does not store read zero ---------------
        write(CTRL, 32'h5555_5552);            // MODE only: bits 2 to 0 are 010
        expect_reg("CTRL pattern", CTRL, 32'd2);
        write(CTRL, 32'hAAAA_AAAC);            // IE only
        expect_reg("CTRL pattern 2", CTRL, 32'd4);
        write(CTRL, 32'hFFFF_FFFE);            // MODE and IE, EN clear: nothing starts
        expect_reg("CTRL pattern 3", CTRL, 32'd6);
        write(CTRL, 32'd0);
        write(LOAD, 32'hFFFF_FFFF);
        expect_reg("LOAD all ones", LOAD, M);
        write(LOAD, 32'hAAAA_AAAA);
        expect_reg("LOAD pattern", LOAD, 32'hAAAA_AAAA & M);
        write(LOAD, 32'h5555_5555);
        expect_reg("LOAD pattern 2", LOAD, 32'h5555_5555 & M);
        write(LOAD, 32'd0);
        expect_reg("LOAD zero", LOAD, 32'd0);
        write(STATUS, 32'hFFFF_FFFF);          // a write of ones never sets the flag
        expect_reg("STATUS write never sets", STATUS, 32'd0);

        // --- One-shot, interrupt masked: expiry sets the flag, clears EN, leaves the count at zero ---
        write(LOAD, 32'd3);
        write(CTRL, 32'd1);                     // start: the count loads
        expect_state("one-shot started", 3'b001, 32'd3, 1'b0, 1'b0);
        expect_state("one-shot started again", 3'b001, 32'd3, 1'b0, 1'b0);  // a read changes nothing
        step();
        expect_state("one-shot 2", 3'b001, 32'd2, 1'b0, 1'b0);
        step(2);
        expect_state("one-shot at zero", 3'b001, 32'd0, 1'b0, 1'b0);
        step();                                 // the expiry
        expect_state("one-shot expired", 3'b000, 32'd0, 1'b1, 1'b0);
        step(3);
        expect_state("one-shot stays stopped", 3'b000, 32'd0, 1'b1, 1'b0);
        write(STATUS, 32'hFFFF_FFFE);           // bit 0 clear: nothing changes
        expect_reg("STATUS write of zero", STATUS, 32'd1);
        write(STATUS, 32'd1);
        step(3);
        expect_state("one-shot cleared and quiet", 3'b000, 32'd0, 1'b0, 1'b0);

        // --- One-shot with the interrupt on ---------------------------------------------------------
        write(CTRL, 32'd5);                     // EN and IE: the count loads 3
        step(3);
        expect_state("one-shot IE at zero", 3'b101, 32'd0, 1'b0, 1'b0);
        step();
        expect_state("one-shot IE expired", 3'b100, 32'd0, 1'b1, 1'b1);
        write(STATUS, 32'd1);
        expect_state("one-shot IE cleared", 3'b100, 32'd0, 1'b0, 1'b0);
        write(CTRL, 32'd0);

        // --- Periodic, interrupt masked: expiry reloads the count and keeps EN -----------------------
        write(LOAD, 32'd2);
        write(CTRL, 32'd3);                     // EN and MODE
        expect_state("periodic started", 3'b011, 32'd2, 1'b0, 1'b0);
        step(3);                                // two counts and the expiry
        expect_state("periodic expired", 3'b011, 32'd2, 1'b1, 1'b0);
        check("periodic, IE clear: irq masked", {31'd0, irq}, 32'd0);  // MASKED-PERIODIC-CHECK
        write(STATUS, 32'd1);                   // count 2 to 1 at this edge: no expiry
        expect_state("periodic cleared", 3'b011, 32'd1, 1'b0, 1'b0);
        step(2);
        expect_state("periodic expired again", 3'b011, 32'd2, 1'b1, 1'b0);

        // --- Periodic with the interrupt on ----------------------------------------------------------
        write(CTRL, 32'd7);                     // a CTRL write while running does not restart the count
        expect_state("periodic IE on", 3'b111, 32'd2, 1'b1, 1'b1);
        write(STATUS, 32'd1);
        expect_state("periodic IE cleared", 3'b111, 32'd1, 1'b0, 1'b0);
        step(2);
        expect_state("periodic IE expired", 3'b111, 32'd2, 1'b1, 1'b1);
        write(CTRL, 32'd0);                     // stop: the count holds
        expect_state("stopped", 3'b000, 32'd2, 1'b1, 1'b0);
        step(3);
        expect_state("stopped holds", 3'b000, 32'd2, 1'b1, 1'b0);
        write(STATUS, 32'd1);

        // --- A LOAD write does not change a count in flight -----------------------------------------
        write(LOAD, 32'd4);
        write(CTRL, 32'd3);
        expect_reg("late load: started", COUNT, 32'd4);
        write(LOAD, 32'd9);                     // the count still falls: 4 to 3
        expect_reg("late load: count unchanged", COUNT, 32'd3);
        expect_reg("late load: LOAD stored", LOAD, 32'd9);
        step(3);
        expect_reg("late load: at zero", COUNT, 32'd0);
        step();                                 // the expiry reloads the new value
        expect_state("late load: reloaded", 3'b011, 32'd9, 1'b1, 1'b0);
        write(CTRL, 32'd0);
        write(STATUS, 32'd1);
        write(CTRL, 32'd1);                     // a start loads the stored value
        expect_state("restart loads LOAD", 3'b001, 32'd9, 1'b0, 1'b0);
        write(CTRL, 32'd0);

        // --- A CTRL write takes the place of an expiry ------------------------------------------------
        write(LOAD, 32'd1);
        write(CTRL, 32'd1);
        step();
        expect_state("write wins: at zero", 3'b001, 32'd0, 1'b0, 1'b0);
        write(CTRL, 32'd1);                     // EN already set: no restart, and no expiry at this edge
        expect_state("write wins: no expiry", 3'b001, 32'd0, 1'b0, 1'b0);
        step();
        expect_state("write wins: expiry after", 3'b000, 32'd0, 1'b1, 1'b0);
        write(STATUS, 32'd1);

        // --- An expiry at the very edge of a clear keeps the flag set ---------------------------------
        write(LOAD, 32'd0);
        write(CTRL, 32'd3);                     // periodic with a zero reload: it expires at every edge
        step();
        expect_state("set wins: expired", 3'b011, 32'd0, 1'b1, 1'b0);
        write(STATUS, 32'd1);                   // the clear and the next expiry share an edge
        expect_state("set wins: still set", 3'b011, 32'd0, 1'b1, 1'b0);
        write(CTRL, 32'd0);
        write(STATUS, 32'd1);
        expect_state("set wins: stopped and cleared", 3'b000, 32'd0, 1'b0, 1'b0);

        // --- The widest count: every bit moves, and a COUNT write changes nothing --------------------
        write(LOAD, 32'hFFFF_FFFF);
        write(CTRL, 32'd1);
        expect_reg("full count: started", COUNT, M);
        step(2);
        expect_reg("full count: two down", COUNT, M - 32'd2);
        write(COUNT, 32'd0);                    // read only: the count still falls
        expect_reg("full count: COUNT write ignored", COUNT, M - 32'd3);
        write(CTRL, 32'd0);
        expect_reg("full count: held", COUNT, M - 32'd3);
        write(LOAD, 32'd0);
        write(CTRL, 32'd1);
        expect_reg("full count: restarted at zero", COUNT, 32'd0);
        write(CTRL, 32'd0);

        // --- Reset from a busy state -------------------------------------------------------------------
        write(LOAD, 32'd3);
        write(CTRL, 32'd7);
        step(4);
        expect_state("busy before reset", 3'b111, 32'd3, 1'b1, 1'b1);
        reset_dut;
        expect_state("after the second reset", 3'd0, 32'd0, 1'b0, 1'b0);
        expect_reg("LOAD after the second reset", LOAD, 32'd0);

        done = 1'b1;
    end
endmodule

module tick_timer_tb;
    logic [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    int checks, errors;

    tick_timer_tb_lane #(.W(16)) lane16 ();
    tick_timer_tb_lane #(.W(5)) lane5 ();

    initial begin
        wait (lane16.done && lane5.done);
        checks = lane16.checks + lane5.checks;
        errors = lane16.errors + lane5.errors;
        if (checks < 150) begin
            $error("too few checks: %0d", checks);
            errors++;
        end
        if (errors == 0)
            $display("tick_timer_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
