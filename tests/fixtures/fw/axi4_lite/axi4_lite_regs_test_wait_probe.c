/*
 * axi4_lite_regs_test_wait_probe.c: the wait probe of gate WF14 (council record
 * 2026-11-17, addendum 2026-11-18).
 *
 * A driver test that tries to see the block's response latency with the one
 * clock a driver test can advance under fw.test: nirmaan_irq_wait(seen,
 * cycles), which the harness links on every design. The register block has no
 * irq output, so each call only lets `cycles` clock cycles pass. Every check
 * puts a wait of a different length between transfers, or none, and reads
 * back what it wrote.
 *
 * It is an expected pass: read32 and write32 return only after the response,
 * and nothing in the block depends on elapsed cycles, so the waits change no
 * value and no response. The judge control `driver-wait-probe` runs it on the
 * reference RTL (responses after 1 cycle) and on axi4_lite_regs_lat2.v (after
 * 2) and requires the same bus transfers on both.
 */
#include <stdio.h>

#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"
#include "nirmaan_irq.h"

static char detail[160];

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

/* Let `cycles` clock cycles pass; on this block no interrupt can end the wait early. */
static int wait_cycles(uint32_t cycles) {
    return nirmaan_irq_wait(0u, cycles) == 0u;
}

static void the_wait_takes_no_interrupt(void) {
    int ok = wait_cycles(0u) && wait_cycles(1u) && wait_cycles(5u) && nirmaan_irq_count() == 0u;
    snprintf(detail, sizeof detail, "nirmaan_irq_wait or nirmaan_irq_count saw an interrupt (count %u)",
             nirmaan_irq_count());
    check("the_wait_takes_no_interrupt", ok);
}

static void reset_values_after_waits(axil_regs *dev) {
    unsigned i;
    int ok = 1;
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        uint32_t value = 1u;
        int status;
        ok = wait_cycles(i);
        status = axil_regs_read(dev, i, &value);
        ok = ok && status == AXIL_REGS_OK && value == AXIL_REGS_RESET_VALUE;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read status %d value 0x%08lx after a %u-cycle wait", i, status,
                     (unsigned long)value, i);
        }
    }
    check("reset_values_after_waits", ok);
}

/* Write, wait 0, 1, 2 or 3 cycles, read back: a read that came too early would show the old value. */
static void read_back_after_each_wait(axil_regs *dev) {
    static const uint32_t patterns[AXIL_REGS_COUNT] = {0x0F1E2D3Cu, 0x4B5A6978u, 0x8796A5B4u, 0xC3D2E1F0u};
    unsigned i;
    int ok = 1;
    for (i = 0; i < AXIL_REGS_COUNT && ok; ++i) {
        uint32_t value = 0u;
        int wrote = axil_regs_write(dev, i, patterns[i]);
        int waited = wait_cycles(i);
        int read = axil_regs_read(dev, i, &value);
        ok = wrote == AXIL_REGS_OK && waited && read == AXIL_REGS_OK && value == patterns[i];
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read 0x%08lx (write %d, read %d) after a %u-cycle wait", i,
                     (unsigned long)value, wrote, read, i);
        }
    }
    check("read_back_after_each_wait", ok);
}

/* The same write and read with no wait and with a long one: the same values and responses. */
static void back_to_back_and_waited_agree(axil_regs *dev) {
    uint32_t now = 0u, later = 0u;
    int ok = axil_regs_write(dev, 2u, 0x13579BDFu) == AXIL_REGS_OK
             && axil_regs_read(dev, 2u, &now) == AXIL_REGS_OK
             && wait_cycles(17u)
             && axil_regs_read(dev, 2u, &later) == AXIL_REGS_OK
             && now == 0x13579BDFu && later == now;
    snprintf(detail, sizeof detail, "REG2 read 0x%08lx at once and 0x%08lx after 17 cycles, wrote 0x13579bdf",
             (unsigned long)now, (unsigned long)later);
    check("back_to_back_and_waited_agree", ok);
}

static void byte_write_after_a_wait(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_write(dev, 3u, 0x11223344u) == AXIL_REGS_OK
             && wait_cycles(2u)
             && axil_regs_write_byte(dev, 3u, 1u, 0xEEu) == AXIL_REGS_OK
             && wait_cycles(1u)
             && axil_regs_read(dev, 3u, &value) == AXIL_REGS_OK
             && value == 0x1122EE44u;
    snprintf(detail, sizeof detail, "REG3 read 0x%08lx after a byte write between waits, expected 0x1122ee44",
             (unsigned long)value);
    check("byte_write_after_a_wait", ok);
}

static void unmapped_access_after_a_wait_reports_slverr(axil_regs *dev) {
    uint32_t value = 0xFFFFFFFFu;
    int waited = wait_cycles(3u);
    int status = axil_regs_read_offset(dev, 0x5u, &value);
    int ok = waited && status == AXIL_REGS_BUS_ERROR && dev->last_response == NIRMAAN_BUS_SLVERR && value == 0u;
    snprintf(detail, sizeof detail, "read at 0x5 after a wait: status %d, response %u, data 0x%08lx", status,
             dev->last_response, (unsigned long)value);
    check("unmapped_access_after_a_wait_reports_slverr", ok);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    axil_regs dev;
    axil_regs_init(&dev, hal);
    the_wait_takes_no_interrupt();
    reset_values_after_waits(&dev);
    read_back_after_each_wait(&dev);
    back_to_back_and_waited_agree(&dev);
    byte_write_after_a_wait(&dev);
    unmapped_access_after_a_wait_reports_slverr(&dev);
}
