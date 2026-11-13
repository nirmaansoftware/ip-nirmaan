// Reference properties for dv/formal-credit-counter (wave 2, W2-E2): the
// approved credit_counter at MAX 4 and MAX 5, each against a model written
// from interface_spec.md alone. Immediate assertions and $past, the SVA
// subset open Yosys reads (no implication or sequence operators).
`timescale 1ns / 1ps
module credit_counter_props #(
    parameter integer MAX = 4
) (
    input wire clk,
    input wire rst_n,
    input wire take,
    input wire give
);
    localparam [7:0] LIMIT = MAX[7:0];

    wire [7:0] credits;
    wire avail;
    wire full;
    wire err;
    credit_counter #(.MAX(MAX)) dut (.clk(clk), .rst_n(rst_n), .take(take), .give(give),
                                     .credits(credits), .avail(avail), .full(full), .err(err));

    // The model: what the specification says credits and err hold.
    reg [7:0] m_credits;
    reg m_err;
    reg past_valid = 1'b0;
    wire take_only = take && !give;
    wire give_only = give && !take;

    always @(posedge clk) begin
        past_valid <= 1'b1;
        if (!rst_n) begin
            m_credits <= LIMIT;                                     // CC-RESET
            m_err <= 1'b0;
        end else begin
            if (take_only && m_credits != 8'd0)
                m_credits <= m_credits - 8'd1;                      // CC-TAKE
            else if (give_only && m_credits != LIMIT)
                m_credits <= m_credits + 8'd1;                      // CC-GIVE
            if ((take_only && m_credits == 8'd0) || (give_only && m_credits == LIMIT))
                m_err <= 1'b1;                                      // CC-UNDERFLOW, CC-OVERFLOW
        end
    end

    // The first edge is a reset, so every later state is a specified one.
    always @(*)
        if (!past_valid)
            assume (!rst_n);

    always @(*)
        if (past_valid) begin
            assert (m_credits <= LIMIT);                            // CC-RANGE (the model)
            assert (credits == m_credits);                          // CC-TAKE, CC-GIVE, CC-BOTH, CC-IDLE
            assert (err == m_err);                                  // CC-ERR-STICKY
            assert (avail == (credits != 8'd0));                    // CC-STATUS
            assert (full == (credits == LIMIT));                    // CC-STATUS
        end

    // Edge by edge, in the specification's own terms.
    always @(posedge clk)
        if (past_valid && $past(past_valid) && $past(rst_n)) begin
            if ($past(take) && $past(give))
                assert (credits == $past(credits));                 // CC-BOTH
            if ($past(err))
                assert (err);                                       // CC-ERR-STICKY
        end

    // Covers: every corner the specification names is reachable.
    always @(posedge clk)
        if (past_valid && rst_n) begin
            cover (credits == 8'd0);
            cover (full && take && give);
            cover (credits == 8'd0 && take && give);
            cover (credits == 8'd0 && take_only);
            cover (full && give_only);
            cover (err && credits == LIMIT - 8'd1);
        end
endmodule

// Both parameter points in one proof: MAX 4 is a power of two, MAX 5 is not.
module credit_counter_check (
    input wire clk,
    input wire rst_n,
    input wire take,
    input wire give
);
    credit_counter_props #(.MAX(4)) max4 (.clk(clk), .rst_n(rst_n), .take(take), .give(give));
    credit_counter_props #(.MAX(5)) max5 (.clk(clk), .rst_n(rst_n), .take(take), .give(give));
endmodule
