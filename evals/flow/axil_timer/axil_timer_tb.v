// Self-checking testbench for axil_timer.v: the whole-flow case flow/axil-timer's
// reference (check 1). It is that case's own copy of the single-seat case's
// tests/fixtures/rtl/axil_timer/axil_timer_tb.v (P3-E2), which stays as it is,
// with every check of that file kept and groups added: RDATA held still under
// backpressure while COUNT runs, a STATUS clear on the edge a one-shot count
// ends, a reset while EXPIRED is set, and, at the end of each lane, the port
// widths, every strobe of LOAD alone and none, CTRL and STATUS bits that read
// as zero, every unmapped address, irq held for 100000 cycles, long counts
// and stops, thirty periods, and long gaps and backpressure. A write leaves
// its address, data and strobes unknown while it does not offer them.
//
// Two lanes run the same checks, one at ADDR_WIDTH 4 and one at ADDR_WIDTH 8
// (where offsets 0x10 and up must get SLVERR, not alias the registers). Each
// lane covers reset values; LOAD write and read back, with wstrb partial
// writes; COUNT read only; SLVERR for unaligned and unmapped offsets, with
// writes changing nothing; a CTRL write with wstrb[0] low changing nothing;
// AW before W and W before AW; B and R backpressure; one-shot counts of 1, 2
// and more cycles, timed to the cycle, with EN clearing itself and no second
// interrupt; the interrupt enable as a mask on a level interrupt; periodic
// counts timed over several periods; an acknowledgement in the very cycle a
// periodic count ends, which must leave EXPIRED set; a restart while running;
// a stop that freezes COUNT and ends the interrupts; RDATA and RRESP held
// still while RVALID waits on a read of a running COUNT; an acknowledgement in
// the very cycle a one-shot count ends, which must leave EXPIRED set; and
// reset in the middle of a count, with EXPIRED set.
//
// Inputs are driven just after the falling edge and outputs are sampled 1 ns
// later, so every check sees the values the next rising edge will use. Each
// lane counts rising edges; a write takes effect on the edge after which
// BVALID is first seen, and a count of LOAD cycles ends LOAD edges later.
`timescale 1ns / 1ps
module axil_timer_tb_lane #(
    parameter AW = 4
) ();
    localparam [1:0] OKAY = 2'b00;
    localparam [1:0] SLVERR = 2'b10;
    localparam TIMEOUT = 50;
    localparam [31:0] EN = 32'h1, IE = 32'h2, PERIODIC = 32'h4;

    reg          aclk = 1'b0;
    reg          aresetn = 1'b0;
    reg  [AW-1:0] awaddr = {AW{1'b0}};
    reg          awvalid = 1'b0;
    wire         awready;
    reg  [31:0]  wdata = 32'd0;
    reg  [3:0]   wstrb = 4'd0;
    reg          wvalid = 1'b0;
    wire         wready;
    wire [1:0]   bresp;
    wire         bvalid;
    reg          bready = 1'b0;
    reg  [AW-1:0] araddr = {AW{1'b0}};
    reg          arvalid = 1'b0;
    wire         arready;
    wire [31:0]  rdata;
    wire [1:0]   rresp;
    wire         rvalid;
    reg          rready = 1'b0;
    wire         irq;

    integer errors = 0;
    integer checks = 0;
    reg     done = 1'b0;
    integer edges = 0;       // rising edges so far
    integer write_edge = 0;  // the edge on which the last write took effect
    integer rise_edge = -1;  // the edge after which irq last rose
    reg     irq_seen = 1'b0;
    integer i, start, first;
    reg     rose;
    reg [1:0]  resp;
    reg [31:0] data;
    reg        hold_irq = 1'b0;  // set: irq must stay high on every cycle
    integer    irq_drops = 0;    // cycles irq was low while hold_irq was set

    axil_timer #(.ADDR_WIDTH(AW)) dut (
        .aclk(aclk), .aresetn(aresetn),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready),
        .s_axil_wdata(wdata), .s_axil_wstrb(wstrb), .s_axil_wvalid(wvalid), .s_axil_wready(wready),
        .s_axil_bresp(bresp), .s_axil_bvalid(bvalid), .s_axil_bready(bready),
        .s_axil_araddr(araddr), .s_axil_arvalid(arvalid), .s_axil_arready(arready),
        .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid), .s_axil_rready(rready),
        .irq(irq)
    );

    always #5 aclk = ~aclk;
    always @(posedge aclk) edges = edges + 1;
    // irq changes only on a rising edge; 1 ns after each one, record the
    // edge after which it rose.
    always @(posedge aclk) begin
        #1;
        if (irq === 1'b1 && !irq_seen)
            rise_edge = edges;
        irq_seen = irq === 1'b1;
        if (hold_irq && irq !== 1'b1)
            irq_drops = irq_drops + 1;
    end

    task automatic check(input [8*48-1:0] what, input [31:0] got, input [31:0] expected);
        begin
            checks = checks + 1;
            if (got !== expected) begin
                $error("lane AW=%0d: %0s: got 0x%08h, expected 0x%08h", AW, what, got, expected);
                errors = errors + 1;
            end
        end
    endtask

    // One write, started at a falling edge. AW is offered aw_delay cycles
    // after the start and W w_delay cycles after it; BREADY rises b_delay
    // cycles after BVALID is first seen. Records the edge it took effect on.
    task automatic write(input [7:0] addr, input [31:0] value, input [3:0] strb,
                         input integer aw_delay, input integer w_delay, input integer b_delay,
                         output [1:0] got_resp);
        integer cyc, b_seen_cyc;
        reg aw_done, w_done, b_done;
        reg [1:0] held_resp;
        begin
            cyc = 0;
            b_seen_cyc = -1;
            aw_done = 1'b0;
            w_done = 1'b0;
            b_done = 1'b0;
            held_resp = 2'bxx;
            while (!b_done && cyc < TIMEOUT) begin
                awvalid = !aw_done && cyc >= aw_delay;
                awaddr = awvalid ? addr[AW-1:0] : {AW{1'bx}};
                wvalid = !w_done && cyc >= w_delay;
                wdata = wvalid ? value : 32'hxxxxxxxx;
                wstrb = wvalid ? strb : 4'hx;
                bready = b_seen_cyc >= 0 && cyc - b_seen_cyc >= b_delay;
                #1;
                if (bvalid) begin
                    if (!(aw_done && w_done)) begin
                        $error("lane AW=%0d: write 0x%h: BVALID before the request was accepted", AW, addr);
                        errors = errors + 1;
                    end
                    if (b_seen_cyc < 0) begin
                        b_seen_cyc = cyc;
                        held_resp = bresp;
                        write_edge = edges;
                    end
                    check("BRESP stable while BVALID waits", {30'd0, bresp}, {30'd0, held_resp});
                end
                if (awvalid && awready)
                    aw_done = 1'b1;
                if (wvalid && wready)
                    w_done = 1'b1;
                if (bvalid && bready)
                    b_done = 1'b1;
                @(negedge aclk);
                cyc = cyc + 1;
            end
            if (!b_done) begin
                $error("lane AW=%0d: write 0x%h: no response within %0d cycles", AW, addr, TIMEOUT);
                errors = errors + 1;
            end
            awvalid = 1'b0;
            wvalid = 1'b0;
            bready = 1'b0;
            got_resp = held_resp;
        end
    endtask

    // One read, started at a falling edge; RREADY rises r_delay cycles after
    // RVALID is first seen.
    task automatic read(input [7:0] addr, input integer r_delay, output [31:0] got_data, output [1:0] got_resp);
        integer cyc, r_seen_cyc;
        reg ar_done, r_done;
        reg [31:0] held_data;
        reg [1:0] held_resp;
        begin
            cyc = 0;
            r_seen_cyc = -1;
            ar_done = 1'b0;
            r_done = 1'b0;
            held_data = 32'hxxxxxxxx;
            held_resp = 2'bxx;
            while (!r_done && cyc < TIMEOUT) begin
                arvalid = !ar_done;
                araddr = arvalid ? addr[AW-1:0] : {AW{1'bx}};
                rready = r_seen_cyc >= 0 && cyc - r_seen_cyc >= r_delay;
                #1;
                if (rvalid) begin
                    if (!ar_done) begin
                        $error("lane AW=%0d: read 0x%h: RVALID before the request was accepted", AW, addr);
                        errors = errors + 1;
                    end
                    if (r_seen_cyc < 0) begin
                        r_seen_cyc = cyc;
                        held_data = rdata;
                        held_resp = rresp;
                    end
                    check("RDATA stable while RVALID waits", rdata, held_data);
                    check("RRESP stable while RVALID waits", {30'd0, rresp}, {30'd0, held_resp});
                end
                if (arvalid && arready)
                    ar_done = 1'b1;
                if (rvalid && rready)
                    r_done = 1'b1;
                @(negedge aclk);
                cyc = cyc + 1;
            end
            if (!r_done) begin
                $error("lane AW=%0d: read 0x%h: no response within %0d cycles", AW, addr, TIMEOUT);
                errors = errors + 1;
            end
            arvalid = 1'b0;
            rready = 1'b0;
            got_data = held_data;
            got_resp = held_resp;
        end
    endtask

    task automatic write_ok(input [7:0] addr, input [31:0] value, input [3:0] strb);
        begin
            write(addr, value, strb, 0, 0, 0, resp);
            check("write OKAY", {30'd0, resp}, {30'd0, OKAY});
        end
    endtask

    task automatic expect_reg(input [8*48-1:0] what, input [7:0] addr, input [31:0] expected);
        begin
            read(addr, 0, data, resp);
            check(what, data, expected);
            check("read OKAY", {30'd0, resp}, {30'd0, OKAY});
        end
    endtask

    // An unmapped or read-only write: SLVERR, and no register changes.
    task automatic write_err(input [7:0] addr, input [31:0] value);
        begin
            write(addr, value, 4'hF, 0, 0, 0, resp);
            check("write SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        end
    endtask

    task automatic read_err(input [7:0] addr);
        begin
            read(addr, 0, data, resp);
            check("read SLVERR", {30'd0, resp}, {30'd0, SLVERR});
            check("read SLVERR data", data, 32'd0);
        end
    endtask

    // Waits up to limit falling edges for irq; reports whether it rose.
    task automatic wait_irq(input integer limit, output reg rose);
        integer n;
        begin
            n = 0;
            while (irq !== 1'b1 && n < limit) begin
                @(negedge aclk);
                #1;
                n = n + 1;
            end
            rose = irq === 1'b1;
        end
    endtask

    // Watches irq for cycles falling edges; it must stay low.
    task automatic quiet(input [8*48-1:0] what, input integer cycles);
        integer n, high;
        begin
            high = 0;
            for (n = 0; n < cycles; n = n + 1) begin
                @(negedge aclk);
                #1;
                if (irq !== 1'b0)
                    high = high + 1;
            end
            check(what, high, 0);
        end
    endtask

    task automatic reset_dut;
        begin
            aresetn = 1'b0;
            repeat (3) @(negedge aclk);
            aresetn = 1'b1;
            @(negedge aclk);
            #1;
        end
    endtask

    // A one-shot count of load cycles with the interrupt enabled: timed to
    // the edge, EN clears itself, COUNT is zero, and there is no second
    // interrupt after the acknowledgement.
    task automatic one_shot(input [31:0] load);
        integer cycles;
        begin
            cycles = load == 0 ? 1 : load;
            write_ok(8'h04, load, 4'hF);
            write_ok(8'h00, EN | IE, 4'h1);
            start = write_edge;
            wait_irq(cycles + 4, rose);
            check("one-shot interrupt", {31'd0, rose}, 32'd1);
            check("one-shot length in cycles", rise_edge - start, cycles);
            expect_reg("one-shot EN clears itself", 8'h00, IE);
            expect_reg("one-shot COUNT at zero", 8'h08, 32'd0);
            expect_reg("one-shot EXPIRED", 8'h0C, 32'd1);
            write_ok(8'h0C, 32'd1, 4'h1);
            check("irq after the acknowledgement", {31'd0, irq}, 32'd0);
            expect_reg("EXPIRED after the acknowledgement", 8'h0C, 32'd0);
            quiet("no second one-shot interrupt", 3 * cycles + 6);
            expect_reg("one-shot stays stopped", 8'h00, IE);
        end
    endtask

    initial begin
        @(negedge aclk);
        reset_dut;

        // Reset values.
        for (i = 0; i < 4; i = i + 1)
            expect_reg("reset value", {i[5:0], 2'b00}, 32'd0);
        check("irq after reset", {31'd0, irq}, 32'd0);

        // LOAD read back, with partial strobes; AW and W in either order; backpressure.
        write_ok(8'h04, 32'h1234_5678, 4'hF);
        expect_reg("LOAD read back", 8'h04, 32'h1234_5678);
        write_ok(8'h04, 32'hAABB_CCDD, 4'b0101);
        expect_reg("LOAD wstrb 0101", 8'h04, 32'h12BB_56DD);
        write(8'h04, 32'h0000_0100, 4'hF, 3, 0, 2, resp);
        check("W before AW OKAY", {30'd0, resp}, {30'd0, OKAY});
        write(8'h04, 32'h0000_0200, 4'b0011, 0, 3, 1, resp);
        check("AW before W OKAY", {30'd0, resp}, {30'd0, OKAY});
        read(8'h04, 3, data, resp);
        check("LOAD after both orders, R backpressure", data, 32'h0000_0200);

        // COUNT is read only; unaligned and unmapped offsets get SLVERR and change nothing.
        write_err(8'h08, 32'd5);
        expect_reg("COUNT unchanged by a write", 8'h08, 32'd0);
        write_err(8'h05, 32'hFFFF_FFFF);
        write_err(8'h01, EN | IE);
        read_err(8'h06);
        read_err(8'h0B);
        if (AW > 4) begin
            write_err(8'h14, 32'hDEAD_BEEF);
            write_err(8'h10, EN | IE);
            write_err(8'h1C, 32'd1);
            write_err(8'h40, 32'hDEAD_BEEF);
            write_err(8'hFC, 32'hDEAD_BEEF);
            read_err(8'h10);
            read_err(8'h14);
            read_err(8'h44);
            read_err(8'hFC);
        end
        expect_reg("LOAD unchanged by unmapped writes", 8'h04, 32'h0000_0200);
        expect_reg("CTRL unchanged by unmapped writes", 8'h00, 32'd0);

        // A CTRL write with wstrb[0] low changes nothing.
        write_ok(8'h00, EN | IE | PERIODIC, 4'b1110);
        expect_reg("CTRL unchanged without wstrb[0]", 8'h00, 32'd0);
        quiet("no count without wstrb[0]", 8);

        // One-shot counts, timed to the edge.
        one_shot(32'd0);
        one_shot(32'd1);
        one_shot(32'd2);
        one_shot(32'd9);

        // The interrupt enable masks a level interrupt: EXPIRED is set, irq
        // follows IE until the acknowledgement.
        write_ok(8'h04, 32'd4, 4'hF);
        write_ok(8'h00, EN, 4'hF);
        quiet("masked count raises no interrupt", 10);
        expect_reg("masked count sets EXPIRED", 8'h0C, 32'd1);
        write_ok(8'h00, IE, 4'hF);
        check("IE raises the pending interrupt", {31'd0, irq}, 32'd1);
        write_ok(8'h00, 32'd0, 4'hF);
        check("IE low masks it again", {31'd0, irq}, 32'd0);
        write_ok(8'h0C, 32'd0, 4'hF);
        expect_reg("writing 0 to STATUS clears nothing", 8'h0C, 32'd1);
        write_ok(8'h0C, 32'd1, 4'b1110);
        expect_reg("STATUS clear needs wstrb[0]", 8'h0C, 32'd1);
        write_ok(8'h0C, 32'd1, 4'h1);
        expect_reg("STATUS cleared", 8'h0C, 32'd0);

        // Periodic counts: each period is LOAD cycles, and EN stays set.
        write_ok(8'h04, 32'd7, 4'hF);
        write_ok(8'h00, EN | IE | PERIODIC, 4'h1);
        start = write_edge;
        for (i = 0; i < 4; i = i + 1) begin
            wait_irq(12, rose);
            check("periodic interrupt", {31'd0, rose}, 32'd1);
            check("periodic period in cycles", rise_edge - start, 7);
            start = rise_edge;
            write_ok(8'h0C, 32'd1, 4'h1);
        end
        read(8'h00, 0, data, resp);
        check("periodic EN stays set", data, EN | IE | PERIODIC);

        // An acknowledgement in the cycle a periodic count ends leaves
        // EXPIRED set: the next count end is start + 7. A write with no
        // delays takes effect on the first edge after it starts.
        while (edges < start + 6)
            @(negedge aclk);
        write_ok(8'h0C, 32'd1, 4'h1);
        check("acknowledgement lands on the count end", write_edge, start + 7);
        expect_reg("a count end beats a same-cycle clear", 8'h0C, 32'd1);

        // A stop: COUNT freezes, EN reads 0, and no more interrupts come.
        write_ok(8'h00, IE | PERIODIC, 4'h1);
        read(8'h08, 0, first, resp);
        expect_reg("stop freezes COUNT", 8'h08, first);
        expect_reg("stop clears EN", 8'h00, IE | PERIODIC);
        write_ok(8'h0C, 32'd1, 4'h1);
        expect_reg("STATUS cleared after the stop", 8'h0C, 32'd0);
        quiet("no interrupt after a stop", 20);
        expect_reg("COUNT still frozen", 8'h08, first);

        // A restart while running counts LOAD cycles from the restart.
        write_ok(8'h04, 32'd12, 4'hF);
        write_ok(8'h00, EN | IE, 4'h1);
        repeat (5) @(negedge aclk);
        write_ok(8'h00, EN | IE, 4'h1);
        start = write_edge;
        wait_irq(20, rose);
        check("restart interrupt", {31'd0, rose}, 32'd1);
        check("restart counts from the restart", rise_edge - start, 12);
        write_ok(8'h0C, 32'd1, 4'h1);

        // A read waiting on RREADY holds RDATA still, even while the register
        // it read changes: COUNT, read with backpressure during a count (the
        // read task checks RDATA and RRESP on every cycle RVALID waits). Only
        // the response is judged here, not the value read.
        write_ok(8'h04, 32'd20, 4'hF);
        write_ok(8'h00, EN, 4'h1);
        read(8'h08, 5, data, resp);
        check("read of a running COUNT OKAY", {30'd0, resp}, {30'd0, OKAY});
        read(8'h08, 3, data, resp);
        check("read of a running COUNT OKAY", {30'd0, resp}, {30'd0, OKAY});
        write_ok(8'h00, 32'd0, 4'h1);
        write_ok(8'h0C, 32'd1, 4'h1);
        expect_reg("STATUS cleared after the running reads", 8'h0C, 32'd0);

        // An acknowledgement in the cycle a one-shot count ends leaves EXPIRED
        // set too: the count started on edge start ends on start + 7.
        write_ok(8'h04, 32'd7, 4'hF);
        write_ok(8'h00, EN | IE, 4'h1);
        start = write_edge;
        while (edges < start + 6)
            @(negedge aclk);
        write_ok(8'h0C, 32'd1, 4'h1);
        check("one-shot acknowledgement lands on the count end", write_edge, start + 7);
        expect_reg("a one-shot count end beats a same-cycle clear", 8'h0C, 32'd1);
        expect_reg("the one-shot count ended", 8'h00, IE);

        // Reset in the middle of a periodic count clears everything, EXPIRED
        // too: it is still set from the one-shot count above, and irq is high.
        write_ok(8'h04, 32'd30, 4'hF);
        write_ok(8'h00, EN | IE | PERIODIC, 4'h1);
        repeat (4) @(negedge aclk);
        check("irq high, EXPIRED set, before the reset", {31'd0, irq}, 32'd1);
        reset_dut;
        check("irq after a reset with EXPIRED set", {31'd0, irq}, 32'd0);
        for (i = 0; i < 4; i = i + 1)
            expect_reg("value after reset", {i[5:0], 2'b00}, 32'd0);
        quiet("no interrupt after reset", 40);

        // Every port has the width the document gives it.
        check("s_axil_awaddr width", $bits(dut.s_axil_awaddr), AW);
        check("s_axil_awvalid width", $bits(dut.s_axil_awvalid), 1);
        check("s_axil_awready width", $bits(dut.s_axil_awready), 1);
        check("s_axil_wdata width", $bits(dut.s_axil_wdata), 32);
        check("s_axil_wstrb width", $bits(dut.s_axil_wstrb), 4);
        check("s_axil_wvalid width", $bits(dut.s_axil_wvalid), 1);
        check("s_axil_wready width", $bits(dut.s_axil_wready), 1);
        check("s_axil_bresp width", $bits(dut.s_axil_bresp), 2);
        check("s_axil_bvalid width", $bits(dut.s_axil_bvalid), 1);
        check("s_axil_bready width", $bits(dut.s_axil_bready), 1);
        check("s_axil_araddr width", $bits(dut.s_axil_araddr), AW);
        check("s_axil_arvalid width", $bits(dut.s_axil_arvalid), 1);
        check("s_axil_arready width", $bits(dut.s_axil_arready), 1);
        check("s_axil_rdata width", $bits(dut.s_axil_rdata), 32);
        check("s_axil_rresp width", $bits(dut.s_axil_rresp), 2);
        check("s_axil_rvalid width", $bits(dut.s_axil_rvalid), 1);
        check("s_axil_rready width", $bits(dut.s_axil_rready), 1);
        check("irq width", $bits(dut.irq), 1);
        check("aclk width", $bits(dut.aclk), 1);
        check("aresetn width", $bits(dut.aresetn), 1);

        // LOAD holds all 32 bits, and each strobe alone writes only its own byte.
        write_ok(8'h04, 32'hFFFF_FFFF, 4'hF);
        expect_reg("LOAD all ones", 8'h04, 32'hFFFF_FFFF);
        write_ok(8'h04, 32'd0, 4'b0001);
        expect_reg("LOAD wstrb 0001", 8'h04, 32'hFFFF_FF00);
        write_ok(8'h04, 32'd0, 4'b0010);
        expect_reg("LOAD wstrb 0010", 8'h04, 32'hFFFF_0000);
        write_ok(8'h04, 32'd0, 4'b0100);
        expect_reg("LOAD wstrb 0100", 8'h04, 32'hFF00_0000);
        write_ok(8'h04, 32'd0, 4'b1000);
        expect_reg("LOAD wstrb 1000", 8'h04, 32'h0000_0000);
        write_ok(8'h04, 32'hA5C3_96E1, 4'b1010);
        expect_reg("LOAD wstrb 1010", 8'h04, 32'hA500_9600);
        write_ok(8'h04, 32'h1234_5678, 4'b0000);
        expect_reg("LOAD wstrb 0000 writes nothing", 8'h04, 32'hA500_9600);
        write_ok(8'h00, EN | IE | PERIODIC, 4'b0000);
        expect_reg("CTRL wstrb 0000 writes nothing", 8'h00, 32'd0);
        quiet("no count after a CTRL write with no strobe", 8);

        // CTRL bits 31:3 and STATUS bits 31:1 read as zero, whatever is written.
        write_ok(8'h00, 32'hFFFF_FFF8, 4'hF);
        expect_reg("CTRL bits 31:3 read as zero", 8'h00, 32'd0);
        write_ok(8'h00, 32'hFFFF_FFFE, 4'hF);
        expect_reg("CTRL bits 31:3 read as zero, IE and MODE", 8'h00, IE | PERIODIC);
        write_ok(8'h00, 32'd0, 4'hF);
        write_ok(8'h0C, 32'hFFFF_FFFE, 4'hF);
        expect_reg("STATUS bits 31:1 read as zero", 8'h0C, 32'd0);

        // Every address but the four registers' is unmapped: with EXPIRED set,
        // irq high and the count stopped, a write of all ones to each other
        // address (COUNT too) gets SLVERR and changes nothing, and a read of
        // each gets SLVERR and zero. irq stays high on every cycle of it.
        write_ok(8'h04, 32'd3, 4'hF);
        write_ok(8'h00, EN, 4'h1);
        repeat (6) @(negedge aclk);
        write_ok(8'h04, 32'h0000_0055, 4'hF);
        write_ok(8'h00, IE | PERIODIC, 4'h1);
        check("irq high before the address sweep", {31'd0, irq}, 32'd1);
        hold_irq = 1'b1;
        for (i = 0; i < (1 << AW); i = i + 1)
            if (i[1:0] != 2'b00 || i >= 16 || i == 8) begin
                write_err(i[7:0], 32'hFFFF_FFFF);
                if (i != 8)
                    read_err(i[7:0]);
            end
        expect_reg("LOAD unchanged by the address sweep", 8'h04, 32'h0000_0055);
        expect_reg("CTRL unchanged by the address sweep", 8'h00, IE | PERIODIC);
        expect_reg("COUNT unchanged by the address sweep", 8'h08, 32'd0);
        expect_reg("STATUS unchanged by the address sweep", 8'h0C, 32'd1);
        write_ok(8'h0C, 32'hFFFF_FFFE, 4'hF);
        expect_reg("STATUS bits 31:1 read as zero, EXPIRED set", 8'h0C, 32'd1);

        // irq stays high until EXPIRED is cleared or IE is written 0: through
        // 100000 idle cycles and through writes that do neither.
        repeat (100000) @(negedge aclk);
        write_ok(8'h04, 32'd9, 4'hF);
        write_ok(8'h0C, 32'd0, 4'hF);
        write_ok(8'h0C, 32'd1, 4'b1110);
        write_ok(8'h0C, 32'd1, 4'b0000);
        write_ok(8'h00, IE, 4'h1);
        write_ok(8'h00, IE | PERIODIC, 4'b1111);
        expect_reg("STATUS still set while irq is held", 8'h0C, 32'd1);
        hold_irq = 1'b0;
        check("irq high until EXPIRED cleared or IE 0", irq_drops, 0);
        write_ok(8'h00, PERIODIC, 4'h1);
        check("IE written 0 lowers irq", {31'd0, irq}, 32'd0);
        write_ok(8'h00, IE, 4'h1);
        check("IE written 1 raises irq again", {31'd0, irq}, 32'd1);
        write_ok(8'h0C, 32'd1, 4'h1);
        check("the clear lowers irq", {31'd0, irq}, 32'd0);

        // Long counts, timed to the edge: 300 cycles, and 65539 (above 16 bits).
        one_shot(32'd300);
        write_ok(8'h04, 32'h0001_0003, 4'hF);
        write_ok(8'h00, EN | IE, 4'h1);
        start = write_edge;
        wait_irq(32'h0001_0003 + 4, rose);
        check("long one-shot interrupt", {31'd0, rose}, 32'd1);
        check("long one-shot length in cycles", rise_edge - start, 32'h0001_0003);
        write_ok(8'h0C, 32'd1, 4'h1);
        quiet("no second interrupt after the long one-shot", 70000);
        expect_reg("the long one-shot stays stopped", 8'h00, IE);
        expect_reg("no second count end after the long one-shot", 8'h0C, 32'd0);

        // A stop: COUNT went down by one on every edge after the start, the
        // stop edge too, from all 32 bits of LOAD. EN written 0 again leaves
        // it, and no count ends while stopped.
        write_ok(8'h04, 32'hFFFF_FFFF, 4'hF);
        write_ok(8'h00, EN | IE, 4'h1);
        start = write_edge;
        repeat (40) @(negedge aclk);
        write_ok(8'h00, IE, 4'h1);
        first = 32'hFFFF_FFFF - (write_edge - start);
        expect_reg("COUNT after a stop, all 32 bits", 8'h08, first);
        write_ok(8'h00, IE, 4'h1);
        expect_reg("EN written 0 again leaves COUNT", 8'h08, first);
        quiet("no interrupt while stopped", 2000);
        expect_reg("COUNT frozen while stopped", 8'h08, first);
        expect_reg("EN stays 0 while stopped", 8'h00, IE);
        expect_reg("no count end while stopped", 8'h0C, 32'd0);
        write_ok(8'h04, 32'd25, 4'hF);
        write_ok(8'h00, EN | IE, 4'h1);
        start = write_edge;
        repeat (10) @(negedge aclk);
        write_ok(8'h00, IE, 4'h1);
        expect_reg("COUNT after a stop", 8'h08, 25 - (write_edge - start));

        // Thirty periods in a row, each LOAD cycles, with EN set throughout.
        write_ok(8'h04, 32'd8, 4'hF);
        write_ok(8'h00, EN | IE | PERIODIC, 4'h1);
        start = write_edge;
        for (i = 0; i < 30; i = i + 1) begin
            wait_irq(12, rose);
            check("periodic interrupt, thirty periods", {31'd0, rose}, 32'd1);
            check("periodic period, thirty periods", rise_edge - start, 8);
            start = rise_edge;
            write_ok(8'h0C, 32'd1, 4'h1);
        end
        expect_reg("periodic EN set after thirty periods", 8'h00, EN | IE | PERIODIC);
        write_ok(8'h00, IE | PERIODIC, 4'h1);
        check("the stop lands before the next count end", {31'd0, write_edge < start + 8}, 32'd1);
        quiet("no interrupt after the periodic stop", 20);

        // Three periods of 300 cycles.
        write_ok(8'h04, 32'd300, 4'hF);
        write_ok(8'h00, EN | IE | PERIODIC, 4'h1);
        start = write_edge;
        for (i = 0; i < 3; i = i + 1) begin
            wait_irq(304, rose);
            check("periodic interrupt, LOAD 300", {31'd0, rose}, 32'd1);
            check("periodic period, LOAD 300", rise_edge - start, 300);
            start = rise_edge;
            write_ok(8'h0C, 32'd1, 4'h1);
        end
        write_ok(8'h00, IE | PERIODIC, 4'h1);
        check("LOAD 300 stop lands before next count end", {31'd0, write_edge < start + 300}, 32'd1);
        quiet("no interrupt after the LOAD 300 stop", 20);

        // Write address and data apart by 40 cycles either way, and responses
        // held for 40 cycles of backpressure.
        write(8'h04, 32'h0000_1234, 4'hF, 0, 40, 0, resp);
        check("AW 40 cycles before W OKAY", {30'd0, resp}, {30'd0, OKAY});
        expect_reg("LOAD after AW 40 cycles before W", 8'h04, 32'h0000_1234);
        write(8'h04, 32'h0000_5678, 4'hF, 40, 0, 0, resp);
        check("W 40 cycles before AW OKAY", {30'd0, resp}, {30'd0, OKAY});
        expect_reg("LOAD after W 40 cycles before AW", 8'h04, 32'h0000_5678);
        write(8'h04, 32'h0000_9ABC, 4'hF, 0, 0, 40, resp);
        check("B backpressure 40 cycles OKAY", {30'd0, resp}, {30'd0, OKAY});
        write(8'h05, 32'h0000_0000, 4'hF, 0, 0, 40, resp);
        check("B backpressure 40 cycles SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        read(8'h04, 40, data, resp);
        check("R backpressure 40 cycles", data, 32'h0000_9ABC);
        check("R backpressure 40 cycles OKAY", {30'd0, resp}, {30'd0, OKAY});
        read(8'h07, 40, data, resp);
        check("R backpressure 40 cycles SLVERR", {30'd0, resp}, {30'd0, SLVERR});
        check("R backpressure 40 cycles SLVERR data", data, 32'd0);

        done = 1'b1;
    end
endmodule

module axil_timer_tb;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer checks, errors;

    axil_timer_tb_lane #(.AW(4)) lane4 ();
    axil_timer_tb_lane #(.AW(8)) lane8 ();

    initial begin
        wait (lane4.done && lane8.done);
        checks = lane4.checks + lane8.checks;
        errors = lane4.errors + lane8.errors;
        if (checks < 300) begin
            $error("too few checks: %0d", checks);
            errors = errors + 1;
        end
        if (errors == 0)
            $display("axil_timer_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
