// APB4 subordinate with four 32-bit registers at 0x0, 0x4, 0x8, 0xC.
// An M26 fixture: see interface_spec.md and microarchitecture.md.
//
// * Zero wait states: pready is always high, so every transfer is one setup
//   cycle and one access cycle.
// * pstrb selects which bytes of the register a write changes.
// * Unmapped addresses (not word aligned, or beyond 0xC) get pslverr, the
//   same policy as the AXI4-Lite block's SLVERR: a write changes nothing, a
//   read returns zero.
// * prdata and pslverr are driven only in the access phase and are zero
//   otherwise.
// * presetn is synchronous and active low; every register resets to zero.
`timescale 1ns / 1ps
module apb_regs #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 32
) (
    input  wire                    pclk,
    input  wire                    presetn,
    input  wire [ADDR_WIDTH-1:0]   paddr,
    input  wire                    psel,
    input  wire                    penable,
    input  wire                    pwrite,
    input  wire [DATA_WIDTH-1:0]   pwdata,
    input  wire [DATA_WIDTH/8-1:0] pstrb,
    output reg  [DATA_WIDTH-1:0]   prdata,
    output wire                    pready,
    output wire                    pslverr
);
    localparam STRB_WIDTH = DATA_WIDTH / 8;

    // An address is mapped when it is word aligned and inside 0x0 to 0xC.
    function is_mapped(input [ADDR_WIDTH-1:0] addr);
        is_mapped = (addr[1:0] == 2'b00) && ((addr >> 4) == {ADDR_WIDTH{1'b0}});
    endfunction

    // The register value after a write: bytes whose strobe is set take the new data.
    function [DATA_WIDTH-1:0] merge(input [DATA_WIDTH-1:0] old, input [DATA_WIDTH-1:0] data,
                                    input [STRB_WIDTH-1:0] strb);
        integer b;
        begin
            merge = old;
            for (b = 0; b < STRB_WIDTH; b = b + 1)
                if (strb[b])
                    merge[8*b +: 8] = data[8*b +: 8];
        end
    endfunction

    // The register file.
    reg [DATA_WIDTH-1:0] reg0, reg1, reg2, reg3;

    // The access phase is the last cycle of every transfer: pready is high.
    wire access = psel && penable;
    wire mapped = is_mapped(paddr);

    assign pready = 1'b1;
    assign pslverr = access && !mapped;

    // Read data: the addressed register in a mapped read access, else zero.
    always @(*) begin
        prdata = {DATA_WIDTH{1'b0}};
        if (access && !pwrite && mapped) begin
            case (paddr[3:2])
                2'd0: prdata = reg0;
                2'd1: prdata = reg1;
                2'd2: prdata = reg2;
                default: prdata = reg3;
            endcase
        end
    end

    // Writes take effect on the rising edge that ends a mapped write access.
    always @(posedge pclk) begin
        if (!presetn) begin
            reg0 <= {DATA_WIDTH{1'b0}};
            reg1 <= {DATA_WIDTH{1'b0}};
            reg2 <= {DATA_WIDTH{1'b0}};
            reg3 <= {DATA_WIDTH{1'b0}};
        end else if (access && pwrite && mapped) begin
            case (paddr[3:2])
                2'd0: reg0 <= merge(reg0, pwdata, pstrb);
                2'd1: reg1 <= merge(reg1, pwdata, pstrb);
                2'd2: reg2 <= merge(reg2, pwdata, pstrb);
                default: reg3 <= merge(reg3, pwdata, pstrb);
            endcase
        end
    end

`ifdef FORMAL
    // Protocol and register properties, proven by apb_regs.sby. Assumptions
    // describe a manager that follows the APB rules; assertions check this
    // subordinate.
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
    // address, direction and data; penable rises only after a setup cycle, and
    // falls after the access cycle (pready is always high).
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

    // The specification's decode and byte merge, written independently of
    // the design's is_mapped and merge, so a bug there cannot hide.
    wire f_mapped = paddr[1:0] == 2'b00 && paddr < 16;
    reg [DATA_WIDTH-1:0] f_reg;
    always @(*)
        case (paddr[3:2])
            2'd0: f_reg = reg0;
            2'd1: f_reg = reg1;
            2'd2: f_reg = reg2;
            default: f_reg = reg3;
        endcase

    // One register after a clock edge: bytes change only in a mapped write
    // access to it, and only those whose strobe was set, to the written data.
    task f_check_reg(input [DATA_WIDTH-1:0] now, input [DATA_WIDTH-1:0] before, input [1:0] index);
        integer b;
        for (b = 0; b < STRB_WIDTH; b = b + 1)
            if ($past(access && pwrite && f_mapped) && $past(paddr[3:2]) == index && $past(pstrb[b]))
                assert (now[8*b +: 8] == $past(pwdata[8*b +: 8]));
            else
                assert (now[8*b +: 8] == before[8*b +: 8]);
    endtask

    always @(posedge pclk) begin
        if (f_past_valid) begin
            // Zero wait states: every access cycle completes the transfer.
            assert (pready);
            // Outside the access phase the response signals are quiet.
            if (!access) begin
                assert (!pslverr);
                assert (prdata == {DATA_WIDTH{1'b0}});
            end
            // The response follows the address policy.
            if (access) begin
                assert (pslverr == !f_mapped);
                if (!pwrite)
                    assert (prdata == (f_mapped ? f_reg : {DATA_WIDTH{1'b0}}));
            end
            // After reset every register is zero; after that, registers change
            // only as written.
            if (!$past(presetn)) begin
                assert (reg0 == 0 && reg1 == 0 && reg2 == 0 && reg3 == 0);
            end else begin
                f_check_reg(reg0, $past(reg0), 2'd0);
                f_check_reg(reg1, $past(reg1), 2'd1);
                f_check_reg(reg2, $past(reg2), 2'd2);
                f_check_reg(reg3, $past(reg3), 2'd3);
            end
        end
    end
`endif
endmodule
