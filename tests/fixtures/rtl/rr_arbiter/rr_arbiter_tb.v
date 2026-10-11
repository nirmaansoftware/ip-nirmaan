// Self-checking testbench for rr_arbiter.v.
//
// Two arbiters run side by side: the default N 4, and N 5 (not a power of
// two, so the pointer wraps early). Each lane keeps a reference pointer and,
// on every rising edge, checks that the grant is exactly the first request
// at or after the pointer (so it is one-hot or zero and only to a requester),
// and that no held request has waited N cycles or more (fairness).
//
// Directed phases cover reset, no requests, each requester alone, everyone
// requesting (strict rotation), a requester that holds its request while the
// others come and go, and reset in the middle of traffic. A random phase
// follows. Coverage counters prove each lane saw every case.
//
// Inputs are driven just after the falling edge; the lanes compare on the
// rising edge, before the pointer updates.
`timescale 1ns / 1ps
module rr_arbiter_tb_lane #(
    parameter N = 4
) (
    input wire         clk,
    input wire         rst_n,
    input wire [N-1:0] req
);
    wire [N-1:0] grant;

    rr_arbiter #(.N(N)) dut (.clk(clk), .rst_n(rst_n), .req(req), .grant(grant));

    integer ptr = 0;
    integer errors = 0;
    integer checks = 0;
    integer waited [0:N-1];
    integer grants [0:N-1];
    integer max_wait = 0;
    integer seen_idle = 0;
    integer seen_all = 0;
    integer i, w;
    reg [N-1:0] expected;

    task automatic check(input [255:0] what, input [31:0] got, input [31:0] expected_value);
        begin
            checks = checks + 1;
            if (got !== expected_value) begin
                $error("N %0d: %0s: got 0x%0h, expected 0x%0h", N, what, got, expected_value);
                errors = errors + 1;
            end
        end
    endtask

    initial
        for (i = 0; i < N; i = i + 1) begin
            waited[i] = 0;
            grants[i] = 0;
        end

    always @(posedge clk) begin
        if (!rst_n) begin
            ptr = 0;
            for (i = 0; i < N; i = i + 1)
                waited[i] = 0;
        end else begin
            // The reference: the first request at or after the pointer wins.
            expected = {N{1'b0}};
            w = -1;
            for (i = 0; i < N; i = i + 1)
                if (w < 0 && req[(ptr + i) % N])
                    w = (ptr + i) % N;
            if (w >= 0)
                expected[w] = 1'b1;
            check("grant", {{(32-N){1'b0}}, grant}, {{(32-N){1'b0}}, expected});
            if (req == {N{1'b0}}) seen_idle = seen_idle + 1;
            if (req == {N{1'b1}}) seen_all = seen_all + 1;
            // Fairness: count the cycles each held request has waited.
            for (i = 0; i < N; i = i + 1) begin
                if (req[i] && !grant[i]) begin
                    waited[i] = waited[i] + 1;
                    if (waited[i] > max_wait)
                        max_wait = waited[i];
                    if (waited[i] >= N) begin
                        $error("N %0d: requester %0d waited %0d cycles", N, i, waited[i]);
                        errors = errors + 1;
                    end
                end else begin
                    waited[i] = 0;
                end
                if (grant[i])
                    grants[i] = grants[i] + 1;
            end
            if (w >= 0)
                ptr = (w + 1) % N;
        end
    end

    // Called at the end: every case must have happened at least once.
    task automatic check_coverage;
        begin
            check("covered: no requests", {31'd0, seen_idle > 0}, 32'd1);
            check("covered: everyone requesting", {31'd0, seen_all > 0}, 32'd1);
            check("covered: the longest fair wait, N-1 cycles", max_wait, N - 1);
            for (i = 0; i < N; i = i + 1)
                check("covered: every requester granted", {31'd0, grants[i] > 0}, 32'd1);
        end
    endtask
endmodule

module rr_arbiter_tb;
    reg       clk = 1'b0;
    reg       rst_n = 1'b0;
    reg [3:0] req4 = 4'd0;
    reg [4:0] req5 = 5'd0;
    wire [3:0] grant4 = lane4.grant;
    integer   i;
    integer   seed = 26;
    integer   direct_errors = 0;

    rr_arbiter_tb_lane #(.N(4)) lane4 (.clk(clk), .rst_n(rst_n), .req(req4));
    rr_arbiter_tb_lane #(.N(5)) lane5 (.clk(clk), .rst_n(rst_n), .req(req5));

    always #5 clk = ~clk;

    task automatic cycle(input [3:0] r4, input [4:0] r5);
        begin
            req4 = r4;
            req5 = r5;
            @(negedge clk);
        end
    endtask

    task automatic reset_dut;
        begin
            rst_n = 1'b0;
            req4 = 4'd0;
            req5 = 5'd0;
            repeat (2) @(negedge clk);
            rst_n = 1'b1;
        end
    endtask

    task automatic expect_grant(input [3:0] expected);
        begin
            #1;
            if (grant4 !== expected) begin
                $error("rotation with everyone requesting: got %b, expected %b", grant4, expected);
                direct_errors = direct_errors + 1;
            end
        end
    endtask

    initial begin
        @(negedge clk);
        reset_dut;

        // After reset, with everyone requesting, requester 0 wins and then
        // requester 1: the winner drops to the lowest priority.
        req4 = 4'b1111;
        expect_grant(4'b0001);
        @(negedge clk);
        expect_grant(4'b0010);
        @(negedge clk);

        // No requests: no grant.
        cycle(4'd0, 5'd0);
        cycle(4'd0, 5'd0);
        // Each requester alone, twice in a row.
        for (i = 0; i < 5; i = i + 1) begin
            cycle(4'd1 << i, 5'd1 << i);
            cycle(4'd1 << i, 5'd1 << i);
        end
        // Everyone requesting: strict rotation, and each waits exactly N-1.
        for (i = 0; i < 12; i = i + 1)
            cycle(4'b1111, 5'b11111);
        // Requester 2 holds its request while the others come and go.
        for (i = 0; i < 40; i = i + 1)
            cycle(4'b0100 | $random(seed), 5'b00100 | $random(seed));
        // Reset in the middle of traffic returns priority to requester 0.
        reset_dut;
        cycle(4'b1010, 5'b10100);
        // Random traffic, from sparse to dense requests.
        for (i = 0; i < 3000; i = i + 1)
            case ((i / 300) % 3)
                0: cycle($random(seed) & $random(seed), $random(seed) & $random(seed));
                1: cycle($random(seed), $random(seed));
                default: cycle($random(seed) | $random(seed), $random(seed) | $random(seed));
            endcase
        cycle(4'd0, 5'd0);

        lane4.check_coverage;
        lane5.check_coverage;
        if (lane4.errors + lane5.errors + direct_errors == 0)
            $display("rr_arbiter_tb: PASS (%0d checks)", lane4.checks + lane5.checks);
        $finish;
    end
endmodule
