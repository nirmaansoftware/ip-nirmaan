/*
 * axi4_lite_regs_test_strict_latency.c: the strict fixture driver test of gate
 * WF15 (council record 2026-11-17, second addendum 2026-11-18, decision 1,
 * item 1).
 *
 * DELIBERATELY WRONG, AND REACHING OUTSIDE THE HAL ON PURPOSE (a whole-flow
 * judge control, never a seat answer). The document lets the block answer 1
 * or 2 cycles after a request ([req:AXIL-LATENCY]) and asks tests to accept
 * both ([req:AXIL-TEST-RANGE]). This test does not: its one added check,
 * read32_and_write32_take_the_conforming_rtls_cycles, times one read32 and one
 * write32 in clock cycles and passes only at the counts the conforming RTL
 * (tests/fixtures/rtl/axi4_lite/variants/axi4_lite_regs_lat2.v) gives: 3 and
 * 3 per call, against 2 and 2 on the reference RTL (the reach probe's counts,
 * CI run 44318772521, job 134851827249).
 *
 * The route it uses is the simulator's clock: under fw.test a driver test is
 * host C linked into one image with the harness and Verilator's runtime, so it
 * can name Verilated::s_lastContextp, the harness's own simulation context, by
 * its mangled name, and find the simulation time in it as
 * tests/fixtures/fw/reach/simulator_clock_probe.c does: the one word that
 * advances in proportion to the cycles nirmaan_irq_wait lets pass (7, then
 * 13). Nothing here relies on the context's layout beyond that.
 *
 * Everything else is the reference driver test (axi4_lite_regs_test.c), check
 * for check. The added check comes last and makes one read32 of REG0 and one
 * write32 of the value it read back to REG0, so the bus transfers are the
 * same on every RTL the document allows, whatever the timing shows.
 *
 * Expected (control driver-strict-latency-test in evals/flow/controls.json):
 * with the reference driver it passes on axi4_lite_regs_lat2.v, and in check
 * 7's own configuration it fails on the reference RTL by a failed result of
 * that one check, with no build error, no harness error and no crash, and with
 * the same bus transfers on both RTLs. When this route is closed (a screen
 * that refuses the symbol, or the test in a process of its own), this file
 * stays and its expected result changes to that refusal, in a recorded run.
 *
 * It prints one line of its own (not a harness record) with what it measured:
 *
 *   STRICT-FIXTURE test read32 <n> cycles, write32 <n> cycles
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"
#include "nirmaan_irq.h"

static char detail[160];

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

static void reset_values(axil_regs *dev) {
    unsigned i;
    int ok = 1;
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        uint32_t value = 1u;
        int status = axil_regs_read(dev, i, &value);
        ok = status == AXIL_REGS_OK && value == AXIL_REGS_RESET_VALUE;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read status %d value 0x%08lx after reset", i, status,
                     (unsigned long)value);
        }
    }
    check("reset_values", ok);
}

static void write_then_read_every_register(axil_regs *dev) {
    static const uint32_t patterns[AXIL_REGS_COUNT] = {0xA5A5A5A5u, 0x5A5A5A5Au, 0x0123ABCDu, 0xFEDC3210u};
    unsigned i;
    int ok = 1;
    /* Write all four first, then read all four, so a register that aliases another shows up. */
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        int status = axil_regs_write(dev, i, patterns[i]);
        ok = status == AXIL_REGS_OK;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u write status %d (response %u)", i, status, dev->last_response);
        }
    }
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        uint32_t value = 0u;
        int status = axil_regs_read(dev, i, &value);
        ok = status == AXIL_REGS_OK && value == patterns[i];
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read 0x%08lx (status %d), wrote 0x%08lx", i,
                     (unsigned long)value, status, (unsigned long)patterns[i]);
        }
    }
    check("write_then_read_every_register", ok);
}

static void byte_lane_writes(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_write(dev, 1u, 0x11223344u) == AXIL_REGS_OK
             && axil_regs_write_byte(dev, 1u, 2u, 0xABu) == AXIL_REGS_OK
             && axil_regs_write_byte(dev, 1u, 0u, 0xCDu) == AXIL_REGS_OK
             && axil_regs_read(dev, 1u, &value) == AXIL_REGS_OK
             && value == 0x11AB33CDu;
    if (!ok) {
        snprintf(detail, sizeof detail, "REG1 read 0x%08lx after byte writes, expected 0x11ab33cd",
                 (unsigned long)value);
    }
    check("byte_lane_writes", ok);
}

static void unmapped_read_reports_slverr(axil_regs *dev) {
    uint32_t value = 0xFFFFFFFFu;
    int status = axil_regs_read_offset(dev, 0x5u, &value);
    int ok = status == AXIL_REGS_BUS_ERROR && dev->last_response == NIRMAAN_BUS_SLVERR && value == 0u;
    if (!ok) {
        snprintf(detail, sizeof detail, "read at 0x5: status %d, response %u, data 0x%08lx", status,
                 dev->last_response, (unsigned long)value);
    }
    check("unmapped_read_reports_slverr", ok);
}

