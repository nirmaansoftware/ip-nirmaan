// Self-checking testbench for axi4_lite_regs.v: the whole-flow case
// flow/axi4-lite-regs-driver's reference (check 1). It is that case's own copy
// of the single-seat case's tests/fixtures/rtl/axi4_lite/axi4_lite_regs_tb.v,
// which stays as it is, with every check of that file kept and groups added:
// back-to-back requests accepted in the cycle after the response is taken
// (with and without a wait on READY), reset in the middle of a transaction,
// responses dropped by the first reset edge, every register bit, each strobe
// alone, every unmapped address, and write halves 40 cycles apart. It drops
// one check of the original, "AWREADY in reset", which no flow document states
// (AXIL-TEST-RANGE; tests/test_whole_flow_cases.py lists it as the exemption).
//
// Covers reset values, write then read of every register, wstrb partial
// writes, AW before W, W before AW, both together, B and R backpressure,
// back-to-back transactions, SLVERR for unmapped addresses, the latency
// bound (B and R valid at most 2 cycles after the request is complete), a
// new request accepted in the cycle after a response is taken, and reset
// while a write response waits, while a read response waits, and with only
// the address or only the data of a write accepted.
//
// Inputs are driven just after the falling edge and handshakes are sampled
// 1 ns later, so every check sees the values the next rising edge will use.
`timescale 1ns / 1ps
module axi4_lite_regs_tb;
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
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer i;
    reg [1:0]  resp;
    reg [31:0] data;
    reg [31:0] model [0:3];
    reg        b2b = 1'b0;  // set: the request offered first must be accepted on the next edge

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
                if (b2b && cyc == 0)
                    check("next-cycle write accepted", {31'd0, awready && wready}, 32'd1);
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
                if (b2b && cyc == 0)
                    check("next-cycle read accepted", {31'd0, arready}, 32'd1);
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
            @(negedge aclk);
            #1;
            check("BVALID after the first reset edge", {31'd0, bvalid}, 32'd0);
            check("RVALID after the first reset edge", {31'd0, rvalid}, 32'd0);
            repeat (2) @(negedge aclk);
            #1;
            // No AWREADY check here: the original's "AWREADY in reset" is a rule of
            // the single-seat microarchitecture only (AXIL-TEST-RANGE).
            check("BVALID in reset", {31'd0, bvalid}, 32'd0);
            check("RVALID in reset", {31'd0, rvalid}, 32'd0);
            aresetn = 1'b1;
            @(negedge aclk);
            for (i = 0; i < 4; i = i + 1)
                model[i] = 32'd0;
        end
    endtask

    // Offers part of a transaction for 4 cycles, then resets the block with it
    // still in progress. kind 0: a write to 0x4, left waiting for BREADY;
    // kind 1: a read of 0x8, left waiting for RREADY; kind 2: a write address
    // (0x4) alone; kind 3: write data (0x5555_5555) alone. Each valid drops
    // after the edge that accepts it, and every valid drops when reset starts.
    task automatic reset_during(input integer kind);
        integer n;
        reg aw_hs, w_hs, ar_hs;
        begin
            awvalid = kind == 0 || kind == 2;
            awaddr = awvalid ? 4'h4 : 4'hx;
            wvalid = kind == 0 || kind == 3;
            wdata = kind == 0 ? 32'h7777_7777 : kind == 3 ? 32'h5555_5555 : 32'hxxxxxxxx;
            wstrb = wvalid ? 4'hF : 4'hx;
            arvalid = kind == 1;
            araddr = arvalid ? 4'h8 : 4'hx;
            bready = 1'b0;
            rready = 1'b0;
            for (n = 0; n < 4; n = n + 1) begin
                #1;
                aw_hs = awvalid && awready;
                w_hs = wvalid && wready;
                ar_hs = arvalid && arready;
                @(negedge aclk);
                if (aw_hs)
                    awvalid = 1'b0;
                if (w_hs)
                    wvalid = 1'b0;
                if (ar_hs)
                    arvalid = 1'b0;
            end
            awvalid = 1'b0;
            wvalid = 1'b0;
            arvalid = 1'b0;
            reset_dut;
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
        check("wstrb 0101", data, 32'hFF22_FF44);
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

        // Back-to-back: no idle cycle between transactions. Each write after
        // the first, and each read after the first, is offered in the cycle
        // after the previous response was taken, and must be accepted on the
        // next edge (AW and W together, or AR).
        for (i = 0; i < 8; i = i + 1) begin
            b2b = i > 0;
            write_ok({i[1:0], 2'b00},32'h0100_0000 * i + i, 4'hF, 0, 0, 0);
        end
        for (i = 0; i < 4; i = i + 1) begin
            b2b = i > 0;
            read({i[1:0], 2'b00},0, 0, data, resp);
            check("back-to-back read", data, model[i]);
        end
        b2b = 1'b0;

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

        // Reset in the middle of a transaction. A write response waiting on
        // BREADY, and a read response waiting on RREADY, are dropped: no
        // response is valid during or after reset (reset_dut checks during).
        write_ok(4'h4, 32'h7777_7777, 4'hF, 0, 0, 0);
        reset_during(0);
        check("BVALID after reset mid-write", {31'd0, bvalid}, 32'd0);
        read_all(0);
        write_ok(4'h8, 32'h8888_8888, 4'hF, 0, 0, 0);
        reset_during(1);
        check("RVALID after reset mid-read", {31'd0, rvalid}, 32'd0);
        read_all(0);
        // A write with only its address, or only its data, accepted before
        // reset is discarded: the next write, offered the other way round,
        // completes only with its own address and data.
        reset_during(2);
        write_ok(4'h8, 32'h1357_9BDF, 4'hF, 3, 0, 0);
        read_all(0);
        reset_during(3);
        write_ok(4'hC, 32'h2468_ACE0, 4'hF, 0, 3, 0);
        read_all(0);

        // Every register holds all 32 bits: all ones, then all zeros.
        for (i = 0; i < 4; i = i + 1)
            write_ok({i[1:0], 2'b00}, 32'hFFFF_FFFF, 4'hF, 0, 0, 0);
        read_all(0);
        for (i = 0; i < 4; i = i + 1)
            write_ok({i[1:0], 2'b00}, 32'h0000_0000, 4'hF, 0, 0, 0);
        read_all(0);

        // Each strobe alone writes only its own byte.
        write_ok(4'h4, 32'hFFFF_FFFF, 4'hF, 0, 0, 0);
        for (i = 0; i < 4; i = i + 1) begin
            write_ok(4'h4, 32'h0000_0000, 4'b0001 << i, 0, 0, 0);
            read_all(0);
        end
        write_ok(4'h8, 32'hA5C3_96E1, 4'b0001, 0, 0, 0);
        write_ok(4'h8, 32'hA5C3_96E1, 4'b0010, 0, 0, 0);
        write_ok(4'h8, 32'hA5C3_96E1, 4'b0100, 0, 0, 0);
        write_ok(4'h8, 32'hA5C3_96E1, 4'b1000, 0, 0, 0);
        read_all(0);

        // Every address but the four registers' is unmapped: a write of all
        // ones to each gets SLVERR and changes no register, and a read of each
        // gets SLVERR and zero.
        write_ok(4'h0, 32'h0123_4567, 4'hF, 0, 0, 0);
        write_ok(4'h4, 32'h89AB_CDEF, 4'hF, 0, 0, 0);
        write_ok(4'h8, 32'h7654_3210, 4'hF, 0, 0, 0);
        write_ok(4'hC, 32'hFEDC_BA98, 4'hF, 0, 0, 0);
        for (i = 0; i < 16; i = i + 1)
            if (i[1:0] != 2'b00) begin
                write(i[3:0], 32'hFFFF_FFFF, 4'hF, 0, 0, 0, resp);
                check("unmapped write SLVERR, every address", {30'd0, resp}, {30'd0, SLVERR});
                read(i[3:0], 0, 0, data, resp);
                check("unmapped read SLVERR, every address", {30'd0, resp}, {30'd0, SLVERR});
                check("unmapped read data, every address", data, 32'd0);
            end
        read_all(0);

        // Write address and data apart by 40 cycles either way.
        write_ok(4'h4, 32'h1357_2468, 4'hF, 0, 40, 0);
        write_ok(4'hC, 32'h8642_7531, 4'hF, 40, 0, 0);
        read_all(0);

        // Back-to-back after responses that waited on READY: each request
        // after the first is offered in the cycle after the previous response
        // was taken, and must be accepted on the next edge.
        for (i = 0; i < 8; i = i + 1) begin
            b2b = i > 0;
            write_ok({i[1:0], 2'b00}, 32'h0300_0000 * i + 32'h55, 4'hF, 0, 0, 2);
        end
        for (i = 0; i < 4; i = i + 1) begin
            b2b = i > 0;
            read({i[1:0], 2'b00}, 0, 2, data, resp);
            check("back-to-back read after a wait", data, model[i]);
        end
        b2b = 1'b0;

        if (errors == 0)
            $display("axi4_lite_regs_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
