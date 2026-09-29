// Synchronous FIFO: one clock, DEPTH entries of WIDTH bits.
// An M26 fixture: see interface_spec.md and microarchitecture.md.
//
// * A write is accepted when wr_en is high and the FIFO is not full; a read
//   is accepted when rd_en is high and the FIFO is not empty. Both may be
//   accepted in the same cycle. A write while full and a read while empty are
//   ignored: no overflow, no underflow.
// * First-word fall-through: while the FIFO is not empty, rd_data already
//   shows the oldest entry; a read accepted on a rising edge removes it.
// * full, empty and count describe the state after the last rising edge.
// * DEPTH need not be a power of two. rst_n is synchronous and active low.
`timescale 1ns / 1ps
module sync_fifo #(
    parameter DEPTH = 8,
    parameter WIDTH = 8
) (
    input  wire                       clk,
    input  wire                       rst_n,
    // Write side
    input  wire                       wr_en,
    input  wire [WIDTH-1:0]           wr_data,
    output wire                       full,
    // Read side
    input  wire                       rd_en,
    output wire [WIDTH-1:0]           rd_data,
    output wire                       empty,
    // Occupancy, 0 to DEPTH
    output reg  [$clog2(DEPTH+1)-1:0] count
);
    localparam AW = $clog2(DEPTH);
    localparam CW = $clog2(DEPTH + 1);
    localparam [AW-1:0] LAST = DEPTH[AW-1:0] - 1'b1;
    localparam [CW-1:0] FULL_COUNT = DEPTH[CW-1:0];

    // The storage, and the next slot to write and to read.
    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [AW-1:0]    wr_ptr;
    reg [AW-1:0]    rd_ptr;

    // A pointer's next value: it wraps after the last slot, for any DEPTH.
    function [AW-1:0] next(input [AW-1:0] ptr);
        next = (ptr == LAST) ? {AW{1'b0}} : ptr + 1'b1;
    endfunction

    assign full = (count == FULL_COUNT);
    assign empty = (count == {CW{1'b0}});
    assign rd_data = mem[rd_ptr];

    // The flags gate the requests, so a full FIFO drops a write and an empty
    // one drops a read.
    wire wr_acc = wr_en && !full;
    wire rd_acc = rd_en && !empty;

    // Storage is datapath: not reset, and written only outside reset.
    always @(posedge clk) begin
        if (rst_n && wr_acc)
            mem[wr_ptr] <= wr_data;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= {AW{1'b0}};
            rd_ptr <= {AW{1'b0}};
            count <= {CW{1'b0}};
        end else begin
            if (wr_acc)
                wr_ptr <= next(wr_ptr);
            if (rd_acc)
                rd_ptr <= next(rd_ptr);
            case ({wr_acc, rd_acc})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: count <= count;
            endcase
        end
    end

`ifdef FORMAL
    // Properties, proven by sync_fifo.sby for any input sequence.
    reg f_past_valid = 1'b0;
    always @(posedge clk)
        f_past_valid <= 1'b1;

    // The first cycle is in reset.
    always @(*)
        if (!f_past_valid)
            assume (!rst_n);

    // Where the write pointer must be: count slots after the read pointer.
    wire [31:0] f_sum = rd_ptr + count;
    wire [31:0] f_wr_expected = (f_sum >= DEPTH) ? f_sum - DEPTH : f_sum;

    // Data integrity: one slot, chosen by the solver, is tracked from the
    // write that fills it to the read that empties it.
    (* anyconst *) reg [AW-1:0] f_slot;
    reg             f_held;
    reg [WIDTH-1:0] f_data;
    wire [31:0]     f_offset = (f_slot >= rd_ptr) ? f_slot - rd_ptr : DEPTH + f_slot - rd_ptr;
    always @(*)
        assume (f_slot <= LAST);
    always @(posedge clk) begin
        if (!rst_n) begin
            f_held <= 1'b0;
        end else begin
            if (rd_acc && rd_ptr == f_slot)
                f_held <= 1'b0;
            if (wr_acc && wr_ptr == f_slot) begin
                f_held <= 1'b1;
                f_data <= wr_data;
            end
        end
    end

    always @(posedge clk) begin
        if (f_past_valid) begin
            // After reset the FIFO is empty.
            if (!$past(rst_n)) begin
                assert (empty && !full && count == {CW{1'b0}});
                assert (!f_held);
            end
            // The flags follow count, and are never both high.
            assert (full == (count == DEPTH));
            assert (empty == (count == 0));
            assert (!(full && empty));
            // count and the pointers stay in range.
            assert (count <= FULL_COUNT);
            assert (wr_ptr <= LAST && rd_ptr <= LAST);
            assert (wr_ptr == f_wr_expected[AW-1:0]);
            if ($past(rst_n)) begin
                // No overflow: a write while full changes nothing on the write side.
                if ($past(wr_en && full)) begin
                    assert (wr_ptr == $past(wr_ptr));
                    assert (count == $past(count) - {{(CW-1){1'b0}}, $past(rd_acc)});
                end
                // No underflow: a read while empty changes nothing on the read side.
                if ($past(rd_en && empty)) begin
                    assert (rd_ptr == $past(rd_ptr));
                    assert (count == $past(count) + {{(CW-1){1'b0}}, $past(wr_acc)});
                end
                // count moves by exactly the accepted writes minus the accepted reads.
                if ($past(wr_acc && !rd_acc))
                    assert (count == $past(count) + 1'b1);
                if ($past(rd_acc && !wr_acc))
                    assert (count == $past(count) - 1'b1);
                if ($past(wr_acc == rd_acc))
                    assert (count == $past(count));
            end
            // The tracked slot holds its word from write to read, and a read
            // of it returns exactly what was written.
            assert (f_held == (f_offset < count));
            if (f_held)
                assert (mem[f_slot] == f_data);
            if (f_held && rd_ptr == f_slot)
                assert (rd_data == f_data);
        end
    end
`endif
endmodule
