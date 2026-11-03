// Self-checking testbench for skid_buffer.v (P3-E3), the eval case's reference.
//
// Two lanes run the same checks, one with 8-bit beats and one with 1-bit
// beats. Each lane keeps its own model of the slice: a list of the beats it
// accepted and how many have left. On every cycle it checks that m_valid is
// high exactly while a beat is held, that s_ready is high exactly while fewer
// than two are held, that m_data is the oldest held beat, and that a beat
// offered and not taken stays unchanged. Before each edge it also flips
// m_ready and s_valid for 1 ns and checks that s_ready does not move: ready
// is registered.
//
// The directed part covers reset values; the one-cycle latency; a stream of
// back-to-back beats at full throughput; a stall with one beat held (the
// slice must still accept a second) and then two (it must not accept a
// third); ready rising after the stall, with the beats out in order, each
// once, and a new beat following the skid beat straight away; upstream
// dropping s_valid while the slice is full; and reset with beats held. Then
// several hundred cycles of seeded random traffic, and a final drain in which
// every accepted beat must come out.
//
// Inputs are driven just after the falling edge and outputs are sampled 1 ns
// later, so every check sees the values the next rising edge will use.
`timescale 1ns / 1ps
module skid_buffer_tb_lane #(
    parameter WIDTH = 8,
    parameter SEED = 1
) ();
    localparam TIMEOUT = 40;
    localparam MAXBEATS = 2048;

    reg              clk = 1'b0;
    reg              rst_n = 1'b0;
    reg              s_valid = 1'b0;
    wire             s_ready;
    reg  [WIDTH-1:0] s_data = {WIDTH{1'b0}};
    wire             m_valid;
    reg              m_ready = 1'b0;
    wire [WIDTH-1:0] m_data;

    integer errors = 0;
    integer checks = 0;
    reg     done = 1'b0;

    // The model: every beat accepted since reset, and how many have left.
    reg [WIDTH-1:0] sent [0:MAXBEATS-1];
    integer tx = 0;
    integer rx = 0;
    // The last cycle's output, for the hold rule.
    reg             held = 1'b0;
    reg [WIDTH-1:0] held_data = {WIDTH{1'b0}};
    // The number of beats each directed step saw move.
    integer took_in, took_out;
    integer seed;
    integer n;
    reg     ready_before;

    skid_buffer #(.WIDTH(WIDTH)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_valid(s_valid), .s_ready(s_ready), .s_data(s_data),
        .m_valid(m_valid), .m_ready(m_ready), .m_data(m_data)
    );

    always #5 clk = ~clk;

    task automatic check(input [8*48-1:0] what, input [31:0] got, input [31:0] expected);
        begin
            checks = checks + 1;
            if (got !== expected) begin
                $error("lane WIDTH=%0d: %0s: got 0x%08h, expected 0x%08h", WIDTH, what, got, expected);
                errors = errors + 1;
            end
        end
    endtask

    function [31:0] wide(input [WIDTH-1:0] v);
        wide = {{(32 - WIDTH){1'b0}}, v};
    endfunction

    // A value for beat number k: it changes from beat to beat at every WIDTH.
    function [WIDTH-1:0] pattern(input integer k);
        reg [31:0] mixed;
        begin
            mixed = k * 32'h9E37_79B9 + 32'h0000_0005;
            pattern = mixed[WIDTH-1:0];
        end
    endfunction

    // One cycle, started at a falling edge: drive the inputs, check the
    // outputs against the model, then let the rising edge move the beats.
    task automatic cycle(input valid, input [WIDTH-1:0] data, input ready);
        integer held_now;
        begin
            s_data = data;
            // Registered ready: flip both inputs that could reach it, then
            // set them; s_ready must not move.
            s_valid = !valid;
            m_ready = !ready;
            #1;
            ready_before = s_ready;
            s_valid = valid;
            m_ready = ready;
            #1;
            check("s_ready moved with m_ready or s_valid", {31'd0, s_ready}, {31'd0, ready_before});
            held_now = tx - rx;
            check("m_valid while beats are held", {31'd0, m_valid}, {31'd0, held_now != 0});
            check("s_ready while room is left", {31'd0, s_ready}, {31'd0, held_now < 2});
            if (held_now > 0 && rx < MAXBEATS)
                check("m_data is the oldest beat", wide(m_data), wide(sent[rx]));
            if (held) begin
                check("a stalled beat stays valid", {31'd0, m_valid}, 32'd1);
                check("a stalled beat keeps its data", wide(m_data), wide(held_data));
            end
            // The edge: what the ports agree on moves.
            if (m_valid && m_ready) begin
                rx = rx + 1;
                took_out = took_out + 1;
            end
            if (s_valid && s_ready) begin
                if (tx < MAXBEATS)
                    sent[tx] = s_data;
                tx = tx + 1;
                took_in = took_in + 1;
            end
            held = m_valid && !m_ready;
            held_data = m_data;
            @(negedge clk);
        end
    endtask

    // Reset for two cycles; the model empties with the slice.
    task automatic reset_dut;
        begin
            rst_n = 1'b0;
            s_valid = 1'b0;
            m_ready = 1'b0;
            @(negedge clk);
            @(negedge clk);
            rst_n = 1'b1;
            tx = 0;
            rx = 0;
            held = 1'b0;
            #1;
            check("m_valid after reset", {31'd0, m_valid}, 32'd0);
            check("s_ready after reset", {31'd0, s_ready}, 32'd1);
            @(negedge clk);
        end
    endtask

    // Offer the next beat of the pattern; the model records it if taken.
    task automatic offer(input ready);
        begin
            cycle(1'b1, pattern(tx), ready);
        end
    endtask

    // Take beats until the slice is empty.
    task automatic drain;
        integer waits, k;
        begin
            waits = 0;
            while (tx != rx && waits < TIMEOUT) begin
                cycle(1'b0, {WIDTH{1'b0}}, 1'b1);
                waits = waits + 1;
            end
            check("drained", tx - rx, 0);
            // Nothing more comes out of an empty slice.
            for (k = 0; k < 3; k = k + 1)
                cycle(1'b0, {WIDTH{1'b0}}, 1'b1);
        end
    endtask

    initial begin
        seed = SEED;
        took_in = 0;
        took_out = 0;
        @(negedge clk);
        reset_dut;

        // Idle: nothing offered, nothing comes out.
        for (n = 0; n < 3; n = n + 1)
            cycle(1'b0, {WIDTH{1'b0}}, 1'b1);
        check("idle moves nothing", took_in + took_out, 0);

        // One beat: accepted on the edge, out on the next cycle.
        offer(1'b1);
        check("one beat in", took_in, 1);
        check("one beat, a cycle later", {31'd0, m_valid}, 32'd1);
        drain;

        // Full throughput: 32 beats back to back with m_ready high, so after
        // the first edge one beat enters and one leaves on every edge.
        took_in = 0;
        took_out = 0;
        for (n = 0; n < 32; n = n + 1)
            offer(1'b1);
        check("full throughput: every beat taken", took_in, 32);
        check("full throughput: one out per edge", took_out, 31);
        drain;

        // A stall: one beat held and m_ready low; the slice still takes a
        // second beat (the skid), then refuses a third.
        took_in = 0;
        offer(1'b0);
        check("stall: first beat in", took_in, 1);
        offer(1'b0);
        check("stall: second beat into the skid", took_in, 2);
        for (n = 0; n < 4; n = n + 1)
            offer(1'b0);
        check("stall: no third beat", took_in, 2);
        // Upstream drops and raises s_valid while the slice is full.
        cycle(1'b0, {WIDTH{1'b1}}, 1'b0);
        cycle(1'b1, {WIDTH{1'b1}}, 1'b0);
        cycle(1'b0, {WIDTH{1'b0}}, 1'b0);
        check("full: s_valid toggling adds nothing", took_in, 2);

        // Ready rises: the held beat leaves, the skid beat follows on the next
        // edge, and a new beat is taken in the cycle the skid beat leaves.
        took_out = 0;
        offer(1'b1);
        check("ready rises: the held beat leaves", took_out, 1);
        check("ready rises: no beat taken while full", took_in, 2);
        offer(1'b1);
        check("the skid beat leaves", took_out, 2);
        check("a new beat follows the skid beat", took_in, 3);
        for (n = 0; n < 6; n = n + 1)
            offer(1'b1);
        check("full throughput again", took_in, 9);
        drain;

        // Stalls of every length, two beats deep.
        for (n = 1; n < 5; n = n + 1) begin
            offer(1'b0);
            offer(1'b0);
            repeat (n) offer(1'b0);
            repeat (n) offer(1'b1);
            drain;
        end

        // Reset with two beats held: both are dropped.
        offer(1'b0);
        offer(1'b0);
        reset_dut;
        for (n = 0; n < 3; n = n + 1)
            cycle(1'b0, {WIDTH{1'b0}}, 1'b1);
        took_in = 0;
        offer(1'b1);
        check("after reset: a beat passes", took_in, 1);
        drain;

        // Seeded random traffic: s_valid about three cycles in four, m_ready
        // about one in two, then a drain.
        for (n = 0; n < 600; n = n + 1)
            cycle(($random(seed) & 3) != 0, pattern(tx), ($random(seed) & 1) != 0);
        drain;
        // Random traffic with a slow consumer, then a fast one.
        for (n = 0; n < 200; n = n + 1)
            cycle(1'b1, pattern(tx), ($random(seed) & 3) == 0);
        for (n = 0; n < 200; n = n + 1)
            cycle(($random(seed) & 3) == 0, pattern(tx), ($random(seed) & 3) != 0);
        drain;
        check("beats fit the model", {31'd0, tx < MAXBEATS}, 32'd1);

        done = 1'b1;
    end
endmodule

module skid_buffer_tb;
    reg [8*64-1:0] nonce;  // the run's nonce (+nirmaan_nonce=), for the verdict line
    integer checks, errors;

    skid_buffer_tb_lane #(.WIDTH(8), .SEED(11)) lane8 ();
    skid_buffer_tb_lane #(.WIDTH(1), .SEED(23)) lane1 ();

    initial begin
        wait (lane8.done && lane1.done);
        checks = lane8.checks + lane1.checks;
        errors = lane8.errors + lane1.errors;
        if (checks < 8000) begin
            $error("too few checks: %0d", checks);
            errors = errors + 1;
        end
        if (errors == 0)
            $display("skid_buffer_tb: PASS (%0d checks)", checks);
        // The verdict the gate reads (docs/GATE_INTEGRITY.md): the run's nonce, then the counts.
        if (!$value$plusargs("nirmaan_nonce=%s", nonce))
            nonce = "none";
        $display("NIRMAAN-SIM %0s %0d passed, %0d failed", nonce, (checks > errors ? checks - errors : 0), errors);
        $finish;
    end
endmodule
