// A testbench that is wrong on purpose: axi4_lite_regs_tb.v with one bad
// expectation. It expects a wstrb 0101 write to replace the whole register
// (0x11223344) instead of only bytes 0 and 2 (0xFF22FF44). Used to prove a
// failing simulation is a recorded, failed run. Everything else is identical.
//
// Covers reset values, write then read of every register, wstrb partial
// writes, AW before W, W before AW, both together, B and R backpressure,
// back-to-back transactions, SLVERR for unmapped addresses, and the latency
// bound (B and R valid at most 2 cycles after the request is complete).
//
// Inputs are driven just after the falling edge and handshakes are sampled
// 1 ns later, so every check sees the values the next rising edge will use.
`timescale 1ns / 1ps
module axi4_lite_regs_tb_fail;
    localparam [1:0] OKAY = 2'b00;
    localparam [1:0] SLVERR = 2'b10;
    localparam MAX_LATENCY = 2;
    localparam TIMEOUT = 50;

    reg         aclk = 1'b0;
    reg         aresetn = 1'b0;
    reg  [3:0]  awaddr = 4'd0;
    reg         awvalid = 1'b0;
    wire        awready;
    reg  [31:0] wdata = 32'd0;
    reg  [3:0]  wstrb = 4'd0;
    reg         wvalid = 1'b0;
    wire        wready;
    wire [1:0]  bresp;
    wire        bvalid;
    reg         bready = 1'b0;
    reg  [3:0]  araddr = 4'd0;
    reg         arvalid = 1'b0;
    wire        arready;
    wire [31:0] rdata;
    wire [1:0]  rresp;
    wire        rvalid;
    reg         rready = 1'b0;

    integer errors = 0;
    integer checks = 0;
    integer i;
    reg [1:0]  resp;
    reg [31:0] data;
    reg [31:0] model [0:3];

    axi4_lite_regs #(.ADDR_WIDTH(4), .DATA_WIDTH(32)) dut (
        .aclk(aclk), .aresetn(aresetn),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata), .s_axil_wstrb(wstrb), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(rready)
    );

    always #5 aclk = ~aclk;

    task automatic check(input [255:0] what, input [31:0] got, input [31:0] expected);
        begin
            checks = checks + 1;
            if (got !== expected) begin
                $error("%0s: got 0x%08h, expected 0x%08h", what, got, expected);
                errors = errors + 1;
            end
        end
    endtask

    // One write. AW is offered aw_delay cycles after the start and W w_delay
    // cycles after it; BREADY rises b_delay cycles after BVALID is first seen.
    task automatic write(input [3:0] addr, input [31:0] value, input [3:0] strb,
                         input integer aw_delay, input integer w_delay, input integer b_delay,
                         output [1:0] got_resp);
        integer cyc, done_cyc, b_seen_cyc;
        reg aw_done, w_done, b_done;
        reg [1:0] held_resp;
        begin
            cyc = 0;
            done_cyc = -1;
            b_seen_cyc = -1;
            aw_done = 1'b0;
            w_done = 1'b0;
            b_done = 1'b0;
            held_resp = 2'bxx;
            while (!b_done && cyc < TIMEOUT) begin
                awvalid = !aw_done && cyc >= aw_delay;
                awaddr = awvalid ? addr : 4'hx;
                wvalid = !w_done && cyc >= w_delay;
                wdata = wvalid ? value : 32'hxxxxxxxx;
                wstrb = wvalid ? strb : 4'hx;
                bready = b_seen_cyc >= 0 && cyc - b_seen_cyc >= b_delay;
                #1;
                if (bvalid) begin
                    if (!(aw_done && w_done)) begin
                        $error("write 0x%h: BVALID before the request was accepted", addr);
                        errors = errors + 1;
                    end
                    if (b_seen_cyc < 0) begin
                        b_seen_cyc = cyc;
                        held_resp = bresp;
                        check("write latency within bound", {31'd0, cyc - done_cyc <= MAX_LATENCY}, 32'd1);
                    end
                    check("BRESP stable while BVALID waits", {30'd0, bresp}, {30'd0, held_resp});
                    bready = cyc - b_seen_cyc >= b_delay;
                    #1;
                end
                if (awvalid && awready)
                    aw_done = 1'b1;
                if (wvalid && wready)
                    w_done = 1'b1;
                if (done_cyc < 0 && aw_done && w_done)
                    done_cyc = cyc;
                if (bvalid && bready)
                    b_done = 1'b1;
                @(negedge aclk);
                cyc = cyc + 1;
            end
            if (!b_done) begin
                $error("write 0x%h: no response within %0d cycles", addr, TIMEOUT);
                errors = errors + 1;
            end
            awvalid = 1'b0;
            wvalid = 1'b0;
            bready = 1'b0;
            got_resp = held_resp;
        end
    endtask

    // One read. AR is offered ar_delay cycles after the start; RREADY rises
    // r_delay cycles after RVALID is first seen.
    task automatic read(input [3:0] addr, input integer ar_delay, input integer r_delay,
                        output [31:0] got_data, output [1:0] got_resp);
        integer cyc, done_cyc, r_seen_cyc;
        reg ar_done, r_done;
        reg [31:0] held_data;
        reg [1:0] held_resp;
        begin
            cyc = 0;
            done_cyc = -1;
            r_seen_cyc = -1;
            ar_done = 1'b0;
            r_done = 1'b0;
            held_data = 32'hxxxxxxxx;
            held_resp = 2'bxx;
            while (!r_done && cyc < TIMEOUT) begin
                arvalid = !ar_done && cyc >= ar_delay;
                araddr = arvalid ? addr : 4'hx;
                rready = r_seen_cyc >= 0 && cyc - r_seen_cyc >= r_delay;
                #1;
                if (rvalid) begin
                    if (!ar_done) begin
                        $error("read 0x%h: RVALID before the request was accepted", addr);
                        errors = errors + 1;
                    end
                    if (r_seen_cyc < 0) begin
                        r_seen_cyc = cyc;
                        held_data = rdata;
                        held_resp = rresp;
                        check("read latency within bound", {31'd0, cyc - done_cyc <= MAX_LATENCY}, 32'd1);
                    end
                    check("RDATA stable while RVALID waits", rdata, held_data);
                    check("RRESP stable while RVALID waits", {30'd0, rresp}, {30'd0, held_resp});
                    rready = cyc - r_seen_cyc >= r_delay;
                    #1;
                end
                if (arvalid && arready)
                    ar_done = 1'b1;
                if (done_cyc < 0 && ar_done)
                    done_cyc = cyc;
                if (rvalid && rready)
                    r_done = 1'b1;
                @(negedge aclk);
                cyc = cyc + 1;
            end
            if (!r_done) begin
                $error("read 0x%h: no response within %0d cycles", addr, TIMEOUT);
                errors = errors + 1;
            end
            arvalid = 1'b0;
            rready = 1'b0;
            got_data = held_data;
            got_resp = held_resp;
        end
    endtask

    // Reads every register and compares it with the model.
    task automatic read_all(input integer r_delay);
        integer n;
        begin
            for (n = 0; n < 4; n = n + 1) begin
                read({n[1:0], 2'b00}, 0, r_delay, data, resp);
                check("read data", data, model[n]);
                check("read response OKAY", {30'd0, resp}, {30'd0, OKAY});
            end
        end
    endtask

    // A mapped write, checked for OKAY, with the model updated to match.
    task automatic write_ok(input [3:0] addr, input [31:0] value, input [3:0] strb,
                            input integer aw_delay, input integer w_delay, input integer b_delay);
        integer b;
        begin
            write(addr, value, strb, aw_delay, w_delay, b_delay, resp);
            check("write response OKAY", {30'd0, resp}, {30'd0, OKAY});
            for (b = 0; b < 4; b = b + 1)
                if (strb[b])
                    model[addr[3:2]][8*b +: 8] = value[8*b +: 8];
        end
    endtask

    task automatic reset_dut;
        begin
            aresetn = 1'b0;
            repeat (3) @(negedge aclk);
            #1;
            check("AWREADY in reset", {31'd0, awready}, 32'd1);
            check("BVALID in reset", {31'd0, bvalid}, 32'd0);
            check("RVALID in reset", {31'd0, rvalid}, 32'd0);
            aresetn = 1'b1;
            @(negedge aclk);
            for (i = 0; i < 4; i = i + 1)
                model[i] = 32'd0;
        end
    endtask

    initial begin
        @(negedge aclk);
        reset_dut;

        // Reset values: every register reads zero.
        read_all(0);

        // Write then read every register, AW and W together.
        write_ok(4'h0, 32'h1111_1111, 4'hF, 0, 0, 0);
        write_ok(4'h4, 32'h2222_2222, 4'hF, 0, 0, 0);
        write_ok(4'h8, 32'h3333_3333, 4'hF, 0, 0, 0);
        write_ok(4'hC, 32'h4444_4444, 4'hF, 0, 0, 0);
        read_all(0);

        // wstrb partial writes.
        write_ok(4'h8, 32'hFFFF_FFFF, 4'hF, 0, 0, 0);
        write_ok(4'h8, 32'h1122_3344, 4'b0101, 0, 0, 0);
        read(4'h8, 0, 0, data, resp);
        check("wstrb 0101", data, 32'h1122_3344);  // wrong on purpose
        write_ok(4'h8, 32'hAABB_CCDD, 4'b1000, 0, 0, 0);
        write_ok(4'h8, 32'h0000_0000, 4'b0000, 0, 0, 0);
        read(4'h8, 0, 0, data, resp);
        check("wstrb 1000 then 0000", data, 32'hAA22_FF44);
        read_all(0);

        // AW before W, W before AW, and both together after a wait.
        write_ok(4'h0, 32'hA0A0_A0A0, 4'hF, 0, 3, 0);
        write_ok(4'h4, 32'hB1B1_B1B1, 4'hF, 3, 0, 0);
        write_ok(4'hC, 32'hC3C3_C3C3, 4'hF, 2, 2, 0);
        write_ok(4'h8, 32'hD2D2_D2D2, 4'hF, 0, 1, 0);
        write_ok(4'h8, 32'hE2E2_E2E2, 4'hF, 1, 0, 0);
        read_all(0);

        // B and R backpressure.
        write_ok(4'h4, 32'h5A5A_5A5A, 4'hF, 0, 0, 4);
        write_ok(4'h0, 32'h6B6B_6B6B, 4'hF, 0, 2, 3);
        read_all(4);

        // Back-to-back: no idle cycle between transactions.
        for (i = 0; i < 8; i = i + 1)
            write_ok({i[1:0], 2'b00},32'h0100_0000 * i + i, 4'hF, 0, 0, 0);
        for (i = 0; i < 4; i = i + 1) begin
            read({i[1:0], 2'b00},0, 0, data, resp);
            check("back-to-back read", data, model[i]);
        end

        // Unmapped (misaligned) addresses: SLVERR, no write, read data zero.
        write(4'h5, 32'hDEAD_BEEF, 4'hF, 0, 0, 0, resp);
        check("unmapped write SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        write(4'hE, 32'hDEAD_BEEF, 4'hF, 2, 0, 1, resp);
        check("unmapped write SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        read(4'h6, 0, 0, data, resp);
        check("unmapped read SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        check("unmapped read data", data, 32'd0);
        read(4'h3, 0, 2, data, resp);
        check("unmapped read SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        read_all(0);

        // Reset again: every register returns to its reset value.
        reset_dut;
        read_all(0);

        if (errors == 0)
            $display("axi4_lite_regs_tb_fail: PASS (%0d checks)", checks);
        $finish;
    end
endmodule
