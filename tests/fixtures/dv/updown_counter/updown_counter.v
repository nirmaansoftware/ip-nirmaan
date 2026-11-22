// Up/down counter with parallel load (RX-E1): a 4-bit register stepped by the
// adder, wrapping at both ends, with flags at the wrap. The approved RTL
// (gold) of the eval case dv/equiv-updown: see interface_spec.md and
// microarchitecture.md.
`timescale 1ns / 1ps
module updown_counter (
    input  wire       clk,
    input  wire       rst,
    input  wire       load,
    input  wire [3:0] din,
    input  wire       en,
    input  wire       up,
    output reg  [3:0] q,
    output wire       carry,
    output wire       borrow
);
    assign carry  = en && !load && up && (q == 4'd15);
    assign borrow = en && !load && !up && (q == 4'd0);

    always @(posedge clk) begin
        if (rst)
            q <= 4'd0;
        else if (load)
            q <= din;
        else if (en)
            q <= up ? q + 4'd1 : q - 4'd1;
    end
endmodule
