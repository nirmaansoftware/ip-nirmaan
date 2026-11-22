// A second implementation of the same debouncer, written with a history of
// samples instead of a counter. Same ports, same behaviour.
`timescale 1ns / 1ps
module debounce #(
    parameter integer STABLE = 4
) (
    input  wire clk,
    input  wire rst,
    input  wire noisy,
    output reg  clean
);
    reg [STABLE-1:0] hist;

    always @(posedge clk) begin
        if (rst) begin
            hist  <= {STABLE{1'b0}};
            clean <= 1'b0;
        end else begin
            hist <= {hist[STABLE-2:0], noisy};
            if (&{hist, noisy})
                clean <= 1'b1;
            else if (!noisy)
                clean <= 1'b0;
        end
    end
endmodule