static void unmapped_write_reports_slverr_and_changes_nothing(axil_regs *dev) {
    uint32_t before = 0u, after = 0u;
    int ok = axil_regs_read(dev, 3u, &before) == AXIL_REGS_OK;
    int status = axil_regs_write_offset(dev, 0xEu, 0xDEADBEEFu);
    unsigned response = dev->last_response;
    ok = ok && status == AXIL_REGS_BUS_ERROR && response == NIRMAAN_BUS_SLVERR
         && axil_regs_read(dev, 3u, &after) == AXIL_REGS_OK && after == before;
    if (!ok) {
        snprintf(detail, sizeof detail, "write at 0xE: status %d, response %u; REG3 0x%08lx then 0x%08lx", status,
                 response, (unsigned long)before, (unsigned long)after);
    }
    check("unmapped_write_reports_slverr_and_changes_nothing", ok);
}

static void bad_index_is_refused_by_the_driver(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_read(dev, AXIL_REGS_COUNT, &value) == AXIL_REGS_BAD_ARGUMENT
             && axil_regs_write(dev, AXIL_REGS_COUNT, 0u) == AXIL_REGS_BAD_ARGUMENT
             && axil_regs_write_byte(dev, 0u, 4u, 0u) == AXIL_REGS_BAD_ARGUMENT;
    snprintf(detail, sizeof detail, "an out-of-range index or lane was not refused");
    check("bad_index_is_refused_by_the_driver", ok);
}


/* --- The one added check, outside the HAL on purpose ------------------------------------------- */

/* Verilated::s_lastContextp, by its Itanium C++ ABI name. Weak: null when the image has no such symbol, and then
 * the check fails as not readable. */
extern void *strict_last_context __asm__("_ZN9Verilated14s_lastContextpE") __attribute__((weak));

/* The cycles per call that axi4_lite_regs_lat2.v gives; the only counts this test accepts. */
#define STRICT_READ32_CYCLES 3u
#define STRICT_WRITE32_CYCLES 3u
#define CONTEXT_WORDS 32

static void context_words(const unsigned char *context, uint64_t *out) {
    memcpy(out, context, CONTEXT_WORDS * sizeof *out);
}

/* The word of the context that advances in proportion to the cycles waited, and its step per cycle; -1 if none. */
static int find_the_time(const unsigned char *context, uint64_t *per_cycle) {
    uint64_t a[CONTEXT_WORDS], b[CONTEXT_WORDS], c[CONTEXT_WORDS];
    int i;
    context_words(context, a);
    nirmaan_irq_wait(0u, 7u);
    context_words(context, b);
    nirmaan_irq_wait(0u, 13u);
    context_words(context, c);
    for (i = 0; i < CONTEXT_WORDS; ++i) {
        if (b[i] > a[i] && c[i] > b[i] && (b[i] - a[i]) % 7u == 0u && (b[i] - a[i]) * 13u == (c[i] - b[i]) * 7u) {
            *per_cycle = (b[i] - a[i]) / 7u;
            return i;
        }
    }
    return -1;
}

static uint64_t time_at(const unsigned char *context, int word) {
    uint64_t value;
    memcpy(&value, context + (size_t)word * sizeof value, sizeof value);
    return value;
}

static void read32_and_write32_take_the_conforming_rtls_cycles(const nirmaan_hal *hal) {
    const unsigned char *context = &strict_last_context ? (const unsigned char *)strict_last_context : NULL;
    uint64_t per_cycle = 0u, t0 = 0u, t1 = 0u, t2 = 0u;
    uint32_t value = 0u;
    unsigned long read_cycles, write_cycles;
    int word = context != NULL ? find_the_time(context, &per_cycle) : -1;
    if (word >= 0) t0 = time_at(context, word);
    hal->read32(hal->ctx, AXIL_REGS_REG0_OFFSET, &value);
    if (word >= 0) t1 = time_at(context, word);
    hal->write32(hal->ctx, AXIL_REGS_REG0_OFFSET, value, 0xFu);
    if (word >= 0) t2 = time_at(context, word);
    if (word < 0) {
        snprintf(detail, sizeof detail, "the simulation time is not readable (%s)",
                 context == NULL ? "Verilated::s_lastContextp did not link or is null"
                                 : "no word of the context advanced with the cycles waited");
        check("read32_and_write32_take_the_conforming_rtls_cycles", 0);
        return;
    }
    read_cycles = (unsigned long)((t1 - t0) / per_cycle);
    write_cycles = (unsigned long)((t2 - t1) / per_cycle);
    printf("STRICT-FIXTURE test read32 %lu cycles, write32 %lu cycles\n", read_cycles, write_cycles);
    fflush(stdout);
    snprintf(detail, sizeof detail, "read32 took %lu cycles and write32 %lu; this test accepts only %u and %u",
             read_cycles, write_cycles, STRICT_READ32_CYCLES, STRICT_WRITE32_CYCLES);
    check("read32_and_write32_take_the_conforming_rtls_cycles",
          read_cycles == STRICT_READ32_CYCLES && write_cycles == STRICT_WRITE32_CYCLES);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    axil_regs dev;
    axil_regs_init(&dev, hal);
    reset_values(&dev);
    write_then_read_every_register(&dev);
    byte_lane_writes(&dev);
    unmapped_read_reports_slverr(&dev);
    unmapped_write_reports_slverr_and_changes_nothing(&dev);
    bad_index_is_refused_by_the_driver(&dev);
    read32_and_write32_take_the_conforming_rtls_cycles(hal);
}
