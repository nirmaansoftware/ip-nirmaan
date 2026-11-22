// A pulse-width modulator. The output repeats with a period of PERIOD clock
// cycles. In each period it is high for `duty` consecutive clock cycles at the
// start of the period, then low (`duty` 0 keeps it low, `duty` of PERIOD or more
// keeps it high). `duty` is sampled once, at the first clock of a period, so a
// change in the middle of a period takes effect in the next period.
`timescale 1ns / 1ps
module pwm_gen #(
    parameter integer PERIOD = 8
) (
    input  wire       clk,
    input  wire       rst,
    input  wire [3:0] duty,
    output reg        pwm
);
    reg [3:0] cnt;
    reg [3:0] duty_q;
    wire [3:0] duty_now = (cnt == 4'd0) ? duty : duty_q;

    always @(posedge clk) begin
        if (rst) begin
            cnt    <= 4'd0;
            duty_q <= 4'd0;
            pwm    <= 1'b0;
        end else begin
            if (cnt == PERIOD - 1)
                cnt <= 4'd0;
            else
                cnt <= cnt + 4'd1;
            if (cnt == 4'd0)
                duty_q <= duty;
            pwm <= (cnt < duty_now);
        end
    end
endmodule
