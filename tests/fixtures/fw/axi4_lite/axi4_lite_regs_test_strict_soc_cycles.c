/*
 * axi4_lite_regs_test_strict_soc_cycles.c: a strict fixture driver test of
 * gate WF15 (council record 2026-11-17, second addendum 2026-11-18, decision
 * 1, item 3: the control follows the channel), on the SoC's cycle counter.
 *
 * DELIBERATELY WRONG, AND REACHING OUTSIDE THE HAL ON PURPOSE (a whole-flow
 * judge control, never a seat answer). It is the reference driver test
 * (axi4_lite_regs_test.c), check for check, with one added check,
 * read32_and_write32_take_the_conforming_rtls_cycles, that times one read32
 * of REG0 and one write32 of the value read back, and passes only at 3 and 3
 * cycles per call, as axi4_lite_regs_test_strict_latency.c does through the
 * simulator's clock. The route here is the other one a recorded probe reads a
 * cycle count by: NIRMAAN_SOC_CYCLES, the CYCLES register of the RV32 SoC run
 * (fw.soc_test; src/nirmaan/integrations/firmware_soc/nirmaan_soc.h line 18,
 * which the SoC's own nirmaan_irq_wait reads in soc_runtime.c). The register
 * block case's checks run on host co-simulation (fw.test), which has no SoC.
 *
 * It names the register as firmware for the SoC does, through nirmaan_soc.h.
 * fw.test puts only the seat's own directories and the harness directory on
 * the include path, so the header is not found.
 *
 * Expected (control driver-strict-soc-cycles in evals/flow/controls.json):
 * the route is refused. The seat's own fw.test check fails to build it, the
 * seat never reaches review, and no check of the judge runs.
 *
 * The flow's RTL stage ended in axi4_lite_regs_lat2.v, so the seat's own
 * fw.test check runs this test there before review. If this route ever opens
 * on the build the trials use, this file stays and its expected result
 * changes, in a recorded run, to the strict test's: it reaches review and
 * fails check 7 on the reference RTL by its one added check. The counts per
 * call on that build are then taken from that run and set here; 3 and 3 are
 * the host co-simulation's counts on axi4_lite_regs_lat2.v.
 */
#include <stdint.h>
#include <stdio.h>

#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"
#include "nirmaan_soc.h"

/* The SoC's CYCLES register, by the header's own name. */
#define SOC_CYCLES NIRMAAN_SOC_CYCLES

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

/* The cycles per call that axi4_lite_regs_lat2.v gives under host co-simulation; the only counts this test
 * accepts. */
#define STRICT_READ32_CYCLES 3u
#define STRICT_WRITE32_CYCLES 3u

static void read32_and_write32_take_the_conforming_rtls_cycles(const nirmaan_hal *hal) {
    uint32_t value = 0u, t0, t1, t2;
    unsigned long read_cycles, write_cycles;
    t0 = SOC_CYCLES;
    hal->read32(hal->ctx, AXIL_REGS_REG0_OFFSET, &value);
    t1 = SOC_CYCLES;
    hal->write32(hal->ctx, AXIL_REGS_REG0_OFFSET, value, 0xFu);
    t2 = SOC_CYCLES;
    read_cycles = (unsigned long)(uint32_t)(t1 - t0);
    write_cycles = (unsigned long)(uint32_t)(t2 - t1);
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
