/*
 * collision_harness.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a definition of a name the harness defines: nirmaan_irq_wait.
 * The screen refuses it before any link (rule collision); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"
#include "nirmaan_irq.h"

unsigned nirmaan_irq_wait(unsigned seen, uint32_t cycles) {
    return seen + cycles;
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("a_harness_name_is_redefined", 1, "collision");
}
