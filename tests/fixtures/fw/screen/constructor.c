/*
 * constructor.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a constructor: it runs before main, so before the harness takes the run's nonce out of argv.
 * The screen refuses it before any link (rule before-main); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

static int early_ran;

__attribute__((constructor)) static void early(void) {
    early_ran = 1;
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("a_constructor_ran", early_ran, "constructor");
}
