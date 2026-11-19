"""Scratch-style mutants of the two whole-flow reference RTLs, for the adversarial sweep of the flow requirements
documents (G3, ip#339). Each mutant violates exactly one tag the case's testbench copy judges; the name's prefix
names the tag (``TIMER_TAGS``, ``REGS_TAGS``). ``timer_mutants`` and ``regs_mutants`` build every mutant from the
reference RTL's text by exact replacements, so the sweep records (``evals/flow/<block>/mutant_sweep.json``) can be
checked against them by sha256 without committing the mutant files. ``tests/test_whole_flow_cases.py`` holds the
records to these builders and runs one mutant per tag on the testbench copy.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

TIMER_TAGS = {"MODULE": "TMR-MODULE", "ADDRW": "TMR-ADDR-WIDTH", "PORTS": "TMR-PORTS", "MAP": "TMR-MAP",
              "CTRLSTRB": "TMR-CTRL-STRB", "LOAD": "TMR-LOAD", "STATUS": "TMR-STATUS-CLEAR", "START": "TMR-START",
              "LOAD0": "TMR-LOAD-ZERO", "COUNT": "TMR-COUNT", "LENGTH": "TMR-COUNT-LENGTH", "ONESHOT": "TMR-ONESHOT",
              "PERIODIC": "TMR-PERIODIC", "STOP": "TMR-STOP", "STOPEDGE": "TMR-STOP-EDGE",
              "ENDCLEAR": "TMR-END-BEATS-CLEAR", "IRQ": "TMR-IRQ", "ORDER": "TMR-ORDER", "RESP": "TMR-RESPONSE",
              "RESPEDGE": "TMR-RESPONSE-EDGE", "DECODE": "TMR-DECODE", "SLVERR": "TMR-SLVERR", "RESET": "TMR-RESET"}
REGS_TAGS = {"MAP": "AXIL-MAP", "PORTS": "AXIL-PORTS", "PARAMS": "AXIL-PARAMS", "ORDER": "AXIL-ORDER",
             "WSTRB": "AXIL-WSTRB", "SLVERR": "AXIL-SLVERR", "LATENCY": "AXIL-LATENCY", "B2B": "AXIL-B2B",
             "RESET": "AXIL-RESET"}


def tag_of(name: str, tags: dict[str, str]) -> str:
    """The tag a mutant violates, from the prefix of its name."""
    return tags[name.split("_")[0]]


def _builder(s: str):
    out: dict[str, str] = {}

    def sub(name: str, *pairs: tuple[str, str]) -> None:
        t = s
        for a, b in pairs:
            if a not in t:
                raise ValueError(f"{name}: the reference RTL has no {a!r}")
            t = t.replace(a, b, 1)
        out[name] = t

    return out, sub


def timer_mutants(s: str) -> dict[str, str]:
    """Every timer mutant's text, by name, from the text of tests/fixtures/rtl/axil_timer/axil_timer.v."""
    out, sub = _builder(s)

    # TMR-MODULE: a 32-bit timer; these count with fewer bits.
    sub('MODULE_cnt24', ("    reg [31:0] load, count;", "    reg [31:0] load; reg [23:0] count;"),
        ("COUNT: s_axil_rdata <= count;", "COUNT: s_axil_rdata <= {8'd0, count};"))
    sub('MODULE_cnt16', ("    reg [31:0] load, count;", "    reg [31:0] load; reg [15:0] count;"),
        ("COUNT: s_axil_rdata <= count;", "COUNT: s_axil_rdata <= {16'd0, count};"))
    # TMR-MODULE: no periodic mode at all (MODE stored but ignored).
    sub('MODULE_no_periodic', ("                    if (mode) begin\n                        count <= load;", "                    if (1'b0) begin\n                        count <= load;"))
    # TMR-ADDR-WIDTH: at AW 8, offsets with bit 5, bit 6 or bit 7 alias the registers (reads and writes).
    for b in (4, 5, 6, 7):
        sub(f'ADDRW_ignore_bit{b}', ("is_mapped = (addr[1:0] == 2'b00) && ((addr >> 4) == {ADDR_WIDTH{1'b0}});",
            f"is_mapped = (addr[1:0] == 2'b00) && (((addr & ~(8'h{1 << b:02X})) >> 4) == {{ADDR_WIDTH{{1'b0}}}});"))
    # TMR-ADDR-WIDTH: write decode only ignores bit 6 (reads right).
    sub('ADDRW_wr_ignore_bit6', ("wire                  wr_ok = is_mapped(wr_addr) &&", "wire                  wr_ok = is_mapped(wr_addr & ~8'h40) &&"))
    # TMR-PORTS: irq two bits wide; rdata 33 bits; awaddr one bit short.
    sub('PORTS_irq_2bit', ("    output wire                  irq\n", "    output wire [1:0]            irq\n"), ("    assign irq = expired && ie;", "    assign irq = {1'b0, expired && ie};"))
    sub('PORTS_rdata_33', ("    output reg  [31:0]           s_axil_rdata,", "    output reg  [32:0]           s_axil_rdata,"))
    sub('PORTS_bresp_3bit', ("    output reg  [1:0]            s_axil_bresp,", "    output reg  [2:0]            s_axil_bresp,"))
    sub('PORTS_slverr_11', ("localparam [1:0] RESP_SLVERR = 2'b10;", "localparam [1:0] RESP_SLVERR = 2'b11;"))
    # TMR-MAP: CTRL keeps bit 3 / bit 31; STATUS keeps a written bit 31; LOAD bit 31 stuck at 0; LOAD resets to 1.
    sub('MAP_ctrl_bit3', ("    reg        en, ie, mode, expired;", "    reg        en, ie, mode, expired; reg b3;"),
        ("                    ie <= wr_data[1];", "                    ie <= wr_data[1]; b3 <= wr_data[3];"),
        ("            en <= 1'b0;\n            ie <= 1'b0;", "            en <= 1'b0; b3 <= 1'b0;\n            ie <= 1'b0;"),
        ("CTRL: s_axil_rdata <= {29'b0, mode, ie, en};", "CTRL: s_axil_rdata <= {28'b0, b3, mode, ie, en};"))
    sub('MAP_ctrl_bit31', ("    reg        en, ie, mode, expired;", "    reg        en, ie, mode, expired; reg b31;"),
        ("                    ie <= wr_data[1];", "                    ie <= wr_data[1]; b31 <= wr_data[31];"),
        ("            en <= 1'b0;\n            ie <= 1'b0;", "            en <= 1'b0; b31 <= 1'b0;\n            ie <= 1'b0;"),
        ("CTRL: s_axil_rdata <= {29'b0, mode, ie, en};", "CTRL: s_axil_rdata <= {b31, 28'b0, mode, ie, en};"))
    sub('MAP_status_bit31', ("    reg        en, ie, mode, expired;", "    reg        en, ie, mode, expired; reg s31;"),
        ("                if (wr_ok && wr_addr[3:2] == LOAD)", "                if (wr_ok && wr_addr[3:2] == STATUS && wr_strb[3]) s31 <= wr_data[31];\n                if (wr_ok && wr_addr[3:2] == LOAD)"),
        ("            en <= 1'b0;\n            ie <= 1'b0;", "            en <= 1'b0; s31 <= 1'b0;\n            ie <= 1'b0;"),
        ("default: s_axil_rdata <= {31'b0, expired};", "default: s_axil_rdata <= {s31, 30'b0, expired};"))
    sub('MAP_load_bit31', ("                    load <= merge(load, wr_data, wr_strb);", "                    load <= merge(load, wr_data, wr_strb) & 32'h7FFF_FFFF;"))
    sub('MAP_load_reset1', ("            load <= 32'd0;\n", "            load <= 32'd1;\n"))
    # TMR-CTRL-STRB: CTRL written on any strobe; CTRL write without wstrb[0] answers SLVERR.
    sub('CTRLSTRB_any', ("wire                  ctrl_write = do_write && wr_ok && wr_addr[3:2] == CTRL && wr_strb[0];", "wire                  ctrl_write = do_write && wr_ok && wr_addr[3:2] == CTRL && |wr_strb;"))
    sub('CTRLSTRB_slverr', ("                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;", "                s_axil_bresp <= wr_ok && !(wr_addr[3:2] == CTRL && !wr_strb[0]) ? RESP_OKAY : RESP_SLVERR;"))
    # TMR-LOAD: byte 1 written by strobe 2; byte 3 by strobe 3 only when strobe 0 too.
    sub('LOAD_strb1_swap', ("                if (strb[b])", "                if (strb[b == 1 ? 2 : b])"))
    sub('LOAD_strb3_needs0', ("                if (strb[b])", "                if (strb[b] && (b != 3 || strb[0]))"))
    # TMR-STATUS-CLEAR: needs all strobes; clears on any write with strobe 0.
    sub('STATUS_needs_all', ("wr_addr[3:2] == STATUS && wr_strb[0] && wr_data[0];", "wr_addr[3:2] == STATUS && (&wr_strb) && wr_data[0];"))
    sub('STATUS_any', ("wr_addr[3:2] == STATUS && wr_strb[0] && wr_data[0];", "wr_addr[3:2] == STATUS && wr_strb[0];"))
    # TMR-START: EN written 1 while running is ignored; the start loads LOAD - 1.
    sub('START_restart_ignored', ("                        en <= 1'b1;\n                        count <= load;", "                        en <= 1'b1;\n                        if (!en) count <= load;"))
    sub('START_load_minus1', ("                        en <= 1'b1;\n                        count <= load;", "                        en <= 1'b1;\n                        count <= load - 32'd1;"))
    # TMR-LOAD-ZERO: a one-shot LOAD of 0 counts as 2.
    sub('LOAD0_counts2', ("                        count <= load;\n                    end else begin\n                        en <= 1'b0;", "                        count <= (load == 0) ? 32'd2 : load;\n                    end else begin\n                        en <= 1'b0;"))
    # TMR-COUNT: decrements by 2 while COUNT is above 255; or skips a step above 65535.
    sub('COUNT_dec2_high', ("                    count <= count - 32'd1;", "                    count <= count - (count > 32'd255 ? 32'd2 : 32'd1);"))
    sub('COUNT_dec2_veryhigh', ("                    count <= count - 32'd1;", "                    count <= count - (count > 32'd65535 ? 32'd2 : 32'd1);"))
    # TMR-COUNT-LENGTH: a count of more than 100 cycles ends one edge late.
    sub('LENGTH_plus1_big', ("                        count <= load;\n                    end else begin\n                        en <= 1'b0;", "                        count <= (load > 100) ? load + 32'd1 : load;\n                    end else begin\n                        en <= 1'b0;"))
    # TMR-ONESHOT: one-shot leaves COUNT at 1, not 0, after the end.
    sub('ONESHOT_count1', ("                        count <= 32'd0;\n                        en <= 1'b0;", "                        count <= 32'd1;\n                        en <= 1'b0;"))
    # TMR-PERIODIC: a periodic count stops after its 6th period.
    sub('PERIODIC_stops_6', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [3:0] np;"),
        ("            load <= 32'd0;\n", "            load <= 32'd0; np <= 0;\n"),
        ("                    if (mode) begin\n                        count <= load;", "                    if (mode && np != 5) begin np <= np + 1;\n                        count <= load;"))
    # TMR-STOP: EN 0 stops, but the count runs on after 10 cycles stopped.
    # TMR-END-BEATS-CLEAR: in one-shot mode the clear wins.
    sub('ENDCLEAR_oneshot', ("            if (count_end)\n                expired <= 1'b1;", "            if (count_end && !(ack_write && !mode))\n                expired <= 1'b1;"))
    # TMR-IRQ: irq ages out after 20 / 300 / 3000 cycles high; any LOAD write drops EXPIRED.
    for n, w in ((20, 5), (300, 9), (3000, 12)):
        sub(f'IRQ_ageout{n}', ("    assign irq = expired && ie;",
            f"    reg [{w}:0] ag; always @(posedge aclk) ag <= !aresetn ? 0 : (expired && ie) ? (ag == {n} ? ag : ag + 1) : 0;\n    assign irq = expired && ie && ag < {n};"))
    sub('IRQ_load_write_clears', ("            if (ack_write)\n                expired <= 1'b0;", "            if (ack_write || (do_write && wr_ok && wr_addr[3:2] == LOAD))\n                expired <= 1'b0;"))
    # TMR-ORDER: write data, or the write address, taken from the bus at completion, not held.
    sub('ORDER_wdata_not_held', ("wire [31:0]           wr_data = w_held ? w_data_q : s_axil_wdata;", "wire [31:0]           wr_data = s_axil_wdata;"))
    sub('ORDER_wstrb_not_held', ("wire [3:0]            wr_strb = w_held ? w_strb_q : s_axil_wstrb;", "wire [3:0]            wr_strb = s_axil_wstrb;"))
    sub('ORDER_awaddr_not_held', ("wire [ADDR_WIDTH-1:0] wr_addr = aw_held ? aw_addr_q : s_axil_awaddr;", "wire [ADDR_WIDTH-1:0] wr_addr = s_axil_awaddr;"))
    # TMR-ORDER: a held write address is dropped after 8 cycles without its data.
    sub('ORDER_aw_timeout', ("    reg                  aw_held;", "    reg                  aw_held; reg [3:0] awt;"),
        ("            aw_held <= 1'b0;\n            w_held <= 1'b0;\n            s_axil_bvalid <= 1'b0;", "            aw_held <= 1'b0; awt <= 0;\n            w_held <= 1'b0;\n            s_axil_bvalid <= 1'b0;"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n\n            // The count", "            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            awt <= aw_held ? awt + 1 : 0;\n\n            // The count"),
        ("            end else begin\n                if (aw_hs) begin", "            end else begin\n                if (awt == 8) aw_held <= 1'b0;\n                if (aw_hs) begin"))
    # TMR-RESPONSE: BVALID / RVALID high one extra cycle after the handshake; BVALID / RVALID drop after 6 cycles waiting.
    sub('RESP_bvalid_extra', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg bx;"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;", "            bx <= 1'b0;\n            if (s_axil_bvalid && s_axil_bready && !bx) bx <= 1'b1;\n            else if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;"),
        ("            s_axil_bvalid <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;", "            s_axil_bvalid <= 1'b0; bx <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;"))
    sub('RESP_rvalid_extra', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg rx;"),
        ("            if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;", "            rx <= 1'b0;\n            if (s_axil_rvalid && s_axil_rready && !rx) rx <= 1'b1;\n            else if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;"),
        ("            s_axil_rvalid <= 1'b0;\n            s_axil_rresp <= RESP_OKAY;", "            s_axil_rvalid <= 1'b0; rx <= 1'b0;\n            s_axil_rresp <= RESP_OKAY;"))
    sub('RESP_bvalid_timeout', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [3:0] bw;"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;", "            bw <= s_axil_bvalid ? bw + 1 : 0;\n            if ((s_axil_bvalid && s_axil_bready) || bw == 6)\n                s_axil_bvalid <= 1'b0;"),
        ("            s_axil_bvalid <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;", "            s_axil_bvalid <= 1'b0; bw <= 0;\n            s_axil_bresp <= RESP_OKAY;"))
    sub('RESP_rvalid_timeout', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [3:0] rw;"),
        ("            if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;", "            rw <= s_axil_rvalid ? rw + 1 : 0;\n            if ((s_axil_rvalid && s_axil_rready) || rw == 6)\n                s_axil_rvalid <= 1'b0;"),
        ("            s_axil_rvalid <= 1'b0;\n            s_axil_rresp <= RESP_OKAY;", "            s_axil_rvalid <= 1'b0; rw <= 0;\n            s_axil_rresp <= RESP_OKAY;"))
    sub('RESP_bresp_flip', ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;", "            if (s_axil_bvalid && !s_axil_bready && s_axil_bresp == RESP_SLVERR) s_axil_bresp <= RESP_OKAY;\n            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;"))
    # TMR-RESPONSE: RVALID rises before the address is accepted when ARVALID is high one cycle (early response).
    # TMR-RESPONSE-EDGE: BVALID, RVALID one edge late (write effect on time); the whole write one edge late.
    sub('RESPEDGE_b_late', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg bp; reg [1:0] bpr;"),
        ("                s_axil_bvalid <= 1'b1;\n                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;", "                bp <= 1'b1; bpr <= wr_ok ? RESP_OKAY : RESP_SLVERR;"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;", "            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            if (bp) begin bp <= 1'b0; s_axil_bvalid <= 1'b1; s_axil_bresp <= bpr; end"),
        ("            s_axil_bvalid <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;", "            s_axil_bvalid <= 1'b0; bp <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;"),
        ("    assign s_axil_awready = !aw_held && !s_axil_bvalid;", "    assign s_axil_awready = !aw_held && !s_axil_bvalid && !bp;"),
        ("    assign s_axil_wready = !w_held && !s_axil_bvalid;", "    assign s_axil_wready = !w_held && !s_axil_bvalid && !bp;"))
    # TMR-DECODE: write decode ignores addr[1]; read decode ignores addr[0]; offsets 0x3 read as STATUS.
    sub('DECODE_wr_ignore_a1', ("wire                  wr_ok = is_mapped(wr_addr) &&", "wire                  wr_ok = (wr_addr[0] == 1'b0 && (wr_addr >> 4) == 0) &&"))
    sub('DECODE_wr_ignore_a0', ("wire                  wr_ok = is_mapped(wr_addr) &&", "wire                  wr_ok = (wr_addr[1] == 1'b0 && (wr_addr >> 4) == 0) &&"))
    sub('DECODE_rd_ignore_a0', ("                if (is_mapped(s_axil_araddr)) begin", "                if (s_axil_araddr[1] == 1'b0 && (s_axil_araddr >> 4) == 0) begin"))
    sub('DECODE_rd_ignore_a1', ("                if (is_mapped(s_axil_araddr)) begin", "                if (s_axil_araddr[0] == 1'b0 && (s_axil_araddr >> 4) == 0) begin"))
    # TMR-SLVERR: an unmapped write answers SLVERR but still writes LOAD (offset 0x6); a COUNT write answers OKAY;
    # an unmapped write at 0xE clears EXPIRED; an unmapped read returns the register's data.
    sub('SLVERR_unm_writes_load', ("                if (wr_ok && wr_addr[3:2] == LOAD)", "                if ((wr_ok || wr_addr[1:0] == 2'b10) && wr_addr[3:2] == LOAD && (wr_addr >> 4) == 0)"))
    sub('SLVERR_unm_clears', ("wire                  ack_write = do_write && wr_ok &&", "wire                  ack_write = do_write && (wr_ok || (wr_addr[1:0] == 2'b10 && (wr_addr >> 4) == 0)) &&"))
    sub('SLVERR_count_okay', ("                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;", "                s_axil_bresp <= (wr_ok || (is_mapped(wr_addr) && wr_addr[3:2] == COUNT)) ? RESP_OKAY : RESP_SLVERR;"))
    sub('SLVERR_unm_rdata', ("                    s_axil_rresp <= RESP_SLVERR;\n                    s_axil_rdata <= 32'd0;", "                    s_axil_rresp <= RESP_SLVERR;\n                    s_axil_rdata <= (s_axil_araddr[1:0] == 2'b11) ? load : 32'd0;"))
    sub('SLVERR_count_write_effect', ("                if (wr_ok && wr_addr[3:2] == LOAD)", "                if (is_mapped(wr_addr) && wr_addr[3:2] == COUNT) count <= wr_data;\n                if (wr_ok && wr_addr[3:2] == LOAD)"))
    # TMR-RESET: reset keeps MODE; keeps LOAD; keeps EXPIRED; irq high for the cycle after reset.
    sub('RESET_keeps_mode', ("            mode <= 1'b0;\n            expired <= 1'b0;", "            expired <= 1'b0;"))
    sub('RESET_keeps_load', ("            load <= 32'd0;\n", ""))
    sub('RESET_keeps_expired', ("            mode <= 1'b0;\n            expired <= 1'b0;", "            mode <= 1'b0;"))
    sub('RESET_keeps_count_running', ("            en <= 1'b0;\n            ie <= 1'b0;", "            ie <= 1'b0;"))

    sub('IRQ_ie_no_raise', ("    assign irq = expired && ie;", "    reg ie_at_end; always @(posedge aclk) if (!aresetn) ie_at_end <= 0; else if (en && count <= 32'd1) ie_at_end <= ie;\n    assign irq = expired && ie && ie_at_end;"))
    sub('STOP_resumes', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [4:0] st;"),
        ("            load <= 32'd0;\n", "            load <= 32'd0; st <= 0;\n"),
        ("            if (en) begin\n", "            st <= en ? 5'd0 : (st == 5'd31 ? st : st + 5'd1);\n            if (!en && st == 5'd10 && count > 32'd1) en <= 1'b1;\n            if (en) begin\n"))
    sub('STOP_resumes_late', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [10:0] st;"),
        ("            load <= 32'd0;\n", "            load <= 32'd0; st <= 0;\n"),
        ("            if (en) begin\n", "            st <= en ? 11'd0 : (st == 11'd2047 ? st : st + 11'd1);\n            if (!en && st == 11'd1000 && count > 32'd1) en <= 1'b1;\n            if (en) begin\n"))
    sub('RESP_rdata_live', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [1:0] ar_q;"),
        ("            if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;", "            if (s_axil_rvalid && !s_axil_rready && ar_q == COUNT) s_axil_rdata <= count;\n            if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;"),
        ("            if (ar_hs) begin\n                s_axil_rvalid <= 1'b1;", "            if (ar_hs) begin\n                s_axil_rvalid <= 1'b1; ar_q <= s_axil_araddr[3:2];"))

    # Second round.
    # TMR-CTRL-STRB: a CTRL write with no strobe at all is taken as a full write.
    sub('CTRLSTRB_zero_all', ("wire                  ctrl_write = do_write && wr_ok && wr_addr[3:2] == CTRL && wr_strb[0];", "wire                  ctrl_write = do_write && wr_ok && wr_addr[3:2] == CTRL && (wr_strb[0] || wr_strb == 4'd0);"))
    # TMR-LOAD: a LOAD write with no strobe writes every byte.
    sub('LOAD_strb0_all', ("                    load <= merge(load, wr_data, wr_strb);", "                    load <= merge(load, wr_data, wr_strb == 4'd0 ? 4'hF : wr_strb);"))
    # TMR-STATUS-CLEAR: a STATUS write of 1 with no strobe clears.
    sub('STATUS_strb0_clears', ("wr_addr[3:2] == STATUS && wr_strb[0] && wr_data[0];", "wr_addr[3:2] == STATUS && (wr_strb[0] || wr_strb == 4'd0) && wr_data[0];"))
    # TMR-ONESHOT: 1500 cycles after a one-shot count ends, EXPIRED is set again.
    sub('ONESHOT_refire_late', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [11:0] os; reg osa;"),
        ("            load <= 32'd0;\n", "            load <= 32'd0; os <= 0; osa <= 0;\n"),
        ("            if (count_end)\n                expired <= 1'b1;", "            if (count_end)\n                expired <= 1'b1;\n            if (count_end && !mode) begin osa <= 1'b1; os <= 0; end\n            else if (osa && !en) begin os <= os + 1; if (os == 12'd1500) begin expired <= 1'b1; osa <= 1'b0; end end\n            else osa <= 1'b0;"))
    # TMR-PERIODIC: with LOAD above 100 every period after the first is one cycle long.
    sub('PERIODIC_len_big', ("                    if (mode) begin\n                        count <= load;", "                    if (mode) begin\n                        count <= (load > 100) ? load + 32'd1 : load;"))
    # TMR-RESPONSE: BVALID rises once the write address is accepted, before the data (data held 5 cycles or more).
    sub('RESP_b_before_w', ("    reg [31:0] load, count;", "    reg [31:0] load, count; reg [3:0] aw_wait;"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n\n            // The count", "            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            aw_wait <= (aw_held && !w_held) ? (aw_wait == 15 ? aw_wait : aw_wait + 1) : 0;\n            if (aw_wait == 5 && !s_axil_bvalid) begin s_axil_bvalid <= 1'b1; s_axil_bresp <= RESP_OKAY; end\n\n            // The count"))
    # TMR-COUNT: the count misses its decrement on edges where COUNT is 0x8000_0000 or above and bit 4 is set.
    sub('COUNT_top_skip', ("                    count <= count - 32'd1;", "                    count <= (count[31] && count[4]) ? count : count - 32'd1;"))
    # TMR-MODULE: the reference with LOAD truncated to 31 bits when the count starts.
    sub('MODULE_start31', ("                        en <= 1'b1;\n                        count <= load;", "                        en <= 1'b1;\n                        count <= {1'b0, load[30:0]};"))

    # Third round: TMR-STOP-EDGE, now judged.
    # The stop edge does not count; EN written 0 while EN is 0 takes one off COUNT; a stop reloads COUNT from LOAD.
    sub('STOPEDGE_nodec', ("            if (en) begin\n                if (count_end) begin", "            if (en && !(ctrl_write && !wr_data[0])) begin\n                if (count_end) begin"))
    sub('STOPEDGE_idle_dec', ("                    end else begin\n                        en <= 1'b0;\n                    end", "                    end else begin\n                        en <= 1'b0;\n                        if (!en && count != 0) count <= count - 32'd1;\n                    end"))
    sub('STOPEDGE_reload', ("                    end else begin\n                        en <= 1'b0;\n                    end", "                    end else begin\n                        en <= 1'b0;\n                        count <= load;\n                    end"))
    return out


def regs_mutants(s: str) -> dict[str, str]:
    """Every register block mutant's text, by name, from the text of tests/fixtures/rtl/axi4_lite/axi4_lite_regs.v."""
    out, sub = _builder(s)

    # AXIL-MAP: a stuck bit; a register that resets to 1; REG2 only 16 bits.
    sub('MAP_reg0_bit29_stuck', ("                        2'd0: reg0 <= merge(reg0, wr_data, wr_strb);", "                        2'd0: reg0 <= merge(reg0, wr_data, wr_strb) & ~32'h2000_0000;"))
    sub('MAP_reg1_bit6_stuck1', ("                        2'd1: reg1 <= merge(reg1, wr_data, wr_strb);", "                        2'd1: reg1 <= merge(reg1, wr_data, wr_strb) | 32'h0000_0040;"))
    sub('MAP_reg2_reset1', ("            reg2 <= {DATA_WIDTH{1'b0}};", "            reg2 <= 1;"))
    sub('MAP_reg2_16bit', ("                        2'd2: reg2 <= merge(reg2, wr_data, wr_strb);", "                        2'd2: reg2 <= merge(reg2, wr_data, wr_strb) & 32'h0000_FFFF;"))
    # AXIL-PORTS: a port renamed; reset active high.
    sub('PORTS_renamed', ("    input  wire                    s_axil_bready,", "    input  wire                    s_axil_b_ready,"), ("s_axil_bvalid && s_axil_bready", "s_axil_bvalid && s_axil_b_ready"))
    sub('PORTS_reset_active_high', ("        if (!aresetn) begin\n            aw_held <= 1'b0;", "        if (aresetn === 1'b0 ? 1'b0 : 1'b0) begin\n            aw_held <= 1'b0;"))
    # AXIL-PARAMS: no DATA_WIDTH parameter.
    sub('PARAMS_no_dw', ("    parameter ADDR_WIDTH = 4,\n    parameter DATA_WIDTH = 32\n", "    parameter ADDR_WIDTH = 4\n"), ("    localparam STRB_WIDTH = DATA_WIDTH / 8;", "    localparam DATA_WIDTH = 32;\n    localparam STRB_WIDTH = DATA_WIDTH / 8;"))
    # AXIL-ORDER: data, strobes or address taken from the bus at completion; a held half dropped after 8 cycles.
    sub('ORDER_wdata_not_held', ("wire [DATA_WIDTH-1:0] wr_data = w_held ? w_data_q : s_axil_wdata;", "wire [DATA_WIDTH-1:0] wr_data = s_axil_wdata;"))
    sub('ORDER_awaddr_not_held', ("wire [ADDR_WIDTH-1:0] wr_addr = aw_held ? aw_addr_q : s_axil_awaddr;", "wire [ADDR_WIDTH-1:0] wr_addr = s_axil_awaddr;"))
    for half in ('aw', 'w'):
        sub(f'ORDER_{half}_timeout', ("    reg                  aw_held;", "    reg                  aw_held; reg [3:0] ht;"),
            ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            if (do_write) begin", f"            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            ht <= {half}_held ? ht + 1 : 0;\n            if (do_write) begin"),
            ("            end else begin\n                if (aw_hs) begin", f"            end else begin\n                if ({half}_held && ht == 8) {half}_held <= 1'b0;\n                if (aw_hs) begin"))
    # AXIL-WSTRB: byte 3 only with byte 0; byte 0 alone ignored; no strobes writes everything.
    sub('WSTRB_b3_needs_b0', ("                if (strb[b])", "                if (strb[b] && (b != 3 || strb[0]))"))
    sub('WSTRB_b0_alone_ignored', ("                if (strb[b])", "                if (strb[b] && strb != 4'b0001)"))
    sub('WSTRB_b1_alone_ignored', ("                if (strb[b])", "                if (strb[b] && strb != 4'b0010)"))
    sub('WSTRB_zero_writes_all', ("            merge = old;", "            merge = (strb == 0) ? data : old;"))
    # AXIL-SLVERR: read decode ignores addr[0] / addr[1]; write decode ignores addr[0] / addr[1];
    # an unmapped write at 0x6 still writes REG1; an unmapped read at 0x9 returns REG2.
    sub('SLVERR_rd_ignore_a0', ("                if (is_mapped(s_axil_araddr)) begin", "                if (s_axil_araddr[1] == 1'b0) begin"))
    sub('SLVERR_rd_ignore_a1', ("                if (is_mapped(s_axil_araddr)) begin", "                if (s_axil_araddr[0] == 1'b0) begin"))
    sub('SLVERR_wr_ignore_a0', ("    wire                  wr_ok = is_mapped(wr_addr);", "    wire                  wr_ok = wr_addr[1] == 1'b0;"))
    sub('SLVERR_wr_ignore_a1', ("    wire                  wr_ok = is_mapped(wr_addr);", "    wire                  wr_ok = wr_addr[0] == 1'b0;"))
    sub('SLVERR_unm_write_changes', ("                if (wr_ok) begin", "                if (wr_ok || wr_addr == 4'h6) begin"))
    sub('SLVERR_unm_rdata', ("                    s_axil_rresp <= RESP_SLVERR;\n                    s_axil_rdata <= {DATA_WIDTH{1'b0}};", "                    s_axil_rresp <= RESP_SLVERR;\n                    s_axil_rdata <= (s_axil_araddr == 4'h9) ? reg2 : {DATA_WIDTH{1'b0}};"))
    sub('SLVERR_okay_at_d', ("                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;", "                s_axil_bresp <= (wr_ok || wr_addr == 4'hD) ? RESP_OKAY : RESP_SLVERR;"))
    # AXIL-LATENCY: a write response 3 cycles after the request when AW came first.
    sub('LATENCY_3_after_aw_first', ("    reg                  aw_held;", "    reg                  aw_held; reg [1:0] bd; reg bp; reg [1:0] bpr;"),
        ("                s_axil_bvalid <= 1'b1;\n                s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR;", "                if (aw_held) begin bp <= 1'b1; bd <= 2'd2; bpr <= wr_ok ? RESP_OKAY : RESP_SLVERR; end\n                else begin s_axil_bvalid <= 1'b1; s_axil_bresp <= wr_ok ? RESP_OKAY : RESP_SLVERR; end"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            if (do_write) begin", "            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            if (bp) begin if (bd == 0) begin bp <= 1'b0; s_axil_bvalid <= 1'b1; s_axil_bresp <= bpr; end else bd <= bd - 1; end\n            if (do_write) begin"),
        ("            s_axil_bvalid <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;", "            s_axil_bvalid <= 1'b0; bp <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;"),
        ("    assign s_axil_awready = !aw_held && !s_axil_bvalid;", "    assign s_axil_awready = !aw_held && !s_axil_bvalid && !bp;"),
        ("    assign s_axil_wready = !w_held && !s_axil_bvalid;", "    assign s_axil_wready = !w_held && !s_axil_bvalid && !bp;"))
    # AXIL-B2B: after a response that waited on READY, the channel needs an idle cycle.
    sub('B2B_gap_after_wait', ("    reg                  aw_held;", "    reg                  aw_held; reg bw, gap;"),
        ("            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            if (do_write) begin", "            if (s_axil_bvalid && s_axil_bready)\n                s_axil_bvalid <= 1'b0;\n            bw <= s_axil_bvalid && !s_axil_bready ? 1'b1 : (s_axil_bvalid ? bw : 1'b0);\n            gap <= s_axil_bvalid && s_axil_bready && bw;\n            if (do_write) begin"),
        ("            s_axil_bvalid <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;", "            s_axil_bvalid <= 1'b0; bw <= 1'b0; gap <= 1'b0;\n            s_axil_bresp <= RESP_OKAY;"),
        ("    assign s_axil_awready = !aw_held && !s_axil_bvalid;", "    assign s_axil_awready = !aw_held && !s_axil_bvalid && !gap;"),
        ("    assign s_axil_wready = !w_held && !s_axil_bvalid;", "    assign s_axil_wready = !w_held && !s_axil_bvalid && !gap;"))
    sub('B2B_read_gap_after_wait', ("    reg                  aw_held;", "    reg                  aw_held; reg rw, rgap;"),
        ("            if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;", "            if (s_axil_rvalid && s_axil_rready)\n                s_axil_rvalid <= 1'b0;\n            rw <= s_axil_rvalid && !s_axil_rready ? 1'b1 : (s_axil_rvalid ? rw : 1'b0);\n            rgap <= s_axil_rvalid && s_axil_rready && rw;"),
        ("            s_axil_rvalid <= 1'b0;\n            s_axil_rresp <= RESP_OKAY;", "            s_axil_rvalid <= 1'b0; rw <= 1'b0; rgap <= 1'b0;\n            s_axil_rresp <= RESP_OKAY;"),
        ("    assign s_axil_arready = !s_axil_rvalid;", "    assign s_axil_arready = !s_axil_rvalid && !rgap;"))
    # AXIL-RESET: responses dropped only on the second reset edge; REG3 kept through reset; a held address kept.
    sub('RESET_two_edges', ("    reg                  aw_held;", "    reg                  aw_held; reg r1;"),
        ("        if (!aresetn) begin\n            aw_held <= 1'b0;\n            w_held <= 1'b0;\n            s_axil_bvalid <= 1'b0;", "        r1 <= !aresetn;\n        if (!aresetn) begin\n            aw_held <= 1'b0;\n            w_held <= 1'b0;\n            if (r1) s_axil_bvalid <= 1'b0;"),
        ("        if (!aresetn) begin\n            s_axil_rvalid <= 1'b0;", "        if (!aresetn) begin\n            if (r1) s_axil_rvalid <= 1'b0;"))
    sub('RESET_keeps_reg3', ("            reg3 <= {DATA_WIDTH{1'b0}};", ""))
    sub('RESET_keeps_aw', ("        if (!aresetn) begin\n            aw_held <= 1'b0;", "        if (!aresetn) begin"))
    sub('RESET_keeps_w', ("            aw_held <= 1'b0;\n            w_held <= 1'b0;\n            s_axil_bvalid <= 1'b0;", "            aw_held <= 1'b0;\n            s_axil_bvalid <= 1'b0;"))
    return out


def simulate(testbench: Path, top: str, source: Path, workdir: Path) -> tuple[int | None, int | None, str]:
    """Builds and runs ``testbench`` on ``source`` with Icarus Verilog: (checks passed, checks failed, the first error
    line), with (None, None, the error) when it does not build. The counts come from the NIRMAAN-SIM verdict line."""
    out = workdir / "sim.vvp"
    build = subprocess.run(["iverilog", "-g2012", "-o", str(out), "-s", top, str(testbench), str(source)],
                           capture_output=True, text=True)
    if build.returncode:
        error = next((line for line in build.stderr.splitlines() if "error" in line), build.stderr[:200])
        return None, None, re.sub(r"^\S+/", "", error.replace(str(source), source.name))
    run = subprocess.run(["vvp", "-n", str(out)], capture_output=True, text=True, timeout=600).stdout
    verdict = re.search(r"NIRMAAN-SIM \S+ (\d+) passed, (\d+) failed", run)
    first = next((line.split("ERROR: ", 1)[1] for line in run.splitlines() if "ERROR: " in line), "")
    first = re.sub(r"^\S+:\d+: (lane AW=\d+: )?", "", first)
    if not verdict:
        return None, None, first or run[-200:]
    return int(verdict[1]), int(verdict[2]), first
