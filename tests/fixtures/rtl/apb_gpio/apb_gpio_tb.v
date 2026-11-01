// Self-checking testbench for apb_gpio.v (P3-E2), the eval case's reference.
//
// Two lanes run the same checks, one with 8 pins and one with 32 (every
// byte lane of pstrb in use). Each lane covers reset values; write and read
// back of every read/write register, with pstrb partial writes and bits above
// the pins reading zero; gpio_out and gpio_oe following DATA_OUT and DIR;
// DATA_IN following the pins, read only; pslverr for unaligned and unmapped
// addresses, with writes changing nothing; rising and falling edge detection
// that fires once per edge; high and low level detection that sets the status
// again after a clear while the level holds; write-1-to-clear that clears only
// the bits written 1, in the strobed bytes; the INTR_ENABLE mask on irq; a
// detection in the very cycle of its clear, which must leave the bit set;
// zero wait states and quiet responses outside the access phase; and reset
// again.
//
// Inputs are driven just after the falling edge and outputs are sampled 1 ns
// later, so every check sees the values the next rising edge will use. A pin
// change is sampled on the next rising edge and detected on the one after.
`timescale 1ns / 1ps
module apb_gpio_tb_lane #(
    parameter N = 8
) ();
    localparam TIMEOUT = 20;
    localparam [63:0] ALL = (64'd1 << N) - 64'd1;
    localparam [31:0] PINS = ALL[31:0];
    localparam [7:0] DATA_OUT = 8'h00, DIR = 8'h04, DATA_IN = 8'h08, INTR_RISE = 8'h0C, INTR_FALL = 8'h10,
                     INTR_HIGH = 8'h14, INTR_LOW = 8'h18, INTR_ENABLE = 8'h1C, INTR_STATUS = 8'h20;

    reg          pclk = 1'b0;
    reg          presetn = 1'b0;
    reg  [7:0]   paddr = 8'd0;
    reg          psel = 1'b0;
    reg          penable = 1'b0;
    reg          pwrite = 1'b0;
    reg  [31:0]  pwdata = 32'd0;
    reg  [3:0]   pstrb = 4'd0;
    wire [31:0]  prdata;
    wire         pready;
    wire         pslverr;
    reg  [N-1:0] gpio_in = {N{1'b0}};
    wire [N-1:0] gpio_out;
    wire [N-1:0] gpio_oe;
    wire         irq;

    integer errors = 0;
    integer checks = 0;
    reg     done = 1'b0;
    reg        err;
    reg [31:0] data;
    // The upper pins used by the checks: pin 20 and pin 31 on the wide lane,
    // pins 5 and 7 on the narrow one.
    localparam integer HI_A = N > 20 ? 20 : 5;
    localparam integer HI_B = N - 1;

    apb_gpio #(.ADDR_WIDTH(8), .N(N)) dut (
        .pclk(pclk), .presetn(presetn),
        .paddr(paddr), .psel(psel), .penable(penable), .pwrite(pwrite),
        .pwdata(pwdata), .pstrb(pstrb),
        .prdata(prdata), .pready(pready), .pslverr(pslverr),
        .gpio_in(gpio_in), .gpio_out(gpio_out), .gpio_oe(gpio_oe), .irq(irq)
    );

    always #5 pclk = ~pclk;

    task automatic check(input [8*48-1:0] what, input [31:0] got, input [31:0] expected);
        begin
            checks = checks + 1;
            if (got !== expected) begin
                $error("lane N=%0d: %0s: got 0x%08h, expected 0x%08h", N, what, got, expected);
                errors = errors + 1;
            end
        end
    endtask

    // Outside the access phase, prdata and pslverr must be zero.
    task automatic check_quiet;
        begin
            check("pslverr outside access", {31'd0, pslverr}, 32'd0);
            check("prdata outside access", prdata, 32'd0);
        end
    endtask

    // Idle cycles: psel low.
    task automatic idle(input integer cycles);
        integer n;
        begin
            psel = 1'b0;
            penable = 1'b0;
            for (n = 0; n < cycles; n = n + 1) begin
                #1;
                check_quiet;
                @(negedge pclk);
            end
        end
    endtask

    // One transfer, started at a falling edge: a setup cycle, then access
    // cycles until pready. A write takes effect on the second rising edge.
    task automatic transfer(input wr, input [7:0] addr, input [31:0] value, input [3:0] strb,
                            output [31:0] got_data, output got_err);
        integer waits;
        begin
            psel = 1'b1;
            penable = 1'b0;
            pwrite = wr;
            paddr = addr;
            pwdata = wr ? value : 32'd0;
            pstrb = wr ? strb : 4'd0;
            #1;
            check_quiet;
            @(negedge pclk);
            penable = 1'b1;
            waits = 0;
            #1;
            while (!pready && waits < TIMEOUT) begin
                @(negedge pclk);
                #1;
                waits = waits + 1;
            end
            check("wait states", waits, 0);
            got_data = prdata;
            got_err = pslverr;
            @(negedge pclk);
            psel = 1'b0;
            penable = 1'b0;
            pwdata = 32'd0;
        end
    endtask

    task automatic write_ok(input [7:0] addr, input [31:0] value, input [3:0] strb);
        begin
            transfer(1'b1, addr, value, strb, data, err);
            check("write pslverr low", {31'd0, err}, 32'd0);
        end
    endtask

    task automatic expect_reg(input [8*48-1:0] what, input [7:0] addr, input [31:0] expected);
        begin
            transfer(1'b0, addr, 32'd0, 4'd0, data, err);
            check(what, data, expected);
            check("read pslverr low", {31'd0, err}, 32'd0);
        end
    endtask

    task automatic unmapped(input [7:0] addr);
        begin
            transfer(1'b1, addr, 32'hFFFF_FFFF, 4'hF, data, err);
            check("unmapped write pslverr", {31'd0, err}, 32'd1);
            transfer(1'b0, addr, 32'd0, 4'd0, data, err);
            check("unmapped read pslverr", {31'd0, err}, 32'd1);
            check("unmapped read data", data, 32'd0);
        end
    endtask

    // A pin vector, widened to 32 bits.
    function [31:0] wide(input [N-1:0] v);
        integer k;
        begin
            wide = 32'd0;
            for (k = 0; k < N; k = k + 1)
                wide[k] = v[k];
        end
    endfunction

    task automatic pins(input [31:0] value);
        begin
            gpio_in = value[N-1:0];
        end
    endtask

    task automatic reset_dut;
        begin
            presetn = 1'b0;
            psel = 1'b0;
            penable = 1'b0;
            repeat (3) @(negedge pclk);
            #1;
            check_quiet;
            check("irq in reset", {31'd0, irq}, 32'd0);
            presetn = 1'b1;
            @(negedge pclk);
        end
    endtask

    // Every register, read back against expected values.
    task automatic expect_all(input [8*48-1:0] what, input [31:0] out, input [31:0] dirv, input [31:0] rise,
                              input [31:0] fall, input [31:0] high, input [31:0] low, input [31:0] enable);
        begin
            expect_reg(what, DATA_OUT, out);
            expect_reg(what, DIR, dirv);
            expect_reg(what, INTR_RISE, rise);
            expect_reg(what, INTR_FALL, fall);
            expect_reg(what, INTR_HIGH, high);
            expect_reg(what, INTR_LOW, low);
            expect_reg(what, INTR_ENABLE, enable);
        end
    endtask

    wire [31:0] bit_a = 32'd1 << HI_A;
    wire [31:0] bit_b = 32'd1 << HI_B;

    initial begin
        @(negedge pclk);
        reset_dut;

        // Reset values.
        expect_all("reset value", 0, 0, 0, 0, 0, 0, 0);
        expect_reg("DATA_IN after reset", DATA_IN, 32'd0);
        expect_reg("INTR_STATUS after reset", INTR_STATUS, 32'd0);
        check("gpio_out after reset", wide(gpio_out), 32'd0);
        check("gpio_oe after reset", wide(gpio_oe), 32'd0);

        // Read/write registers: every bit that exists, partial strobes, bits
        // above the pins ignored.
        write_ok(DATA_OUT, 32'hFFFF_FFFF, 4'hF);
        write_ok(DIR, 32'hA5A5_A5A5, 4'hF);
        write_ok(INTR_RISE, 32'h1111_1111, 4'hF);
        write_ok(INTR_FALL, 32'h2222_2222, 4'hF);
        write_ok(INTR_HIGH, 32'h4444_4444, 4'hF);
        write_ok(INTR_LOW, 32'h8888_8888, 4'hF);
        write_ok(INTR_ENABLE, 32'h3C3C_3C3C, 4'hF);
        expect_all("read back", PINS, 32'hA5A5_A5A5 & PINS, 32'h1111_1111 & PINS, 32'h2222_2222 & PINS,
                   32'h4444_4444 & PINS, 32'h8888_8888 & PINS, 32'h3C3C_3C3C & PINS);
        check("gpio_out follows DATA_OUT", wide(gpio_out), PINS);
        check("gpio_oe follows DIR", wide(gpio_oe), 32'hA5A5_A5A5 & PINS);
        write_ok(DATA_OUT, 32'h1234_5678, 4'b0101);
        expect_reg("pstrb 0101", DATA_OUT, 32'hFF34_FF78 & PINS);
        write_ok(DATA_OUT, 32'h0000_0000, 4'b0000);
        expect_reg("pstrb 0000 changes nothing", DATA_OUT, 32'hFF34_FF78 & PINS);
        write_ok(DIR, 32'h0F0F_0F0F, 4'b1010);
        expect_reg("pstrb 1010", DIR, 32'h0FA5_0FA5 & PINS);
        check("gpio_out after partial writes", wide(gpio_out), 32'hFF34_FF78 & PINS);
        check("gpio_oe after partial writes", wide(gpio_oe), 32'h0FA5_0FA5 & PINS);
        write_ok(DATA_OUT, 32'd0, 4'hF);
        write_ok(DIR, 32'd0, 4'hF);
        write_ok(INTR_RISE, 32'd0, 4'hF);
        write_ok(INTR_FALL, 32'd0, 4'hF);
        write_ok(INTR_HIGH, 32'd0, 4'hF);
        write_ok(INTR_LOW, 32'd0, 4'hF);
        write_ok(INTR_ENABLE, 32'd0, 4'hF);
        expect_all("all cleared", 0, 0, 0, 0, 0, 0, 0);
        write_ok(INTR_STATUS, 32'hFFFF_FFFF, 4'hF);

        // DATA_IN follows the pins, one edge later, and is read only.
        pins(32'h5AC3_96E1);
        idle(2);
        expect_reg("DATA_IN follows the pins", DATA_IN, 32'h5AC3_96E1 & PINS);
        transfer(1'b1, DATA_IN, 32'd0, 4'hF, data, err);
        check("DATA_IN write pslverr", {31'd0, err}, 32'd1);
        expect_reg("DATA_IN unchanged by a write", DATA_IN, 32'h5AC3_96E1 & PINS);
        pins(32'd0);
        idle(2);

        // Unmapped addresses change nothing.
        unmapped(8'h01);
        unmapped(8'h06);
        unmapped(8'h22);
        unmapped(8'h24);
        unmapped(8'h28);
        unmapped(8'h3C);
        unmapped(8'h40);
        unmapped(8'h44);
        unmapped(8'hFC);
        expect_all("unchanged by unmapped writes", 0, 0, 0, 0, 0, 0, 0);
        expect_reg("status unchanged by unmapped writes", INTR_STATUS, 32'd0);

        // Rising edges on pin 0 and an upper pin: one status bit per edge,
        // and a clear sticks while the pin stays high.
        write_ok(INTR_RISE, 32'h1 | bit_a, 4'hF);
        write_ok(INTR_ENABLE, 32'h1 | bit_a, 4'hF);
        pins(32'h1 | bit_a);
        idle(3);
        expect_reg("rising edges detected", INTR_STATUS, 32'h1 | bit_a);
        check("irq on a rising edge", {31'd0, irq}, 32'd1);
        write_ok(INTR_STATUS, 32'h1, 4'hF);
        expect_reg("W1C clears only bit 0", INTR_STATUS, bit_a);
        write_ok(INTR_STATUS, bit_a, 4'hF);
        idle(4);
        expect_reg("an edge fires once", INTR_STATUS, 32'd0);
        check("irq after the clear", {31'd0, irq}, 32'd0);
        pins(32'd0);
        idle(3);
        expect_reg("a falling edge is not a rising one", INTR_STATUS, 32'd0);

        // Falling edges on pin 1.
        write_ok(INTR_RISE, 32'd0, 4'hF);
        write_ok(INTR_FALL, 32'h2, 4'hF);
        pins(32'h2);
        idle(3);
        expect_reg("a rising edge is not a falling one", INTR_STATUS, 32'd0);
        pins(32'h0);
        idle(3);
        expect_reg("falling edge detected", INTR_STATUS, 32'h2);
        write_ok(INTR_STATUS, 32'h2, 4'hF);
        idle(3);
        expect_reg("a falling edge fires once", INTR_STATUS, 32'd0);
        write_ok(INTR_FALL, 32'd0, 4'hF);

        // High level on pin 2: a clear does not stick while the pin is high.
        write_ok(INTR_HIGH, 32'h4, 4'hF);
        pins(32'h4);
        idle(3);
        expect_reg("high level detected", INTR_STATUS, 32'h4);
        write_ok(INTR_STATUS, 32'h4, 4'hF);
        expect_reg("high level sets the bit again", INTR_STATUS, 32'h4);
        pins(32'h0);
        idle(3);
        write_ok(INTR_STATUS, 32'h4, 4'hF);
        idle(3);
        expect_reg("high level gone, clear sticks", INTR_STATUS, 32'd0);
        write_ok(INTR_HIGH, 32'd0, 4'hF);

        // Low level on pin 3 and on the top pin: set while low.
        write_ok(INTR_LOW, 32'h8 | bit_b, 4'hF);
        idle(1);
        expect_reg("low level detected", INTR_STATUS, 32'h8 | bit_b);
        write_ok(INTR_STATUS, 32'h8 | bit_b, 4'hF);
        expect_reg("low level sets the bits again", INTR_STATUS, 32'h8 | bit_b);
        pins(32'h8 | bit_b);
        idle(3);
        write_ok(INTR_STATUS, 32'h8 | bit_b, 4'hF);
        idle(3);
        expect_reg("low level gone, clear sticks", INTR_STATUS, 32'd0);
        write_ok(INTR_LOW, 32'd0, 4'hF);
        pins(32'h0);
        idle(2);

        // Write-1-to-clear with several bits pending: only the bits written 1,
        // only in strobed bytes; writing 0 clears nothing.
        write_ok(INTR_RISE, 32'h3 | bit_a, 4'hF);
        pins(32'h3 | bit_a);
        idle(3);
        expect_reg("three bits pending", INTR_STATUS, 32'h3 | bit_a);
        write_ok(INTR_STATUS, 32'd0, 4'hF);
        expect_reg("writing 0 clears nothing", INTR_STATUS, 32'h3 | bit_a);
        write_ok(INTR_STATUS, 32'hFFFF_FFFF, 4'b0000);
        expect_reg("unstrobed clear clears nothing", INTR_STATUS, 32'h3 | bit_a);
        write_ok(INTR_STATUS, 32'h2, 4'hF);
        expect_reg("W1C keeps the other bits", INTR_STATUS, 32'h1 | bit_a);
        if (N > 8) begin
            write_ok(INTR_STATUS, 32'hFFFF_FFFF, 4'b0001);
            expect_reg("clear in byte 0 only", INTR_STATUS, bit_a);
        end
        write_ok(INTR_STATUS, 32'hFFFF_FFFF, 4'hF);
        expect_reg("all clear", INTR_STATUS, 32'd0);

        // The mask: a pending bit raises irq only when enabled.
        write_ok(INTR_ENABLE, 32'd0, 4'hF);
        pins(32'h0);
        idle(2);
        pins(32'h1);
        idle(3);
        expect_reg("masked bit pending", INTR_STATUS, 32'h1);
        check("masked bit raises no irq", {31'd0, irq}, 32'd0);
        write_ok(INTR_ENABLE, 32'h2, 4'hF);
        check("another pin's enable raises no irq", {31'd0, irq}, 32'd0);
        write_ok(INTR_ENABLE, 32'h1, 4'hF);
        check("enabling the pending bit raises irq", {31'd0, irq}, 32'd1);
        write_ok(INTR_ENABLE, 32'h0, 4'hF);
        check("masking it again drops irq", {31'd0, irq}, 32'd0);
        write_ok(INTR_ENABLE, 32'h1, 4'hF);
        write_ok(INTR_STATUS, 32'h1, 4'hF);
        check("irq low after the clear", {31'd0, irq}, 32'd0);

        // A rising edge detected in the very cycle of its bit's clear: the
        // bit stays set. Pin 0 is pending, falls, then rises as the clear
        // starts: it is sampled on the setup edge and detected on the access
        // edge, the one the clear takes effect on.
        pins(32'h0);
        idle(3);
        pins(32'h1);
        idle(3);
        expect_reg("pending before the race", INTR_STATUS, 32'h1);
        pins(32'h0);
        idle(3);
        pins(32'h1);
        write_ok(INTR_STATUS, 32'h1, 4'hF);
        expect_reg("a detection beats a same-cycle clear", INTR_STATUS, 32'h1);
        check("irq stays high", {31'd0, irq}, 32'd1);
        write_ok(INTR_STATUS, 32'h1, 4'hF);
        expect_reg("cleared after the race", INTR_STATUS, 32'd0);

        // Reset again.
        write_ok(DATA_OUT, 32'hFFFF_FFFF, 4'hF);
        write_ok(INTR_HIGH, 32'h1, 4'hF);
        idle(2);
        reset_dut;
        expect_all("value after reset", 0, 0, 0, 0, 0, 0, 0);
        expect_reg("status after reset", INTR_STATUS, 32'd0);
        check("gpio_out after the second reset", wide(gpio_out), 32'd0);
        idle(2);

        done = 1'b1;
    end
endmodule

module apb_gpio_tb;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer checks, errors;

    apb_gpio_tb_lane #(.N(8)) lane8 ();
    apb_gpio_tb_lane #(.N(32)) lane32 ();

    initial begin
        wait (lane8.done && lane32.done);
        checks = lane8.checks + lane32.checks;
        errors = lane8.errors + lane32.errors;
        if (checks < 600) begin
            $error("too few checks: %0d", checks);
            errors = errors + 1;
        end
        if (errors == 0)
            $display("apb_gpio_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
