// An input debouncer. `clean` follows `noisy`, but only once `noisy` has stopped
// changing: when `noisy` has held its value for STABLE clock edges after a
// change, `clean` takes that value. A change on `noisy`, in either direction,
// restarts the count, so a pulse of STABLE edges or fewer, high or low, never
// reaches `clean`.
`timescale 1ns / 1ps
module debounce #(
    parameter integer STABLE = 4
) (
    input  wire clk,
    input  wire rst,
    input  wire noisy,
    output reg  clean
);
    reg       prev;
    reg [3:0] cnt;

    always @(posedge clk) begin
        if (rst) begin
            prev  <= 1'b0;
            cnt   <= 4'd0;
            clean <= 1'b0;
        end else begin
            prev <= noisy;
            if (noisy != prev)
                cnt <= 4'd0;
            else if (cnt != STABLE - 1)
                cnt <= cnt + 4'd1;
            if (noisy == prev && cnt == STABLE - 1)
                clean <= noisy;
        end
    end
endmodule
