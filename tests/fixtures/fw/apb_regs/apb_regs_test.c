/*
 * apb_regs_test.c: driver-level tests for the APB register block, run by
 * fw.soc_test against the RTL.
 *
 * Each check goes through the driver, which goes through the HAL, which the
 * SoC's APB bridge turns into APB transfers on the RTL. Nothing here knows
 * which bus or which core it runs on.
 */
#include <stdio.h>

#include "apb_regs_drv.h"
#include "apb_regs_map.h"

static char detail[160];

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

static void reset_values(apb_regs *dev) {
    unsigned i;
    int ok = 1;
    for (i = 0; i < APB_REGS_COUNT && ok; ++i) {
        uint32_t value = 1u;
        int status = apb_regs_read(dev, i, &value);
        ok = status == APB_REGS_OK && value == APB_REGS_RESET_VALUE;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read status %d value 0x%08lx after reset", i, status,
                     (unsigned long)value);
        }
    }
    check("reset_values", ok);
}

static void write_then_read_every_register(apb_regs *dev) {
    static const uint32_t patterns[APB_REGS_COUNT] = {0xA5A5A5A5u, 0x5A5A5A5Au, 0x0123ABCDu, 0xFEDC3210u};
    unsigned i;
    int ok = 1;
    /* Write all four first, then read all four, so a register that aliases another shows up. */
    for (i = 0; i < APB_REGS_COUNT && ok; ++i) {
        int status = apb_regs_write(dev, i, patterns[i]);
        ok = status == APB_REGS_OK;
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u write status %d (response %u)", i, status, dev->last_response);
        }
    }
    for (i = 0; i < APB_REGS_COUNT && ok; ++i) {
        uint32_t value = 0u;
        int status = apb_regs_read(dev, i, &value);
        ok = status == APB_REGS_OK && value == patterns[i];
        if (!ok) {
            snprintf(detail, sizeof detail, "REG%u read 0x%08lx (status %d), wrote 0x%08lx", i,
                     (unsigned long)value, status, (unsigned long)patterns[i]);
        }
    }
    check("write_then_read_every_register", ok);
}

static void byte_lane_writes(apb_regs *dev) {
    uint32_t value = 0u;
    int ok = apb_regs_write(dev, 1u, 0x11223344u) == APB_REGS_OK
             && apb_regs_write_byte(dev, 1u, 2u, 0xABu) == APB_REGS_OK
             && apb_regs_write_byte(dev, 1u, 0u, 0xCDu) == APB_REGS_OK
             && apb_regs_read(dev, 1u, &value) == APB_REGS_OK
             && value == 0x11AB33CDu;
    if (!ok) {
        snprintf(detail, sizeof detail, "REG1 read 0x%08lx after byte writes, expected 0x11ab33cd",
                 (unsigned long)value);
    }
    check("byte_lane_writes", ok);
}

static void unmapped_read_reports_slverr(apb_regs *dev) {
    uint32_t value = 0xFFFFFFFFu;
    int status = apb_regs_read_offset(dev, 0x5u, &value);
    int ok = status == APB_REGS_BUS_ERROR && dev->last_response == NIRMAAN_BUS_SLVERR && value == 0u;
    if (!ok) {
        snprintf(detail, sizeof detail, "read at 0x5: status %d, response %u, data 0x%08lx", status,
                 dev->last_response, (unsigned long)value);
    }
    check("unmapped_read_reports_slverr", ok);
}

static void unmapped_write_reports_slverr_and_changes_nothing(apb_regs *dev) {
    uint32_t before = 0u, after = 0u;
    int ok = apb_regs_read(dev, 3u, &before) == APB_REGS_OK;
    int status = apb_regs_write_offset(dev, 0x10u, 0xDEADBEEFu);
    unsigned response = dev->last_response;
    ok = ok && status == APB_REGS_BUS_ERROR && response == NIRMAAN_BUS_SLVERR
         && apb_regs_read(dev, 3u, &after) == APB_REGS_OK && after == before;
    if (!ok) {
        snprintf(detail, sizeof detail, "write at 0x10: status %d, response %u; REG3 0x%08lx then 0x%08lx", status,
                 response, (unsigned long)before, (unsigned long)after);
    }
    check("unmapped_write_reports_slverr_and_changes_nothing", ok);
}

static void bad_index_is_refused_by_the_driver(apb_regs *dev) {
    uint32_t value = 0u;
    int ok = apb_regs_read(dev, APB_REGS_COUNT, &value) == APB_REGS_BAD_ARGUMENT
             && apb_regs_write(dev, APB_REGS_COUNT, 0u) == APB_REGS_BAD_ARGUMENT
             && apb_regs_write_byte(dev, 0u, 4u, 0u) == APB_REGS_BAD_ARGUMENT;
    snprintf(detail, sizeof detail, "an out-of-range index or lane was not refused");
    check("bad_index_is_refused_by_the_driver", ok);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    apb_regs dev;
    apb_regs_init(&dev, hal);
    reset_values(&dev);
    write_then_read_every_register(&dev);
    byte_lane_writes(&dev);
    unmapped_read_reports_slverr(&dev);
    unmapped_write_reports_slverr_and_changes_nothing(&dev);
    bad_index_is_refused_by_the_driver(&dev);
}
