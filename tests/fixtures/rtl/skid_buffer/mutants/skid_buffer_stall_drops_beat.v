// A mutant that is wrong on purpose (P3-E3): skid_buffer.v with one change.
// A beat accepted in a cycle the output stalls is not kept: the skid register
// never fills, so s_ready stays high and the beat is lost.
// Everything else is identical.
//
// Skid buffer (register slice) on a valid/ready stream of WIDTH-bit beats.
// A P3-E3 fixture, the reference of the eval case rtl/skid-buffer: see
// interface_spec.md and microarchitecture.md.
//
// * A beat moves on a rising edge when its side's valid and ready are both
//   high: s_valid and s_ready upstream, m_valid and m_ready downstream.
// * Every output is a flop: m_valid and m_data come from the output register,
//   and s_ready is high exactly while the skid register is empty. Nothing
//   passes combinationally from m_ready or s_valid to any output.
// * Full throughput: with m_ready held high, one beat enters and one leaves
//   on every edge. The slice holds at most two beats, so it can accept one
//   more beat in the cycle the output stalls.
// * Beats leave in the order they entered, each exactly once, and a beat
//   offered on the output and not taken stays there, unchanged.
// * rst_n is synchronous and active low; reset drops any held beat.
`timescale 1ns / 1ps
module skid_buffer #(
    parameter WIDTH = 8
) (
    input  wire             clk,
    input  wire             rst_n,
    // Upstream side: the slice receives beats
    input  wire             s_valid,
    output wire             s_ready,
    input  wire [WIDTH-1:0] s_data,
    // Downstream side: the slice sends beats
    output reg              m_valid,
    input  wire             m_ready,
    output reg  [WIDTH-1:0] m_data
);
    // The skid register holds the one beat accepted while the output stalls.
    reg             skid_valid;
    reg [WIDTH-1:0] skid_data;

    // Registered ready: the inverse of a flop, with no path from m_ready.
    assign s_ready = !skid_valid;

    wire s_fire = s_valid && s_ready;
    // The output register may load: it is empty, or its beat leaves on this edge.
    wire m_free = !m_valid || m_ready;

    always @(posedge clk) begin
        if (!rst_n) begin
            m_valid <= 1'b0;
            skid_valid <= 1'b0;
        end else if (m_free) begin
            // The skid beat goes out first; s_ready is low while it waits,
            // so no new beat arrives in the same cycle.
            m_valid <= skid_valid || s_valid;
            skid_valid <= 1'b0;
        end
    end

    // Data: not reset. Each register loads only where its control says so.
    always @(posedge clk) begin
        if (m_free)
            m_data <= skid_valid ? skid_data : s_data;
        if (!m_free && s_fire)
            skid_data <= s_data;
    end

`ifdef FORMAL
    // Properties, proven by skid_buffer.sby (WIDTH 8) and skid_buffer_w1.sby
    // (WIDTH 1) for any input sequence. Upstream need not hold s_valid or
    // s_data while s_ready is low: nothing here assumes it.
    reg f_past_valid = 1'b0;
    always @(posedge clk)
        f_past_valid <= 1'b1;

    // The first cycle is in reset.
    always @(*)
        if (!f_past_valid)
            assume (!rst_n);

    // The specification as a model: a queue of up to two beats, moved by the
    // handshakes at the ports. f_head is the oldest beat and f_next the one
    // behind it.
    reg [1:0]       f_count;
    reg [WIDTH-1:0] f_head;
    reg [WIDTH-1:0] f_next;
    wire            f_in = s_valid && s_ready;
    wire            f_out = m_valid && m_ready;
    // The beats left once this cycle's output beat has gone.
    wire [1:0]      f_left = f_count - {1'b0, f_out};

    always @(posedge clk) begin
        if (!rst_n) begin
            f_count <= 2'd0;
        end else begin
            f_count <= f_left + {1'b0, f_in};
            if (f_out)
                f_head <= f_next;
            // A new beat goes behind the beats left (a later assignment wins).
            if (f_in && f_left == 2'd0)
                f_head <= s_data;
            if (f_in && f_left != 2'd0)
                f_next <= s_data;
        end
    end

    always @(posedge clk) begin
        if (f_past_valid) begin
            // After reset the slice is empty and ready.
            if (!$past(rst_n))
                assert (f_count == 2'd0 && !m_valid && s_ready);
            // At most two beats; valid while any is held; ready while room is left.
            assert (f_count <= 2'd2);
            assert (m_valid == (f_count != 2'd0));
            assert (s_ready == (f_count != 2'd2));
            // The output shows the oldest beat.
            if (m_valid)
                assert (m_data == f_head);
            // A beat offered and not taken stays, unchanged.
            if ($past(rst_n) && $past(m_valid && !m_ready))
                assert (m_valid && m_data == $past(m_data));
            // Inside: the skid register holds the second beat.
            if (f_count == 2'd2)
                assert (skid_valid && skid_data == f_next);
        end
    end

    // Covers: each is reached, so the proof is not vacuous.
    always @(posedge clk) begin
        if (f_past_valid && $past(rst_n) && rst_n) begin
            // The skid register fills: a beat arrives while the output stalls.
            cover (f_count == 2'd2);
            // A full slice drains in the cycle ready rises.
            cover ($past(f_count == 2'd2) && $past(f_out) && f_count == 2'd1);
            // Full throughput: a beat in and a beat out on two edges in a row.
            cover ($past(f_in && f_out) && f_in && f_out);
            // A beat held on a stall, then taken.
            cover ($past(m_valid && !m_ready) && f_out);
            // The skid beat leaves and a new beat follows it straight away.
            cover ($past(f_count == 2'd2) && $past(f_out) && f_in);
        end
    end
`endif
endmodule
