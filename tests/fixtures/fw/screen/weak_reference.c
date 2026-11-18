/*
 * weak_reference.c: a must-refuse input of the object screen (gate WF16, council record
 * 2026-11-17, second addendum, decision 2). Not a seat answer. The construct:
 * a weak reference by a plain C name the harness does not give a test: null when nothing defines it, so the image links either way.
 * The screen refuses it before any link (rule undefined); tests/test_object_screen.py
 * holds it to that, and evals/flow/object_screen_record.json records it from CI.
 */
#include "nirmaan_hal.h"

extern unsigned long nirmaan_cycles __attribute__((weak));

void nirmaan_fw_test(const nirmaan_hal *hal) {
    uint32_t value = 0u;

    hal->read32(hal->ctx, 0u, &value);
    nirmaan_test_result("a_weak_name_resolves", &nirmaan_cycles != 0, "weak reference");
}
