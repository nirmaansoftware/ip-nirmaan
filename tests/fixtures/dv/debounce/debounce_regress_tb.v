// The regression test that failed: it drives a noisy push-button through two
// bounces and two settled changes, logs every change on `noisy` and on `clean`
// with its cycle number, and checks each change on `clean` against how long
// `noisy` had been different from it.
//
// The stimulus, in order: a high pulse of three cycles (a bounce) from low, a
// settled press, a low pulse of two cycles (a bounce) while pressed, and a
// settled release. Only the two settled changes may reach `clean`.
`timescale 1ns / 1ps
module debounce_regress_tb;
    localparam integer STABLE = 4;
    reg     clk = 1'b0;
    reg     rst = 1'b1;
    reg     noisy = 1'b0;
    wire    clean;
    integer cycle = 0;
    integer held = 0;      // cycles noisy has differed from clean, as the test counts them
    integer changes = 0;
    reg     last_noisy = 1'b0;
    reg     last_clean = 1'b0;
    initial cycle = 0;

    debounce #(.STABLE(STABLE)) dut (.clk(clk), .rst(rst), .noisy(noisy), .clean(clean));
    always #5 clk = ~clk;

    always @(posedge clk) if (!rst) begin
        cycle <= cycle + 1;
        if (noisy !== last_noisy) begin
            $display("INFO: cycle %0d: noisy -> %b", cycle, noisy);
            last_noisy <= noisy;
        end
        if (clean !== last_clean) begin
            changes <= changes + 1;
            $display("INFO: cycle %0d: clean -> %b", cycle, clean);
            if (held < STABLE)
                $display("ERROR: debounce_regress_tb.v:42: cycle %0d: clean went %b after noisy had differed for only %0d cycles, expected %0d",
                         cycle, clean, held, STABLE);
            last_clean <= clean;
        end
        if (noisy !== clean) held <= held + 1; else held <= 0;
    end

    task drive(input value, input integer cycles);
        begin
            #1 noisy = value;
            repeat (cycles) @(posedge clk);
        end
    endtask

    initial begin
        repeat (3) @(posedge clk);
        #1 rst = 1'b0;
        repeat (2) @(posedge clk);
        drive(1'b1, 3);
        $display("INFO: cycle %0d: high bounce of 3 cycles done, clean=%b", cycle, clean);
        drive(1'b0, 12);
        drive(1'b1, 14);
        drive(1'b0, 2);
        $display("INFO: cycle %0d: low bounce of 2 cycles done, clean=%b", cycle, clean);
        drive(1'b1, 14);
        drive(1'b0, 14);
        if (changes !== 2)
            $display("ERROR: debounce_regress_tb.v:62: clean changed %0d times, expected 2", changes);
        $finish;
    end
endmodule
