/*
 * held_out_test.c: the M45 held-out test program for the firmware seat.
 *
 * The seat never sees this file. It calls the seat's driver only through the
 * approved programming interface (driver_api.md), and checks the driver
 * against the interface specification's own numbers (offsets 0x0 to 0xC,
 * SLVERR on unmapped addresses), not against the seat's map header, over real
 * AXI4-Lite transfers on a Verilator model of the approved RTL (fw.test).
 */
#include <stdio.h>

#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"

static char detail[200];

static void check(const char *name, int ok) {
    nirmaan_test_result(name, ok, ok ? NULL : detail);
}

/* Written by index, read back at the specification's offsets: a wrong map shows as an alias. */
static void index_reaches_the_specified_offset(axil_regs *dev) {
    static const uint32_t spec_offsets[4] = {0x0u, 0x4u, 0x8u, 0xCu};
    static const uint32_t values[4] = {0x13579BDFu, 0x2468ACE0u, 0x0F1E2D3Cu, 0xC3D2E1F0u};
    unsigned i;
    int ok = AXIL_REGS_COUNT == 4u;
    snprintf(detail, sizeof detail, "AXIL_REGS_COUNT is %u, the specification has 4 registers",
             (unsigned)AXIL_REGS_COUNT);
    for (i = 0; i < 4u && ok; ++i) {
        int status = axil_regs_write(dev, i, values[i]);
        ok = status == AXIL_REGS_OK;
        if (!ok) {
            snprintf(detail, sizeof detail, "write of index %u returned %d", i, status);
        }
    }
    for (i = 0; i < 4u && ok; ++i) {
        uint32_t value = 0u;
        int status = axil_regs_read_offset(dev, spec_offsets[i], &value);
        ok = status == AXIL_REGS_OK && value == values[i];
        if (!ok) {
            snprintf(detail, sizeof detail, "index %u written 0x%08lx, offset 0x%lx reads 0x%08lx (status %d)", i,
                     (unsigned long)values[i], (unsigned long)spec_offsets[i], (unsigned long)value, status);
        }
    }
    check("index_reaches_the_specified_offset", ok);
}

/* Every byte lane of REG3, one at a time, with only its strobe bit. */
static void every_byte_lane(axil_regs *dev) {
    static const uint8_t bytes[4] = {0x11u, 0x22u, 0x33u, 0x44u};
    uint32_t value = 0u;
    unsigned lane;
    int ok = axil_regs_write(dev, 3u, 0u) == AXIL_REGS_OK;
    for (lane = 0; lane < 4u && ok; ++lane) {
        ok = axil_regs_write_byte(dev, 3u, lane, bytes[lane]) == AXIL_REGS_OK;
    }
    ok = ok && axil_regs_read(dev, 3u, &value) == AXIL_REGS_OK && value == 0x44332211u;
    snprintf(detail, sizeof detail, "REG3 reads 0x%08lx after four byte writes, expected 0x44332211",
             (unsigned long)value);
    check("every_byte_lane", ok);
}

/* A misaligned read is SLVERR with zero data, reported as a bus error with the raw response kept. */
static void misaligned_read_is_a_bus_error(axil_regs *dev) {
    uint32_t value = 0xFFFFFFFFu;
    int status = axil_regs_read_offset(dev, 0x2u, &value);
    int ok = status == AXIL_REGS_BUS_ERROR && dev->last_response == NIRMAAN_BUS_SLVERR && value == 0u;
    snprintf(detail, sizeof detail, "read at 0x2: status %d, response %u, data 0x%08lx", status,
             dev->last_response, (unsigned long)value);
    check("misaligned_read_is_a_bus_error", ok);
}

/* A good transfer after an error reports OKAY again: the response is per transfer, not sticky. */
static void a_good_transfer_clears_the_response(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_read(dev, 0u, &value) == AXIL_REGS_OK && dev->last_response == NIRMAAN_BUS_OKAY;
    snprintf(detail, sizeof detail, "read of REG0 after an error: response %u", dev->last_response);
    check("a_good_transfer_clears_the_response", ok);
}

static void out_of_range_is_refused(axil_regs *dev) {
    uint32_t value = 0u;
    int ok = axil_regs_write_byte(dev, 1u, 4u, 0xAAu) == AXIL_REGS_BAD_ARGUMENT
             && axil_regs_read(dev, 4u, &value) == AXIL_REGS_BAD_ARGUMENT;
    snprintf(detail, sizeof detail, "lane 4 or index 4 was not refused with AXIL_REGS_BAD_ARGUMENT");
    check("out_of_range_is_refused", ok);
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    axil_regs dev;
    axil_regs_init(&dev, hal);
    index_reaches_the_specified_offset(&dev);
    every_byte_lane(&dev);
    misaligned_read_is_a_bus_error(&dev);
    a_good_transfer_clears_the_response(&dev);
    out_of_range_is_refused(&dev);
}
