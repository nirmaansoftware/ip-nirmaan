// Self-checking SystemVerilog testbench for irq_ctrl.v (W2-E1), the reference
// answer of the eval case dv/directed-irq-ctrl.
//
// Two lanes run the same directed checks, one with 8 sources and one with 5
// (a count that is not a power of two). Each lane covers reset values;
// write and read back of ENABLE and MODE, with bits N and up reading zero;
// a PENDING write that never sets a bit; high-level detection, which sets the
// bit again at the edge of its own clear while the input holds; rising-edge
// detection, which fires once per edge; detection while disabled, with irq
// and the claim masked for high-level and rising-edge sources alike;
// write-1-to-clear of only the bits written 1; the fixed priority (lowest
// number wins) on irq_id and in a CLAIM read; acknowledge, which clears only
// the named bit and ignores a number of N or more; a detection at the very
// edge of its clear (by PENDING write and by acknowledge), which must leave
// the bit set; reads that change nothing; and reset again.
//
// Every input changes 1 ns after a rising edge and every check samples 1 ns
// after one, so a check sees the registers the last edge wrote.
`timescale 1ns / 1ps
module irq_ctrl_tb_lane #(
    parameter int N = 8
) ();
    localparam logic [1:0] ENABLE = 2'd0, MODE = 2'd1, PENDING = 2'd2, CLAIM = 2'd3;
    localparam logic [31:0] ALL = (N == 32) ? 32'hFFFF_FFFF : ((32'd1 << N) - 32'd1);

    logic         clk = 1'b0;
    logic         rst_n = 1'b0;
    logic [N-1:0] src = '0;
    logic         we = 1'b0;
    logic [1:0]   addr = 2'd0;
    logic [31:0]  wdata = 32'd0;
    logic [31:0]  rdata;
    logic         irq;
    logic [4:0]   irq_id;

    int  errors = 0;
    int  checks = 0;
    bit  done = 1'b0;
    logic [31:0] data;

    irq_ctrl #(.N(N)) dut (
        .clk(clk), .rst_n(rst_n), .src(src), .we(we), .addr(addr), .wdata(wdata),
        .rdata(rdata), .irq(irq), .irq_id(irq_id)
    );

    always #5 clk = ~clk;

    task automatic check(input string what, input logic [31:0] got, input logic [31:0] expected);
        checks++;
        if (got !== expected) begin
            $error("lane N=%0d: %s: got 0x%08h, expected 0x%08h", N, what, got, expected);
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

    // irq, irq_id and the CLAIM read must agree with the expected claim.
    task automatic expect_claim(input string what, input logic valid, input logic [4:0] id);
        check({what, ": irq"}, {31'd0, irq}, {31'd0, valid});
        check({what, ": irq_id"}, {27'd0, irq_id}, {27'd0, id});
        expect_reg({what, ": CLAIM"}, CLAIM, {valid, 26'd0, id});
    endtask

    task automatic reset_dut;
        rst_n = 1'b0;
        step(2);
        rst_n = 1'b1;
    endtask

    // A one-cycle pulse on the given sources, then back to zero.
    task automatic pulse(input logic [31:0] which);
        src = which[N-1:0];
        step();
        src = '0;
        step();
    endtask

    localparam int HI = N - 1;  // the highest-numbered source
    localparam int MID = 2;

    initial begin
        step();
        reset_dut;

        // Reset values.
        expect_reg("ENABLE after reset", ENABLE, 32'd0);
        expect_reg("MODE after reset", MODE, 32'd0);
        expect_reg("PENDING after reset", PENDING, 32'd0);
        expect_claim("after reset", 1'b0, 5'd0);

        // ENABLE and MODE read back; bits N and up read zero.
        write(ENABLE, 32'hFFFF_FFFF);
        expect_reg("ENABLE all ones", ENABLE, ALL);
        write(ENABLE, 32'hA5A5_A5A5);
        expect_reg("ENABLE pattern", ENABLE, 32'hA5A5_A5A5 & ALL);
        write(MODE, 32'h5A5A_5A5A);
        expect_reg("MODE pattern", MODE, 32'h5A5A_5A5A & ALL);
        write(MODE, 32'hFFFF_FFFF);
        expect_reg("MODE all ones", MODE, ALL);
        expect_reg("ENABLE kept by a MODE write", ENABLE, 32'hA5A5_A5A5 & ALL);
        expect_reg("PENDING untouched by register writes", PENDING, 32'd0);
        // Writing ones to PENDING never sets a bit.
        write(PENDING, 32'hFFFF_FFFF);
        expect_reg("PENDING write sets nothing", PENDING, 32'd0);
        expect_claim("nothing pending", 1'b0, 5'd0);
        write(ENABLE, 32'd0);
        write(MODE, 32'd0);

        // High-level detection, disabled: pending sets, irq stays low.
        src[MID] = 1'b1;
        step();
        expect_reg("level detected while disabled", PENDING, 32'd1 << MID);
        expect_claim("level source disabled", 1'b0, 5'd0);
        // A clear while the level holds: the detection at the same edge wins.
        write(PENDING, 32'd1 << MID);
        expect_reg("level held through its clear", PENDING, 32'd1 << MID);
        write(ENABLE, 32'd1 << MID);
        expect_claim("level source enabled", 1'b1, 5'(MID));
        write(CLAIM, MID);
        expect_reg("level held through its acknowledge", PENDING, 32'd1 << MID);
        expect_claim("level still claimed", 1'b1, 5'(MID));
        src[MID] = 1'b0;
        step();
        write(CLAIM, MID);
        expect_reg("level cleared once low", PENDING, 32'd0);
        expect_claim("level cleared", 1'b0, 5'd0);
        // The mask again: with ENABLE cleared, a held level stays pending and silent.
        write(ENABLE, 32'd0);
        src[MID] = 1'b1;
        step(2);
        expect_claim("level masked after enable cleared", 1'b0, 5'd0);
        src[MID] = 1'b0;
        step();
        write(PENDING, 32'd1 << MID);
        expect_reg("level clear after mask check", PENDING, 32'd0);

        // Rising-edge detection: fires once per edge.
        write(MODE, 32'd1 << 1);
        src[1] = 1'b1;
        step();
        expect_reg("edge detected", PENDING, 32'd1 << 1);
        expect_claim("edge source disabled", 1'b0, 5'd0);
        write(PENDING, 32'd1 << 1);
        step(3);
        expect_reg("edge does not fire again while held", PENDING, 32'd0);
        src[1] = 1'b0;
        step(2);
        expect_reg("falling edge detects nothing", PENDING, 32'd0);
        src[1] = 1'b1;
        step();
        expect_reg("second rising edge detected", PENDING, 32'd1 << 1);
        write(ENABLE, 32'd1 << 1);
        expect_claim("edge source enabled", 1'b1, 5'd1);
        // A rising edge at the very edge of a PENDING clear keeps the bit.
        src[1] = 1'b0;
        step();
        src[1] = 1'b1;
        write(PENDING, 32'd1 << 1);
        expect_reg("edge beats a same-edge PENDING clear", PENDING, 32'd1 << 1);
        // And at the very edge of an acknowledge.
        src[1] = 1'b0;
        step();
        src[1] = 1'b1;
        write(CLAIM, 32'd1);
        expect_reg("edge beats a same-edge acknowledge", PENDING, 32'd1 << 1);
        write(CLAIM, 32'd1);
        expect_reg("edge acknowledged", PENDING, 32'd0);
        expect_claim("edge acknowledged", 1'b0, 5'd0);
        src[1] = 1'b0;
        step();

        // Every source in rising-edge mode, every source pending.
        write(MODE, 32'hFFFF_FFFF);
        write(ENABLE, 32'd0);
        pulse(ALL);
        expect_reg("every source pending", PENDING, ALL);
        expect_claim("every source masked", 1'b0, 5'd0);
        // Write-1-to-clear clears only the bits written 1.
        write(PENDING, 32'd1 << MID);
        expect_reg("one bit cleared", PENDING, ALL & ~(32'd1 << MID));
        write(PENDING, 32'd0);
        expect_reg("a write of zero clears nothing", PENDING, ALL & ~(32'd1 << MID));

        // Priority: the lowest-numbered enabled pending source wins.
        write(ENABLE, ALL);
        expect_claim("source 0 first", 1'b1, 5'd0);
        // Out-of-range acknowledges change nothing.
        for (int id = N; id < 32; id++) begin
            write(CLAIM, id);
            expect_reg("acknowledge of N or more ignored", PENDING, ALL & ~(32'd1 << MID));
        end
        // Bits above 4 of an acknowledge are not part of the number.
        write(CLAIM, 32'hFFFF_FFE0);
        expect_reg("acknowledge of source 0 with high bits set", PENDING, ALL & ~(32'd1 << MID) & ~32'd1);
        expect_claim("source 1 next", 1'b1, 5'd1);
        write(CLAIM, 32'd1);
        expect_reg("acknowledge clears only source 1", PENDING, ALL & ~(32'd1 << MID) & ~32'd3);
        expect_claim("source 3 next, 2 already cleared", 1'b1, 5'd3);
        // The mask applies to the claim: with source 3 disabled, the next one up wins.
        write(ENABLE, ALL & ~32'd8);
        expect_claim("disabled source 3 skipped", 1'b1, 5'(N > 4 ? 4 : 0));
        write(ENABLE, 32'd1 << HI);
        expect_claim("only the highest source enabled", 1'b1, 5'(HI));
        write(ENABLE, ALL);
        expect_claim("source 3 again", 1'b1, 5'd3);
        // Reads change nothing.
        expect_reg("CLAIM read twice", CLAIM, {1'b1, 26'd0, 5'd3});
        expect_reg("PENDING after reads", PENDING, ALL & ~(32'd1 << MID) & ~32'd3);
        // Acknowledge each remaining source in claim order.
        for (int id = 3; id < N; id++) begin
            expect_claim("claim order", 1'b1, 5'(id));
            write(CLAIM, id);
        end
        expect_reg("all acknowledged", PENDING, 32'd0);
        expect_claim("all acknowledged", 1'b0, 5'd0);

        // Two sources at once, pulsed together: the lower one is claimed first.
        pulse((32'd1 << HI) | (32'd1 << 1));
        expect_claim("pair: lower first", 1'b1, 5'd1);
        write(CLAIM, 32'd1);
        expect_claim("pair: then the higher", 1'b1, 5'(HI));
        write(PENDING, 32'd1 << HI);
        expect_claim("pair: cleared", 1'b0, 5'd0);

        // Reset again, from a busy state.
        write(MODE, 32'd0);
        src = '1;
        step(2);
        expect_reg("busy before reset", PENDING, ALL);
        src = '0;
        reset_dut;
        expect_reg("ENABLE after the second reset", ENABLE, 32'd0);
        expect_reg("MODE after the second reset", MODE, 32'd0);
        expect_reg("PENDING after the second reset", PENDING, 32'd0);
        expect_claim("after the second reset", 1'b0, 5'd0);

        done = 1'b1;
    end
endmodule

module irq_ctrl_tb;
    logic [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    int checks, errors;

    irq_ctrl_tb_lane #(.N(8)) lane8 ();
    irq_ctrl_tb_lane #(.N(5)) lane5 ();

    initial begin
        wait (lane8.done && lane5.done);
        checks = lane8.checks + lane5.checks;
        errors = lane8.errors + lane5.errors;
        if (checks < 200) begin
            $error("too few checks: %0d", checks);
            errors++;
        end
        if (errors == 0)
            $display("irq_ctrl_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
