// Gray-code counter (wave 2, W2-E3): a 4-bit register holding the Gray-coded
// count, stepped by decode, add one and encode, with a wrap flag at the last
// code. The approved RTL (gold) of the eval case dv/equiv-gray: see
// interface_spec.md and microarchitecture.md.
`timescale 1ns / 1ps
module gray_counter (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    output reg  [3:0] gray,
    output wire       wrap
);
    wire [3:0] bin  = {gray[3], ^gray[3:2], ^gray[3:1], ^gray[3:0]};
    wire [3:0] inc  = bin + 4'd1;
    wire [3:0] next = inc ^ (inc >> 1);

    assign wrap = en && (gray == 4'b1000);

    always @(posedge clk) begin
        if (rst)
            gray <= 4'b0000;
        else if (en)
            gray <= next;
    end
endmodule
