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

        // The coverage matrix (G3, one round that closes classes): the tasks below.
        matrix;

        done = 1'b1;
    end

    // --- The coverage matrix (G3, one round that closes classes) -----------------------------
    // Each class is closed in both lanes, not sampled:
    // * writes: ordering (AW and W together, AW first, W first) x every address class (each
    //   register, every unaligned offset, and at ADDR_WIDTH 8 offsets from 0x10 up, aligned and
    //   not, with each high bit) x every wstrb value (0, the fourteen partial ones, full);
    // * reads: every address class, with RREADY 0, 1 and 2 cycles late;
    // * a protocol monitor that judges READY and the response edges on every edge of the whole
    //   run, so the ready timing after every OKAY and SLVERR response, back to back, and reads
    //   and writes overlapping in both orders, are judged too (TMR-READY, TMR-RESPONSE-EDGE);
    // * one-shot and periodic counts with LOAD 0, 1, 2, 37 and 0x0001_0005, irq checked after
    //   every edge against STATUS clears landed on every phase of the count;
    // * restarts, stops and LOAD writes in the middle of a count, in both modes;
    // * CTRL with every strobe and EN 0 and 1 in the data, running and stopped;
    // * irq after the very edge of an IE write or a STATUS clear (TMR-IRQ-EDGE).
    // No CTRL write is landed on a count end (TMR-CTRL-WINS stays unjudged): a periodic count
    // of LOAD 0 to 2 is ended by a reset with no transfer in progress.
    localparam [31:0] BIG = 32'h0010_0000;  // a count that never ends inside the matrix
    reg        mon_on = 1'b0;    // set once the first reset ends
    integer    mon_errors = 0;   // monitor failures (the first five are printed)
    reg        m_aw_held = 1'b0; // a write address held, by the monitor's own count
    reg        m_w_held = 1'b0;  // write data held, likewise
    reg        irq_hist [0:4095];  // irq after each edge, by edge number mod 4096
    integer    clr_edge [0:15];    // the edges a trace's STATUS clears took effect on
    integer    n_addr;
    reg [31:0] m_load, m_ctrl, m_count;
    reg        m_run;
    integer    m_start;

    initial begin
        @(posedge aresetn);
        mon_on = 1'b1;
    end

    task automatic mon_fail(input [8*48-1:0] what, input [31:0] got, input [31:0] expected);
        begin
            if (mon_errors < 5)
                $error("lane AW=%0d: %0s: got 0x%08h, expected 0x%08h", AW, what, got, expected);
            mon_errors = mon_errors + 1;
        end
    endtask

    // On every edge: the values the edge uses, sampled at the edge before the block updates;
    // then, 1 ns later, what the edge must have done. READY is high exactly when nothing of its
    // direction is held and no response of its direction waits; VALID rises after the very
    // edge that completes a write or accepts a read address, and drops after the edge that
    // takes it.
    always @(posedge aclk) begin : monitor
        reg aw_hs, w_hs, ar_hs, b_hs, r_hs, bv, rv, rst, done_w;
        rst = aresetn !== 1'b1;
        bv = bvalid === 1'b1;
        rv = rvalid === 1'b1;
        aw_hs = awvalid === 1'b1 && awready === 1'b1;
        w_hs = wvalid === 1'b1 && wready === 1'b1;
        ar_hs = arvalid === 1'b1 && arready === 1'b1;
        b_hs = bv && bready === 1'b1;
        r_hs = rv && rready === 1'b1;
        if (mon_on && !rst) begin
            if (awready !== (!m_aw_held && !bv))
                mon_fail("monitor: AWREADY", {31'd0, awready}, {31'd0, !m_aw_held && !bv});
            if (wready !== (!m_w_held && !bv))
                mon_fail("monitor: WREADY", {31'd0, wready}, {31'd0, !m_w_held && !bv});
            if (arready !== !rv)
                mon_fail("monitor: ARREADY", {31'd0, arready}, {31'd0, !rv});
        end
        done_w = (m_aw_held || aw_hs) && (m_w_held || w_hs);
        #1;
        irq_hist[edges % 4096] = irq === 1'b1;
        if (mon_on && !rst) begin
            if (bvalid !== (done_w || (bv && !b_hs)))
                mon_fail("monitor: BVALID after the edge", {31'd0, bvalid}, {31'd0, done_w || (bv && !b_hs)});
            if (rvalid !== (ar_hs || (rv && !r_hs)))
                mon_fail("monitor: RVALID after the edge", {31'd0, rvalid}, {31'd0, ar_hs || (rv && !r_hs)});
        end
        if (rst || done_w) begin
            m_aw_held = 1'b0;
            m_w_held = 1'b0;
        end else begin
            if (aw_hs)
                m_aw_held = 1'b1;
            if (w_hs)
                m_w_held = 1'b1;
        end
    end

    // The address classes of this lane: all 16 offsets below 0x10, and at ADDR_WIDTH 8 the
    // register offsets with each high bit (0x10, 0x20, 0x40, 0x80) and with all four, and four
    // unaligned offsets from 0x10 up.
    function [7:0] mx_addr(input integer k);
        reg [7:0] hb;
        begin
            if (k < 16)
                mx_addr = k;
            else if (k >= 36)
                mx_addr = (k == 36) ? 8'h11 : (k == 37) ? 8'h13 : (k == 38) ? 8'h7E : 8'hFF;
            else begin
                hb = ((k - 16) / 4 == 0) ? 8'h10 : ((k - 16) / 4 == 1) ? 8'h20 : ((k - 16) / 4 == 2) ? 8'h40 :
                     ((k - 16) / 4 == 3) ? 8'h80 : 8'hF0;
                mx_addr = hb | (((k - 16) % 4) * 4);
            end
        end
    endfunction

    function [31:0] mx_merge(input [31:0] old, input [31:0] value, input [3:0] strb);
        integer b;
        begin
            mx_merge = old;
            for (b = 0; b < 4; b = b + 1)
                if (strb[b])
                    mx_merge[8*b +: 8] = value[8*b +: 8];
        end
    endfunction

    // One write in ordering o: 0 AW and W together, 1 AW first (W two cycles later), 2 W first
    // (AW two cycles later); BREADY o cycles late.
    task automatic wr_o(input [7:0] addr, input [31:0] value, input [3:0] strb, input integer o,
                        output [1:0] got_resp);
        write(addr, value, strb, o == 2 ? 2 : 0, o == 1 ? 2 : 0, o, got_resp);
    endtask

    // Sets EXPIRED with a one-shot count of LOAD 0 and leaves the count stopped (LOAD 0).
    task automatic mx_arm(input [31:0] ctrl_after);
        begin
            write_ok(8'h04, 32'd0, 4'hF);
            write_ok(8'h00, EN, 4'h1);
            repeat (3) @(negedge aclk);
            write_ok(8'h00, ctrl_after, 4'hF);
        end
    endtask

    // Every COUNT and unmapped write, by ordering, address and strobe, with EXPIRED set, irq high
    // and the count stopped: SLVERR, and no register changes; then a read of the address.
    task automatic mx_unmapped;
        integer o, k, s, drops;
        reg [7:0] a;
        begin
            mx_arm(IE | PERIODIC);
            write_ok(8'h04, 32'h0000_0055, 4'hF);
            check("matrix: irq high before the write sweep", {31'd0, irq}, 32'd1);
            drops = irq_drops;
            hold_irq = 1'b1;
            for (o = 0; o < 3; o = o + 1)
                for (k = 0; k < n_addr; k = k + 1) begin
                    a = mx_addr(k);
                    if (a != 8'h00 && a != 8'h04 && a != 8'h0C) begin
                        for (s = 0; s < 16; s = s + 1) begin
                            wr_o(a, ((s + o + k) % 2) ? 32'hFFFF_FFFF : 32'h0000_0000, s[3:0], o, resp);
                            check("matrix: COUNT or unmapped write SLVERR", {30'd0, resp}, {30'd0, SLVERR});
                        end
                        read(a, o, data, resp);
                        check("matrix: read response", {30'd0, resp}, {30'd0, a == 8'h08 ? OKAY : SLVERR});
                        check("matrix: read data", data, 32'd0);
                        expect_reg("matrix: LOAD unchanged", 8'h04, 32'h0000_0055);
                        expect_reg("matrix: CTRL unchanged", 8'h00, IE | PERIODIC);
                        expect_reg("matrix: COUNT unchanged", 8'h08, 32'd0);
                        expect_reg("matrix: STATUS unchanged", 8'h0C, 32'd1);
                    end
                end
            hold_irq = 1'b0;
            check("matrix: irq held through the write sweep", irq_drops - drops, 0);
        end
    endtask

    // LOAD by ordering and every strobe, count stopped: each write reads back merged, with
    // RREADY 0 to 2 cycles late.
    task automatic mx_load;
        integer o, s;
        reg [31:0] v;
        begin
            m_load = 32'h0000_0055;
            for (o = 0; o < 3; o = o + 1)
                for (s = 0; s < 16; s = s + 1) begin
                    v = 32'h9E37_79B9 * (16 * o + s + 1);
                    wr_o(8'h04, v, s[3:0], o, resp);
                    check("matrix: LOAD write OKAY", {30'd0, resp}, {30'd0, OKAY});
                    m_load = mx_merge(m_load, v, s[3:0]);
                    read(8'h04, o, data, resp);
                    check("matrix: LOAD read back, by strobe", data, m_load);
                    check("matrix: LOAD read OKAY", {30'd0, resp}, {30'd0, OKAY});
                end
        end
    endtask

    // STATUS by ordering, every strobe and data with bit 0 set and clear, IE 1: EXPIRED is
    // cleared exactly when wstrb[0] and data bit 0 are set, and irq follows after that very edge.
    task automatic mx_status;
        integer o, s, v;
        reg [31:0] value;
        reg        clears;
        begin
            for (o = 0; o < 3; o = o + 1)
                for (s = 0; s < 16; s = s + 1)
                    for (v = 0; v < 2; v = v + 1) begin
                        mx_arm(IE);
                        value = v ? 32'hFFFF_FFFF : 32'hFFFF_FFFE;
                        clears = s[0] && value[0];
                        wr_o(8'h0C, value, s[3:0], o, resp);
                        check("matrix: STATUS write OKAY", {30'd0, resp}, {30'd0, OKAY});
                        check("matrix: irq before the STATUS write edge", {31'd0, irq_hist[(write_edge - 1) % 4096]}, 32'd1);
                        check("matrix: irq after the STATUS write edge", {31'd0, irq_hist[write_edge % 4096]}, {31'd0, !clears});
                        read(8'h0C, o, data, resp);
                        check("matrix: STATUS after a write, by strobe", data, {31'd0, !clears});
                        write_ok(8'h0C, 32'd1, 4'h1);
                    end
        end
    endtask

    // irq after the very edge of an IE write, by ordering, with EXPIRED set.
    task automatic mx_irq_edge;
        integer o;
        begin
            mx_arm(32'd0);
            for (o = 0; o < 3; o = o + 1) begin
                wr_o(8'h00, IE, 4'h1, o, resp);
                check("matrix: irq before the IE 1 edge", {31'd0, irq_hist[(write_edge - 1) % 4096]}, 32'd0);
                check("matrix: irq after the IE 1 edge", {31'd0, irq_hist[write_edge % 4096]}, 32'd1);
                wr_o(8'h00, 32'd0, 4'h1, o, resp);
                check("matrix: irq before the IE 0 edge", {31'd0, irq_hist[(write_edge - 1) % 4096]}, 32'd1);
                check("matrix: irq after the IE 0 edge", {31'd0, irq_hist[write_edge % 4096]}, 32'd0);
            end
            write_ok(8'h0C, 32'd1, 4'h1);
        end
    endtask

    // CTRL with every strobe, EN 0 and 1 in the data (and bits 31:3 set or clear), each ordering,
    // with the count stopped and running; IE and MODE start opposite to the data, so any change
    // shows. LOAD is BIG, so no count ends. CTRL is read back, then the count is stopped and
    // COUNT must be BIG less the edges from its last start to the stop edge.
    task automatic mx_ctrl;
        integer p, s, di, o;
        reg [31:0] value, pre;
        begin
            write_ok(8'h00, 32'd0, 4'hF);
            write_ok(8'h0C, 32'd1, 4'h1);
            write_ok(8'h04, BIG, 4'hF);
            read(8'h08, 0, m_count, resp);
            m_run = 1'b0;
            for (p = 0; p < 2; p = p + 1)
                for (s = 0; s < 16; s = s + 1)
                    for (di = 0; di < 4; di = di + 1)
                        for (o = 0; o < 3; o = o + 1) begin
                            value = (di == 0 ? 32'd0 : di == 1 ? EN : di == 2 ? IE | PERIODIC : EN | IE | PERIODIC)
                                    | (s[1] ? 32'hFFFF_FFF8 : 32'd0);
                            pre = {29'd0, !value[2], !value[1], p[0]};
                            write_ok(8'h00, pre, 4'hF);
                            m_ctrl = pre;
                            if (p) begin
                                m_run = 1'b1;
                                m_start = write_edge;
                            end
                            wr_o(8'h00, value, s[3:0], o, resp);
                            check("matrix: CTRL write OKAY", {30'd0, resp}, {30'd0, OKAY});
                            if (s[0]) begin
                                m_ctrl = {29'd0, value[2:0]};
                                if (value[0]) begin
                                    m_run = 1'b1;
                                    m_start = write_edge;
                                end else if (m_run) begin
                                    m_run = 1'b0;
                                    m_count = BIG - (write_edge - m_start);
                                end
                            end
                            read(8'h00, o, data, resp);
                            check("matrix: CTRL after a CTRL write, by strobe", data, m_ctrl);
                            if (m_run) begin
                                write_ok(8'h00, m_ctrl & ~EN, 4'h1);
                                m_run = 1'b0;
                                m_count = BIG - (write_edge - m_start);
                            end
                            expect_reg("matrix: COUNT after the CTRL write", 8'h08, m_count);
                        end
            expect_reg("matrix: no count end in the CTRL matrix", 8'h0C, 32'd0);
        end
    endtask

    // A LOAD write in the middle of a count, in both modes, by ordering and strobe class: the
    // running count is not changed (it ends LOAD 60 edges after its start), and a periodic count
    // reloads the merged LOAD at that end; then a stop, before the next end, leaves COUNT one
    // less than before the stop edge.
    task automatic mx_load_mid;
        integer mo, o, sc, e1;
        reg [3:0]  strb;
        reg [31:0] value, merged;
        begin
            for (mo = 0; mo < 2; mo = mo + 1)
                for (o = 0; o < 3; o = o + 1)
                    for (sc = 0; sc < 4; sc = sc + 1) begin
                        strb = sc == 0 ? 4'hF : sc == 1 ? 4'b0001 : sc == 2 ? 4'b0110 : 4'b0000;
                        value = sc == 0 ? 32'd25 : sc == 1 ? 32'h0000_000D : sc == 2 ? 32'h0012_3400 : 32'hFFFF_FFFF;
                        merged = mx_merge(32'd60, value, strb);
                        write_ok(8'h0C, 32'd1, 4'h1);
                        write_ok(8'h04, 32'd60, 4'hF);
                        write_ok(8'h00, EN | IE | (mo ? PERIODIC : 32'd0), 4'h1);
                        start = write_edge;
                        repeat (4 + o) @(negedge aclk);
                        wr_o(8'h04, value, strb, o, resp);
                        check("matrix: LOAD write mid-count OKAY", {30'd0, resp}, {30'd0, OKAY});
                        wait_irq(70, rose);
                        check("matrix: count end after a LOAD write", {31'd0, rose}, 32'd1);
                        check("matrix: a LOAD write leaves the running count", rise_edge - start, 60);
                        e1 = rise_edge;
                        write_ok(8'h0C, 32'd1, 4'h1);
                        if (!mo) begin
                            expect_reg("matrix: one-shot ended after a LOAD write", 8'h00, IE);
                            expect_reg("matrix: one-shot COUNT 0 after a LOAD write", 8'h08, 32'd0);
                        end else begin
                            if (merged <= 100) begin
                                wait_irq(merged + 4, rose);
                                check("matrix: period after a LOAD write", rise_edge - e1, merged);
                                e1 = rise_edge;
                                write_ok(8'h0C, 32'd1, 4'h1);
                            end
                            write_ok(8'h00, IE | PERIODIC, 4'h1);
                            check("matrix: the stop lands before the next end", {31'd0, write_edge < e1 + merged}, 32'd1);
                            expect_reg("matrix: COUNT after a periodic stop", 8'h08, merged - (write_edge - e1));
                        end
                    end
        end
    endtask

    // A count of LOAD load in mode mo, irq checked after every edge from the start to the
    // sixteenth STATUS clear (the clears take effect every few edges, so they land on every
    // phase of a short count): irq is high after an edge that ends a count (an edge E + k * P
    // in periodic mode, only E + P in one-shot, P = LOAD or 1 for LOAD 0), and after every edge
    // until a clear that lands on an edge that ends none. Then: a long count is timed by its
    // rises; a periodic one is stopped and COUNT checked, or for P up to 2 ended by a reset.
    task automatic mx_count(input [31:0] load, input integer mo);
        integer p, n, e, c, last, e1;
        reg     ends, exp_irq, cleared;
        begin
            p = load == 0 ? 1 : load;
            write_ok(8'h00, IE, 4'h1);
            write_ok(8'h0C, 32'd1, 4'h1);
            write_ok(8'h04, load, 4'hF);
            write_ok(8'h00, EN | IE | (mo ? PERIODIC : 32'd0), 4'h1);
            start = write_edge;
            for (n = 0; n < 16; n = n + 1) begin
                repeat (n % 3) @(negedge aclk);
                write_ok(8'h0C, 32'd1, 4'h1);
                clr_edge[n] = write_edge;
            end
            last = clr_edge[15] + 1;
            exp_irq = 1'b0;
            c = 0;
            for (e = start; e <= last; e = e + 1) begin
                ends = e > start && (mo ? (e - start) % p == 0 : e - start == p);
                cleared = c < 16 && clr_edge[c] == e;
                if (cleared)
                    c = c + 1;
                exp_irq = ends || (exp_irq && !cleared);
                check("matrix: irq after each edge of a count", {31'd0, irq_hist[e % 4096]}, {31'd0, exp_irq});
            end
            if (!mo) begin
                if (p > last - start) begin
                    wait_irq(p + 4, rose);
                    check("matrix: long one-shot length", rise_edge - start, p);
                    write_ok(8'h0C, 32'd1, 4'h1);
                end
                expect_reg("matrix: one-shot EN clears itself", 8'h00, IE);
                expect_reg("matrix: one-shot COUNT at zero", 8'h08, 32'd0);
                if (p < 100)
                    quiet("matrix: no second one-shot end", 2 * p + 6);
            end else if (p <= 2) begin
                reset_dut;
            end else begin
                for (n = 0; n < 4 && irq === 1'b1; n = n + 1)
                    write_ok(8'h0C, 32'd1, 4'h1);
                wait_irq(p + 4, rose);
                check("matrix: periodic end on the period", (rise_edge - start) % p, 0);
                e1 = rise_edge;
                write_ok(8'h0C, 32'd1, 4'h1);
                wait_irq(p + 4, rose);
                check("matrix: periodic period", rise_edge - e1, p);
                e1 = rise_edge;
                write_ok(8'h00, IE | PERIODIC, 4'h1);
                check("matrix: the stop lands before the next end", {31'd0, write_edge < e1 + p}, 32'd1);
                expect_reg("matrix: COUNT after a periodic stop", 8'h08, p - (write_edge - e1));
            end
        end
    endtask

    // Reads and writes overlapping: a write (to LOAD, OKAY, or to 0x05, SLVERR) in each ordering
    // with BREADY 3 cycles late, and a read (of CTRL, or of 0x06) with RREADY 4 cycles late, the
    // second started 0 to 3 cycles after the first, either way round. The monitor judges the
    // response edges; here the responses and the data.
    task automatic mx_overlap;
        integer o, k, v, w_first;
        reg [1:0]  r1, r2;
        reg [31:0] d2, value;
        begin
            write_ok(8'h00, IE, 4'hF);
            for (o = 0; o < 3; o = o + 1)
                for (k = 0; k < 4; k = k + 1)
                    for (v = 0; v < 2; v = v + 1)
                        for (w_first = 0; w_first < 2; w_first = w_first + 1) begin
                            value = 32'h0101_0101 * (16 * o + 4 * k + 2 * v + w_first + 1);
                            fork
                                begin
                                    if (!w_first)
                                        repeat (k) @(negedge aclk);
                                    write(v ? 8'h05 : 8'h04, value, 4'hF, o == 2 ? 2 : 0, o == 1 ? 2 : 0, 3, r1);
                                end
                                begin
                                    if (w_first)
                                        repeat (k) @(negedge aclk);
                                    read(v ? 8'h06 : 8'h00, 4, d2, r2);
                                end
                            join
                            check("matrix: overlapped write response", {30'd0, r1}, {30'd0, v ? SLVERR : OKAY});
                            check("matrix: overlapped read response", {30'd0, r2}, {30'd0, v ? SLVERR : OKAY});
                            check("matrix: overlapped read data", d2, v ? 32'd0 : IE);
                            if (!v)
                                m_load = value;
                            expect_reg("matrix: LOAD after an overlapped write", 8'h04, m_load);
                        end
        end
    endtask

    // Back to back after every response kind: writes and reads alternating OKAY and SLVERR, each
    // offered in the cycle after the previous response is taken, with READY 0, 1 and 2 cycles
    // late. The monitor judges that each is accepted on the next edge.
    task automatic mx_b2b;
        integer bd, n;
        reg [7:0] wa, ra;
        reg       bad;
        begin
            for (bd = 0; bd < 3; bd = bd + 1)
                for (n = 0; n < 9; n = n + 1) begin
                    wa = n == 0 ? 8'h04 : n == 1 ? 8'h05 : n == 2 ? 8'h09 : n == 3 ? 8'h04 : n == 4 ? 8'h04 :
                         n == 5 ? 8'h08 : n == 6 ? (AW > 4 ? 8'h14 : 8'h0E) : n == 7 ? 8'h04 : 8'h02;
                    bad = wa != 8'h04;
                    write(wa, 32'h0000_0100 + n, 4'hF, 0, 0, bd, resp);
                    check("matrix: back-to-back write response", {30'd0, resp}, {30'd0, bad ? SLVERR : OKAY});
                end
            for (bd = 0; bd < 3; bd = bd + 1)
                for (n = 0; n < 9; n = n + 1) begin
                    ra = n == 0 ? 8'h04 : n == 1 ? 8'h06 : n == 2 ? 8'h03 : n == 3 ? 8'h00 : n == 4 ? 8'h0C :
                         n == 5 ? (AW > 4 ? 8'h18 : 8'h0D) : n == 6 ? 8'h07 : n == 7 ? 8'h08 : 8'h01;
                    bad = ra[1:0] != 2'b00 || ra >= 8'h10;
                    read(ra, bd, data, resp);
                    check("matrix: back-to-back read response", {30'd0, resp}, {30'd0, bad ? SLVERR : OKAY});
                end
        end
    endtask

    task automatic matrix;
        begin
            n_addr = AW > 4 ? 40 : 16;
            reset_dut;
            mx_unmapped;
            mx_load;
            mx_status;
            mx_irq_edge;
            mx_ctrl;
            mx_load_mid;
            mx_count(32'd0, 0);
            mx_count(32'd1, 0);
            mx_count(32'd2, 0);
            mx_count(32'd37, 0);
            mx_count(32'h0001_0005, 0);
            mx_count(32'd0, 1);
            mx_count(32'd1, 1);
            mx_count(32'd2, 1);
            mx_count(32'd37, 1);
            mx_count(32'h0001_0005, 1);
            mx_overlap;
            mx_b2b;
            check("matrix: protocol monitor failures", mon_errors, 0);
        end
    endtask
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
