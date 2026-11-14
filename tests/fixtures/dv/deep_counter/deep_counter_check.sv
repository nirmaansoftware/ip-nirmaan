// Reference properties for dv/prove-deep-counter (wave 2, W2-E2): the
// approved deep_counter at its default LIMIT 99 against a model written from
// interface_spec.md alone. The properties are inductive, so the setup proves
// them in prove mode (k-induction) with a 20-cycle unrolling, though the
// counter first wraps 100 cycles after reset. Immediate assertions and $past,
// the SVA subset open Yosys reads.
`timescale 1ns / 1ps
module deep_counter_check (
    input wire clk,
    input wire rst_n,
    input wire en,
    input wire clr
);
    localparam [6:0] LAST = 7'd99;

    wire [6:0] count;
    wire carry;
    deep_counter #(.LIMIT(99)) dut (.clk(clk), .rst_n(rst_n), .en(en), .clr(clr), .count(count), .carry(carry));

    // The model: what the specification says count holds.
    reg [6:0] m_count;
    reg past_valid = 1'b0;
    always @(posedge clk) begin
        past_valid <= 1'b1;
        if (!rst_n || clr)
            m_count <= 7'd0;                                        // DC-RESET, DC-CLEAR
        else if (en)
            m_count <= (m_count == LAST) ? 7'd0 : m_count + 7'd1;   // DC-COUNT
    end

    // The first edge is a reset, so every later state is a specified one.
    always @(*)
        if (!past_valid)
            assume (!rst_n);

    // The invariant: the model stays in range and the design matches it. Both
    // hold after one edge from any state where they held, so induction closes.
    always @(*)
        if (past_valid) begin
            assert (m_count <= LAST);                               // DC-RANGE (the model)
            assert (count == m_count);                              // DC-COUNT, DC-HOLD, DC-RANGE
            assert (carry == (en && !clr && count == LAST));        // DC-CARRY
        end

    // Edge by edge, in the specification's own terms.
    always @(posedge clk)
        if (past_valid && $past(past_valid) && $past(rst_n) && !$past(clr)) begin
            if (!$past(en))
                assert (count == $past(count));                     // DC-HOLD
            if ($past(en) && $past(count) != LAST)
                assert (count == $past(count) + 7'd1);              // DC-COUNT
        end

    // Covers within the unrolling: counting, holding and a clear mid-count.
    always @(posedge clk)
        if (past_valid && rst_n) begin
            cover (count == 7'd15);
            cover (count == 7'd6 && !en && !clr);
            cover (count == 7'd9 && clr);
        end
endmodule
