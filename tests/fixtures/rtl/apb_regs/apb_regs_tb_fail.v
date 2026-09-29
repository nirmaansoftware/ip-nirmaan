// A testbench that is wrong on purpose: apb_regs_tb.v with one bad
// expectation. It expects a pstrb 0101 write to replace the whole register
// (0x11223344) instead of only bytes 0 and 2 (0xFF22FF44). Used to prove a
// failing simulation is a recorded, failed run. Everything else is identical.
//
// Covers reset values, write then read of every register, pstrb partial
// writes, back-to-back transfers and idle gaps, pslverr for unmapped
// addresses (misaligned, and beyond 0xC) with writes changing nothing and
// reads returning zero, zero wait states (pready high in every access cycle),
// quiet prdata and pslverr outside the access phase, and reset again.
//
// Inputs are driven just after the falling edge and outputs are sampled 1 ns
// later, so every check sees the values the next rising edge will use.
`timescale 1ns / 1ps
module apb_regs_tb_fail;
    localparam TIMEOUT = 20;

    reg         pclk = 1'b0;
    reg         presetn = 1'b0;
    reg  [7:0]  paddr = 8'd0;
    reg         psel = 1'b0;
    reg         penable = 1'b0;
    reg         pwrite = 1'b0;
    reg  [31:0] pwdata = 32'd0;
    reg  [3:0]  pstrb = 4'd0;
    wire [31:0] prdata;
    wire        pready;
    wire        pslverr;

    integer errors = 0;
    integer checks = 0;
    integer i;
    reg        err;
    reg [31:0] data;
    reg [31:0] model [0:3];

    apb_regs #(.ADDR_WIDTH(8), .DATA_WIDTH(32)) dut (
        .pclk(pclk), .presetn(presetn),
        .paddr(paddr), .psel(psel), .penable(penable), .pwrite(pwrite),
        .pwdata(pwdata), .pstrb(pstrb),
        .prdata(prdata), .pready(pready), .pslverr(pslverr)
    );

    always #5 pclk = ~pclk;

    task automatic check(input [255:0] what, input [31:0] got, input [31:0] expected);
        begin
            checks = checks + 1;
            if (got !== expected) begin
                $error("%0s: got 0x%08h, expected 0x%08h", what, got, expected);
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

    // One transfer: a setup cycle, then access cycles until pready. The bus
    // is left with psel low, so a following call starts back to back.
    task automatic transfer(input wr, input [7:0] addr, input [31:0] value, input [3:0] strb,
                            output [31:0] got_data, output got_err);
        integer waits;
        begin
            psel = 1'b1;
            penable = 1'b0;
            pwrite = wr;
            paddr = addr;
            pwdata = wr ? value : 32'd0;
            pstrb = wr ? strb : 4'd0;  // APB4: pstrb is low for reads
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

    // A mapped write, checked for no error, with the model updated to match.
    task automatic write_ok(input [7:0] addr, input [31:0] value, input [3:0] strb);
        integer b;
        begin
            transfer(1'b1, addr, value, strb, data, err);
            check("write pslverr low", {31'd0, err}, 32'd0);
            for (b = 0; b < 4; b = b + 1)
                if (strb[b])
                    model[addr[3:2]][8*b +: 8] = value[8*b +: 8];
        end
    endtask

    // Reads every register and compares it with the model.
    task automatic read_all;
        integer n;
        begin
            for (n = 0; n < 4; n = n + 1) begin
                transfer(1'b0, {4'd0, n[1:0], 2'b00}, 32'd0, 4'd0, data, err);
                check("read data", data, model[n]);
                check("read pslverr low", {31'd0, err}, 32'd0);
            end
        end
    endtask

    task automatic unmapped(input [7:0] addr);
        begin
            transfer(1'b1, addr, 32'hDEAD_BEEF, 4'hF, data, err);
            check("unmapped write pslverr", {31'd0, err}, 32'd1);
            transfer(1'b0, addr, 32'd0, 4'd0, data, err);
            check("unmapped read pslverr", {31'd0, err}, 32'd1);
            check("unmapped read data", data, 32'd0);
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
            check("pready in reset", {31'd0, pready}, 32'd1);
            presetn = 1'b1;
            @(negedge pclk);
            for (i = 0; i < 4; i = i + 1)
                model[i] = 32'd0;
        end
    endtask

    initial begin
        @(negedge pclk);
        reset_dut;

        // Reset values: every register reads zero.
        read_all;

        // Write then read every register.
        write_ok(8'h00, 32'h1111_1111, 4'hF);
        write_ok(8'h04, 32'h2222_2222, 4'hF);
        write_ok(8'h08, 32'h3333_3333, 4'hF);
        write_ok(8'h0C, 32'h4444_4444, 4'hF);
        read_all;

        // pstrb partial writes.
        write_ok(8'h08, 32'hFFFF_FFFF, 4'hF);
        write_ok(8'h08, 32'h1122_3344, 4'b0101);
        transfer(1'b0, 8'h08, 32'd0, 4'd0, data, err);
        check("pstrb 0101", data, 32'h1122_3344);  // wrong on purpose
        write_ok(8'h08, 32'hAABB_CCDD, 4'b1000);
        write_ok(8'h08, 32'h0000_0000, 4'b0000);
        transfer(1'b0, 8'h08, 32'd0, 4'd0, data, err);
        check("pstrb 1000 then 0000", data, 32'hAA22_FF44);
        read_all;

        // Idle gaps between transfers.
        idle(3);
        write_ok(8'h04, 32'h5A5A_5A5A, 4'hF);
        idle(1);
        write_ok(8'h00, 32'h6B6B_6B6B, 4'hF);
        idle(2);
        read_all;

        // Back to back: a write then an immediate read of the same register.
        for (i = 0; i < 8; i = i + 1) begin
            write_ok({4'd0, i[1:0], 2'b00}, 32'h0100_0000 * i + i, 4'hF);
            transfer(1'b0, {4'd0, i[1:0], 2'b00}, 32'd0, 4'd0, data, err);
            check("back-to-back read", data, model[i % 4]);
        end

        // Unmapped addresses: misaligned, and beyond the last register.
        unmapped(8'h05);
        unmapped(8'h0E);
        unmapped(8'h03);
        unmapped(8'h10);
        unmapped(8'hFC);
        unmapped(8'h40);
        read_all;

        // Reset again: every register returns to its reset value.
        idle(1);
        reset_dut;
        read_all;
        idle(2);

        if (errors == 0)
            $display("apb_regs_tb_fail: PASS (%0d checks)", checks);
        $finish;
    end
endmodule
