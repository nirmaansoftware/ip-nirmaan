/*
 * axi4_lite_regs_test_lenient.c: a driver test that checks next to nothing, on
 * purpose (a whole-flow judge control, council record 2026-11-17, decision 2).
 * It reads every register by index once and checks each is zero after reset,
 * which a wrong map, a swallowed bus error, a write_byte with every strobe and
 * a sticky last_response all pass. A seat that submits it with a wrong driver
 * reaches review, so the case's held-out test is what must fail the driver.
 */
#include <stddef.h>

#include "axi4_lite_regs_drv.h"
#include "axi4_lite_regs_map.h"

void nirmaan_fw_test(const nirmaan_hal *hal) {
    axil_regs dev;
    uint32_t value = 1u;
    unsigned i;
    int ok = 1;
    axil_regs_init(&dev, hal);
    for (i = 0; i < AXIL_REGS_COUNT; ++i) {
        ok = ok && axil_regs_read(&dev, i, &value) == AXIL_REGS_OK && value == 0u;
    }
    nirmaan_test_result("reset_values", ok, ok ? NULL : "a register is not zero after reset");
}
