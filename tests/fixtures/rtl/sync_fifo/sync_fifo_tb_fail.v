// A testbench that is wrong on purpose: sync_fifo_tb.v with one bad
// expectation. It expects a full FIFO of depth 8 to hold 9 entries instead of
// 8. Used to prove a failing simulation is a recorded, failed run. Everything
// else is identical.
//
// Two FIFOs run side by side on the same stimulus: the default DEPTH 8 by
// WIDTH 8, and DEPTH 5 by WIDTH 12 (not a power of two, so the pointers wrap
// early). Each lane keeps a reference queue and, on every rising edge, checks
// full, empty, count and (when not empty) rd_data against it.
//
// Directed phases cover reset values, filling to full, a write while full
// (overflow, dropped), draining to empty, a read while empty (underflow,
// dropped), a write and a read together when empty, when full and in between,
// pointer wrap-around, and reset in the middle of traffic. A random phase
// follows. Coverage counters prove each lane saw every corner case.
//
// Inputs are driven just after the falling edge; the lanes compare on the
// rising edge, before the design's registers update.
`timescale 1ns / 1ps
module sync_fifo_tb_lane #(
    parameter DEPTH = 8,
    parameter WIDTH = 8
) (
    input wire             clk,
    input wire             rst_n,
    input wire             wr_en,
    input wire             rd_en,
    input wire [WIDTH-1:0] wr_data
);
    localparam CW = $clog2(DEPTH + 1);

    wire             full;
    wire             empty;
    wire [WIDTH-1:0] rd_data;
    wire [CW-1:0]    count;

    sync_fifo #(.DEPTH(DEPTH), .WIDTH(WIDTH)) dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_data(wr_data), .full(full),
        .rd_en(rd_en), .rd_data(rd_data), .empty(empty), .count(count)
    );

    // The reference queue: a ring of DEPTH words.
    reg [WIDTH-1:0] model [0:DEPTH-1];
    integer head = 0;
    integer used = 0;
    integer errors = 0;
    integer checks = 0;
    // Coverage: corner cases this lane actually exercised.
    integer seen_full = 0;
    integer seen_overflow = 0;
    integer seen_underflow = 0;
    integer seen_both_full = 0;
    integer seen_both_empty = 0;
    integer seen_both_mid = 0;
    integer seen_wrap = 0;
    integer reads = 0;

    task automatic check(input [255:0] what, input [31:0] got, input [31:0] expected);
        begin
            checks = checks + 1;
            if (got !== expected) begin
                $error("DEPTH %0d: %0s: got 0x%0h, expected 0x%0h", DEPTH, what, got, expected);
                errors = errors + 1;
            end
        end
    endtask

    reg wr_ok, rd_ok;
    always @(posedge clk) begin
        if (!rst_n) begin
            head = 0;
            used = 0;
        end else begin
            check("count", {{(32-CW){1'b0}}, count}, used);
            check("full", {31'd0, full}, {31'd0, used == DEPTH});
            check("empty", {31'd0, empty}, {31'd0, used == 0});
            if (used > 0)
                check("rd_data (oldest entry)", {{(32-WIDTH){1'b0}}, rd_data},
                      {{(32-WIDTH){1'b0}}, model[head]});
            wr_ok = wr_en && used < DEPTH;
            rd_ok = rd_en && used > 0;
            if (used == DEPTH) seen_full = seen_full + 1;
            if (wr_en && used == DEPTH) seen_overflow = seen_overflow + 1;
            if (rd_en && used == 0) seen_underflow = seen_underflow + 1;
            if (wr_en && rd_en && used == DEPTH) seen_both_full = seen_both_full + 1;
            if (wr_en && rd_en && used == 0) seen_both_empty = seen_both_empty + 1;
            if (wr_en && rd_en && used > 0 && used < DEPTH) seen_both_mid = seen_both_mid + 1;
            if (rd_ok && head == DEPTH - 1) seen_wrap = seen_wrap + 1;
            if (wr_ok)
                model[(head + used) % DEPTH] = wr_data;
            if (rd_ok) begin
                head = (head + 1) % DEPTH;
                reads = reads + 1;
            end
            used = used + (wr_ok ? 1 : 0) - (rd_ok ? 1 : 0);
        end
    end

    // Called at the end: every corner case must have happened at least once.
    task automatic check_coverage;
        begin
            check("covered: full", {31'd0, seen_full > 0}, 32'd1);
            check("covered: write while full", {31'd0, seen_overflow > 0}, 32'd1);
            check("covered: read while empty", {31'd0, seen_underflow > 0}, 32'd1);
            check("covered: write and read when full", {31'd0, seen_both_full > 0}, 32'd1);
            check("covered: write and read when empty", {31'd0, seen_both_empty > 0}, 32'd1);
            check("covered: write and read in between", {31'd0, seen_both_mid > 0}, 32'd1);
            check("covered: pointer wrap", {31'd0, seen_wrap > 0}, 32'd1);
        end
    endtask
endmodule

module sync_fifo_tb_fail;
    localparam W = 12;

    reg          clk = 1'b0;
    reg          rst_n = 1'b0;
    reg          wr_en = 1'b0;
    reg          rd_en = 1'b0;
    reg  [W-1:0] wr_data = {W{1'b0}};
    integer      i;
    integer      seed = 26;
    integer      direct_errors = 0;

    sync_fifo_tb_lane #(.DEPTH(8), .WIDTH(8)) lane8 (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .rd_en(rd_en), .wr_data(wr_data[7:0]));
    sync_fifo_tb_lane #(.DEPTH(5), .WIDTH(W)) lane5 (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .rd_en(rd_en), .wr_data(wr_data));

    always #5 clk = ~clk;

    // One cycle of stimulus, driven after the falling edge.
    task automatic cycle(input we, input re);
        begin
            wr_en = we;
            rd_en = re;
            wr_data = wr_data + 12'h135;
            @(negedge clk);
        end
    endtask

    task automatic reset_dut;
        begin
            rst_n = 1'b0;
            wr_en = 1'b0;
            rd_en = 1'b0;
            repeat (2) @(negedge clk);
            rst_n = 1'b1;
        end
    endtask

    initial begin
        @(negedge clk);
        reset_dut;
        cycle(1'b0, 1'b0);

        // Fill past full: the extra writes are overflow and must be dropped.
        for (i = 0; i < 10; i = i + 1)
            cycle(1'b1, 1'b0);
        // A full FIFO of depth 8 holds exactly 8 entries.
        if (lane8.dut.count !== 4'd9) begin  // wrong on purpose
            $error("count when full: got %0d, expected 9", lane8.dut.count);
            direct_errors = direct_errors + 1;
        end
        // Write and read together while full: only the read happens.
        cycle(1'b1, 1'b1);
        cycle(1'b1, 1'b1);
        // Drain past empty: the extra reads are underflow and must be dropped.
        for (i = 0; i < 10; i = i + 1)
            cycle(1'b0, 1'b1);
        // Write and read together while empty: only the write happens.
        cycle(1'b1, 1'b1);
        cycle(1'b0, 1'b0);
        // Steady streaming at half occupancy, wrapping the pointers many times.
        cycle(1'b1, 1'b0);
        cycle(1'b1, 1'b0);
        for (i = 0; i < 30; i = i + 1)
            cycle(1'b1, 1'b1);
        // Reset in the middle of traffic empties both FIFOs.
        cycle(1'b1, 1'b0);
        reset_dut;
        cycle(1'b0, 1'b1);

        // Random traffic, biased in turn towards filling and draining.
        for (i = 0; i < 3000; i = i + 1)
            if ((i / 250) % 2 == 0)
                cycle(($random(seed) % 4) != 0, ($random(seed) % 4) == 0);
            else
                cycle(($random(seed) % 4) == 0, ($random(seed) % 4) != 0);
        cycle(1'b0, 1'b0);

        lane8.check_coverage;
        lane5.check_coverage;
        if (lane8.reads < 500 || lane5.reads < 500) begin
            $error("too few reads: %0d and %0d", lane8.reads, lane5.reads);
            direct_errors = direct_errors + 1;
        end
        if (lane8.errors + lane5.errors + direct_errors == 0)
            $display("sync_fifo_tb_fail: PASS (%0d checks)", lane8.checks + lane5.checks);
        $finish;
    end
endmodule
