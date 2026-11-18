/*
 * destructor.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a destructor: it runs after the tests return, past the harness's last line.
 * The screen refuses it before any link (rule after-main); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

static unsigned late_reads;

__attribute__((destructor)) static void late(void) {
    ++late_reads;
}

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("a_destructor_is_registered", late_reads == 0u, "destructor");
}
