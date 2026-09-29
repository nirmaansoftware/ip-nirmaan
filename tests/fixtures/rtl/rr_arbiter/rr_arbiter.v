// Round-robin arbiter for N requesters.
// An M26 fixture: see interface_spec.md and microarchitecture.md.
//
// * Each cycle, at most one requester is granted: the first one with its
//   request high, searching upwards from the priority pointer and wrapping.
// * The grant is combinational (same cycle as the request). On every rising
//   edge with a grant, the pointer moves to one past the granted requester,
//   so the winner has the lowest priority next.
// * Fairness: a requester that holds its request high is granted within N
//   cycles, whatever the others do.
// * rst_n is synchronous and active low; after reset requester 0 has the
//   highest priority.
`timescale 1ns / 1ps
module rr_arbiter #(
    parameter N = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [N-1:0] req,
    output reg  [N-1:0] grant
);
    localparam IW = $clog2(N);
    localparam [IW-1:0] LAST = N[IW-1:0] - 1'b1;

    // The requester with the highest priority this cycle.
    reg [IW-1:0] ptr;
    // The granted requester's index, valid when grant is not zero.
    reg [IW-1:0] winner;

    // Search from ptr upwards, wrapping after the last requester; the first
    // request found wins.
    integer k;
    reg [IW-1:0] idx;
    reg          found;
    always @(*) begin
        grant = {N{1'b0}};
        winner = {IW{1'b0}};
        found = 1'b0;
        idx = ptr;
        for (k = 0; k < N; k = k + 1) begin
            if (!found && req[idx]) begin
                grant[idx] = 1'b1;
                winner = idx;
                found = 1'b1;
            end
            idx = (idx == LAST) ? {IW{1'b0}} : idx + 1'b1;
        end
    end

    // The winner drops to the lowest priority.
    always @(posedge clk) begin
        if (!rst_n)
            ptr <= {IW{1'b0}};
        else if (found)
            ptr <= (winner == LAST) ? {IW{1'b0}} : winner + 1'b1;
    end

`ifdef FORMAL
    // Properties, proven by rr_arbiter.sby for any request sequence.
    reg f_past_valid = 1'b0;
    always @(posedge clk)
        f_past_valid <= 1'b1;

    // The first cycle is in reset.
    always @(*)
        if (!f_past_valid)
            assume (!rst_n);

    // How many cycles each requester has waited with its request held high,
    // 8 bits per requester.
    reg [8*N-1:0] f_wait;
    // The distance from the pointer up to requester i, wrapping.
    function integer f_dist(input integer i);
        f_dist = (i >= ptr) ? i - ptr : N + i - ptr;
    endfunction

    integer f_i;
    always @(posedge clk) begin
        for (f_i = 0; f_i < N; f_i = f_i + 1)
            if (!rst_n || !req[f_i] || grant[f_i])
                f_wait[8*f_i +: 8] <= 8'd0;
            else
                f_wait[8*f_i +: 8] <= f_wait[8*f_i +: 8] + 8'd1;
    end

    integer f_j, f_k;
    always @(*) begin
        if (f_past_valid) begin
            // The pointer names a requester.
            assert (ptr <= LAST);
            // At most one grant, and only to a requester.
            assert ((grant & (grant - 1'b1)) == {N{1'b0}});
            assert ((grant & ~req) == {N{1'b0}});
            // Work conserving: if anyone requests, someone is granted.
            assert ((req == {N{1'b0}}) == (grant == {N{1'b0}}));
            // Round-robin order: no requester sits between the pointer and the
            // one granted.
            for (f_j = 0; f_j < N; f_j = f_j + 1)
                for (f_k = 0; f_k < N; f_k = f_k + 1)
                    if (grant[f_j] && req[f_k])
                        assert (f_dist(f_k) >= f_dist(f_j));
            // Bounded wait: a held request is granted within N cycles, as the
            // pointer comes at least one step closer to it on every cycle it
            // waits.
            for (f_j = 0; f_j < N; f_j = f_j + 1) begin
                assert (f_wait[8*f_j +: 8] <= N - 1);
                if (f_wait[8*f_j +: 8] != 8'd0)
                    assert (f_wait[8*f_j +: 8] + f_dist(f_j) <= N - 1);
            end
        end
    end

    // The last winner has the lowest priority now: the pointer sits one past
    // it. After reset, requester 0 has the highest priority.
    integer f_w;
    always @(posedge clk) begin
        if (f_past_valid) begin
            if (!$past(rst_n))
                assert (ptr == {IW{1'b0}});
            else
                for (f_w = 0; f_w < N; f_w = f_w + 1)
                    if ($past(grant[f_w]))
                        assert (f_dist(f_w) == N - 1);
        end
    end
`endif
endmodule
