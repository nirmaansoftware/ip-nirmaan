// A mutant that is wrong on purpose (P3-E2): apb_gpio.v with one change. irq
// ignores INTR_ENABLE: any pending status bit raises it, masked or not.
// Everything else is identical.
//
// APB4 GPIO block with N pins: output data and output enable per pin, a
// sampled input, edge and level interrupt detection, an interrupt enable
// mask, and a write-1-to-clear interrupt status. A P3-E2 fixture, the
// reference of the eval case rtl/apb-gpio: see interface_spec.md and
// microarchitecture.md.
//
// Registers (32 bits; bits N and up read as zero and ignore writes, N 1 to 32):
//   0x00 DATA_OUT     RW   the value driven on gpio_out
//   0x04 DIR          RW   1 drives the pin: gpio_oe
//   0x08 DATA_IN      RO   the sampled input; a write gets pslverr
//   0x0C INTR_RISE    RW   detect a rising edge
//   0x10 INTR_FALL    RW   detect a falling edge
//   0x14 INTR_HIGH    RW   detect a high level
//   0x18 INTR_LOW     RW   detect a low level
//   0x1C INTR_ENABLE  RW   1 lets the pin's status bit raise irq
//   0x20 INTR_STATUS  W1C  set by a detected condition; writing 1 clears it,
//                          and a condition detected in the cycle of the clear
//                          leaves it set
//
// * Zero wait states: pready is always high.
// * pstrb selects the bytes a write changes, on INTR_STATUS too.
// * Unmapped addresses (not word aligned, or beyond 0x20) get pslverr: a
//   write changes nothing, a read returns zero.
// * gpio_in is synchronous to pclk; it is sampled once (DATA_IN), and edges
//   compare the sample with the one before it.
// * presetn is synchronous and active low; every register resets to zero.
`timescale 1ns / 1ps
module apb_gpio #(
    parameter ADDR_WIDTH = 8,
    parameter N = 8
) (
    input  wire                  pclk,
    input  wire                  presetn,
    input  wire [ADDR_WIDTH-1:0] paddr,
    input  wire                  psel,
    input  wire                  penable,
    input  wire                  pwrite,
    input  wire [31:0]           pwdata,
    input  wire [3:0]            pstrb,
    output reg  [31:0]           prdata,
    output wire                  pready,
    output wire                  pslverr,
    input  wire [N-1:0]          gpio_in,
    output wire [N-1:0]          gpio_out,
    output wire [N-1:0]          gpio_oe,
    output wire                  irq
);
    localparam [3:0] DATA_OUT = 4'd0, DIR = 4'd1, DATA_IN = 4'd2, INTR_RISE = 4'd3, INTR_FALL = 4'd4,
                     INTR_HIGH = 4'd5, INTR_LOW = 4'd6, INTR_ENABLE = 4'd7, INTR_STATUS = 4'd8;

    // An address is mapped when it is word aligned and inside 0x00 to 0x20.
    function is_mapped(input [ADDR_WIDTH-1:0] addr);
        is_mapped = (addr[1:0] == 2'b00) && ((addr >> 6) == {ADDR_WIDTH{1'b0}}) && (addr[5:2] <= INTR_STATUS);
    endfunction

    // The pins that exist: register bits N and up are held at zero.
    localparam [31:0] PINS = N >= 32 ? 32'hFFFF_FFFF : (32'd1 << N) - 32'd1;

    // The input pins, widened to a register's 32 bits.
    function [31:0] widen(input [N-1:0] pins);
        integer i;
        begin
            widen = 32'd0;
            for (i = 0; i < N; i = i + 1)
                widen[i] = pins[i];
        end
    endfunction

    reg [31:0] data_out, dir, intr_rise, intr_fall, intr_high, intr_low, intr_enable, intr_status;
    reg [31:0] in_q, in_prev;

    wire       access = psel && penable;
    wire       mapped = is_mapped(paddr);
    wire [3:0] index = paddr[5:2];
    wire       wr = access && pwrite && mapped && index != DATA_IN;

    assign pready = 1'b1;
    assign pslverr = access && (!mapped || (pwrite && index == DATA_IN));
    assign gpio_out = data_out[N-1:0];
    assign gpio_oe = dir[N-1:0];

    // A write's new value: the strobed bytes take the written data, on the
    // pins that exist.
    wire [31:0] mask = {{8{pstrb[3]}}, {8{pstrb[2]}}, {8{pstrb[1]}}, {8{pstrb[0]}}} & PINS;
    function [31:0] merge(input [31:0] old, input [31:0] data, input [31:0] bytes);
        merge = (old & ~bytes) | (data & bytes);
    endfunction

    // Detection, from the sample and the one before it.
    wire [31:0] rise = in_q & ~in_prev;
    wire [31:0] fall = ~in_q & in_prev;
    wire [31:0] detected = ((rise & intr_rise) | (fall & intr_fall) | (in_q & intr_high) | (~in_q & intr_low)) & PINS;
    wire [31:0] clear = (wr && index == INTR_STATUS) ? (pwdata & mask) : 32'd0;

    assign irq = |intr_status;

    // Read data: the addressed register in a mapped read access, else zero.
    always @(*) begin
        prdata = 32'd0;
        if (access && !pwrite && mapped) begin
            case (index)
                DATA_OUT: prdata = data_out;
                DIR: prdata = dir;
                DATA_IN: prdata = in_q;
                INTR_RISE: prdata = intr_rise;
                INTR_FALL: prdata = intr_fall;
                INTR_HIGH: prdata = intr_high;
                INTR_LOW: prdata = intr_low;
                INTR_ENABLE: prdata = intr_enable;
                default: prdata = intr_status;
            endcase
        end
    end

    always @(posedge pclk) begin
        if (!presetn) begin
            data_out <= 32'd0;
            dir <= 32'd0;
            intr_rise <= 32'd0;
            intr_fall <= 32'd0;
            intr_high <= 32'd0;
            intr_low <= 32'd0;
            intr_enable <= 32'd0;
            intr_status <= 32'd0;
            in_q <= 32'd0;
            in_prev <= 32'd0;
        end else begin
            in_q <= widen(gpio_in);
            in_prev <= in_q;
            // A condition detected in the cycle of a clear leaves its bit set.
            intr_status <= (intr_status & ~clear) | detected;
            if (wr) begin
                case (index)
                    DATA_OUT: data_out <= merge(data_out, pwdata, mask);
                    DIR: dir <= merge(dir, pwdata, mask);
                    INTR_RISE: intr_rise <= merge(intr_rise, pwdata, mask);
                    INTR_FALL: intr_fall <= merge(intr_fall, pwdata, mask);
                    INTR_HIGH: intr_high <= merge(intr_high, pwdata, mask);
                    INTR_LOW: intr_low <= merge(intr_low, pwdata, mask);
                    INTR_ENABLE: intr_enable <= merge(intr_enable, pwdata, mask);
                    default: ;
                endcase
            end
        end
    end

`ifdef FORMAL
    // Protocol and register properties, proven by apb_gpio.sby (N 8) and
    // apb_gpio_n32.sby (N 32). Assumptions describe a manager that follows
    // the APB rules; assertions check this block against a model of the
    // specification, written independently of the design's decode, strobe
    // merge and detection.
    reg f_past_valid = 1'b0;
    always @(posedge pclk)
        f_past_valid <= 1'b1;

    // The first cycle is in reset.
    always @(*)
        if (!f_past_valid)
            assume (!presetn);

    // Manager: no transfer in reset; penable only with psel.
    always @(*) begin
        if (!presetn)
            assume (!psel);
        assume (!penable || psel);
    end

    // Manager: a setup cycle is followed by its access cycle, with the same
    // address, direction and data; penable rises only after a setup cycle.
    always @(posedge pclk) begin
        if (f_past_valid && $past(presetn) && presetn) begin
            if ($past(psel && !penable))
                assume (psel && penable && paddr == $past(paddr) && pwrite == $past(pwrite)
                        && pwdata == $past(pwdata) && pstrb == $past(pstrb));
            if (penable)
                assume ($past(psel && !penable));
        end
        if (f_past_valid && !$past(presetn))
            assume (!penable);
    end

    // The specification's decode: word aligned, at most 0x20.
    wire       f_mapped = paddr[1:0] == 2'b00 && paddr <= 8'h20;
    wire [3:0] f_index = paddr[5:2];
    wire       f_write = access && pwrite && f_mapped;

    // The specification's strobe merge and pins, one bit at a time.
    reg [31:0] f_bytes;
    integer f_i;
    always @(*)
        for (f_i = 0; f_i < 32; f_i = f_i + 1)
            f_bytes[f_i] = f_i < N && pstrb[f_i / 8];
    wire [31:0] f_new_bits = pwdata & f_bytes;
    wire [31:0] f_keep_bits = ~f_bytes;
    reg [31:0] f_pins_in;
    integer f_j;
    always @(*)
        for (f_j = 0; f_j < 32; f_j = f_j + 1)
            f_pins_in[f_j] = f_j < N ? gpio_in[f_j % N] : 1'b0;

    // The model: every register, the input samples, and the status.
    reg [31:0] f_out, f_dir, f_rise, f_fall, f_high, f_low, f_enable, f_status, f_in, f_in_before;
    wire [31:0] f_event = (f_in & ~f_in_before & f_rise) | (~f_in & f_in_before & f_fall)
                          | (f_in & f_high) | (~f_in & f_low);
    wire        f_clear_write = f_write && f_index == 4'd8;
    always @(posedge pclk) begin
        if (!presetn) begin
            f_out <= 0;
            f_dir <= 0;
            f_rise <= 0;
            f_fall <= 0;
            f_high <= 0;
            f_low <= 0;
            f_enable <= 0;
            f_status <= 0;
            f_in <= 0;
            f_in_before <= 0;
        end else begin
            f_in <= f_pins_in;
            f_in_before <= f_in;
            f_status <= f_event | (f_clear_write ? (f_status & ~f_new_bits) : f_status);
            if (f_write && f_index == 4'd0) f_out <= (f_out & f_keep_bits) | f_new_bits;
            if (f_write && f_index == 4'd1) f_dir <= (f_dir & f_keep_bits) | f_new_bits;
            if (f_write && f_index == 4'd3) f_rise <= (f_rise & f_keep_bits) | f_new_bits;
            if (f_write && f_index == 4'd4) f_fall <= (f_fall & f_keep_bits) | f_new_bits;
            if (f_write && f_index == 4'd5) f_high <= (f_high & f_keep_bits) | f_new_bits;
            if (f_write && f_index == 4'd6) f_low <= (f_low & f_keep_bits) | f_new_bits;
            if (f_write && f_index == 4'd7) f_enable <= (f_enable & f_keep_bits) | f_new_bits;
        end
    end

    reg [31:0] f_rdata;
    always @(*)
        case (f_index)
            4'd0: f_rdata = f_out;
            4'd1: f_rdata = f_dir;
            4'd2: f_rdata = f_in;
            4'd3: f_rdata = f_rise;
            4'd4: f_rdata = f_fall;
            4'd5: f_rdata = f_high;
            4'd6: f_rdata = f_low;
            4'd7: f_rdata = f_enable;
            default: f_rdata = f_status;
        endcase

    always @(posedge pclk) begin
        if (f_past_valid) begin
            // Zero wait states.
            assert (pready);
            // Outside the access phase the response signals are quiet.
            if (!access) begin
                assert (!pslverr);
                assert (prdata == 32'd0);
            end
            // The response follows the address policy; DATA_IN is read only.
            if (access) begin
                assert (pslverr == (!f_mapped || (pwrite && f_index == 4'd2)));
                if (!pwrite)
                    assert (prdata == (f_mapped ? f_rdata : 32'd0));
            end
            // Every register follows the specification, and so do the pins
            // and irq.
            assert (data_out == f_out && dir == f_dir && in_q == f_in && in_prev == f_in_before);
            assert (intr_rise == f_rise && intr_fall == f_fall && intr_high == f_high && intr_low == f_low);
            assert (intr_enable == f_enable && intr_status == f_status);
            assert (gpio_out == f_out[N-1:0] && gpio_oe == f_dir[N-1:0]);
            assert (irq == ((f_status & f_enable) != 0));
        end
    end

    // Covers (M27): each is reached under the manager assumptions above, so
    // the proof is not vacuous and every detection and response path is used.
    always @(posedge pclk) begin
        if (f_past_valid && $past(presetn) && presetn) begin
            // Each kind of detection sets a status bit that was clear.
            cover ((f_in & ~f_in_before & f_rise & ~f_status) != 0);
            cover ((~f_in & f_in_before & f_fall & ~f_status) != 0);
            cover ((f_in & f_high & ~f_status) != 0);
            cover ((~f_in & f_low & ~f_status) != 0);
            // A clear of a pending bit, and a detection in the cycle of its clear.
            cover (f_clear_write && (f_status & f_new_bits & ~f_event) != 0);
            cover (f_clear_write && (f_status & f_new_bits & f_event) != 0);
            // irq raised; a pending bit masked; a partial-strobe write.
            cover (irq);
            cover (f_status != 0 && !irq);
            cover (f_write && f_index == 4'd0 && pstrb != 4'hF && pstrb != 4'h0);
            // Both error kinds, and a nonzero read.
            cover (access && pslverr && !f_mapped);
            cover (access && pslverr && f_mapped);
            cover (access && !pwrite && f_mapped && prdata != 32'd0);
        end
    end
`endif
endmodule
