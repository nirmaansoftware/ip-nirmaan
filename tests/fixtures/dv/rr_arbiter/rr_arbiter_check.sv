// Reference properties for dv/formal-rr-arbiter (RX-E1): the approved
// rr_arbiter against a model written from interface_spec.md alone, plus the
// specification's own statements (one hot, only requesters, yield, bounded
// wait). Immediate assertions and $past, the SVA subset open Yosys reads (no
// implication or sequence operators).
`timescale 1ns / 1ps
module rr_arbiter_check (
    input wire       clk,
    input wire       rst_n,
    input wire [2:0] req
);
    wire [2:0] grant;
    wire [1:0] last;
    rr_arbiter dut (.clk(clk), .rst_n(rst_n), .req(req), .grant(grant), .last(last));

    // The model: the priority order is last + 1, last + 2, last, modulo 3.
    reg [1:0] m_last;
    reg [2:0] m_grant;
    reg       past_valid = 1'b0;
    integer   k;
    reg [1:0] idx;
    always @(*) begin
        m_grant = 3'b000;
        for (k = 3; k >= 1; k = k - 1) begin
            idx = (m_last + k) % 3;
            if (req[idx])
                m_grant = 3'b001 << idx;
        end
    end

    always @(posedge clk) begin
        past_valid <= 1'b1;
        if (!rst_n)
            m_last <= 2'd2;                                         // RR-RESET
        else if (m_grant == 3'b001)
            m_last <= 2'd0;                                         // RR-ROTATE
        else if (m_grant == 3'b010)
            m_last <= 2'd1;
        else if (m_grant == 3'b100)
            m_last <= 2'd2;
    end

    // The first edge is a reset, so every later state is a specified one.
    always @(*)
        if (!past_valid)
            assume (!rst_n);

    // Waits: edges a requester has held req high without a grant.
    reg [1:0] wait0 = 2'd0, wait1 = 2'd0, wait2 = 2'd0;
    always @(posedge clk)
        if (!rst_n) begin
            wait0 <= 2'd0;
            wait1 <= 2'd0;
            wait2 <= 2'd0;
        end else begin
            wait0 <= (req[0] && !grant[0]) ? wait0 + 2'd1 : 2'd0;
            wait1 <= (req[1] && !grant[1]) ? wait1 + 2'd1 : 2'd0;
            wait2 <= (req[2] && !grant[2]) ? wait2 + 2'd1 : 2'd0;
        end

    always @(*)
        if (past_valid) begin
            assert (m_last <= 2'd2);                                // the model's state is a requester
            assert (last == m_last);                                // RR-RESET, RR-ROTATE, RR-HOLD
            assert (grant == m_grant);                              // RR-IDLE, RR-PICK
            assert ((grant & ~req) == 3'b000);                      // RR-ONLY-REQUESTERS
            assert ((grant & (grant - 3'b001)) == 3'b000);          // at most one bit
            assert ((req != 3'b000) == (grant != 3'b000));          // RR-IDLE, RR-PICK
        end

    // Edge by edge, in the specification's own terms.
    always @(posedge clk)
        if (past_valid && $past(past_valid) && $past(rst_n) && rst_n) begin
            // RR-YIELD: the requester granted at the last edge gives way to any other requester.
            if (($past(grant) & req) != 3'b000 && (req & ~$past(grant)) != 3'b000)
                assert ((grant & $past(grant)) == 3'b000);
            // RR-HOLD: no grant, no change.
            if ($past(grant) == 3'b000)
                assert (last == $past(last));
        end

    // RR-BOUND: no requester waits for a third grant of others.
    always @(*)
        if (past_valid && rst_n) begin
            assert (wait0 <= 2'd2);
            assert (wait1 <= 2'd2);
            assert (wait2 <= 2'd2);
        end

    // Covers: every corner the specification names is reachable.
    always @(posedge clk)
        if (past_valid && rst_n) begin
            cover (req == 3'b111 && grant == 3'b001);
            cover (req == 3'b111 && grant == 3'b010);
            cover (req == 3'b111 && grant == 3'b100);
            cover (req == 3'b000);
            cover (last == 2'd0 && req == 3'b101 && grant == 3'b100);
            cover (wait0 == 2'd2 && req[0]);
            cover (wait2 == 2'd2 && req[2]);
        end
endmodule
