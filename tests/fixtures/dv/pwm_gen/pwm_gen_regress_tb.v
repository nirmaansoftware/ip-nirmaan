// The three regression tests that failed in the nightly run, in one file. A
// plusarg picks the test: +test=pulse_width, +test=period or +test=duty_update.
// Each test sets a duty, watches `pwm` for a few periods and judges one thing.
`timescale 1ns / 1ps
module pwm_gen_regress_tb;
    localparam integer PERIOD = 8;
    reg        clk = 1'b0;
    reg        rst = 1'b1;
    reg  [3:0] duty = 4'd3;
    wire       pwm;
    integer    t0, t1, width, mid_high;
    integer    cycle = 0;
    reg [8*16-1:0] name;

    pwm_gen #(.PERIOD(PERIOD)) dut (.clk(clk), .rst(rst), .duty(duty), .pwm(pwm));
    always #5 clk = ~clk;
    always @(posedge clk) cycle <= cycle + 1;

    initial begin
        if (!$value$plusargs("test=%s", name)) name = "pulse_width";
        if (name == "duty_update") duty = 4'd2;
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        @(posedge pwm);
        t0 = cycle;
        if (name == "pulse_width") begin
            width = 0;
            while (pwm) begin
                width = width + 1;
                @(posedge clk); #1;
            end
            if (width !== 3)
                $display("ERROR: pwm_gen_regress_tb.v:33: pulse_width: duty 3 gave a pulse of %0d clocks, expected 3", width);
        end else if (name == "period") begin
            @(negedge pwm);
            @(posedge pwm);
            t1 = cycle;
            if (t1 - t0 !== PERIOD)
                $display("ERROR: pwm_gen_regress_tb.v:39: period: rising edges %0d clocks apart, expected %0d", t1 - t0, PERIOD);
        end else begin
            repeat (4) @(posedge clk);
            #1 duty = 4'd6;
            mid_high = 0;
            repeat (2) begin
                @(posedge clk); #1;
                if (pwm) mid_high = mid_high + 1;
            end
            if (mid_high !== 0)
                $display("ERROR: pwm_gen_regress_tb.v:49: duty_update: duty changed 2 to 6 mid-period, pwm high for %0d clocks before the next period, expected 0", mid_high);
        end
        $finish;
    end
endmodule
